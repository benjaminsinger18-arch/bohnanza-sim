"""Focuses on the most common beans (easier to grow big) and dumps rare ones fast."""
from bohnanza import Bot

PREFERRED = {"Blue", "Chili", "Stink", "Green", "Coffee", "Wax"}


class Specialist(Bot):
    description = "Prefers common beans (Blue/Chili/Stink/Green, Coffee/Wax); dumps rare ones."
    details = ('Prefers the common beans (Blue, Chili, Stink, Green, plus Coffee and Wax in the variant). Sacrifices and cashes out rare beans first and turns down trades for them.')

    def card_value(self, view, bean):
        v = super().card_value(view, bean)
        return v + (0.5 if bean in PREFERRED else -0.5)

    def plant_second_card(self, view):
        b = view.hand[0]
        return view.field_index(b) is not None or (view.empty_field() is not None and b in PREFERRED)

    def pick_harvest(self, view):
        # sacrifice non-preferred fields first
        return max(view.harvestable(),
                   key=lambda i: (view.fields[i][0] not in PREFERRED, view.field_payout(i), -view.fields[i][1]))

    def maybe_harvest(self, view):
        out = super().maybe_harvest(view)
        # cash in rare beans as soon as they pay, freeing the field
        out += [i for i in view.harvestable()
                if i not in out and view.fields[i][0] not in PREFERRED and view.field_payout(i) >= 1]
        return out

    def respond_to_offer(self, view, offer):
        if any(b not in PREFERRED and view.field_index(b) is None for b in offer.gives):
            return None
        return super().respond_to_offer(view, offer)
