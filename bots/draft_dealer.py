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


class BigSpender(DraftDealer):
    key = "big_spender"
    description = "Like draft_dealer, but offers the biggest pick it can still afford, to win the trade."
    details = ("Same playstyle as draft_dealer, but when paying with a pick it offers the most generous pick "
               "(up to 2 cards for 2 turns) whose cost in coins is still below what it gains. It wins more "
               "trades and gives away more of its future flips, never at a loss by its own maths.")
    PICK_MENU = ((1, 1), (1, 2), (2, 1), (2, 2))

    def ev_pick(self, view, gain, partner, their_loss):
        if not view.draft_picks_allowed:
            return None
        cap = view.pick_capacity()
        menu = [Pick(c, t) for c, t in self.PICK_MENU if c <= cap]
        for pk in sorted(menu, key=lambda pk: -self.pick_cost(view, pk, partner)):
            if (self.pick_cost(view, pk, partner) < gain - self.MIN_TRADE_GAIN
                    and self.pick_value(view, pk) >= their_loss + self.MIN_TRADE_GAIN):
                return pk
        return None
