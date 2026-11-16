"""Baseline: random legal choices everywhere. Everything should beat this."""
from bohnanza import Bot, Offer, Request


class RandomBot(Bot):
    key = "random"
    description = "Random legal moves (baseline)."
    details = ('Makes random legal moves. This is the floor every real strategy should beat.')

    def plant_second_card(self, view):
        return self.rng.random() < 0.5

    def choose_field(self, view, bean):
        return self.rng.choice(view.legal_fields(bean))

    def maybe_harvest(self, view):
        h = view.harvestable()
        return [self.rng.choice(h)] if h and self.rng.random() < 0.05 else []

    def plant_order(self, view, cards):
        cards = list(cards)
        self.rng.shuffle(cards)
        return cards

    def propose_offers(self, view):
        if not view.flipped or self.rng.random() < 0.4:
            return []
        i = self.rng.randrange(len(view.flipped))
        want = (self.rng.choice(list(view.deck_counts)),) if self.rng.random() < 0.5 else ()
        return [Offer(give_flipped=(i,), want=want)]

    def respond_to_offer(self, view, offer):
        if self.rng.random() < 0.3:
            return self.find_payment(view, offer.want, allow_field_beans=True)
        return None

    def solicit(self, view):
        if view.flipped and view.hand and self.rng.random() < 0.2:
            return Request(give_hand=(self.rng.randrange(len(view.hand)),),
                           want=(self.rng.choice(view.flipped),))
        return None

    def choose_trade(self, view, deals):
        return self.rng.choice(deals) if self.rng.random() < 0.5 else None

    def buy_third_field(self, view):
        return self.rng.random() < 0.1

    def draft_pick(self, view, count):
        idx = list(range(len(view.flipped)))
        self.rng.shuffle(idx)
        return tuple(idx[:self.rng.randint(0, count)])
