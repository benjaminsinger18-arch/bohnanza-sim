"""Bean types, card counts and beanometers (from the Rio Grande rulebook)."""
from collections import Counter

# name: (number of cards, cards needed for 1, 2, 3, 4 coins; None = not possible)
BEANS: dict[str, tuple[int, tuple]] = {
    "Blue":      (20, (4, 6, 8, 10)),
    "Chili":     (18, (3, 6, 8, 9)),
    "Stink":     (16, (3, 5, 7, 8)),
    "Green":     (14, (3, 5, 6, 7)),
    "Soy":       (12, (2, 4, 6, 7)),
    "BlackEyed": (10, (2, 4, 5, 6)),
    "Red":       (8,  (2, 3, 4, 5)),
    "Garden":    (6,  (None, 2, 3, None)),
    # 3-7 player variant beans
    "Coffee":    (24, (4, 7, 10, 12)),
    "Wax":       (22, (4, 7, 9, 11)),
    "Cocoa":     (4,  (None, 2, 3, 4)),
}
BASE_BEANS = ("Blue", "Chili", "Stink", "Green", "Soy", "BlackEyed", "Red", "Garden")
VARIANT_BEANS = ("Coffee", "Wax", "Cocoa")
BEAN_NAMES: tuple[str, ...] = tuple(BEANS)


def deck_counts(beans) -> Counter:
    return Counter({b: BEANS[b][0] for b in beans})


def build_deck(beans) -> list[str]:
    return [b for b in beans for _ in range(BEANS[b][0])]


def payout(bean: str | None, n: int) -> int:
    """Gold coins earned by harvesting n cards of this bean."""
    if bean is None:
        return 0
    coins = 0
    for c, t in enumerate(BEANS[bean][1], start=1):
        if t is not None and n >= t:
            coins = c
    return coins


def next_threshold(bean: str, n: int) -> int | None:
    """Field size at which the next coin is earned, or None if already maxed."""
    for t in BEANS[bean][1]:
        if t is not None and t > n:
            return t
    return None


def max_threshold(bean: str) -> int:
    return max(t for t in BEANS[bean][1] if t is not None)
