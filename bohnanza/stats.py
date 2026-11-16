"""Aggregate game rows into per-bot statistics."""
import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import mean, median, pstdev

from .engine import STAT_KEYS


def load_runs(results_dir: Path) -> list[dict]:
    p = Path(results_dir) / "runs.jsonl"
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_rows(results_dir: Path, run: str | None = "latest") -> list[dict]:
    """run: a run id, 'latest' (default) or 'all'."""
    p = Path(results_dir) / "games.jsonl"
    if not p.exists():
        return []
    rows = [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]
    if run == "all":
        return rows
    if run in (None, "latest"):
        runs = load_runs(results_dir)
        if not runs:
            return rows
        run = runs[-1]["run"]
    return [r for r in rows if r.get("run") == run]


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def compute(rows: list[dict], runs_meta: list[dict] | None = None) -> dict:
    per = defaultdict(lambda: {"coins": [], "wins": 0, "ranks": [], "expected": 0.0,
                               **{k: 0 for k in STAT_KEYS}, "hand_left": 0})
    h2h_w = defaultdict(lambda: defaultdict(int))
    h2h_n = defaultdict(lambda: defaultdict(int))
    seat_w = defaultdict(lambda: defaultdict(int))
    seat_n = defaultdict(lambda: defaultdict(int))
    conv_points: dict[str, list] = defaultdict(list)
    run_w = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    sizes, rules = set(), set()

    total = len(rows)
    step = max(1, total // 150)
    for gi, r in enumerate(rows):
        sizes.add(r["n"])
        rules.add(r.get("rules", "base"))
        ps = r["players"]
        for p in ps:
            s = per[p["bot"]]
            s["coins"].append(p["coins"])
            s["wins"] += p["win"]
            s["ranks"].append(p["rank"])
            s["expected"] += 1 / r["n"]
            for k in STAT_KEYS:
                s[k] += p.get(k, 0)
            s["hand_left"] += p.get("hand_left", 0)
            seat_w[p["bot"]][p["seat"]] += p["win"]
            seat_n[p["bot"]][p["seat"]] += 1
            rw = run_w[r.get("run", "?")][p["bot"]]
            rw[0] += p["win"]
            rw[1] += 1
        for a in ps:
            for b in ps:
                if a is not b and a["bot"] != b["bot"]:
                    h2h_n[a["bot"]][b["bot"]] += 1
                    h2h_w[a["bot"]][b["bot"]] += a["rank"] < b["rank"]
        if gi % step == 0 or gi == total - 1:
            for bot, s in per.items():
                conv_points[bot].append((gi + 1, s["wins"] / len(s["coins"])))

    bots = {}
    for bot, s in per.items():
        n = len(s["coins"])
        lo, hi = wilson(s["wins"], n)
        h = s["harvests"]
        bots[bot] = {
            "bot": bot, "games": n, "wins": s["wins"], "win_rate": s["wins"] / n,
            "ci_lo": lo, "ci_hi": hi, "expected": s["expected"] / n,
            "lift": (s["wins"] / n) / (s["expected"] / n) if s["expected"] else 0,
            "mean_coins": mean(s["coins"]), "median_coins": median(s["coins"]),
            "sd_coins": pstdev(s["coins"]), "avg_rank": mean(s["ranks"]),
            "trades_pg": s["trades"] / n, "gifts_pg": s["gifts_given"] / n,
            "cards_given_pg": s["cards_given"] / n, "cards_received_pg": s["cards_received"] / n,
            "harvests_pg": h / n, "avg_harvest_size": s["harvest_cards"] / h if h else 0,
            "coins_per_harvest": s["harvest_coins"] / h if h else 0,
            "forced_pg": s["forced_harvests"] / n, "violations": s["violations"],
            "hand_left_pg": s["hand_left"] / n,
            "coins_hist": _hist(s["coins"]),
        }
    order = sorted(bots, key=lambda b: (-bots[b]["win_rate"], -bots[b]["mean_coins"]))
    h2h = {a: {b: (h2h_w[a][b] / h2h_n[a][b] if h2h_n[a][b] else None) for b in order} for a in order}
    max_seat = max(sizes) if sizes else 0
    by_seat = {b: [(seat_w[b][i] / seat_n[b][i]) if seat_n[b][i] else None for i in range(max_seat)]
               for b in order}
    meta_by_run = {m["run"]: m for m in (runs_meta or [])}
    history = []
    for run_id, d in run_w.items():
        m = meta_by_run.get(run_id, {})
        history.append({"run": run_id, "time": m.get("time", run_id), "games": m.get("games"),
                        "win_rate": {b: w / n for b, (w, n) in d.items()}})
    history.sort(key=lambda h: h["time"])
    return {"games": total, "sizes": sorted(sizes), "rules": sorted(rules), "order": order,
            "bots": bots, "h2h": h2h, "by_seat": by_seat, "convergence": dict(conv_points),
            "history": history}


def _hist(values: list[int]) -> dict:
    out: dict[int, int] = defaultdict(int)
    for v in values:
        out[v] += 1
    return dict(sorted(out.items()))


def format_table(st: dict) -> str:
    hdr = f"{'bot':<18}{'games':>7}{'win%':>8}{'95% CI':>15}{'vs fair':>9}{'coins':>8}{'rank':>6}" \
          f"{'trades':>8}{'harv sz':>9}{'forced':>8}{'viol':>6}"
    lines = [hdr, "-" * len(hdr)]
    for b in st["order"]:
        s = st["bots"][b]
        ci = f"{s['ci_lo'] * 100:.1f}-{s['ci_hi'] * 100:.1f}"
        lines.append(f"{b:<18}{s['games']:>7}{s['win_rate']*100:>7.1f}%{ci:>15}"
                     f"{s['lift']:>8.2f}x{s['mean_coins']:>8.2f}{s['avg_rank']:>6.2f}"
                     f"{s['trades_pg']:>8.1f}{s['avg_harvest_size']:>9.2f}{s['forced_pg']:>8.1f}{s['violations']:>6}")
    lines.append(f"\n{st['games']} games  |  rules: {', '.join(st['rules'])}  |  table sizes: "
                 f"{', '.join(map(str, st['sizes']))}  |  'vs fair' = win rate / (1 / players)")
    return "\n".join(lines)
