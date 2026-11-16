"""Keeps fields clean at any cost: gives away whatever doesn't fit, pays extra for beans it grows."""
from bohnanza import Bot, Offer, Request


class GenerousTrader(Bot):
    description = "Gifts unwanted cards immediately (flipped and front-of-hand); pays 2-for-1."
    details = ('Keeps fields clean at any cost: gives away every unusable flipped card plus front hand cards that would force a harvest, pays 2-for-1 for beans it wants, and accepts any trade that is not a net loss.')

    def propose_offers(self, view):
        offers = [Offer(give_flipped=(i,)) for i in self.unwanted_flipped(view)]
        # also dump front hand cards that would force a harvest next turn
        for i, b in enumerate(view.hand[:2]):
            if not view.fits(b):
                offers.append(Offer(give_hand=(i,)))
        return offers

    def choose_trade(self, view, deals):
        best = max(deals, key=lambda d: self.deal_score(view, d))
        return best if self.deal_score(view, best) >= 0 else None

    def respond_to_offer(self, view, offer):
        if offer.want_picks:  # never promises draft picks
            return None
        if not view.fits_all(list(view.pending) + list(offer.gives)):
            return None
        return self.find_payment(view, offer.want, allow_field_beans=True)

    def solicit(self, view):
        for b in view.flipped:
            if view.field_index(b) is not None:
                junk = [i for i, h in enumerate(view.hand) if h not in view.my_beans][:2]
                return Request(give_hand=tuple(junk), want=(b,))
        return None
