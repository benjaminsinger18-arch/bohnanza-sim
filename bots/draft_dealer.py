"""Bots that would rather pay with draft picks (future flipped cards) than with hand cards."""
from bohnanza import Bot, Offer, Pick, Request


class DraftDealer(Bot):
    key = "draft_dealer"
    description = "Pays with draft picks first, small ones (1 card, 1-2 turns), always priced in coins."
    details = ("Thinks in coins like the strategist, but reaches for draft picks first: when it wants a flipped "
               "card it offers the cheapest pick that still leaves it a gain before considering hand cards, it "
               "tries to sell unwanted flips for a pick on the first trade round, and it only ever promises "
               "small picks (1 card for 1-2 turns).")
    PICK_MENU = ((1, 1), (1, 2))

    def solicit(self, view):
        best, best_net = None, self.MIN_TRADE_GAIN
        base = self.cards_value(view, view.pending)
        for b in set(view.flipped):
            gain = self.cards_value(view, list(view.pending) + [b]) - base
            pk = self.ev_pick(view, gain, view.active, float("-inf"))
            if pk:
                net = gain - self.pick_cost(view, pk, view.active)
                if net > best_net:
                    best, best_net = Request(give_picks=(pk,), want=(b,)), net
        return best or super().solicit(view)

    def propose_offers(self, view):
        offers = super().propose_offers(view)
        if view.trade_round == 0 and view.draft_picks_allowed:
            offers = [Offer(give_flipped=o.give_flipped, give_hand=o.give_hand, want_picks=(Pick(1, 1),))
                      if (o.give_flipped or o.give_hand) and not o.give_picks else o for o in offers]
        return offers

