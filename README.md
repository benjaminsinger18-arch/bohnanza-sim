# 🫘 Bohnanza Bot Lab

**Let a dozen bean farmers play thousands of games of [Bohnanza](https://boardgamegeek.com/boardgame/11/bohnanza), and find out which strategy actually wins.**

Each bot is a small Python class with its own playstyle: one hoards, one trades aggressively, one targets whoever is leading. The simulator runs the full base game at 3, 4 and 5 players, enforces every rule, and gives you a leaderboard and an HTML dashboard.

```
bot                 games    win%   vs fair   coins
---------------------------------------------------
strategist           7966   29.0%     1.16x   14.26
rare_hunter          7975   28.8%     1.15x   14.19
field_grower         8086   28.7%     1.15x   14.28
contrarian           7924   28.1%     1.13x   14.16
specialist           8060   27.9%     1.12x   14.20
...
closer               8090   18.0%     0.72x   13.53
```
<sub>28,000 games, base rules, 3–5 players. "vs fair" is the win rate divided by 1 / players, so 1.00x is an average bot.</sub>

---

## ✨ What you get

- 🎲 **The real game.** All of these are enforced: hand order, planting, the bean protection rule, trading, the third bean field, three passes through the deck, and the tiebreak.
- 🤖 **14 ready-made bots** to play against each other, or against your own.
- 📊 **Clear results.** You get win rates with confidence intervals, coins per game, and splits by table size and seat. There's also a turn-by-turn replay of any game.
- 🧩 **Easy to extend.** Most new bots are a few lines that change one or two settings.

## 🚀 Get started in a minute

You need Python 3.10 or newer. Nothing else is required to run games; `pytest` is only for the tests.

```bash
git clone https://github.com/benjaminsinger18-arch/bohnanza-sim.git
cd bohnanza-sim

python -m bohnanza list                     # meet the bots
python -m bohnanza run --bots strategist,field_grower,hoarder,quick_cash \
                       --games 2000 --report --open
```

The last command plays 2,000 games, prints the leaderboard and opens the dashboard in your browser.

**Other things to try:**

```bash
# A big free-for-all at every table size
python -m bohnanza run --bots strategist,rare_hunter,contrarian,two_fields,leader_hater,trade_shark \
                       --players 3-5 --games 10000 --report

# Watch one game unfold, turn by turn
python -m bohnanza replay --seed 7 --bots strategist,hoarder,quick_cash,random

# Build one dashboard from every run so far
python -m bohnanza report --all
```

## 🧑‍🌾 Meet the bots

Every bot thinks in **coins**. They all share one valuation engine, the *strategist*, and each one shifts a setting or two to give it a personality.

| Bot | Personality |
|---|---|
| 🧠 `strategist` | The well-rounded default that everyone else is measured against |
| 🌱 `field_grower` | Loves growing fields and hates cutting them down young |
| 💎 `rare_hunter` | Goes after the rare, high-value beans |
| 🔄 `contrarian` | Avoids beans that rivals are already growing |
| 🎯 `specialist` | Sticks to the common beans that keep coming |
| ✌️ `two_fields` | Never buys a third bean field |
| 🎟️ `draft_dealer` | Pays with draft picks instead of cards |
| 🏗️ `field_buyer` | Buys the third field as soon as it can afford it |
| 😠 `leader_hater` | Won't help whoever is winning |
| 🐿️ `hoarder` | Picky: trades only for a clear gain |
| 🎁 `generous_trader` | Gives junk away freely, without caring who benefits |
| 🦈 `trade_shark` | Hates letting a trade partner gain anything |
| 💸 `quick_cash` | Impatient: sells fields early |
| ⏱️ `closer` | Plays for the long game early and cashes out late |
| 🎲 `random` | Makes random legal moves (the floor) |

## 🛠️ Write your own bot

Drop a file into `bots/` and it joins the roster automatically. The simplest bots just change a setting:

```python
# bots/gambler.py
from bohnanza import Bot

class Gambler(Bot):
    description = "Always buys a third field and never sells early."
    THIRD_FIELD_MAX_PROGRESS = 1.0
    THIRD_FIELD_MAX_PLAYERS = 99
    RISK_DISCOUNT = 1.2
```

When you want full control, override a decision:

```python
from bohnanza import Bot

class Stubborn(Bot):
    description = "Never plants a second card; harvests only at 2+ coins."

    def plant_second_card(self, view):
        return False

    def maybe_harvest(self, view):
        return [i for i in view.harvestable() if view.field_payout(i) >= 2]
```

Then put it against the others:

```bash
python -m bohnanza run --bots gambler,strategist,field_grower,rare_hunter --games 5000 --report --open
```

If a bot returns an illegal move, the engine plays the default move instead and counts it as a **violation** in the report, so a buggy bot never crashes a tournament. To make illegal moves raise an error while debugging, use `Game(..., strict=True)`.

---

## 📖 Reference

<details>
<summary><b>Command-line options</b></summary>

| Command | What it does |
|---|---|
| `list` | Show the bots it found |
| `run` | Run a tournament |
| `report` | Build the HTML dashboard (`--all` combines every run, `--run ID` shows one run) |
| `replay` | Print one game, turn by turn |

`run` options:

| Option | Meaning |
|---|---|
| `--bots a,b,c` | Which bots play |
| `--games N` | How many games to play |
| `--players 4` · `3-5` · `3,5` | Table size or sizes |
| `--seed S` | Makes results reproducible |
| `--workers N` | Parallel processes (default: all cores but one) |
| `--report` / `--open` | Build the dashboard, and open it |
| `--no-third-field` / `--no-draft-picks` | Turn off those rules |

**How bots are seated:**
- **Same number of bots as seats:** every seating order is cycled, so each bot plays each seat equally often.
- **More bots than seats:** each game draws a random subset.
- **Fewer bots than seats:** some bots are repeated at the same table.

**Where results go** (`results/`, not committed to git):
- `games.jsonl`: every game, appended across runs.
- `runs.jsonl`: run metadata.
- `report.html`: the dashboard.

</details>

<details>
<summary><b>Decision hooks a bot can override</b></summary>

| Hook | When | Return |
|---|---|---|
| `plant_second_card(view)` | Phase 1, after the mandatory front card | `bool` |
| `choose_field(view, bean)` | Every time a bean is planted | field index. Picking a field that holds a different bean harvests it first. |
| `maybe_harvest(view)` | Start of every phase, for every player | list of field indices to harvest now |
| `plant_order(view, cards)` | Phase 3 | the same cards, in the order to plant them |
| `propose_offers(view)` | Phase 2, active player, each trade round | `list[Offer]` |
| `respond_to_offer(view, offer)` | Phase 2, other players | hand indices whose beans exactly match `offer.want`, `()` to accept a gift, or `None` to decline |
| `solicit(view)` | Phase 2, other players | a `Request` (your hand cards for beans you want from the active player), or `None` |
| `choose_trade(view, deals)` | Phase 2, active player | one `Deal`, or `None` to stop trading |
| `draft_pick(view, count)` | Right after the flip, when you hold a pick on the active player | up to `count` indices into `view.flipped` (`()` = pass) |
| `buy_third_field(view)` | Start of every phase, and before a forced harvest, when you can afford it | `bool` |
| `pick_value(view, pick)` / `pick_cost(view, pick, holder)` | Used by the default trade scoring | coins |

`Bot` also provides helpers you can reuse or override: `field_value`, `card_value`, `cards_value`, `hand_value`, `pick_harvest`, `unwanted_flipped`, `find_payment`, `deal_score` and `help_weight`. Each bot gets a seeded `self.rng`.

</details>

<details>
<summary><b>What a bot can see (<code>view</code>)</b></summary>

- **Your own state:**
  - `hand`: in order; index 0 is the front card
  - `fields`: a tuple of `(bean, count)`
  - `coins`
  - `pending`: cards you got in a trade, which must be planted in phase 3
- **Opponents:** `opponents` lists each one's fields, coins and hand size. Their hand contents are hidden.
- **The table and turn:**
  - `flipped`, `discard`, `deck_size`, `deck_counts`, `removed`
  - `exhaustions` and `end_exhaustions`: how many times the deck has run out, and how many end the game
  - `active`, `phase`, `turn`, `trade_round`, `progress`, `num_players`
- **Helpers:**
  - `payout(bean, n)`, `field_payout(i)`, `next_coin(i)`, `is_maxed(i)`
  - `field_index(bean)`, `empty_field()`, `fits(bean)`, `fits_all(beans)`
  - `can_harvest(i)`, `harvestable()`, `legal_fields(bean)`, `remaining_unseen(bean)`
  - `third_field_cost`, `draft_picks`, `picks_held`, `picks_owed`, `pick_capacity()`

</details>

<details>
<summary><b>How the strategist thinks</b></summary>

| Decision | Rule |
|---|---|
| **Field value** | The larger of what the field pays if sold now and `RISK_DISCOUNT` × where it can still grow. Growth is estimated from the copies still out there: unseen cards, plus discards if the deck gets reshuffled again. |
| **Rare vs common beans** | Comes straight from the field-value estimate. Once few copies of a rare bean remain, its fields stop gaining value. It also expects `RIVAL_CUT` (30%) fewer copies of a bean for every opponent field already growing it. |
| **Planting** | It plants a second hand card only if the card extends a field, fills an empty one, or replaces a field worth selling anyway. Killing a field that pays nothing costs an extra `CHURN_PENALTY`. Every card that extends a field is worth a bonus `GROW_BONUS`. |
| **Selling fields** | Sells once a field pays and can't realistically grow. When forced to sell, it gives up the field that loses the least future value. |
| **Third field** | Buys one at tables of up to `THIRD_FIELD_MAX_PLAYERS` (4), while less than `THIRD_FIELD_MAX_PROGRESS` (60%) of the game has gone. |
| **Trading** | Accepts a trade only if it gains more than `MIN_TRADE_GAIN`, after subtracting the partner's gain × `HELP_WEIGHT` (`LEADER_HELP_WEIGHT` if the partner is leading). It offers away junk, first for a bean it needs, then for a small pick, and finally as a gift. |
| **Draft picks** | Values a pick by the flips it expects to want. When it wants a bean but has no junk card to pay with, it offers the cheapest pick that costs less than the bean is worth. |

All of these are class attributes, so you can tune them without rewriting any methods.

</details>

<details>
<summary><b>House rules: third field and draft picks</b></summary>

**Third bean field.** This is the classic rule, and it's on by default.
- In games where players start with 2 fields, a player can buy a third for 3 coins.
- Bots are asked whether to buy at the start of every phase, and just before a forced harvest.
- The 3 coin cards go back onto the discard pile.

**Draft picks.** This is a house rule, on by default.
- **What a pick is:** `Pick(cards, turns)` is a promise from the player who gives it. On each of the giver's next `turns` turns, right after the flip, the holder takes up to `cards` (1 or 2) of the flipped cards for free.
- **Trading picks:** picks are traded like cards in phase 2, using `give_picks` and `want_picks` on an `Offer` or a `Request`. A pick can also be given on its own, as a gift.
- **Limits:**
  - A player can never owe more than 2 cards across all their outstanding picks.
  - A pick lasts at most 10 turns.
  - A holder can't pass a pick on to someone else.
  - Picks not used by the end of the game are worthless.

</details>

<details>
<summary><b>Rules notes and simplifications</b></summary>

- **Rules source:** the Rio Grande rulebook. The base game is 3–5 players: the deck is played through 3 times, and the active player draws 3 cards. The 3–7 player variant with Cocoa, Wax and Coffee beans is still available with `--rules variant`.
- **Harvest timing:** in the real game you can harvest "at any time". Here, bots get the chance at the start of every phase, and a harvest also happens whenever planting forces one.
- **Trading:**
  - Trading runs for up to 20 rounds per turn.
  - The active player completes at most one deal per round.
  - Cards received in a trade must be planted, so they can't be traded again.
- **Turn order:** seat 0 always starts. The dashboard's win-by-seat chart shows the effect of turn order.
- **Not implemented:** the 2-player Bean Duel.

</details>

## 🧪 Tests

```bash
pip install -r requirements.txt
python -m pytest -q
```
