"""Harvests every field the moment it is worth at least 1 coin."""
from bohnanza import Bot


class QuickCash(Bot):
    description = "Harvests as soon as a field reaches its first coin."
    details = ('Harvests every field the moment it is worth 1 coin. Everything else uses the default.')

    def maybe_harvest(self, view):
        return [i for i in view.harvestable() if view.field_payout(i) >= 1]
