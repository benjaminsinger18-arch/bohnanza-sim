"""Bets on common beans: expects to collect more of them, and less of the rare ones."""
from bohnanza import Bot

COMMON = {"Blue", "Chili", "Stink", "Green", "Coffee", "Wax"}


class Specialist(Bot):
    description = "Expects to collect 40% more of the common beans and 40% less of the rare ones."
    details = ("Thinks in coins like the strategist, but its growth estimate favours the common beans (Blue, "
               "Chili, Stink, Green, plus Coffee and Wax in the variant): it expects to collect 1.4x as many of "
               "them and 0.6x as many rare ones. Every decision (planting, selling, trading, picks) follows "
               "from that, so it keeps common fields and sells or trades away rare ones.")
    COMMON_BIAS = 1.4
    RARE_BIAS = 0.6

    def available(self, view, bean):
        return super().available(view, bean) * (self.COMMON_BIAS if bean in COMMON else self.RARE_BIAS)
