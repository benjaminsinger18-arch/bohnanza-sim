"""Bot base class: a healthy baseline strategy. Subclass it in bots/<your_bot>.py and
override only what you want (or just tweak the tuning knobs).

How the baseline thinks
-----------------------
Everything is measured in coins.

* field_value(bean, count): what a field is worth if kept and grown. It is the larger of
  "sell it now" and a discounted estimate of where it can still grow, based on how many
  copies of that bean are still out there (unseen + discards that will be reshuffled),
  the share of them I can expect to get, and how much of the game is left.
  -> rare beans (few copies left) stop growing in value quickly; common beans keep growing.
* card_value(bean): the change in my total value from planting one card right now
  (extend a field / start a new one / force-sell a field to make room).
* Trades, draft picks, the third field and selling fields are all judged with those numbers.

Every hook gets a fresh, read-only PlayerView (see state.py). Illegal return values
(or exceptions) are replaced with this base class's default and counted as a violation.
"""
import random
from collections import Counter
from dataclasses import replace

from .cards import BEANS, payout
from .state import PlayerView
from .trading import Deal, Offer, OfferView, Pick, Request


def smooth_payout(bean: str, n: float) -> float:
    """Beanometer with straight lines between its steps (so 5 Blue ~ 1.5 coins)."""
    pts = [(0, 0.0)] + [(t, float(c)) for c, t in enumerate(BEANS[bean][1], 1) if t is not None]
    if n >= pts[-1][0]:
        return pts[-1][1]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if n <= x1:
            return y0 + (y1 - y0) * (n - x0) / (x1 - x0)
    return pts[-1][1]


class Bot:
    key: str | None = None       # CLI name; defaults to the module filename
    name: str | None = None      # display name; defaults to the class name
    description: str = ""        # one line, shown by `list`
    details: str = ""            # longer explanation, shown in the report

    # ------------------------------------------------------------------ tuning knobs
    RISK_DISCOUNT = 0.85            # how much of a field's expected growth counts (vs selling now)
    FUTURE_SHARE = None             # share of the remaining copies of a bean I expect to get
                                    # (None = 1.5 / number of players)
    HELP_WEIGHT = 0.25              # how much a trade partner's gain counts against me
    LEADER_HELP_WEIGHT = 0.6        # ...when that partner is in the lead
    MIN_TRADE_GAIN = 0.05           # smallest gain (coins) worth trading for
    PICK_TURN_DISCOUNT = 0.85       # each turn a draft pick waits, it's worth this much less
    HAND_DEPTH_DECAY = 0.75         # cards deeper in the hand matter less (they're turns away)
    THIRD_FIELD_MAX_PROGRESS = 0.6  # buy a 3rd field only if less than this share of the game is gone
    JUNK_HAND_THRESHOLD = -0.2      # front hand cards worth less than this get offered away
    PICK_MENU = ((1, 1), (1, 2), (2, 1), (1, 3), (2, 2), (2, 3))  # (cards, turns) picks I'm willing to offer

    def __init__(self):
        self.seat: int = -1
        self.num_players: int = 0
        self.rng = random.Random()

    def setup(self, seat: int, num_players: int, rng: random.Random) -> None:
        """Called once at the start of each game."""
        self.seat, self.num_players, self.rng = seat, num_players, rng

    @property
    def display_name(self) -> str:
        return self.name or type(self).__name__

    # ================================================================== valuation
    def _ctx(self, view: PlayerView) -> dict:
        """Per-decision cache for numbers that don't depend on my fields."""
        if getattr(self, "_ctx_key", None) is not view.opponents:
            self._ctx_key = view.opponents
            self._ctx_data = {}
        return self._ctx_data

    def available(self, view: PlayerView, bean: str) -> float:
        """Copies of a bean I might still see: unseen now, plus discards if the pile gets reshuffled again."""
        c = self._ctx(view)
        if "avail" not in c:
            more_passes = view.exhaustions < view.end_exhaustions - 1
            disc = Counter(view.discard)
            c["avail"] = {b: max(0, view.remaining_unseen(b)) + (disc[b] if more_passes else 0)
                          for b in view.deck_counts}
        return c["avail"].get(bean, 0)

    def future_share(self, view: PlayerView) -> float:
        return self.FUTURE_SHARE if self.FUTURE_SHARE is not None else min(1.0, 1.5 / view.num_players)

    def field_value(self, view: PlayerView, bean: str | None, count: int) -> float:
        """Coins a field is worth if kept and grown; never less than selling it now."""
        if bean is None or count <= 0:
            return 0.0
        c = self._ctx(view)
        k = ("fv", bean, count)
        if k not in c:
            reach = self.available(view, bean) * self.future_share(view) * (1.0 - view.progress)
            c[k] = max(float(payout(bean, count)), self.RISK_DISCOUNT * smooth_payout(bean, count + reach))
        return c[k]

    def empty_field_value(self, view: PlayerView) -> float:
        """What an empty field is worth: the average new field I could start in it."""
        c = self._ctx(view)
        if "empty" not in c:
            weights = {b: self.available(view, b) for b in view.deck_counts}
            tot = sum(weights.values())
            c["empty"] = (sum(w * self.field_value(view, b, 1) for b, w in weights.items()) / tot) if tot else 0.0
        return c["empty"]

    def card_value(self, view: PlayerView, bean: str) -> float:
        """Coins gained (or lost) by planting one card of this bean right now."""
        c = self._ctx(view)
        k = ("cv", view.fields, bean)
        if k not in c:
            c[k] = self._card_value(view, bean)
        return c[k]

    def _card_value(self, view: PlayerView, bean: str) -> float:
        i = view.field_index(bean)
        if i is not None:
            c = view.fields[i][1]
            return self.field_value(view, bean, c + 1) - self.field_value(view, bean, c)
        if view.empty_field() is not None:
            return self.field_value(view, bean, 1) - self.empty_field_value(view)
        j = self.pick_harvest(view)
        bj, cj = view.fields[j]
        return payout(bj, cj) - self.field_value(view, bj, cj) + self.field_value(view, bean, 1)

    def after_planting(self, view: PlayerView, bean: str) -> PlayerView:
        """A copy of the view with this bean planted where I'd put it (for what-if maths)."""
        fields = list(view.fields)
        i = view.field_index(bean)
        if i is None:
            i = view.empty_field()
        if i is None:
            i = self.pick_harvest(view)
            fields[i] = (None, 0)
        b, c = fields[i]
        fields[i] = (bean, c + 1)
        return replace(view, fields=tuple(fields))

    def cards_value(self, view: PlayerView, beans) -> float:
        """Coins gained by planting these beans in this order."""
        total, v = 0.0, view
        for b in beans:
            total += self.card_value(v, b)
            v = self.after_planting(v, b)
        return total

    def hand_value(self, view: PlayerView, i: int) -> float:
        """What the hand card at position i is worth to me (negative = I'd rather lose it)."""
        v = self.card_value(view, view.hand[i])
        return v if i < 2 else v * self.HAND_DEPTH_DECAY ** ((i - 1) // 2)

    def help_weight(self, view: PlayerView, seat: int | None) -> float:
        """How much an opponent's gain counts against me (more if they're leading)."""
        if seat is None or seat == view.seat:
            return self.HELP_WEIGHT
        o = view.opponent(seat)
        best_other = max([view.coins] + [x.coins for x in view.opponents if x.seat != seat])
        return self.LEADER_HELP_WEIGHT if o.coins > best_other else self.HELP_WEIGHT

    def partner_gain(self, view: PlayerView, seat: int, beans) -> float:
        """Rough coins an opponent gains from these beans, judged from their visible fields."""
        o = view.opponent(seat)
        theirs = {b for b, _ in o.fields if b}
        empty = any(b is None for b, _ in o.fields)
        return sum(0.5 if b in theirs else 0.2 if empty else 0.0 for b in beans)

    # ================================================================== phase 1
    def plant_second_card(self, view: PlayerView) -> bool:
        """After the mandatory front card: also plant the (new) front card?"""
        return self.card_value(view, view.hand[0]) >= 0

    # ================================================================== planting
    def choose_field(self, view: PlayerView, bean: str) -> int:
        """Field index to plant `bean` in. Picking a field holding a different bean
        sells (harvests) it first (must satisfy the bean protection rule)."""
        i = view.field_index(bean)
        if i is not None:
            return i
        e = view.empty_field()
        if e is not None:
            return e
        return self.pick_harvest(view)

    def pick_harvest(self, view: PlayerView) -> int:
        """Which field to sell when forced: the one losing the least future value; ties -> more coins."""
        def key(i):
            b, c = view.fields[i]
            return payout(b, c) - self.field_value(view, b, c), payout(b, c)
        return max(view.harvestable(), key=key)

    def plant_order(self, view: PlayerView, cards: tuple[str, ...]) -> list[str]:
        """Order to plant traded/kept cards in phase 3: matching fields first, duplicates together."""
        cnt = Counter(cards)
        return sorted(cards, key=lambda b: (view.field_index(b) is None, -cnt[b], b))

    # ================================================================== selling fields
    def maybe_harvest(self, view: PlayerView) -> list[int]:
        """Voluntary sales, offered at the start of every phase.
        Baseline: sell a field once it pays and can't realistically grow any more."""
        out = []
        for i in view.harvestable():
            b, c = view.fields[i]
            p = payout(b, c)
            if p > 0 and self.field_value(view, b, c) <= p + 1e-9:
                out.append(i)
        return out

    # ================================================================== third field
    def buy_third_field(self, view: PlayerView) -> bool:
        """Offered whenever you can afford a 3rd field. Baseline: buy it if the game is young enough."""
        return (view.third_field_cost is not None and view.coins >= view.third_field_cost
                and view.progress < self.THIRD_FIELD_MAX_PROGRESS)

    # ================================================================== draft picks
    def flip_odds(self, view: PlayerView) -> dict:
        """Chance that a flipped card is each bean (from what's still unseen)."""
        c = self._ctx(view)
        if "odds" not in c:
            u = {b: max(0, view.remaining_unseen(b)) for b in view.deck_counts}
            tot = sum(u.values())
            c["odds"] = {b: x / tot for b, x in u.items() if x} if tot else {}
        return c["odds"]

    def _turn_discount(self, turns: int) -> float:
        d = self.PICK_TURN_DISCOUNT
        return sum(d ** k for k in range(1, turns + 1))

    def their_card_value(self, view: PlayerView, seat: int, bean: str) -> float:
        """Rough value of a bean to another player, judged from their visible fields."""
        o = view.opponent(seat)
        if any(b == bean for b, _ in o.fields):
            return 0.5
        if any(b is None for b, _ in o.fields):
            return 0.0
        return -0.5

    def ev_pick(self, view: PlayerView, gain: float, partner: int | None, their_loss: float) -> Pick | None:
        """The cheapest draft pick (from PICK_MENU) that is worth more to the partner than the card they
        give up, while costing me less than what I gain. None if no pick is positive for both sides."""
        if not view.draft_picks_allowed:
            return None
        cap = view.pick_capacity()
        menu = [Pick(c, t) for c, t in self.PICK_MENU if c <= cap]
        for pk in sorted(menu, key=lambda pk: self.pick_cost(view, pk, partner)):
            if self.pick_cost(view, pk, partner) >= gain - self.MIN_TRADE_GAIN:
                break  # every remaining pick costs even more
            if self.pick_value(view, pk) >= their_loss + self.MIN_TRADE_GAIN:
                return pk
        return None

    def pick_value(self, view: PlayerView, pick: Pick) -> float:
        """Expected coins from holding a draft pick: the best of the 2 flips (1-card pick)
        or both flips (2-card pick), only counting cards I'd actually want, discounted per turn."""
        odds = self.flip_odds(view)
        vals = {b: max(0.0, self.card_value(view, b)) for b in odds}
        if pick.cards >= 2:
            e = 2 * sum(p * vals[b] for b, p in odds.items())
        else:
            items = list(odds.items())
            e = sum(p1 * p2 * max(vals[b1], vals[b2]) for b1, p1 in items for b2, p2 in items)
        return e * self._turn_discount(pick.turns)

    def pick_cost(self, view: PlayerView, pick: Pick, holder: int | None = None) -> float:
        """Expected coins I lose by promising a draft pick: flips I'd have wanted, plus the help it gives the holder."""
        odds = self.flip_odds(view)
        mine = sum(p * max(0.0, self.card_value(view, b)) for b, p in odds.items())
        loss = pick.cards * mine * self._turn_discount(pick.turns)
        return loss + self.help_weight(view, holder) * self.pick_value(view, pick)

    def draft_pick(self, view: PlayerView, count: int) -> tuple[int, ...]:
        """Using a pick: take up to `count` flipped cards, best first, only if they're worth having."""
        chosen: list[int] = []
        plan = list(view.pending)
        for _ in range(count):
            base = self.cards_value(view, plan)
            best, best_v = None, 0.0
            for i, b in enumerate(view.flipped):
                if i in chosen:
                    continue
                v = self.cards_value(view, plan + [b]) - base
                if v > best_v:
                    best, best_v = i, v
            if best is None:
                break
            chosen.append(best)
            plan.append(view.flipped[best])
        return tuple(chosen)

    # ================================================================== trading (active player)
    def unwanted_flipped(self, view: PlayerView) -> list[int]:
        """Flipped cards I'm better off without."""
        allc = list(view.pending) + list(view.flipped)
        base = self.cards_value(view, allc)
        out = []
        for i in range(len(view.flipped)):
            without = list(view.pending) + [b for j, b in enumerate(view.flipped) if j != i]
            if self.cards_value(view, without) > base + 0.01:
                out.append(i)
        return out

    def wanted_bean(self, view: PlayerView) -> str | None:
        """The bean I'd most like to receive (best value among beans I'm growing)."""
        return max(view.my_beans, key=lambda b: self.card_value(view, b), default=None)

    def propose_offers(self, view: PlayerView) -> list[Offer]:
        """Baseline: sell unwanted flipped cards and junk front hand cards (first for a bean
        I grow, then as gifts). When I want a bean but have nothing good to pay with, I always offer
        an EV-priced draft pick for it."""
        offers = []
        want = self.wanted_bean(view)
        ask = (want,) if view.trade_round == 0 and want else ()
        for i in self.unwanted_flipped(view):
            offers.append(Offer(give_flipped=(i,), want=ask))
        for i in range(min(2, len(view.hand))):
            if self.hand_value(view, i) < self.JUNK_HAND_THRESHOLD:
                offers.append(Offer(give_hand=(i,), want=ask))
        # want a bean but nothing good to pay with -> always offer an EV-priced draft pick for it
        if want and not any(o.want for o in offers):
            pk = self.ev_pick(view, self.card_value(view, want), None, their_loss=0.3)
            if pk:
                offers.append(Offer(give_picks=(pk,), want=(want,)))
        return offers

    def deal_score(self, view: PlayerView, deal: Deal) -> float:
        """Coins I gain from a deal (as the active player), compared with not trading."""
        kept = [b for i, b in enumerate(view.flipped) if i not in deal.active_flipped]
        base = self.cards_value(view, list(view.pending) + list(view.flipped))
        after = self.cards_value(view, list(view.pending) + list(deal.active_gets) + kept)
        s = after - base
        s -= sum(self.hand_value(view, i) for i in deal.active_hand)
        s += sum(self.pick_value(view, p) for p in deal.active_gets_picks)
        s -= sum(self.pick_cost(view, p, deal.partner) for p in deal.active_gives_picks)
        s -= self.help_weight(view, deal.partner) * self.partner_gain(view, deal.partner, deal.active_gives)
        return s

    def choose_trade(self, view: PlayerView, deals: tuple[Deal, ...]) -> Deal | None:
        """Pick the deal with the best score, if it's worth at least MIN_TRADE_GAIN."""
        best, best_score = None, self.MIN_TRADE_GAIN
        for d in deals:
            s = self.deal_score(view, d)
            if s > best_score:
                best, best_score = d, s
        return best

    # ================================================================== trading (other players)
    def find_payment(self, view: PlayerView, want, allow_field_beans=False) -> tuple[int, ...] | None:
        """Hand indices paying for `want`, choosing the copies I value least.
        allow_field_beans=False refuses to pay with beans I'm growing."""
        used, pay = set(), []
        for bean in want:
            if not allow_field_beans and bean in view.my_beans:
                return None
            cands = [i for i, b in enumerate(view.hand) if b == bean and i not in used]
            if not cands:
                return None
            i = min(cands, key=lambda i: self.hand_value(view, i))
            used.add(i)
            pay.append(i)
        return tuple(pay)

    def respond_to_offer(self, view: PlayerView, offer: OfferView) -> tuple[int, ...] | None:
        """Accept (by returning hand indices matching offer.want) if the trade gains me coins
        after counting what I pay, picks either way, and the help it gives the active player."""
        pay = self.find_payment(view, offer.want, allow_field_beans=True)
        if pay is None:
            return None
        gain = self.cards_value(view, list(view.pending) + list(offer.gives)) - self.cards_value(view, view.pending)
        gain -= sum(self.hand_value(view, i) for i in pay)
        gain += sum(self.pick_value(view, p) for p in offer.give_picks)
        gain -= sum(self.pick_cost(view, p, offer.proposer) for p in offer.want_picks)
        gain -= self.help_weight(view, offer.proposer) * self.partner_gain(
            view, offer.proposer, [view.hand[i] for i in pay])
        return pay if gain > self.MIN_TRADE_GAIN else None

    def solicit(self, view: PlayerView) -> Request | None:
        """Ask the active player for the flipped card I'd gain most from, paying with my
        worst hand card if it's junk, otherwise an EV-priced draft pick, otherwise asking for it free."""
        best, best_net = None, self.MIN_TRADE_GAIN
        base = self.cards_value(view, view.pending)
        junk = min(range(len(view.hand)), key=lambda i: self.hand_value(view, i), default=None)
        junk_v = self.hand_value(view, junk) if junk is not None else 0.0
        for b in set(view.flipped):
            gain = self.cards_value(view, list(view.pending) + [b]) - base
            if gain <= self.MIN_TRADE_GAIN:
                continue
            if junk is not None and junk_v < 0:      # a good trade: pay with a card I don't want
                req, net = Request(give_hand=(junk,), want=(b,)), gain - junk_v
            else:                                     # no good trade: always offer an EV-priced pick
                pk = self.ev_pick(view, gain, view.active, self.their_card_value(view, view.active, b))
                if pk:
                    req, net = Request(give_picks=(pk,), want=(b,)), gain - self.pick_cost(view, pk, view.active)
                else:
                    req, net = Request(want=(b,)), gain
            if net > best_net:
                best, best_net = req, net
        return best
