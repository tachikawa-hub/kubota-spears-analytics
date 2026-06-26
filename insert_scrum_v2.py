#!/usr/bin/env python3
"""insert_scrum_v2.py — Scrum section full redesign
Changes vs v1:
  - Result: table format with color-coded rows (no bar chart)
  - Stability: two SVG donut pie charts (Own/Opp), Wheel removed
  - Attack Option: table with proper names (SH Pass / SH Run / Pick & Go / No.8 Pass)
  - Scrum by Match: bar chart (won rate) + 90% target dashed line, full width
"""
import os, re, math

# ── Data ───────────────────────────────────────────────────────────────────────

SPEARS_SCRUM = {
    "name": "Kubota Spears",
    "own":  [158, 138],
    "results": {"WonOut":99,"WonPen":31,"WonFK":8,"Reset":12,"LostPen":4,"LostFK":2,"LostOut":2,"LostRev":0},
    "stability": [33, 114, 11],
    "attack":    {"Pass":74,"Run":14,"Pick":15,"No8Pass":8},
    "direction": {"Left":45,"Right":47,"Blind":20},
    "matches": [
        ( 1,"Steelers",  2, 2),
        ( 2,"BlackRams", 4, 3),
        ( 3,"Sungoliath",4, 3),
        ( 4,"Heat",      8, 8),
        ( 5,"Verblitz", 10, 8),
        ( 6,"BraveLupus",7, 6),
        ( 7,"D-Rocks",  12,11),
        ( 8,"BlueRevs",  6, 6),
        ( 9,"Dynaboars", 5, 3),
        (10,"Eagles",   16,11),
        (11,"WildKnights",9,8),
        (12,"D-Rocks",   4, 3),
        (13,"BraveLupus",8, 8),
        (14,"Verblitz",  7, 7),
        (15,"Sungoliath",5, 5),
        (16,"Heat",     15,15),
        (17,"BlackRams",11, 9),
        (18,"Steelers",  9, 7),
        (19,"BraveLupus",6, 6),
        (20,"WildKnights",4,3),
        (22,"Steelers",  6, 6),
    ],
}

TEAM_SCRUM_DATA = {
    "Steelers": {
        "name":"Kobelco Kobe Steelers",
        "own":[19,13],
        "results":{"WonOut":6,"WonPen":4,"WonFK":3,"Reset":4,"LostPen":2,"LostFK":0,"LostOut":0,"LostRev":0},
        "stability":[2,16,1],
        "attack":{"Pass":5,"Run":1,"Pick":0,"No8Pass":0},
        "direction":{"Left":2,"Right":3,"Blind":1},
        "matches":[(1,2,2,4,3),(18,9,7,7,4),(22,6,6,8,6)],
    },
    "BlackRams": {
        "name":"BlackRams Tokyo",
        "own":[18,17],
        "results":{"WonOut":13,"WonPen":2,"WonFK":2,"Reset":0,"LostPen":0,"LostFK":1,"LostOut":0,"LostRev":0},
        "stability":[2,13,3],
        "attack":{"Pass":9,"Run":1,"Pick":1,"No8Pass":2},
        "direction":{"Left":8,"Right":4,"Blind":2},
        "matches":[(2,4,3,8,8),(17,11,9,10,9)],
    },
    "BraveLupus": {
        "name":"Toshiba Brave Lupus Tokyo",
        "own":[30,24],
        "results":{"WonOut":24,"WonPen":0,"WonFK":0,"Reset":3,"LostPen":3,"LostFK":0,"LostOut":0,"LostRev":0},
        "stability":[1,25,4],
        "attack":{"Pass":21,"Run":2,"Pick":0,"No8Pass":1},
        "direction":{"Left":18,"Right":5,"Blind":1},
        "matches":[(6,7,6,10,9),(13,8,8,8,7),(19,6,6,12,8)],
    },
    "BlueRevs": {
        "name":"Shizuoka BlueRevs",
        "own":[11,10],
        "results":{"WonOut":6,"WonPen":3,"WonFK":1,"Reset":1,"LostPen":0,"LostFK":0,"LostOut":0,"LostRev":0},
        "stability":[1,10,0],
        "attack":{"Pass":4,"Run":2,"Pick":0,"No8Pass":0},
        "direction":{"Left":3,"Right":1,"Blind":2},
        "matches":[(8,6,6,11,10)],
    },
    "Dynaboars": {
        "name":"Mitsubishi Sagamihara Dynaboars",
        "own":[8,6],
        "results":{"WonOut":4,"WonPen":2,"WonFK":0,"Reset":0,"LostPen":1,"LostFK":1,"LostOut":0,"LostRev":0},
        "stability":[1,7,0],
        "attack":{"Pass":5,"Run":0,"Pick":0,"No8Pass":0},
        "direction":{"Left":2,"Right":3,"Blind":0},
        "matches":[(9,5,3,8,6)],
    },
    "Eagles": {
        "name":"Yokohama Canon Eagles",
        "own":[9,9],
        "results":{"WonOut":6,"WonPen":2,"WonFK":1,"Reset":0,"LostPen":0,"LostFK":0,"LostOut":0,"LostRev":0},
        "stability":[0,7,2],
        "attack":{"Pass":6,"Run":0,"Pick":0,"No8Pass":1},
        "direction":{"Left":3,"Right":3,"Blind":1},
        "matches":[(10,16,11,9,9)],
    },
    "D-Rocks": {
        "name":"Urayasu D-Rocks",
        "own":[13,11],
        "results":{"WonOut":11,"WonPen":0,"WonFK":0,"Reset":0,"LostPen":2,"LostFK":0,"LostOut":0,"LostRev":0},
        "stability":[0,8,5],
        "attack":{"Pass":8,"Run":0,"Pick":2,"No8Pass":1},
        "direction":{"Left":5,"Right":5,"Blind":1},
        "matches":[(7,12,11,5,3),(12,4,3,8,8)],
    },
    "WildKnights": {
        "name":"Saitama Wild Knights",
        "own":[16,13],
        "results":{"WonOut":10,"WonPen":1,"WonFK":2,"Reset":1,"LostPen":2,"LostFK":0,"LostOut":0,"LostRev":0},
        "stability":[1,14,1],
        "attack":{"Pass":9,"Run":0,"Pick":1,"No8Pass":0},
        "direction":{"Left":6,"Right":3,"Blind":1},
        "matches":[(11,9,8,8,6),(20,4,3,8,7)],
    },
    "Heat": {
        "name":"Mie Honda Heat",
        "own":[16,14],
        "results":{"WonOut":13,"WonPen":1,"WonFK":0,"Reset":1,"LostPen":1,"LostFK":0,"LostOut":0,"LostRev":0},
        "stability":[1,15,0],
        "attack":{"Pass":6,"Run":1,"Pick":3,"No8Pass":2},
        "direction":{"Left":5,"Right":6,"Blind":1},
        "matches":[(4,8,8,10,9),(16,15,15,6,5)],
    },
    "Sungoliath": {
        "name":"Tokyo Sungoliath",
        "own":[14,9],
        "results":{"WonOut":8,"WonPen":0,"WonFK":1,"Reset":3,"LostPen":2,"LostFK":0,"LostOut":0,"LostRev":0},
        "stability":[0,13,1],
        "attack":{"Pass":7,"Run":0,"Pick":0,"No8Pass":1},
        "direction":{"Left":4,"Right":4,"Blind":0},
        "matches":[(3,4,3,9,4),(15,5,5,5,5)],
    },
    "Verblitz": {
        "name":"Toyota Verblitz",
        "own":[22,22],
        "results":{"WonOut":19,"WonPen":1,"WonFK":2,"Reset":0,"LostPen":0,"LostFK":0,"LostOut":0,"LostRev":0},
        "stability":[1,19,2],
        "attack":{"Pass":16,"Run":1,"Pick":1,"No8Pass":0},
        "direction":{"Left":6,"Right":11,"Blind":2},
        "matches":[(5,10,8,7,7),(14,7,7,15,15)],
    },
}

SCOUT_DIR = "/Users/ktachikawa/Desktop/kubota-spears-analytics"
BIOUT_DIR = "/Users/ktachikawa/Desktop/BIoutput"

# ── Helpers ────────────────────────────────────────────────────────────────────

def pct(n, d): return round(100 * n / d) if d else 0

def won_color(wp):
    return "#16a34a" if wp >= 90 else "#2563eb" if wp >= 75 else "#d97706"

ATK_NAMES   = {"Pass":"SH Pass","Run":"SH Run","Pick":"Pick & Go","No8Pass":"No.8 Pass"}
ATK_COLORS  = {"Pass":"#2563EB","Run":"#16A34A","Pick":"#D97706","No8Pass":"#7C3AED"}
DIR_COLORS  = {"Left":"#2563EB","Right":"#D97706","Blind":"#7C3AED"}

RESULT_ROWS = [
    ("WonOut",  "Won Outright",          "#16a34a", "#f0fdf4"),
    ("WonPen",  "Penalty Won",           "#22c55e", "#f0fdf4"),
    ("WonFK",   "Free Kick Won",         "#4ade80", "#f0fdf4"),
    ("Reset",   "Reset",                 "#6b7280", "#f9fafb"),
    ("LostOut", "Lost Outright",         "#dc2626", "#fff1f2"),
    ("LostFK",  "Lost Free Kick",        "#ef4444", "#fff1f2"),
    ("LostPen", "Lost Penalty Conceded", "#f87171", "#fff1f2"),
    ("LostRev", "Lost Reverse",          "#fca5a5", "#fff1f2"),
]

# ── Column builders ─────────────────────────────────────────────────────────────

def result_table_block(r, tot, won, section_label, color):
    wp = pct(won, tot)
    wc = won_color(wp)

    rows_html = ""
    for key, display, row_color, bg in RESULT_ROWS:
        cnt = r.get(key, 0)
        if cnt == 0:
            continue
        p = pct(cnt, tot)
        rows_html += (
            f'<tr style="background:{bg}">'
            f'<td style="padding:4px 6px;font-size:9px;color:{row_color};font-weight:700;'
            f'border-left:3px solid {row_color}">{display}</td>'
            f'<td style="padding:4px 6px;font-size:9px;color:#333;text-align:right;font-weight:700">{cnt}</td>'
            f'<td style="padding:4px 6px;font-size:9px;color:#888;text-align:right">{p}%</td>'
            f'</tr>'
        )

    total_html = (
        f'<tr style="background:#F8F9FA;border-top:2px solid #DEE2E6">'
        f'<td style="padding:4px 6px;font-size:9px;font-weight:800;color:#14213D">TOTAL</td>'
        f'<td style="padding:4px 6px;font-size:9px;font-weight:800;color:#14213D;text-align:right">{tot}</td>'
        f'<td style="padding:4px 6px;font-size:9px;color:#888;text-align:right">100%</td>'
        f'</tr>'
    )

    return (
        f'<div style="background:#fff;border:1px solid #DEE2E6;border-radius:6px;overflow:hidden">'
        f'<div style="background:#F8F9FA;padding:4px 8px;border-bottom:1px solid #DEE2E6;'
        f'display:flex;align-items:center;justify-content:space-between">'
        f'<span style="font-size:8.5px;font-weight:800;color:#14213D;text-transform:uppercase;'
        f'letter-spacing:.05em">{section_label}</span>'
        f'<span style="font-family:Oswald,sans-serif;font-size:20px;font-weight:700;color:{wc}">'
        f'{wp}% <span style="font-size:9px;color:#888;font-family:sans-serif">Won</span></span>'
        f'</div>'
        f'<table style="width:100%;border-collapse:collapse">'
        f'<thead><tr style="background:#F8F9FA">'
        f'<th style="padding:3px 6px;font-size:7.5px;color:#555;text-align:left;'
        f'font-weight:700;border-bottom:1px solid #DEE2E6">Result</th>'
        f'<th style="padding:3px 6px;font-size:7.5px;color:#555;text-align:right;'
        f'font-weight:700;border-bottom:1px solid #DEE2E6">n</th>'
        f'<th style="padding:3px 6px;font-size:7.5px;color:#555;text-align:right;'
        f'font-weight:700;border-bottom:1px solid #DEE2E6">%</th>'
        f'</tr></thead>'
        f'<tbody>{rows_html}{total_html}</tbody>'
        f'</table></div>'
    )


def result_col(team_scrum, opp_scrum):
    own_block = result_table_block(
        team_scrum["results"], team_scrum["own"][0], team_scrum["own"][1],
        "Own Ball Scrum Result", "#F97316"
    )
    opp_block = result_table_block(
        opp_scrum["results"], opp_scrum["own"][0], opp_scrum["own"][1],
        "Opp Ball Won Rate", "#6B7280"
    )
    return (
        f'<div style="display:flex;flex-direction:column;gap:8px">'
        + own_block + opp_block
        + f'</div>'
    )


def _donut_svg(pos, neu, neg, title):
    total = pos + neu + neg or 1
    pos_p = pct(pos, total)
    neu_p = pct(neu, total)
    neg_p = pct(neg, total)

    cx, cy = 50, 52
    r_out, r_in = 38, 22
    segs = [(pos, "#16A34A"), (neu, "#9CA3AF"), (neg, "#DC2626")]

    def arc_path(start_deg, sweep_deg, ro, ri):
        if sweep_deg >= 360:
            sweep_deg = 359.99
        s = math.radians(start_deg - 90)
        e = math.radians(start_deg + sweep_deg - 90)
        lg = 1 if sweep_deg > 180 else 0
        x1o = cx + ro * math.cos(s); y1o = cy + ro * math.sin(s)
        x2o = cx + ro * math.cos(e); y2o = cy + ro * math.sin(e)
        x1i = cx + ri * math.cos(e); y1i = cy + ri * math.sin(e)
        x2i = cx + ri * math.cos(s); y2i = cy + ri * math.sin(s)
        return (f"M {x1o:.2f} {y1o:.2f} A {ro} {ro} 0 {lg} 1 {x2o:.2f} {y2o:.2f} "
                f"L {x1i:.2f} {y1i:.2f} A {ri} {ri} 0 {lg} 0 {x2i:.2f} {y2i:.2f} Z")

    angle = 0
    paths = ""
    for val, color in segs:
        if val == 0:
            continue
        sweep = 360 * val / total
        paths += f'<path d="{arc_path(angle, sweep, r_out, r_in)}" fill="{color}"/>'
        angle += sweep

    center_txt = (
        f'<text x="{cx}" y="{cy-5}" text-anchor="middle" font-size="16" '
        f'font-weight="700" fill="#16A34A">{pos_p}%</text>'
        f'<text x="{cx}" y="{cy+9}" text-anchor="middle" font-size="7.5" fill="#555">Positive</text>'
    )

    legend = (
        f'<text x="{cx}" y="{cy+30}" text-anchor="middle" font-size="7" fill="#16A34A" font-weight="700">'
        f'Pos {pos} ({pos_p}%)</text>'
        f'<text x="{cx}" y="{cy+41}" text-anchor="middle" font-size="7" fill="#6B7280" font-weight="700">'
        f'Neu {neu} ({neu_p}%)</text>'
        f'<text x="{cx}" y="{cy+52}" text-anchor="middle" font-size="7" fill="#DC2626" font-weight="700">'
        f'Neg {neg} ({neg_p}%)</text>'
    )

    title_txt = (
        f'<text x="{cx}" y="11" text-anchor="middle" font-size="8" '
        f'font-weight="800" fill="#14213D">{title}</text>'
    )

    return (
        f'<svg viewBox="0 0 100 115" width="100" height="115" style="display:block">'
        + title_txt + paths + center_txt + legend
        + f'</svg>'
    )


def stability_col(own_stab, opp_stab):
    own_svg = _donut_svg(*own_stab, "Own Ball")
    opp_svg = _donut_svg(*opp_stab, "Opp Ball")
    return (
        f'<div style="background:#fff;border:1px solid #DEE2E6;border-radius:6px;overflow:hidden">'
        f'<div style="background:#F8F9FA;padding:4px 8px;border-bottom:1px solid #DEE2E6">'
        f'<span style="font-size:8.5px;font-weight:800;color:#14213D;text-transform:uppercase;'
        f'letter-spacing:.05em">Stability</span></div>'
        f'<div style="padding:10px 6px;display:flex;justify-content:space-around;align-items:center">'
        + own_svg + opp_svg
        + f'</div></div>'
    )


def attack_col(team_scrum):
    atk = team_scrum["attack"]
    atk_tot = sum(atk.values()) or 1

    rows_html = ""
    for key in ["Pass", "Run", "Pick", "No8Pass"]:
        cnt = atk.get(key, 0)
        if not cnt:
            continue
        name  = ATK_NAMES[key]
        color = ATK_COLORS[key]
        p     = pct(cnt, atk_tot)
        rows_html += (
            f'<tr>'
            f'<td style="padding:4px 6px;font-size:9px;color:{color};font-weight:700;'
            f'border-left:3px solid {color}">{name}</td>'
            f'<td style="padding:4px 6px;font-size:9px;color:#333;text-align:right;font-weight:700">{cnt}</td>'
            f'<td style="padding:4px 6px;font-size:9px;color:#888;text-align:right">{p}%</td>'
            f'</tr>'
        )

    total_row = (
        f'<tr style="background:#F8F9FA;border-top:2px solid #DEE2E6">'
        f'<td style="padding:4px 6px;font-size:9px;font-weight:800;color:#14213D">TOTAL</td>'
        f'<td style="padding:4px 6px;font-size:9px;font-weight:800;color:#14213D;text-align:right">'
        f'{sum(atk.values())}</td>'
        f'<td style="padding:4px 6px;font-size:9px;color:#888;text-align:right">100%</td>'
        f'</tr>'
    )

    atk_table = (
        f'<div style="background:#fff;border:1px solid #DEE2E6;border-radius:6px;overflow:hidden">'
        f'<div style="background:#F8F9FA;padding:4px 8px;border-bottom:1px solid #DEE2E6">'
        f'<span style="font-size:8.5px;font-weight:800;color:#14213D;text-transform:uppercase;'
        f'letter-spacing:.05em">Attack Option</span></div>'
        f'<table style="width:100%;border-collapse:collapse">'
        f'<thead><tr style="background:#F8F9FA">'
        f'<th style="padding:3px 6px;font-size:7.5px;color:#555;text-align:left;'
        f'font-weight:700;border-bottom:1px solid #DEE2E6">Option</th>'
        f'<th style="padding:3px 6px;font-size:7.5px;color:#555;text-align:right;'
        f'font-weight:700;border-bottom:1px solid #DEE2E6">n</th>'
        f'<th style="padding:3px 6px;font-size:7.5px;color:#555;text-align:right;'
        f'font-weight:700;border-bottom:1px solid #DEE2E6">%</th>'
        f'</tr></thead>'
        f'<tbody>{rows_html}{total_row}</tbody>'
        f'</table></div>'
    )

    drc = team_scrum["direction"]
    drc_tot = sum(drc.values()) or 1
    dir_segs = dir_legend = ""
    for d in ["Left", "Right", "Blind"]:
        cnt = drc.get(d, 0)
        if not cnt:
            continue
        c = DIR_COLORS[d]
        dp = pct(cnt, drc_tot)
        dir_segs   += f'<div style="flex:{cnt};background:{c}" title="{d}: {cnt}"></div>'
        dir_legend += (
            f'<span style="display:inline-flex;align-items:center;gap:2px;margin-right:8px">'
            f'<span style="width:7px;height:7px;border-radius:1px;background:{c}"></span>'
            f'<span style="font-size:7px;color:{c};font-weight:700">{d} {cnt} ({dp}%)</span></span>'
        )

    dir_block = ""
    if dir_segs:
        dir_block = (
            f'<div style="background:#fff;border:1px solid #DEE2E6;border-radius:6px;'
            f'overflow:hidden;margin-top:8px">'
            f'<div style="background:#F8F9FA;padding:4px 8px;border-bottom:1px solid #DEE2E6">'
            f'<span style="font-size:8.5px;font-weight:800;color:#14213D;text-transform:uppercase;'
            f'letter-spacing:.05em">Attack Direction</span></div>'
            f'<div style="padding:8px 10px">'
            f'<div style="height:14px;display:flex;border-radius:3px;overflow:hidden;margin-bottom:6px">'
            f'{dir_segs}</div>'
            f'<div style="display:flex;flex-wrap:wrap">{dir_legend}</div>'
            f'</div></div>'
        )

    return (
        f'<div style="display:flex;flex-direction:column;gap:0">'
        + atk_table + dir_block
        + f'</div>'
    )


# ── Match charts ──────────────────────────────────────────────────────────────

def match_chart_spears():
    matches = SPEARS_SCRUM["matches"]
    n = len(matches)
    bar_w = 34; gap = 3
    pad_l = 28; pad_r = 30; pad_t = 18; pad_b = 32
    chart_h = 80
    svg_w = pad_l + n * (bar_w + gap) - gap + pad_r
    svg_h = pad_t + chart_h + pad_b

    grid = ""
    for p in [0, 25, 50, 75, 90, 100]:
        y = pad_t + chart_h - round(chart_h * p / 100)
        lw = "1" if p == 90 else "0.5"
        sc = "#E5E7EB" if p != 90 else "#FCA5A5"
        grid += (
            f'<line x1="{pad_l}" y1="{y}" x2="{svg_w-pad_r}" y2="{y}" '
            f'stroke="{sc}" stroke-width="{lw}"/>'
            f'<text x="{pad_l-4}" y="{y+3}" text-anchor="end" font-size="6" fill="#888">{p}</text>'
        )

    gl_y = pad_t + chart_h - round(chart_h * 90 / 100)
    guide = (
        f'<line x1="{pad_l}" y1="{gl_y}" x2="{svg_w-pad_r}" y2="{gl_y}" '
        f'stroke="#DC2626" stroke-width="1.2" stroke-dasharray="5,3"/>'
        f'<text x="{svg_w-pad_r+3}" y="{gl_y+3}" font-size="6.5" '
        f'fill="#DC2626" font-weight="700">90%</text>'
    )

    bars = ""
    for i, (rnd, opp, tot, won) in enumerate(matches):
        wp    = pct(won, tot)
        bar_h = max(3, round(chart_h * wp / 100))
        x     = pad_l + i * (bar_w + gap)
        y     = pad_t + chart_h - bar_h
        c     = won_color(wp)
        bars += (
            f'<rect x="{x}" y="{y}" width="{bar_w}" height="{bar_h}" fill="{c}" rx="2" opacity="0.85"/>'
            f'<text x="{x+bar_w//2}" y="{y-3}" text-anchor="middle" font-size="7" '
            f'fill="{c}" font-weight="700">{wp}%</text>'
            f'<text x="{x+bar_w//2}" y="{pad_t+chart_h+11}" text-anchor="middle" '
            f'font-size="6.5" fill="#333">R{rnd}</text>'
            f'<text x="{x+bar_w//2}" y="{pad_t+chart_h+21}" text-anchor="middle" '
            f'font-size="5.5" fill="#888">{opp[:5]}</text>'
        )

    legend = (
        f'<rect x="{pad_l}" y="5" width="10" height="7" fill="#2563EB" rx="1" opacity="0.85"/>'
        f'<text x="{pad_l+13}" y="12" font-size="6.5" fill="#555">Won Rate %</text>'
        f'<line x1="{pad_l+60}" y1="8.5" x2="{pad_l+75}" y2="8.5" '
        f'stroke="#DC2626" stroke-width="1.2" stroke-dasharray="4,3"/>'
        f'<text x="{pad_l+78}" y="12" font-size="6.5" fill="#DC2626">Target 90%</text>'
    )

    return (
        f'<div style="background:#fff;border:1px solid #DEE2E6;border-radius:6px;'
        f'overflow:hidden;margin-top:10px">'
        f'<div style="background:#F8F9FA;padding:5px 8px;border-bottom:1px solid #DEE2E6">'
        f'<span style="font-size:8.5px;font-weight:800;color:#14213D;text-transform:uppercase;'
        f'letter-spacing:.05em">Scrum by Match — Spears Own Ball (全21試合)</span></div>'
        f'<div style="padding:6px 8px;overflow-x:auto">'
        f'<svg viewBox="0 0 {svg_w} {svg_h}" width="100%" '
        f'style="min-width:{svg_w}px;display:block;max-width:100%">'
        + legend + grid + guide + bars
        + f'</svg></div></div>'
    )


def match_chart_opp(opp_abbr, matches):
    if not matches:
        return ""

    n       = len(matches)
    grp_w   = 70; gap = 14
    bar_w   = 28
    pad_l   = 32; pad_r = 36; pad_t = 18; pad_b = 36
    chart_h = 80
    svg_w   = pad_l + n * (grp_w + gap) - gap + pad_r
    svg_h   = pad_t + chart_h + pad_b

    grid = ""
    for p in [0, 25, 50, 75, 90, 100]:
        y = pad_t + chart_h - round(chart_h * p / 100)
        sc = "#FCA5A5" if p == 90 else "#E5E7EB"
        lw = "1" if p == 90 else "0.5"
        grid += (
            f'<line x1="{pad_l}" y1="{y}" x2="{svg_w-pad_r}" y2="{y}" '
            f'stroke="{sc}" stroke-width="{lw}"/>'
            f'<text x="{pad_l-4}" y="{y+3}" text-anchor="end" font-size="6" fill="#888">{p}</text>'
        )

    gl_y = pad_t + chart_h - round(chart_h * 90 / 100)
    guide = (
        f'<line x1="{pad_l}" y1="{gl_y}" x2="{svg_w-pad_r}" y2="{gl_y}" '
        f'stroke="#DC2626" stroke-width="1.2" stroke-dasharray="5,3"/>'
        f'<text x="{svg_w-pad_r+3}" y="{gl_y+3}" font-size="6.5" fill="#DC2626" font-weight="700">90%</text>'
    )

    bars = ""
    for i, (rnd, sp_tot, sp_won, opp_tot, opp_won) in enumerate(matches):
        sp_wp  = pct(sp_won, sp_tot)
        opp_wp = pct(opp_won, opp_tot)
        gx = pad_l + i * (grp_w + gap)

        for wp, color, bx_offset, lbl in [
            (sp_wp,  "#2563EB", 0,          "Spears"),
            (opp_wp, "#10B981", bar_w + 14, opp_abbr[:5]),
        ]:
            bh = max(3, round(chart_h * wp / 100))
            bx = gx + bx_offset
            by = pad_t + chart_h - bh
            bars += (
                f'<rect x="{bx}" y="{by}" width="{bar_w}" height="{bh}" '
                f'fill="{color}" rx="2" opacity="0.85"/>'
                f'<text x="{bx+bar_w//2}" y="{by-3}" text-anchor="middle" '
                f'font-size="7.5" fill="{color}" font-weight="700">{wp}%</text>'
                f'<text x="{bx+bar_w//2}" y="{pad_t+chart_h+22}" text-anchor="middle" '
                f'font-size="6" fill="{color}" font-weight="700">{lbl}</text>'
            )

        mid = gx + grp_w // 2
        bars += (
            f'<text x="{mid}" y="{pad_t+chart_h+11}" text-anchor="middle" '
            f'font-size="8" fill="#333" font-weight="700">R{rnd}</text>'
        )

    legend = (
        f'<rect x="{pad_l}" y="5" width="10" height="7" fill="#2563EB" rx="1" opacity="0.85"/>'
        f'<text x="{pad_l+13}" y="12" font-size="6.5" fill="#2563EB" font-weight="700">Spears</text>'
        f'<rect x="{pad_l+55}" y="5" width="10" height="7" fill="#10B981" rx="1" opacity="0.85"/>'
        f'<text x="{pad_l+68}" y="12" font-size="6.5" fill="#10B981" font-weight="700">{opp_abbr}</text>'
        f'<line x1="{pad_l+100}" y1="8.5" x2="{pad_l+115}" y2="8.5" '
        f'stroke="#DC2626" stroke-width="1.2" stroke-dasharray="4,3"/>'
        f'<text x="{pad_l+118}" y="12" font-size="6.5" fill="#DC2626">Target 90%</text>'
    )

    return (
        f'<div style="background:#fff;border:1px solid #DEE2E6;border-radius:6px;'
        f'overflow:hidden;margin-top:10px">'
        f'<div style="background:#F8F9FA;padding:5px 8px;border-bottom:1px solid #DEE2E6">'
        f'<span style="font-size:8.5px;font-weight:800;color:#14213D;text-transform:uppercase;'
        f'letter-spacing:.05em">Scrum by Match</span></div>'
        f'<div style="padding:6px 8px;overflow-x:auto">'
        f'<svg viewBox="0 0 {svg_w} {svg_h}" width="100%" '
        f'style="min-width:{svg_w}px;display:block;max-width:100%">'
        + legend + grid + guide + bars
        + f'</svg></div></div>'
    )


# ── Panel / Section builder ───────────────────────────────────────────────────

def build_panel(team_scrum, opp_scrum, label, header_color, match_section=None):
    col1 = result_col(team_scrum, opp_scrum)
    col2 = stability_col(team_scrum["stability"], opp_scrum["stability"])
    col3 = attack_col(team_scrum)

    grid = (
        f'<div style="display:grid;grid-template-columns:1.15fr 0.75fr 0.85fr;gap:10px;margin-bottom:10px">'
        + col1 + col2 + col3
        + f'</div>'
    )

    return (
        f'<div style="background:#FAFAFA;border:1px solid #DEE2E6;border-radius:8px;'
        f'padding:12px 14px;margin-bottom:12px">'
        f'<div style="display:flex;align-items:center;gap:8px;padding:6px 10px;'
        f'background:{header_color}18;border-radius:5px;border-left:4px solid {header_color};margin-bottom:12px">'
        f'<span style="font-family:Oswald,sans-serif;font-size:13px;font-weight:700;'
        f'letter-spacing:.08em;text-transform:uppercase;color:{header_color}">⬛ {label}</span>'
        f'</div>'
        + grid
        + (match_section or "")
        + f'</div>'
    )


def build_section(abbr, opp):
    opp_d = TEAM_SCRUM_DATA[abbr]

    sp_panel = build_panel(
        team_scrum    = SPEARS_SCRUM,
        opp_scrum     = opp_d,
        label         = "Kubota Spears",
        header_color  = "#F97316",
        match_section = match_chart_spears(),
    )

    divider = (
        f'<div style="display:flex;align-items:center;gap:8px;margin:14px 0">'
        f'<div style="flex:1;height:2px;background:linear-gradient(to right,#E9ECEF,#ADB5BD)"></div>'
        f'<span style="font-size:8px;font-weight:700;color:#6B7280;text-transform:uppercase;'
        f'letter-spacing:.1em">vs {opp_d["name"]}</span>'
        f'<div style="flex:1;height:2px;background:linear-gradient(to left,#E9ECEF,#ADB5BD)"></div>'
        f'</div>'
    )

    opp_panel = build_panel(
        team_scrum    = opp_d,
        opp_scrum     = SPEARS_SCRUM,
        label         = opp_d["name"],
        header_color  = "#10B981",
        match_section = match_chart_opp(abbr, opp_d["matches"]),
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


# ── File processor ────────────────────────────────────────────────────────────

def process_file(fpath, abbr):
    with open(fpath, encoding="utf-8") as f:
        content = f.read()

    new_sc = build_section(abbr, TEAM_SCRUM_DATA[abbr])

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
    for d in [BIOUT_DIR, SCOUT_DIR]:
        if not os.path.isdir(d):
            continue
        for fname in sorted(os.listdir(d)):
            if not (fname.startswith("scout_Spears_vs_") and fname.endswith(".html")):
                continue
            m = re.match(r"scout_Spears_vs_(.+)_R\d+\.html", fname)
            if not m or m.group(1) not in TEAM_SCRUM_DATA:
                continue
            fpath = os.path.join(d, fname)
            if process_file(fpath, m.group(1)):
                print(f"  ✓ {fname}")
                done += 1
            else:
                print(f"  ✗ SKIP {fname}")
    print(f"\nDone: {done} files updated.")


if __name__ == "__main__":
    main()
