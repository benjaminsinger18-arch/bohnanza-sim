"""CLI: python -m bohnanza {list,run,report,replay}"""
import argparse
import sys
import webbrowser
from pathlib import Path

from .registry import discover
from .report import build_report
from .stats import compute, format_table, load_rows, load_runs
from .tournament import RESULTS_DIR, play_one, run_tournament


def _keys(s: str) -> list[str]:
    return [k.strip() for k in s.split(",") if k.strip()]


def cmd_list(a):
    bots = discover(a.bots_dir)
    w = max(map(len, bots), default=4)
    for k, c in sorted(bots.items()):
        print(f"  {k:<{w}}  {c.description or c.__doc__ or ''}")


def _report(a, run: str):
    rows = load_rows(a.results_dir, run)
    if not rows:
        sys.exit("no results found - run a tournament first")
    st = compute(rows, load_runs(a.results_dir))
    classes = discover(a.bots_dir)
    st["bot_info"] = {k: {"description": classes[k].description if k in classes else "",
                          "details": classes[k].details if k in classes else "(bot file no longer in bots/)"}
                      for k in st["order"]}
    print(format_table(st))
    sub = f"{'all runs' if run == 'all' else 'run ' + rows[0].get('run', '?')} · {st['games']:,} games"
    out = build_report(st, Path(a.results_dir) / "report.html", subtitle=sub)
    print(f"\nreport: {out}")
    if getattr(a, "open", False):
        webbrowser.open(out.resolve().as_uri())


def cmd_run(a):
    keys = _keys(a.bots)
    run_id, _ = run_tournament(keys, a.games, seed=a.seed, rules=a.rules, players=a.players,
                               workers=a.workers, bots_dir=a.bots_dir, results_dir=Path(a.results_dir),
                               draft_picks=not a.no_draft_picks)
    print(f"run {run_id}\n")
    if a.report:
        _report(a, run_id)
    else:
        print(format_table(compute(load_rows(a.results_dir, run_id))))


def cmd_report(a):
    _report(a, "all" if a.all else (a.run or "latest"))


def cmd_replay(a):
    res, g = play_one(_keys(a.bots), a.seed, a.rules, a.bots_dir, verbose=True, draft_picks=not a.no_draft_picks)
    print("\n".join(g.log_lines))
    print()
    for p in sorted(res["players"], key=lambda p: p["rank"]):
        print(f"  #{p['rank']} {p['bot']:<16} seat {p['seat'] + 1}  {p['coins']} coins")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="bohnanza", description="Bohnanza bot simulator")
    ap.add_argument("--bots-dir", default=None, help="folder with bot files (default: ./bots)")
    ap.add_argument("--results-dir", default=str(RESULTS_DIR))
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="show available bots").set_defaults(fn=cmd_list)

    r = sub.add_parser("run", help="run a tournament")
    r.add_argument("--bots", required=True, help="comma-separated bot keys")
    r.add_argument("--games", type=int, default=1000)
    r.add_argument("--seed", type=int, default=1)
    r.add_argument("--rules", choices=["base", "variant"], default="base",
                   help="base = 3-5 players; variant = 3-7 players with Cocoa/Wax/Coffee")
    r.add_argument("--players", default=None, help="table size: 4, 3-5, or 3,5 (default: number of bots)")
    r.add_argument("--workers", type=int, default=None)
    r.add_argument("--no-draft-picks", action="store_true", help="disable the draft-pick house rule")
    r.add_argument("--report", action="store_true", help="build the HTML report afterwards")
    r.add_argument("--open", action="store_true", help="open the report in a browser")
    r.set_defaults(fn=cmd_run)

    p = sub.add_parser("report", help="build the HTML report")
    p.add_argument("--run", default=None, help="run id (default: latest)")
    p.add_argument("--all", action="store_true", help="aggregate every run so far")
    p.add_argument("--open", action="store_true")
    p.set_defaults(fn=cmd_report)

    q = sub.add_parser("replay", help="print one game turn by turn")
    q.add_argument("--bots", required=True)
    q.add_argument("--seed", type=int, default=1)
    q.add_argument("--rules", choices=["base", "variant"], default="base")
    q.add_argument("--no-draft-picks", action="store_true")
    q.set_defaults(fn=cmd_replay)

    a = ap.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
