"""Never buys a 3rd bean field: keeps its coins."""
from bohnanza import Bot


class TwoFields(Bot):
    description = "Never buys a 3rd bean field; plays the strategist's game with 2 fields."
    details = ("Plays exactly like the strategist, except it never spends 3 coins on a 3rd bean field. "
               "Shows what the 3rd field is worth. (3-player games start with 3 fields, so there it is "
               "identical to the strategist.)")

    def buy_third_field(self, view):
        return False
