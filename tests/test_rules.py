import random
from collections import Counter

import pytest

from bohnanza import Bot, Game, Offer, make_rules, payout
from bohnanza.cards import BASE_BEANS, BEANS, VARIANT_BEANS, deck_counts

VAR = set(VARIANT_BEANS)
from bohnanza.engine import IllegalAction
from bohnanza.registry import discover, make_bot
from bohnanza.state import can_harvest_fields


# ---------------------------------------------------------------- cards & rule sets
def test_base_deck_is_104_cards():
    assert sum(deck_counts(BASE_BEANS).values()) == 104


@pytest.mark.parametrize("bean,n,coins", [
    ("Blue", 3, 0), ("Blue", 4, 1), ("Blue", 10, 4), ("Blue", 15, 4),
    ("Stink", 2, 0), ("Stink", 3, 1), ("Stink", 4, 1), ("Stink", 5, 2), ("Stink", 7, 3), ("Stink", 8, 4),
    ("Chili", 3, 1), ("Chili", 9, 4), ("Garden", 1, 0), ("Garden", 2, 2), ("Garden", 3, 3),
    ("Red", 2, 1), ("Red", 5, 4), ("Cocoa", 2, 2), ("Cocoa", 4, 4), ("Coffee", 12, 4),
    ("Wax", 3, 0), ("Wax", 4, 1), ("Wax", 7, 2), ("Wax", 9, 3), ("Wax", 11, 4),
])
def test_beanometer(bean, n, coins):
    assert payout(bean, n) == coins


@pytest.mark.parametrize("rules,n,fields,drop,draw_each,end", [
    ("base", 3, 3, VAR, False, 3), ("base", 4, 2, VAR, False, 3), ("base", 5, 2, VAR, False, 3),
    ("variant", 3, 3, {"Cocoa"}, True, 2), ("variant", 4, 2, {"Coffee"}, True, 3),
    ("variant", 5, 2, {"Coffee"}, True, 3), ("variant", 6, 2, {"Cocoa", "Garden"}, True, 3),
    ("variant", 7, 2, {"Cocoa", "Garden"}, True, 3),
])
def test_rulesets(rules, n, fields, drop, draw_each, end):
    r = make_rules(rules, n)
    assert r.fields == fields and r.draw_each == draw_each and r.end_exhaustions == end
    assert set(BEANS) - set(r.beans) == drop


@pytest.mark.parametrize("rules,n", [("base", 2), ("base", 6), ("variant", 8)])
def test_invalid_player_counts(rules, n):
    with pytest.raises(ValueError):
        make_rules(rules, n)


# ---------------------------------------------------------------- field rules
def test_bean_protection_rule():
    assert not can_harvest_fields((("Blue", 1), ("Red", 3)), 0)
    assert can_harvest_fields((("Blue", 1), ("Red", 1)), 0)
    assert can_harvest_fields((("Blue", 1), ("Red", 3)), 1)
    assert not can_harvest_fields(((None, 0), ("Red", 3)), 0)


def _game(n=4, rules="base", seed=0, bots=None):
    return Game(bots or [Bot() for _ in range(n)], seed=seed, rules=rules, strict=True)


def test_field_count_by_players():
    assert len(_game(3).players[0].fields) == 3
    assert len(_game(4).players[0].fields) == 2


def test_forced_harvest_when_no_room():
    g = _game()
    p = g.players[0]
    p.fields[0].bean, p.fields[0].count = "Blue", 4
    p.fields[1].bean, p.fields[1].count = "Red", 2
    g.plant(0, "Chili")
    beans = {f.bean for f in p.fields}
    assert "Chili" in beans and p.stats["forced_harvests"] == 1
    assert p.coins == 1  # default bot harvests the best payer (4 Blue = 1 coin, 2 Red = 1 coin; fewer cards -> Red)


def test_illegal_field_choice_is_caught():
    class Cheater(Bot):
        def choose_field(self, view, bean):
            return 0  # always field 0, even if it holds a 1-card field that's protected

    g = Game([Cheater(), Bot(), Bot(), Bot()], seed=0, strict=True)
    p = g.players[0]
    p.fields[0].bean, p.fields[0].count = "Blue", 1
    p.fields[1].bean, p.fields[1].count = "Red", 3
    with pytest.raises(IllegalAction):
        g.plant(0, "Chili")


def test_illegal_choice_falls_back_when_not_strict():
    class Cheater(Bot):
        def choose_field(self, view, bean):
            return 99

    g = Game([Cheater(), Bot(), Bot(), Bot()], seed=0)
    g.plant(0, "Chili")
    assert g.players[0].stats["violations"] == 1
    assert any(f.bean == "Chili" for f in g.players[0].fields)


# ---------------------------------------------------------------- hand order
def test_plants_front_card_only():
    seen = []

    class Spy(Bot):
        def choose_field(self, view, bean):
            seen.append(bean)
            return super().choose_field(view, bean)

        def plant_second_card(self, view):
            return False

    g = Game([Spy(), Bot(), Bot(), Bot()], seed=5, strict=True)
    front = g.players[0].hand[0]
    g.play_turn()
    assert seen[0] == front


def test_draws_go_to_back_of_hand():
    g = _game(seed=3)
    hand_before = list(g.players[0].hand)
    g.play_turn()
    p = g.players[0]
    # after planting 1-2 front cards and trading nothing from hand (default), the rest keeps order
    survivors = [c for c in hand_before[1:]]
    assert p.hand[:len(p.hand) - 3] == survivors[len(survivors) - (len(p.hand) - 3):]


# ---------------------------------------------------------------- trading
def test_received_cards_cannot_be_retraded():
    """Cards received in a trade go to `pending`, never the hand, so no offer can index them."""
    class Giver(Bot):
        def propose_offers(self, view):
            return [Offer(give_flipped=(0,))] if view.flipped else []

        def choose_trade(self, view, deals):
            return deals[0] if deals else None

    class Taker(Bot):
        def respond_to_offer(self, view, offer):
            return ()

        def solicit(self, view):
            return None

    g = Game([Giver(), Taker(), Taker(), Taker()], seed=1, strict=True)
    hand_sizes = [len(p.hand) for p in g.players]
    g.phase = 2
    g.flipped = [g.deck.pop(), g.deck.pop()]
    g.trade_phase()
    taker = g.players[1]
    assert taker.pending  # got a gift
    assert len(taker.hand) == hand_sizes[1]  # not in the hand
    g.deck.extend(g.flipped)  # restore for conservation
    g.flipped = []
    g.deck.extend(taker.pending)
    taker.pending = []
    g.check_conservation()


def test_payment_must_match_want():
    class Liar(Bot):
        def respond_to_offer(self, view, offer):
            return (0,)  # pays with front card regardless of what's wanted

    class Asker(Bot):
        def propose_offers(self, view):
            return [Offer(give_flipped=(0,), want=("NotABean",))] if view.flipped else []

    g = Game([Asker(), Liar(), Liar(), Liar()], seed=2)
    g.phase = 2
    g.flipped = [g.deck.pop(), g.deck.pop()]
    g.trade_phase()
    assert sum(p.stats["violations"] for p in g.players[1:]) >= 1
    assert g.trades == 0


def test_cannot_offer_field_cards():
    class FieldOffer(Bot):
        def propose_offers(self, view):
            return [Offer(give_hand=(50,))]  # not a hand index

    g = Game([FieldOffer(), Bot(), Bot(), Bot()], seed=2)
    g.phase = 2
    g.trade_phase()
    assert g.players[0].stats["violations"] >= 1


# ---------------------------------------------------------------- game end
@pytest.mark.parametrize("rules,n", [("base", 3), ("base", 4), ("base", 5),
                                     ("variant", 3), ("variant", 5), ("variant", 7)])
def test_game_ends_on_correct_exhaustion(rules, n):
    g = _game(n, rules, seed=11)
    g.play()
    assert g.exhaustions == g.rules.end_exhaustions
    assert all(f.bean is None for p in g.players for f in p.fields)  # final harvest


def test_tiebreak_furthest_from_start():
    g = _game(4, seed=0)
    for p in g.players:
        p.hand.clear()
    g.deck = []
    g.discard = []
    g.ending = True
    g.counts = Counter()
    g.removed = Counter()
    res = g.play()
    winner = next(p for p in res["players"] if p["win"])
    assert winner["seat"] == 3  # all tied on 0 -> last seat wins


# ---------------------------------------------------------------- whole games
def test_conservation_many_random_games():
    keys = sorted(discover())
    rng = random.Random(0)
    for i in range(300):
        rules = rng.choice(["base", "variant"])
        n = rng.randint(3, 5 if rules == "base" else 7)
        bots = [make_bot(rng.choice(keys)) for _ in range(n)]
        res = Game(bots, seed=i, rules=rules, check=True).play()
        assert sum(p["violations"] for p in res["players"]) == 0, (i, res)


def test_deterministic():
    def run():
        bots = [make_bot(k) for k in ("random", "hoarder", "quick_cash", "stingy")]
        return Game(bots, seed=42).play()
    assert run() == run()
