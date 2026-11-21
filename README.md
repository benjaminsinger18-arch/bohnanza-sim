# Bohnanza Bot Lab

Simulates thousands of Bohnanza games between bots you write, then reports which strategies win.

- **Rules:** the base game for 3–5 players (`--rules base`) and the 3–7 player variant with Cocoa, Wax and Coffee beans (`--rules variant`). Rules come from the Rio Grande rulebook.
- **Rule enforcement:** hand order, the bean protection rule, the trade restrictions, deck run-outs and the tiebreak are all enforced.
- **Bots:** each bot is a Python class in `bots/`.
- **Output:** a terminal leaderboard plus an HTML dashboard.

## Quick start

```bash
python -m bohnanza list                                   # bots it found
python -m bohnanza run --bots strategist,hoarder,quick_cash,field_grower --games 5000 --report --open
python -m bohnanza run --bots strategist,field_grower,rare_hunter,contrarian,specialist,generous_trader \
       --rules variant --players 3-7 --games 5000 --report
python -m bohnanza report --all                           # combine every run so far
python -m bohnanza replay --seed 7 --bots strategist,hoarder,quick_cash,random   # one game, turn by turn
```

`run` options:
- **`--games N`:** how many games to play.
- **`--seed S`:** makes results reproducible.
- **`--players 4 | 3-5 | 3,5`:** table size or sizes.
- **`--rules base|variant`:** which rule set.
- **`--workers N`:** number of parallel processes (default: all cores but one).

### How bots are seated

- **Same number of bots as seats:** the runner cycles through every seating order, so each bot plays each seat equally often.
- **More bots than seats:** each game draws a random subset of bots.
- **Fewer bots than seats:** some bots are repeated at the same table.

### Where results go

- Every game is appended to `results/games.jsonl`, so history builds up across runs.
- Run metadata goes to `results/runs.jsonl`.
- The dashboard is written to `results/report.html`.

## Starter bots

All of them think in coins, using the strategist's valuation; each one shifts a setting or two to express a playstyle. `random` is the exception, kept as a floor.

| Bot | Playstyle |
|---|---|
| `strategist` | The defaults, unchanged |
| `quick_cash` | Impatient: `RISK_DISCOUNT = 0.6`, so it cashes fields early |
| `hoarder` | Picky: `CHURN_PENALTY = 2`, trades only for gains of 0.4+ coins |
| `specialist` | Expects 1.4× the common beans and 0.6× the rare ones |
| `generous_trader` | Ignores how much trades help others, gives junk away at once |
| `draft_dealer` / `big_spender` | Pay with draft picks first (small / biggest affordable) |
| `leader_hater` | Anything that helps the leader counts 3× against it; gifts go to everyone else |
| `field_buyer` | Buys the 3rd field the moment it can, cashing a field early to afford it |
| `two_fields` | Never buys a 3rd field |
| `field_grower` | +1.5 coins on every card that extends a field (strategist +0.75); killing a young field costs 2 |
| `rare_hunter` | Expects 1.4× the rare beans and 0.7× the common ones |
| `contrarian` | Expects 30% fewer copies of a bean for every rival field growing it |
| `pick_miser` | Never promises draft picks, but takes them |
| `closer` | Counts 100% of growth early, falling to 50% by the end |
| `trade_shark` | A partner's gain counts 80% against it (150% vs the leader); wants 0.2+ coins per trade |
| `random` | Random legal moves |

## Writing a bot

Create `bots/my_bot.py`. Its key becomes the filename (`my_bot`), unless you set `key = "..."`. Override only the decisions you care about; everything else uses the defaults in `bohnanza/bot.py`.

```python
from bohnanza import Bot, Offer, Request

class MyBot(Bot):
    description = "Harvests at 2 coins, never plants a second card."

    def plant_second_card(self, view):
        return False

    def maybe_harvest(self, view):
        return [i for i in view.harvestable() if view.field_payout(i) >= 2]
```

### Decision hooks

| Hook | When | Return |
|---|---|---|
| `plant_second_card(view)` | Phase 1, after the mandatory front card | `bool` |
| `choose_field(view, bean)` | Every time a bean is planted | field index. Picking a field that holds a different bean harvests it first. |
| `maybe_harvest(view)` | Start of every phase, for every player | list of field indices to harvest now |
| `plant_order(view, cards)` | Phase 3 | the same cards in the order you want them planted |
| `propose_offers(view)` | Phase 2, active player, each trade round | `list[Offer]` |
| `respond_to_offer(view, offer)` | Phase 2, other players | hand indices whose beans exactly match `offer.want`, `()` to accept a gift, or `None` to decline |
| `solicit(view)` | Phase 2, other players | a `Request` (your hand cards → beans you want from the active player), or `None` |
| `choose_trade(view, deals)` | Phase 2, active player | one `Deal`, or `None` to stop trading |
| `draft_pick(view, count)` | Phase 2, right after the flip, when you hold a pick on the active player | up to `count` indices into `view.flipped` to take (`()` = pass) |
| `buy_third_field(view)` | Start of every phase, and before a forced harvest, when you can afford it | `bool` |
| `pick_value(view, pick)` / `pick_cost(view, pick, holder)` | Used by the default trade scoring | what a `Pick` is worth to receive / costs to promise, in coins |

`Bot` also provides helpers you can override and reuse: `card_value`, `pick_harvest`, `unwanted_flipped`, `find_payment` and `deal_score`. Each bot gets a seeded `self.rng`.

### What a bot can see (`view`)

**Your own state:**
- `hand`: in order, index 0 is the front card
- `fields`: a tuple of `(bean, count)`
- `coins`
- `pending`: cards you received in a trade, which must be planted in phase 3

**Opponents:** `opponents` lists each one's fields, coins and hand size. Their hand contents are hidden.

**The table and turn:**
- `flipped`, `discard`, `deck_size`
- `exhaustions` and `end_exhaustions`: how many times the deck has run out, and how many end the game
- `removed`: cards turned into coins
- `deck_counts`
- `active`, `phase`, `turn`, `trade_round`, `rules`

**Helpers:**
- `payout(bean, n)`, `field_payout(i)`, `next_coin(i)`, `is_maxed(i)`
- `field_index(bean)`, `empty_field()`, `fits(bean)`, `fits_all(beans)`
- `can_harvest(i)`, `harvestable()`, `legal_fields(bean)`, `remaining_unseen(bean)`

**Illegal moves:** if a bot returns something illegal, or raises an exception, the engine substitutes the default decision and counts a **violation**. The violation count appears in the report. To make illegal moves raise an error instead (useful while debugging), use `Game(..., strict=True)`.

## The strategist (the default strategy)

Every bot inherits a sensible strategy from `Bot`. The `strategist` bot plays it unchanged, so you can measure your ideas against it. It judges every decision in coins:

| Decision | Strategist rule |
|---|---|
| **Field value** | The larger of what the field pays if sold now and `RISK_DISCOUNT` × where it can still grow. Growth is estimated from copies still out there (unseen, plus discards if the pile gets reshuffled again) × `FUTURE_SHARE` × the share of the game left. |
| **Rare vs common beans** | Comes straight from the field-value estimate. Once few copies of a rare bean remain, its fields stop gaining value. Common beans keep growing. |
| **Planting** | Extends a matching field, otherwise starts a new one. A second hand card is planted only if it extends a field, fills an empty one, or replaces a field worth selling anyway. Killing a field that pays nothing costs an extra `CHURN_PENALTY` (1 coin), and 1-card fields count only `NEW_FIELD_GROWTH` (half) of their growth, so it stops churning its fields. Every card that extends one of its fields is worth an extra `GROW_BONUS` (0.75 coin), so it trades hard for its own beans. `RISK_DISCOUNT` is 1.0: a field's expected growth counts in full. |
| **Selling fields** | Sells a field once it pays and can't realistically grow any more. When forced, it sells the field that loses the least future value. |
| **Third field** | Buys it for 3 coins while less than `THIRD_FIELD_MAX_PROGRESS` (60%) of the game has gone. |
| **Trading** | Accepts a trade only if it gains more than `MIN_TRADE_GAIN` after subtracting what it pays and the partner's gain × `HELP_WEIGHT` (`LEADER_HELP_WEIGHT` if the partner leads). It offers away junk flips and front cards worth less than `JUNK_HAND_THRESHOLD`: first for a bean it grows, then for a 1-card 1-turn pick, then as gifts. |
| **Draft picks** | A pick's value is the flips it expects to want, discounted by `PICK_TURN_DISCOUNT` per turn of waiting. Its cost is the flips it would lose, plus the help the pick gives the holder. **Whenever it wants a bean but has no junk card to pay with, it always offers an EV-priced pick.** That is the cheapest pick in `PICK_MENU` (1–2 cards × 1–3 turns) that costs the strategist less than the bean is worth; the other player decides whether it's enough. |

### Tuning settings

Change any of these with a class attribute; there's no need to rewrite methods:

```python
class Bold(Bot):
    HELP_WEIGHT = 0.0                # doesn't care if trades help opponents
    THIRD_FIELD_MAX_PROGRESS = 1.0   # always buys the 3rd field
    RISK_DISCOUNT = 0.8              # less patient with growing fields
    CHURN_PENALTY = 0.0              # doesn't mind killing young fields
```

The building blocks are `field_value`, `card_value`, `cards_value`, `hand_value`, `pick_value`, `pick_cost`, `deal_score` and `help_weight`. You can override any of them, or call them from your own logic.

## Third bean field (classic rule)

This rule is on by default. Turn it off with `--no-third-field`.

- **The rule:** in games where players start with 2 fields, a player can buy a third for 3 coins.
- **When bots are asked:** at the start of every phase, and just before a forced harvest.
- **The hook:** `buy_third_field(view) -> bool`. `view.third_field_cost` is the price, or `None` if you can't buy one.
- **What happens to the coins:** the 3 coin cards go back into circulation on the discard pile.

## Draft picks (house rule)

Draft picks are on by default. Turn them off with `--no-draft-picks`.

- **What a pick is:** `Pick(cards, turns)` is a promise by the player who gives it. On each of the giver's next `turns` turns, right after the 2 cards are flipped and before any trading, the holder takes up to `cards` (1 or 2) of them for free.
- **Planting:** cards taken with a pick go beside the holder's fields and must be planted in phase 3, the same as traded cards.
- **How picks change hands:** picks are traded like cards during phase 2.
  - **Active player:** `Offer(give_picks=..., want_picks=...)` gives picks to, or asks for picks from, another player.
  - **Other players:** `Request(give_picks=..., want_picks=...)` does the same towards the active player.
  - **Gifts:** a pick can be given on its own, with nothing asked in return.
- **Limits:**
  - **2-card cap:** a player can never owe more than 2 cards across all their outstanding picks. Use `view.pick_capacity()` to check what's left.
  - **Length:** a pick lasts at most 10 turns.
  - **No passing on:** a holder can't trade a pick to someone else.
  - **Game end:** picks not yet used when the game ends are worthless.
- **Order:** when several picks fall on the same turn, they're used in the order they were given.
- **Seeing picks:** `view.draft_picks` lists every outstanding pick. `view.picks_held` and `view.picks_owed` filter it to yours.
- **Default bot:** it offers EV-priced picks for beans it wants, sells junk cards for picks, and accepts picks worth more than they cost. When using a pick, it takes only flipped cards that fit its fields.
- **Starter bots that lean on picks:** `draft_dealer` and `big_spender`, both in `bots/draft_dealer.py`. `draft_dealer` pays with small picks (1 card, 1–2 turns) before hand cards. `big_spender` offers the biggest pick that still costs it less than it gains.

## Rules notes and simplifications

- **Harvest timing:** you can harvest "at any time" in the real game. Here, bots get the chance at the start of every phase, and a harvest also happens whenever planting forces one.
- **Trading:** trading runs in up to 20 rounds per turn, and the active player completes at most one deal per round.
  - **Order within a round:** the active player makes offers, other players respond, other players make requests, and then the active player picks one deal.
  - **Re-trading:** cards received in a trade go beside the fields, never into the hand, so they can't be traded again.
  - **Paying for a request:** by default the active player pays with flipped cards first, then cards from the front of the hand. `choose_trade` can choose different cards with `deal.with_active_cards(...)`.
- **Turn order:** seat 0 always starts. The win-rate-by-seat chart shows the effect of turn order.
- **Wax Bean beanometer:** 4/7/9/11. The supplied rulebook PDF prints 4/8/11/13; edit `bohnanza/cards.py` to switch.
- **Not implemented:** the 2-player Bean Duel.

## Tests

```bash
python -m pytest -q
```
