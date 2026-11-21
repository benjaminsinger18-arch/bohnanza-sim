"""Never promises a draft pick, but happily takes them."""
from bohnanza import Bot


class PickMiser(Bot):
    description = "Never promises draft picks (pays only with cards), but takes any pick offered."
    details = ("Thinks in coins like the strategist, but its future flips are not for sale: it never offers or "
               "agrees to give a draft pick, so it pays for beans only with cards. It still sells junk for picks "
               "and accepts picks other players offer.")
    PICK_MENU = ()

    def respond_to_offer(self, view, offer):
        return None if offer.want_picks else super().respond_to_offer(view, offer)

    def choose_trade(self, view, deals):
        return super().choose_trade(view, tuple(d for d in deals if not d.active_gives_picks))
