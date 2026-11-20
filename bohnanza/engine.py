"""Game engine: enforces the rules, asks bots for decisions, records stats."""
import random
from collections import Counter

from .bot import Bot
from .cards import build_deck, deck_counts, payout
from .rules import RuleSet, make_rules
from .state import Field, PlayerState, PlayerView, OpponentInfo, can_harvest_fields
from .trading import (MAX_PICK_CARDS_OWED, MAX_PICK_TURNS, Deal, Offer, OfferView, Pick,
                      PickInfo, Request)

MAX_TRADE_ROUNDS = 20
MAX_OFFERS = 8
MAX_TURNS = 3000

STAT_KEYS = ("harvests", "harvest_cards", "harvest_coins", "forced_harvests", "trades",
             "trades_as_active", "cards_given", "cards_received", "gifts_given", "violations",
             "picks_given", "picks_received", "pick_cards_taken", "pick_cards_lost", "bought_third_field")


class IllegalAction(Exception):
    pass


class DraftPick:
    """Engine-side outstanding pick (mutable)."""
    __slots__ = ("giver", "holder", "cards", "turns_left")

    def __init__(self, giver: int, holder: int, cards: int, turns_left: int):
        self.giver, self.holder, self.cards, self.turns_left = giver, holder, cards, turns_left


class Game:
    """One game. Seat 0 is the starting player; turn order is seat 0, 1, 2, ..."""

    def __init__(self, bots: list[Bot], seed: int = 0, rules: "str | RuleSet" = "base",
                 verbose: bool = False, check: bool = True, strict: bool = False,
                 draft_picks: bool = True, third_field: bool = True):
        n = len(bots)
        self.rules = rules if isinstance(rules, RuleSet) else make_rules(rules, n, draft_picks, third_field)
        self.picks: list[DraftPick] = []
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
        self.pile_start = len(self.deck)

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
            rules=self.rules.name, end_exhaustions=self.rules.end_exhaustions,
            draft_picks_allowed=self.rules.draft_picks,
            draft_picks=tuple(PickInfo(p.giver, p.holder, p.cards, p.turns_left) for p in self.picks),
            pile_start_size=self.pile_start,
            third_field_cost=self.rules.third_field_cost if len(p.fields) == 2 else None)

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
            self.pile_start = len(self.deck)
        card = self.deck.pop()
        if not self.deck:
            self.exhaustions += 1
            self.log(f"-- draw pile ran out ({self.exhaustions}/{self.rules.end_exhaustions})")
            if self.exhaustions >= self.rules.end_exhaustions:
                self.ending = True
            else:
                self.deck, self.discard = self.discard, []
                self.rng.shuffle(self.deck)
                self.pile_start = max(1, len(self.deck))
        return card

    # ================================================================ fields
    def harvest(self, seat: int, idx: int, final: bool = False) -> None:
        p = self.players[seat]
        f = p.fields[idx]
        coins = payout(f.bean, f.count)
        p.coins += coins
        p.coin_cards.extend([f.bean] * coins)
        self.removed[f.bean] += coins
        self.discard.extend([f.bean] * (f.count - coins))
        if not final:
            p.stats["harvests"] += 1
            p.stats["harvest_cards"] += f.count
            p.stats["harvest_coins"] += coins
        self.log(f"   {p.name} harvests {f.count}x {f.bean} -> {coins} coin(s){' (final)' if final else ''}")
        f.bean, f.count = None, 0

    # ================================================================ third field
    def can_buy_field(self, seat: int) -> bool:
        p, cost = self.players[seat], self.rules.third_field_cost
        return cost is not None and len(p.fields) == 2 and p.coins >= cost

    def offer_field(self, seat: int) -> None:
        """Ask the bot whether to buy a 3rd field now (only when it can afford one)."""
        if not self.can_buy_field(seat) or self.ask(seat, "buy_third_field", self.view(seat)) is not True:
            return
        p, cost = self.players[seat], self.rules.third_field_cost
        paid = p.coin_cards[-cost:]
        del p.coin_cards[-cost:]
        p.coins -= cost
        for b in paid:  # paid coins go back into circulation via the discard pile
            self.removed[b] -= 1
            self.discard.append(b)
        p.fields.append(Field())
        p.stats["bought_third_field"] = 1
        self.log(f"   {p.name} buys a third bean field for {cost} coins")

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
        if all(f.bean not in (None, bean) for f in p.fields):
            self.offer_field(seat)  # last chance to buy room instead of harvesting
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
            self.offer_field(seat)
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

    # ================================================================ draft picks
    @staticmethod
    def _picks_ok(picks) -> bool:
        return isinstance(picks, tuple) and all(
            isinstance(p, Pick) and p.cards in (1, 2) and isinstance(p.turns, int)
            and 1 <= p.turns <= MAX_PICK_TURNS for p in picks)

    def pick_capacity(self, seat: int) -> int:
        return MAX_PICK_CARDS_OWED - sum(p.cards for p in self.picks if p.giver == seat)

    def can_promise(self, seat: int, picks: tuple) -> bool:
        return sum(p.cards for p in picks) <= self.pick_capacity(seat)

    def exercise_picks(self) -> None:
        """Holders of the active player's picks take flipped cards, in the order the picks were issued."""
        a = self.active
        for dp in [p for p in self.picks if p.giver == a]:
            if self.flipped:
                h = dp.holder
                idxs = self.ask(h, "draft_pick", self.view(h), dp.cards)
                idxs = tuple(idxs) if isinstance(idxs, (list, tuple)) else idxs
                if not (self._valid_idx(idxs, len(self.flipped)) and len(idxs) <= dp.cards):
                    self.violation(h, f"draft_pick -> {idxs!r}")
                    idxs = Bot.draft_pick(self.bots[h], self.view(h), dp.cards)
                taken = [self.flipped[i] for i in idxs]
                for i in sorted(idxs, reverse=True):
                    del self.flipped[i]
                self.players[h].pending.extend(taken)
                self.players[h].stats["pick_cards_taken"] += len(taken)
                self.players[a].stats["pick_cards_lost"] += len(taken)
                self.log(f"   DRAFT {self.players[h].name} uses a pick on {self.players[a].name}: "
                         f"takes {taken or 'nothing'}")
            dp.turns_left -= 1
        self.picks = [p for p in self.picks if p.turns_left > 0]

    def _add_picks(self, giver: int, holder: int, picks: tuple) -> None:
        for p in picks:
            self.picks.append(DraftPick(giver, holder, p.cards, p.turns))
            self.players[giver].stats["picks_given"] += 1
            self.players[holder].stats["picks_received"] += 1

    # ================================================================ trading
    @staticmethod
    def _valid_idx(idxs, size: int) -> bool:
        return (isinstance(idxs, tuple) and len(set(idxs)) == len(idxs)
                and all(isinstance(i, int) and 0 <= i < size for i in idxs))

    def _picks_legal(self, seat: int, give, want) -> bool:
        """Shape/rule check for picks in an offer or request (capacity is checked separately)."""
        give, want = tuple(give), tuple(want)
        if not (give or want):
            return True
        return self.rules.draft_picks and self._picks_ok(give) and self._picks_ok(want)

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
                        and self._valid_idx(tuple(off.give_hand), len(ap.hand))
                        and self._picks_legal(a, off.give_picks, off.want_picks)
                        and self.can_promise(a, tuple(off.give_picks))):
                    self.violation(a, f"bad offer {off!r}")
                    continue
                gives = tuple(self.flipped[i] for i in off.give_flipped) + tuple(ap.hand[i] for i in off.give_hand)
                want, gp, wp = tuple(off.want), tuple(off.give_picks), tuple(off.want_picks)
                if not (gives or want or gp or wp):
                    continue
                ov = OfferView(proposer=a, gives=gives, want=want, give_picks=gp, want_picks=wp)
                for seat in self.order_from(a)[1:]:
                    if off.to is not None and seat != off.to:
                        continue
                    if not self.can_promise(seat, wp):
                        continue  # this player couldn't honour the picks asked for
                    resp = self.ask(seat, "respond_to_offer", self.view(seat), ov)
                    if resp is None:
                        continue
                    hand = self.players[seat].hand
                    resp = tuple(resp) if isinstance(resp, (list, tuple)) else resp
                    if not self._valid_idx(resp, len(hand)) or Counter(hand[i] for i in resp) != Counter(want):
                        self.violation(seat, f"respond_to_offer -> {resp!r}")
                        continue
                    deals.append(Deal(seat, tuple(off.give_flipped), tuple(off.give_hand), resp,
                                      gives, tuple(hand[i] for i in resp), "offer", gp, wp))
            for seat in self.order_from(a)[1:]:
                req = self.ask(seat, "solicit", self.view(seat))
                if req is None:
                    continue
                hand = self.players[seat].hand
                if not (isinstance(req, Request) and self._valid_idx(tuple(req.give_hand), len(hand))
                        and self._picks_legal(seat, req.give_picks, req.want_picks)
                        and self.can_promise(seat, tuple(req.give_picks))):
                    self.violation(seat, f"solicit -> {req!r}")
                    continue
                gp, wp = tuple(req.give_picks), tuple(req.want_picks)
                if not (req.give_hand or req.want or gp or wp):
                    continue
                if not self.can_promise(a, wp):
                    continue
                fill = self._fulfil(tuple(req.want))
                if fill is None:
                    continue
                ff, fh = fill
                deals.append(Deal(seat, ff, fh, tuple(req.give_hand), tuple(req.want),
                                  tuple(hand[i] for i in req.give_hand), "request", wp, gp))
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
                   and d.active_gives_picks == c.active_gives_picks
                   and d.active_gets_picks == c.active_gets_picks
                   for c in deals):
            return False
        # picks promised earlier this turn may have used up capacity
        if not (self.can_promise(self.active, d.active_gives_picks)
                and self.can_promise(d.partner, d.active_gets_picks)):
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
        self._add_picks(self.active, d.partner, d.active_gives_picks)
        self._add_picks(d.partner, self.active, d.active_gets_picks)
        self.trades += 1
        for q, gave, got in ((ap, a_cards, p_cards), (pp, p_cards, a_cards)):
            q.stats["trades"] += 1
            q.stats["cards_given"] += len(gave)
            q.stats["cards_received"] += len(got)
        ap.stats["trades_as_active"] += 1
        if not p_cards and not d.active_gets_picks:
            ap.stats["gifts_given"] += 1
        fmt = lambda cards, picks: " + ".join(
            [str(cards)] * bool(cards) + [f"pick({p.cards} card{'s' * (p.cards > 1)} x {p.turns} turn{'s' * (p.turns > 1)})"
                                         for p in picks]) or "nothing"
        self.log(f"   TRADE {ap.name} gives {fmt(a_cards, d.active_gives_picks)} <-> "
                 f"{pp.name} gives {fmt(p_cards, d.active_gets_picks)}")

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
        self.exercise_picks()
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
