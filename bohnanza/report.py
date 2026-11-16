"""Build a self-contained HTML dashboard from computed stats."""
import html
import json
from pathlib import Path

CHART_JS = "https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"


def build_report(st: dict, out: Path, title: str = "Bohnanza Bot Lab", subtitle: str = "") -> Path:
    data = json.dumps(st, separators=(",", ":"))
    page = (TEMPLATE.replace("__TITLE__", html.escape(title))
            .replace("__SUBTITLE__", html.escape(subtitle))
            .replace("__CHARTJS__", CHART_JS)
            .replace("__DATA__", data.replace("</", "<\\/")))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    return out


TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<script src="__CHARTJS__"></script>
<style>
:root {
  color-scheme: light;
  --page: #f9f9f7; --surface: #fcfcfb; --ink: #0b0b0b; --ink-2: #52514e; --muted: #898781;
  --grid: #e1e0d9; --axis: #c3c2b7; --border: rgba(11,11,11,0.10);
  --s1:#2a78d6; --s2:#eb6834; --s3:#1baf7a; --s4:#eda100; --s5:#e87ba4; --s6:#008300; --s7:#6250d6; --s8:#e34948;
  --pos: #2a78d6; --neg: #e34948; --mid: #f0efec; --good: #006300;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --page: #0d0d0d; --surface: #1a1a19; --ink: #f0efec; --ink-2: #c3c2b7; --muted: #898781;
    --grid: #2c2c2a; --axis: #383835; --border: rgba(255,255,255,0.10);
    --s1:#3987e5; --s2:#d95926; --s3:#199e70; --s4:#c98500; --s5:#d55181; --s6:#008300; --s7:#9085e9; --s8:#e66767;
    --pos: #3987e5; --neg: #e66767; --mid: #383835; --good: #0ca30c;
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --page: #0d0d0d; --surface: #1a1a19; --ink: #f0efec; --ink-2: #c3c2b7; --muted: #898781;
  --grid: #2c2c2a; --axis: #383835; --border: rgba(255,255,255,0.10);
  --s1:#3987e5; --s2:#d95926; --s3:#199e70; --s4:#c98500; --s5:#d55181; --s6:#008300; --s7:#9085e9; --s8:#e66767;
  --pos: #3987e5; --neg: #e66767; --mid: #383835; --good: #0ca30c;
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--page); color: var(--ink);
  font: 14px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }
main { max-width: 1180px; margin: 0 auto; padding: 28px 16px 64px; }
header { display: flex; justify-content: space-between; align-items: flex-end; gap: 16px; flex-wrap: wrap; margin-bottom: 20px; }
h1 { font-size: 24px; margin: 0; letter-spacing: -0.01em; }
.sub { color: var(--ink-2); margin-top: 4px; }
h2 { font-size: 15px; margin: 0 0 2px; }
.note { color: var(--muted); font-size: 12.5px; margin: 0 0 12px; }
.grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }
.card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 18px; min-width: 0; }
.wide { grid-column: 1 / -1; }
.tiles { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 16px; margin-bottom: 16px; }
.tile .k { color: var(--ink-2); font-size: 12.5px; }
.tile .v { font-size: 26px; font-weight: 600; margin-top: 2px; }
.tile .d { color: var(--muted); font-size: 12.5px; }
.chart { position: relative; height: 300px; }
.tablewrap { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; font-variant-numeric: tabular-nums; }
th, td { padding: 7px 10px; text-align: right; white-space: nowrap; border-bottom: 1px solid var(--grid); }
th { color: var(--ink-2); font-weight: 600; font-size: 12.5px; }
th:first-child, td:first-child { text-align: left; }
.sw { display: inline-block; width: 10px; height: 10px; border-radius: 3px; margin-right: 8px; vertical-align: -1px; }
.bar { display: inline-block; height: 6px; border-radius: 3px; background: var(--s1); vertical-align: middle; margin-left: 8px; }
.h2h td.cell { text-align: center; min-width: 64px; font-weight: 600; }
.h2h td.self { color: var(--muted); text-align: center; }
.legend { display: flex; gap: 14px; flex-wrap: wrap; margin: 0 0 10px; font-size: 12.5px; color: var(--ink-2); }
button.theme { background: var(--surface); color: var(--ink); border: 1px solid var(--border); border-radius: 8px; padding: 6px 12px; cursor: pointer; font: inherit; }
.empty { color: var(--muted); padding: 30px 0; text-align: center; }
.defaults { background: var(--page); border: 1px solid var(--border); border-radius: 10px; padding: 12px 16px; margin-bottom: 14px; color: var(--ink-2); }
.defaults b { color: var(--ink); }
.defaults ul, .insights { margin: 6px 0 0; padding-left: 20px; }
.defaults li, .insights li { margin: 4px 0; }
.insights b { color: var(--ink); }
#meet td.what { text-align: left; white-space: normal; min-width: 320px; color: var(--ink-2); }
@media (max-width: 760px) {
  .grid { grid-template-columns: 1fr; }
  .tiles { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
</style>
</head>
<body>
<main>
<header>
  <div><h1>__TITLE__</h1><div class="sub">__SUBTITLE__</div></div>
  <button class="theme" id="themeBtn" type="button">Toggle theme</button>
</header>

<section class="tiles" id="tiles"></section>

<section class="grid">
  <div class="card wide">
    <h2>Leaderboard</h2>
    <p class="note">Win rate with 95% confidence interval. “vs fair” = win rate ÷ fair share (1 ÷ players). Above 1.00× beats an average seat.</p>
    <div class="tablewrap"><table id="leader"></table></div>
  </div>

  <div class="card wide">
    <h2>Meet the bots</h2>
    <p class="note">Every bot starts from the same default playstyle and changes only a few decisions.</p>
    <div class="defaults">
      <b>The shared default:</b>
      <ul>
        <li><b>Planting:</b> the front card goes into a field already growing that bean, otherwise an empty field. A second card is planted only if it fits without forcing a harvest.</li>
        <li><b>Forced harvest:</b> when a bean has nowhere to go, it harvests the field that pays the most right now.</li>
        <li><b>Voluntary harvest:</b> only once a field can't earn any more coins.</li>
        <li><b>Trading:</b> offers unusable flipped cards for a bean it grows, then gives them away. Accepts cards that fit if it can pay with beans it doesn't grow, and asks for flipped cards matching its fields.</li>
        <li><b>Draft picks:</b> never promises one, but accepts picks it is offered. When using a pick, it takes the flipped cards that fit its fields and passes on the rest.</li>
      </ul>
    </div>
    <div class="tablewrap"><table id="meet"></table></div>
    <h2 style="margin-top:18px">What stands out in this run</h2>
    <p class="note">Generated from this run's numbers.</p>
    <ul class="insights" id="insights"></ul>
  </div>

  <div class="card">
    <h2>Win rate</h2>
    <p class="note">Bars = win rate, whiskers = 95% CI, line = fair share.</p>
    <div class="chart"><canvas id="cWin"></canvas></div>
  </div>

  <div class="card">
    <h2>Coins per game</h2>
    <p class="note">Share of games ending with each coin total.</p>
    <div class="legend" id="lgHist"></div>
    <div class="chart"><canvas id="cHist"></canvas></div>
  </div>

  <div class="card wide">
    <h2>Head-to-head</h2>
    <p class="note">How often the row bot finished above the column bot when they shared a table. Blue = row wins more, red = loses more.</p>
    <div class="tablewrap"><table class="h2h" id="h2h"></table></div>
  </div>

  <div class="card">
    <h2>Win rate by seat</h2>
    <p class="note">Seat 1 starts the game. Ties go to the player furthest from the starter.</p>
    <div class="legend" id="lgSeat"></div>
    <div class="chart"><canvas id="cSeat"></canvas></div>
  </div>

  <div class="card">
    <h2>Convergence</h2>
    <p class="note">Running win rate as games accumulate. Flat lines mean the result is stable.</p>
    <div class="legend" id="lgConv"></div>
    <div class="chart"><canvas id="cConv"></canvas></div>
  </div>

  <div class="card wide" id="histCard">
    <h2>Across runs</h2>
    <p class="note">Win rate in each tournament run over time (only with <code>report --all</code> and more than one run).</p>
    <div class="legend" id="lgRuns"></div>
    <div class="chart"><canvas id="cRuns"></canvas></div>
  </div>

  <div class="card wide">
    <h2>Playstyle fingerprint</h2>
    <p class="note">Per-game averages. Forced = harvests made because a bean had nowhere to go. Violations = illegal moves the engine corrected (should be 0).</p>
    <div class="tablewrap"><table id="behav"></table></div>
  </div>
</section>
</main>

<script>
const ST = __DATA__;
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const pct = v => v == null ? "–" : (v * 100).toFixed(1) + "%";
const order = ST.order;
// colour follows the bot (alphabetical), never its rank
const alpha = [...order].sort();
const color = b => { const i = alpha.indexOf(b); return i < 8 ? css("--s" + (i + 1)) : css("--muted"); };
const charts = [];

function legend(id, bots) {
  document.getElementById(id).innerHTML = bots.map(b =>
    `<span><span class="sw" style="background:${color(b)}"></span>${b}</span>`).join("");
}

function tiles() {
  const top = ST.bots[order[0]];
  const best = order.reduce((a, b) => ST.bots[b].mean_coins > ST.bots[a].mean_coins ? b : a, order[0]);
  const viol = order.reduce((s, b) => s + ST.bots[b].violations, 0);
  document.getElementById("tiles").innerHTML = [
    ["Games simulated", ST.games.toLocaleString(), `${ST.rules.join(", ")} rules · ${ST.sizes.join("/")} players`],
    ["Top win rate", order[0] || "–", top ? `${pct(top.win_rate)} · ${top.lift.toFixed(2)}× fair share` : ""],
    ["Most coins / game", best || "–", best ? ST.bots[best].mean_coins.toFixed(2) + " coins average" : ""],
    ["Rule violations", viol.toLocaleString(), viol ? "a bot is returning illegal moves" : "all bots played legally"],
  ].map(([k, v, d]) => `<div class="card tile"><div class="k">${k}</div><div class="v">${v}</div><div class="d">${d}</div></div>`).join("");
}

function leader() {
  const max = Math.max(...order.map(b => ST.bots[b].win_rate), 0.01);
  let h = `<tr><th>#</th><th style="text-align:left">Bot</th><th>Games</th><th>Win rate</th><th>95% CI</th><th>vs fair</th><th>Avg coins</th><th>Median</th><th>Avg rank</th></tr>`;
  order.forEach((b, i) => {
    const s = ST.bots[b];
    h += `<tr><td>${i + 1}</td><td style="text-align:left"><span class="sw" style="background:${color(b)}"></span>${b}</td>
      <td>${s.games.toLocaleString()}</td>
      <td>${pct(s.win_rate)}<span class="bar" style="width:${Math.round(60 * s.win_rate / max)}px"></span></td>
      <td>${pct(s.ci_lo)} – ${pct(s.ci_hi)}</td>
      <td style="color:${s.lift >= 1 ? css("--good") : "inherit"}">${s.lift.toFixed(2)}×</td>
      <td>${s.mean_coins.toFixed(2)}</td><td>${s.median_coins}</td><td>${s.avg_rank.toFixed(2)}</td></tr>`;
  });
  document.getElementById("leader").innerHTML = h;
}

const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

function meet() {
  const info = ST.bot_info || {};
  let h = `<tr><th style="text-align:left">Bot</th><th style="text-align:left">What it does differently</th><th>Win rate</th><th>Avg coins</th></tr>`;
  order.forEach(b => {
    const i = info[b] || {}, s = ST.bots[b];
    const what = i.details || i.description || "(no description - add `details` to the bot class)";
    h += `<tr><td><span class="sw" style="background:${color(b)}"></span><b>${esc(b)}</b></td>
      <td class="what">${esc(what)}</td><td>${pct(s.win_rate)}</td><td>${s.mean_coins.toFixed(1)}</td></tr>`;
  });
  document.getElementById("meet").innerHTML = h;

  const B = ST.bots, out = [];
  if (order.length >= 2) {
    const [k1, k2] = order, a = B[k1], b = B[k2];
    out.push(`<b>${esc(k1)}</b> wins most (${pct(a.win_rate)}, ${a.lift.toFixed(2)}× fair share)` +
      (a.ci_lo <= b.ci_hi
        ? `, but its lead over <b>${esc(k2)}</b> (${pct(b.win_rate)}) is within the margin of error. Run more games to separate them.`
        : `, clearly ahead of <b>${esc(k2)}</b> (${pct(b.win_rate)}).`));
    const med = arr => { const s = [...arr].sort((x, y) => x - y), m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };
    const real = order.filter(k => k !== "random");  // the random baseline would always "win" this one
    const fm = real.length ? med(real.map(k => B[k].forced_pg)) : 0;
    const mostF = real.length ? real.reduce((x, y) => B[y].forced_pg > B[x].forced_pg ? y : x) : null;
    if (mostF && fm > 0 && B[mostF].forced_pg >= 1.5 * fm)
      out.push(`<b>${esc(mostF)}</b> is forced to harvest most often: ${B[mostF].forced_pg.toFixed(1)} times a game against a median of ${fm.toFixed(1)}. Forced harvests usually break up fields before they pay.`);
    order.filter(k => B[k].trades_pg === 0).forEach(k =>
      out.push(`<b>${esc(k)}</b> never trades and wins ${pct(B[k].win_rate)} of games (${B[k].lift.toFixed(2)}× fair share).`));
    const big = order.reduce((x, y) => B[y].avg_harvest_size > B[x].avg_harvest_size ? y : x);
    out.push(`<b>${esc(big)}</b> harvests the biggest fields (${B[big].avg_harvest_size.toFixed(2)} cards on average) and ` +
      (B[big].lift >= 1 ? `beats a fair share (${B[big].lift.toFixed(2)}×).` : `still falls short of a fair share (${B[big].lift.toFixed(2)}×), so clean fields alone don't win.`));
    const gift = order.reduce((x, y) => B[y].gifts_pg > B[x].gifts_pg ? y : x);
    if (B[gift].gifts_pg >= 1)
      out.push(`<b>${esc(gift)}</b> gives away the most cards for free (${B[gift].gifts_pg.toFixed(1)} gifts a game), and every gift helps an opponent.`);
    const pickers = order.filter(k => (B[k].picks_given_pg || 0) + (B[k].picks_received_pg || 0) > 0);
    if (pickers.length) {
      const giver = pickers.reduce((x, y) => B[y].picks_given_pg > B[x].picks_given_pg ? y : x);
      const drafter = pickers.reduce((x, y) => B[y].pick_cards_taken_pg > B[x].pick_cards_taken_pg ? y : x);
      out.push(`Draft picks: <b>${esc(giver)}</b> gives the most (${B[giver].picks_given_pg.toFixed(1)} a game, losing ${B[giver].pick_cards_lost_pg.toFixed(1)} flipped cards to them) and wins ${pct(B[giver].win_rate)}. ` +
        `<b>${esc(drafter)}</b> drafts the most cards (${B[drafter].pick_cards_taken_pg.toFixed(1)} a game).`);
    }
    const viol = order.filter(k => B[k].violations > 0);
    if (viol.length) out.push(`Rule violations from ${viol.map(esc).join(", ")}: the engine corrected them, but check those bots' code.`);
  }
  document.getElementById("insights").innerHTML = out.map(x => `<li>${x}</li>`).join("");
}

function behav() {
  const cols = [["trades_pg", "Trades", 1], ["gifts_pg", "Gifts given", 2], ["cards_given_pg", "Cards given", 1],
    ["cards_received_pg", "Cards received", 1], ["harvests_pg", "Harvests", 1], ["avg_harvest_size", "Cards / harvest", 2],
    ["coins_per_harvest", "Coins / harvest", 2], ["forced_pg", "Forced harvests", 1], ["hand_left_pg", "Cards left in hand", 1],
    ["picks_given_pg", "Picks given", 2], ["picks_received_pg", "Picks received", 2],
    ["pick_cards_taken_pg", "Cards drafted", 2], ["pick_cards_lost_pg", "Cards lost to picks", 2],
    ["violations", "Violations", 0]];
  let h = `<tr><th style="text-align:left">Bot</th>${cols.map(c => `<th>${c[1]}</th>`).join("")}</tr>`;
  order.forEach(b => {
    const s = ST.bots[b];
    h += `<tr><td><span class="sw" style="background:${color(b)}"></span>${b}</td>${cols.map(([k, , d]) => `<td>${(+s[k]).toFixed(d)}</td>`).join("")}</tr>`;
  });
  document.getElementById("behav").innerHTML = h;
}

function mix(a, b, t) {
  const p = h => [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16));
  const [x, y] = [p(a), p(b)];
  return "#" + x.map((v, i) => Math.round(v + (y[i] - v) * t).toString(16).padStart(2, "0")).join("");
}

function h2h() {
  let h = `<tr><th style="text-align:left">row beats column →</th>${order.map(b => `<th style="text-align:center">${b}</th>`).join("")}</tr>`;
  const mid = css("--mid"), pos = css("--pos"), neg = css("--neg");
  order.forEach(a => {
    h += `<tr><td><span class="sw" style="background:${color(a)}"></span>${a}</td>`;
    order.forEach(b => {
      const v = ST.h2h[a][b];
      if (a === b || v == null) { h += `<td class="self">–</td>`; return; }
      const t = Math.min(1, Math.abs(v - 0.5) / 0.3);
      const bg = mix(mid, v >= 0.5 ? pos : neg, t * 0.85);
      const ink = t > 0.55 ? "#ffffff" : css("--ink");
      h += `<td class="cell" style="background:${bg};color:${ink}" title="${a} finished above ${b} in ${pct(v)} of shared games">${pct(v)}</td>`;
    });
    h += "</tr>";
  });
  document.getElementById("h2h").innerHTML = h;
}

function baseOpts(yPct = true) {
  const ink2 = css("--ink-2"), grid = css("--grid"), axis = css("--axis"), muted = css("--muted");
  return {
    responsive: true, maintainAspectRatio: false, animation: false,
    interaction: { mode: "index", intersect: false },
    plugins: { legend: { display: false },
      tooltip: { backgroundColor: css("--surface"), titleColor: css("--ink"), bodyColor: ink2,
        borderColor: css("--border"), borderWidth: 1, padding: 10, boxPadding: 4, usePointStyle: true,
        callbacks: yPct ? { label: c => ` ${c.dataset.label}: ${pct(c.parsed.y)}` } : {} } },
    scales: {
      x: { grid: { display: false }, border: { color: axis }, ticks: { color: muted } },
      y: { grid: { color: grid }, border: { display: false }, ticks: { color: muted,
        callback: yPct ? v => Math.round(v * 100) + "%" : undefined }, beginAtZero: true },
    },
  };
}

const lineDs = (b, data) => ({ label: b, data, borderColor: color(b), backgroundColor: color(b),
  borderWidth: 2, pointRadius: 0, pointHoverRadius: 5, tension: 0.2, spanGaps: true });

function draw() {
  charts.splice(0).forEach(c => c.destroy());
  tiles(); leader(); meet(); behav(); h2h();
  if (!order.length) return;

  // --- win rate bars + CI whiskers + fair-share line
  const fair = order.map(b => ST.bots[b].expected);
  const whisker = { id: "whisker", afterDatasetsDraw(chart) {
    const { ctx, scales: { y } } = chart, meta = chart.getDatasetMeta(0);
    ctx.save(); ctx.strokeStyle = css("--ink-2"); ctx.lineWidth = 1.5;
    meta.data.forEach((bar, i) => {
      const s = ST.bots[order[i]], x = bar.x, y1 = y.getPixelForValue(s.ci_lo), y2 = y.getPixelForValue(s.ci_hi);
      ctx.beginPath(); ctx.moveTo(x, y1); ctx.lineTo(x, y2);
      ctx.moveTo(x - 5, y1); ctx.lineTo(x + 5, y1); ctx.moveTo(x - 5, y2); ctx.lineTo(x + 5, y2); ctx.stroke();
    });
    ctx.restore();
  } };
  const winOpts = baseOpts();
  winOpts.interaction = { mode: "index", intersect: false };
  winOpts.plugins.tooltip.callbacks = {
    label: c => c.datasetIndex === 0
      ? ` win rate ${pct(c.parsed.y)} (CI ${pct(ST.bots[order[c.dataIndex]].ci_lo)}–${pct(ST.bots[order[c.dataIndex]].ci_hi)})`
      : ` fair share ${pct(c.parsed.y)}` };
  charts.push(new Chart(document.getElementById("cWin"), {
    data: { labels: order, datasets: [
      { type: "bar", label: "Win rate", data: order.map(b => ST.bots[b].win_rate), backgroundColor: css("--s1"),
        borderRadius: { topLeft: 4, topRight: 4 }, borderSkipped: "bottom", maxBarThickness: 44 },
      { type: "line", label: "Fair share", data: fair, borderColor: css("--muted"), borderWidth: 1.5,
        pointRadius: 0, stepped: "middle" } ] },
    options: winOpts, plugins: [whisker] }));

  // --- coin distribution (share of games per coin total)
  let maxC = 0;
  order.forEach(b => Object.keys(ST.bots[b].coins_hist).forEach(k => maxC = Math.max(maxC, +k)));
  const xs = [...Array(maxC + 1).keys()];
  charts.push(new Chart(document.getElementById("cHist"), { type: "line",
    data: { labels: xs, datasets: order.map(b => {
      const h = ST.bots[b].coins_hist, n = ST.bots[b].games;
      return lineDs(b, xs.map(x => (h[x] || 0) / n)); }) },
    options: (() => { const o = baseOpts(); o.scales.x.title = { display: true, text: "coins", color: css("--muted") };
      o.plugins.tooltip.callbacks.title = i => `${i[0].label} coins`; return o; })() }));
  legend("lgHist", order);

  // --- by seat
  const seats = ST.sizes.length ? [...Array(Math.max(...ST.sizes)).keys()].map(i => "Seat " + (i + 1)) : [];
  charts.push(new Chart(document.getElementById("cSeat"), { type: "line",
    data: { labels: seats, datasets: order.map(b => ({ ...lineDs(b, ST.by_seat[b]), pointRadius: 4, tension: 0 })) },
    options: baseOpts() }));
  legend("lgSeat", order);

  // --- convergence
  charts.push(new Chart(document.getElementById("cConv"), { type: "line",
    data: { datasets: order.map(b => lineDs(b, (ST.convergence[b] || []).map(([x, y]) => ({ x, y })))) },
    options: (() => { const o = baseOpts(); o.scales.x.type = "linear";
      o.scales.x.title = { display: true, text: "games played", color: css("--muted") };
      o.plugins.tooltip.callbacks.title = i => `after ${i[0].parsed.x.toLocaleString()} games`; return o; })() }));
  legend("lgConv", order);

  // --- history across runs
  const card = document.getElementById("histCard");
  if (ST.history.length > 1) {
    card.style.display = "";
    charts.push(new Chart(document.getElementById("cRuns"), { type: "line",
      data: { labels: ST.history.map(h => h.time), datasets: order.map(b =>
        ({ ...lineDs(b, ST.history.map(h => h.win_rate[b] ?? null)), pointRadius: 4, tension: 0 })) },
      options: baseOpts() }));
    legend("lgRuns", order);
  } else card.style.display = "none";
}

document.getElementById("themeBtn").addEventListener("click", () => {
  const root = document.documentElement;
  const dark = root.dataset.theme ? root.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
  root.dataset.theme = dark ? "light" : "dark";
  draw();
});
matchMedia("(prefers-color-scheme: dark)").addEventListener("change", draw);
draw();
</script>
</body>
</html>
"""
