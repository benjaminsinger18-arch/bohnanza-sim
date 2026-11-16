"""Run many games in parallel and append results to results/games.jsonl."""
import json
import os
import random
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from itertools import permutations
from pathlib import Path

from .engine import Game
from .registry import discover, make_bot
from .rules import make_rules

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"


def parse_players(spec, num_bots: int) -> list[int]:
    """'4' -> [4]; '3-5' -> [3, 4, 5]; None -> [num_bots]."""
    if spec is None:
        return [num_bots]
    spec = str(spec)
    if "-" in spec:
        lo, hi = (int(x) for x in spec.split("-"))
        return list(range(lo, hi + 1))
    return [int(x) for x in spec.split(",")]


def lineups(keys: list[str], sizes: list[int], games: int, seed: int):
    """Yield (game_index, lineup, game_seed). Full seat rotation when #bots == table size."""
    rng = random.Random(seed)
    perm_cache: dict[int, list] = {}
    for i in range(games):
        size = sizes[i % len(sizes)]
        if len(keys) == size:
            if size not in perm_cache:
                perms = list(permutations(keys))
                rng.shuffle(perms)
                perm_cache[size] = perms
            perms = perm_cache[size]
            lineup = list(perms[i // len(sizes) % len(perms)])
        elif len(keys) > size:
            lineup = rng.sample(keys, size)
        else:  # fewer bots than seats: repeat bots
            pool = (keys * (size // len(keys) + 1))
            rng.shuffle(pool)
            lineup = pool[:size]
        yield i, lineup, seed * 1_000_003 + i


def play_one(lineup: list[str], game_seed: int, rules: str, bots_dir=None, verbose=False):
    bots = [make_bot(k, bots_dir) for k in lineup]
    g = Game(bots, seed=game_seed, rules=rules, verbose=verbose)
    return g.play(), g


def _run_chunk(args):
    items, rules, bots_dir = args
    out = []
    for i, lineup, gs in items:
        res, _ = play_one(lineup, gs, rules, bots_dir)
        res["game"] = i
        out.append(res)
    return out


def run_tournament(keys: list[str], games: int, seed: int = 1, rules: str = "base",
                   players=None, workers: int | None = None, bots_dir=None,
                   results_dir: Path = RESULTS_DIR, progress: bool = True) -> tuple[str, list[dict]]:
    available = discover(bots_dir)
    for k in keys:
        if k not in available:
            raise SystemExit(f"unknown bot {k!r}. Available: {', '.join(sorted(available))}")
    sizes = parse_players(players, len(keys))
    for s in sizes:
        make_rules(rules, s)  # validates player count for this rule set
    items = list(lineups(keys, sizes, games, seed))
    run_id = time.strftime("%Y%m%d-%H%M%S") + f"-s{seed}"
    workers = workers or max(1, (os.cpu_count() or 2) - 1)
    chunk = max(20, games // (workers * 8) or 1)
    chunks = [(items[j:j + chunk], rules, bots_dir) for j in range(0, len(items), chunk)]

    t0 = time.time()
    rows: list[dict] = []
    if workers == 1 or len(chunks) == 1:
        for c in chunks:
            rows.extend(_run_chunk(c))
    else:
        with ProcessPoolExecutor(max_workers=workers) as ex:
            futs = [ex.submit(_run_chunk, c) for c in chunks]
            for f in as_completed(futs):
                rows.extend(f.result())
                if progress:
                    print(f"\r  {len(rows)}/{games} games", end="", flush=True)
    if progress:
        print(f"\r  {games} games in {time.time() - t0:.1f}s" + " " * 10)
    rows.sort(key=lambda r: r["game"])
    meta = {"run": run_id, "time": time.strftime("%Y-%m-%d %H:%M:%S"), "bots": keys,
            "games": games, "seed": seed, "rules": rules, "players": sizes}
    for r in rows:
        r["run"] = run_id

    results_dir.mkdir(parents=True, exist_ok=True)
    with open(results_dir / "games.jsonl", "a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, separators=(",", ":")) + "\n")
    with open(results_dir / "runs.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(meta) + "\n")
    return run_id, rows
