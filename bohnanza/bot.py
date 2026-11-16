"""Bot base class. Subclass it in bots/<your_bot>.py and override only what you want.

Every hook gets a fresh, read-only PlayerView (see state.py). Illegal return values
(or exceptions) are replaced with this base class's default and counted as a violation.
"""
import random
from collections import Counter

from .state import PlayerView
from .trading import Deal, Offer, OfferView, Pick, Request


class Bot:
    key: str | None = None       # CLI name; defaults to the module filename
    name: str | None = None      # display name; defaults to the class name
    description: str = ""     # one line, shown by `list`
    details: str = ""         # longer explanation, shown in the report

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

    # ------------------------------------------------------------------ valuation
    def card_value(self, view: PlayerView, bean: str) -> float:
        """How much I like receiving/planting one card of this bean right now.
        +1 matches a field, 0 fits an empty field, -1 would force a harvest."""
        if view.field_index(bean) is not None:
            return 1.0
        if view.empty_field() is not None:
            return 0.0
        return -1.0

    # ------------------------------------------------------------------ phase 1
    def plant_second_card(self, view: PlayerView) -> bool:
        """After the mandatory front card: also plant the (new) front card?"""
        return view.field_index(view.hand[0]) is not None or view.empty_field() is not None

    # ------------------------------------------------------------------ planting
    def choose_field(self, view: PlayerView, bean: str) -> int:
        """Field index to plant `bean` in. Picking a field holding a different bean
        harvests it first (must satisfy the bean protection rule)."""
        i = view.field_index(bean)
        if i is not None:
            return i
        e = view.empty_field()
        if e is not None:
            return e
        return self.pick_harvest(view)

    def pick_harvest(self, view: PlayerView) -> int:
        """Which field to sacrifice when forced: best payout, then fewest cards wasted."""
        return max(view.harvestable(),
                   key=lambda i: (view.field_payout(i), -view.fields[i][1]))

    def plant_order(self, view: PlayerView, cards: tuple[str, ...]) -> list[str]:
        """Order to plant traded/kept cards in phase 3: matching fields first."""
        cnt = Counter(cards)
        return sorted(cards, key=lambda b: (view.field_index(b) is None, -cnt[b], b))

    # ------------------------------------------------------------------ harvesting
    def maybe_harvest(self, view: PlayerView) -> list[int]:
        """Voluntary harvests, called at the start of every phase for every player.
        Default: cash in fields that can't earn any more coins."""
        return [i for i in view.harvestable() if view.is_maxed(i)]

    # ------------------------------------------------------------------ trading (active)
    def unwanted_flipped(self, view: PlayerView) -> list[int]:
        """Flipped cards that won't fit after planting pending cards."""
        sim = list(view.pending)
        bad = []
        for i, b in enumerate(view.flipped):
            if view.fits_all(sim + [b]):
                sim.append(b)
            else:
                bad.append(i)
        return bad

    def propose_offers(self, view: PlayerView) -> list[Offer]:
        """Default: first ask for one of my field beans in exchange for each unwanted
        flipped card; from round 1 on, just give them away."""
        offers = []
        biggest = max((f for f in view.fields if f[0]), key=lambda f: f[1], default=None)
        for i in self.unwanted_flipped(view):
            if view.trade_round == 0 and biggest:
                offers.append(Offer(give_flipped=(i,), want=(biggest[0],)))
            else:
                offers.append(Offer(give_flipped=(i,)))
        return offers

    def choose_trade(self, view: PlayerView, deals: tuple[Deal, ...]) -> Deal | None:
        """Pick one deal (or None to end trading). Default: best positive net card value."""
        best, best_score = None, 0.0
        for d in deals:
            s = self.deal_score(view, d)
            if s > best_score:
                best, best_score = d, s
        return best

    def deal_score(self, view: PlayerView, deal: Deal) -> float:
        gets = sum(self.card_value(view, b) for b in deal.active_gets)
        gives = sum(self.card_value(view, b) for b in deal.active_gives)
        gets += sum(self.pick_value(view, p) for p in deal.active_gets_picks)
        gives += sum(self.pick_value(view, p) for p in deal.active_gives_picks)
        return gets - gives

    # ------------------------------------------------------------------ draft picks
    def pick_value(self, view: PlayerView, pick: Pick) -> float:
        """Rough worth of one draft pick, in the same units as card_value.
        Used both for picks received (gain) and picks promised (cost)."""
        return 0.5 * pick.cards * pick.turns

    def draft_pick(self, view: PlayerView, count: int) -> tuple[int, ...]:
        """Using a pick: return up to `count` indices into view.flipped to take for free.
        Default: take the cards worth most to me, skipping any that would force a harvest."""
        chosen: list[int] = []
        ranked = sorted(range(len(view.flipped)), key=lambda i: -self.card_value(view, view.flipped[i]))
        for i in ranked:
            if len(chosen) == count:
                break
            planned = list(view.pending) + [view.flipped[j] for j in chosen] + [view.flipped[i]]
            if self.card_value(view, view.flipped[i]) >= 0 and view.fits_all(planned):
                chosen.append(i)
        return tuple(chosen)

    # ------------------------------------------------------------------ trading (others)
    def respond_to_offer(self, view: PlayerView, offer: OfferView) -> tuple[int, ...] | None:
        """Accept by returning hand indices whose beans exactly match offer.want.
        Default: never promises draft picks; happily accepts picks given to it."""
        if offer.want_picks:
            return None
        if not view.fits_all(list(view.pending) + list(offer.gives)):
            return None
        return self.find_payment(view, offer.want)

    def find_payment(self, view: PlayerView, want, allow_field_beans=False) -> tuple[int, ...] | None:
        """Hand indices paying for `want`, preferring front cards that don't match my fields."""
        used, pay = set(), []
        for bean in want:
            idx = next((i for i, b in enumerate(view.hand) if b == bean and i not in used
                        and (allow_field_beans or b not in view.my_beans)), None)
            if idx is None:
                return None
            used.add(idx)
            pay.append(idx)
        return tuple(pay)

    def solicit(self, view: PlayerView) -> Request | None:
        """Ask the active player for a flipped card that matches one of my fields,
        offering a hand card I don't want (or nothing)."""
        for b in view.flipped:
            if view.field_index(b) is not None and view.fits_all(list(view.pending) + [b]):
                junk = next((i for i, h in enumerate(view.hand) if h not in view.my_beans), None)
                return Request(give_hand=() if junk is None else (junk,), want=(b,))
        return None
