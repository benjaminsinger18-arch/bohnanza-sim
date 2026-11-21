"""Buys the 3rd bean field as soon as possible."""
from bohnanza import Bot


class FieldBuyer(Bot):
    description = "Buys the 3rd bean field the moment it can, cashing a field early to afford it."
    details = ("Thinks in coins like the strategist, but rushes the 3rd bean field: it buys it whenever it has "
               "3 coins, at any point in the game, and if selling one paying field would get it to 3 coins it "
               "sells the one that loses the least future value. (3-player games already start with 3 fields, "
               "so there it plays exactly like the strategist.)")
    THIRD_FIELD_MAX_PROGRESS = 1.01

    def maybe_harvest(self, view):
        out = super().maybe_harvest(view)
        cost = view.third_field_cost
        if cost is None or view.coins >= cost:
            return out
        have = view.coins + sum(view.field_payout(i) for i in out)
        if have >= cost:
            return out
        cands = [i for i in view.harvestable() if i not in out and have + view.field_payout(i) >= cost]
        if cands:
            out.append(min(cands, key=lambda i: self.field_value(view, *view.fields[i]) - view.field_payout(i)))
        return out
