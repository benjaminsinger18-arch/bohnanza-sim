"""Never buys a 3rd bean field: keeps its coins."""
from bohnanza import Bot


class TwoFields(Bot):
    description = "Never buys a 3rd bean field, even at 4 players (where the strategist buys one)."
    details = ("Plays exactly like the strategist, except it never spends 3 coins on a 3rd bean field. The "
               "strategist buys one at 4-player tables and skips it at 5, so this bot only differs at 4 players.")

    def buy_third_field(self, view):
        return False
