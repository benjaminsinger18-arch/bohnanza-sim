"""Hates on the leader: never feeds them, steers gifts and picks to everyone else."""
from bohnanza import Bot, Offer


class LeaderHater(Bot):
    description = "Treats every coin the leader gains as costing it 3; steers gifts to the other players."
    details = ("Thinks in coins like the strategist, but the leader (the richest opponent, if they're level with "
               "it or ahead) is the enemy: anything a trade, gift or draft pick gives the leader counts 3x "
               "against it (strategist 0.6x), it won't ask the leader for cards unless it pays with junk the "
               "leader can't use, and its giveaways go only to the other players.")
    LEADER_HATE = 3.0

    def leader(self, view):
        top = max(view.opponents, key=lambda o: o.coins, default=None)
        return top.seat if top is not None and top.coins >= view.coins else None

    def help_weight(self, view, seat):
        if seat is not None and seat == self.leader(view):
            return self.LEADER_HATE
        return self.HELP_WEIGHT

    def propose_offers(self, view):
        lead = self.leader(view)
        out = []
        for o in super().propose_offers(view):
            gift = (o.give_flipped or o.give_hand) and not (o.want or o.want_picks or o.give_picks)
            if gift and lead is not None and o.to is None:  # giveaways go to everyone but the leader
                out += [Offer(give_flipped=o.give_flipped, give_hand=o.give_hand, to=x.seat)
                        for x in view.opponents if x.seat != lead]
            else:
                out.append(o)
        return out[:8]

    def solicit(self, view):
        req = super().solicit(view)
        if req is None or view.active != self.leader(view):
            return req
        # from the leader: only if what I hand over is useless to them
        if req.give_picks:
            return None
        if all(self.their_card_value(view, view.active, view.hand[i]) < 0 for i in req.give_hand):
            return req
        return None
