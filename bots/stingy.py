"""Never trades and never accepts gifts."""
from bohnanza import Bot


class Stingy(Bot):
    description = "Never trades or accepts gifts."
    details = ('Never trades: no offers, no requests, and it refuses gifts.')

    def propose_offers(self, view):
        return []

    def respond_to_offer(self, view, offer):
        return None

    def solicit(self, view):
        return None

    def choose_trade(self, view, deals):
        return None
