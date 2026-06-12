#!/usr/bin/env python3
"""
Season KPI Report generator — Kubota Spears (18 matches).

Reads rugby.db, aggregates per-match KPIs for Kubota Spears across
Kicking Game / Attack / Defence, and renders season_kpi.html using the
same visual design system + KPI definitions as match_report_final.html /
match_stats_final.py.

KPI definitions follow match_stats_final.py exactly:
  Try=5, Conv=2, PG=3, DG=3 (kicked only)
  Lineout Won = result in {Won Clean Catch, Won Tap (Scrappy)}
  Turnover Won = Possession 'Turnover Won' + Collection/Jackal Success
                 (overlap within 0.5 match-min removed)
"""
import json
import sqlite3

TEAM = "Kubota Spears"
DB = "rugby.db"
OUT = "season_kpi.html"


def match_min(ps_timestamp, period, p2_start):
    if period == 1:
        return ps_timestamp / 60.0
    return 40.0 + (ps_timestamp - p2_start) / 60.0


def count(rows, **conds):
    """Count rows matching all (column == value) conditions; value may be a set/list."""
    n = 0
    for r in rows:
        ok = True
        for k, v in conds.items():
            cell = r[k]
            if isinstance(v, (set, list, tuple)):
                if cell not in v:
                    ok = False
                    break
            elif cell != v:
                ok = False
                break
        if ok:
            n += 1
    return n


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def metres_sum(rows, action_name):
    return sum(_num(r["metres"]) for r in rows if r["action_name"] == action_name)


def to_won(team_rows, p2_start):
    """Possession TO Won + Jackal Success, dedup within 0.5 match-min."""
    poss_mins, jck_mins = [], []
    for r in team_rows:
        if r["action_name"] == "Possession" and r["action_type_name"] == "Turnover Won":
            poss_mins.append(match_min(_num(r["ps_timestamp"]), r["period"], p2_start))
        elif (r["action_name"] == "Collection" and r["action_type_name"] == "Jackal"
              and r["action_result_name"] == "Success"):
            jck_mins.append(match_min(_num(r["ps_timestamp"]), r["period"], p2_start))
    overlap = sum(1 for j in jck_mins if any(abs(j - p) < 0.5 for p in poss_mins))
    return len(poss_mins) + len(jck_mins) - overlap


def rnd(num, den, d=1):
    return round(num / den * 100, d) if den else 0.0


def avg(num, den, d=1):
    return round(num / den, d) if den else 0.0


con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
cur = con.cursor()

matches = cur.execute(
    "SELECT * FROM matches ORDER BY date_played, fxid"
).fetchall()

per_match = []
for m in matches:
    fxid = m["fxid"]
    # p2 start uses ALL events in the match (mirrors original df logic)
    p2_vals = cur.execute(
        "SELECT MIN(ps_timestamp) v FROM events WHERE fxid=? AND period=2", (fxid,)
    ).fetchone()["v"]
    p2_start = _num(p2_vals)

    rows = cur.execute(
        "SELECT * FROM events WHERE fxid=? AND team_name=?", (fxid, TEAM)
    ).fetchall()

    # --- attack ---
    carries = metres_sum(rows, "Carry")
    n_carry = count(rows, action_name="Carry")
    n_kick = count(rows, action_name="Kick")
    kick_m = metres_sum(rows, "Kick")
    n_ruck = count(rows, action_name="Ruck")
    ruck_won = count(rows, action_name="Ruck",
                     action_result_name={"Won Outright", "Penalty Won"})
    n_lo = count(rows, action_name="Lineout Throw")
    lo_won = count(rows, action_name="Lineout Throw",
                   action_result_name={"Won Clean Catch", "Won Tap (Scrappy)"})
    n_tack = count(rows, action_name="Tackle")
    n_miss = count(rows, action_name="Missed Tackle")
    n22 = count(rows, action_name="Attacking 22 Entry")
    s22 = sum(1 for r in rows if r["action_name"] == "Attacking 22 Entry"
              and r["action_type_name"] and "Try" in r["action_type_name"])

    # --- goal kicking ---
    def gk(typ, res):
        return count(rows, action_name="Goal Kick",
                     action_type_name=typ, action_result_name=res)
    conv_made = gk("Conversion", "Goal Kicked")
    conv_miss = gk("Conversion", "Goal Missed")
    pg_made = gk("Penalty Goal", "Goal Kicked")
    pg_miss = gk("Penalty Goal", "Goal Missed")
    dg_made = gk("Drop Goal", "Goal Kicked")
    dg_miss = gk("Drop Goal", "Goal Missed")
    gk_made = conv_made + pg_made + dg_made
    gk_att = gk_made + conv_miss + pg_miss + dg_miss
    pts_boot = conv_made * 2 + pg_made * 3 + dg_made * 3

    rec = {
        "fxid": fxid,
        "date": m["date_played"],
        "opp": m["opponent_name"],
        "ha": "H" if m["kubota_is_home"] else "A",
        "kub": m["kubota_score"],
        "opp_score": m["opponent_score"],
        "result": m["kubota_result"],
        # kicking
        "kicks": n_kick,
        "kick_m": kick_m,
        "avg_kick": avg(kick_m, n_kick),
        "gk_made": gk_made,
        "gk_att": gk_att,
        "gk_pct": rnd(gk_made, gk_att, 0),
        "pts_boot": pts_boot,
        # attack
        "tries": count(rows, action_name="Try"),
        "carries": n_carry,
        "metres": int(carries),
        "avg_carry": avg(carries, n_carry),
        "linebreaks": count(rows, action_name="Attacking Qualities",
                            action_type_name="Initial Break"),
        "def_beaten": count(rows, action_name="Attacking Qualities",
                            action_type_name="Defender Beaten"),
        # successful offloads only: Pass / Offload → Own Player
        "offloads": count(rows, action_name="Pass", action_type_name="Offload",
                          action_result_name="Own Player"),
        "passes": count(rows, action_name="Pass"),
        "ruck_won": ruck_won,
        "ruck_tot": n_ruck,
        "ruck_pct": rnd(ruck_won, n_ruck),
        "e22": n22,
        "s22": s22,
        "s22_pct": rnd(s22, n22, 0),
        # defence
        "tack_made": n_tack,
        "tack_miss": n_miss,
        "tack_att": n_tack + n_miss,
        "tack_pct": rnd(n_tack, n_tack + n_miss),
        "to_won": to_won(rows, p2_start),
        "to_con": count(rows, action_name="Turnover"),
        "pens": count(rows, action_name="Penalty Conceded"),
        "lo_steal": count(rows, action_name="Sequences",
                          action_type_name="Lineout Steal"),
    }
    per_match.append(rec)

con.close()

# --- season aggregates ---
n = len(per_match)
wins = sum(1 for r in per_match if r["result"] == "W")
losses = sum(1 for r in per_match if r["result"] == "L")
draws = sum(1 for r in per_match if r["result"] == "D")
pf = sum(r["kub"] for r in per_match)
pa = sum(r["opp_score"] for r in per_match)


def tot(key):
    return sum(r[key] for r in per_match)


season = {
    "matches": n, "wins": wins, "losses": losses, "draws": draws,
    "pf": pf, "pa": pa, "diff": pf - pa,
    "ppg": round(pf / n, 1), "papg": round(pa / n, 1),
    "tries": tot("tries"),
    "tries_pg": round(tot("tries") / n, 1),
    # kicking
    "kicks_pg": round(tot("kicks") / n, 1),
    "kick_m_pg": round(tot("kick_m") / n),
    "avg_kick": avg(tot("kick_m"), tot("kicks")),
    "gk_made": tot("gk_made"), "gk_att": tot("gk_att"),
    "gk_pct": rnd(tot("gk_made"), tot("gk_att"), 0),
    "pts_boot": tot("pts_boot"),
    # attack
    "carries_pg": round(tot("carries") / n, 1),
    "metres_pg": round(tot("metres") / n),
    "avg_carry": avg(tot("metres"), tot("carries")),
    "linebreaks": tot("linebreaks"),
    "lb_pg": round(tot("linebreaks") / n, 1),
    "offloads": tot("offloads"),
    "passes_pg": round(tot("passes") / n),
    "ruck_pct": rnd(tot("ruck_won"), tot("ruck_tot")),  # weighted: won / total rucks
    "e22": tot("e22"),
    "e22_pg": round(tot("e22") / n, 1),
    "s22_pct": rnd(tot("s22"), tot("e22"), 0),  # weighted: try-entries / total entries
    # defence
    "tack_made": tot("tack_made"),
    "tack_miss": tot("tack_miss"),
    "tack_pct": rnd(tot("tack_made"), tot("tack_att")),
    "to_won": tot("to_won"),
    "to_won_pg": round(tot("to_won") / n, 1),
    "to_con": tot("to_con"),
    "to_con_pg": round(tot("to_con") / n, 1),
    "pens": tot("pens"),
    "pens_pg": round(tot("pens") / n, 1),
}

DATA = {"team": TEAM, "season": season, "matches": per_match}

# ---------------------------------------------------------------- HTML
TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Season KPI Report – Kubota Spears</title>
<style>
:root {
  --kub-dark: #14213d;
  --kub-mid:  #1d3055;
  --kub-red:  #d6202b;
  --kub-gold: #e8a13c;
  --neutral:  #f5f4f0;
  --ink:      #1a1a1a;
  --muted:    #6b6b6b;
  --rule:     #d8d4cc;
  --good:     #1a7a3c;
  --warn:     #b85c00;
  --loss:     #c0202b;
  --radius:   4px;
  font-size: 14px;
}
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Helvetica Neue', Arial, sans-serif; background: #e8e4dc; color: var(--ink); }

.page {
  width: 297mm; min-height: 210mm;
  margin: 8mm auto; background: var(--neutral);
  display: flex; flex-direction: column;
  page-break-after: always; overflow: hidden;
  box-shadow: 0 2px 12px rgba(0,0,0,.18);
}
.page-header {
  background: var(--kub-dark); color: white;
  padding: 12px 20px 10px;
  display: flex; justify-content: space-between; align-items: center;
}
.page-header h1 { font-size: 16px; font-weight: 700; letter-spacing: .04em; }
.page-header .subtitle { font-size: 11px; color: var(--kub-gold); letter-spacing: .08em; text-transform: uppercase; }
.page-header .meta { text-align: right; font-size: 11px; color: rgba(255,255,255,.7); line-height: 1.5; }
.record-pill {
  background: var(--kub-red); padding: 5px 16px; border-radius: 20px;
  font-size: 17px; font-weight: 900; letter-spacing: .04em;
}

/* KPI summary cards */
.cards { display: flex; gap: 12px; padding: 16px 20px 4px; flex-wrap: wrap; }
.card {
  flex: 1; min-width: 120px;
  border: 1px solid var(--rule); border-radius: var(--radius);
  background: white; padding: 12px 14px; text-align: center;
}
.card .big { font-size: 30px; font-weight: 900; color: var(--kub-dark); line-height: 1; }
.card .sub { font-size: 9px; text-transform: uppercase; letter-spacing: .06em; color: var(--muted); margin-top: 6px; }
.card .note { font-size: 10px; color: var(--muted); margin-top: 3px; }

/* season table */
.tbl-wrap { flex: 1; padding: 14px 20px; }
.tbl-title {
  font-size: 11px; font-weight: 800; letter-spacing: .1em; text-transform: uppercase;
  color: var(--muted); border-bottom: 2px solid var(--rule); padding-bottom: 5px; margin-bottom: 10px;
}
.season-tbl { width: 100%; border-collapse: collapse; font-size: 11px; }
.season-tbl thead th {
  padding: 6px 7px; background: var(--kub-dark); color: white;
  font-size: 9.5px; font-weight: 700; letter-spacing: .03em; text-transform: uppercase;
  border-right: 1px solid rgba(255,255,255,.1); white-space: nowrap; text-align: center;
}
.season-tbl thead th.lcol { text-align: left; }
.season-tbl tbody td {
  padding: 4px 7px; text-align: center; border-bottom: 1px solid var(--rule);
  border-right: 1px solid var(--rule); white-space: nowrap; font-weight: 600;
}
.season-tbl tbody td.date-cell { text-align: left; color: var(--muted); font-size: 10px; min-width: 70px; }
.season-tbl tbody td.opp-cell  { text-align: left; font-weight: 600; min-width: 130px; }
.season-tbl tbody td.ha-cell   { font-size: 10px; color: var(--muted); }
.season-tbl tbody tr:hover td { background: rgba(0,0,0,.025); }
.season-tbl tbody tr.win  td.res-cell { color: var(--good); font-weight: 800; }
.season-tbl tbody tr.loss td.res-cell { color: var(--loss); font-weight: 800; }
.season-tbl tbody tr.win  td.score-cell { background: rgba(26,122,60,.07); }
.season-tbl tbody tr.loss td.score-cell { background: rgba(192,32,43,.07); }
.season-tbl tbody tr.total-row td {
  background: var(--kub-dark); color: white; font-weight: 800;
  border-top: 2px solid #555; border-bottom: none;
}
.season-tbl tbody tr.total-row td.lcol { text-align: left; }
.cell-good { color: var(--good); font-weight: 800; }
.cell-warn { color: var(--warn); font-weight: 800; }
.legend { display: flex; gap: 16px; flex-wrap: wrap; margin-top: 8px; font-size: 9px; color: var(--muted); }

@media print {
  body { background: white; }
  .page { margin: 0; box-shadow: none; width: 100%; }
}
</style>
</head>
<body>
<script>
const DATA = REPLACE_DATA_HERE;
const S = DATA.season;
const M = DATA.matches;

function header(title, right) {
  return `
    <div class="page-header">
      <div>
        <div class="subtitle">Japan Rugby League One D1 · Season 2026</div>
        <h1>${DATA.team} — ${title}</h1>
        <div style="font-size:11px;color:rgba(255,255,255,.6);margin-top:2px">${S.matches} matches · ${S.wins}W–${S.losses}L${S.draws?'–'+S.draws+'D':''}</div>
      </div>
      <div class="record-pill">${S.wins}–${S.losses}${S.draws?'–'+S.draws:''}</div>
      <div class="meta">${right||''}</div>
    </div>`;
}

function fmtDate(d) { const [y,m,da]=d.split('-'); return `${da}/${m}`; }

// ── PAGE 1: SEASON OVERVIEW ──────────────────────────
function pageOverview() {
  const cards = [
    [`${S.wins}–${S.losses}${S.draws?'–'+S.draws:''}`, 'Record', `Win ${Math.round(S.wins/S.matches*100)}%`],
    [`${S.pf}`, 'Points For', `${S.ppg}/game`],
    [`${S.pa}`, 'Points Against', `${S.papg}/game`],
    [`${S.diff>=0?'+':''}${S.diff}`, 'Points Diff', `${S.tries} tries`],
    [`${S.gk_pct}%`, 'Goal Kicking', `${S.gk_made}/${S.gk_att}`],
    [`${S.tack_pct}%`, 'Tackle Success', `${S.tack_made} made`],
  ];
  const cardHtml = cards.map(([b,s,n]) => `
    <div class="card"><div class="big">${b}</div><div class="sub">${s}</div><div class="note">${n}</div></div>`).join('');

  const rows = M.map(r => `
    <tr class="${r.result==='W'?'win':r.result==='L'?'loss':''}">
      <td class="date-cell">${fmtDate(r.date)}</td>
      <td class="ha-cell">${r.ha}</td>
      <td class="opp-cell">${r.opp}</td>
      <td class="score-cell">${r.kub}–${r.opp_score}</td>
      <td class="res-cell">${r.result}</td>
      <td>${r.tries}</td>
      <td>${r.metres}</td>
      <td>${r.linebreaks}</td>
      <td>${r.tack_pct}%</td>
      <td>${r.to_won}</td>
      <td class="${r.pens>=12?'cell-warn':''}">${r.pens}</td>
    </tr>`).join('');

  const totRow = `<tr class="total-row">
    <td class="lcol" colspan="3">SEASON TOTAL / AVG</td>
    <td>${S.pf}–${S.pa}</td>
    <td>${S.wins}W ${S.losses}L</td>
    <td>${S.tries}</td>
    <td>${S.metres_pg}</td>
    <td>${S.linebreaks}</td>
    <td>${S.tack_pct}%</td>
    <td>${S.to_won}</td>
    <td>${S.pens}</td>
  </tr>`;

  return `<div class="page">
    ${header('Season Overview', `PF ${S.pf} – PA ${S.pa}<br>Diff ${S.diff>=0?'+':''}${S.diff}`)}
    <div class="cards">${cardHtml}</div>
    <div class="tbl-wrap">
      <div class="tbl-title">Match-by-Match Results</div>
      <table class="season-tbl">
        <thead><tr>
          <th class="lcol">Date</th><th>H/A</th><th class="lcol">Opponent</th>
          <th>Score</th><th>Res</th><th>Tries</th><th>Carry m</th>
          <th>LB</th><th>Tackle%</th><th>TO Won</th><th>Pens</th>
        </tr></thead>
        <tbody>${rows}${totRow}</tbody>
      </table>
      <div class="legend">
        <span>H/A = Home/Away</span><span>LB = Linebreaks</span>
        <span>TO Won = Turnovers Won</span><span>Pens = Penalties Conceded</span>
        <span>Carry m = total per match (avg in total row)</span>
      </div>
    </div>
  </div>`;
}

// ── generic per-match KPI table ──────────────────────
function kpiPage(title, cols, totalCells, legend) {
  const head = cols.map(c => `<th class="${c.lcol?'lcol':''}">${c.h}</th>`).join('');
  const rows = M.map(r => {
    const tds = cols.map(c => {
      let v = c.fn(r);
      const cls = c.cls ? c.cls(r) : '';
      const extra = c.lcol ? 'date-cell' : '';
      return `<td class="${extra} ${cls}">${v}</td>`;
    }).join('');
    return `<tr class="${r.result==='W'?'win':r.result==='L'?'loss':''}">${tds}</tr>`;
  }).join('');
  const totRow = `<tr class="total-row">${totalCells}</tr>`;
  return `<div class="page">
    ${header(title)}
    <div class="tbl-wrap">
      <div class="tbl-title">${title} — per match (Kubota Spears only)</div>
      <table class="season-tbl">
        <thead><tr>${head}</tr></thead>
        <tbody>${rows}${totRow}</tbody>
      </table>
      <div class="legend">${legend.map(l=>`<span>${l}</span>`).join('')}</div>
    </div>
  </div>`;
}

const matchHeadCols = [
  {h:'Date', lcol:true, fn:r=>fmtDate(r.date)},
  {h:'H/A', fn:r=>r.ha},
  {h:'Opponent', lcol:true, fn:r=>r.opp},
  {h:'Score', fn:r=>`${r.kub}–${r.opp_score}`, cls:r=>'score-cell'},
];

// ── PAGE 2: KICKING GAME ─────────────────────────────
function pageKicking() {
  const cols = matchHeadCols.concat([
    {h:'Kicks', fn:r=>r.kicks},
    {h:'Kick m', fn:r=>r.kick_m},
    {h:'Avg m', fn:r=>r.avg_kick},
    {h:'GK Made', fn:r=>r.gk_made},
    {h:'GK Att', fn:r=>r.gk_att},
    {h:'GK %', fn:r=>r.gk_pct+'%', cls:r=>r.gk_att && r.gk_pct>=80?'cell-good':(r.gk_att && r.gk_pct<60?'cell-warn':'')},
    {h:'Pts (boot)', fn:r=>r.pts_boot},
  ]);
  const tot = `
    <td class="lcol" colspan="3">SEASON TOTAL / AVG</td>
    <td>—</td>
    <td>${S.kicks_pg}*</td><td>${S.kick_m_pg}*</td><td>${S.avg_kick}</td>
    <td>${S.gk_made}</td><td>${S.gk_att}</td><td>${S.gk_pct}%</td><td>${S.pts_boot}</td>`;
  return kpiPage('Kicking Game', cols, tot, [
    'Kicks = kicks from hand in play', 'Kick m = total kick metres',
    'GK = Goal Kicks (Conv+PG+DG)', 'Pts(boot) = Conv·2 + PG·3 + DG·3',
    '* = per-match average'
  ]);
}

// ── PAGE 3: ATTACK KPIs ──────────────────────────────
function pageAttack() {
  const cols = matchHeadCols.concat([
    {h:'Tries', fn:r=>r.tries, cls:r=>r.tries>=5?'cell-good':''},
    {h:'Carries', fn:r=>r.carries},
    {h:'Carry m', fn:r=>r.metres},
    {h:'Avg/Carry', fn:r=>r.avg_carry},
    {h:'LB', fn:r=>r.linebreaks, cls:r=>r.linebreaks>=10?'cell-good':''},
    {h:'Def Beaten', fn:r=>r.def_beaten},
    {h:'Offloads', fn:r=>r.offloads},
    {h:'Passes', fn:r=>r.passes},
    {h:'Ruck%', fn:r=>r.ruck_pct+'%'},
    {h:'22m Ent', fn:r=>r.e22},
    {h:'22m Try%', fn:r=>r.s22_pct+'%'},
  ]);
  const tot = `
    <td class="lcol" colspan="3">SEASON TOTAL / AVG</td>
    <td>—</td>
    <td>${S.tries}</td><td>${S.carries_pg}*</td><td>${S.metres_pg}*</td><td>${S.avg_carry}</td>
    <td>${S.linebreaks}</td><td>—</td><td>${S.offloads}</td><td>${S.passes_pg}*</td>
    <td>${S.ruck_pct}%</td><td>${S.e22}</td><td>${S.s22_pct}%</td>`;
  return kpiPage('Attack KPIs', cols, tot, [
    'LB = Linebreaks (Initial Break)', 'Def Beaten = Defenders Beaten',
    'Offloads = successful only (to own player)',
    'Carry m = total per match', 'Ruck% = Won Outright + Penalty Won',
    '22m Try% = entries leading to a try', '* = per-match average'
  ]);
}

// ── PAGE 4: DEFENCE KPIs ─────────────────────────────
function pageDefence() {
  const cols = matchHeadCols.concat([
    {h:'Tackles', fn:r=>r.tack_made},
    {h:'Missed', fn:r=>r.tack_miss, cls:r=>r.tack_miss>=20?'cell-warn':''},
    {h:'Attempted', fn:r=>r.tack_att},
    {h:'Tackle %', fn:r=>r.tack_pct+'%', cls:r=>r.tack_pct>=88?'cell-good':(r.tack_pct<80?'cell-warn':'')},
    {h:'TO Won', fn:r=>r.to_won, cls:r=>r.to_won>=10?'cell-good':''},
    {h:'TO Con', fn:r=>r.to_con, cls:r=>r.to_con>=15?'cell-warn':''},
    {h:'Pens', fn:r=>r.pens, cls:r=>r.pens>=12?'cell-warn':''},
    {h:'LO Steals', fn:r=>r.lo_steal},
  ]);
  const tot = `
    <td class="lcol" colspan="3">SEASON TOTAL / AVG</td>
    <td>—</td>
    <td>${S.tack_made}</td><td>${S.tack_miss}</td><td>${S.tack_made+S.tack_miss}</td>
    <td>${S.tack_pct}%</td><td>${S.to_won}</td><td>${S.to_con}</td><td>${S.pens}</td><td>—</td>`;
  return kpiPage('Defence KPIs', cols, tot, [
    'TO Won = Turnovers Won (Poss TO + Jackal, dedup)',
    'TO Con = Turnovers Conceded', 'Pens = Penalties Conceded',
    'LO Steals = Lineout Steals', 'green ≥88% / amber <80% tackle'
  ]);
}

document.addEventListener('DOMContentLoaded', () => {
  document.body.innerHTML =
    pageOverview() + pageKicking() + pageAttack() + pageDefence();
});
</script>
</body>
</html>"""

html = TEMPLATE.replace("REPLACE_DATA_HERE", json.dumps(DATA, ensure_ascii=False))
with open(OUT, "w", encoding="utf-8") as f:
    f.write(html)

print(f"Wrote {OUT}")
print(f"Record: {wins}W-{losses}L-{draws}D | PF {pf} / PA {pa} (diff {pf-pa:+d})")
print(f"Goal kicking: {season['gk_made']}/{season['gk_att']} ({season['gk_pct']}%)")
print(f"Tackle %: {season['tack_pct']} | TO won/g {season['to_won_pg']} | Pens/g {season['pens_pg']}")
