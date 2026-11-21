"""Impatient: a coin now beats a bigger field later."""
from bohnanza import Bot


class QuickCash(Bot):
    description = "Impatient: counts only 60% of a field's future growth, so it cashes fields early."
    details = ("Thinks in coins like the strategist, but trusts the future less: a field's growth counts at 60% "
               "(strategist 100%), so it sells fields as soon as the coins in hand beat that discounted growth. "
               "Smaller, safer harvests; fewer big payouts.")
    RISK_DISCOUNT = 0.6
