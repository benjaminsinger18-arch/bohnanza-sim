"""Rule sets. Everything that varies between the base game and the 3-7 player variant."""
from dataclasses import dataclass

from .cards import BASE_BEANS, VARIANT_BEANS


@dataclass(frozen=True)
class RuleSet:
    name: str                 # "base" or "variant"
    num_players: int
    beans: tuple[str, ...]    # bean types in the deck
    fields: int               # bean fields per player
    draw_each: bool           # phase 4: False = active draws 3; True = every player draws 1
    end_exhaustions: int      # game ends when the draw pile runs out this many times
    hand_size: int = 5
    flip: int = 2


RULESETS = ("base", "variant")


def make_rules(name: str, num_players: int) -> RuleSet:
    n = num_players
    if name == "base":
        if not 3 <= n <= 5:
            raise ValueError("base game is for 3-5 players")
        return RuleSet("base", n, BASE_BEANS, 3 if n == 3 else 2, False, 3)
    if name == "variant":
        if not 3 <= n <= 7:
            raise ValueError("the 3-7 player variant is for 3-7 players")
        drop = {"Cocoa"} if n == 3 else {"Coffee"} if n <= 5 else {"Cocoa", "Garden"}
        beans = tuple(b for b in BASE_BEANS + VARIANT_BEANS if b not in drop)
        return RuleSet("variant", n, beans, 3 if n == 3 else 2, True, 2 if n == 3 else 3)
    raise ValueError(f"unknown rules {name!r}; choose from {RULESETS}")
