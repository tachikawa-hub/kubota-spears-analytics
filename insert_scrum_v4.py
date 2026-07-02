#!/usr/bin/env python3
"""insert_scrum_v4.py — Scrum section v4
Changes vs v3:
  - Won Rate = Won / (Won + Lost), Reset excluded from denominator
  - Scrum by Match: bar chart → 2-line chart (Own Ball / Opp Ball per match)
  - Opponent panel: full-season match data (18 matches from all CSV)
  - Spears panel: 21 matches from DB
"""
import os, re, math, csv, sqlite3, collections
from data_paths import CSV_DIR, DB_PATH, OUTPUT_DIR, list_csv_files

BIOUT_DIR = OUTPUT_DIR

# abbr → CSV/DB full team name
_DB_TEAM_NAME = {
    "BlackRams":   "BlackRams Tokyo",
    "BlueRevs":    "Shizuoka BlueRevs",
    "BraveLupus":  "Toshiba Brave Lupus Tokyo",
    "D-Rocks":     "Urayasu D-Rocks",
    "Dynaboars":   "Mitsubishi Sagamihara Dynaboars",
    "Eagles":      "Yokohama Canon Eagles",
    "Heat":        "Mie Honda Heat",
    "Steelers":    "Kobelco Kobe Steelers",
    "Sungoliath":  "Tokyo Sungoliath",
    "Verblitz":    "Toyota Verblitz",
    "WildKnights": "Saitama Wild Knights",
}
_FULL_TO_ABBR = {v: k for k, v in _DB_TEAM_NAME.items()}
_D1_TEAM_SET  = set(_DB_TEAM_NAME.values()) | {"Kubota Spears"}

# CSV/DB ActionResultName → internal key
_SCRUM_RESULT_MAP = {
    "Won Outright":  "WonOut",
    "Won Penalty":   "WonPen",
    "Won Free Kick": "WonFK",
    "Reset":         "Reset",
    "Lost Outright": "LostOut",
    "Lost Free Kick":"LostFK",
    "Lost Pen Con":  "LostPen",
}


def _load_spears_opp_scrum():
    """OPP BALL for Spears panel: opponents' scrum results in all 21 Spears matches, from DB."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.execute("""
            SELECT e.action_result_name, COUNT(*) as n
            FROM events e
            JOIN matches m ON e.fxid = m.fxid
            WHERE m.season = 2026
              AND (m.home_team_name = 'Kubota Spears' OR m.away_team_name = 'Kubota Spears')
              AND e.team_name != 'Kubota Spears'
              AND e.action_name = 'Scrum'
            GROUP BY e.action_result_name
        """)
        results, total = {}, 0
        for row_name, n in cur.fetchall():
            key = _SCRUM_RESULT_MAP.get(row_name)
            if key is not None:
                results[key] = results.get(key, 0) + n
                total += n
        conn.close()
        return results, total
    except Exception as e:
        print(f"[WARN] Spears OPP scrum load failed: {e}")
        return {}, 0


def _load_opp_scrum_from_csvs():
    """OPP BALL for each scout team: opponents' scrum results in all their D1 matches, from CSV."""
    data = collections.defaultdict(lambda: {"results": {}, "total": 0})
    for fpath in list_csv_files(CSV_DIR):
        try:
            with open(fpath, encoding="utf-8-sig", newline="") as f:
                for row in csv.DictReader(f):
                    if row.get("actionName") != "Scrum":
                        continue
                    if "D1" not in (row.get("competitionName") or ""):
                        continue
                    tn   = row.get("teamName", "")
                    home = row.get("homeTeamName", "")
                    away = row.get("awayTeamName", "")
                    if tn == home:
                        focal_full = away
                    elif tn == away:
                        focal_full = home
                    else:
                        continue
                    abbr = _FULL_TO_ABBR.get(focal_full)
                    if abbr is None:
                        continue  # Kubota Spears or non-D1
                    key = _SCRUM_RESULT_MAP.get(row.get("ActionResultName", ""))
                    if key is None:
                        continue
                    data[abbr]["results"][key] = data[abbr]["results"].get(key, 0) + 1
                    data[abbr]["total"] += 1
        except Exception:
            continue
    return dict(data)


_SPEARS_OPP_SCRUM = _load_spears_opp_scrum()
_SCOUT_OPP_SCRUM  = _load_opp_scrum_from_csvs()

# ─────────────────────────────────────────────────────────────────────────────
# DATA
# matches format: (round, opp_short, own_wp, opp_wp)  ← Won Rate excluding Reset
# ─────────────────────────────────────────────────────────────────────────────

SPEARS_SCRUM = {
    "name": "Kubota Spears",
    "own":  [158, 138],
    "results": {"WonOut":99,"WonPen":31,"WonFK":8,"Reset":12,"LostPen":4,"LostFK":2,"LostOut":2},
    "stability": [33, 114, 11],
    "attack": {"Scrum Half Pass":74,"Scrum Half Run":14,"No 8 Pick Up":15,"No 8 Pass":8,"Scrum Half Kick":1},
    "direction": {"Open":92,"Blind":20},
    "matches": [
        # (round, opp_abbr, spears_wp, opp_wp)  — Won/(Won+Lost) per match
        ( 1,"Steelers",   100, 100),
        ( 2,"BlackRams",   75, 100),
        ( 3,"Sungoliath",  75,  67),
        ( 4,"Heat",       100, 100),
        ( 5,"Verblitz",   100, 100),
        ( 6,"BraveLupus", 100,  90),
        ( 7,"D-Rocks",    100,  60),
        ( 8,"BlueRevs",   100, 100),
        ( 9,"Dynaboars",   60,  75),
        (10,"Eagles",      92, 100),
        (11,"WildKnight",  100, 86),
        (12,"D-Rocks",    100, 100),
        (13,"BraveLupus", 100,  88),
        (14,"Verblitz",   100, 100),
        (15,"Sungoliath", 100, 100),
        (16,"Heat",       100,  83),
        (17,"BlackRams",   90,  90),
        (18,"Steelers",    88,  80),
        (19,"BraveLupus", 100,  89),
        (20,"WildKnight",  75,  88),
        (22,"Steelers",   100,  86),
    ],
}

TEAM_SCRUM_DATA = {
    "Steelers": {
        "name":"Kobelco Kobe Steelers",
        "own":[133,105],
        "results":{"WonOut":72,"WonPen":23,"WonFK":10,"Reset":16,"LostPen":8,"LostFK":4,"LostOut":0},
        "stability":[17,109,7],
        "attack":{"Scrum Half Pass":33,"No 8 Pick Up":19,"No 8 Pass":28,"Scrum Half Run":1,"Scrum Half Kick":1},
        "direction":{"Open":73,"Blind":9},
        "matches": [
            ( 1,"Spears",    100, 100),( 2,"Heat",       86,  91),( 3,"Verblitz",  100, 100),
            ( 4,"Sungoliath",100,  88),( 5,"BlackRams",   86, 100),( 6,"Eagles",   100, 100),
            ( 7,"BlueRevs",   67, 100),( 8,"BraveLupus",  90, 100),( 9,"WildKnight", 73, 100),
            (10,"D-Rocks",   100,  91),(11,"Dynaboars",  100,  91),(12,"Eagles",    100,  89),
            (13,"BlueRevs",   80,  93),(14,"BlackRams",   89, 100),(15,"Verblitz",   83, 100),
            (16,"Sungoliath",100, 100),(17,"Heat",        100, 100),(18,"Spears",     80,  88),
        ],
    },
    "BlackRams": {
        "name":"BlackRams Tokyo",
        "own":[150,136],
        "results":{"WonOut":96,"WonPen":31,"WonFK":9,"Reset":10,"LostPen":2,"LostFK":2,"LostOut":0},
        "stability":[27,117,6],
        "attack":{"Scrum Half Pass":56,"No 8 Pick Up":20,"Scrum Half Run":14,"No 8 Pass":7,"Scrum Half Kick":8},
        "direction":{"Open":87,"Blind":19},
        "matches": [
            ( 1,"Sungoliath",100, 100),( 2,"Spears",     100,  75),( 3,"Heat",      100,  73),
            ( 4,"Verblitz",  100, 100),( 5,"Steelers",   100,  86),( 6,"Dynaboars", 100, 100),
            ( 7,"WildKnight", 90, 100),( 8,"Eagles",     100, 100),( 9,"D-Rocks",   100,  71),
            (10,"BraveLupus",100,  57),(11,"BlueRevs",    83, 100),(12,"WildKnight",100,  80),
            (13,"Dynaboars", 100,  92),(14,"Steelers",   100,  89),(15,"Heat",        89,  80),
            (16,"Verblitz",  100,  83),(17,"Spears",      90,  90),(18,"Sungoliath", 100, 100),
        ],
    },
    "BraveLupus": {
        "name":"Toshiba Brave Lupus Tokyo",
        "own":[133,96],
        "results":{"WonOut":69,"WonPen":21,"WonFK":6,"Reset":13,"LostPen":19,"LostFK":3,"LostOut":2},
        "stability":[17,100,16],
        "attack":{"Scrum Half Pass":60,"No 8 Pass":8,"Scrum Half Run":6},
        "direction":{"Open":68,"Blind":6},
        "matches": [
            ( 1,"WildKnight", 67,  91),( 2,"BlueRevs",   71,  92),( 3,"Eagles",     88,  73),
            ( 4,"Dynaboars",  70, 100),( 5,"D-Rocks",    83, 100),( 6,"Spears",      90, 100),
            ( 7,"Heat",      100,  89),( 8,"Steelers",   100,  90),( 9,"Verblitz",    71, 100),
            (10,"BlackRams",  57, 100),(11,"Sungoliath",  50, 100),(12,"Heat",        100,  89),
            (13,"Spears",     88, 100),(14,"D-Rocks",    100, 100),(15,"Dynaboars",  100, 100),
            (16,"Eagles",     50, 100),(17,"BlueRevs",   100,  88),(18,"WildKnight",  70,  93),
        ],
    },
    "BlueRevs": {
        "name":"Shizuoka BlueRevs",
        "own":[173,134],
        "results":{"WonOut":75,"WonPen":52,"WonFK":7,"Reset":22,"LostPen":15,"LostFK":2,"LostOut":0},
        "stability":[47,116,11],
        "attack":{"Scrum Half Pass":67,"Scrum Half Run":12,"No 8 Pick Up":9,"No 8 Pass":7,"Scrum Half Kick":2},
        "direction":{"Open":85,"Blind":13},
        "matches": [
            ( 1,"Eagles",    100, 100),( 2,"BraveLupus",  92,  71),( 3,"D-Rocks",    86,  80),
            ( 4,"WildKnight", 78,  86),( 5,"Dynaboars",  100,  67),( 6,"Verblitz",    88,  57),
            ( 7,"Steelers",  100,  67),( 8,"Spears",     100, 100),( 9,"Heat",         86, 100),
            (10,"Sungoliath", 67,  86),(11,"BlackRams",  100,  83),(12,"Verblitz",     89,  83),
            (13,"Steelers",   93,  80),(14,"Dynaboars",   78,  86),(15,"WildKnight",   89, 100),
            (16,"D-Rocks",    91,  83),(17,"BraveLupus", 100,  88),(18,"Eagles",        79,  75),
        ],
    },
    "Dynaboars": {
        "name":"Mitsubishi Sagamihara Dynaboars",
        "own":[138,117],
        "results":{"WonOut":95,"WonPen":12,"WonFK":10,"Reset":7,"LostPen":9,"LostFK":5,"LostOut":0},
        "stability":[8,112,18],
        "attack":{"Scrum Half Pass":58,"No 8 Pick Up":24,"No 8 Pass":10,"Scrum Half Run":2,"Scrum Half Kick":1},
        "direction":{"Open":79,"Blind":16},
        "matches": [
            ( 1,"D-Rocks",    80, 100),( 2,"Eagles",      80,  88),( 3,"WildKnight",  80,  82),
            ( 4,"BraveLupus", 100,  70),( 5,"BlueRevs",    67, 100),( 6,"BlackRams",  100, 100),
            ( 7,"Sungoliath", 100,  62),( 8,"Heat",        100,  80),( 9,"Spears",      75,  60),
            (10,"Verblitz",    75, 100),(11,"Steelers",     91, 100),(12,"Sungoliath",  86, 100),
            (13,"BlackRams",   92, 100),(14,"BlueRevs",     86,  78),(15,"BraveLupus", 100, 100),
            (16,"WildKnight", 100,  83),(17,"Eagles",      100,  86),(18,"D-Rocks",    100,  89),
        ],
    },
    "Eagles": {
        "name":"Yokohama Canon Eagles",
        "own":[145,112],
        "results":{"WonOut":77,"WonPen":22,"WonFK":13,"Reset":17,"LostPen":12,"LostFK":2,"LostOut":2},
        "stability":[10,117,18],
        "attack":{"Scrum Half Pass":66,"No 8 Pick Up":11,"Scrum Half Run":7,"No 8 Pass":3},
        "direction":{"Open":81,"Blind":6},
        "matches": [
            ( 1,"BlueRevs",  100, 100),( 2,"Dynaboars",   88,  80),( 3,"BraveLupus",  73,  88),
            ( 4,"D-Rocks",    67,  75),( 5,"WildKnight",   50,  90),( 6,"Steelers",   100, 100),
            ( 7,"Verblitz",  100, 100),( 8,"BlackRams",   100, 100),( 9,"Sungoliath",  80,  88),
            (10,"Spears",    100,  92),(11,"Heat",          75, 100),(12,"Steelers",    89, 100),
            (13,"Verblitz",  100,  89),(14,"WildKnight",  100,  90),(15,"D-Rocks",      80, 100),
            (16,"BraveLupus",100,  50),(17,"Dynaboars",    86, 100),(18,"BlueRevs",     75,  79),
        ],
    },
    "D-Rocks": {
        "name":"Urayasu D-Rocks",
        "own":[147,115],
        "results":{"WonOut":99,"WonPen":10,"WonFK":6,"Reset":13,"LostPen":14,"LostFK":5,"LostOut":0},
        "stability":[13,117,17],
        "attack":{"Scrum Half Pass":71,"No 8 Pick Up":19,"Scrum Half Run":5,"No 8 Pass":8},
        "direction":{"Open":93,"Blind":10},
        "matches": [
            ( 1,"Dynaboars", 100,  80),( 2,"WildKnight",  50, 100),( 3,"BlueRevs",    80,  86),
            ( 4,"Eagles",     75,  67),( 5,"BraveLupus",  100,  83),( 6,"Heat",        100,  86),
            ( 7,"Spears",     60, 100),( 8,"Sungoliath",   60,  70),( 9,"BlackRams",    71, 100),
            (10,"Steelers",   91, 100),(11,"Verblitz",    100, 100),(12,"Spears",       100, 100),
            (13,"Heat",        60,  60),(14,"BraveLupus", 100, 100),(15,"Eagles",       100,  80),
            (16,"BlueRevs",    83,  91),(17,"WildKnight", 100,  86),(18,"Dynaboars",     89, 100),
        ],
    },
    "WildKnights": {
        "name":"Saitama Wild Knights",
        "own":[156,125],
        "results":{"WonOut":94,"WonPen":22,"WonFK":9,"Reset":16,"LostPen":8,"LostFK":6,"LostOut":1},
        "stability":[9,132,15],
        "attack":{"Scrum Half Pass":74,"No 8 Pick Up":13,"Scrum Half Run":4,"No 8 Pass":4,"Scrum Half Kick":1},
        "direction":{"Open":86,"Blind":12},
        "matches": [
            ( 1,"BraveLupus", 91,  67),( 2,"D-Rocks",    100,  50),( 3,"Dynaboars",   82,  80),
            ( 4,"BlueRevs",    86,  78),( 5,"Eagles",      90,  50),( 6,"Sungoliath", 100,  75),
            ( 7,"BlackRams",  100,  90),( 8,"Verblitz",    67,  86),( 9,"Steelers",   100,  73),
            (10,"Heat",        88,  70),(11,"Spears",       86, 100),(12,"BlackRams",   80, 100),
            (13,"Sungoliath",  86, 100),(14,"Eagles",      100,  90),(15,"BlueRevs",   100,  89),
            (16,"Dynaboars",   83, 100),(17,"D-Rocks",    100, 100),(18,"BraveLupus",   93,  70),
        ],
    },
    "Heat": {
        "name":"Mie Honda Heat",
        "own":[141,118],
        "results":{"WonOut":105,"WonPen":9,"WonFK":4,"Reset":8,"LostPen":10,"LostFK":5,"LostOut":0},
        "stability":[17,120,5],
        "attack":{"Scrum Half Pass":52,"No 8 Pick Up":31,"No 8 Pass":16,"Scrum Half Run":4,"Scrum Half Kick":3},
        "direction":{"Open":87,"Blind":20},
        "matches": [
            ( 1,"Verblitz",  100,  62),( 2,"Steelers",    91,  86),( 3,"BlackRams",   73, 100),
            ( 4,"Spears",    100, 100),( 5,"Sungoliath",  100,  83),( 6,"D-Rocks",     86, 100),
            ( 7,"BraveLupus", 89, 100),( 8,"Dynaboars",   80, 100),( 9,"BlueRevs",    100,  86),
            (10,"WildKnight", 70,  88),(11,"Eagles",      100,  75),(12,"BraveLupus",   89, 100),
            (13,"D-Rocks",    60,  60),(14,"Sungoliath",  100, 100),(15,"BlackRams",    80,  89),
            (16,"Spears",     83, 100),(17,"Steelers",    100, 100),(18,"Verblitz",     100, 100),
        ],
    },
    "Sungoliath": {
        "name":"Tokyo Sungoliath",
        "own":[126,98],
        "results":{"WonOut":65,"WonPen":22,"WonFK":11,"Reset":14,"LostPen":10,"LostFK":3,"LostOut":1},
        "stability":[16,101,9],
        "attack":{"Scrum Half Pass":55,"No 8 Pass":10,"No 8 Pick Up":4,"Scrum Half Kick":2,"Scrum Half Run":1},
        "direction":{"Open":63,"Blind":8},
        "matches": [
            ( 1,"BlackRams",  100, 100),( 2,"Verblitz",  100, 100),( 3,"Spears",      67,  75),
            ( 4,"Steelers",    88, 100),( 5,"Heat",        83, 100),( 6,"WildKnight",  75, 100),
            ( 7,"Dynaboars",   62, 100),( 8,"D-Rocks",    70,  60),( 9,"Eagles",       88,  80),
            (10,"BlueRevs",    86,  67),(11,"BraveLupus", 100,  50),(12,"Dynaboars",  100,  86),
            (13,"WildKnight", 100,  86),(14,"Heat",        100, 100),(15,"Spears",     100, 100),
            (16,"Steelers",   100, 100),(17,"Verblitz",   100, 100),(18,"BlackRams",   100, 100),
        ],
    },
    "Verblitz": {
        "name":"Toyota Verblitz",
        "own":[141,117],
        "results":{"WonOut":97,"WonPen":10,"WonFK":10,"Reset":14,"LostPen":8,"LostFK":2,"LostOut":0},
        "stability":[9,117,15],
        "attack":{"Scrum Half Pass":76,"No 8 Pick Up":10,"Scrum Half Run":8,"No 8 Pass":5,"Scrum Half Kick":1},
        "direction":{"Open":91,"Blind":10},
        "matches": [
            ( 1,"Heat",        62, 100),( 2,"Sungoliath", 100, 100),( 3,"Steelers",   100, 100),
            ( 4,"BlackRams",  100, 100),( 5,"Spears",     100, 100),( 6,"BlueRevs",    57,  88),
            ( 7,"Eagles",     100, 100),( 8,"WildKnight",  86,  67),( 9,"BraveLupus", 100,  71),
            (10,"Dynaboars",  100,  75),(11,"D-Rocks",    100, 100),(12,"BlueRevs",    83,  89),
            (13,"Eagles",      89, 100),(14,"Spears",     100, 100),(15,"Steelers",    100,  83),
            (16,"BlackRams",   83, 100),(17,"Sungoliath", 100, 100),(18,"Heat",        100, 100),
        ],
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def pct(n, d): return round(100 * n / d) if d else 0

def won_color(wp):
    return "#16a34a" if wp >= 90 else "#2563eb" if wp >= 75 else "#d97706"

ATK_COLORS = {
    "Scrum Half Pass":"#2563EB","Scrum Half Run":"#16A34A",
    "No 8 Pick Up":"#D97706","No 8 Pass":"#7C3AED","Scrum Half Kick":"#0891B2",
}
DIR_COLORS = {"Open":"#3B82F6","Blind":"#F97316"}

RESULT_ROWS = [
    ("WonOut",  "Won Outright",          "#16a34a","#f0fdf4"),
    ("WonPen",  "Penalty Won",           "#22c55e","#f0fdf4"),
    ("WonFK",   "Free Kick Won",         "#4ade80","#f0fdf4"),
    ("Reset",   "Reset",                 "#6b7280","#f9fafb"),
    ("LostOut", "Lost Outright",         "#dc2626","#fff1f2"),
    ("LostFK",  "Lost Free Kick",        "#ef4444","#fff1f2"),
    ("LostPen", "Lost Penalty Conceded", "#f87171","#fff1f2"),
]

def _won_denom(results):
    """Won Rate denominator = Won + Lost (excluding Reset)."""
    won  = results.get("WonOut",0)+results.get("WonPen",0)+results.get("WonFK",0)
    lost = results.get("LostPen",0)+results.get("LostFK",0)+results.get("LostOut",0)
    return won, won + lost

# ─────────────────────────────────────────────────────────────────────────────
# RESULT TABLE
# ─────────────────────────────────────────────────────────────────────────────

def _result_table_html(section_label, results, total_all):
    """Build a result table card. Won Rate = Won/(Won+Lost), Reset excluded from denom."""
    won_n, denom = _won_denom(results)
    wp = pct(won_n, denom)
    wc = won_color(wp)

    rows = ""
    for key, display, color, bg in RESULT_ROWS:
        cnt = results.get(key, 0)
        if cnt == 0:
            continue
        p = pct(cnt, total_all)
        rows += (
            f'<tr style="background:{bg}">'
            f'<td style="padding:4px 6px;font-size:10px;color:{color};font-weight:700;border-left:3px solid {color}">{display}</td>'
            f'<td style="padding:4px 6px;font-size:10px;color:#333;text-align:right;font-weight:700">{cnt}</td>'
            f'<td style="padding:4px 6px;font-size:10px;color:#888;text-align:right">{p}%</td>'
            f'</tr>'
        )
    rows += (
        f'<tr style="background:#F8F9FA;border-top:2px solid #DEE2E6">'
        f'<td style="padding:4px 6px;font-size:10px;font-weight:800;color:#14213D">TOTAL</td>'
        f'<td style="padding:4px 6px;font-size:10px;font-weight:800;color:#14213D;text-align:right">{total_all}</td>'
        f'<td style="padding:4px 6px;font-size:10px;color:#888;text-align:right">100%</td>'
        f'</tr>'
    )

    return (
        f'<div style="background:#fff;border:1px solid #DEE2E6;border-radius:6px;overflow:hidden">'
        f'<div style="background:#F8F9FA;padding:5px 8px;border-bottom:1px solid #DEE2E6;'
        f'display:flex;align-items:center;justify-content:space-between">'
        f'<span style="font-size:8.5px;font-weight:800;color:#14213D;text-transform:uppercase;letter-spacing:.05em">{section_label}</span>'
        f'<span style="font-family:Oswald,sans-serif;font-size:26px;font-weight:700;color:{wc};line-height:1">'
        f'{wp}%'
        f'<span style="font-size:9.5px;color:#888;font-family:sans-serif;margin-left:4px">Won ({won_n}/{denom})</span>'
        f'</span>'
        f'</div>'
        f'<table style="width:100%;border-collapse:collapse">'
        f'<thead><tr style="background:#F8F9FA">'
        f'<th style="padding:3px 6px;font-size:8.5px;color:#555;text-align:left;font-weight:700;border-bottom:1px solid #DEE2E6">Result</th>'
        f'<th style="padding:3px 6px;font-size:8.5px;color:#555;text-align:right;font-weight:700;border-bottom:1px solid #DEE2E6">n</th>'
        f'<th style="padding:3px 6px;font-size:8.5px;color:#555;text-align:right;font-weight:700;border-bottom:1px solid #DEE2E6">%</th>'
        f'</tr></thead>'
        f'<tbody>{rows}</tbody>'
        f'</table></div>'
    )

def result_col(team_d, opp_d, opp_results=None, opp_total=None):
    own = _result_table_html("Own Ball Scrum Result", team_d["results"], team_d["own"][0])
    if opp_results and opp_total:
        opp = _result_table_html("Opp Ball Scrum Result", opp_results, opp_total)
    else:
        opp = _result_table_html("Opp Ball Scrum Result", opp_d["results"], opp_d["own"][0])
    return f'<div style="display:flex;flex-direction:column;gap:8px">{own}{opp}</div>'

# ─────────────────────────────────────────────────────────────────────────────
# STABILITY DONUT  (semicircle donut, 180°)
# Arc order left→right: Negative(red) | Neutral(gray) | Positive(green)
# White vertical target line at 95%.  No needle.
# ─────────────────────────────────────────────────────────────────────────────

def _speedometer_svg(pos, neu, neg):
    """Semicircle donut SVG — thick ring, no needle, white 95% target line."""
    total   = pos + neu + neg or 1
    neg_end = 100.0 * neg / total
    neu_end = 100.0 * (neg + neu) / total

    cx, cy = 74, 64
    ro, ri = 58, 26   # ring thickness = 32px
    SVG_W  = 148
    SVG_H  = 70       # 6px below center baseline

    def pt(p, r):
        a = math.pi * (1.0 - p / 100.0)
        return cx + r * math.cos(a), cy - r * math.sin(a)

    def arc_seg(p1, p2, color):
        if p2 - p1 < 0.05:
            return ""
        la = 1 if (p2 - p1) >= 99.9 else 0
        x1o, y1o = pt(p1, ro); x2o, y2o = pt(p2, ro)
        x1i, y1i = pt(p1, ri); x2i, y2i = pt(p2, ri)
        d = (f"M {x1o:.2f},{y1o:.2f} A {ro} {ro} 0 {la} 0 {x2o:.2f},{y2o:.2f} "
             f"L {x2i:.2f},{y2i:.2f} A {ri} {ri} 0 {la} 1 {x1i:.2f},{y1i:.2f} Z")
        return f'<path d="{d}" fill="{color}"/>'

    segs = (
        arc_seg(0,       neg_end, "#DC2626") +
        arc_seg(neg_end, neu_end, "#9CA3AF") +
        arc_seg(neu_end, 100.0,   "#16A34A")
    )

    # White vertical target line at 95%
    tx_o, ty_o = pt(95, ro + 4)
    tx_i, ty_i = pt(95, ri - 4)
    target = (
        f'<line x1="{tx_i:.2f}" y1="{ty_i:.2f}" x2="{tx_o:.2f}" y2="{ty_o:.2f}" '
        f'stroke="white" stroke-width="3" stroke-linecap="round"/>'
    )

    return (
        f'<svg viewBox="0 0 {SVG_W} {SVG_H}" style="display:block;width:100%">'
        + segs + target
        + f'</svg>'
    )


def _gauge_block(pos, neu, neg, title):
    """HTML block: ① title ② SVG donut ③ large % (HTML) ④ legend."""
    total    = pos + neu + neg or 1
    stable_p = round(100 * (pos + neu) / total)
    pos_p    = round(100 * pos / total)
    neu_p    = round(100 * neu / total)
    neg_p    = 100 - pos_p - neu_p
    nc       = won_color(stable_p)

    svg = _speedometer_svg(pos, neu, neg)

    title_html = (
        f'<div style="text-align:center;font-size:8.5px;font-weight:800;color:#14213D;'
        f'text-transform:uppercase;letter-spacing:.05em;padding-bottom:1px">{title}</div>'
    )
    pct_html = (
        f'<div style="text-align:center;font-family:Oswald,sans-serif;font-size:26px;'
        f'font-weight:800;color:{nc};line-height:1;margin:0 0 2px">{stable_p}%</div>'
    )
    legend_html = (
        f'<div style="display:flex;justify-content:space-between;padding:0 2px">'
        f'<span style="font-size:6.5px;color:#DC2626;font-weight:700">Neg {neg} ({neg_p}%)</span>'
        f'<span style="font-size:6.5px;color:#6B7280;font-weight:700">Neu {neu} ({neu_p}%)</span>'
        f'<span style="font-size:6.5px;color:#16A34A;font-weight:700">Pos {pos} ({pos_p}%)</span>'
        f'</div>'
    )

    return title_html + svg + pct_html + legend_html


def stability_col(own_stab, opp_stab):
    own_block = _gauge_block(*own_stab, "Own Ball")
    opp_block = _gauge_block(*opp_stab, "Opp Ball")
    return (
        f'<div style="background:#fff;border:1px solid #DEE2E6;border-radius:6px;overflow:hidden;'
        f'display:flex;flex-direction:column">'
        f'<div style="background:#F8F9FA;padding:4px 8px;border-bottom:1px solid #DEE2E6">'
        f'<span style="font-size:8.5px;font-weight:800;color:#14213D;text-transform:uppercase;'
        f'letter-spacing:.05em">Stability</span>'
        f'</div>'
        f'<div style="flex:1;padding:4px 4px 0">{own_block}</div>'
        f'<div style="height:1px;background:#E5E7EB;margin:0 6px"></div>'
        f'<div style="flex:1;padding:4px 4px 4px">{opp_block}</div>'
        f'</div>'
    )

# ─────────────────────────────────────────────────────────────────────────────
# ATTACK OPTION + DIRECTION
# ─────────────────────────────────────────────────────────────────────────────

def attack_col(team_d):
    atk = team_d["attack"]
    atk_tot = sum(atk.values()) or 1

    rows = ""
    for key in sorted(atk, key=lambda k: -atk[k]):
        cnt = atk[key]
        if not cnt: continue
        color = ATK_COLORS.get(key,"#6B7280")
        p = pct(cnt, atk_tot)
        rows += (
            f'<tr>'
            f'<td style="padding:4px 6px;font-size:10px;color:{color};font-weight:700;border-left:3px solid {color}">{key}</td>'
            f'<td style="padding:4px 6px;font-size:10px;color:#333;text-align:right;font-weight:700">{cnt}</td>'
            f'<td style="padding:4px 6px;font-size:10px;color:#888;text-align:right">{p}%</td>'
            f'</tr>'
        )
    rows += (
        f'<tr style="background:#F8F9FA;border-top:2px solid #DEE2E6">'
        f'<td style="padding:4px 6px;font-size:10px;font-weight:800;color:#14213D">TOTAL</td>'
        f'<td style="padding:4px 6px;font-size:10px;font-weight:800;color:#14213D;text-align:right">{sum(atk.values())}</td>'
        f'<td style="padding:4px 6px;font-size:10px;color:#888;text-align:right">100%</td>'
        f'</tr>'
    )

    atk_card = (
        f'<div style="background:#fff;border:1px solid #DEE2E6;border-radius:6px;overflow:hidden">'
        f'<div style="background:#F8F9FA;padding:4px 8px;border-bottom:1px solid #DEE2E6">'
        f'<span style="font-size:8.5px;font-weight:800;color:#14213D;text-transform:uppercase;letter-spacing:.05em">Attack Option</span>'
        f'</div>'
        f'<table style="width:100%;border-collapse:collapse">'
        f'<thead><tr style="background:#F8F9FA">'
        f'<th style="padding:3px 6px;font-size:8.5px;color:#555;text-align:left;font-weight:700;border-bottom:1px solid #DEE2E6">Option</th>'
        f'<th style="padding:3px 6px;font-size:8.5px;color:#555;text-align:right;font-weight:700;border-bottom:1px solid #DEE2E6">n</th>'
        f'<th style="padding:3px 6px;font-size:8.5px;color:#555;text-align:right;font-weight:700;border-bottom:1px solid #DEE2E6">%</th>'
        f'</tr></thead>'
        f'<tbody>{rows}</tbody></table></div>'
    )

    drc = team_d["direction"]
    drc_tot = sum(drc.values()) or 1
    dir_card = ""
    if drc_tot:
        segs = legend = ""
        for d in ["Open","Blind"]:
            cnt = drc.get(d, 0)
            if not cnt: continue
            c = DIR_COLORS[d]
            dp = pct(cnt, drc_tot)
            segs   += f'<div style="flex:{cnt};background:{c}"></div>'
            legend += (
                f'<span style="display:inline-flex;align-items:center;gap:3px;margin-right:10px">'
                f'<span style="width:10px;height:10px;border-radius:2px;background:{c}"></span>'
                f'<span style="font-size:10px;color:{c};font-weight:700">{d}: {cnt} ({dp}%)</span></span>'
            )
        dir_card = (
            f'<div style="background:#fff;border:1px solid #DEE2E6;border-radius:6px;overflow:hidden;margin-top:8px">'
            f'<div style="background:#F8F9FA;padding:4px 8px;border-bottom:1px solid #DEE2E6">'
            f'<span style="font-size:8.5px;font-weight:800;color:#14213D;text-transform:uppercase;letter-spacing:.05em">Attack Direction</span>'
            f'<span style="font-size:8px;color:#888;margin-left:6px">n={drc_tot}</span>'
            f'</div>'
            f'<div style="padding:10px 12px">'
            f'<div style="height:20px;display:flex;border-radius:4px;overflow:hidden;margin-bottom:8px">{segs}</div>'
            f'<div>{legend}</div>'
            f'</div></div>'
        )

    return f'<div style="display:flex;flex-direction:column;gap:0">{atk_card}{dir_card}</div>'

# ─────────────────────────────────────────────────────────────────────────────
# LINE CHART
# ─────────────────────────────────────────────────────────────────────────────

def _line_chart(title, matches):
    """2-line chart: matches = [(round, opp_short, own_wp, opp_wp), ...]"""
    n = len(matches)
    if n == 0:
        return ""

    pt_gap  = 42
    pad_l   = 32; pad_r = 32; pad_t = 28; pad_b = 38
    chart_h = 88
    chart_w = max((n - 1) * pt_gap, pt_gap) if n > 1 else pt_gap * 2
    svg_w   = pad_l + chart_w + pad_r
    svg_h   = pad_t + chart_h + pad_b

    def yp(wp): return pad_t + chart_h - round(chart_h * wp / 100)
    def xp(i):  return pad_l + (round(i * chart_w / (n - 1)) if n > 1 else chart_w // 2)

    # Y grid
    grid = ""
    for p in [0, 25, 50, 75, 90, 100]:
        y  = yp(p)
        sc = "#FCA5A5" if p == 90 else "#E5E7EB"
        lw = "0.8" if p != 90 else "0"
        grid += (
            f'<line x1="{pad_l}" y1="{y}" x2="{svg_w-pad_r}" y2="{y}" '
            f'stroke="{sc}" stroke-width="{lw}"/>'
            f'<text x="{pad_l-5}" y="{y+3}" text-anchor="end" font-size="7" fill="#888">{p}</text>'
        )

    # 90% target line
    gl_y = yp(90)
    guide = (
        f'<line x1="{pad_l}" y1="{gl_y}" x2="{svg_w-pad_r}" y2="{gl_y}" '
        f'stroke="#DC2626" stroke-width="1.3" stroke-dasharray="6,4"/>'
        f'<text x="{svg_w-pad_r+4}" y="{gl_y+3}" font-size="7" fill="#DC2626" font-weight="700">90%</text>'
    )

    # Polylines
    pts1 = " ".join(f"{xp(i)},{yp(m[2])}" for i, m in enumerate(matches))
    pts2 = " ".join(f"{xp(i)},{yp(m[3])}" for i, m in enumerate(matches))
    lines = (
        f'<polyline points="{pts1}" fill="none" stroke="#2563EB" stroke-width="2.2" stroke-linejoin="round" stroke-linecap="round"/>'
        f'<polyline points="{pts2}" fill="none" stroke="#F97316" stroke-width="1.8" stroke-dasharray="6,3" stroke-linejoin="round" stroke-linecap="round"/>'
    )

    # Dots + labels
    dots = ""
    for i, (rnd, opp, wp1, wp2) in enumerate(matches):
        x = xp(i)
        y1, y2 = yp(wp1), yp(wp2)
        same = abs(wp1 - wp2) <= 6

        # Label offsets to avoid collision
        off1 = -8  if not same else -14
        off2 =  12 if not same else  18

        dots += (
            f'<circle cx="{x}" cy="{y1}" r="3.5" fill="#2563EB" stroke="#fff" stroke-width="1.2"/>'
            f'<text x="{x}" y="{y1+off1}" text-anchor="middle" font-size="7" fill="#2563EB" font-weight="700">{wp1}%</text>'
            f'<circle cx="{x}" cy="{y2}" r="3" fill="#F97316" stroke="#fff" stroke-width="1.2"/>'
            f'<text x="{x}" y="{y2+off2}" text-anchor="middle" font-size="7" fill="#F97316">{wp2}%</text>'
            f'<text x="{x}" y="{svg_h-pad_b+13}" text-anchor="middle" font-size="7.5" fill="#333" font-weight="700">R{rnd}</text>'
            f'<text x="{x}" y="{svg_h-pad_b+24}" text-anchor="middle" font-size="6" fill="#888">{opp[:6]}</text>'
        )

    legend_html = (
        f'<div style="display:flex;align-items:center;gap:14px;padding:5px 10px;'
        f'background:#F8F9FA;border-bottom:1px solid #DEE2E6">'
        f'<span style="font-size:8.5px;font-weight:800;color:#14213D;text-transform:uppercase;letter-spacing:.05em">{title}</span>'
        f'<span style="display:flex;align-items:center;gap:4px">'
        f'<svg width="18" height="5"><line x1="0" y1="2.5" x2="18" y2="2.5" stroke="#2563EB" stroke-width="2.2"/></svg>'
        f'<span style="font-size:8px;color:#2563EB;font-weight:700">Own Ball</span></span>'
        f'<span style="display:flex;align-items:center;gap:4px">'
        f'<svg width="18" height="5"><line x1="0" y1="2.5" x2="18" y2="2.5" stroke="#F97316" stroke-width="1.8" stroke-dasharray="5,2"/></svg>'
        f'<span style="font-size:8px;color:#F97316;font-weight:700">Opp Ball</span></span>'
        f'<span style="display:flex;align-items:center;gap:4px">'
        f'<svg width="18" height="5"><line x1="0" y1="2.5" x2="18" y2="2.5" stroke="#DC2626" stroke-width="1.3" stroke-dasharray="5,3"/></svg>'
        f'<span style="font-size:8px;color:#DC2626;font-weight:700">Target 90%</span></span>'
        f'</div>'
    )

    return (
        f'<div style="background:#fff;border:1px solid #DEE2E6;border-radius:6px;overflow:hidden;margin-top:10px">'
        + legend_html
        + f'<div style="padding:6px 8px;overflow-x:auto">'
        f'<svg viewBox="0 0 {svg_w} {svg_h}" width="100%" '
        f'style="min-width:{svg_w}px;display:block">'
        + grid + guide + lines + dots
        + f'</svg></div></div>'
    )

# ─────────────────────────────────────────────────────────────────────────────
# PANEL / SECTION
# ─────────────────────────────────────────────────────────────────────────────

def build_panel(team_d, opp_d, label, header_color, chart_title, matches, opp_results=None, opp_total=None):
    col1 = result_col(team_d, opp_d, opp_results=opp_results, opp_total=opp_total)
    col2 = stability_col(team_d["stability"], opp_d["stability"])
    col3 = attack_col(team_d)
    chart = _line_chart(chart_title, matches)

    grid = (
        f'<div style="display:grid;grid-template-columns:1.2fr 0.8fr 0.9fr;gap:10px;margin-bottom:10px">'
        + col1 + col2 + col3
        + f'</div>'
    )

    return (
        f'<div style="background:#FAFAFA;border:1px solid #DEE2E6;border-radius:8px;padding:12px 14px;margin-bottom:12px">'
        f'<div style="display:flex;align-items:center;gap:8px;padding:6px 10px;background:{header_color}18;'
        f'border-radius:5px;border-left:4px solid {header_color};margin-bottom:12px">'
        f'<span style="font-family:Oswald,sans-serif;font-size:13px;font-weight:700;'
        f'letter-spacing:.08em;text-transform:uppercase;color:{header_color}">⬛ {label}</span>'
        f'</div>'
        + grid + chart
        + f'</div>'
    )


def build_section(abbr):
    opp_d = TEAM_SCRUM_DATA[abbr]

    sp_opp_results, sp_opp_total = _SPEARS_OPP_SCRUM
    scout_opp = _SCOUT_OPP_SCRUM.get(abbr, {})
    scout_opp_results = scout_opp.get("results", {})
    scout_opp_total   = scout_opp.get("total", 0)

    sp_panel = build_panel(
        team_d       = SPEARS_SCRUM,
        opp_d        = opp_d,
        label        = "Kubota Spears",
        header_color = "#F97316",
        chart_title  = "Scrum by Match — Spears Own Ball (全21試合)",
        matches      = SPEARS_SCRUM["matches"],
        opp_results  = sp_opp_results,
        opp_total    = sp_opp_total,
    )

    divider = (
        f'<div style="display:flex;align-items:center;gap:8px;margin:14px 0">'
        f'<div style="flex:1;height:2px;background:linear-gradient(to right,#E9ECEF,#ADB5BD)"></div>'
        f'<span style="font-size:8px;font-weight:700;color:#6B7280;text-transform:uppercase;letter-spacing:.1em">vs {opp_d["name"]}</span>'
        f'<div style="flex:1;height:2px;background:linear-gradient(to left,#E9ECEF,#ADB5BD)"></div>'
        f'</div>'
    )

    opp_panel = build_panel(
        team_d       = opp_d,
        opp_d        = SPEARS_SCRUM,
        label        = opp_d["name"],
        header_color = "#10B981",
        chart_title  = f'Scrum by Match — {opp_d["name"]} 全シーズン',
        matches      = opp_d["matches"],
        opp_results  = scout_opp_results,
        opp_total    = scout_opp_total,
    )

    return (
        f'<div id="sc" class="section">\n'
        f'  <div style="padding:0 2px">\n'
        f'    {sp_panel}\n'
        f'    {divider}\n'
        f'    {opp_panel}\n'
        f'  </div>\n'
        f'</div>\n'
    )

# ─────────────────────────────────────────────────────────────────────────────
# FILE PROCESSOR
# ─────────────────────────────────────────────────────────────────────────────

def process_file(fpath, abbr):
    with open(fpath, encoding="utf-8") as f:
        content = f.read()

    new_sc = build_section(abbr)
    SC = '<div id="sc" class="section">'
    SP = '<div id="sp" class="section">'
    LO = '<div id="lo" class="section">'

    if SC in content:
        sc_i = content.index(SC)
        sp_i = content.index(SP, sc_i)
        content = content[:sc_i] + new_sc + content[sp_i:]
    elif LO in content and SP in content:
        lo_i = content.index(LO)
        sp_i = content.index(SP, lo_i)
        content = content[:sp_i] + new_sc + content[sp_i:]
    else:
        return False

    if "showSection('sc'" not in content:
        lo_btn = ">Lineout</button>"
        if lo_btn in content:
            idx = content.index(lo_btn) + len(lo_btn)
            nav = '<button class="nav-btn" style="color:#6366f1" onclick="showSection(\'sc\',this)">Scrum</button>'
            content = content[:idx] + "\n  " + nav + content[idx:]

    with open(fpath, "w", encoding="utf-8") as f:
        f.write(content)
    return True


def main():
    done = 0
    for fname in sorted(os.listdir(BIOUT_DIR)):
        if not (fname.startswith("scout_Spears_vs_") and fname.endswith(".html")):
            continue
        m = re.match(r"scout_Spears_vs_(.+)_R\d+\.html", fname)
        if not m or m.group(1) not in TEAM_SCRUM_DATA:
            continue
        fpath = os.path.join(BIOUT_DIR, fname)
        if process_file(fpath, m.group(1)):
            print(f"  ✓ {fname}")
            done += 1
        else:
            print(f"  ✗ SKIP {fname}")
    print(f"\nDone: {done} files updated.")


if __name__ == "__main__":
    main()
