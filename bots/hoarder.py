"""Grows fields big, only harvests when maxed or forced, and only accepts beans it already grows."""
from bohnanza import Bot


class Hoarder(Bot):
    description = "Grows long fields; harvests only when maxed or forced; picky trader."
    details = ('Grows long fields. Only plants a second card if it extends an existing field, keeping empty fields free, and only accepts traded beans it already grows.')

    def plant_second_card(self, view):
        # only if it extends an existing field (keeps empty fields free for flips/trades)
        return view.field_index(view.hand[0]) is not None

    def pick_harvest(self, view):
        # when forced, cash the field that pays most right now; ties -> the bigger one
        return max(view.harvestable(), key=lambda i: (view.field_payout(i), view.fields[i][1]))

    def respond_to_offer(self, view, offer):
        if not all(view.field_index(b) is not None for b in offer.gives):
            return None
        return self.find_payment(view, offer.want)
