"""Trade data structures.

Flow inside phase 2 (repeated for up to MAX_TRADE_ROUNDS rounds):
  1. Active player:   propose_offers(view)              -> list[Offer]
  2. Other players:   respond_to_offer(view, OfferView) -> tuple of hand indices to pay with, or None
  3. Other players:   solicit(view)                     -> Request or None
  4. Active player:   choose_trade(view, deals)         -> one Deal (or None to stop trading)

Draft picks (house rule, on by default) can be traded alongside cards. A Pick is a promise
by the giver: on each of the giver's next `turns` turns, right after the 2 cards are flipped
and before any trading, the holder takes up to `cards` of them for free.
"""
from dataclasses import dataclass, replace

MAX_PICK_TURNS = 10
MAX_PICK_CARDS_OWED = 2   # a player can never owe more cards per turn than get flipped


@dataclass(frozen=True)
class Pick:
    """A draft pick: `cards` (1 or 2) of the flipped cards on each of the giver's next `turns` turns."""
    cards: int = 1
    turns: int = 1


@dataclass(frozen=True)
class Offer:
    """Made by the active player. 'I give these cards/picks, I want these beans/picks.'

    give_flipped: indices into view.flipped
    give_hand:    indices into view.hand (any position)
    want:         bean types the partner must hand over (empty = nothing)
    give_picks:   draft picks the active player promises the partner
    want_picks:   draft picks the partner must promise the active player
    to:           restrict the offer to one seat (None = everyone)
    """
    give_flipped: tuple[int, ...] = ()
    give_hand: tuple[int, ...] = ()
    want: tuple[str, ...] = ()
    give_picks: tuple[Pick, ...] = ()
    want_picks: tuple[Pick, ...] = ()
    to: int | None = None


@dataclass(frozen=True)
class OfferView:
    """What the other players see of an Offer."""
    proposer: int
    gives: tuple[str, ...]
    want: tuple[str, ...]
    give_picks: tuple[Pick, ...] = ()   # picks you would receive
    want_picks: tuple[Pick, ...] = ()   # picks you would have to promise


@dataclass(frozen=True)
class Request:
    """Made by a non-active player to the active player.

    give_hand:  indices into the requester's hand they will hand over
    want:       bean types they want from the active player (flipped cards or hand)
    give_picks: draft picks the requester promises the active player
    want_picks: draft picks the requester wants the active player to promise
    """
    give_hand: tuple[int, ...] = ()
    want: tuple[str, ...] = ()
    give_picks: tuple[Pick, ...] = ()
    want_picks: tuple[Pick, ...] = ()


@dataclass(frozen=True)
class Deal:
    """A fully specified trade the active player can accept.

    The active player may return a modified copy (via deal.with_active_cards)
    choosing *which* of its cards pay, as long as the bean types stay the same.
    """
    partner: int
    active_flipped: tuple[int, ...]
    active_hand: tuple[int, ...]
    partner_hand: tuple[int, ...]
    active_gives: tuple[str, ...]
    active_gets: tuple[str, ...]
    source: str  # "offer" or "request"
    active_gives_picks: tuple[Pick, ...] = ()   # picks the active player promises the partner
    active_gets_picks: tuple[Pick, ...] = ()    # picks the partner promises the active player

    def with_active_cards(self, flipped: tuple[int, ...], hand: tuple[int, ...]) -> "Deal":
        return replace(self, active_flipped=tuple(flipped), active_hand=tuple(hand))


@dataclass(frozen=True)
class PickInfo:
    """An outstanding draft pick, as seen in view.draft_picks."""
    giver: int
    holder: int
    cards: int
    turns_left: int
