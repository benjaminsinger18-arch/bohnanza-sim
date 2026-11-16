# Bohnanza Bot Lab

Simulates thousands of Bohnanza games between bots you write, then reports which strategies win.

- **Rules:** the base game for 3–5 players (`--rules base`) and the 3–7 player variant with Cocoa, Wax and Coffee beans (`--rules variant`). Rules come from the Rio Grande rulebook.
- **Rule enforcement:** hand order, the bean protection rule, the trade restrictions, deck run-outs and the tiebreak are all enforced.
- **Bots:** each bot is a Python class in `bots/`.
- **Output:** a terminal leaderboard plus an HTML dashboard.

## Quick start

```bash
python -m bohnanza list                                   # bots it found
python -m bohnanza run --bots hoarder,quick_cash,stingy,random --games 5000 --report --open
python -m bohnanza run --bots hoarder,quick_cash,specialist,generous_trader,stingy,random \
       --rules variant --players 3-7 --games 5000 --report
python -m bohnanza report --all                           # combine every run so far
python -m bohnanza replay --seed 7 --bots hoarder,quick_cash,stingy,random   # one game, turn by turn
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

## Rules notes and simplifications

- **Harvest timing:** you can harvest "at any time" in the real game. Here, bots get the chance at the start of every phase, and a harvest also happens whenever planting forces one.
- **Trading:** trading runs in up to 10 rounds per turn, and the active player completes at most one deal per round.
  - **Order within a round:** the active player makes offers, other players respond, other players make requests, and then the active player picks one deal.
  - **Re-trading:** cards received in a trade go beside the fields, never into the hand, so they can't be traded again.
  - **Paying for a request:** by default the active player pays with flipped cards first, then cards from the front of the hand. `choose_trade` can choose different cards with `deal.with_active_cards(...)`.
- **Turn order:** seat 0 always starts. The win-rate-by-seat chart shows the effect of turn order.
- **Wax Bean beanometer:** the values (4/8/11/13) are as printed in the supplied rulebook PDF. Some printings use 4/7/9/11, so edit `bohnanza/cards.py` if your cards differ.
- **Not implemented:** the 2-player Bean Duel.

## Tests

```bash
python -m pytest -q
```
