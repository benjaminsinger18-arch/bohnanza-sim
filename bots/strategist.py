"""The strategist: the full coin-counting strategy (the Bot defaults), so it can sit at the table."""
from bohnanza import Bot


class Strategist(Bot):
    description = "Judges every decision in expected coins; the strategy every other bot builds on."
    details = ("Judges every decision in coins: a field is worth what it pays now or, if more copies are still "
               "out there, a discounted estimate of what it can grow to. It sells fields only once they can't "
               "realistically grow, buys a 3rd field early, trades only when it gains after counting the help it "
               "gives the partner (more so if the partner leads), and prices draft picks by the flips it expects.")
