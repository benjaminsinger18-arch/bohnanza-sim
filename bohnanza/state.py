"""Mutable engine state + the read-only PlayerView handed to bots."""
from collections import Counter
from dataclasses import dataclass, field

from .cards import payout as _payout, next_threshold, max_threshold

FieldT = tuple  # (bean | None, count)


@dataclass
class Field:
    bean: str | None = None
    count: int = 0


@dataclass
class PlayerState:
    seat: int
    name: str
    fields: list[Field]
    hand: list[str] = field(default_factory=list)
    pending: list[str] = field(default_factory=list)  # traded-in cards waiting for phase 3
    coins: int = 0
    stats: Counter = field(default_factory=Counter)


def can_harvest_fields(fields: tuple[FieldT, ...], idx: int) -> bool:
    """Bean protection rule: a 1-card field can't be harvested while another field has >1."""
    bean, count = fields[idx]
    if bean is None or count == 0:
        return False
    if count == 1:
        return not any(c > 1 for i, (_, c) in enumerate(fields) if i != idx)
    return True


@dataclass(frozen=True)
class OpponentInfo:
    seat: int
    name: str
    fields: tuple[FieldT, ...]
    coins: int
    hand_size: int
    pending: tuple[str, ...]


@dataclass(frozen=True)
class PlayerView:
    """Everything a bot is allowed to know. Immutable; a fresh one is built for every decision."""
    seat: int
    num_players: int
    active: int            # seat of the active player
    phase: int             # 1-4
    turn: int
    trade_round: int       # 0-based round inside phase 2
    hand: tuple[str, ...]  # your hand, in order (index 0 = front card)
    fields: tuple[FieldT, ...]
    coins: int
    pending: tuple[str, ...]   # cards you received in trades this turn (must be planted in phase 3)
    opponents: tuple[OpponentInfo, ...]
    flipped: tuple[str, ...]   # face-up cards from phase 2 still held by the active player
    discard: tuple[str, ...]
    deck_size: int
    exhaustions: int           # how many times the draw pile has run out (game ends at 3)
    removed: dict              # bean -> cards turned into coins so far (public knowledge)
    deck_counts: dict          # bean -> copies in this game's deck
    rules: str = "base"        # "base" or "variant"
    end_exhaustions: int = 3   # pile run-outs that end the game
    draft_picks_allowed: bool = True
    draft_picks: tuple = ()    # every outstanding PickInfo(giver, holder, cards, turns_left), in issue order

    # ---------- convenience ----------
    @property
    def is_active(self) -> bool:
        return self.seat == self.active

    # ---------- draft picks ----------
    @property
    def picks_held(self) -> list:
        """Draft picks other players owe me."""
        return [p for p in self.draft_picks if p.holder == self.seat]

    @property
    def picks_owed(self) -> list:
        """Draft picks I owe other players."""
        return [p for p in self.draft_picks if p.giver == self.seat]

    def pick_capacity(self, seat: int | None = None) -> int:
        """How many more pick-cards this player (default: me) can promise (max 2 owed at once)."""
        seat = self.seat if seat is None else seat
        return max(0, 2 - sum(p.cards for p in self.draft_picks if p.giver == seat))

    @property
    def my_beans(self) -> set[str]:
        return {b for b, _ in self.fields if b is not None}

    def payout(self, bean: str | None, n: int) -> int:
        return _payout(bean, n)

    def field_payout(self, idx: int) -> int:
        return _payout(*self.fields[idx])

    def next_coin(self, idx: int) -> int | None:
        """Cards still needed in field idx to earn one more coin (None if maxed/empty)."""
        bean, count = self.fields[idx]
        if bean is None:
            return None
        t = next_threshold(bean, count)
        return None if t is None else t - count

    def is_maxed(self, idx: int) -> bool:
        bean, count = self.fields[idx]
        return bean is not None and count >= max_threshold(bean)

    def field_index(self, bean: str) -> int | None:
        """Index of a field already growing this bean (largest one), else None."""
        best = None
        for i, (b, c) in enumerate(self.fields):
            if b == bean and (best is None or c > self.fields[best][1]):
                best = i
        return best

    def empty_field(self) -> int | None:
        for i, (b, _) in enumerate(self.fields):
            if b is None:
                return i
        return None

    def fits(self, bean: str) -> bool:
        """Can this bean be planted without harvesting anything?"""
        return self.field_index(bean) is not None or self.empty_field() is not None

    def fits_all(self, beans) -> bool:
        """Can all these beans be planted (in this order) without harvesting?"""
        sim = [b for b, _ in self.fields]
        for bean in beans:
            if bean in sim:
                continue
            if None in sim:
                sim[sim.index(None)] = bean
            else:
                return False
        return True

    def can_harvest(self, idx: int) -> bool:
        return can_harvest_fields(self.fields, idx)

    def harvestable(self) -> list[int]:
        return [i for i in range(len(self.fields)) if self.can_harvest(i)]

    def legal_fields(self, bean: str) -> list[int]:
        """Fields choose_field may return for this bean (occupied-by-other => it gets harvested)."""
        out = []
        for i, (b, _) in enumerate(self.fields):
            if b is None or b == bean or self.can_harvest(i):
                out.append(i)
        return out

    def remaining_unseen(self, bean: str) -> int:
        """Copies of this bean not visible to you (other hands + draw pile)."""
        seen = self.hand.count(bean) + self.discard.count(bean) + self.flipped.count(bean)
        seen += self.pending.count(bean) + self.removed.get(bean, 0)
        seen += sum(c for b, c in self.fields if b == bean)
        for o in self.opponents:
            seen += sum(c for b, c in o.fields if b == bean) + o.pending.count(bean)
        return self.deck_counts.get(bean, 0) - seen

    def opponent(self, seat: int) -> OpponentInfo:
        for o in self.opponents:
            if o.seat == seat:
                return o
        raise KeyError(seat)
