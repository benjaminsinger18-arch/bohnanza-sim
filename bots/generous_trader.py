"""Trades freely: doesn't mind helping opponents, takes any trade that doesn't cost it."""
from bohnanza import Bot, Offer


class GenerousTrader(Bot):
    description = "Ignores how much trades help others; gives junk away at once; takes any non-losing trade."
    details = ("Thinks in coins like the baseline, but only counts its own side of a trade: a partner's gain "
               "doesn't count against it (baseline 25%, 60% vs the leader), any trade that isn't a loss is "
               "accepted, and cards that would hurt its fields are given away immediately instead of being "
               "sold first. Keeps its fields clean and makes friends, at the cost of feeding opponents.")
    HELP_WEIGHT = 0.0
    LEADER_HELP_WEIGHT = 0.0
    MIN_TRADE_GAIN = 0.0
    JUNK_HAND_THRESHOLD = 0.0

    def propose_offers(self, view):
        offers = super().propose_offers(view)
        if view.trade_round == 0:  # give junk away now instead of selling it first
            offers = [Offer(give_flipped=o.give_flipped, give_hand=o.give_hand, to=o.to)
                      if (o.give_flipped or o.give_hand) and not o.give_picks else o for o in offers]
        return offers
