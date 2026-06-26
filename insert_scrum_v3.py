import os
import re
import math

BIOUT_DIR = "/Users/ktachikawa/Desktop/BIoutput"

SPEARS_SCRUM = {
    "name": "Kubota Spears",
    "own":  [158, 138],
    "results": {"WonOut":99,"WonPen":31,"WonFK":8,"Reset":12,"LostPen":4,"LostFK":2,"LostOut":2},
    "stability": [33, 114, 11],
    "attack": {"Scrum Half Pass":74,"Scrum Half Run":14,"No 8 Pick Up":15,"No 8 Pass":8,"Scrum Half Kick":1},
    "direction": {"Open":92,"Blind":20},
    "matches": [
        ( 1,"Steelers",  2, 2),( 2,"BlackRams", 4, 3),( 3,"Sungoliath",4, 3),
        ( 4,"Heat",      8, 8),( 5,"Verblitz", 10, 8),( 6,"BraveLupus",7, 6),
        ( 7,"D-Rocks",  12,11),( 8,"BlueRevs",  6, 6),( 9,"Dynaboars", 5, 3),
        (10,"Eagles",   16,11),(11,"WildKnights",9,8),(12,"D-Rocks",   4, 3),
        (13,"BraveLupus",8, 8),(14,"Verblitz",  7, 7),(15,"Sungoliath",5, 5),
        (16,"Heat",     15,15),(17,"BlackRams",11, 9),(18,"Steelers",  9, 7),
        (19,"BraveLupus",6, 6),(20,"WildKnights",4,3),(22,"Steelers",  6, 6),
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
        "matches":[(1,2,2,4,3),(18,9,7,7,4),(22,6,6,8,6)],
    },
    "BlackRams": {
        "name":"BlackRams Tokyo",
        "own":[150,136],
        "results":{"WonOut":96,"WonPen":31,"WonFK":9,"Reset":10,"LostPen":2,"LostFK":2,"LostOut":0},
        "stability":[27,117,6],
        "attack":{"Scrum Half Pass":56,"No 8 Pick Up":20,"Scrum Half Run":14,"No 8 Pass":7,"Scrum Half Kick":8},
        "direction":{"Open":87,"Blind":19},
        "matches":[(2,4,3,8,8),(17,11,9,10,9)],
    },
    "BraveLupus": {
        "name":"Toshiba Brave Lupus Tokyo",
        "own":[133,96],
        "results":{"WonOut":69,"WonPen":21,"WonFK":6,"Reset":13,"LostPen":19,"LostFK":3,"LostOut":2},
        "stability":[17,100,16],
        "attack":{"Scrum Half Pass":60,"No 8 Pass":8,"Scrum Half Run":6},
        "direction":{"Open":68,"Blind":6},
        "matches":[(6,7,6,10,9),(13,8,8,8,7),(19,6,6,12,8)],
    },
    "BlueRevs": {
        "name":"Shizuoka BlueRevs",
        "own":[173,134],
        "results":{"WonOut":75,"WonPen":52,"WonFK":7,"Reset":22,"LostPen":15,"LostFK":2,"LostOut":0},
        "stability":[47,116,11],
        "attack":{"Scrum Half Pass":67,"Scrum Half Run":12,"No 8 Pick Up":9,"No 8 Pass":7,"Scrum Half Kick":2},
        "direction":{"Open":85,"Blind":13},
        "matches":[(8,6,6,11,10)],
    },
    "Dynaboars": {
        "name":"Mitsubishi Sagamihara Dynaboars",
        "own":[138,117],
        "results":{"WonOut":95,"WonPen":12,"WonFK":10,"Reset":7,"LostPen":9,"LostFK":5,"LostOut":0},
        "stability":[8,112,18],
        "attack":{"Scrum Half Pass":58,"No 8 Pick Up":24,"No 8 Pass":10,"Scrum Half Run":2,"Scrum Half Kick":1},
        "direction":{"Open":79,"Blind":16},
        "matches":[(9,5,3,8,6)],
    },
    "Eagles": {
        "name":"Yokohama Canon Eagles",
        "own":[145,112],
        "results":{"WonOut":77,"WonPen":22,"WonFK":13,"Reset":17,"LostPen":12,"LostFK":2,"LostOut":2},
        "stability":[10,117,18],
        "attack":{"Scrum Half Pass":66,"No 8 Pick Up":11,"Scrum Half Run":7,"No 8 Pass":3},
        "direction":{"Open":81,"Blind":6},
        "matches":[(10,16,11,9,9)],
    },
    "D-Rocks": {
        "name":"Urayasu D-Rocks",
        "own":[147,115],
        "results":{"WonOut":99,"WonPen":10,"WonFK":6,"Reset":13,"LostPen":14,"LostFK":5,"LostOut":0},
        "stability":[13,117,17],
        "attack":{"Scrum Half Pass":71,"No 8 Pick Up":19,"Scrum Half Run":5,"No 8 Pass":8},
        "direction":{"Open":93,"Blind":10},
        "matches":[(7,12,11,5,3),(12,4,3,8,8)],
    },
    "WildKnights": {
        "name":"Saitama Wild Knights",
        "own":[156,125],
        "results":{"WonOut":94,"WonPen":22,"WonFK":9,"Reset":16,"LostPen":8,"LostFK":6,"LostOut":1},
        "stability":[9,132,15],
        "attack":{"Scrum Half Pass":74,"No 8 Pick Up":13,"Scrum Half Run":4,"No 8 Pass":4,"Scrum Half Kick":1},
        "direction":{"Open":86,"Blind":12},
        "matches":[(11,9,8,8,6),(20,4,3,8,7)],
    },
    "Heat": {
        "name":"Mie Honda Heat",
        "own":[141,118],
        "results":{"WonOut":105,"WonPen":9,"WonFK":4,"Reset":8,"LostPen":10,"LostFK":5,"LostOut":0},
        "stability":[17,120,5],
        "attack":{"Scrum Half Pass":52,"No 8 Pick Up":31,"No 8 Pass":16,"Scrum Half Run":4,"Scrum Half Kick":3},
        "direction":{"Open":87,"Blind":20},
        "matches":[(4,8,8,10,9),(16,15,15,6,5)],
    },
    "Sungoliath": {
        "name":"Tokyo Sungoliath",
        "own":[126,98],
        "results":{"WonOut":65,"WonPen":22,"WonFK":11,"Reset":14,"LostPen":10,"LostFK":3,"LostOut":1},
        "stability":[16,101,9],
        "attack":{"Scrum Half Pass":55,"No 8 Pass":10,"No 8 Pick Up":4,"Scrum Half Kick":2,"Scrum Half Run":1},
        "direction":{"Open":63,"Blind":8},
        "matches":[(3,4,3,9,4),(15,5,5,5,5)],
    },
    "Verblitz": {
        "name":"Toyota Verblitz",
        "own":[141,117],
        "results":{"WonOut":97,"WonPen":10,"WonFK":10,"Reset":14,"LostPen":8,"LostFK":2,"LostOut":0},
        "stability":[9,117,15],
        "attack":{"Scrum Half Pass":76,"No 8 Pick Up":10,"Scrum Half Run":8,"No 8 Pass":5,"Scrum Half Kick":1},
        "direction":{"Open":91,"Blind":10},
        "matches":[(5,10,8,7,7),(14,7,7,15,15)],
    },
}

ATTACK_COLORS = {
    "Scrum Half Pass": "#2563EB",
    "Scrum Half Run":  "#16A34A",
    "No 8 Pick Up":   "#D97706",
    "No 8 Pass":       "#7C3AED",
    "Scrum Half Kick": "#0891B2",
}

SC = '<div id="sc" class="section">'
SP = '<div id="sp" class="section">'
LO = '<div id="lo" class="section">'


def won_color(wp):
    return "#16a34a" if wp >= 90 else "#2563eb" if wp >= 75 else "#d97706"


def pct(n, d):
    return round(n * 100 / d) if d else 0


def donut_path(cx, cy, r_out, r_in, start_deg, sweep_deg, fill):
    def pt(cx, cy, r, deg):
        rad = math.radians(deg - 90)
        return cx + r * math.cos(rad), cy + r * math.sin(rad)

    large = 1 if sweep_deg > 180 else 0
    ox1, oy1 = pt(cx, cy, r_out, start_deg)
    ox2, oy2 = pt(cx, cy, r_out, start_deg + sweep_deg)
    ix1, iy1 = pt(cx, cy, r_in, start_deg + sweep_deg)
    ix2, iy2 = pt(cx, cy, r_in, start_deg)
    d = (
        f"M {ox1:.2f} {oy1:.2f} "
        f"A {r_out} {r_out} 0 {large} 1 {ox2:.2f} {oy2:.2f} "
        f"L {ix1:.2f} {iy1:.2f} "
        f"A {r_in} {r_in} 0 {large} 0 {ix2:.2f} {iy2:.2f} "
        f"Z"
    )
    return f'<path d="{d}" fill="{fill}"/>'


def build_donut_svg(label, pos, neu, neg):
    total = pos + neu + neg
    if total == 0:
        stab_pct = 0
        pos_pct = neu_pct = neg_pct = 0
    else:
        stab_pct = round((pos + neu) / total * 100)
        pos_pct = round(pos / total * 100)
        neu_pct = round(neu / total * 100)
        neg_pct = 100 - pos_pct - neu_pct

    cx, cy = 60, 68
    r_out, r_in = 46, 28
    vb_w, vb_h = 120, 140

    pos_sweep = pos / total * 360 if total else 0
    neu_sweep = neu / total * 360 if total else 0
    neg_sweep = 360 - pos_sweep - neu_sweep

    cur = 0
    paths = ""
    if pos_sweep > 0:
        paths += donut_path(cx, cy, r_out, r_in, cur, pos_sweep, "#16A34A")
        cur += pos_sweep
    if neu_sweep > 0:
        paths += donut_path(cx, cy, r_out, r_in, cur, neu_sweep, "#9CA3AF")
        cur += neu_sweep
    if neg_sweep > 0:
        paths += donut_path(cx, cy, r_out, r_in, cur, neg_sweep, "#DC2626")

    html = (
        f'<div style="text-align:center">'
        f'<div style="font-size:9px;font-weight:700;color:#14213D;margin-bottom:2px">{label}</div>'
        f'<svg viewBox="0 0 {vb_w} {vb_h}" width="{vb_w}" height="{vb_h}" style="display:block;margin:0 auto">'
        f'{paths}'
        f'<text x="{cx}" y="{cy-8}" text-anchor="middle" font-size="9" fill="#6B7280">安定率</text>'
        f'<text x="{cx}" y="{cy+12}" text-anchor="middle" font-size="20" font-weight="700" fill="#16a34a">{stab_pct}%</text>'
        f'</svg>'
        f'<div style="font-size:9px;line-height:1.6;margin-top:2px">'
        f'<span style="color:#16A34A;font-weight:700">Pos {pos} ({pos_pct}%)</span><br>'
        f'<span style="color:#6B7280;font-weight:700">Neu {neu} ({neu_pct}%)</span><br>'
        f'<span style="color:#DC2626;font-weight:700">Neg {neg} ({neg_pct}%)</span>'
        f'</div>'
        f'</div>'
    )
    return html


def build_result_table(title, own_n, own_won, results):
    won_n = results.get("WonOut", 0) + results.get("WonPen", 0) + results.get("WonFK", 0)
    won_pct = pct(won_n, own_n)
    wp_color = won_color(won_pct)

    rows_def = [
        ("WonOut",  "Won Outright",         "#16a34a", "#f0fdf4"),
        ("WonPen",  "Penalty Won",          "#22c55e", "#f0fdf4"),
        ("WonFK",   "Free Kick Won",        "#4ade80", "#f0fdf4"),
        ("Reset",   "Reset",                "#6b7280", "#f9fafb"),
        ("LostOut", "Lost Outright",        "#dc2626", "#fff1f2"),
        ("LostPen", "Lost Penalty Conceded","#f87171", "#fff1f2"),
        ("LostFK",  "Lost Free Kick",       "#ef4444", "#fff1f2"),
    ]

    rows_html = ""
    for key, label, color, bg in rows_def:
        n = results.get(key, 0)
        if n == 0:
            continue
        p = pct(n, own_n)
        rows_html += (
            f'<tr style="background:{bg}">'
            f'<td style="padding:4px 6px;font-size:10px;color:{color};font-weight:700;border-left:3px solid {color}">{label}</td>'
            f'<td style="padding:4px 6px;font-size:10px;color:#333;text-align:right;font-weight:700">{n}</td>'
            f'<td style="padding:4px 6px;font-size:10px;color:#888;text-align:right">{p}%</td>'
            f'</tr>'
        )

    rows_html += (
        f'<tr style="background:#F8F9FA;border-top:2px solid #DEE2E6">'
        f'<td style="padding:4px 6px;font-size:10px;font-weight:800;color:#14213D">TOTAL</td>'
        f'<td style="padding:4px 6px;font-size:10px;font-weight:800;color:#14213D;text-align:right">{own_n}</td>'
        f'<td style="padding:4px 6px;font-size:10px;color:#888;text-align:right">100%</td>'
        f'</tr>'
    )

    html = (
        f'<div style="background:#fff;border:1px solid #DEE2E6;border-radius:6px;overflow:hidden">'
        f'<div style="background:#F8F9FA;padding:4px 8px;border-bottom:1px solid #DEE2E6;display:flex;align-items:center;justify-content:space-between">'
        f'<span style="font-size:8.5px;font-weight:800;color:#14213D;text-transform:uppercase;letter-spacing:.05em">{title}</span>'
        f'<div style="font-family:Oswald,sans-serif;font-size:28px;font-weight:700;color:{wp_color};line-height:1">'
        f'{won_pct}%<span style="font-size:10px;color:#888;font-family:sans-serif;margin-left:3px">Won ({won_n}/{own_n})</span>'
        f'</div>'
        f'</div>'
        f'<table style="width:100%;border-collapse:collapse">'
        f'<thead><tr style="background:#F8F9FA">'
        f'<th style="padding:3px 6px;font-size:8.5px;color:#555;text-align:left;font-weight:700;border-bottom:1px solid #DEE2E6">Result</th>'
        f'<th style="padding:3px 6px;font-size:8.5px;color:#555;text-align:right;font-weight:700;border-bottom:1px solid #DEE2E6">n</th>'
        f'<th style="padding:3px 6px;font-size:8.5px;color:#555;text-align:right;font-weight:700;border-bottom:1px solid #DEE2E6">%</th>'
        f'</tr></thead>'
        f'<tbody>{rows_html}</tbody>'
        f'</table>'
        f'</div>'
    )
    return html


def build_opp_result_table(title, opp_n, opp_won, spears_results):
    won_n = spears_results.get("WonOut", 0) + spears_results.get("WonPen", 0) + spears_results.get("WonFK", 0)
    won_pct = pct(won_n, opp_n)
    wp_color = won_color(won_pct)

    rows_def = [
        ("WonOut",  "Won Outright",         "#16a34a", "#f0fdf4"),
        ("WonPen",  "Penalty Won",          "#22c55e", "#f0fdf4"),
        ("WonFK",   "Free Kick Won",        "#4ade80", "#f0fdf4"),
        ("Reset",   "Reset",                "#6b7280", "#f9fafb"),
        ("LostOut", "Lost Outright",        "#dc2626", "#fff1f2"),
        ("LostPen", "Lost Penalty Conceded","#f87171", "#fff1f2"),
        ("LostFK",  "Lost Free Kick",       "#ef4444", "#fff1f2"),
    ]

    rows_html = ""
    for key, label, color, bg in rows_def:
        n = spears_results.get(key, 0)
        if n == 0:
            continue
        p = pct(n, opp_n)
        rows_html += (
            f'<tr style="background:{bg}">'
            f'<td style="padding:4px 6px;font-size:10px;color:{color};font-weight:700;border-left:3px solid {color}">{label}</td>'
            f'<td style="padding:4px 6px;font-size:10px;color:#333;text-align:right;font-weight:700">{n}</td>'
            f'<td style="padding:4px 6px;font-size:10px;color:#888;text-align:right">{p}%</td>'
            f'</tr>'
        )

    rows_html += (
        f'<tr style="background:#F8F9FA;border-top:2px solid #DEE2E6">'
        f'<td style="padding:4px 6px;font-size:10px;font-weight:800;color:#14213D">TOTAL</td>'
        f'<td style="padding:4px 6px;font-size:10px;font-weight:800;color:#14213D;text-align:right">{opp_n}</td>'
        f'<td style="padding:4px 6px;font-size:10px;color:#888;text-align:right">100%</td>'
        f'</tr>'
    )

    html = (
        f'<div style="background:#fff;border:1px solid #DEE2E6;border-radius:6px;overflow:hidden">'
        f'<div style="background:#F8F9FA;padding:4px 8px;border-bottom:1px solid #DEE2E6;display:flex;align-items:center;justify-content:space-between">'
        f'<span style="font-size:8.5px;font-weight:800;color:#14213D;text-transform:uppercase;letter-spacing:.05em">{title}</span>'
        f'<div style="font-family:Oswald,sans-serif;font-size:28px;font-weight:700;color:{wp_color};line-height:1">'
        f'{won_pct}%<span style="font-size:10px;color:#888;font-family:sans-serif;margin-left:3px">Won ({won_n}/{opp_n})</span>'
        f'</div>'
        f'</div>'
        f'<table style="width:100%;border-collapse:collapse">'
        f'<thead><tr style="background:#F8F9FA">'
        f'<th style="padding:3px 6px;font-size:8.5px;color:#555;text-align:left;font-weight:700;border-bottom:1px solid #DEE2E6">Result</th>'
        f'<th style="padding:3px 6px;font-size:8.5px;color:#555;text-align:right;font-weight:700;border-bottom:1px solid #DEE2E6">n</th>'
        f'<th style="padding:3px 6px;font-size:8.5px;color:#555;text-align:right;font-weight:700;border-bottom:1px solid #DEE2E6">%</th>'
        f'</tr></thead>'
        f'<tbody>{rows_html}</tbody>'
        f'</table>'
        f'</div>'
    )
    return html


def build_attack_option_table(attack):
    items = [(k, v) for k, v in attack.items() if v > 0]
    items.sort(key=lambda x: -x[1])
    total = sum(v for _, v in items)

    rows = ""
    for name, n in items:
        color = ATTACK_COLORS.get(name, "#6B7280")
        p = pct(n, total)
        rows += (
            f'<tr>'
            f'<td style="padding:4px 6px;font-size:10px;color:{color};font-weight:700;border-left:3px solid {color}">{name}</td>'
            f'<td style="padding:4px 6px;font-size:10px;color:#333;text-align:right;font-weight:700">{n}</td>'
            f'<td style="padding:4px 6px;font-size:10px;color:#888;text-align:right">{p}%</td>'
            f'</tr>'
        )
    rows += (
        f'<tr style="background:#F8F9FA;border-top:2px solid #DEE2E6">'
        f'<td style="padding:4px 6px;font-size:10px;font-weight:800;color:#14213D">TOTAL</td>'
        f'<td style="padding:4px 6px;font-size:10px;font-weight:800;color:#14213D;text-align:right">{total}</td>'
        f'<td style="padding:4px 6px;font-size:10px;color:#888;text-align:right">100%</td>'
        f'</tr>'
    )

    html = (
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
        f'<tbody>{rows}</tbody>'
        f'</table>'
        f'</div>'
    )
    return html


def build_attack_direction_card(direction):
    open_n = direction.get("Open", 0)
    blind_n = direction.get("Blind", 0)
    total = open_n + blind_n
    open_pct = pct(open_n, total)
    blind_pct = 100 - open_pct

    html = (
        f'<div style="background:#fff;border:1px solid #DEE2E6;border-radius:6px;overflow:hidden;margin-top:8px">'
        f'<div style="background:#F8F9FA;padding:4px 8px;border-bottom:1px solid #DEE2E6">'
        f'<span style="font-size:8.5px;font-weight:800;color:#14213D;text-transform:uppercase;letter-spacing:.05em">Attack Direction</span>'
        f'</div>'
        f'<div style="padding:8px 10px">'
        f'<div style="height:20px;display:flex;border-radius:3px;overflow:hidden;margin-bottom:6px">'
        f'<div style="flex:{open_n};background:#3B82F6" title="Open: {open_n}"></div>'
        f'<div style="flex:{blind_n};background:#F97316" title="Blind: {blind_n}"></div>'
        f'</div>'
        f'<div style="font-size:10px;color:#555">'
        f'<span style="color:#3B82F6;font-weight:700">Open: {open_n} ({open_pct}%)</span>'
        f' | '
        f'<span style="color:#F97316;font-weight:700">Blind: {blind_n} ({blind_pct}%)</span>'
        f'</div>'
        f'<div style="font-size:9px;color:#9CA3AF;margin-top:2px">n={total} scrums with direction recorded</div>'
        f'</div>'
        f'</div>'
    )
    return html


def build_panel(team_data, is_spears=False, opp_name=""):
    own_n = team_data["own"][0]
    own_won = team_data["own"][1]
    stab = team_data["stability"]

    own_won_count = (
        team_data["results"].get("WonOut", 0)
        + team_data["results"].get("WonPen", 0)
        + team_data["results"].get("WonFK", 0)
    )

    if is_spears:
        own_title = "Own Ball Scrum Result"
        own_table = build_result_table(own_title, own_n, own_won_count, team_data["results"])
        opp_d = TEAM_SCRUM_DATA.get(opp_name, {})
        opp_table = build_opp_result_table(
            "Opp Ball Won Rate",
            opp_d.get("own", [0, 0])[0],
            opp_d.get("own", [0, 0])[1],
            opp_d.get("results", {}),
        )
    else:
        own_title = "Own Ball Scrum Result"
        own_table = build_result_table(own_title, own_n, own_won_count, team_data["results"])
        opp_table = build_opp_result_table(
            "Opp Ball Won Rate",
            SPEARS_SCRUM["own"][0],
            SPEARS_SCRUM["own"][1],
            SPEARS_SCRUM["results"],
        )

    own_donut = build_donut_svg("Own Ball", stab[0], stab[1], stab[2])

    if is_spears:
        opp_stab = TEAM_SCRUM_DATA[opp_name]["stability"] if opp_name in TEAM_SCRUM_DATA else [0, 0, 0]
    else:
        opp_stab = SPEARS_SCRUM["stability"]

    opp_donut = build_donut_svg("Opp Ball", opp_stab[0], opp_stab[1], opp_stab[2])

    attack_table = build_attack_option_table(team_data["attack"])
    direction_card = build_attack_direction_card(team_data["direction"])

    col1 = (
        f'<div style="display:flex;flex-direction:column;gap:8px">'
        f'{own_table}'
        f'{opp_table}'
        f'</div>'
    )

    col2 = (
        f'<div style="background:#fff;border:1px solid #DEE2E6;border-radius:6px;overflow:hidden">'
        f'<div style="background:#F8F9FA;padding:4px 8px;border-bottom:1px solid #DEE2E6">'
        f'<span style="font-size:8.5px;font-weight:800;color:#14213D;text-transform:uppercase;letter-spacing:.05em">Stability</span>'
        f'</div>'
        f'<div style="padding:10px 6px;display:flex;justify-content:space-around;align-items:flex-start">'
        f'{own_donut}'
        f'{opp_donut}'
        f'</div>'
        f'</div>'
    )

    col3 = (
        f'<div style="display:flex;flex-direction:column;gap:0">'
        f'{attack_table}'
        f'{direction_card}'
        f'</div>'
    )

    panel = (
        f'<div style="display:grid;grid-template-columns:1.2fr 0.8fr 0.9fr;gap:10px;margin-bottom:10px">'
        f'{col1}{col2}{col3}'
        f'</div>'
    )
    return panel


def build_spears_match_chart(matches):
    bar_w = 38
    gap = 4
    pad_l = 32
    pad_r = 35
    pad_t = 18
    chart_h = 85
    pad_b = 30

    n = len(matches)
    svg_w = pad_l + n * (bar_w + gap) - gap + pad_r
    svg_h = pad_t + chart_h + pad_b

    y_labels = [0, 25, 50, 75, 90, 100]

    lines = ""
    for yv in y_labels:
        y = pad_t + chart_h - (yv / 100 * chart_h)
        color = "#FCA5A5" if yv == 90 else "#E5E7EB"
        lines += f'<line x1="{pad_l}" y1="{y:.1f}" x2="{pad_l + n*(bar_w+gap)-gap}" y2="{y:.1f}" stroke="{color}" stroke-width="0.5"/>'
        lines += f'<text x="{pad_l-3}" y="{y+3:.1f}" text-anchor="end" font-size="6" fill="#888">{yv}</text>'

    target_y = pad_t + chart_h - (90 / 100 * chart_h)
    lines += (
        f'<line x1="{pad_l}" y1="{target_y:.1f}" x2="{pad_l + n*(bar_w+gap)-gap}" y2="{target_y:.1f}" '
        f'stroke="#DC2626" stroke-width="1.2" stroke-dasharray="5,3"/>'
        f'<text x="{pad_l + n*(bar_w+gap)-gap+3}" y="{target_y+3:.1f}" font-size="6.5" fill="#DC2626" font-weight="700">90%</text>'
    )

    bars = ""
    for i, (rnd, opp, sp_won, sp_total) in enumerate(matches):
        x = pad_l + i * (bar_w + gap)
        wp = pct(sp_won, sp_total)
        bh = wp / 100 * chart_h
        by = pad_t + chart_h - bh
        bc = won_color(wp)
        cx = x + bar_w / 2
        label_y = by - 4 if by > pad_t + 8 else pad_t + 7
        opp_short = opp[:5]
        bars += (
            f'<rect x="{x}" y="{by:.1f}" width="{bar_w}" height="{bh:.1f}" fill="{bc}" rx="2" opacity="0.85"/>'
            f'<text x="{cx:.1f}" y="{label_y:.1f}" text-anchor="middle" font-size="7.5" fill="{bc}" font-weight="700">{wp}%</text>'
            f'<text x="{cx:.1f}" y="{pad_t+chart_h+14}" text-anchor="middle" font-size="7" fill="#333">R{rnd}</text>'
            f'<text x="{cx:.1f}" y="{pad_t+chart_h+22}" text-anchor="middle" font-size="6" fill="#888">{opp_short}</text>'
        )

    legend = (
        f'<div style="display:flex;align-items:center;gap:12px;padding:4px 8px 0">'
        f'<div style="display:flex;align-items:center;gap:4px">'
        f'<div style="width:10px;height:7px;background:#2563EB;border-radius:1px;opacity:.85"></div>'
        f'<span style="font-size:6.5px;color:#555">Won Rate %</span>'
        f'</div>'
        f'<div style="display:flex;align-items:center;gap:4px">'
        f'<div style="width:14px;height:1px;border-top:2px dashed #DC2626"></div>'
        f'<span style="font-size:6.5px;color:#DC2626">Target 90%</span>'
        f'</div>'
        f'</div>'
    )

    svg = (
        f'<svg viewBox="0 0 {svg_w} {svg_h}" width="100%" style="min-width:{svg_w}px;display:block;max-width:100%">'
        f'{lines}{bars}'
        f'</svg>'
    )

    html = (
        f'<div style="background:#fff;border:1px solid #DEE2E6;border-radius:6px;overflow:hidden;margin-top:10px">'
        f'<div style="background:#F8F9FA;padding:5px 8px;border-bottom:1px solid #DEE2E6">'
        f'<span style="font-size:8.5px;font-weight:800;color:#14213D;text-transform:uppercase;letter-spacing:.05em">'
        f'Scrum by Match — Spears Own Ball (全21試合)'
        f'</span>'
        f'</div>'
        f'{legend}'
        f'<div style="padding:4px 8px 6px;overflow-x:auto">'
        f'{svg}'
        f'</div>'
        f'</div>'
    )
    return html


def build_opp_match_chart(opp_key, opp_name, matches):
    grp_w = 90
    bar_w = 36
    gap = 20
    pad_l = 32
    pad_r = 35
    pad_t = 18
    chart_h = 85
    pad_b = 40

    n = len(matches)
    calc_w = pad_l + n * grp_w + pad_r
    legend_needs = 200
    svg_w = max(calc_w, legend_needs + 60)
    svg_h = pad_t + chart_h + pad_b

    y_labels = [0, 25, 50, 75, 90, 100]
    chart_right = pad_l + n * grp_w + pad_r - grp_w // 2

    lines = ""
    for yv in y_labels:
        y = pad_t + chart_h - (yv / 100 * chart_h)
        color = "#FCA5A5" if yv == 90 else "#E5E7EB"
        lines += f'<line x1="{pad_l}" y1="{y:.1f}" x2="{pad_l + n*grp_w}" y2="{y:.1f}" stroke="{color}" stroke-width="0.5"/>'
        lines += f'<text x="{pad_l-3}" y="{y+3:.1f}" text-anchor="end" font-size="6" fill="#888">{yv}</text>'

    target_y = pad_t + chart_h - (90 / 100 * chart_h)
    right_x = pad_l + n * grp_w
    lines += (
        f'<line x1="{pad_l}" y1="{target_y:.1f}" x2="{right_x}" y2="{target_y:.1f}" '
        f'stroke="#DC2626" stroke-width="1.2" stroke-dasharray="5,3"/>'
        f'<text x="{right_x+3}" y="{target_y+3:.1f}" font-size="6.5" fill="#DC2626" font-weight="700">90%</text>'
    )

    bars = ""
    for i, (rnd, sp_won, sp_total, opp_won, opp_total) in enumerate(matches):
        grp_x = pad_l + i * grp_w
        cx_grp = grp_x + grp_w / 2

        sp_wp = pct(sp_won, sp_total)
        sp_bh = sp_wp / 100 * chart_h
        sp_by = pad_t + chart_h - sp_bh
        sp_bc = won_color(sp_wp)
        sp_x = grp_x + (grp_w - 2 * bar_w - gap) // 2

        opp_wp = pct(opp_won, opp_total)
        opp_bh = opp_wp / 100 * chart_h
        opp_by = pad_t + chart_h - opp_bh
        opp_bc = won_color(opp_wp)
        opp_x = sp_x + bar_w + gap

        sp_cx = sp_x + bar_w / 2
        opp_cx = opp_x + bar_w / 2

        sp_label_y = sp_by - 4 if sp_by > pad_t + 8 else pad_t + 7
        opp_label_y = opp_by - 4 if opp_by > pad_t + 8 else pad_t + 7

        r_y = pad_t + chart_h + 14
        team_y = pad_t + chart_h + 26

        opp_short = opp_key[:5]

        bars += (
            f'<rect x="{sp_x}" y="{sp_by:.1f}" width="{bar_w}" height="{sp_bh:.1f}" fill="#2563EB" rx="2" opacity="0.85"/>'
            f'<text x="{sp_cx:.1f}" y="{sp_label_y:.1f}" text-anchor="middle" font-size="8" fill="#2563EB" font-weight="700">{sp_wp}%</text>'
            f'<rect x="{opp_x}" y="{opp_by:.1f}" width="{bar_w}" height="{opp_bh:.1f}" fill="#10B981" rx="2" opacity="0.85"/>'
            f'<text x="{opp_cx:.1f}" y="{opp_label_y:.1f}" text-anchor="middle" font-size="8" fill="#10B981" font-weight="700">{opp_wp}%</text>'
            f'<text x="{cx_grp:.1f}" y="{r_y}" text-anchor="middle" font-size="9" fill="#333" font-weight="700">R{rnd}</text>'
            f'<text x="{sp_cx:.1f}" y="{team_y}" text-anchor="middle" font-size="7.5" fill="#2563EB" font-weight="700">Spears</text>'
            f'<text x="{opp_cx:.1f}" y="{team_y}" text-anchor="middle" font-size="7.5" fill="#10B981" font-weight="700">{opp_short}</text>'
        )

    legend = (
        f'<div style="display:flex;align-items:center;gap:12px;padding:4px 8px 0">'
        f'<div style="display:flex;align-items:center;gap:4px">'
        f'<div style="width:10px;height:7px;background:#2563EB;border-radius:1px;opacity:.85"></div>'
        f'<span style="font-size:6.5px;color:#2563EB;font-weight:700">Spears</span>'
        f'</div>'
        f'<div style="display:flex;align-items:center;gap:4px">'
        f'<div style="width:10px;height:7px;background:#10B981;border-radius:1px;opacity:.85"></div>'
        f'<span style="font-size:6.5px;color:#10B981;font-weight:700">{opp_key}</span>'
        f'</div>'
        f'<div style="display:flex;align-items:center;gap:4px">'
        f'<div style="width:14px;height:1px;border-top:2px dashed #DC2626"></div>'
        f'<span style="font-size:6.5px;color:#DC2626">Target 90%</span>'
        f'</div>'
        f'</div>'
    )

    svg = (
        f'<svg viewBox="0 0 {svg_w} {svg_h}" width="100%" style="min-width:{svg_w}px;display:block;max-width:100%">'
        f'{lines}{bars}'
        f'</svg>'
    )

    html = (
        f'<div style="background:#fff;border:1px solid #DEE2E6;border-radius:6px;overflow:hidden;margin-top:10px">'
        f'<div style="background:#F8F9FA;padding:5px 8px;border-bottom:1px solid #DEE2E6">'
        f'<span style="font-size:8.5px;font-weight:800;color:#14213D;text-transform:uppercase;letter-spacing:.05em">'
        f'Scrum by Match — vs {opp_name}'
        f'</span>'
        f'</div>'
        f'{legend}'
        f'<div style="padding:4px 8px 6px;overflow-x:auto">'
        f'{svg}'
        f'</div>'
        f'</div>'
    )
    return html


def build_scrum_section(opp_key, opp_name, round_num):
    tdata = TEAM_SCRUM_DATA[opp_key]

    spears_panel = build_panel(SPEARS_SCRUM, is_spears=True, opp_name=opp_key)
    spears_chart = build_spears_match_chart(SPEARS_SCRUM["matches"])

    opp_panel = build_panel(tdata, is_spears=False, opp_name=opp_key)
    opp_chart = build_opp_match_chart(opp_key, opp_name, tdata["matches"])

    spears_block = (
        f'<div style="background:#FAFAFA;border:1px solid #DEE2E6;border-radius:8px;padding:12px 14px;margin-bottom:12px">'
        f'<div style="display:flex;align-items:center;gap:8px;padding:6px 10px;background:#F9731618;border-radius:5px;border-left:4px solid #F97316;margin-bottom:12px">'
        f'<span style="font-family:Oswald,sans-serif;font-size:13px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#F97316">'
        f'&#9632; Kubota Spears'
        f'</span>'
        f'</div>'
        f'{spears_panel}'
        f'{spears_chart}'
        f'</div>'
    )

    divider = (
        f'<div style="display:flex;align-items:center;gap:8px;margin:14px 0">'
        f'<div style="flex:1;height:2px;background:linear-gradient(to right,#E9ECEF,#ADB5BD)"></div>'
        f'<span style="font-size:8px;font-weight:700;color:#6B7280;text-transform:uppercase;letter-spacing:.1em">vs {opp_name}</span>'
        f'<div style="flex:1;height:2px;background:linear-gradient(to left,#E9ECEF,#ADB5BD)"></div>'
        f'</div>'
    )

    opp_block = (
        f'<div style="background:#FAFAFA;border:1px solid #DEE2E6;border-radius:8px;padding:12px 14px;margin-bottom:12px">'
        f'<div style="display:flex;align-items:center;gap:8px;padding:6px 10px;background:#10B98118;border-radius:5px;border-left:4px solid #10B981;margin-bottom:12px">'
        f'<span style="font-family:Oswald,sans-serif;font-size:13px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#10B981">'
        f'&#9632; {opp_name}'
        f'</span>'
        f'</div>'
        f'{opp_panel}'
        f'{opp_chart}'
        f'</div>'
    )

    section = (
        f'<div id="sc" class="section">\n'
        f'  <div style="padding:0 2px">\n'
        f'    {spears_block}\n'
        f'    {divider}\n'
        f'    {opp_block}\n'
        f'  </div>\n'
        f'</div>\n'
    )
    return section


def process_file(filepath, opp_key, round_num):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    opp_name = TEAM_SCRUM_DATA[opp_key]["name"]
    new_sc = build_scrum_section(opp_key, opp_name, round_num)

    if SC in content and SP in content:
        sc_start = content.index(SC)
        sp_start = content.index(SP)
        if sc_start < sp_start:
            new_content = content[:sc_start] + new_sc + content[sp_start:]
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(new_content)
            return True

    if LO in content and SP in content:
        sp_start = content.index(SP)
        new_content = content[:sp_start] + new_sc + content[sp_start:]
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(new_content)

        scrum_btn = '<button class="nav-btn" style="color:#6366f1" onclick="showSection(\'sc\',this)">Scrum</button>'
        lo_btn_pattern = re.compile(r'(<button[^>]+onclick="showSection\(\'lo\'[^>]+>Lineout</button>)')
        if scrum_btn not in new_content:
            with open(filepath, "r", encoding="utf-8") as f:
                nc2 = f.read()
            nc2 = lo_btn_pattern.sub(r'\1' + scrum_btn, nc2, count=1)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(nc2)
        return True

    return False


def main():
    pattern = re.compile(r"scout_Spears_vs_(.+)_R(\d+)\.html$")
    count = 0
    for fname in sorted(os.listdir(BIOUT_DIR)):
        m = pattern.match(fname)
        if not m:
            continue
        opp_key = m.group(1)
        round_num = int(m.group(2))
        if opp_key not in TEAM_SCRUM_DATA:
            continue
        filepath = os.path.join(BIOUT_DIR, fname)
        updated = process_file(filepath, opp_key, round_num)
        if updated:
            print(f"✓ {fname}")
            count += 1
    print(f"Done: {count} files")


if __name__ == "__main__":
    main()
