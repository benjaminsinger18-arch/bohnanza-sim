"""Really wants to grow its fields: pays extra for beans that extend them and never sells early."""
from bohnanza import Bot


class FieldGrower(Bot):
    description = "Lives to grow fields: +1.5 coins on every card that extends one (strategist +0.75)."
    details = ("Thinks in coins like the strategist, but takes field growth to the extreme: every card that "
               "extends one of its fields is worth an extra 1.5 coins to it (strategist 0.75), and killing a young "
               "field costs it 2 coins (strategist 1). So it buys its own beans very aggressively (cards, junk or "
               "draft picks) and only sells a field once it truly can't grow any more.")
    CHURN_PENALTY = 2.0
    GROW_BONUS = 1.5
