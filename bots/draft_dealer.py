"""Bots that pay with draft picks (future flipped cards) instead of hand cards."""
from bohnanza import Bot, Offer, Pick, Request


class DraftDealer(Bot):
    key = "draft_dealer"
    description = "Buys beans it needs with 1-card, 1-turn draft picks; sells junk flips for picks."
    details = ("Pays for cards with draft picks instead of hand cards: asks for flipped cards that match its "
               "fields in exchange for a pick, offers picks to buy its main bean from other hands, and tries "
               "to sell unusable flipped cards for a pick before giving them away. Promises 1 card for 1 turn.")
    PICK_CARDS = 1
    PICK_TURNS = 1

    @property
    def pick(self) -> Pick:
        return Pick(self.PICK_CARDS, self.PICK_TURNS)

    def can_pay_pick(self, view) -> bool:
        return view.draft_picks_allowed and view.pick_capacity() >= self.PICK_CARDS

    # --- as a non-active player: buy flipped cards with picks
    def solicit(self, view):
        for b in view.flipped:
            if view.field_index(b) is not None and view.fits_all(list(view.pending) + [b]):
                if self.can_pay_pick(view):
                    return Request(give_picks=(self.pick,), want=(b,))
                return super().solicit(view)
        return None

    def respond_to_offer(self, view, offer):
        if offer.want_picks:
            if not all(view.field_index(b) is not None for b in offer.gives) or not offer.gives:
                return None
            if sum(p.cards for p in offer.want_picks) > view.pick_capacity():
                return None
            return self.find_payment(view, offer.want)
        return super().respond_to_offer(view, offer)

    # --- as the active player
    def propose_offers(self, view):
        offers = []
        junk = self.unwanted_flipped(view)
        if view.trade_round == 0 and view.draft_picks_allowed:
            offers += [Offer(give_flipped=(i,), want_picks=(Pick(1, 1),)) for i in junk]
        else:
            offers += super().propose_offers(view)
        # buy my biggest field's bean from other players' hands with a pick
        biggest = max((f for f in view.fields if f[0]), key=lambda f: f[1], default=None)
        if biggest and self.can_pay_pick(view):
            offers.append(Offer(give_picks=(self.pick,), want=(biggest[0],)))
        return offers


class BigSpender(DraftDealer):
    key = "big_spender"
    description = "Like draft_dealer, but promises 2 cards for 2 turns per pick."
    details = ("Same playstyle as draft_dealer, but every pick it gives is worth 2 cards on each of its next "
               "2 turns. It wins more trades but gives away far more of its own future flips.")
    PICK_CARDS = 2
    PICK_TURNS = 2
