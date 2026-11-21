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
    class NoHandTrades(Bot):
        def propose_offers(self, view):
            return []

    g = Game([NoHandTrades(), Bot(), Bot(), Bot()], seed=3, strict=True)
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
        bots = [make_bot(k) for k in ("random", "hoarder", "quick_cash", "field_grower")]
        return Game(bots, seed=42).play()
    assert run() == run()


# ---------------------------------------------------------------- draft picks
from bohnanza import Pick, Request  # noqa: E402
from bohnanza.engine import DraftPick  # noqa: E402


def test_pick_taken_before_trading_and_expires():
    g = _game(4, seed=1)
    g.picks = [DraftPick(giver=0, holder=2, cards=1, turns_left=2)]
    g.flipped = [g.deck.pop(), g.deck.pop()]

    class Grab(Bot):
        def draft_pick(self, view, count):
            return (0,)

    g.bots[2] = Grab()
    first = g.flipped[0]
    g.exercise_picks()
    assert g.players[2].pending == [first] and len(g.flipped) == 1
    assert g.picks[0].turns_left == 1
    g.exercise_picks()
    assert g.picks == []  # used on both of the giver's turns, then gone
    assert g.players[2].stats["pick_cards_taken"] == 2 and g.players[0].stats["pick_cards_lost"] == 2


def test_pick_only_applies_on_givers_turn():
    g = _game(4, seed=1)
    g.picks = [DraftPick(giver=1, holder=2, cards=2, turns_left=1)]
    g.active = 0
    g.flipped = [g.deck.pop(), g.deck.pop()]
    g.exercise_picks()
    assert len(g.flipped) == 2 and len(g.picks) == 1


def test_cannot_owe_more_than_two_cards():
    g = _game(4)
    g.picks = [DraftPick(giver=1, holder=2, cards=2, turns_left=3)]
    assert not g.can_promise(1, (Pick(1, 1),))
    assert g.can_promise(3, (Pick(2, 5),))
    assert not g.can_promise(3, (Pick(1, 1), Pick(2, 1)))


def test_pick_traded_via_request_and_not_used_same_turn():
    class Buyer(Bot):
        def solicit(self, view):
            if view.flipped and view.pick_capacity() >= 2:
                return Request(give_picks=(Pick(2, 3),), want=(view.flipped[0],))
            return None

    class Seller(Bot):  # active player: values picks highly
        def pick_value(self, view, pick):
            return 10

        def propose_offers(self, view):
            return []

    g = Game([Seller(), Buyer(), Bot(), Bot()], seed=3, strict=True)
    g.play_turn()
    assert len(g.picks) == 1
    p = g.picks[0]
    assert (p.giver, p.holder, p.cards, p.turns_left) == (1, 0, 2, 3)
    assert g.players[1].stats["picks_given"] == 1 and g.players[0].stats["picks_received"] == 1


def test_draft_picks_can_be_disabled():
    class Buyer(Bot):
        def solicit(self, view):
            return Request(give_picks=(Pick(1, 1),), want=()) if view.flipped else None

    g = Game([Bot(), Buyer(), Bot(), Bot()], seed=3, draft_picks=False)
    g.play_turn()
    assert g.picks == [] and g.players[1].stats["violations"] >= 1


def test_bad_pick_shapes_rejected():
    class Bad(Bot):
        def solicit(self, view):
            return Request(give_picks=(Pick(3, 1),)) if view.flipped else None

    g = Game([Bot(), Bad(), Bot(), Bot()], seed=3)
    g.play_turn()
    assert all(p.giver != 1 for p in g.picks) and g.players[1].stats["violations"] >= 1


# ---------------------------------------------------------------- third bean field
def _put(g, seat, idx, bean, count):
    """Place beans in a field, taking them out of the deck/hands so card counts stay right."""
    for _ in range(count):
        if bean in g.deck:
            g.deck.remove(bean)
        else:
            next(q.hand for q in g.players if bean in q.hand).remove(bean)
    f = g.players[seat].fields[idx]
    f.bean, f.count = bean, count


def test_buy_third_field_pays_coins_back_into_discard():
    g = _game(4, seed=2)
    p = g.players[0]
    _put(g, 0, 0, "Red", 5)
    g.harvest(0, 0)  # 5 Red -> 4 coins
    disc_before = len(g.discard)
    g.offer_field(0)  # strategist buys early in the game
    assert len(p.fields) == 3 and p.coins == 1 and len(p.coin_cards) == 1
    assert len(g.discard) == disc_before + 3 and p.stats["bought_third_field"] == 1
    g.check_conservation()
    g.offer_field(0)
    assert len(p.fields) == 3  # only one extra field


def test_cannot_buy_without_coins_or_when_disabled():
    g = _game(4, seed=2)
    g.offer_field(0)
    assert len(g.players[0].fields) == 2
    g2 = Game([Bot() for _ in range(4)], seed=2, third_field=False)
    p = g2.players[0]
    p.coins, p.coin_cards = 3, ["Red"] * 3
    g2.offer_field(0)
    assert len(p.fields) == 2


def test_three_player_game_has_no_purchase():
    g = _game(3)
    assert g.view(0).third_field_cost is None


def test_buy_offered_before_forced_harvest():
    g = _game(4, seed=2)
    p = g.players[0]
    _put(g, 0, 0, "Blue", 3)
    _put(g, 0, 1, "Red", 1)
    p.coins, p.coin_cards = 3, ["Soy"] * 3
    g.removed["Soy"] += 3
    g.deck.remove("Soy"); g.deck.remove("Soy"); g.deck.remove("Soy")
    g.deck.remove("Chili")
    g.plant(0, "Chili")
    assert len(p.fields) == 3 and p.stats["forced_harvests"] == 0
    g.check_conservation()


# ---------------------------------------------------------------- strategist valuation
def test_rare_bean_with_no_copies_left_is_sold():
    from bohnanza.registry import make_bot
    b = make_bot("strategist")
    g = Game([b, Bot(), Bot(), Bot()], seed=0)
    v = g.view(0)
    from dataclasses import replace
    v = replace(v, fields=(("Garden", 3), (None, 0)))  # Garden maxes at 3 -> nothing left to gain
    assert b.maybe_harvest(v) == [0]
    v2 = replace(v, fields=(("Blue", 6), (None, 0)))  # plenty of Blue still out there early on
    assert b.maybe_harvest(v2) == []


# ---------------------------------------------------------------- strategist planting
def _front(g, seat, beans):
    """Put these beans at the front of a player's hand (swapping them in from the deck)."""
    p = g.players[seat]
    for b in reversed(beans):
        g.deck.remove(b)
        g.deck.append(p.hand.pop())
        p.hand.insert(0, b)


def test_strategist_keeps_second_card_that_would_kill_a_young_field():
    g = _game(4, seed=5)
    _put(g, 0, 0, "Blue", 1)
    _put(g, 0, 1, "Chili", 1)
    _front(g, 0, ["Stink"])
    assert g.bots[0].plant_second_card(g.view(0)) is False
    _front(g, 0, ["Blue"])
    assert g.bots[0].plant_second_card(g.view(0)) is True
    g.check_conservation()


def test_strategist_offers_junk_front_card_away():
    g = _game(4, seed=5)
    _put(g, 0, 0, "Blue", 2)
    _put(g, 0, 1, "Chili", 2)
    _front(g, 0, ["Stink"])
    v = g.view(0)
    offers = g.bots[0].propose_offers(v)
    assert any(o.give_hand == (0,) for o in offers)
