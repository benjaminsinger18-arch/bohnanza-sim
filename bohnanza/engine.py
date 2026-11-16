"""Game engine: enforces the rules, asks bots for decisions, records stats."""
import random
from collections import Counter

from .bot import Bot
from .cards import build_deck, deck_counts, payout
from .rules import RuleSet, make_rules
from .state import Field, PlayerState, PlayerView, OpponentInfo, can_harvest_fields
from .trading import Deal, Offer, OfferView, Request

MAX_TRADE_ROUNDS = 10
MAX_OFFERS = 8
MAX_TURNS = 3000

STAT_KEYS = ("harvests", "harvest_cards", "harvest_coins", "forced_harvests", "trades",
             "trades_as_active", "cards_given", "cards_received", "gifts_given", "violations")


class IllegalAction(Exception):
    pass


class Game:
    """One game. Seat 0 is the starting player; turn order is seat 0, 1, 2, ..."""

    def __init__(self, bots: list[Bot], seed: int = 0, rules: "str | RuleSet" = "base",
                 verbose: bool = False, check: bool = True, strict: bool = False):
        n = len(bots)
        self.rules = rules if isinstance(rules, RuleSet) else make_rules(rules, n)
        self.n, self.bots, self.seed = n, bots, seed
        self.rng = random.Random(seed)
        self.check, self.strict = check, strict
        self.log_lines: list[str] | None = [] if verbose else None
        self.players = [PlayerState(seat=i, name=b.display_name,
                                    fields=[Field() for _ in range(self.rules.fields)])
                        for i, b in enumerate(bots)]
        self.counts = deck_counts(self.rules.beans)
        self.deck = build_deck(self.rules.beans)
        self.rng.shuffle(self.deck)
        self.discard: list[str] = []
        self.flipped: list[str] = []
        self.removed: Counter = Counter()
        self.exhaustions = 0
        self.ending = False
        self.active = 0
        self.turn = 0
        self.phase = 0
        self.trade_round = 0
        self.trades = 0
        for i, b in enumerate(bots):
            b.setup(i, n, random.Random(self.rng.getrandbits(64)))
        for p in self.players:
            for _ in range(self.rules.hand_size):
                p.hand.append(self.deck.pop())

    # ================================================================ helpers
    def log(self, msg: str) -> None:
        if self.log_lines is not None:
            self.log_lines.append(msg)

    @staticmethod
    def _ftup(q: PlayerState) -> tuple:
        return tuple((f.bean, f.count) for f in q.fields)

    def view(self, seat: int) -> PlayerView:
        p = self.players[seat]
        return PlayerView(
            seat=seat, num_players=self.n, active=self.active, phase=self.phase, turn=self.turn,
            trade_round=self.trade_round, hand=tuple(p.hand), fields=self._ftup(p), coins=p.coins,
            pending=tuple(p.pending),
            opponents=tuple(OpponentInfo(q.seat, q.name, self._ftup(q), q.coins, len(q.hand), tuple(q.pending))
                            for q in self.players if q.seat != seat),
            flipped=tuple(self.flipped), discard=tuple(self.discard), deck_size=len(self.deck),
            exhaustions=self.exhaustions, removed=dict(self.removed), deck_counts=dict(self.counts),
            rules=self.rules.name, end_exhaustions=self.rules.end_exhaustions)

    def violation(self, seat: int, msg: str) -> None:
        self.players[seat].stats["violations"] += 1
        self.log(f"   !! {self.players[seat].name} illegal: {msg}")
        if self.strict:
            raise IllegalAction(f"seat {seat}: {msg}")

    def ask(self, seat: int, method: str, *args):
        """Call a bot hook; on exception fall back to the Bot default."""
        bot = self.bots[seat]
        try:
            return getattr(bot, method)(*args)
        except IllegalAction:
            raise
        except Exception as e:  # noqa: BLE001 - bots are user code
            if self.strict:
                raise
            self.violation(seat, f"{method} raised {type(e).__name__}: {e}")
            return getattr(Bot, method)(bot, *args)

    def order_from(self, seat: int) -> list[int]:
        return [(seat + k) % self.n for k in range(self.n)]

    def draw(self) -> str | None:
        if self.ending:
            return None
        if not self.deck:
            if not self.discard:  # degenerate: nothing left anywhere
                self.ending = True
                return None
            self.deck, self.discard = self.discard, []
            self.rng.shuffle(self.deck)
        card = self.deck.pop()
        if not self.deck:
            self.exhaustions += 1
            self.log(f"-- draw pile ran out ({self.exhaustions}/{self.rules.end_exhaustions})")
            if self.exhaustions >= self.rules.end_exhaustions:
                self.ending = True
            else:
                self.deck, self.discard = self.discard, []
                self.rng.shuffle(self.deck)
        return card

    # ================================================================ fields
    def harvest(self, seat: int, idx: int, final: bool = False) -> None:
        p = self.players[seat]
        f = p.fields[idx]
        coins = payout(f.bean, f.count)
        p.coins += coins
        self.removed[f.bean] += coins
        self.discard.extend([f.bean] * (f.count - coins))
        if not final:
            p.stats["harvests"] += 1
            p.stats["harvest_cards"] += f.count
            p.stats["harvest_coins"] += coins
        self.log(f"   {p.name} harvests {f.count}x {f.bean} -> {coins} coin(s){' (final)' if final else ''}")
        f.bean, f.count = None, 0

    def legal_plant(self, seat: int, idx, bean: str) -> bool:
        p = self.players[seat]
        if not isinstance(idx, int) or isinstance(idx, bool) or not 0 <= idx < len(p.fields):
            return False
        f = p.fields[idx]
        if f.bean in (None, bean):
            return True
        return can_harvest_fields(self._ftup(p), idx)

    def plant(self, seat: int, bean: str) -> None:
        p = self.players[seat]
        idx = self.ask(seat, "choose_field", self.view(seat), bean)
        if not self.legal_plant(seat, idx, bean):
            self.violation(seat, f"choose_field({bean}) -> {idx!r}")
            idx = Bot.choose_field(self.bots[seat], self.view(seat), bean)
        f = p.fields[idx]
        if f.bean not in (None, bean):
            p.stats["forced_harvests"] += 1
            self.harvest(seat, idx)
        f.bean = bean
        f.count += 1
        self.log(f"   {p.name} plants {bean} in field {idx + 1} ({f.count})")

    def checkpoint(self) -> None:
        """Voluntary harvest opportunity for every player."""
        for seat in self.order_from(self.active):
            idxs = self.ask(seat, "maybe_harvest", self.view(seat))
            if not idxs:
                continue
            p = self.players[seat]
            for idx in list(idxs):
                fields = self._ftup(p)
                if isinstance(idx, int) and 0 <= idx < len(fields) and can_harvest_fields(fields, idx):
                    self.harvest(seat, idx)
                else:
                    self.violation(seat, f"maybe_harvest -> {idx!r}")

    # ================================================================ trading
    @staticmethod
    def _valid_idx(idxs, size: int) -> bool:
        return (isinstance(idxs, tuple) and len(set(idxs)) == len(idxs)
                and all(isinstance(i, int) and 0 <= i < size for i in idxs))

    def trade_phase(self) -> None:
        a = self.active
        ap = self.players[a]
        empty_rounds = 0
        for r in range(MAX_TRADE_ROUNDS):
            self.trade_round = r
            deals: list[Deal] = []
            offers = self.ask(a, "propose_offers", self.view(a)) or []
            for off in list(offers)[:MAX_OFFERS]:
                if not (isinstance(off, Offer) and self._valid_idx(tuple(off.give_flipped), len(self.flipped))
                        and self._valid_idx(tuple(off.give_hand), len(ap.hand))):
                    self.violation(a, f"bad offer {off!r}")
                    continue
                gives = tuple(self.flipped[i] for i in off.give_flipped) + tuple(ap.hand[i] for i in off.give_hand)
                want = tuple(off.want)
                if not gives and not want:
                    continue
                ov = OfferView(proposer=a, gives=gives, want=want)
                for seat in self.order_from(a)[1:]:
                    if off.to is not None and seat != off.to:
                        continue
                    resp = self.ask(seat, "respond_to_offer", self.view(seat), ov)
                    if resp is None:
                        continue
                    hand = self.players[seat].hand
                    resp = tuple(resp) if isinstance(resp, (list, tuple)) else resp
                    if not self._valid_idx(resp, len(hand)) or Counter(hand[i] for i in resp) != Counter(want):
                        self.violation(seat, f"respond_to_offer -> {resp!r}")
                        continue
                    deals.append(Deal(seat, tuple(off.give_flipped), tuple(off.give_hand), resp,
                                      gives, tuple(hand[i] for i in resp), "offer"))
            for seat in self.order_from(a)[1:]:
                req = self.ask(seat, "solicit", self.view(seat))
                if req is None:
                    continue
                hand = self.players[seat].hand
                if not isinstance(req, Request) or not self._valid_idx(tuple(req.give_hand), len(hand)):
                    self.violation(seat, f"solicit -> {req!r}")
                    continue
                if not req.give_hand and not req.want:
                    continue
                fill = self._fulfil(tuple(req.want))
                if fill is None:
                    continue
                ff, fh = fill
                deals.append(Deal(seat, ff, fh, tuple(req.give_hand), tuple(req.want),
                                  tuple(hand[i] for i in req.give_hand), "request"))
            if not deals:
                empty_rounds += 1
                if empty_rounds >= 2:
                    break
                continue
            empty_rounds = 0
            choice = self.ask(a, "choose_trade", self.view(a), tuple(deals))
            if choice is None:
                break
            if not self._deal_ok(choice, deals):
                self.violation(a, f"choose_trade -> {choice!r}")
                break
            self.execute(choice)
        self.trade_round = 0

    def _fulfil(self, want: tuple[str, ...]):
        """Default way the active player pays for a Request: flipped cards first, then front of hand."""
        ff: list[int] = []
        fh: list[int] = []
        for bean in want:
            i = next((i for i, b in enumerate(self.flipped) if b == bean and i not in ff), None)
            if i is not None:
                ff.append(i)
                continue
            hand = self.players[self.active].hand
            j = next((j for j, b in enumerate(hand) if b == bean and j not in fh), None)
            if j is None:
                return None
            fh.append(j)
        return tuple(ff), tuple(fh)

    def _deal_ok(self, d, deals) -> bool:
        if not isinstance(d, Deal):
            return False
        if not any(d.partner == c.partner and d.partner_hand == c.partner_hand
                   and Counter(d.active_gives) == Counter(c.active_gives) and d.source == c.source
                   for c in deals):
            return False
        hand = self.players[self.active].hand
        if not (self._valid_idx(tuple(d.active_flipped), len(self.flipped))
                and self._valid_idx(tuple(d.active_hand), len(hand))):
            return False
        actual = Counter(self.flipped[i] for i in d.active_flipped) + Counter(hand[i] for i in d.active_hand)
        return actual == Counter(d.active_gives)

    def execute(self, d: Deal) -> None:
        ap, pp = self.players[self.active], self.players[d.partner]
        a_cards = [self.flipped[i] for i in d.active_flipped] + [ap.hand[i] for i in d.active_hand]
        p_cards = [pp.hand[i] for i in d.partner_hand]
        for i in sorted(d.active_flipped, reverse=True):
            del self.flipped[i]
        for i in sorted(d.active_hand, reverse=True):
            del ap.hand[i]
        for i in sorted(d.partner_hand, reverse=True):
            del pp.hand[i]
        # received cards go beside the fields (pending), never into the hand -> can't be re-traded
        ap.pending.extend(p_cards)
        pp.pending.extend(a_cards)
        self.trades += 1
        for q, gave, got in ((ap, a_cards, p_cards), (pp, p_cards, a_cards)):
            q.stats["trades"] += 1
            q.stats["cards_given"] += len(gave)
            q.stats["cards_received"] += len(got)
        ap.stats["trades_as_active"] += 1
        if not p_cards:
            ap.stats["gifts_given"] += 1
        self.log(f"   TRADE {ap.name} gives {a_cards or 'nothing'} <-> {pp.name} gives {p_cards or 'nothing'}")

    # ================================================================ turn
    def play_turn(self) -> None:
        a = self.active
        p = self.players[a]
        self.log(f"Turn {self.turn + 1}: {p.name} (seat {a}) hand={p.hand} "
                 f"fields={self._ftup(p)} coins={p.coins}")
        # Phase 1: plant from hand
        self.phase = 1
        self.checkpoint()
        if p.hand:
            self.plant(a, p.hand.pop(0))
            if p.hand and self.ask(a, "plant_second_card", self.view(a)) is True:
                self.plant(a, p.hand.pop(0))
        # Phase 2: flip and trade
        self.phase = 2
        for _ in range(self.rules.flip):
            c = self.draw()
            if c is not None:
                self.flipped.append(c)
        self.log(f"   flips {self.flipped}")
        self.checkpoint()
        self.trade_phase()
        # Phase 3: plant flipped + traded cards
        self.phase = 3
        self.checkpoint()
        for seat in self.order_from(a):
            q = self.players[seat]
            cards = list(q.pending)
            if seat == a:
                cards += self.flipped
                self.flipped = []
            if not cards:
                continue
            order = self.ask(seat, "plant_order", self.view(seat), tuple(cards))
            if not isinstance(order, (list, tuple)) or Counter(order) != Counter(cards):
                self.violation(seat, f"plant_order -> {order!r}")
                order = Bot.plant_order(self.bots[seat], self.view(seat), tuple(cards))
            remaining = list(order)
            while remaining:
                bean = remaining.pop(0)
                q.pending = remaining[:]  # still-unplanted cards stay visible as pending
                self.plant(seat, bean)
            q.pending = []
        if self.ending:
            return
        # Phase 4: draw
        self.phase = 4
        if self.rules.draw_each:
            for seat in self.order_from(a):
                c = self.draw()
                if c is None:
                    break
                self.players[seat].hand.append(c)
        else:
            for _ in range(3):
                c = self.draw()
                if c is None:
                    break
                p.hand.append(c)
        self.active = (a + 1) % self.n
        self.turn += 1

    def check_conservation(self) -> None:
        total = Counter(self.deck) + Counter(self.discard) + Counter(self.flipped) + self.removed
        for q in self.players:
            total += Counter(q.hand) + Counter(q.pending)
            for f in q.fields:
                if f.bean:
                    total[f.bean] += f.count
        if total != self.counts:
            raise AssertionError(f"card conservation broken: extra={total - self.counts} "
                                 f"missing={self.counts - total}")

    # ================================================================ game
    def play(self) -> dict:
        while not self.ending and self.turn < MAX_TURNS:
            self.play_turn()
            if self.check:
                self.check_conservation()
        self.log("== game over: final harvest")
        for q in self.players:
            for i, f in enumerate(q.fields):
                if f.bean:
                    self.harvest(q.seat, i, final=True)
        if self.check:
            self.check_conservation()
        # ranking: most coins; ties -> furthest clockwise from the starting player (highest seat)
        order = sorted(range(self.n), key=lambda s: (self.players[s].coins, s), reverse=True)
        rank = {s: r + 1 for r, s in enumerate(order)}
        players = []
        for q in self.players:
            players.append({
                "bot": getattr(self.bots[q.seat], "_registry_key", q.name), "name": q.name,
                "seat": q.seat, "coins": q.coins, "rank": rank[q.seat], "win": rank[q.seat] == 1,
                "hand_left": len(q.hand),
                **{k: q.stats[k] for k in STAT_KEYS},
            })
        self.log("Final: " + ", ".join(f"{q.name}={q.coins}" for q in self.players))
        return {"seed": self.seed, "rules": self.rules.name, "n": self.n, "turns": self.turn,
                "trades": self.trades, "players": players}
