#!/usr/bin/env python3
"""
Season KPI Report v2 — Kubota Spears.

Tab-switching layout (Overview / Kicking Game / Attack / Defence).
Each tab = an "avg-table" comparing Win / Loss / Season averages, plus a
per-match detail table.

KPI definitions (confirmed with the user):
  - Kick Regain   = Kick result 'Own Player - Collected'
  - Kick Hit Grass= Kick result 'Collected Bounce' (bounce-in-touch excluded)
  - Turnover Conc = action_name='Turnover'
  - 22m Success   = 22 Entry Outcome 'Try' or 'Penalty Conceded'
  - Turnover Rate = Turnover Conceded / attacks (Possession-event count)
  - Territory %   = rucks (BOTH teams) mapped to absolute pitch from Kubota's
                    frame (Kubota ruck abs=x; opponent ruck abs=100-x), share
                    with abs>50. x_coord is attack-normalised (verified: no
                    home/away flip), so a single-team threshold is invalid.
Other defs follow match_stats_final.py (Try=5/Conv=2/PG=3/DG=3, Lineout,
Turnover Won = Possession 'Turnover Won' + Jackal Success dedup'd <0.5 min).
"""
import json
import sqlite3
from statistics import mean

TEAM = "Kubota Spears"
DB = "rugby.db"
OUT = "season_kpi_v2.html"


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def match_min(ps, period, p2):
    return ps / 60.0 if period == 1 else 40.0 + (ps - p2) / 60.0


con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
cur = con.cursor()


def C(fxid, **conds):
    """Count Kubota events in a match matching conditions (value may be set)."""
    sql = "SELECT COUNT(*) FROM events WHERE fxid=? AND team_name=?"
    params = [fxid, TEAM]
    for k, v in conds.items():
        if isinstance(v, (set, list, tuple)):
            ph = ",".join("?" * len(v))
            sql += f" AND {k} IN ({ph})"
            params += list(v)
        else:
            sql += f" AND {k}=?"
            params.append(v)
    return cur.execute(sql, params).fetchone()[0]


def CL(fx, action, col, like):
    """Count Kubota events in a match where col LIKE pattern."""
    return cur.execute(
        f"SELECT COUNT(*) FROM events WHERE fxid=? AND team_name=? AND action_name=? AND {col} LIKE ?",
        (fx, TEAM, action, like)).fetchone()[0]


def CT(fx, team, **conds):
    """Count events for an arbitrary team in a match matching conditions (value may be set)."""
    sql = "SELECT COUNT(*) FROM events WHERE fxid=? AND team_name=?"
    params = [fx, team]
    for k, v in conds.items():
        if isinstance(v, (set, list, tuple)):
            sql += f" AND {k} IN ({','.join('?' * len(v))})"
            params += list(v)
        else:
            sql += f" AND {k}=?"
            params.append(v)
    return cur.execute(sql, params).fetchone()[0]


matches = cur.execute("SELECT * FROM matches ORDER BY date_played, fxid").fetchall()
per_match = []

# season-wide penalty accumulators (page: Penalty)
pen_types = {}
pen_od = {"Offence": 0, "Defence": 0}
pen_half = {1: 0, 2: 0}
pen_quarter = {"Q1": 0, "Q2": 0, "Q3": 0, "Q4": 0}

for m in matches:
    fx = m["fxid"]
    p2 = _num(cur.execute(
        "SELECT MIN(ps_timestamp) v FROM events WHERE fxid=? AND period=2", (fx,)
    ).fetchone()["v"])

    # durations / possession (both teams)
    poss_rows = cur.execute(
        "SELECT team_name tn, ps_timestamp ts, ps_endstamp te "
        "FROM events WHERE fxid=? AND action_name='Possession'", (fx,)
    ).fetchall()
    at_kub = sum(_num(r["te"]) - _num(r["ts"]) for r in poss_rows if r["tn"] == TEAM)
    at_tot = sum(_num(r["te"]) - _num(r["ts"]) for r in poss_rows)

    # territory: Kubota events, action-time (ps_endstamp-ps_timestamp) split by x_coord half
    #   own = x in [-10,50], opp = x in [51,110]; Territory % = opp time / (own+opp) time
    terr_rows = cur.execute(
        "SELECT x_coord x, ps_timestamp ts, ps_endstamp te FROM events "
        "WHERE fxid=? AND team_name=? AND x_coord IS NOT NULL AND x_coord!='' "
        "AND ps_endstamp IS NOT NULL AND ps_endstamp!=''", (fx, TEAM)
    ).fetchall()
    terr_num = terr_den = 0.0  # terr_num = opp-half time, terr_den = total time
    for r in terr_rows:
        x = _num(r["x"])
        dur = _num(r["te"]) - _num(r["ts"])
        if dur <= 0:
            continue
        if 51 <= x <= 110:
            terr_num += dur
            terr_den += dur
        elif -10 <= x <= 50:
            terr_den += dur

    # turnovers won (Possession 'Turnover Won' + Jackal Success, dedup <0.5 min)
    poss_mins, jck_mins = [], []
    for r in cur.execute(
        "SELECT action_name an, action_type_name tp, action_result_name rs, "
        "ps_timestamp ts, period pd FROM events WHERE fxid=? AND team_name=?", (fx, TEAM)
    ).fetchall():
        if r["an"] == "Possession" and r["tp"] == "Turnover Won":
            poss_mins.append(match_min(_num(r["ts"]), r["pd"], p2))
        elif r["an"] == "Collection" and r["tp"] == "Jackal" and r["rs"] == "Success":
            jck_mins.append(match_min(_num(r["ts"]), r["pd"], p2))
    overlap = sum(1 for j in jck_mins if any(abs(j - p) < 0.5 for p in poss_mins))
    tw = len(poss_mins) + len(jck_mins) - overlap

    # counts
    kicks = C(fx, action_name="Kick")
    km = sum(_num(r["metres"]) for r in cur.execute(
        "SELECT metres FROM events WHERE fxid=? AND team_name=? AND action_name='Kick'", (fx, TEAM)
    ).fetchall())
    rucks = C(fx, action_name="Ruck")
    carries = C(fx, action_name="Carry")
    metres = sum(_num(r["metres"]) for r in cur.execute(
        "SELECT metres FROM events WHERE fxid=? AND team_name=? AND action_name='Carry'", (fx, TEAM)
    ).fetchall())
    tk = C(fx, action_name="Tackle")
    mt = C(fx, action_name="Missed Tackle")

    # goal kicking
    def gk(t, r):
        return C(fx, action_name="Goal Kick", action_type_name=t, action_result_name=r)
    gk_made = gk("Conversion", "Goal Kicked") + gk("Penalty Goal", "Goal Kicked") + gk("Drop Goal", "Goal Kicked")
    gk_att = gk_made + gk("Conversion", "Goal Missed") + gk("Penalty Goal", "Goal Missed") + gk("Drop Goal", "Goal Missed")

    # set piece
    lo_throw = C(fx, action_name="Lineout Throw")
    lo_won = CL(fx, "Lineout Throw", "action_result_name", "Won%")
    lo_steal = CL(fx, "Lineout Take", "action_type_name", "Lineout Steal%")
    sc_tot = C(fx, action_name="Scrum")
    sc_won = CL(fx, "Scrum", "action_result_name", "Won%")
    sc_reset = C(fx, action_name="Scrum", action_result_name="Reset")
    ma_tot = C(fx, action_name="Maul")
    ma_won = C(fx, action_name="Maul", action_result_name="Won Outright")
    ma_try = C(fx, action_name="Maul", action_result_name="Try Scored")
    ma_m = sum(_num(r["metres"]) for r in cur.execute(
        "SELECT metres FROM events WHERE fxid=? AND team_name=? AND action_name='Maul'", (fx, TEAM)
    ).fetchall())

    # opponent stats (for Defence match-by-match opponent columns)
    ot = m["opponent_name"]
    opp_carries = CT(fx, ot, action_name="Carry")
    opp_glo = CT(fx, ot, action_name="Carry", qualifier3_name="Crossed Gain line")
    opp_rucks = CT(fx, ot, action_name="Ruck")
    opp_lqb = CT(fx, ot, action_name="Ruck",
                 qualifier4_name={"0-1 Seconds", "1-2 Seconds", "2-3 Seconds"})
    tries_conceded = CT(fx, ot, action_name="Try")
    opp_e22 = CT(fx, ot, action_name="Attacking 22 Entry")
    opp_s22 = CT(fx, ot, action_name="Attacking 22 Entry",
                 action_type_name={"22 Entry Outcome - Try", "22 Entry Outcome - Penalty Conceded"})

    # penalty season accumulation (type / attack-defence / half / quarter)
    for r in cur.execute(
        "SELECT action_type_name tp, qualifier3_name od, period pd, ps_timestamp ts "
        "FROM events WHERE fxid=? AND team_name=? AND action_name='Penalty Conceded'", (fx, TEAM)
    ).fetchall():
        t = r["tp"] or "Other"
        pen_types[t] = pen_types.get(t, 0) + 1
        if r["od"] in pen_od:
            pen_od[r["od"]] += 1
        pd = int(_num(r["pd"]))
        if pd in pen_half:
            pen_half[pd] += 1
        mm = match_min(_num(r["ts"]), pd, p2)
        q = "Q1" if mm <= 20 else "Q2" if mm <= 40 else "Q3" if mm <= 60 else "Q4"
        pen_quarter[q] += 1

    rec = {
        "fxid": fx, "date": m["date_played"], "opp": m["opponent_name"],
        "ha": "H" if m["kubota_is_home"] else "A",
        "kub": m["kubota_score"], "opp_score": m["opponent_score"], "result": m["kubota_result"],
        # raw components
        "at_kub": at_kub, "at_tot": at_tot,
        "terr_num": terr_num, "terr_den": terr_den,
        "tw": tw,
        "kicks": kicks, "km": int(km), "rucks": rucks,
        "regain": C(fx, action_name="Kick", action_result_name="Own Player - Collected"),
        "hg": C(fx, action_name="Kick", action_result_name="Collected Bounce"),
        "carries": carries, "metres": int(metres),
        "glo": C(fx, action_name="Carry", qualifier3_name="Crossed Gain line"),
        "lqb_n": C(fx, action_name="Ruck",
                   qualifier4_name={"0-1 Seconds", "1-2 Seconds", "2-3 Seconds"}),
        "offloads": C(fx, action_name="Pass", action_type_name="Offload",
                      action_result_name="Own Player"),
        "e22": C(fx, action_name="Attacking 22 Entry"),
        "s22": C(fx, action_name="Attacking 22 Entry",
                 action_type_name={"22 Entry Outcome - Try", "22 Entry Outcome - Penalty Conceded"}),
        "tries": C(fx, action_name="Try"),
        "pen": C(fx, action_name="Penalty Conceded"),
        "to_con": C(fx, action_name="Turnover"),
        "attacks": C(fx, action_name="Possession"),
        "tk": tk, "mt": mt,
        "dom": C(fx, action_name="Tackle", qualifier4_name="Dominant Tackle"),
        "gk_made": gk_made, "gk_att": gk_att,
        # set piece
        "lo_throw": lo_throw, "lo_won": lo_won, "lo_lost": lo_throw - lo_won,
        "lo_steal": lo_steal,
        "sc_tot": sc_tot, "sc_won": sc_won, "sc_reset": sc_reset,
        "ma_tot": ma_tot, "ma_won": ma_won, "ma_try": ma_try, "ma_m": int(ma_m),
        # opponent stats
        "opp_carries": opp_carries, "opp_glo": opp_glo,
        "opp_rucks": opp_rucks, "opp_lqb": opp_lqb,
        "tries_conceded": tries_conceded, "opp_e22": opp_e22, "opp_s22": opp_s22,
    }
    per_match.append(rec)

# ---- player season totals (pages: Individual Attack / Defence) --------------
pos_map, shirt_map, _best = {}, {}, {}
for r in cur.execute(
    "SELECT player_name nm, player_position_name pos, CAST(player_shirt_number AS INT) sh, "
    "COUNT(*) n FROM events WHERE team_name=? AND player_name IS NOT NULL AND player_name!='' "
    "GROUP BY 1,2,3", (TEAM,)
).fetchall():
    nm = r["nm"]
    if nm not in _best or r["n"] > _best[nm]:
        _best[nm] = r["n"]
        pos_map[nm] = r["pos"] or ""
        shirt_map[nm] = r["sh"] if r["sh"] is not None else 99

# play time per player (minutes, summed across matches) from Sub In/Sub Out
play_time = {}
for m in matches:
    fx = m["fxid"]
    p2 = _num(cur.execute(
        "SELECT MIN(ps_timestamp) v FROM events WHERE fxid=? AND period=2", (fx,)
    ).fetchone()["v"])
    sub_in, sub_out = {}, {}
    for r in cur.execute(
        "SELECT player_name nm, ps_timestamp ts, period pd FROM events "
        "WHERE fxid=? AND team_name=? AND action_name='Sub In'", (fx, TEAM)
    ).fetchall():
        if r["nm"]:
            mmv = match_min(_num(r["ts"]), int(_num(r["pd"])), p2)
            sub_in[r["nm"]] = min(sub_in.get(r["nm"], 1e9), mmv)
    for r in cur.execute(
        "SELECT player_name nm, ps_timestamp ts, period pd FROM events "
        "WHERE fxid=? AND team_name=? AND action_name='Sub Out'", (fx, TEAM)
    ).fetchall():
        if r["nm"]:
            mmv = match_min(_num(r["ts"]), int(_num(r["pd"])), p2)
            sub_out[r["nm"]] = max(sub_out.get(r["nm"], -1), mmv)
    for row in cur.execute(
        "SELECT DISTINCT player_name nm FROM events WHERE fxid=? AND team_name=? "
        "AND player_name IS NOT NULL AND player_name!=''", (fx, TEAM)
    ).fetchall():
        nm = row["nm"]
        hi, ho = nm in sub_in, nm in sub_out
        if ho and not hi:
            s, e = 0, sub_out[nm]
        elif hi and not ho:
            s, e = sub_in[nm], 80
        elif hi and ho:
            s, e = sub_in[nm], sub_out[nm]
        else:
            s, e = 0, 80
        s, e = max(0, s), min(80, e)
        if e > s:
            play_time[nm] = play_time.get(nm, 0) + (e - s)
play_time = {k: int(round(v)) for k, v in play_time.items()}

# standard 1-15 positional order for ranking
POS_ORDER = ["Loosehead Prop", "Hooker", "Tighthead Prop", "Lock (4)", "Lock (5)",
             "Blindside Flanker", "Openside Flanker", "Number 8", "Scrum Half",
             "Fly Half", "Inside Centre", "Outside Centre", "Right Wing", "Left Wing", "Full Back"]


def pos_key(p):
    """Sort key: (position index, -play time). Unknown positions go last."""
    pos = p["pos"]
    idx = POS_ORDER.index(pos) if pos in POS_ORDER else len(POS_ORDER)
    return (idx, -p.get("pt", 0))


SPD_FAST = "('0-1 Seconds','1-2 Seconds','2-3 Seconds')"
SPD_SLOW = "('3-4 Seconds','4-5 Seconds','5-6 Seconds','6+ Seconds')"
PASS_BAD = "('Incomplete','Error','Forward','Intercepted','Off Target')"

players_attack = []
for r in cur.execute(
    "SELECT player_name nm, "
    "SUM(action_name='Carry') carries, "
    "SUM(CASE WHEN action_name='Carry' THEN CAST(metres AS REAL) ELSE 0 END) metres, "
    "SUM(action_name='Carry' AND qualifier3_name='Crossed Gain line') glo, "
    "SUM(action_name='Attacking Qualities' AND action_type_name='Initial Break') lb, "
    "SUM(action_name='Attacking Qualities' AND action_type_name='Defender Beaten') db, "
    "SUM(action_name='Pass' AND action_type_name='Offload' AND action_result_name='Own Player') ol, "
    "SUM(action_name='Try') tries, "
    "SUM(action_name='Turnover') err, "
    "SUM(action_name='Pass') passes, "
    f"SUM(action_name='Pass' AND action_type_name IN {PASS_BAD}) pass_bad, "
    "SUM(action_name='Kick') kicks, "
    "SUM(CASE WHEN action_name='Kick' THEN CAST(metres AS REAL) ELSE 0 END) kick_m, "
    f"SUM(action_name='Ruck' AND qualifier4_name IN {SPD_FAST}) ooa13, "
    f"SUM(action_name='Ruck' AND qualifier4_name IN {SPD_SLOW}) ooa4 "
    "FROM events WHERE team_name=? AND player_name IS NOT NULL AND player_name!='' "
    "GROUP BY player_name", (TEAM,)
).fetchall():
    nm = r["nm"]
    if (r["carries"] or 0) == 0 and (r["tries"] or 0) == 0:
        continue
    car, pas, kk = r["carries"], r["passes"], r["kicks"]
    ooa_t = r["ooa13"] + r["ooa4"]
    players_attack.append({
        "name": nm, "pos": pos_map.get(nm, ""), "shirt": shirt_map.get(nm, 99),
        "pt": play_time.get(nm, 0),
        "carries": car, "metres": int(r["metres"]),
        "avg": round(r["metres"] / car, 1) if car else 0,
        "gl": round(r["glo"] / car * 100, 1) if car else 0,
        "lb": r["lb"], "db": r["db"], "ol": r["ol"], "tries": r["tries"], "err": r["err"],
        "passes": pas,
        "pass_acc": round((pas - r["pass_bad"]) / pas * 100, 1) if pas else 0,
        "kicks": kk, "kick_m": int(r["kick_m"]),
        "avg_kick": round(r["kick_m"] / kk, 1) if kk else 0,
        "ooa13": r["ooa13"], "ooa4": r["ooa4"],
        "ooa_eff": round(r["ooa13"] / ooa_t * 100, 1) if ooa_t else 0,
    })
players_attack.sort(key=pos_key)

players_defence = []
for r in cur.execute(
    "SELECT player_name nm, "
    "SUM(action_name='Tackle') tk, "
    "SUM(action_name='Missed Tackle') mt, "
    "SUM(action_name='Tackle' AND qualifier4_name='Dominant Tackle') dom, "
    "SUM(action_name='Tackle' AND action_result_name='Passive') passive, "
    "SUM(action_name='Tackle' AND action_result_name='Offload Allowed') oa, "
    "SUM(action_name='Tackle' AND qualifier6_name='Legs') legs, "
    "SUM(action_name='Tackle' AND qualifier6_name IN ('Upper Torso','Lower Torso','Legs')) ht_tot, "
    "SUM(action_name='Collection' AND action_type_name='Jackal' AND action_result_name='Success') jck, "
    "SUM(action_name='Tackle' AND action_result_name='Turnover Won') tow_tackle, "
    "SUM(action_name='Ruck OOA' AND action_type_name='Penalty Won') pw, "
    "SUM(action_name='Penalty Conceded') pen "
    "FROM events WHERE team_name=? AND player_name IS NOT NULL AND player_name!='' "
    "GROUP BY player_name", (TEAM,)
).fetchall():
    nm = r["nm"]
    att = (r["tk"] or 0) + (r["mt"] or 0)
    if att == 0:
        continue
    players_defence.append({
        "name": nm, "pos": pos_map.get(nm, ""), "shirt": shirt_map.get(nm, 99),
        "pt": play_time.get(nm, 0),
        "tk": r["tk"], "mt": r["mt"], "att": att,
        "pct": round(r["tk"] / att * 100, 1) if att else 0,
        "dom": r["dom"], "dom_pct": round(r["dom"] / att * 100, 1) if att else 0,
        "passive": r["passive"], "oa": r["oa"],
        "legs": r["legs"], "ht_tot": r["ht_tot"],
        "leg_pct": round(r["legs"] / r["ht_tot"] * 100, 1) if r["ht_tot"] else 0,
        "jck": r["jck"],
        "tow": r["tow_tackle"] + r["pw"],  # tackle turnovers + breakdown penalties won
        "pen": r["pen"],
    })
players_defence.sort(key=pos_key)

# lineout throwers (set piece page)
lineout_throwers = []
for r in cur.execute(
    "SELECT player_name nm, "
    "SUM(action_name='Lineout Throw' AND action_result_name LIKE 'Won%') won, "
    "SUM(action_name='Lineout Throw' AND action_result_name LIKE 'Lost%') lost, "
    "SUM(action_name='Lineout Throw') tot "
    "FROM events WHERE team_name=? AND player_name IS NOT NULL AND player_name!='' "
    "GROUP BY player_name", (TEAM,)
).fetchall():
    if (r["tot"] or 0) > 0:
        lineout_throwers.append({
            "name": r["nm"], "pos": pos_map.get(r["nm"], ""),
            "won": r["won"], "lost": r["lost"], "tot": r["tot"],
            "pct": round(r["won"] / r["tot"] * 100, 1) if r["tot"] else 0,
        })
lineout_throwers.sort(key=lambda x: x["tot"], reverse=True)

# league averages (all 12 teams across the DB's 18 matches = 36 team-matches)
TM = cur.execute(
    "SELECT COUNT(*) FROM (SELECT DISTINCT fxid, team_name FROM events "
    "WHERE team_name IS NOT NULL AND team_name!='')").fetchone()[0]


def lg(where=""):
    return cur.execute(
        f"SELECT COUNT(*) FROM events WHERE action_name='Penalty Conceded' {where}").fetchone()[0]


league = {
    "tm": TM,
    "infr": lg() / TM,
    "full": lg("AND qualifier4_name='Full Penalty'") / TM,
    "fk": lg("AND qualifier4_name='Free Kick'") / TM,
    "att": lg("AND qualifier3_name='Offence'") / TM,
    "def": lg("AND qualifier3_name='Defence'") / TM,
}
kub_pen_full = cur.execute(
    "SELECT COUNT(*) FROM events WHERE team_name=? AND action_name='Penalty Conceded' "
    "AND qualifier4_name='Full Penalty'", (TEAM,)).fetchone()[0]
kub_pen_fk = cur.execute(
    "SELECT COUNT(*) FROM events WHERE team_name=? AND action_name='Penalty Conceded' "
    "AND qualifier4_name='Free Kick'", (TEAM,)).fetchone()[0]

# lineout claims by player (set piece page)
lineout_players = []
for r in cur.execute(
    "SELECT player_name nm, "
    "SUM(action_name='Lineout Take' AND action_result_name LIKE 'Won%') won "
    "FROM events WHERE team_name=? AND player_name IS NOT NULL AND player_name!='' "
    "GROUP BY player_name", (TEAM,)
).fetchall():
    if (r["won"] or 0) > 0:
        lineout_players.append({"name": r["nm"], "pos": pos_map.get(r["nm"], ""), "won": r["won"]})
lineout_players.sort(key=lambda x: x["won"], reverse=True)

con.close()


# ---- group aggregation ------------------------------------------------------
def mn(recs, f):
    return mean([r[f] for r in recs]) if recs else 0.0


def rate(recs, num, den):
    d = sum(r[den] for r in recs)
    return sum(r[num] for r in recs) / d * 100 if d else 0.0


def ratio(recs, num, den):
    d = sum(r[den] for r in recs)
    return sum(r[num] for r in recs) / d if d else 0.0


def group_kpis(recs):
    return {
        "pf": mn(recs, "kub"), "pa": mn(recs, "opp_score"),
        "bip": mn(recs, "at_tot") / 60.0,
        "poss": rate(recs, "at_kub", "at_tot"),
        "terr": rate(recs, "terr_num", "terr_den"),
        "tries": mn(recs, "tries"),
        "tries_con": mn(recs, "tries_conceded"),
        "trate": rate(recs, "to_con", "attacks"),
        "pen": mn(recs, "pen"),
        # kicking
        "kicks": mn(recs, "kicks"), "km": mn(recs, "km"),
        "avg_kick": ratio(recs, "km", "kicks"),
        "r2k": ratio(recs, "rucks", "kicks"),
        "regain": mn(recs, "regain"), "hg": mn(recs, "hg"),
        "gk_pct": rate(recs, "gk_made", "gk_att"),
        # attack
        "carries": mn(recs, "carries"), "metres": mn(recs, "metres"),
        "gl": rate(recs, "glo", "carries"),
        "lqb": rate(recs, "lqb_n", "rucks"),
        "offloads": mn(recs, "offloads"),
        "e22": mn(recs, "e22"), "s22": mn(recs, "s22"),
        "s22_pct": rate(recs, "s22", "e22"),
        "to_con": mn(recs, "to_con"),
        # defence
        "tk": mn(recs, "tk"), "mt": mn(recs, "mt"),
        "tack_att": mn(recs, "tk") + mn(recs, "mt"),
        "tack_pct": rate(recs, "tk", None) if False else (
            sum(r["tk"] for r in recs) / sum(r["tk"] + r["mt"] for r in recs) * 100
            if sum(r["tk"] + r["mt"] for r in recs) else 0.0),
        "dom_pct": rate(recs, "dom", "tk"),
        "tw": mn(recs, "tw"),
        # set piece
        "lo_won": mn(recs, "lo_won"), "lo_lost": mn(recs, "lo_lost"),
        "lo_steal": mn(recs, "lo_steal"), "lo_pct": rate(recs, "lo_won", "lo_throw"),
        "sc_tot": mn(recs, "sc_tot"), "sc_reset": mn(recs, "sc_reset"),
        "sc_pct": rate(recs, "sc_won", "sc_tot"),
        "ma_tot": mn(recs, "ma_tot"), "ma_try": mn(recs, "ma_try"), "ma_m": mn(recs, "ma_m"),
    }


wins = [r for r in per_match if r["result"] == "W"]
losses = [r for r in per_match if r["result"] == "L"]
groups = {"win": group_kpis(wins), "loss": group_kpis(losses), "season": group_kpis(per_match)}

DATA = {
    "team": TEAM,
    "n": len(per_match), "nw": len(wins), "nl": len(losses),
    "pf_tot": sum(r["kub"] for r in per_match), "pa_tot": sum(r["opp_score"] for r in per_match),
    "groups": groups,
    "matches": per_match,
    "penalty": {
        "total": sum(pen_types.values()),
        "full": kub_pen_full, "fk": kub_pen_fk,
        "types": sorted(pen_types.items(), key=lambda kv: kv[1], reverse=True),
        "od": pen_od,
        "half": {"H1": pen_half[1], "H2": pen_half[2]},
        "quarter": pen_quarter,
    },
    "league": league,
    "players_attack": players_attack,
    "players_defence": players_defence,
    "lineout_players": lineout_players,
    "lineout_throwers": lineout_throwers,
}

TEMPLATE = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Season KPI Report v2 – Kubota Spears</title>
<style>
:root{
  --kub-dark:#14213d; --kub-mid:#1d3055; --kub-red:#d6202b; --kub-gold:#e8a13c;
  --neutral:#f5f4f0; --ink:#1a1a1a; --muted:#6b6b6b; --rule:#d8d4cc;
  --good:#1a7a3c; --warn:#b85c00; --win:#1a7a3c; --loss:#c0202b; --radius:4px; font-size:14px;
}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0;}
body{font-family:'Helvetica Neue',Arial,sans-serif;background:#e8e4dc;color:var(--ink);}
.shell{width:1000px;margin:14px auto;background:var(--neutral);box-shadow:0 2px 14px rgba(0,0,0,.18);border-radius:6px;overflow:hidden;}
.page-header{background:var(--kub-dark);color:white;padding:14px 22px;display:flex;justify-content:space-between;align-items:center;}
.page-header .subtitle{font-size:11px;color:var(--kub-gold);letter-spacing:.08em;text-transform:uppercase;}
.page-header h1{font-size:18px;font-weight:800;letter-spacing:.03em;margin-top:2px;}
.page-header .rec{font-size:12px;color:rgba(255,255,255,.7);margin-top:3px;}
.record-pill{background:var(--kub-red);padding:6px 18px;border-radius:22px;font-size:18px;font-weight:900;}
/* tabs */
.tabs{display:flex;background:var(--kub-mid);padding:0 12px;}
.tab-btn{background:none;border:none;color:rgba(255,255,255,.6);font-size:12px;font-weight:700;
  letter-spacing:.05em;text-transform:uppercase;padding:11px 20px;cursor:pointer;border-bottom:3px solid transparent;}
.tab-btn:hover{color:white;}
.tab-btn.active{color:white;border-bottom-color:var(--kub-gold);}
.tab-panel{display:none;padding:18px 22px 24px;}
.tab-panel.active{display:block;}
/* avg table */
.avg-table{width:100%;border-collapse:collapse;font-size:12px;margin-bottom:8px;}
.avg-table th{padding:8px 10px;background:var(--kub-dark);color:white;font-size:10px;font-weight:700;
  letter-spacing:.05em;text-transform:uppercase;text-align:center;}
.avg-table th.k{text-align:left;}
.avg-table th.win{background:#13532b;} .avg-table th.loss{background:#7d1820;}
.avg-table td{padding:7px 10px;text-align:center;border-bottom:1px solid var(--rule);font-weight:700;font-size:13px;}
.avg-table td.k{text-align:left;font-weight:600;font-size:12px;color:var(--ink);}
.avg-table td.k small{display:block;color:var(--muted);font-size:9px;font-weight:500;}
.avg-table td.win{background:rgba(26,122,60,.08);color:var(--win);}
.avg-table td.loss{background:rgba(192,32,43,.08);color:var(--loss);}
.avg-table td.delta.pos{color:var(--good);} .avg-table td.delta.neg{color:var(--loss);}
.avg-table tr:hover td{filter:brightness(.985);}
.sec-title{font-size:11px;font-weight:800;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);
  border-bottom:2px solid var(--rule);padding-bottom:5px;margin:18px 0 10px;}
/* per-match (it) table */
.it-wrap{overflow-x:auto;}
.it-table{width:100%;border-collapse:collapse;font-size:11px;}
.it-table th,.it-table td{min-width:40px;}
.it-table th.l,.it-table td.l{min-width:auto;}
.it-table thead th{padding:6px 6px;background:var(--kub-mid);color:white;font-size:9px;font-weight:700;
  letter-spacing:.02em;text-transform:uppercase;white-space:normal;line-height:1.2;vertical-align:bottom;text-align:center;}
.it-table thead th.l{text-align:left;}
.it-table thead th.opp{background:#c4600f;}
.it-table tbody td.oppcol{background:rgba(196,96,15,.06);}
.it-table tbody td{padding:4px 7px;text-align:center;border-bottom:1px solid var(--rule);font-weight:600;white-space:nowrap;}
.it-table tbody td.l{text-align:left;}
.it-table tbody td.date{color:var(--muted);font-size:10px;}
.it-table tbody tr.win td.res{color:var(--win);font-weight:800;}
.it-table tbody tr.loss td.res{color:var(--loss);font-weight:800;}
.it-table tbody tr.win td.score{background:rgba(26,122,60,.06);}
.it-table tbody tr.loss td.score{background:rgba(192,32,43,.06);}
.it-table tbody tr:hover td{background:rgba(0,0,0,.025);}
.it-table tfoot td{padding:6px 7px;text-align:center;background:var(--kub-dark);color:white;font-weight:800;font-size:11px;}
.it-table tfoot td.l{text-align:left;}
.note{font-size:9px;color:var(--muted);margin-top:8px;line-height:1.5;}
.cards{display:flex;gap:12px;margin-bottom:6px;flex-wrap:wrap;}
.card{flex:1;min-width:110px;border:1px solid var(--rule);border-radius:var(--radius);background:white;padding:11px;text-align:center;}
.card .big{font-size:26px;font-weight:900;color:var(--kub-dark);line-height:1;}
.card .sub{font-size:9px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);margin-top:6px;}
/* penalty page */
.pen-cols{display:flex;gap:22px;align-items:flex-start;flex-wrap:wrap;}
.pen-col{flex:1;min-width:300px;}
.pen-bar-row{display:flex;align-items:center;gap:8px;margin-bottom:5px;}
.pen-bar-label{font-size:11px;min-width:150px;color:var(--ink);}
.pen-bar-track{flex:1;height:14px;background:#e8e4dc;border-radius:7px;overflow:hidden;}
.pen-bar-fill{height:100%;border-radius:7px;background:var(--kub-red);}
.pen-bar-num{font-size:11px;font-weight:800;min-width:22px;text-align:right;}
.stack{display:flex;height:34px;border-radius:5px;overflow:hidden;margin:6px 0 4px;font-size:12px;font-weight:800;color:white;}
.stack .seg{display:flex;align-items:center;justify-content:center;}
.stack .att{background:var(--kub-gold);color:#3a2a08;}
.stack .def{background:var(--kub-mid);}
.qbox-row{display:flex;gap:10px;margin-top:6px;}
.qbox{flex:1;text-align:center;background:#f8f6f2;border:1px solid var(--rule);border-radius:var(--radius);padding:10px 4px;}
.qbox .num{font-size:24px;font-weight:900;color:var(--kub-dark);}
.qbox .lbl{font-size:9px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);margin-top:4px;}
.vbar-chart{display:flex;align-items:flex-end;gap:14px;height:130px;padding:6px 4px 0;border-bottom:2px solid var(--rule);}
.vbar-col{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;height:100%;}
.vbar-num{font-size:13px;font-weight:800;color:var(--kub-dark);margin-bottom:3px;}
.vbar{width:70%;max-width:46px;background:var(--kub-red);border-radius:3px 3px 0 0;}
.vbar-lbl{font-size:10px;font-weight:700;color:var(--muted);margin-top:5px;text-transform:uppercase;}
/* individual ranking table */
.rank-wrap{overflow-x:auto;}
.rank-table{width:100%;border-collapse:collapse;font-size:11px;}
.avg-table td.delta.pos{color:var(--good);} .avg-table td.delta.neg{color:var(--loss);}
.rank-table thead th{padding:6px 5px;background:var(--kub-dark);color:white;font-size:9px;font-weight:700;
  letter-spacing:.02em;text-transform:uppercase;white-space:normal;line-height:1.15;vertical-align:bottom;text-align:center;border-right:1px solid rgba(255,255,255,.08);min-width:40px;}
.rank-table thead th.l{min-width:auto;}
.rank-table thead th.l{text-align:left;}
.rank-table tbody td{padding:4px 6px;text-align:center;border-bottom:1px solid var(--rule);font-weight:600;white-space:nowrap;}
.rank-table tbody td.shirt{background:#f0ede8;font-weight:800;}
.rank-table tbody td.name{text-align:left;font-weight:700;min-width:140px;}
.rank-table tbody td.pos{text-align:left;color:var(--muted);font-size:10px;min-width:96px;}
.rank-table tbody tr:hover td{background:rgba(0,0,0,.025);}
.rank-table tbody tr:nth-child(-n+3) td.name{color:var(--kub-red);}
.rank-table tfoot td{padding:6px;background:var(--kub-dark);color:white;font-weight:800;text-align:center;}
.rank-table tfoot td.l{text-align:left;}
.cell-good{color:var(--good);font-weight:800;} .cell-warn{color:var(--warn);font-weight:800;} .cell-dim{color:#bbb;}
.mini-table{width:100%;border-collapse:collapse;font-size:11px;max-width:420px;}
.mini-table th{padding:5px 8px;background:var(--kub-mid);color:white;font-size:9.5px;text-transform:uppercase;text-align:left;}
.mini-table td{padding:4px 8px;border-bottom:1px solid var(--rule);}
.mini-table td.n{text-align:right;font-weight:800;}
</style></head>
<body>
<div class="shell">
  <div class="page-header">
    <div>
      <div class="subtitle">Japan Rugby League One D1 · Season 2026</div>
      <h1 id="h-title">Kubota Spears — Season KPI Report</h1>
      <div class="rec" id="h-rec"></div>
    </div>
    <div class="record-pill" id="h-pill"></div>
  </div>
  <div class="tabs" id="tabs"></div>
  <div id="panels"></div>
</div>
<script>
const DATA = REPLACE_DATA_HERE;
const G = DATA.groups, M = DATA.matches;
const f1=x=>(Math.round(x*10)/10).toFixed(1);
const f0=x=>Math.round(x).toString();
const f2=x=>(Math.round(x*100)/100).toFixed(2);
const fmtDate=d=>{const[y,m,da]=d.split('-');return da+'/'+m;};

document.getElementById('h-rec').textContent =
  `${DATA.n} matches · ${DATA.nw}W–${DATA.nl}L · PF ${DATA.pf_tot} / PA ${DATA.pa_tot} (${DATA.pf_tot-DATA.pa_tot>=0?'+':''}${DATA.pf_tot-DATA.pa_tot})`;
document.getElementById('h-pill').textContent = `${DATA.nw}–${DATA.nl}`;

// KPI rows for the avg-table: [key,label,note,fmt,goodHigh]
// goodHigh: true => higher is better (delta W-L positive=green)
function avgTable(rows){
  const head=`<thead><tr><th class="k">KPI</th><th class="win">Win avg (${DATA.nw})</th>
    <th class="loss">Loss avg (${DATA.nl})</th><th>Season avg (${DATA.n})</th><th>Δ Win–Loss</th></tr></thead>`;
  const body=rows.map(([k,lbl,note,fmt,gh])=>{
    const w=G.win[k], l=G.loss[k], s=G.season[k];
    const d=w-l;
    const dcls=(gh?d>=0:d<=0)?'pos':'neg';
    const F=fmt===2?f2:fmt===0?f0:f1;
    const suf=(''+lbl).includes('%')?'%':'';
    return `<tr>
      <td class="k">${lbl}<small>${note}</small></td>
      <td class="win">${F(w)}${suf}</td>
      <td class="loss">${F(l)}${suf}</td>
      <td>${F(s)}${suf}</td>
      <td class="delta ${dcls}">${d>=0?'+':''}${F(d)}${suf}</td>
    </tr>`;}).join('');
  return `<table class="avg-table">${head}<tbody>${body}</tbody></table>`;
}

function itTable(cols, foot){
  const head=`<thead><tr>${cols.map(c=>`<th class="${c.l?'l':''} ${c.hcls||''}">${c.h}</th>`).join('')}</tr></thead>`;
  const body=M.map(r=>`<tr class="${r.result==='W'?'win':r.result==='L'?'loss':''}">
    ${cols.map(c=>`<td class="${c.cls?c.cls:''}">${c.fn(r)}</td>`).join('')}</tr>`).join('');
  const tf=foot?`<tfoot><tr>${foot.map(c=>`<td class="${c.l?'l':''}">${c.v}</td>`).join('')}</tr></tfoot>`:'';
  return `<div class="it-wrap"><table class="it-table">${head}<tbody>${body}</tbody>${tf}</table></div>`;
}

const baseCols=[
  {h:'Date',l:1,cls:'l date',fn:r=>fmtDate(r.date)},
  {h:'Home / Away',fn:r=>r.ha},
  {h:'Opponent',l:1,cls:'l',fn:r=>r.opp},
  {h:'Score',cls:'score',fn:r=>`${r.kub}–${r.opp_score}`},
  {h:'Result',cls:'res',fn:r=>r.result},
];

const TABS=[
 {id:'overview',title:'Overview',build:()=>{
   const cards=[
     [`${DATA.nw}–${DATA.nl}`,'Record'],
     [`${f1(G.season.pf)}`,'Pts For/g'],
     [`${f1(G.season.pa)}`,'Pts Against/g'],
     [`${f1(G.season.bip)}'`,'Ball In Play/g'],
     [`${f1(G.season.poss)}%`,'Possession'],
     [`${f1(G.season.terr)}%`,'Territory'],
   ].map(([b,s])=>`<div class="card"><div class="big">${b}</div><div class="sub">${s}</div></div>`).join('');
   const avg=avgTable([
     ['pf','Points For','per match',1,true],
     ['pa','Points Against','per match',1,false],
     ['bip','Ball In Play','minutes/match (both teams)',1,true],
     ['poss','Possession %','Kubota attack time ÷ total',1,true],
     ['terr','Territory %','action-time in opp half (x 51–110)',1,true],
     ['tries','Tries Scored','per match',1,true],
     ['tries_con','Tries Conceded','per match',1,false],
     ['trate','Turnover Rate %','TO conceded ÷ attacks',1,false],
     ['pen','Penalties Conceded','per match',1,false],
   ]);
   const it=itTable(baseCols.concat([
     {h:'Ball In Play (min)',fn:r=>f1(r.at_tot/60)},
     {h:'Possession %',fn:r=>f1(r.at_kub/r.at_tot*100)},
     {h:'Territory %',fn:r=>r.terr_den?f1(r.terr_num/r.terr_den*100):'-'},
     {h:'Tries Scored',fn:r=>r.tries},
     {h:'Turnover Rate %',fn:r=>f1(r.to_con/r.attacks*100)},
   ]));
   return `<div class="cards">${cards}</div>
     <div class="sec-title">Win / Loss / Season — averages</div>${avg}
     <div class="sec-title">Match-by-match</div>${it}
     <div class="note">Territory % = Kubota action-time (ps_endstamp−ps_timestamp, summed over all Kubota events with a duration)
       in the opposition half (x_coord 51–110) ÷ total action-time (x_coord −10–110). Computed from Kubota's perspective.</div>`;
 }},
 {id:'kicking',title:'Kicking Game',build:()=>{
   const avg=avgTable([
     ['kicks','Kicks In Play','per match',1,null],
     ['km','Kick Metres','per match',0,null],
     ['avg_kick','Avg m / Kick','metres ÷ kicks',1,null],
     ['r2k','Ruck : Kick Ratio','rucks ÷ kicks',2,null],
     ['regain','Kick Regain','Own Player – Collected /match',1,true],
     ['hg','Kick Hit Grass','Collected Bounce /match',1,null],
     ['gk_pct','Goal Kicking %','goals ÷ attempts',1,true],
     ['trate','Turnover Rate %','TO conceded ÷ attacks',1,false],
   ]);
   const it=itTable(baseCols.concat([
     {h:'Ball In Play (min)',fn:r=>f1(r.at_tot/60)},
     {h:'Possession %',fn:r=>f1(r.at_kub/r.at_tot*100)},
     {h:'Territory %',fn:r=>r.terr_den?f1(r.terr_num/r.terr_den*100):'-'},
     {h:'Kicks In Play',fn:r=>r.kicks},
     {h:'Kick Metres',fn:r=>r.km},
     {h:'Avg Metres / Kick',fn:r=>r.kicks?f1(r.km/r.kicks):'-'},
     {h:'Ruck : Kick Ratio',fn:r=>r.kicks?f2(r.rucks/r.kicks):'-'},
     {h:'Kick Regain',fn:r=>r.regain},
     {h:'Kick Hit Grass',fn:r=>r.hg},
     {h:'Turnover Rate %',fn:r=>f1(r.to_con/r.attacks*100)},
   ]));
   return `<div class="sec-title">Win / Loss / Season — averages</div>${avg}
     <div class="sec-title">Match-by-match</div>${it}
     <div class="note">Kick Regain = kicking team recollects (Own Player – Collected). Kick Hit Grass = Collected Bounce only
       (kick-in-touch-on-bounce excluded). GK% = (Conv+PG+DG made) ÷ attempts.</div>`;
 }},
 {id:'attack',title:'Attack',build:()=>{
   const avg=avgTable([
     ['carries','Ball Carries','per match',1,null],
     ['metres','Carry Metres','per match',0,true],
     ['gl','Gainline %','carries crossing gainline',1,true],
     ['lqb','LQB %','rucks ≤3s (Lightning Quick Ball)',1,true],
     ['offloads','Offloads','successful (to own player)',1,true],
     ['e22','22m Entries','per match',1,true],
     ['s22','22m Success','Try or Penalty won /match',1,true],
     ['s22_pct','22m Success %','success ÷ entries',1,true],
     ['to_con','Turnovers Conceded','per match',1,false],
   ]);
   const it=itTable(baseCols.concat([
     {h:'Ball Carries',fn:r=>r.carries},
     {h:'Carry Metres',fn:r=>r.metres},
     {h:'Gainline %',fn:r=>r.carries?f1(r.glo/r.carries*100):'-'},
     {h:'LQB %',fn:r=>r.rucks?f1(r.lqb_n/r.rucks*100):'-'},
     {h:'Offloads',fn:r=>r.offloads},
     {h:'22m Entries',fn:r=>r.e22},
     {h:'22m Success',fn:r=>r.s22},
     {h:'22m Success %',fn:r=>r.e22?f0(r.s22/r.e22*100)+'%':'-'},
     {h:'Turnovers Conceded',fn:r=>r.to_con},
   ]));
   return `<div class="sec-title">Win / Loss / Season — averages</div>${avg}
     <div class="sec-title">Match-by-match</div>${it}
     <div class="note">Gainline % = carries tagged 'Crossed Gain line' ÷ all carries. LQB % = rucks with ruck-speed ≤3s.
       22m Success = entries whose outcome was a Try or a won penalty (Penalty Conceded by opponent).</div>`;
 }},
 {id:'defence',title:'Defence',build:()=>{
   const avg=avgTable([
     ['tack_att','Tackle Attempts','per match',1,null],
     ['tack_pct','Tackle %','made ÷ attempted',1,true],
     ['dom_pct','Dominant Tackle %','dominant ÷ tackles made',1,true],
     ['tw','Turnovers Won','Poss TO + Jackal /match',1,true],
     ['pen','Penalties Conceded','per match',1,false],
   ]);
   const it=itTable(baseCols.concat([
     {h:'Tackles Made',fn:r=>r.tk},
     {h:'Tackles Missed',fn:r=>r.mt},
     {h:'Tackle Attempts',fn:r=>r.tk+r.mt},
     {h:'Tackle %',fn:r=>(r.tk+r.mt)?f1(r.tk/(r.tk+r.mt)*100):'-'},
     {h:'Dominant Tackle %',fn:r=>r.tk?f1(r.dom/r.tk*100):'-'},
     {h:'Turnovers Won',fn:r=>r.tw},
     {h:'Infringements',fn:r=>r.pen},
     {h:'Opponent Gainline %',hcls:'opp',cls:'oppcol',fn:r=>r.opp_carries?f1(r.opp_glo/r.opp_carries*100):'-'},
     {h:'Opponent LQB %',hcls:'opp',cls:'oppcol',fn:r=>r.opp_rucks?f1(r.opp_lqb/r.opp_rucks*100):'-'},
     {h:'Tries Conceded',hcls:'opp',cls:'oppcol',fn:r=>r.tries_conceded},
     {h:'Opponent 22m Entries',hcls:'opp',cls:'oppcol',fn:r=>r.opp_e22},
     {h:'Opponent 22m Success',hcls:'opp',cls:'oppcol',fn:r=>r.opp_s22},
   ]));
   return `<div class="sec-title">Win / Loss / Season — averages</div>${avg}
     <div class="sec-title">Match-by-match</div>${it}
     <div class="note">Tackle % = tackles made ÷ (made+missed). Dominant Tackle % = qualifier 'Dominant Tackle' ÷ tackles made.
       Turnovers Won = Possession 'Turnover Won' + Jackal success (events within 0.5 match-min de-duplicated).
       <span style="color:#c4600f;font-weight:700">Orange columns = opponent stats</span>: Gainline % / LQB % / Tries scored vs Kubota /
       22m Entries / 22m Success (Try or penalty won) by the opposition.</div>`;
 }},
 {id:'setpiece',title:'Set Piece',build:()=>{
   const avg=avgTable([
     ['lo_won','Lineout Won','per match',1,true],
     ['lo_lost','Lineout Lost','per match',1,false],
     ['lo_pct','Lineout Win %','won ÷ throws',1,true],
     ['lo_steal','Lineout Steals','opp throw stolen /match',1,true],
     ['sc_tot','Scrums','per match',1,null],
     ['sc_reset','Scrum Resets','per match',1,false],
     ['sc_pct','Scrum Win %','won ÷ scrums',1,true],
     ['ma_tot','Mauls','per match',1,null],
     ['ma_try','Maul Tries','per match',1,true],
     ['ma_m','Maul Metres','per match',0,true],
   ]);
   const it=itTable(baseCols.concat([
     {h:'Lineouts Won',fn:r=>r.lo_won},{h:'Lineouts Lost',fn:r=>r.lo_lost},
     {h:'Lineout Win %',fn:r=>r.lo_throw?f0(r.lo_won/r.lo_throw*100)+'%':'-'},
     {h:'Lineout Steals',fn:r=>r.lo_steal},
     {h:'Scrums',fn:r=>r.sc_tot},{h:'Scrum Resets',fn:r=>r.sc_reset},
     {h:'Scrum Win %',fn:r=>r.sc_tot?f0(r.sc_won/r.sc_tot*100)+'%':'-'},
     {h:'Mauls',fn:r=>r.ma_tot},{h:'Maul Tries',fn:r=>r.ma_try},{h:'Maul Metres',fn:r=>r.ma_m},
   ]));
   const th=DATA.lineout_throwers.map(p=>`<tr><td>${p.name}</td><td class="pos">${p.pos}</td>
     <td class="n">${p.tot}</td><td class="n" style="color:var(--good)">${p.won}</td>
     <td class="n" style="color:var(--loss)">${p.lost}</td><td class="n">${p.pct}%</td></tr>`).join('');
   const lp=DATA.lineout_players.map(p=>`<tr><td>${p.name}</td><td class="pos">${p.pos}</td><td class="n">${p.won}</td></tr>`).join('');
   return `<div class="sec-title">Win / Loss / Season — averages</div>${avg}
     <div class="sec-title">Match-by-match</div>${it}
     <div style="display:flex;gap:30px;flex-wrap:wrap;margin-top:4px">
       <div style="flex:1;min-width:380px">
         <div class="sec-title">Thrower success rate (season)</div>
         <table class="mini-table" style="max-width:none"><thead><tr><th>Thrower</th><th>Position</th>
           <th style="text-align:right">Thrown</th><th style="text-align:right">Won</th>
           <th style="text-align:right">Lost</th><th style="text-align:right">Win%</th></tr></thead>
         <tbody>${th}</tbody></table>
       </div>
       <div style="flex:1;min-width:300px">
         <div class="sec-title">Lineout claims by player (season)</div>
         <table class="mini-table"><thead><tr><th>Player</th><th>Position</th><th style="text-align:right">LO Won</th></tr></thead><tbody>${lp}</tbody></table>
       </div>
     </div>
     <div class="note">Thrower Win% = that player's Lineout Throws won ÷ thrown (Won* / Lost* outcomes). Steals = own team winning the
       opposition throw (Lineout Take 'Lineout Steal*'). Maul Metres uses the <code>metres</code> column on Maul events.</div>`;
 }},
 {id:'penalty',title:'Penalty',build:()=>{
   const P=DATA.penalty, max=Math.max(...P.types.map(t=>t[1]),1);
   const bars=P.types.map(([t,n])=>`<div class="pen-bar-row">
     <span class="pen-bar-label">${t}</span>
     <div class="pen-bar-track"><div class="pen-bar-fill" style="width:${Math.round(n/max*100)}%"></div></div>
     <span class="pen-bar-num">${n}</span></div>`).join('');
   const att=P.od.Offence, def=P.od.Defence, odtot=att+def||1;
   const stack=`<div class="stack">
     <div class="seg att" style="width:${att/odtot*100}%">Attack ${att}</div>
     <div class="seg def" style="width:${def/odtot*100}%">Defence ${def}</div></div>`;
   const qmax=Math.max(...['Q1','Q2','Q3','Q4'].map(q=>P.quarter[q]),1);
   const qb=['Q1','Q2','Q3','Q4'].map(q=>`<div class="vbar-col">
     <div class="vbar-num">${P.quarter[q]}</div>
     <div class="vbar" style="height:${Math.round(P.quarter[q]/qmax*96)+4}px"></div>
     <div class="vbar-lbl">${q}</div></div>`).join('');
   const ht=(P.half.H1+P.half.H2)||1;
   const hb=`<div class="stack" style="height:38px">
     <div class="seg att" style="width:${P.half.H1/ht*100}%">1st Half &nbsp;${P.half.H1} (${Math.round(P.half.H1/ht*100)}%)</div>
     <div class="seg def" style="width:${P.half.H2/ht*100}%">2nd Half &nbsp;${P.half.H2} (${Math.round(P.half.H2/ht*100)}%)</div></div>`;
   const cards=[[`${P.total}`,'Total Infringements'],[`${f1(G.season.pen)}`,'Per Match'],
     [`${att}`,'In Attack'],[`${def}`,'In Defence']]
     .map(([b,s])=>`<div class="card"><div class="big">${b}</div><div class="sub">${s}</div></div>`).join('');
   // league comparison (per match)
   const Lg=DATA.league;
   const cmp=[
     ['Infringements / match', P.total/DATA.n, Lg.infr],
     ['Full Penalties / match', P.full/DATA.n, Lg.full],
     ['Free Kicks / match', P.fk/DATA.n, Lg.fk],
     ['In Attack / match', att/DATA.n, Lg.att],
     ['In Defence / match', def/DATA.n, Lg.def],
   ];
   const cmpRows=cmp.map(([lbl,k,l])=>{
     const d=k-l; const cls=d<=0?'pos':'neg';  // fewer infringements = good
     return `<tr><td class="k">${lbl}</td><td>${f1(k)}</td><td>${f1(l)}</td>
       <td class="delta ${cls}">${d>=0?'+':''}${f1(d)}</td></tr>`;}).join('');
   const cmpTable=`<table class="avg-table"><thead><tr><th class="k">Metric</th>
     <th>Kubota</th><th>League avg</th><th>Δ vs League</th></tr></thead><tbody>${cmpRows}</tbody></table>`;
   return `<div class="cards">${cards}</div>
     <div class="sec-title">Kubota vs League average (per match)</div>${cmpTable}
     <div class="pen-cols">
       <div class="pen-col">
         <div class="sec-title">By Type (season total)</div>${bars}
       </div>
       <div class="pen-col">
         <div class="sec-title">Attack vs Defence (qualifier3)</div>${stack}
         <div class="sec-title">By Half</div>${hb}
         <div class="sec-title">By Quarter</div><div class="vbar-chart">${qb}</div>
       </div>
     </div>
     <div class="note">Infringements = Penalty Conceded (Full Penalty ${P.full} + Free Kick ${P.fk} = ${P.total}).
       League avg = all ${Lg.tm} team-matches in rugby.db (12 teams × Kubota's ${DATA.n} fixtures); Δ negative = fewer than league (better).
       Attack/Defence from qualifier3. Quarters from match-minute (Q1≤20', Q2≤40', Q3≤60', Q4&gt;60').</div>`;
 }},
 {id:'ind-attack',title:'Indiv Attack',build:()=>{
   const R=DATA.players_attack;
   const tot=R.reduce((a,r)=>{['carries','metres','glo_x','lb','db','ol','tries','err','passes','pass_acc_n','kicks','kick_m','ooa13','ooa4'].forEach(k=>a[k]=(a[k]||0)+(r[k]||0));return a;},{});
   // recompute weighted totals needing raw: gl% and acc% from components
   const totGlo=R.reduce((s,r)=>s+Math.round(r.gl/100*r.carries),0);
   const totAccN=R.reduce((s,r)=>s+Math.round(r.pass_acc/100*r.passes),0);
   const totOOA=tot.ooa13+tot.ooa4;
   const rows=R.map(r=>`<tr>
     <td class="shirt">${r.shirt}</td><td class="name">${r.name}</td><td class="pos">${r.pos}</td><td>${r.pt}</td>
     <td>${r.carries}</td><td>${r.metres}</td><td>${r.avg}</td>
     <td class="${r.gl>=60?'cell-good':r.gl&&r.gl<45?'cell-warn':''}">${r.carries?r.gl+'%':'-'}</td>
     <td class="${r.lb?'cell-good':'cell-dim'}">${r.lb||'-'}</td>
     <td>${r.db||'-'}</td><td>${r.ol||'-'}</td>
     <td class="${r.tries?'cell-good':'cell-dim'}">${r.tries||'-'}</td>
     <td class="${r.err>=20?'cell-warn':''}">${r.err||'-'}</td>
     <td>${r.passes||'-'}</td><td>${r.passes?r.pass_acc+'%':'-'}</td>
     <td>${r.kicks||'-'}</td><td>${r.kick_m||'-'}</td><td>${r.kicks?r.avg_kick:'-'}</td>
     <td>${r.ooa13||'-'}</td><td>${r.ooa4||'-'}</td>
     <td class="${(r.ooa13+r.ooa4)?(r.ooa_eff>=70?'cell-good':r.ooa_eff<55?'cell-warn':''):'cell-dim'}">${(r.ooa13+r.ooa4)?r.ooa_eff+'%':'-'}</td></tr>`).join('');
   return `<div class="sec-title">Individual Attack — season totals (ranked by carries)</div>
     <div class="rank-wrap"><table class="rank-table">
       <thead><tr><th>No.</th><th class="l">Name</th><th class="l">Position</th><th>Play Time (min)</th>
         <th>Ball Carries</th><th>Carry Metres</th><th>Avg Metres / Carry</th><th>Gainline %</th>
         <th>Linebreaks</th><th>Defenders Beaten</th><th>Offloads</th><th>Tries</th><th>Errors</th>
         <th>Passes</th><th>Pass Accuracy %</th><th>Kicks In Play</th><th>Kick Metres</th><th>Avg Kick Metres</th>
         <th>OOA 1-3s</th><th>OOA 4+s</th><th>OOA Effectiveness %</th></tr></thead>
       <tbody>${rows}</tbody>
       <tfoot><tr><td></td><td class="l">TOTAL (${R.length} players)</td><td></td><td></td>
         <td>${tot.carries}</td><td>${tot.metres}</td><td>${(tot.metres/tot.carries).toFixed(1)}</td>
         <td>${(totGlo/tot.carries*100).toFixed(1)}%</td>
         <td>${tot.lb}</td><td>${tot.db}</td><td>${tot.ol}</td><td>${tot.tries}</td><td>${tot.err}</td>
         <td>${tot.passes}</td><td>${(totAccN/tot.passes*100).toFixed(1)}%</td>
         <td>${tot.kicks}</td><td>${tot.kick_m}</td><td>${(tot.kick_m/tot.kicks).toFixed(1)}</td>
         <td>${tot.ooa13}</td><td>${tot.ooa4}</td><td>${(tot.ooa13/totOOA*100).toFixed(1)}%</td></tr></tfoot>
     </table></div>
     <div class="note">Avg/C = metres ÷ carries · GL% = carries crossing the gainline ÷ carries · LB = Linebreaks · DB = Defenders Beaten ·
       OL = Offloads (to own player) · Err = Turnovers conceded · Acc% = passes not Incomplete/Error/Forward/Intercepted/Off-Target ·
       OOA 1-3 / 4+ = ruck (breakdown) speed ≤3s / &gt;3s from action 'Ruck' speed buckets · OOA Eff% = 1-3 ÷ (1-3 + 4+).
       <b>Handling Count: データなし</b>（DBに該当フィールドなし）.</div>`;
 }},
 {id:'ind-defence',title:'Indiv Defence',build:()=>{
   const R=DATA.players_defence;
   const tot=R.reduce((a,r)=>{['tk','mt','att','dom','passive','oa','legs','ht_tot','jck','tow','pen'].forEach(k=>a[k]=(a[k]||0)+(r[k]||0));return a;},{});
   const rows=R.map(r=>`<tr>
     <td class="shirt">${r.shirt}</td><td class="name">${r.name}</td><td class="pos">${r.pos}</td><td>${r.pt}</td>
     <td>${r.att}</td><td>${r.tk}</td><td class="${r.mt>=20?'cell-warn':''}">${r.mt}</td>
     <td class="${r.pct>=90?'cell-good':r.pct<75?'cell-warn':''}">${r.pct}%</td>
     <td>${r.ht_tot?r.leg_pct+'%':'-'}</td>
     <td class="${r.dom?'cell-good':'cell-dim'}">${r.dom||'-'}</td>
     <td>${r.att?r.dom_pct+'%':'-'}</td>
     <td>${r.passive||'-'}</td>
     <td class="${r.oa>=10?'cell-warn':''}">${r.oa||'-'}</td>
     <td class="${r.jck?'cell-good':'cell-dim'}">${r.jck||'-'}</td>
     <td class="${r.tow?'cell-good':'cell-dim'}">${r.tow||'-'}</td>
     <td class="${r.pen>=12?'cell-warn':''}">${r.pen||'-'}</td></tr>`).join('');
   return `<div class="sec-title">Individual Defence — season totals (ranked by tackles made)</div>
     <div class="rank-wrap"><table class="rank-table">
       <thead><tr><th>No.</th><th class="l">Name</th><th class="l">Position</th><th>Play Time (min)</th>
         <th>Tackle Attempts</th><th>Tackles Made</th><th>Tackles Missed</th><th>Tackle %</th><th>Leg Tackle %</th>
         <th>Dominant Tackles</th><th>Dominant Tackle %</th><th>Passive Tackles</th><th>Offloads Allowed</th>
         <th>Jackal Success</th><th>Turnovers Won</th><th>Infringements</th></tr></thead>
       <tbody>${rows}</tbody>
       <tfoot><tr><td></td><td class="l">TOTAL (${R.length} players)</td><td></td><td></td>
         <td>${tot.att}</td><td>${tot.tk}</td><td>${tot.mt}</td>
         <td>${(tot.tk/tot.att*100).toFixed(1)}%</td>
         <td>${(tot.legs/tot.ht_tot*100).toFixed(1)}%</td>
         <td>${tot.dom}</td><td>${(tot.dom/tot.att*100).toFixed(1)}%</td>
         <td>${tot.passive}</td><td>${tot.oa}</td><td>${tot.jck}</td><td>${tot.tow}</td>
         <td>${tot.pen}</td></tr></tfoot>
     </table></div>
     <div class="note">Att/Made/Miss tackles · Tkl% = made ÷ att · Leg% = leg tackles ÷ tackles with height tag (qualifier6) ·
       Dom% = dominant ÷ att · Passive = passive tackles · OA = offloads allowed (own tackle) · Jackal = Collection/Jackal success ·
       <b>Turnovers Won = tackle turnovers (Tackle/Turnover Won) + breakdown penalties won (Ruck OOA/Penalty Won)</b> ·
       Infringements = Penalties + Free Kicks conceded.</div>`;
 }},
];

const tabsEl=document.getElementById('tabs'), panelsEl=document.getElementById('panels');
TABS.forEach((t,i)=>{
  const b=document.createElement('button');
  b.className='tab-btn'+(i===0?' active':''); b.textContent=t.title; b.dataset.id=t.id;
  b.onclick=()=>{
    document.querySelectorAll('.tab-btn').forEach(x=>x.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(x=>x.classList.remove('active'));
    b.classList.add('active'); document.getElementById('panel-'+t.id).classList.add('active');
  };
  tabsEl.appendChild(b);
  const p=document.createElement('div');
  p.className='tab-panel'+(i===0?' active':''); p.id='panel-'+t.id; p.innerHTML=t.build();
  panelsEl.appendChild(p);
});
</script>
</body></html>"""

html = TEMPLATE.replace("REPLACE_DATA_HERE", json.dumps(DATA, ensure_ascii=False))
with open(OUT, "w", encoding="utf-8") as fh:
    fh.write(html)

g = groups["season"]
print(f"Wrote {OUT}")
print(f"Season: BIP {g['bip']:.1f}min  Poss {g['poss']:.1f}%  Terr {g['terr']:.1f}%  "
      f"Tackle {g['tack_pct']:.1f}%  Dom {g['dom_pct']:.1f}%")
print(f"Win Terr {groups['win']['terr']:.1f}% vs Loss Terr {groups['loss']['terr']:.1f}%")
