"""Bets on the rare beans: short beanometers pay quickly."""
from bohnanza import Bot

COMMON = {"Blue", "Chili", "Stink", "Green", "Coffee", "Wax"}


class RareHunter(Bot):
    description = "Expects to collect 40% more of the rare beans (short beanometers) and 30% less of the common ones."
    details = ("The opposite of the specialist: it believes the rare beans (Garden, Red, Black-eyed, Soy, plus "
               "Cocoa in the variant) are where the coins are, since their beanometers pay after only a few "
               "cards. Its growth estimate counts 1.4x the rare copies still out there and 0.7x the common ones.")
    RARE_BIAS = 1.4
    COMMON_BIAS = 0.7

    def available(self, view, bean):
        return super().available(view, bean) * (self.COMMON_BIAS if bean in COMMON else self.RARE_BIAS)
