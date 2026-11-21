"""Patient early, greedy late: shifts from growing fields to cashing them as the game ends."""
from bohnanza import Bot


class Closer(Bot):
    description = "Patient early (95% of growth counts), cashing in late (falls to 50% by the end)."
    details = ("Thinks in coins like the strategist, but changes gear: early on a field's future growth counts "
               "at 95%, falling steadily to 50% as the deck runs out for the last time. It builds big fields "
               "early and makes sure they're sold before the game ends.")
    EARLY_RISK = 0.95
    LATE_RISK = 0.5

    def field_value(self, view, bean, count):
        self.RISK_DISCOUNT = self.EARLY_RISK + (self.LATE_RISK - self.EARLY_RISK) * view.progress
        return super().field_value(view, bean, count)
