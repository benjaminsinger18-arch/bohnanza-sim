"""Trade data structures.

Flow inside phase 2 (repeated for up to MAX_TRADE_ROUNDS rounds):
  1. Active player:   propose_offers(view)          -> list[Offer]
  2. Other players:   respond_to_offer(view, OfferView) -> tuple of hand indices to pay with, or None
  3. Other players:   solicit(view)                 -> Request or None
  4. Active player:   choose_trade(view, deals)     -> one Deal (or None to stop trading)
"""
from dataclasses import dataclass, replace


@dataclass(frozen=True)
class Offer:
    """Made by the active player. 'I give these cards, I want these bean types.'

    give_flipped: indices into view.flipped
    give_hand:    indices into view.hand (any position)
    want:         bean types the partner must hand over (empty = a gift)
    to:           restrict the offer to one seat (None = everyone)
    """
    give_flipped: tuple[int, ...] = ()
    give_hand: tuple[int, ...] = ()
    want: tuple[str, ...] = ()
    to: int | None = None


@dataclass(frozen=True)
class OfferView:
    """What the other players see of an Offer."""
    proposer: int
    gives: tuple[str, ...]
    want: tuple[str, ...]


@dataclass(frozen=True)
class Request:
    """Made by a non-active player to the active player.

    give_hand: indices into the requester's hand they will hand over (empty = asking for a gift)
    want:      bean types they want from the active player (flipped cards or hand)
    """
    give_hand: tuple[int, ...] = ()
    want: tuple[str, ...] = ()


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

    def with_active_cards(self, flipped: tuple[int, ...], hand: tuple[int, ...]) -> "Deal":
        return replace(self, active_flipped=tuple(flipped), active_hand=tuple(hand))
