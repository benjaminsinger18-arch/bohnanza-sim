"""Really wants to grow its fields: pays extra for beans that extend them and never sells early."""
from bohnanza import Bot


class FieldGrower(Bot):
    description = "Lives to grow fields: +0.5 coin on every card that extends one, counts 100% of growth."
    details = ("Thinks in coins like the strategist, but every card that extends one of its fields is worth "
               "an extra 0.5 coins to it, a field's future growth counts in full (strategist 85%), and killing a "
               "young field costs it 1.5 coins. So it buys its own beans aggressively (cards, junk or draft picks) "
               "and only sells a field once it truly can't grow any more.")
    RISK_DISCOUNT = 1.0
    CHURN_PENALTY = 1.5
    GROW_BONUS = 0.5

    def _card_value(self, view, bean):
        v = super()._card_value(view, bean)
        return v + self.GROW_BONUS if view.field_index(bean) is not None else v
