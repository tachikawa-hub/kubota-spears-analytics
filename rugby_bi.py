#!/usr/bin/env python3
"""
rugby_bi.py — Kubota Spears BI Analytics Suite
================================================
Sub-commands:
  build  — Build rugby.db from CSV data
  match  — Generate match report HTML
  scout  — Generate scouting report HTML
  kpi    — Generate season KPI summary HTML
  all    — Run build + kpi

Usage:
  python3 rugby_bi.py build --data "./BI Scouting"
  python3 rugby_bi.py match --round 22
  python3 rugby_bi.py scout --home "Kubota Spears" --opp "Kobelco Kobe Steelers" --round 22 --data "./BI Scouting"
  python3 rugby_bi.py kpi

Confirmed KPI definitions (all reports unified):
  Attack Time     = Possession + Scrum + Lineout Throw duration
  Ball in Play    = Attack Time + Goal Kick + Restart duration
  Territory %     = Poss+Scrum+LO x_coord>50 time share
  Kicks in Play   = qualifier3 in ('Kick in Play','Kick in Play (Own 22)')
  Scrum Won %     = Won / (Total - Reset)
  22m Entries     = Possession qualifier4 'Enters into Opposition 22' + 'Starts inside Opposition 22'
  Carried into 22m= Possession qualifier4 'Enters into Opposition 22'
  Started in 22m  = Possession qualifier4 'Starts inside Opposition 22'
  # 旧:  Contest Ret %   = Contest kicks (Bomb/Low/Chip/Cross Pitch) regained
  Contest Retained = Contest kicks 5種 (Bomb/Low/Chip/Cross Pitch/Box); retain = Own Player - Collected / Pressure Error / Pressure in Touch / Try Kick
  TO Won          = 6 elements
"""
import argparse, glob, json, os, re, sqlite3, sys
from statistics import mean

try:
    import pandas as pd
    import numpy as np
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False


# ═══════════════════════════════════════════════════════════════
# SHARED DEFINITIONS
# ═══════════════════════════════════════════════════════════════

TEAM = "Kubota Spears"
DB   = "rugby.db"
MATCH_TEMPLATE = "match_report_template.html"

TEAM_ABBR_MAP = {
    'Kubota Spears': 'KUB', 'Kobelco Kobe Steelers': 'KOB',
    'Tokyo Sungoliath': 'SUN', 'Saitama Wild Knights': 'PAN',
    'Toyota Verblitz': 'TOY', 'Urayasu D-Rocks': 'UDR',
    'Mie Honda Heat': 'HND', 'Mitsubishi Sagamihara Dynaboars': 'DYN',
    'BlackRams Tokyo': 'BRT', 'Yokohama Canon Eagles': 'YCE',
    'Shizuoka BlueRevs': 'SBR', 'Toshiba Brave Lupus Tokyo': 'TOH',
}
TEAM_COLORS = {
    'BlackRams Tokyo':'#1a1a1a','Kobelco Kobe Steelers':'#DC2626',
    'Kubota Spears':'#F97316','Mie Honda Heat':'#4B5563',
    'Mitsubishi Sagamihara Dynaboars':'#16A34A','Saitama Wild Knights':'#2563EB',
    'Shizuoka BlueRevs':'#38BDF8','Tokyo Sungoliath':'#EAB308',
    'Toshiba Brave Lupus Tokyo':'#DC2626','Toyota Verblitz':'#15803D',
    'Urayasu D-Rocks':'#1E3A8A','Yokohama Canon Eagles':'#EF4444',
}
TEAM_SHORT = {
    'BlackRams Tokyo':'BlackRams','Kobelco Kobe Steelers':'Steelers',
    'Kubota Spears':'Spears','Mie Honda Heat':'Heat',
    'Mitsubishi Sagamihara Dynaboars':'Dynaboars','Saitama Wild Knights':'WildKnights',
    'Shizuoka BlueRevs':'BlueRevs','Tokyo Sungoliath':'Sungoliath',
    'Toshiba Brave Lupus Tokyo':'BraveLupus','Toyota Verblitz':'Verblitz',
    'Urayasu D-Rocks':'D-Rocks','Yokohama Canon Eagles':'Eagles',
}
TEAM_BADGE = {
    'BlackRams Tokyo':'BR','Kobelco Kobe Steelers':'KS','Kubota Spears':'KS',
    'Mie Honda Heat':'MH','Mitsubishi Sagamihara Dynaboars':'MD',
    'Saitama Wild Knights':'WK','Shizuoka BlueRevs':'BR','Tokyo Sungoliath':'SG',
    'Toshiba Brave Lupus Tokyo':'BL','Toyota Verblitz':'TV',
    'Urayasu D-Rocks':'DR','Yokohama Canon Eagles':'YE',
}
POS_GROUP = {
    "Loosehead Prop":"Front Row","Hooker":"Front Row","Tighthead Prop":"Front Row",
    "Lock (4)":"Lock","Lock (5)":"Lock","Lock":"Lock",
    "Blindside Flanker":"Loosie","Openside Flanker":"Loosie","Flanker":"Loosie","Number 8":"Loosie",
    "Scrum Half":"Inside","Fly Half":"Inside",
    "Inside Centre":"Midfield","Outside Centre":"Midfield",
    "Left Wing":"Back 3","Right Wing":"Back 3","Wing":"Back 3","Full Back":"Back 3",
}
FW   = ['Loosehead Prop','Hooker','Tighthead Prop','Lock (4)','Lock (5)',
        'Blindside Flanker','Openside Flanker','Number 8']
BK   = ['Scrum Half','Fly Half','Inside Centre','Outside Centre',
        'Left Wing','Right Wing','Full Back']
DEAD = ['Kick in Touch (Full)','Kick in Touch (Bounce)','Error - Out of Play',
        'Error - Dead Ball','Pressure in Touch','In Goal','Try Kick']
GOAL = ['Penalty Goal','Conversion','Drop Goal']
# 旧: CONT = ['Bomb','Low','Chip','Cross Pitch']
CONT = ['Bomb','Low','Chip','Cross Pitch','Box']
TO_S = ['Turnover Won','Lineout Steal','Scrum Steal']
REST = ['50m Restart','50m Restart Retained','Goal Line Restart',
        '22m Restart','22m Restart Retained']
SPD_FAST = ("0-1 Seconds","1-2 Seconds","2-3 Seconds")
SPD_SLOW = ("3-4 Seconds","4-5 Seconds","5-6 Seconds","6+ Seconds")
PASS_BAD = ("Incomplete","Error","Forward","Intercepted","Off Target")

def team_abbr(name):
    return TEAM_ABBR_MAP.get(name, "".join(w[0] for w in name.split()).upper())

def _num(v):
    try: return float(v)
    except (TypeError, ValueError): return 0.0

def match_min(ps, period, p2):
    ps = _num(ps)
    return ps / 60.0 if int(_num(period)) == 1 else 40.0 + (ps - p2) / 60.0

def quarter(mm):
    return "Q1" if mm <= 20 else "Q2" if mm <= 40 else "Q3" if mm <= 60 else "Q4"

def mmss(sec):
    sec = int(round(sec))
    return f"{sec // 60:02d}:{sec % 60:02d}"

# Module-level globals set by cmd_match / cmd_kpi
con = cur = fx = p2 = None

MONTHS = {1:"January",2:"February",3:"March",4:"April",5:"May",6:"June",
          7:"July",8:"August",9:"September",10:"October",11:"November",12:"December"}


# ═══════════════════════════════════════════════════════════════
# SECTION 2: MATCH REPORT
# ═══════════════════════════════════════════════════════════════

def C(fx, team, **conds):
    sql = "SELECT COUNT(*) FROM events WHERE fxid=? AND team_name=?"
    params = [fx, team]
    for k, v in conds.items():
        if isinstance(v, (set, list, tuple)):
            ph = ",".join("?" * len(v))
            sql += f" AND {k} IN ({ph})"
            params += list(v)
        else:
            sql += f" AND {k}=?"
            params.append(v)
    return cur.execute(sql, params).fetchone()[0]


def CL(fx, team, action, col, like):
    return cur.execute(
        f"SELECT COUNT(*) FROM events WHERE fxid=? AND team_name=? AND action_name=? AND {col} LIKE ?",
        (fx, team, action, like)).fetchone()[0]


def SUMM(fx, team, action, col="metres"):
    rows = cur.execute(
        f"SELECT {col} v FROM events WHERE fxid=? AND team_name=? AND action_name=?",
        (fx, team, action)).fetchall()
    return sum(_num(r["v"]) for r in rows)





# ---------------------------------------------------------------------------
# per-team full-match stats (home_stats / away_stats)
# ---------------------------------------------------------------------------
def team_stats(team, opp):
    poss_rows = cur.execute(
        "SELECT team_name tn, ps_timestamp ts, ps_endstamp te "
        "FROM events WHERE fxid=? AND action_name='Possession'", (fx,)
    ).fetchall()
    # Attack Time: Possession + Scrum + Lineout Throw (Optaと一致 MAE=9.4s)
    sc_rows = cur.execute(
        "SELECT team_name tn, ps_timestamp ts, ps_endstamp te "
        "FROM events WHERE fxid=? AND action_name='Scrum'", (fx,)
    ).fetchall()
    lo_rows = cur.execute(
        "SELECT team_name tn, ps_timestamp ts, ps_endstamp te "
        "FROM events WHERE fxid=? AND action_name='Lineout Throw'", (fx,)
    ).fetchall()
    gk_rows = cur.execute(
        "SELECT ps_timestamp ts, ps_endstamp te "
        "FROM events WHERE fxid=? AND action_name='Goal Kick'", (fx,)
    ).fetchall()
    rs_rows = cur.execute(
        "SELECT ps_timestamp ts, ps_endstamp te "
        "FROM events WHERE fxid=? AND action_name='Restart'", (fx,)
    ).fetchall()
    def _dur(rows, team_filter=None):
        return sum(max(0, _num(r["te"]) - _num(r["ts"]))
                   for r in rows if team_filter is None or r.get("tn","") == team_filter)
    poss_dur = sum(_num(r["te"]) - _num(r["ts"]) for r in poss_rows if r["tn"] == team)
    sc_dur   = sum(max(0,_num(r["te"])-_num(r["ts"])) for r in sc_rows if r["tn"]==team)
    lo_dur   = sum(max(0,_num(r["te"])-_num(r["ts"])) for r in lo_rows if r["tn"]==team)
    gk_dur   = sum(max(0,_num(r["te"])-_num(r["ts"])) for r in gk_rows)
    rs_dur   = sum(max(0,_num(r["te"])-_num(r["ts"])) for r in rs_rows)
    at_team  = poss_dur + sc_dur + lo_dur
    # BIP_old = 全Possession + 全Scrum + 全LO + GoalKick + Restart（旧定義・並走用）
    at_tot_poss = sum(max(0,_num(r["te"]) - _num(r["ts"])) for r in poss_rows)
    at_tot_sc   = sum(max(0,_num(r["te"]) - _num(r["ts"])) for r in sc_rows)
    at_tot_lo   = sum(max(0,_num(r["te"]) - _num(r["ts"])) for r in lo_rows)
    bip_total   = at_tot_poss + at_tot_sc + at_tot_lo + gk_dur + rs_dur
    at_tot      = bip_total
    # BIP_v2 = Poss + Scrum + LO のみ（GK・Restart 除外）
    bip_v2      = at_tot_poss + at_tot_sc + at_tot_lo

    # Territory 旧: Possession + Scrum + LO の x_coord(開始座標)>50 割合
    terr_rows = cur.execute(
        "SELECT team_name tn, x_coord x, ps_timestamp ts, ps_endstamp te FROM events "
        "WHERE fxid=? AND team_name=? "
        "AND action_name IN ('Possession','Scrum','Lineout Throw') "
        "AND x_coord IS NOT NULL AND x_coord!='' "
        "AND ps_endstamp IS NOT NULL AND ps_endstamp!=''", (fx, team)
    ).fetchall()
    terr_num = terr_den = 0.0
    for r in terr_rows:
        x = _num(r["x"])
        dur = _num(r["te"]) - _num(r["ts"])
        if dur <= 0:
            continue
        if x > 50:
            terr_num += dur
        terr_den += dur

    # Territory v2: 中点座標 (x_start+x_end)/2 >50 で判定・BIP_v2 分母
    terr_rows_v2 = cur.execute(
        "SELECT x_coord x, x_coord_end xe, ps_timestamp ts, ps_endstamp te FROM events "
        "WHERE fxid=? AND team_name=? "
        "AND action_name IN ('Possession','Scrum','Lineout Throw') "
        "AND ps_endstamp IS NOT NULL AND ps_endstamp!=''", (fx, team)
    ).fetchall()
    terr_num_v2 = terr_den_v2 = 0.0
    for r in terr_rows_v2:
        dur = _num(r["te"]) - _num(r["ts"])
        if dur <= 0:
            continue
        xe = r["xe"]; xs = r["x"]
        if xe and xs:
            coord = (_num(xs) + _num(xe)) / 2
        elif xs:
            coord = _num(xs)
        else:
            coord = None
        if coord is None:
            continue
        if coord > 50:
            terr_num_v2 += dur
        terr_den_v2 += dur

    # TO Won: Ruck OOA TO + Jackal + LO Steal + Scrum Steal + Tackle TO + Forced in Touch（6要素）
    tw = 0
    for r in cur.execute(
        "SELECT action_name an, action_type_name tp, action_result_name rs "
        "FROM events WHERE fxid=? AND team_name=?", (fx, team)
    ).fetchall():
        an, tp, rs = r["an"], r["tp"] or "", r["rs"] or ""
        if an=="Ruck OOA" and tp=="Turnover Won": tw+=1
        elif an=="Collection" and tp=="Jackal" and rs=="Success": tw+=1
        elif an=="Lineout Take" and "Steal" in tp: tw+=1
        elif an=="Sequences" and tp=="Scrum Steal": tw+=1
        elif an=="Tackle" and rs=="Turnover Won": tw+=1
    for r in cur.execute(
        "SELECT action_result_name rs FROM events "
        "WHERE fxid=? AND action_name='Tackle' AND team_name!=? AND action_result_name='Forced in Touch'",
        (fx, team)
    ).fetchall():
        tw += 1

    carries = C(fx, team, action_name="Carry")
    metres = SUMM(fx, team, "Carry")
    otg = C(fx, team, action_name="Carry", qualifier3_name="Crossed Gain line")
    passes = C(fx, team, action_name="Pass")
    linebreaks = C(fx, team, action_name="Attacking Qualities", action_type_name="Initial Break")
    offloads = C(fx, team, action_name="Pass", action_type_name="Offload", action_result_name="Own Player")

    # Kicks in Play: qualifier3_name='Kick in Play' or 'Kick in Play (Own 22)' (Optaと完全一致)
    kip_rows = cur.execute(
        "SELECT metres FROM events WHERE fxid=? AND team_name=? AND action_name='Kick' "
        "AND qualifier3_name IN ('Kick in Play','Kick in Play (Own 22)')", (fx, team)
    ).fetchall()
    kicks = len(kip_rows)
    km = sum(_num(r["metres"]) for r in kip_rows)

    rucks = C(fx, team, action_name="Ruck")
    rucks_won = CL(fx, team, "Ruck", "action_result_name", "Won%")
    lqb_n = C(fx, team, action_name="Ruck", qualifier4_name=SPD_FAST)

    tk = C(fx, team, action_name="Tackle")
    mt = C(fx, team, action_name="Missed Tackle")

    lo_throw = C(fx, team, action_name="Lineout Throw")
    lo_won = CL(fx, team, "Lineout Throw", "action_result_name", "Won%")
    lo_steal = CL(fx, team, "Lineout Take", "action_type_name", "Lineout Steal%")
    sc_tot = C(fx, team, action_name="Scrum")
    penalties = C(fx, team, action_name="Penalty Conceded")
    to_con = C(fx, team, action_name="Turnover")
    e22 = C(fx, team, action_name="Possession",
            qualifier4_name={"Enters into Opposition 22", "Starts inside Opposition 22"})
    c22 = C(fx, team, action_name="Possession", qualifier4_name="Enters into Opposition 22")
    s22 = C(fx, team, action_name="Possession", qualifier4_name="Starts inside Opposition 22")
    tries = C(fx, team, action_name="Try")

    stats = {
        "tries": tries, "passes": passes, "carries": carries, "metres": int(metres),
        "avg_carry": round(metres / carries, 1) if carries else 0.0,
        "linebreaks": linebreaks, "offloads": offloads, "otg": otg,
        "def_beaten": C(fx, team, action_name="Attacking Qualities", action_type_name="Defender Beaten"),
        "kicks": kicks, "kick_m": int(km),
        "avg_kick": round(km / kicks, 1) if kicks else 0.0,
        "rucks": rucks, "ruck_pct": round(rucks_won / rucks * 100, 1) if rucks else 0.0,
        "rucks_won": rucks_won,
        "lqb_pct": round(lqb_n / rucks * 100, 1) if rucks else 0.0,
        "tack_att": tk + mt, "tack_miss": mt,
        "tack_pct": round(tk / (tk + mt) * 100, 1) if (tk + mt) else 0.0,
        "lineouts": lo_throw, "lo_won": lo_won,
        "lo_pct": round(lo_won / lo_throw * 100, 1) if lo_throw else 0.0,
        "lo_steal": lo_steal,
        "scrums": sc_tot, "penalties": penalties,
        "to_won": tw, "to_con": to_con,
        "e22": e22, "c22": c22, "s22": s22,
    }
    return stats, at_team, at_tot, terr_num, terr_den, bip_v2, terr_num_v2, terr_den_v2



# ---------------------------------------------------------------------------
# quarter-by-quarter stats
# ---------------------------------------------------------------------------
def quarter_stats(team, opp):
    Q = {q: {"pts": 0, "tries": 0, "pos_dur": 0.0, "tot_dur": 0.0, "terr_num": 0.0, "terr_den": 0.0,
             "car": 0, "mtr": 0.0, "pas": 0, "rucks": 0, "kicks": 0, "ta": 0, "tm": 0, "lb": 0, "db": 0,
             "tow": 0, "toc": 0, "pen": 0, "e22": 0, "c22": 0, "s22": 0,
             "bip_k": 0.0, "bip_o": 0.0, "atk_k": 0.0, "atk_o": 0.0} for q in ["Q1", "Q2", "Q3", "Q4"]}

    for r in cur.execute(
        "SELECT team_name tn, ps_timestamp ts, ps_endstamp te, period pd "
        "FROM events WHERE fxid=? AND action_name='Possession'", (fx,)
    ).fetchall():
        mm = match_min(r["ts"], r["pd"], p2)
        qq = quarter(mm)
        dur = _num(r["te"]) - _num(r["ts"])
        Q[qq]["tot_dur"] += dur
        if r["tn"] == team:
            Q[qq]["pos_dur"] += dur

    for r in cur.execute(
        "SELECT x_coord x, ps_timestamp ts, ps_endstamp te, period pd FROM events "
        "WHERE fxid=? AND team_name=? AND x_coord IS NOT NULL AND x_coord!='' "
        "AND ps_endstamp IS NOT NULL AND ps_endstamp!=''", (fx, team)
    ).fetchall():
        x = _num(r["x"])
        dur = _num(r["te"]) - _num(r["ts"])
        if dur <= 0:
            continue
        qq = quarter(match_min(r["ts"], r["pd"], p2))
        if 51 <= x <= 110:
            Q[qq]["terr_num"] += dur
            Q[qq]["terr_den"] += dur
        elif -10 <= x <= 50:
            Q[qq]["terr_den"] += dur

    # Territory v2 + Possession% v2: 中点座標・BIP_v2 分母・ゼロサム（マッチレポート手法B と同一）
    # 開始時刻 (ps_timestamp) のバケツに丸ごと帰属（按分なし）
    for r in cur.execute(
        "SELECT team_name tn, x_coord x, x_coord_end xe, ps_timestamp ts, ps_endstamp te, period pd "
        "FROM events WHERE fxid=? AND team_name IN (?,?) "
        "AND action_name IN ('Possession','Scrum','Lineout Throw') "
        "AND ps_endstamp IS NOT NULL AND ps_endstamp!=''", (fx, team, opp)
    ).fetchall():
        dur = _num(r["te"]) - _num(r["ts"])
        if dur <= 0:
            continue
        xe = r["xe"]; xs = r["x"]
        if xe and xs:
            coord = (_num(xs) + _num(xe)) / 2
        elif xs:
            coord = _num(xs)
        else:
            coord = None
        if coord is None:
            continue
        qq = quarter(match_min(r["ts"], r["pd"], p2))
        if r["tn"] == team:
            Q[qq]["bip_k"] += dur
            if coord > 50:
                Q[qq]["atk_k"] += dur
        else:
            Q[qq]["bip_o"] += dur
            if coord > 50:
                Q[qq]["atk_o"] += dur

    for r in cur.execute(
        "SELECT metres mt, ps_timestamp ts, period pd FROM events "
        "WHERE fxid=? AND team_name=? AND action_name='Carry'", (fx, team)
    ).fetchall():
        qq = quarter(match_min(r["ts"], r["pd"], p2))
        Q[qq]["car"] += 1
        Q[qq]["mtr"] += _num(r["mt"])

    for r in cur.execute(
        "SELECT ps_timestamp ts, period pd FROM events "
        "WHERE fxid=? AND team_name=? AND action_name='Pass'", (fx, team)
    ).fetchall():
        Q[quarter(match_min(r["ts"], r["pd"], p2))]["pas"] += 1

    for r in cur.execute(
        "SELECT ps_timestamp ts, period pd FROM events "
        "WHERE fxid=? AND team_name=? AND action_name='Ruck'", (fx, team)
    ).fetchall():
        Q[quarter(match_min(r["ts"], r["pd"], p2))]["rucks"] += 1

    for r in cur.execute(
        "SELECT ps_timestamp ts, period pd FROM events "
        "WHERE fxid=? AND team_name=? AND action_name='Kick'", (fx, team)
    ).fetchall():
        Q[quarter(match_min(r["ts"], r["pd"], p2))]["kicks"] += 1

    for an, miss in [("Tackle", False), ("Missed Tackle", True)]:
        for r in cur.execute(
            "SELECT ps_timestamp ts, period pd FROM events "
            "WHERE fxid=? AND team_name=? AND action_name=?", (fx, team, an)
        ).fetchall():
            qq = quarter(match_min(r["ts"], r["pd"], p2))
            Q[qq]["ta"] += 1
            if miss:
                Q[qq]["tm"] += 1

    for r in cur.execute(
        "SELECT ps_timestamp ts, period pd FROM events "
        "WHERE fxid=? AND team_name=? AND action_name='Attacking Qualities' AND action_type_name='Initial Break'",
        (fx, team)
    ).fetchall():
        Q[quarter(match_min(r["ts"], r["pd"], p2))]["lb"] += 1

    for r in cur.execute(
        "SELECT ps_timestamp ts, period pd FROM events "
        "WHERE fxid=? AND team_name=? AND action_name='Attacking Qualities' AND action_type_name='Defender Beaten'",
        (fx, team)
    ).fetchall():
        Q[quarter(match_min(r["ts"], r["pd"], p2))]["db"] += 1

    for r in cur.execute(
        "SELECT ps_timestamp ts, period pd FROM events "
        "WHERE fxid=? AND team_name=? AND action_name='Turnover'", (fx, team)
    ).fetchall():
        Q[quarter(match_min(r["ts"], r["pd"], p2))]["toc"] += 1

    # tow: 6要素（team_stats と同一定義）
    for r in cur.execute(
        "SELECT action_name an, action_type_name tp, action_result_name rs, "
        "ps_timestamp ts, period pd FROM events WHERE fxid=? AND team_name=?", (fx, team)
    ).fetchall():
        an, tp, rs = r["an"], r["tp"] or "", r["rs"] or ""
        is_tow = False
        if an == "Ruck OOA" and tp == "Turnover Won": is_tow = True
        elif an == "Collection" and tp == "Jackal" and rs == "Success": is_tow = True
        elif an == "Lineout Take" and "Steal" in tp: is_tow = True
        elif an == "Sequences" and tp == "Scrum Steal": is_tow = True
        elif an == "Tackle" and rs == "Turnover Won": is_tow = True
        if is_tow:
            Q[quarter(match_min(r["ts"], r["pd"], p2))]["tow"] += 1
    for r in cur.execute(
        "SELECT ps_timestamp ts, period pd FROM events "
        "WHERE fxid=? AND action_name='Tackle' AND team_name!=? AND action_result_name='Forced in Touch'",
        (fx, team)
    ).fetchall():
        Q[quarter(match_min(r["ts"], r["pd"], p2))]["tow"] += 1

    for r in cur.execute(
        "SELECT ps_timestamp ts, period pd FROM events "
        "WHERE fxid=? AND team_name=? AND action_name='Penalty Conceded'", (fx, team)
    ).fetchall():
        Q[quarter(match_min(r["ts"], r["pd"], p2))]["pen"] += 1

    for r in cur.execute(
        "SELECT qualifier4_name q4, ps_timestamp ts, period pd FROM events "
        "WHERE fxid=? AND team_name=? AND action_name='Possession' "
        "AND qualifier4_name IN ('Enters into Opposition 22','Starts inside Opposition 22')", (fx, team)
    ).fetchall():
        qq = quarter(match_min(r["ts"], r["pd"], p2))
        Q[qq]["e22"] += 1
        if r["q4"] == "Enters into Opposition 22":
            Q[qq]["c22"] += 1
        else:
            Q[qq]["s22"] += 1

    for r in cur.execute(
        "SELECT ps_timestamp ts, period pd FROM events "
        "WHERE fxid=? AND team_name=? AND action_name='Try'", (fx, team)
    ).fetchall():
        qq = quarter(match_min(r["ts"], r["pd"], p2))
        Q[qq]["pts"] += 5
        Q[qq]["tries"] += 1

    for r in cur.execute(
        "SELECT action_type_name tp, ps_timestamp ts, period pd FROM events "
        "WHERE fxid=? AND team_name=? AND action_name='Goal Kick' AND action_result_name='Goal Kicked'",
        (fx, team)
    ).fetchall():
        qq = quarter(match_min(r["ts"], r["pd"], p2))
        Q[qq]["pts"] += 2 if r["tp"] == "Conversion" else 3

    out = {}
    for qq in ["Q1", "Q2", "Q3", "Q4"]:
        d = Q[qq]
        ta = d["ta"]
        bip_v2_q = d["bip_k"] + d["bip_o"]
        ter_num_v2 = d["atk_k"] + (d["bip_o"] - d["atk_o"])
        out[qq] = {
            "pts": d["pts"], "tries": d["tries"],
            "pos_t": mmss(d["bip_k"]),
            "pos_p": round(d["bip_k"] / bip_v2_q * 100) if bip_v2_q else 0,
            "ter_p": round(d["terr_num"] / d["terr_den"] * 100) if d["terr_den"] else 0,
            "ter_p_v2": round(ter_num_v2 / bip_v2_q * 100) if bip_v2_q else 0,
            "bip_v2_q": round(bip_v2_q),
            "atk_k_q": round(d["atk_k"]),
            "bip_o_q": round(d["bip_o"]),
            "atk_o_q": round(d["atk_o"]),
            "car": d["car"], "mtr": int(d["mtr"]),
            "amc": round(d["mtr"] / d["car"], 1) if d["car"] else 0.0,
            "pas": d["pas"],
            "r2k": round(d["rucks"] / d["kicks"], 1) if d["kicks"] else float(d["rucks"]),
            "ta": ta, "tm": d["tm"],
            "tp": round((ta - d["tm"]) / ta * 100, 1) if ta else 0.0,
            "lb": d["lb"], "def_beaten": d["db"], "tow": d["tow"], "toc": d["toc"], "pen": d["pen"],
            "e22": d["e22"], "c22": d["c22"], "s22": d["s22"],
        }
    return out



# ---------------------------------------------------------------------------
# match/timeline events (score / penalty / error / kick / missed kick)
# ---------------------------------------------------------------------------
def events_for(action, result=None, types=None):
    sql = "SELECT team_name tn, ps_timestamp ts, period pd, action_type_name tp FROM events " \
          "WHERE fxid=? AND action_name=?"
    params = [fx, action]
    if result:
        sql += " AND action_result_name=?"
        params.append(result)
    if types:
        ph = ",".join("?" * len(types))
        sql += f" AND action_type_name IN ({ph})"
        params += list(types)
    out = []
    for r in cur.execute(sql, params).fetchall():
        mm = round(match_min(r["ts"], r["pd"], p2))
        out.append({"team": r["tn"].upper(), "min": mm})
    out.sort(key=lambda e: e["min"])
    return out


# ---------------------------------------------------------------------------
# 22m entry detail (bands by 10-min period)
# ---------------------------------------------------------------------------
def e22_detail(team, opp):
    carried = C(fx, team, action_name="Possession", qualifier4_name="Enters into Opposition 22")
    bands = [0] * 9
    for r in cur.execute(
        "SELECT ps_timestamp ts, period pd FROM events "
        "WHERE fxid=? AND team_name=? AND action_name='Possession' "
        "AND qualifier4_name IN ('Enters into Opposition 22','Starts inside Opposition 22')", (fx, team)
    ).fetchall():
        mm = match_min(r["ts"], r["pd"], p2)
        idx = min(int(mm // 10), 8)
        bands[idx] += 1

    # 22m Strike Conversion: use Attacking 22 Entry action outcomes
    a22_rows = cur.execute(
        "SELECT COALESCE(action_type_name,'') tp, COUNT(*) n FROM events "
        "WHERE fxid=? AND team_name=? AND action_name='Attacking 22 Entry' "
        "GROUP BY action_type_name",
        (fx, team)
    ).fetchall()
    a22_by_type = {r["tp"]: r["n"] for r in a22_rows}
    a22_tries  = a22_by_type.get("22 Entry Outcome - Try", 0)
    a22_pg     = a22_by_type.get("22 Entry Outcome - Penalty Goal Attempt", 0)
    a22_to     = a22_by_type.get("22 Entry Outcome - Turnover", 0)
    a22_pc     = a22_by_type.get("22 Entry Outcome - Penalty Conceded", 0)
    a22_kt     = a22_by_type.get("22 Entry Outcome - Kick Turnover", 0)
    a22_sw     = a22_by_type.get("22 Entry Outcome - Scrum Won", 0)
    a22_pos    = a22_tries + a22_pg
    a22_total  = sum(a22_by_type.values())
    success_rate = round(a22_pos / a22_total * 100, 1) if a22_total else 0.0

    # Started = residual: a22_total − carried (guarantees started + carried = entry total)
    started = max(0, a22_total - carried)

    # Try breakdown: Inside 22m = possession "Starts inside Opposition 22"; Outside = entered from outside
    a22_tries_inside = cur.execute(
        "SELECT COUNT(*) FROM events e1 "
        "WHERE e1.fxid=? AND e1.team_name=? "
        "AND e1.action_name='Attacking 22 Entry' "
        "AND e1.action_type_name='22 Entry Outcome - Try' "
        "AND e1.sequence_id IS NOT NULL "
        "AND EXISTS ("
        "  SELECT 1 FROM events e2 "
        "  WHERE e2.fxid=e1.fxid AND e2.sequence_id=e1.sequence_id "
        "  AND e2.action_name='Possession' "
        "  AND e2.qualifier4_name='Starts inside Opposition 22'"
        ")",
        (fx, team)
    ).fetchone()[0]
    a22_tries_outside = a22_tries - a22_tries_inside

    # Turnover sub-breakdown: 1 type per A22 Entry Turnover sequence (correlated subquery avoids
    # double-counting when a sequence has multiple Turnover events)
    to_rows = cur.execute(
        "SELECT COALESCE(tp,'__NONE__') tp, COUNT(*) n FROM ("
        "  SELECT (SELECT action_type_name FROM events "
        "          WHERE fxid=e1.fxid AND sequence_id=e1.sequence_id "
        "          AND action_name='Turnover' AND action_result_name='Error on Attack' "
        "          ORDER BY event_pk LIMIT 1) AS tp "
        "  FROM events e1 "
        "  WHERE e1.fxid=? AND e1.team_name=? "
        "  AND e1.action_name='Attacking 22 Entry' "
        "  AND e1.action_type_name='22 Entry Outcome - Turnover' "
        "  AND e1.sequence_id IS NOT NULL"
        ") sub GROUP BY COALESCE(tp,'__NONE__') ORDER BY n DESC",
        (fx, team)
    ).fetchall()
    a22_to_detail = []
    no_to_count = 0  # sequences with no Turnover event found
    for r in to_rows:
        if r["tp"] == "__NONE__":
            no_to_count = r["n"]
        else:
            a22_to_detail.append([r["tp"], r["n"]])

    # For no-Turnover sequences: check set piece losses in Attack 22
    lo_lost_22m = cur.execute(
        "SELECT COUNT(*) FROM events e_lo "
        "JOIN events e_a22 ON e_lo.fxid=e_a22.fxid AND e_lo.sequence_id=e_a22.sequence_id "
        "WHERE e_lo.fxid=? AND e_lo.team_name=? "
        "AND e_lo.action_name='Lineout Throw' "
        "AND e_lo.field_zone='Attack 22' AND e_lo.action_result_name LIKE 'Lost%' "
        "AND e_lo.sequence_id IS NOT NULL "
        "AND e_a22.action_name='Attacking 22 Entry' "
        "AND e_a22.action_type_name='22 Entry Outcome - Turnover' "
        "AND NOT EXISTS ("
        "  SELECT 1 FROM events e_to "
        "  WHERE e_to.fxid=e_lo.fxid AND e_to.sequence_id=e_lo.sequence_id "
        "  AND e_to.action_name='Turnover' AND e_to.action_result_name='Error on Attack'"
        ")",
        (fx, team)
    ).fetchone()[0]
    sc_lost_22m = cur.execute(
        "SELECT COUNT(*) FROM events e_sc "
        "JOIN events e_a22 ON e_sc.fxid=e_a22.fxid AND e_sc.sequence_id=e_a22.sequence_id "
        "WHERE e_sc.fxid=? AND e_sc.team_name=? "
        "AND e_sc.action_name='Scrum' "
        "AND e_sc.field_zone='Attack 22' AND e_sc.action_result_name LIKE 'Lost%' "
        "AND e_sc.sequence_id IS NOT NULL "
        "AND e_a22.action_name='Attacking 22 Entry' "
        "AND e_a22.action_type_name='22 Entry Outcome - Turnover' "
        "AND NOT EXISTS ("
        "  SELECT 1 FROM events e_to "
        "  WHERE e_to.fxid=e_sc.fxid AND e_to.sequence_id=e_sc.sequence_id "
        "  AND e_to.action_name='Turnover' AND e_to.action_result_name='Error on Attack'"
        ")",
        (fx, team)
    ).fetchone()[0]
    if lo_lost_22m: a22_to_detail.append(["Lost in Lineout", lo_lost_22m])
    if sc_lost_22m: a22_to_detail.append(["Lost in Scrum", sc_lost_22m])
    # Remaining unclassified no-Turnover sequences → "Other"
    other_remaining = no_to_count - lo_lost_22m - sc_lost_22m
    if other_remaining > 0:
        a22_to_detail.append(["Other", other_remaining])

    return {
        "carried": carried, "started": started, "bands": bands,
        "a22_total": a22_total, "a22_tries": a22_tries, "a22_pg": a22_pg,
        "a22_to": a22_to, "a22_pc": a22_pc, "a22_kt": a22_kt, "a22_sw": a22_sw,
        "a22_tries_inside": a22_tries_inside, "a22_tries_outside": a22_tries_outside,
        "a22_to_detail": a22_to_detail,
        "a22_pos": a22_pos, "success_rate": success_rate,
    }


# ---------------------------------------------------------------------------
# set piece detail
# ---------------------------------------------------------------------------
def sequence_tries(fx, team):
    rows = cur.execute(
        "SELECT action_type_name src, COUNT(*) n FROM events "
        "WHERE fxid=? AND team_name=? AND action_name='Sequences' "
        "AND action_result_name='Try' GROUP BY action_type_name",
        (fx, team)
    ).fetchall()
    d = {r["src"]: r["n"] for r in rows}
    return {
        "lineout": d.get("Lineout", 0),
        "scrum": d.get("Scrum", 0),
        "turnover": d.get("Lineout Steal", 0) + d.get("Turnover", 0),
        "tap_pen": d.get("Tap Pen", 0),
        "restart": d.get("50m Restart", 0) + d.get("22m Restart", 0) + d.get("Goal Line Restart", 0),
    }


def setpiece_detail(team):
    lo_throwers = []
    for r in cur.execute(
        "SELECT player_name nm, "
        "SUM(action_result_name LIKE 'Won%') won, "
        "SUM(action_result_name LIKE 'Lost%') lost, "
        "COUNT(*) tot "
        "FROM events WHERE fxid=? AND team_name=? AND action_name='Lineout Throw' "
        "AND player_name IS NOT NULL AND player_name!='' GROUP BY player_name", (fx, team)
    ).fetchall():
        lo_throwers.append({
            "player": r["nm"], "total": r["tot"], "won": r["won"], "lost": r["lost"],
            "pct": round(r["won"] / r["tot"] * 100, 1) if r["tot"] else 0.0,
        })
    lo_throwers.sort(key=lambda x: x["total"], reverse=True)

    lo_jumpers = []
    for r in cur.execute(
        "SELECT player_name nm, "
        "SUM(action_result_name LIKE 'Won%') won, "
        "COUNT(*) tot "
        "FROM events WHERE fxid=? AND team_name=? AND action_name='Lineout Take' "
        "AND player_name IS NOT NULL AND player_name!='' GROUP BY player_name", (fx, team)
    ).fetchall():
        lo_jumpers.append({
            "player": r["nm"], "total": r["tot"], "won": r["won"],
            "pct": round(r["won"] / r["tot"] * 100, 1) if r["tot"] else 0.0,
        })
    lo_jumpers.sort(key=lambda x: x["won"], reverse=True)

    seq_tries = sequence_tries(fx, team)

    ma_tot = C(fx, team, action_name="Maul")
    ma_try = C(fx, team, action_name="Maul", action_result_name="Try Scored")
    ma_m = SUMM(fx, team, "Maul")
    # Inside 22m (x_coord 78-110)
    ma_22 = cur.execute(
        "SELECT COUNT(*) c FROM events WHERE fxid=? AND team_name=? "
        "AND action_name='Maul' AND CAST(x_coord AS REAL) BETWEEN 78 AND 110", (fx, team)
    ).fetchone()["c"]
    maul = {
        "total": ma_tot, "tries": ma_try, "metres": int(ma_m),
        "avg": round(ma_m / ma_tot, 1) if ma_tot else 0.0,
        "inside_22m": ma_22,
        "seq_tries": seq_tries["lineout"],
    }

    sc_tot = C(fx, team, action_name="Scrum")
    sc_won = CL(fx, team, "Scrum", "action_result_name", "Won%")
    sc_pen_won = C(fx, team, action_name="Scrum", action_result_name="Won Penalty")
    sc_reset = C(fx, team, action_name="Scrum", action_result_name="Reset")
    sc_pos = C(fx, team, action_name="Scrum", qualifier3_name="Positive")
    sc_neu = C(fx, team, action_name="Scrum", qualifier3_name="Neutral")
    sc_neg = C(fx, team, action_name="Scrum", qualifier3_name="Negative")
    sc_pen_try = C(fx, team, action_name="Scrum", action_result_name="Penalty Try")
    scrum = {
        "total": sc_tot, "won": sc_won, "pen_won": sc_pen_won, "reset": sc_reset,
        "stability": round(sc_won / (sc_tot - sc_reset) * 100, 1) if (sc_tot - sc_reset) else 0.0,  # Won / (Total - Reset) = Opta方式
        "positive": sc_pos, "neutral": sc_neu, "negative": sc_neg, "pen_try": sc_pen_try,
        "seq_tries": seq_tries["scrum"],
    }

    return {"lo_throwers": lo_throwers, "lo_jumpers": lo_jumpers, "maul": maul, "scrum": scrum}


# ---------------------------------------------------------------------------
# play time (per match, 0-80 min) / pos & shirt lookup
# ---------------------------------------------------------------------------
def player_meta(team):
    pos_map, shirt_map, _best = {}, {}, {}
    for r in cur.execute(
        "SELECT player_name nm, player_position_name pos, CAST(player_shirt_number AS INT) sh, "
        "COUNT(*) n FROM events WHERE fxid=? AND team_name=? AND player_name IS NOT NULL AND player_name!='' "
        "GROUP BY 1,2,3", (fx, team)
    ).fetchall():
        nm = r["nm"]
        if nm not in _best or r["n"] > _best[nm]:
            _best[nm] = r["n"]
            pos_map[nm] = r["pos"] or ""
            shirt_map[nm] = r["sh"] if r["sh"] is not None else 99

    sub_in, sub_out = {}, {}
    for r in cur.execute(
        "SELECT player_name nm, ps_timestamp ts, period pd FROM events "
        "WHERE fxid=? AND team_name=? AND action_name='Sub In'", (fx, team)
    ).fetchall():
        if r["nm"]:
            sub_in[r["nm"]] = min(sub_in.get(r["nm"], 1e9), match_min(r["ts"], r["pd"], p2))
    for r in cur.execute(
        "SELECT player_name nm, ps_timestamp ts, period pd FROM events "
        "WHERE fxid=? AND team_name=? AND action_name='Sub Out'", (fx, team)
    ).fetchall():
        if r["nm"]:
            sub_out[r["nm"]] = max(sub_out.get(r["nm"], -1), match_min(r["ts"], r["pd"], p2))

    play_time = {}
    for nm in pos_map:
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
        play_time[nm] = int(round(max(0, e - s)))

    return pos_map, shirt_map, play_time


# ---------------------------------------------------------------------------
# individual attack / defence
# ---------------------------------------------------------------------------
def players_attack(team, pos_map, shirt_map, play_time):
    out = []
    for r in cur.execute(
        "SELECT player_name nm, "
        "SUM(action_name='Carry') carries, "
        "SUM(CASE WHEN action_name='Carry' THEN CAST(metres AS REAL) ELSE 0 END) metres, "
        "SUM(CASE WHEN action_name='Carry' THEN CAST(metres3 AS REAL) ELSE 0 END) pcm, "
        "SUM(action_name='Carry' AND qualifier3_name='Crossed Gain line') glo, "
        "SUM(action_name='Carry' AND qualifier4_name='Dominant Contact') dom_carry, "
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
        "FROM events WHERE fxid=? AND team_name=? AND player_name IS NOT NULL AND player_name!='' "
        "GROUP BY player_name", (fx, team)
    ).fetchall():
        nm = r["nm"]
        car, pas, kk = r["carries"] or 0, r["passes"] or 0, r["kicks"] or 0
        ooa13, ooa4 = r["ooa13"] or 0, r["ooa4"] or 0
        ooa_t = ooa13 + ooa4
        metres = r["metres"] or 0
        pcm = r["pcm"] or 0
        out.append({
            "shirt": shirt_map.get(nm, 99), "player": nm, "pos": pos_map.get(nm, ""),
            "carries": car, "metres": int(metres),
            "avg_carry": round(metres / car, 1) if car else 0.0,
            "pcm": int(pcm),
            "linebreaks": r["lb"] or 0, "def_beaten": r["db"] or 0, "offloads": r["ol"] or 0,
            "tries": r["tries"] or 0,
            "gl_pct": round((r["glo"] or 0) / car * 100, 1) if car else 0.0,
            "dom_carry": r["dom_carry"] or 0,
            "ooa_1_3": ooa13, "ooa_4p": ooa4,
            "ooa_eff": round(ooa13 / ooa_t * 100, 1) if ooa_t else 0.0,
            "handle_count": car + pas + kk + (r["ol"] or 0),
            "passes": pas,
            "pass_acc": round((pas - (r["pass_bad"] or 0)) / pas * 100, 1) if pas else None,
            "kicks": kk, "kick_m": int(r["kick_m"] or 0),
            "avg_kick": round((r["kick_m"] or 0) / kk, 1) if kk else 0,
            "errors": r["err"] or 0,
        })
    out.sort(key=lambda p: p["shirt"])
    return out


def players_defence(team, pos_map, shirt_map, play_time):
    out = []
    for r in cur.execute(
        "SELECT player_name nm, "
        "SUM(action_name='Tackle') tk, "
        "SUM(action_name='Missed Tackle') mt, "
        "SUM(action_name='Tackle' AND qualifier3_name='Assist') tkl_assist, "
        "SUM(action_name='Tackle' AND qualifier4_name='Dominant Tackle') dom, "
        "SUM(action_name='Tackle' AND action_result_name='Passive') passive, "
        "SUM(action_name='Tackle' AND action_result_name='Offload Allowed') oa, "
        "SUM(action_name='Tackle' AND qualifier6_name='Legs') legs, "
        "SUM(action_name='Tackle' AND qualifier6_name IN ('Upper Torso','Lower Torso','Legs')) ht_tot, "
        "SUM(action_name='Collection' AND action_type_name='Jackal' AND action_result_name='Success') jck, "
        "SUM(action_name='Tackle' AND action_result_name='Turnover Won') tow_tackle, "
        "SUM(action_name='Tackle' AND action_result_name='Forced in Touch') fit, "
        "SUM(action_name='Ruck' AND action_result_name='Penalty Won') ruck_pw, "
        "SUM(action_name='Lineout Take' AND action_type_name LIKE 'Lineout Steal%') lo_steal, "
        "SUM(action_name='Ruck OOA' AND action_type_name='Turnover Won') roa_tow, "
        "SUM(action_name='Tackle' AND action_result_name='Try Saver') try_saver, "
        "SUM(action_name='Penalty Conceded') pen "
        "FROM events WHERE fxid=? AND team_name=? AND player_name IS NOT NULL AND player_name!='' "
        "GROUP BY player_name", (fx, team)
    ).fetchall():
        nm = r["nm"]
        att = (r["tk"] or 0) + (r["mt"] or 0)
        ht_tot = r["ht_tot"] or 0
        out.append({
            "shirt": shirt_map.get(nm, 99), "player": nm, "pos": pos_map.get(nm, ""),
            "mins": play_time.get(nm, 0),
            "att": att, "made": r["tk"] or 0, "miss": r["mt"] or 0, "tkl_assist": r["tkl_assist"] or 0,
            "pct": round((r["tk"] or 0) / att * 100, 1) if att else None,
            "dom": r["dom"] or 0,
            "dom_pct": round((r["dom"] or 0) / att * 100, 1) if att else None,
            "hl": round((r["legs"] or 0) / ht_tot * 100, 1) if ht_tot else None,
            "try_saver": r["try_saver"] or 0, "fit": r["fit"] or 0,
            "to_t": (r["tow_tackle"] or 0) + (r["fit"] or 0), "oa": r["oa"] or 0, "pas": r["passive"] or 0,
            "jck": r["jck"] or 0,
            "tow": (r["tow_tackle"] or 0) + (r["fit"] or 0) + (r["ruck_pw"] or 0) + (r["jck"] or 0) + (r["lo_steal"] or 0) + (r["roa_tow"] or 0),
            "infr": r["pen"] or 0,
        })
    out.sort(key=lambda p: p["shirt"])
    return out


# ---------------------------------------------------------------------------
# penalty detail (PD)
# ---------------------------------------------------------------------------
def penalty_detail(team):
    by_type = {}
    by_pos = {"Front Row": 0, "Lock": 0, "Loosie": 0, "Inside": 0, "Midfield": 0, "Back 3": 0}
    by_quarter = {"Q1": 0, "Q2": 0, "Q3": 0, "Q4": 0}
    attack = defence = 0
    for r in cur.execute(
        "SELECT action_type_name tp, qualifier3_name od, player_position_name pos, "
        "ps_timestamp ts, period pd FROM events "
        "WHERE fxid=? AND team_name=? AND action_name='Penalty Conceded'", (fx, team)
    ).fetchall():
        t = r["tp"] or "Other"
        by_type[t] = by_type.get(t, 0) + 1
        if r["od"] == "Offence":
            attack += 1
        elif r["od"] == "Defence":
            defence += 1
        grp = POS_GROUP.get(r["pos"])
        if grp:
            by_pos[grp] += 1
        qq = quarter(match_min(r["ts"], r["pd"], p2))
        by_quarter[qq] += 1
    return {
        "by_type": by_type, "by_pos_group": by_pos,
        "attack_count": attack, "defence_count": defence,
        "by_half": by_quarter,
    }


# ---------------------------------------------------------------------------
# team sheet
# ---------------------------------------------------------------------------
def teamsheet(team, pos_map, shirt_map, play_time):
    rows = []
    for nm, sh in shirt_map.items():
        rows.append({"shirt": sh, "name": nm, "pos": pos_map.get(nm, ""), "mins": play_time.get(nm, 0)})
    rows.sort(key=lambda r: r["shirt"])
    return rows


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# inject into template

# ---------------------------------------------------------------------------
def replace_const(html, name, value):
    """Replace `const NAME=<JS literal>;` with `const NAME=<json>;`, matching
    balanced braces/brackets so the literal can span multiple lines and
    contain nested structures."""
    pattern = re.compile(r"const " + re.escape(name) + r"\s*=\s*")
    mo = pattern.search(html)
    if not mo:
        raise ValueError(f"const {name} not found")
    start = mo.end()
    i = start
    depth = 0
    in_str = False
    str_ch = ""
    while i < len(html):
        ch = html[i]
        if in_str:
            if ch == "\\":
                i += 2
                continue
            if ch == str_ch:
                in_str = False
        else:
            if ch in "'\"":
                in_str = True
                str_ch = ch
            elif ch in "{[":
                depth += 1
            elif ch in "}]":
                depth -= 1
                if depth == 0:
                    i += 1
                    break
        i += 1
    end = i
    if end < len(html) and html[end] == ";":
        end += 1
    new_literal = json.dumps(value, ensure_ascii=False)
    return html[:mo.start()] + f"const {name}=" + new_literal + ";" + html[end:]


TEAM_ABBR_MAP = {
    'Kubota Spears': 'KUB',
    'Kobelco Kobe Steelers': 'KOB',
    'Tokyo Sungoliath': 'SUN',
    'Saitama Wild Knights': 'PAN',
    'Toyota Verblitz': 'TOY',
    'Urayasu D-Rocks': 'UDR',
    'Mie Honda Heat': 'HND',
    'Mitsubishi Sagamihara Dynaboars': 'DYN',
    'BlackRams Tokyo': 'BRT',
    'Yokohama Canon Eagles': 'YCE',
    'Shizuoka BlueRevs': 'SBR',
    'Toshiba Brave Lupus Tokyo': 'TOH',
}


def cmd_match(args):
    """Generate a single-match report HTML."""
    global con, cur, fx, p2

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    # match lookup
    q = "SELECT * FROM matches WHERE 1=1"
    params = []
    if hasattr(args, 'fxid') and args.fxid:
        q += " AND fxid=?"; params.append(args.fxid)
    if hasattr(args, 'match_date') and args.match_date:
        q += " AND date_played=?"; params.append(args.match_date)
    if hasattr(args, 'opponent') and args.opponent:
        q += " AND opponent_name=?"; params.append(args.opponent)
    if hasattr(args, 'round') and args.round:
        q += " AND round_number=?"; params.append(args.round)
    m = cur.execute(q, params).fetchone()
    if not m:
        sys.exit("No match found matching the given criteria.")

    fx = m["fxid"]
    KUBOTA_T = "Kubota Spears"
    OPP_T = m["opponent_name"]
    HOME_T = KUBOTA_T
    AWAY_T = OPP_T
    p2 = _num(cur.execute("SELECT MIN(ps_timestamp) v FROM events WHERE fxid=? AND period=2", (fx,)).fetchone()["v"])

    h_stats, at_h, at_tot, terr_num_h, terr_den_h, bip_v2_h, terr_num2_h, terr_den2_h = team_stats(HOME_T, AWAY_T)
    a_stats, at_a, _,    terr_num_a, terr_den_a, _,       terr_num2_a, terr_den2_a = team_stats(AWAY_T, HOME_T)
    poss_denom = at_h + at_a
    h_pct = round(at_h / poss_denom * 100) if poss_denom else 0
    a_pct = 100 - h_pct
    # Territory 旧（x_coord 開始座標）
    total_atk_time = terr_den_h + terr_den_a
    if total_atk_time > 0:
        time_in_away_half = terr_num_h + (terr_den_a - terr_num_a)
        h_terr = round(time_in_away_half / total_atk_time * 100)
        a_terr = 100 - h_terr
    else:
        h_terr = a_terr = 0
    # Territory v2（x_coord_end 終端座標 / BIP_v2 分母）
    bip_v2_total = terr_den2_h + terr_den2_a  # = BIP_v2 (Poss+Sc+LO)
    if bip_v2_total > 0:
        time_kub_atk_v2 = terr_num2_h + (terr_den2_a - terr_num2_a)
        h_terr_v2 = round(time_kub_atk_v2 / bip_v2_total * 100)
        a_terr_v2 = 100 - h_terr_v2
    else:
        h_terr_v2 = a_terr_v2 = 0
    qd_h = quarter_stats(HOME_T, AWAY_T)
    qd_a = quarter_stats(AWAY_T, HOME_T)
    score_events = events_for("Try") + events_for(
        "Goal Kick", result="Goal Kicked", types=("Penalty Goal", "Drop Goal"))
    score_events.sort(key=lambda e: e["min"])
    pen_events = events_for("Penalty Conceded")
    error_events = events_for("Turnover")
    kick_events = events_for("Kick")
    miss_kick_events = events_for("Goal Kick", result="Goal Missed")
    HOME_ABBR = team_abbr(HOME_T)
    AWAY_ABBR = team_abbr(AWAY_T)

    HOME_NAME = HOME_T.upper()
    AWAY_NAME = AWAY_T.upper()
    
    pos_map_h, shirt_map_h, play_time_h = player_meta(HOME_T)
    pos_map_a, shirt_map_a, play_time_a = player_meta(AWAY_T)
    
    date_parts = m["date_played"].split("-")
    date_fmt = f"{int(date_parts[2])} {MONTHS[int(date_parts[1])]} {date_parts[0]}"
    
    if m["kubota_is_home"]:
        kubota_ht, opp_ht = m["home_ht_score"], m["away_ht_score"]
    else:
        kubota_ht, opp_ht = m["away_ht_score"], m["home_ht_score"]
    
    D = {
        "info": {
            "home": HOME_NAME, "away": AWAY_NAME,
            "home_score": m["kubota_score"], "away_score": m["opponent_score"],
            "home_ht": kubota_ht, "away_ht": opp_ht,
            "venue": m["venue_name"], "date": date_fmt,
            "round": m["round_number"], "competition": "League One",
        },
        "home_stats": h_stats, "away_stats": a_stats,
        "ball_in_play": {
            "total_fmt": mmss(at_tot), "h_fmt": mmss(at_h), "h_pct": h_pct,
            "a_fmt": mmss(at_a), "a_pct": a_pct, "h_terr": h_terr, "a_terr": a_terr,
            # v2: BIP=Poss+Sc+LO, Territory=x_coord_end>50
            "total_v2_fmt": mmss(bip_v2_total), "h_terr_v2": h_terr_v2, "a_terr_v2": a_terr_v2,
        },
        "score_events": score_events, "pen_events": pen_events, "error_events": error_events,
        "kick_events": kick_events, "miss_kick_events": miss_kick_events,
        "e22_detail": {HOME_NAME: e22_detail(HOME_T, AWAY_T), AWAY_NAME: e22_detail(AWAY_T, HOME_T)},
        "setpiece": {HOME_NAME: setpiece_detail(HOME_T), AWAY_NAME: setpiece_detail(AWAY_T)},
        "teamsheet": {
            HOME_NAME: teamsheet(HOME_T, pos_map_h, shirt_map_h, play_time_h),
            AWAY_NAME: teamsheet(AWAY_T, pos_map_a, shirt_map_a, play_time_a),
        },
    }
    
    TOT = {
        "h": {
            "pts": m["kubota_score"],
            "tries": h_stats["tries"], "pos_t": mmss(at_h), "pos_p": h_pct, "ter_p": h_terr, "ter_p_v2": h_terr_v2,
            "car": h_stats["carries"], "mtr": h_stats["metres"], "amc": h_stats["avg_carry"],
            "pas": h_stats["passes"],
            "r2k": round(h_stats["rucks"] / h_stats["kicks"], 1) if h_stats["kicks"] else float(h_stats["rucks"]),
            "ta": h_stats["tack_att"], "tm": h_stats["tack_miss"], "tp": h_stats["tack_pct"],
            "lb": h_stats["linebreaks"], "tow": h_stats["to_won"], "toc": h_stats["to_con"],
            "pen": h_stats["penalties"], "e22": h_stats["e22"], "c22": h_stats["c22"], "s22": h_stats["s22"],
        },
        "a": {
            "pts": m["opponent_score"],
            "tries": a_stats["tries"], "pos_t": mmss(at_a), "pos_p": a_pct, "ter_p": a_terr, "ter_p_v2": a_terr_v2,
            "car": a_stats["carries"], "mtr": a_stats["metres"], "amc": a_stats["avg_carry"],
            "pas": a_stats["passes"],
            "r2k": round(a_stats["rucks"] / a_stats["kicks"], 1) if a_stats["kicks"] else float(a_stats["rucks"]),
            "ta": a_stats["tack_att"], "tm": a_stats["tack_miss"], "tp": a_stats["tack_pct"],
            "lb": a_stats["linebreaks"], "tow": a_stats["to_won"], "toc": a_stats["to_con"],
            "pen": a_stats["penalties"], "e22": a_stats["e22"], "c22": a_stats["c22"], "s22": a_stats["s22"],
        },
    }
    
    QD = {"h": qd_h, "a": qd_a}
    
    PD = {HOME_NAME: penalty_detail(HOME_T), AWAY_NAME: penalty_detail(AWAY_T)}
    
    ATK = {
        HOME_NAME: players_attack(HOME_T, pos_map_h, shirt_map_h, play_time_h),
        AWAY_NAME: players_attack(AWAY_T, pos_map_a, shirt_map_a, play_time_a),
    }
    DEFV5 = {
        HOME_NAME: players_defence(HOME_T, pos_map_h, shirt_map_h, play_time_h),
        AWAY_NAME: players_defence(AWAY_T, pos_map_a, shirt_map_a, play_time_a),
    }
    
    con.close()

    
    html = open(MATCH_TEMPLATE, encoding="utf-8").read()
    for name, value in [("D", D), ("TOT", TOT), ("QD", QD), ("PD", PD), ("ATK", ATK), ("DEFV5", DEFV5)]:
        html = replace_const(html, name, value)
    
    html = html.replace("label:'Attack KS'", f"label:'Attack {HOME_ABBR}'")
    html = html.replace("label:'Attack SUN'", f"label:'Attack {AWAY_ABBR}'")
    html = html.replace("label:'Defence KS'", f"label:'Defence {HOME_ABBR}'")
    html = html.replace("label:'Defence SUN'", f"label:'Defence {AWAY_ABBR}'")
    html = html.replace(">KS<", f">{HOME_ABBR}<")
    html = html.replace("${HOME_ABBR}", HOME_ABBR)
    html = html.replace("${AWAY_ABBR}", AWAY_ABBR)
    html = html.replace(">SUN<", f">{AWAY_ABBR}<")
    html = html.replace(">KUB<", f">{HOME_ABBR}<")
    html = html.replace("KUB Won", f"{HOME_ABBR} Won")
    html = html.replace("KUB Win", f"{HOME_ABBR} Win")
    html = html.replace("SUN Won", f"{AWAY_ABBR} Won")
    html = html.replace("SUN Win", f"{AWAY_ABBR} Win")
    html = html.replace(">KS ${hEnd.v>0", f">{HOME_ABBR} ${{hEnd.v>0")
    html = html.replace(">SUN ${aEnd.v>0", f">{AWAY_ABBR} ${{aEnd.v>0")
    
    out_opp = m["opponent_name"].replace(" ", "_")
    out_name = f"match_report_{m['date_played']}_{out_opp}.html"
    with open(out_name, "w", encoding="utf-8") as fh:
        fh.write(html)
    
    print(f"Wrote {out_name}")
    print(f"  {KUBOTA_T} {m['kubota_score']} - {m['opponent_score']} {OPP_T} "
          f"(R{m['round_number']}, {m['date_played']}, "
          f"{'Home' if m['kubota_is_home'] else 'Away'})")
    
    con.close()


# ═══════════════════════════════════════════════════════════════
# SECTION 3: SEASON KPI
# ═══════════════════════════════════════════════════════════════

def cmd_kpi(args=None):
    """Generate season KPI report."""
    global con, cur

    OUT = "season_kpi_v2.html"
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    # KPI-specific helper functions (use module-level cur)
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

    # Main processing
    matches = cur.execute("SELECT * FROM matches ORDER BY date_played, fxid").fetchall()
    per_match = []
    
    # season-wide penalty accumulators (page: Penalty)
    pen_types = {}
    pen_od = {"Offence": 0, "Defence": 0}
    pen_half = {1: 0, 2: 0}
    pen_quarter = {"Q1": 0, "Q2": 0, "Q3": 0, "Q4": 0}
    pen_pos = {"Front Row": 0, "Lock": 0, "Loosie": 0, "Inside": 0, "Midfield": 0, "Back 3": 0}
    
    for m in matches:
        fx = m["fxid"]
        opp_t = m["opponent_name"]
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
    
        # Attack Time 修正: Possession + Scrum + Lineout Throw (Optaと一致 MAE=9.4s)
        sc_rows = cur.execute(
            "SELECT team_name tn, ps_timestamp ts, ps_endstamp te "
            "FROM events WHERE fxid=? AND action_name='Scrum'", (fx,)
        ).fetchall()
        lo_rows = cur.execute(
            "SELECT team_name tn, ps_timestamp ts, ps_endstamp te "
            "FROM events WHERE fxid=? AND action_name='Lineout Throw'", (fx,)
        ).fetchall()
        gk_rows = cur.execute(
            "SELECT ps_timestamp ts, ps_endstamp te "
            "FROM events WHERE fxid=? AND action_name='Goal Kick'", (fx,)
        ).fetchall()
        rs_rows = cur.execute(
            "SELECT ps_timestamp ts, ps_endstamp te "
            "FROM events WHERE fxid=? AND action_name='Restart'", (fx,)
        ).fetchall()
        def dur(rows, team=None, tn_col="tn"):
            return sum(max(0, _num(r["te"]) - _num(r["ts"]))
                       for r in rows if team is None or r[tn_col] == team)
        at_kub = dur(poss_rows, TEAM) + dur(sc_rows, TEAM) + dur(lo_rows, TEAM)
        # BIP_v2 = Poss+Sc+LO のみ（GK・RS 除外）
        total_atk_all = dur(poss_rows) + dur(sc_rows) + dur(lo_rows)  # 両チーム合計
        at_opp = total_atk_all - at_kub
        at_tot_old = total_atk_all + dur(gk_rows) + dur(rs_rows)  # 旧BIP（GK/RS込み・ロールバック用）
        at_tot = total_atk_all  # BIP_v2（GK・RS 除外）
        # Possession% = at_kub / (at_kub + at_opp)（at_totではなくattack timeの比率）
    
        # Territory 旧: KUBのPoss+Sc+LOで x_coord(開始)>50 / KUB総時間（ロールバック用）
        terr_rows = cur.execute(
            "SELECT x_coord x, ps_timestamp ts, ps_endstamp te FROM events "
            "WHERE fxid=? AND team_name=? "
            "AND action_name IN ('Possession','Scrum','Lineout Throw') "
            "AND x_coord IS NOT NULL AND x_coord!='' "
            "AND ps_endstamp IS NOT NULL AND ps_endstamp!=''", (fx, TEAM)
        ).fetchall()
        terr_num = terr_den = 0.0
        for r in terr_rows:
            x = _num(r["x"])
            d = _num(r["te"]) - _num(r["ts"])
            if d <= 0:
                continue
            if x > 50:
                terr_num += d
            terr_den += d

        # Territory v2: 中点座標・BIP_v2 分母（マッチレポート手法B と同一ロジック）
        terr_rows_v2 = cur.execute(
            "SELECT team_name tn, x_coord x, x_coord_end xe, ps_timestamp ts, ps_endstamp te FROM events "
            "WHERE fxid=? AND team_name IN (?,?) "
            "AND action_name IN ('Possession','Scrum','Lineout Throw') "
            "AND ps_endstamp IS NOT NULL AND ps_endstamp!=''", (fx, TEAM, opp_t)
        ).fetchall()
        tn_kub = td_kub = tn_opp = td_opp = 0.0
        for r in terr_rows_v2:
            d = _num(r["te"]) - _num(r["ts"])
            if d <= 0:
                continue
            xe = r["xe"]; xs = r["x"]
            if xe and xs: coord = (_num(xs) + _num(xe)) / 2
            elif xs:      coord = _num(xs)
            else:         coord = None
            if coord is None:
                continue
            if r["tn"] == TEAM:
                if coord > 50: tn_kub += d
                td_kub += d
            else:
                if coord > 50: tn_opp += d
                td_opp += d
        terr_num_v2 = tn_kub + (td_opp - tn_opp)  # KUB陣取り時間
        terr_den_v2 = td_kub + td_opp              # BIP_v2
    
            # TO Won: Ruck OOA TO + Jackal + LO Steal + Scrum Steal + Tackle TO + Forced in Touch（6要素）
        tw = 0
        for r in cur.execute(
            "SELECT action_name an, action_type_name tp, action_result_name rs "
            "FROM events WHERE fxid=? AND team_name=?", (fx, TEAM)
        ).fetchall():
            an, tp, rs = r["an"], r["tp"] or "", r["rs"] or ""
            if an=="Ruck OOA" and tp=="Turnover Won": tw+=1
            elif an=="Collection" and tp=="Jackal" and rs=="Success": tw+=1
            elif an=="Lineout Take" and "Steal" in tp: tw+=1
            elif an=="Sequences" and tp=="Scrum Steal": tw+=1
            elif an=="Tackle" and rs=="Turnover Won": tw+=1
        # Forced in Touch: 相手チームのタックルで押し出した数
        for r in cur.execute(
            "SELECT action_result_name rs FROM events "
            "WHERE fxid=? AND action_name='Tackle' AND team_name!=? AND action_result_name='Forced in Touch'",
            (fx, TEAM)
        ).fetchall():
            tw += 1
    
        # counts
        # Kicks in Play: qualifier3_name='Kick in Play' or 'Kick in Play (Own 22)' (Optaと完全一致)
        kip_rows = cur.execute(
            "SELECT metres FROM events WHERE fxid=? AND team_name=? AND action_name='Kick' "
            "AND qualifier3_name IN ('Kick in Play','Kick in Play (Own 22)')", (fx, TEAM)
        ).fetchall()
        kicks = len(kip_rows)
        km = sum(_num(r["metres"]) for r in kip_rows)
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
        # 旧: opp_glo = CT(fx, ot, action_name="Carry", qualifier3_name="Crossed Gain line")
        opp_glo = CT(fx, ot, action_name="Ruck", qualifier3="548")
        # 旧: opp_ruck_gl_d = CT(fx, ot, action_name="Ruck", qualifier3={"548","549","550","551"})
        opp_ruck_gl_d = CT(fx, ot, action_name="Ruck", qualifier3={"548","549","550"})
        opp_rucks = CT(fx, ot, action_name="Ruck")
        opp_lqb = CT(fx, ot, action_name="Ruck",
                     qualifier4_name={"0-1 Seconds", "1-2 Seconds", "2-3 Seconds"})
        tries_conceded = CT(fx, ot, action_name="Try")
        opp_db = CT(fx, ot, action_name="Attacking Qualities", action_type_name="Defender Beaten")
        opp_e22 = CT(fx, ot, action_name="Possession",
                     qualifier4_name={"Enters into Opposition 22", "Starts inside Opposition 22"})
        # Opponent 22m success rate: Attacking 22 Entry outcomes (Try + Penalty Goal Attempt)
        opp_a22_rows = cur.execute(
            "SELECT COALESCE(action_type_name,'') tp, COUNT(*) n FROM events "
            "WHERE fxid=? AND team_name=? AND action_name='Attacking 22 Entry' "
            "GROUP BY action_type_name", (fx, ot)
        ).fetchall()
        opp_a22_by_type = {r["tp"]: r["n"] for r in opp_a22_rows}
        opp_a22_pos = (opp_a22_by_type.get("22 Entry Outcome - Try", 0) +
                       opp_a22_by_type.get("22 Entry Outcome - Penalty Goal Attempt", 0))
        opp_a22_total = sum(opp_a22_by_type.values())
        opp_success_pct = round(opp_a22_pos / opp_a22_total * 100, 1) if opp_a22_total else 0.0

        # Kubota 22m success rate: Attacking 22 Entry outcomes (Try + Penalty Goal Attempt)
        kub_a22_rows = cur.execute(
            "SELECT COALESCE(action_type_name,'') tp, COUNT(*) n FROM events "
            "WHERE fxid=? AND team_name=? AND action_name='Attacking 22 Entry' "
            "GROUP BY action_type_name", (fx, TEAM)
        ).fetchall()
        kub_a22_by_type = {r["tp"]: r["n"] for r in kub_a22_rows}
        kub_a22_pos = (kub_a22_by_type.get("22 Entry Outcome - Try", 0) +
                       kub_a22_by_type.get("22 Entry Outcome - Penalty Goal Attempt", 0))
        kub_a22_total = sum(kub_a22_by_type.values())
        kub_success_pct = round(kub_a22_pos / kub_a22_total * 100, 1) if kub_a22_total else 0.0

        # penalty season accumulation (type / attack-defence / half / quarter)
        for r in cur.execute(
            "SELECT action_type_name tp, qualifier3_name od, player_position_name pos, period pd, ps_timestamp ts "
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
            grp = POS_GROUP.get(r["pos"])
            if grp:
                pen_pos[grp] += 1
    
        rec = {
            "fxid": fx, "date": m["date_played"], "opp": m["opponent_name"],
            "ha": "H" if m["kubota_is_home"] else "A",
            "kub": m["kubota_score"], "opp_score": m["opponent_score"], "result": m["kubota_result"],
            # raw components
            "at_kub": at_kub, "at_tot": at_tot, "at_tot_old": at_tot_old, "poss_den": at_kub + at_opp,
            "terr_num": terr_num, "terr_den": terr_den,              # 旧（ロールバック用）
            "terr_num_v2": terr_num_v2, "terr_den_v2": terr_den_v2,  # v2（中点・BIP_v2）
            "tw": tw,
            "kicks": kicks, "km": int(km), "rucks": rucks,
            # 旧: contest_tot 4種 (Bomb/Low/Chip/Cross Pitch) → 5種 (+Box)
            "contest_tot": len(cur.execute(
                "SELECT 1 FROM events WHERE fxid=? AND team_name=? AND action_name='Kick' "
                "AND action_type_name IN ('Bomb','Low','Chip','Cross Pitch','Box')", (fx, TEAM)
            ).fetchall()),
            # 旧: regain 分子 Own Player - Collected / Pressure Error / Pressure Carried Over
            "regain": len(cur.execute(
                "SELECT 1 FROM events WHERE fxid=? AND team_name=? AND action_name='Kick' "
                "AND action_type_name IN ('Bomb','Low','Chip','Cross Pitch','Box') "
                "AND action_result_name IN ('Own Player - Collected','Pressure Error','Pressure in Touch','Try Kick')", (fx, TEAM)
            ).fetchall()),
            "hg": C(fx, action_name="Kick", action_result_name="Collected Bounce"),
            "carries": carries, "metres": int(metres),
            # 旧: "glo": C(fx, action_name="Carry", qualifier3_name="Crossed Gain line"),
            "glo": C(fx, action_name="Ruck", qualifier3="548"),
            # 旧: "ruck_gl_d": C(fx, action_name="Ruck", qualifier3={"548","549","550","551"}),
            "ruck_gl_d": C(fx, action_name="Ruck", qualifier3={"548","549","550"}),
            "lqb_n": C(fx, action_name="Ruck",
                       qualifier4_name={"0-1 Seconds", "1-2 Seconds", "2-3 Seconds"}),
            "offloads": C(fx, action_name="Pass", action_type_name="Offload",
                          action_result_name="Own Player"),
            "db": C(fx, action_name="Attacking Qualities", action_type_name="Defender Beaten"),
            "lb": C(fx, action_name="Attacking Qualities", action_type_name="Initial Break"),
            "e22": C(fx, action_name="Possession",
                     qualifier4_name={"Enters into Opposition 22", "Starts inside Opposition 22"}),
            "c22": C(fx, action_name="Possession", qualifier4_name="Enters into Opposition 22"),
            "s22": C(fx, action_name="Possession", qualifier4_name="Starts inside Opposition 22"),
            "tries": C(fx, action_name="Try"),
            "pen": C(fx, action_name="Penalty Conceded"),
            "to_con": C(fx, action_name="Turnover"),
            "attacks": C(fx, action_name="Possession"),
            "tk": tk, "mt": mt,
            "dom": C(fx, action_name="Tackle", qualifier4_name="Dominant Tackle"),
            "passive": C(fx, action_name="Tackle", action_result_name="Passive"),
            "oa": C(fx, action_name="Tackle", action_result_name="Offload Allowed"),
            "gk_made": gk_made, "gk_att": gk_att,
            # set piece
            "lo_throw": lo_throw, "lo_won": lo_won, "lo_lost": lo_throw - lo_won,
            "lo_steal": lo_steal,
            "sc_tot": sc_tot, "sc_won": sc_won, "sc_reset": sc_reset,
            "ma_tot": ma_tot, "ma_won": ma_won, "ma_try": ma_try, "ma_m": int(ma_m),
            # opponent stats
            "opp_carries": opp_carries, "opp_glo": opp_glo,
            "opp_ruck_gl_d": opp_ruck_gl_d,
            "opp_rucks": opp_rucks, "opp_lqb": opp_lqb,
            "tries_conceded": tries_conceded, "opp_db": opp_db, "opp_e22": opp_e22,
            "opp_success_pct": opp_success_pct,
            "kub_success_pct": kub_success_pct,
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
        "SUM(CASE WHEN action_name='Carry' THEN CAST(metres3 AS REAL) ELSE 0 END) pcm, "
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
        pcm_val = r["pcm"] or 0
        players_attack.append({
            "name": nm, "pos": pos_map.get(nm, ""), "shirt": shirt_map.get(nm, 99),
            "pt": play_time.get(nm, 0),
            "carries": car, "metres": int(r["metres"]),
            "avg": round(r["metres"] / car, 1) if car else 0,
            "pcm": int(pcm_val),
            "pcm_per_carry": round(pcm_val / car, 2) if car else 0,
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
        "SUM(action_name='Tackle' AND qualifier3_name='Assist') tkl_assist, "
        "SUM(action_name='Tackle' AND qualifier4_name='Dominant Tackle') dom, "
        "SUM(action_name='Tackle' AND action_result_name='Passive') passive, "
        "SUM(action_name='Tackle' AND action_result_name='Offload Allowed') oa, "
        "SUM(action_name='Tackle' AND qualifier6_name='Legs') legs, "
        "SUM(action_name='Tackle' AND qualifier6_name IN ('Upper Torso','Lower Torso','Legs')) ht_tot, "
        "SUM(action_name='Collection' AND action_type_name='Jackal' AND action_result_name='Success') jck, "
        "SUM(action_name='Tackle' AND action_result_name='Turnover Won') tow_tackle, "
        "SUM(action_name='Tackle' AND action_result_name='Forced in Touch') fit, "
        "SUM(action_name='Ruck' AND action_result_name='Penalty Won') ruck_pw, "
        "SUM(action_name='Lineout Take' AND action_type_name LIKE 'Lineout Steal%') lo_steal, "
        "SUM(action_name='Ruck OOA' AND action_type_name='Turnover Won') roa_tow, "
        "SUM(action_name='Tackle' AND action_result_name='Try Saver') try_saver, "
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
            "tk": r["tk"], "mt": r["mt"], "att": att, "tkl_assist": r["tkl_assist"],
            "pct": round(r["tk"] / att * 100, 1) if att else 0,
            "dom": r["dom"], "dom_pct": round(r["dom"] / att * 100, 1) if att else 0,
            "passive": r["passive"], "oa": r["oa"],
            "legs": r["legs"], "ht_tot": r["ht_tot"],
            "leg_pct": round(r["legs"] / r["ht_tot"] * 100, 1) if r["ht_tot"] else 0,
            "jck": r["jck"],
            "lo_steal": r["lo_steal"], "fit": r["fit"], "try_saver": r["try_saver"],
            "to_t": r["tow_tackle"] + r["fit"],
            "tow": r["tow_tackle"] + r["fit"] + (r["ruck_pw"] or 0) + r["jck"] + r["lo_steal"] + (r["roa_tow"] or 0),
            # Tackle TOW + Forced in Touch + Ruck/Penalty Won + Jackal + Lineout Steal + Ruck OOA/Turnover Won
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
            "bip": mn(recs, "at_tot") / 60.0,                          # at_tot は BIP_v2（GK/RS 除外済み）
            "poss": rate(recs, "at_kub", "poss_den"),                  # 変更なし（分母は v2 と同じ）
            "terr": rate(recs, "terr_num_v2", "terr_den_v2"),          # v2（中点・BIP_v2）
            "tries": mn(recs, "tries"),
            "tries_con": mn(recs, "tries_conceded"),
            "trate": rate(recs, "to_con", "attacks"),
            "pen": mn(recs, "pen"),
            # kicking
            "kicks": mn(recs, "kicks"), "km": mn(recs, "km"),
            "avg_kick": ratio(recs, "km", "kicks"),
            "r2k": ratio(recs, "rucks", "kicks"),
            "regain": mn(recs, "regain"), "contest_tot": mn(recs, "contest_tot"), "hg": mn(recs, "hg"),
            "gk_pct": rate(recs, "gk_made", "gk_att"),
            # attack
            "carries": mn(recs, "carries"), "metres": mn(recs, "metres"),
            # 旧: "gl": rate(recs, "glo", "carries"),
            "gl": rate(recs, "glo", "ruck_gl_d"),
            "lqb": rate(recs, "lqb_n", "rucks"),
            "offloads": mn(recs, "offloads"),
            "db": mn(recs, "db"), "lb": mn(recs, "lb"),
            "e22": mn(recs, "e22"), "c22": mn(recs, "c22"), "s22": mn(recs, "s22"),
            "c22_pct": rate(recs, "c22", "e22"),
            "s22_pct": rate(recs, "s22", "e22"),
            "kub_success": mn(recs, "kub_success_pct"),
            "to_con": mn(recs, "to_con"),
            # defence
            "tk": mn(recs, "tk"), "mt": mn(recs, "mt"),
            "tack_att": mn(recs, "tk") + mn(recs, "mt"),
            "tack_pct": rate(recs, "tk", None) if False else (
                sum(r["tk"] for r in recs) / sum(r["tk"] + r["mt"] for r in recs) * 100
                if sum(r["tk"] + r["mt"] for r in recs) else 0.0),
            "dom": mn(recs, "dom"), "dom_pct": rate(recs, "dom", "tk"),
            "passive": mn(recs, "passive"), "oa": mn(recs, "oa"),
            "tw": mn(recs, "tw"),
            # 旧: "opp_gl": rate(recs, "opp_glo", "opp_carries"),
            "opp_gl": rate(recs, "opp_glo", "opp_ruck_gl_d"),
            "opp_lqb": rate(recs, "opp_lqb", "opp_rucks"),
            "opp_db": mn(recs, "opp_db"),
            "opp_e22": mn(recs, "opp_e22"),
            "opp_success": mn(recs, "opp_success_pct"),
            # set piece
            "lo_won": mn(recs, "lo_won"), "lo_lost": mn(recs, "lo_lost"),
            "lo_steal": mn(recs, "lo_steal"), "lo_pct": rate(recs, "lo_won", "lo_throw"),
            "sc_tot": mn(recs, "sc_tot"), "sc_reset": mn(recs, "sc_reset"),
            "sc_pct": round(sum(r["sc_won"] for r in recs) / max(1, sum(r["sc_tot"] - r["sc_reset"] for r in recs)) * 100, 1),
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
            "pos_group": pen_pos,
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
         {h:'Possession %',fn:r=>r.poss_den?f1(r.at_kub/r.poss_den*100):'-'},
         /* OLD: {h:'Territory %',fn:r=>r.terr_den?f1(r.terr_num/r.terr_den*100):'-'}, */
         {h:'Territory %',fn:r=>r.terr_den_v2?f1(r.terr_num_v2/r.terr_den_v2*100):'-'},
         {h:'Tries Scored',fn:r=>r.tries},
         {h:'Tries Conceded',fn:r=>r.tries_conceded},
         {h:'Turnover Rate %',fn:r=>f1(r.to_con/r.attacks*100)},
         {h:'Penalties Conceded',fn:r=>r.pen},
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
         // 旧: ['regain','Contest Ret','Own Player – Collected /match',1,true],
         ['regain','Contest Retained','Own Player - Collected / Pressure Error / Pressure in Touch / Try Kick /match',1,true],
         ['hg','Kick Hit Grass','Collected Bounce /match',1,null],
         ['gk_pct','Goal Kicking %','goals ÷ attempts',1,true],
         ['trate','Turnover Rate %','TO conceded ÷ attacks',1,false],
       ]);
       const it=itTable(baseCols.concat([
         {h:'Ball In Play (min)',fn:r=>f1(r.at_tot/60)},
         {h:'Possession %',fn:r=>r.poss_den?f1(r.at_kub/r.poss_den*100):'-'},
         /* OLD: {h:'Territory %',fn:r=>r.terr_den?f1(r.terr_num/r.terr_den*100):'-'}, */
         {h:'Territory %',fn:r=>r.terr_den_v2?f1(r.terr_num_v2/r.terr_den_v2*100):'-'},
         {h:'Kicks In Play',fn:r=>r.kicks},
         {h:'Kick Metres',fn:r=>r.km},
         {h:'Avg Metres / Kick',fn:r=>r.kicks?f1(r.km/r.kicks):'-'},
         {h:'Ruck : Kick Ratio',fn:r=>r.kicks?f2(r.rucks/r.kicks):'-'},
         // 旧: {h:'Contest Ret',fn:r=>r.regain},
         {h:'Contest Retained',fn:r=>r.regain},
         {h:'Kick Hit Grass',fn:r=>r.hg},
         {h:'Turnover Rate %',fn:r=>f1(r.to_con/r.attacks*100)},
       ]));
       return `<div class="sec-title">Win / Loss / Season — averages</div>${avg}
         <div class="sec-title">Match-by-match</div>${it}
         // 旧: <div class="note">Contest Ret = contest kicks (Bomb/Low/Chip/Cross Pitch) regained. Kick Hit Grass = Collected Bounce only
         <div class="note">Contest Retained = contest kicks 5種 (Bomb/Low/Chip/Cross Pitch/Box) のうち Own Player - Collected / Pressure Error / Pressure in Touch / Try Kick. Kick Hit Grass = Collected Bounce only
           (kick-in-touch-on-bounce excluded). GK% = (Conv+PG+DG made) ÷ attempts.</div>`;
     }},
     {id:'attack',title:'Attack',build:()=>{
       const avg=avgTable([
         ['gl','Gainline %','Ruck Gainline: Over Previous Gainline ÷ (548+549+550)',1,true],
         ['lqb','LQB %','rucks ≤3s (Lightning Quick Ball)',1,true],
         ['carries','Ball Carries','per match',1,null],
         ['metres','Carry Metres','per match',0,true],
         ['db','Defenders Beaten','per match',1,true],
         ['lb','Linebreaks','Attacking Qualities/Initial Break /match',1,true],
         ['offloads','Offloads','successful (to own player)',1,true],
         ['e22','22m Entries','Enters+Starts into Opposition 22 /match',1,true],
         ['kub_success','22m Strike Conv %','(Try + Pen Goal outcomes) ÷ Attacking 22 Entry',1,true],
         ['c22','Carried into 22m','Enters into Opposition 22 /match',1,true],
         ['s22','Started in 22m','Starts inside Opposition 22 /match',1,true],
         ['to_con','Turnovers Conceded','per match',1,false],
       ]);
       const it=itTable(baseCols.concat([
         // 旧: {h:'Gainline %',fn:r=>r.carries?f1(r.glo/r.carries*100):'-'},
         {h:'Gainline %',fn:r=>r.ruck_gl_d?f1(r.glo/r.ruck_gl_d*100):'-'},
         {h:'LQB %',fn:r=>r.rucks?f1(r.lqb_n/r.rucks*100):'-'},
         {h:'Ball Carries',fn:r=>r.carries},
         {h:'Carry Metres',fn:r=>r.metres},
         {h:'Defenders Beaten',fn:r=>r.db},
         {h:'Linebreaks',fn:r=>r.lb},
         {h:'Offloads',fn:r=>r.offloads},
         {h:'22m Entries',fn:r=>r.e22},
         {h:'22m Strike Conv %',fn:r=>r.e22?f1(r.kub_success_pct)+'%':'-'},
         {h:'Carried into 22m',fn:r=>r.c22},
         {h:'Started in 22m',fn:r=>r.s22},
         {h:'Turnovers Conceded',fn:r=>r.to_con},
       ]));
       return `<div class="sec-title">Win / Loss / Season — averages</div>${avg}
         <div class="sec-title">Match-by-match</div>${it}
         <div class="note">Gainline % = Ruck Gainline 'Over Previous Gainline' (Q3=548) ÷ (548+549+550 合計、N/A=551除外). LQB % = rucks with ruck-speed ≤3s.
           Defenders Beaten = Attacking Qualities/Defender Beaten. Linebreaks = Attacking Qualities/Initial Break (Line Break + Kick Line Break + Intercepted Break).
           22m Entries = Possession events with qualifier4 'Enters into Opposition 22' + 'Starts inside Opposition 22'.
           22m Strike Conv % = (Try + Penalty Goal Attempt outcomes from Attacking 22 Entry) ÷ total Attacking 22 Entry count × 100. Note: Attacking 22 Entry count may differ slightly from Possession 22m Entries.</div>`;
     }},
     {id:'defence',title:'Defence',build:()=>{
       const avg=avgTable([
         ['tack_att','Tackle Attempts','per match',1,null],
         ['tack_pct','Tackle %','made ÷ attempted',1,true],
         ['dom','Dominant Tackles','per match',1,true],
         ['dom_pct','Dominant Tackle %','dominant ÷ tackles made',1,true],
         ['passive','Passive Tackles','per match',1,false],
         ['oa','Offloads Allowed','per match',1,false],
         ['tw','Turnovers Won','Poss TO + Jackal /match',1,true],
         ['pen','Penalties Conceded','per match',1,false],
         ['opp_db','Opp Defenders Beaten','opponent Attacking Qualities/Defender Beaten /match',1,false],
         ['opp_gl','Opponent Gainline %','Ruck Gainline: opponent Over Previous Gainline ÷ (548+549+550)',1,false],
         ['opp_lqb','Opponent LQB %','opponent rucks ≤3s',1,false],
         ['tries_con','Tries Conceded','per match',1,false],
         ['opp_e22','Opponent 22m Entries','Enters+Starts into Opposition 22 /match',1,false],
         ['opp_success','Opponent 22m Strike Conv %','(Try + Pen Goal outcomes) ÷ Attacking 22 Entry',1,false],
       ]);
       const it=itTable(baseCols.concat([
         {h:'Tackles Made',fn:r=>r.tk},
         {h:'Tackles Missed',fn:r=>r.mt},
         {h:'Tackle Attempts',fn:r=>r.tk+r.mt},
         {h:'Tackle %',fn:r=>(r.tk+r.mt)?f1(r.tk/(r.tk+r.mt)*100):'-'},
         {h:'Dominant Tackle %',fn:r=>r.tk?f1(r.dom/r.tk*100):'-'},
         {h:'Turnovers Won',fn:r=>r.tw},
         {h:'Infringements',fn:r=>r.pen},
         {h:'Opp Defenders Beaten',hcls:'opp',cls:'oppcol',fn:r=>r.opp_db},
         // 旧: {h:'Opponent Gainline %',hcls:'opp',cls:'oppcol',fn:r=>r.opp_carries?f1(r.opp_glo/r.opp_carries*100):'-'},
         {h:'Opponent Gainline %',hcls:'opp',cls:'oppcol',fn:r=>r.opp_ruck_gl_d?f1(r.opp_glo/r.opp_ruck_gl_d*100):'-'},
         {h:'Opponent LQB %',hcls:'opp',cls:'oppcol',fn:r=>r.opp_rucks?f1(r.opp_lqb/r.opp_rucks*100):'-'},
         {h:'Tries Conceded',hcls:'opp',cls:'oppcol',fn:r=>r.tries_conceded},
         {h:'Opponent 22m Entries',hcls:'opp',cls:'oppcol',fn:r=>r.opp_e22},
         {h:'Opp 22m Strike Conv %',hcls:'opp',cls:'oppcol',fn:r=>r.opp_e22?f1(r.opp_success_pct)+'%':'-'},
       ]));
       return `<div class="sec-title">Win / Loss / Season — averages</div>${avg}
         <div class="sec-title">Match-by-match</div>${it}
         <div class="note">Tackle % = tackles made ÷ (made+missed). Dominant Tackle % = qualifier 'Dominant Tackle' ÷ tackles made.
           Turnovers Won = Possession 'Turnover Won' + Jackal success (events within 0.5 match-min de-duplicated).
           <span style="color:#c4600f;font-weight:700">Orange columns = opponent stats</span>: Gainline % / LQB % / Tries scored vs Kubota /
           Opponent 22m Entries = Possession qualifier4 'Enters into Opposition 22' + 'Starts inside Opposition 22' by the opposition.
           Opponent 22m Strike Conv % = (Try + Penalty Goal Attempt outcomes from Attacking 22 Entry) ÷ total Attacking 22 Entry count × 100. Note: Attacking 22 Entry count may differ from Possession 22m Entries.</div>`;
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
         {h:'Scrum Won %',fn:r=>(r.sc_tot-r.sc_reset)?f0(r.sc_won/(r.sc_tot-r.sc_reset)*100)+'%':'-'},
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
       const posOrder=['Front Row','Lock','Loosie','Inside','Midfield','Back 3'];
       const posMax=Math.max(...posOrder.map(g=>P.pos_group[g]),1);
       const posBars=posOrder.filter(g=>P.pos_group[g]).map(g=>`<div class="pen-bar-row">
         <span class="pen-bar-label">${g}</span>
         <div class="pen-bar-track"><div class="pen-bar-fill" style="width:${Math.round(P.pos_group[g]/posMax*100)}%"></div></div>
         <span class="pen-bar-num">${P.pos_group[g]}</span></div>`).join('');
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
             <div class="sec-title">By Position Group (season total)</div>${posBars}
           </div>
           <div class="pen-col">
             <div class="sec-title">Attack vs Defence (qualifier3)</div>${stack}
             <div class="sec-title">By Half</div>${hb}
             <div class="sec-title">By Quarter</div><div class="vbar-chart">${qb}</div>
           </div>
         </div>
         <div class="note">Infringements = Penalty Conceded (Full Penalty ${P.full} + Free Kick ${P.fk} = ${P.total}).
           League avg = all ${Lg.tm} team-matches in rugby.db (12 teams × Kubota's ${DATA.n} fixtures); Δ negative = fewer than league (better).
           Attack/Defence from qualifier3. Quarters from match-minute (Q1≤20', Q2≤40', Q3≤60', Q4&gt;60').
           Position groups: Front Row (1-3), Lock (4-5), Loosie (6-8), Inside (9-10), Midfield (12-13), Back 3 (11,14,15).</div>`;
     }},
     {id:'ind-attack',title:'Indiv Attack',build:()=>{
       const R=DATA.players_attack;
       const tot=R.reduce((a,r)=>{['carries','metres','pcm','lb','db','ol','tries','err','passes','kicks','kick_m','ooa13','ooa4'].forEach(k=>a[k]=(a[k]||0)+(r[k]||0));return a;},{});
       // recompute weighted totals needing raw components
       const totGlo=R.reduce((s,r)=>s+Math.round(r.gl/100*r.carries),0);
       const totAccN=R.reduce((s,r)=>s+Math.round((r.pass_acc||0)/100*(r.passes||0)),0);
       const totOOA=tot.ooa13+tot.ooa4;
       const rows=R.map(r=>`<tr>
         <td class="shirt">${r.shirt}</td><td class="name">${r.name}</td><td class="pos">${r.pos}</td><td>${r.pt}</td>
         <td>${r.carries}</td><td>${r.metres}</td><td>${r.avg}</td>
         <td>${r.carries?r.pcm_per_carry:'-'}</td>
         <td class="${r.gl>=60?'cell-good':r.gl&&r.gl<45?'cell-warn':''}">${r.carries?r.gl+'%':'-'}</td>
         <td class="${r.lb?'cell-good':'cell-dim'}">${r.lb||'-'}</td>
         <td>${r.db||'-'}</td><td>${r.ol||'-'}</td>
         <td class="${r.tries?'cell-good':'cell-dim'}">${r.tries||'-'}</td>
         <td class="${r.err>=20?'cell-warn':''}">${r.err||'-'}</td>
         <td>${r.passes||'-'}</td><td>${r.passes?r.pass_acc+'%':'-'}</td>
         <td>${r.kicks||'-'}</td><td>${r.kick_m||'-'}</td><td>${r.kicks?r.avg_kick:'-'}</td>
         <td>${r.ooa13||'-'}</td><td>${r.ooa4||'-'}</td>
         <td class="${(r.ooa13+r.ooa4)?(r.ooa_eff>=70?'cell-good':r.ooa_eff<55?'cell-warn':''):'cell-dim'}">${(r.ooa13+r.ooa4)?r.ooa_eff+'%':'-'}</td></tr>`).join('');
       return `<div class="sec-title">Individual Attack — season totals (ranked by position)</div>
         <div class="rank-wrap"><table class="rank-table">
           <thead><tr><th>No.</th><th class="l">Name</th><th class="l">Position</th><th>Play Time (min)</th>
             <th>Ball Carries</th><th>Carry Metres</th><th>Avg m/Carry</th><th>PC m/Carry</th><th>Gainline %</th>
             <th>Linebreaks</th><th>Defenders Beaten</th><th>Offloads</th><th>Tries</th><th>Errors</th>
             <th>Passes</th><th>Pass Accuracy %</th><th>Kicks In Play</th><th>Kick Metres</th><th>Avg Kick Metres</th>
             <th>OOA 1-3s</th><th>OOA 4+s</th><th>OOA Effectiveness %</th></tr></thead>
           <tbody>${rows}</tbody>
           <tfoot><tr><td></td><td class="l">TOTAL (${R.length} players)</td><td></td><td></td>
             <td>${tot.carries}</td><td>${tot.metres}</td><td>${tot.carries?(tot.metres/tot.carries).toFixed(1):'-'}</td>
             <td>${tot.carries?(tot.pcm/tot.carries).toFixed(2):'-'}</td>
             <td>${tot.carries?(totGlo/tot.carries*100).toFixed(1)+'%':'-'}</td>
             <td>${tot.lb}</td><td>${tot.db}</td><td>${tot.ol}</td><td>${tot.tries}</td><td>${tot.err}</td>
             <td>${tot.passes}</td><td>${tot.passes?(totAccN/tot.passes*100).toFixed(1)+'%':'-'}</td>
             <td>${tot.kicks}</td><td>${tot.kick_m}</td><td>${tot.kicks?(tot.kick_m/tot.kicks).toFixed(1):'-'}</td>
             <td>${tot.ooa13}</td><td>${tot.ooa4}</td><td>${totOOA?(tot.ooa13/totOOA*100).toFixed(1)+'%':'-'}</td></tr></tfoot>
         </table></div>
         <div class="note">Avg m/Carry = Carry Metres ÷ carries · PC m/Carry = Post-Contact Metres (metres3) ÷ carries · GL% = carries crossing the gainline ÷ carries ·
           LB = Linebreaks · DB = Defenders Beaten · OL = Offloads (to own player) · Err = Turnovers conceded ·
           Acc% = passes not Incomplete/Error/Forward/Intercepted/Off-Target ·
           OOA 1-3 / 4+ = ruck speed ≤3s / &gt;3s · OOA Eff% = 1-3 ÷ (1-3 + 4+).</div>`;
     }},
     {id:'ind-defence',title:'Indiv Defence',build:()=>{
       const R=DATA.players_defence;
       const tot=R.reduce((a,r)=>{['tk','mt','att','tkl_assist','dom','try_saver','to_t','passive','oa','legs','ht_tot','jck','tow','pen'].forEach(k=>a[k]=(a[k]||0)+(r[k]||0));return a;},{});
       const rows=R.map(r=>`<tr>
         <td class="shirt">${r.shirt}</td><td class="name">${r.name}</td><td class="pos">${r.pos}</td><td>${r.pt}</td>
         <td>${r.att}</td><td class="${r.tkl_assist?'cell-good':'cell-dim'}">${r.tkl_assist||'-'}</td><td>${r.tk}</td><td class="${r.mt>=20?'cell-warn':''}">${r.mt}</td>
         <td class="${r.pct>=90?'cell-good':r.pct<75?'cell-warn':''}">${r.pct}%</td>
         <td>${r.ht_tot?r.leg_pct+'%':'-'}</td>
         <td class="${r.dom?'cell-good':'cell-dim'}">${r.dom||'-'}</td>
         <td>${r.att?r.dom_pct+'%':'-'}</td>
         <td class="${r.try_saver?'cell-good':'cell-dim'}">${r.try_saver||'-'}</td>
         <td class="${r.to_t?'cell-good':'cell-dim'}">${r.to_t||'-'}</td>
         <td class="${r.oa>=10?'cell-warn':''}">${r.oa||'-'}</td>
         <td>${r.passive||'-'}</td>
         <td class="${r.jck?'cell-good':'cell-dim'}">${r.jck||'-'}</td>
         <td class="${r.tow?'cell-good':'cell-dim'}">${r.tow||'-'}</td>
         <td class="${r.pen>=12?'cell-warn':''}">${r.pen||'-'}</td></tr>`).join('');
       return `<div class="sec-title">Individual Defence — season totals (ranked by tackles made)</div>
         <div class="rank-wrap"><table class="rank-table">
           <thead><tr><th>No.</th><th class="l">Name</th><th class="l">Position</th><th>Play Time (min)</th>
             <th>Tackle Attempts</th><th>Tackle Assist</th><th>Tackles Made</th><th>Tackles Missed</th><th>Tackle %</th><th>Leg Tackle %</th>
             <th>Dominant Tackles</th><th>Dominant Tackle %</th><th>Try Saver Tackles</th>
             <th>Turnover Won Tackles</th><th>Offloads Allowed</th><th>Passive Tackles</th>
             <th>Jackal Success</th><th>Turnovers Won</th><th>Infringements</th></tr></thead>
           <tbody>${rows}</tbody>
           <tfoot><tr><td></td><td class="l">TOTAL (${R.length} players)</td><td></td><td></td>
             <td>${tot.att}</td><td>${tot.tkl_assist}</td><td>${tot.tk}</td><td>${tot.mt}</td>
             <td>${(tot.tk/tot.att*100).toFixed(1)}%</td>
             <td>${(tot.legs/tot.ht_tot*100).toFixed(1)}%</td>
             <td>${tot.dom}</td><td>${(tot.dom/tot.att*100).toFixed(1)}%</td>
             <td>${tot.try_saver}</td><td>${tot.to_t}</td>
             <td>${tot.oa}</td><td>${tot.passive}</td><td>${tot.jck}</td><td>${tot.tow}</td>
             <td>${tot.pen}</td></tr></tfoot>
         </table></div>
         <div class="note">Att/Made/Miss tackles · Tackle Assist = qualifier3Name 'Assist' · Tkl% = made ÷ att · Leg% = leg tackles ÷ tackles with height tag (qualifier6) ·
           Dom% = dominant ÷ att · Try Saver = Tackle/Try Saver results ·
           <b>Turnover Won Tackle = Tackle/Turnover Won + Forced in Touch Tackles</b> (Forced in Touch Tackles not shown separately) ·
           OA = offloads allowed (own tackle) · Passive = passive tackles · Jackal = Collection/Jackal success ·
           <b>Turnovers Won = tackle turnovers (Tackle/Turnover Won) + breakdown penalties won (Ruck OOA/Penalty Won) + Lineout Steals
           + Forced in Touch Tackles</b> ·
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
    

    con.close()


# ═══════════════════════════════════════════════════════════════
# SECTION 4: SCOUTING REPORT
# ═══════════════════════════════════════════════════════════════

def compute_stats(df, max_round):
    df = df[df['roundNumber'] <= max_round].copy()
    df['oppTeam'] = df.apply(
        lambda r: r['awayTeamName'] if r['teamName']==r['homeTeamName'] else r['homeTeamName'], axis=1)
    df = df.sort_values(['FXID','MatchTime']).reset_index(drop=True)

    teams   = sorted(df['teamName'].unique())
    m       = df.groupby('teamName')['FXID'].nunique()

    carries  = df[df['actionName']=='Carry']
    passes   = df[df['actionName']=='Pass']
    kicks    = df[df['actionName']=='Kick']
    ruck     = df[df['actionName']=='Ruck']
    ruck_ooa = df[df['actionName']=='Ruck OOA']
    poss     = df[df['actionName']=='Possession']
    seqs     = df[df['actionName']=='Sequences']
    poss_try = poss[poss['ActionResultName']=='Try']
    tries_a  = df[df['actionName']=='Try']
    a22      = poss[poss['qualifier4Name'].isin(['Enters into Opposition 22', 'Starts inside Opposition 22'])]
    a22_car  = poss[poss['qualifier4Name']=='Enters into Opposition 22']
    a22_sta  = poss[poss['qualifier4Name']=='Starts inside Opposition 22']
    aq       = df[df['actionName']=='Attacking Qualities']
    lo_throw = df[df['actionName']=='Lineout Throw']
    scrum    = df[df['actionName']=='Scrum']
    maul     = df[df['actionName']=='Maul']
    tackles  = df[df['actionName']=='Tackle']
    missed_t = df[df['actionName']=='Missed Tackle']
    pen_con  = df[df['actionName']=='Penalty Conceded']
    coll     = df[df['actionName']=='Collection']
    lo_take  = df[df['actionName']=='Lineout Take']
    atk22_ev = df[df['actionName']=='Attacking 22 Entry']

    # Kicks in Play = qualifier3Name が 'Kick in Play' または 'Kick in Play (Own 22)'
    # これがOptaの定義と完全一致（全チームMAE=0.000）
    kicks_ip  = kicks[kicks['qualifier3Name'].isin(['Kick in Play','Kick in Play (Own 22)'])]
    kicks_ng  = kicks[~kicks['ActionResultName'].isin(DEAD) & ~kicks['ActionTypeName'].isin(GOAL)]  # タッチ除く（Opp Half計算用）
    kicks_oh  = kicks_ng[kicks_ng['x_coord'] < 50]
    kicks_4060= kicks_ng[(kicks_ng['x_coord']>=40)&(kicks_ng['x_coord']<=60)]
    cont_k    = kicks[kicks['ActionTypeName'].isin(CONT)]  # CONT は5種 (グローバル定数更新済み)
    # 旧: ret_k = cont_k[cont_k['ActionResultName'].isin(['Own Player - Collected','Pressure Error','Pressure Carried Over'])]
    ret_k     = cont_k[cont_k['ActionResultName'].isin(
                 ['Own Player - Collected','Pressure Error','Pressure in Touch','Try Kick'])]
    passes_no = passes[passes['ActionTypeName']!='Offload']
    offload   = passes[passes['ActionTypeName']=='Offload']

    # =====================================================
    # Possession/BIP/Territory: ps_timestamp/ps_endstampを使用
    # Attack Time  = Possession + Scrum + Lineout Throw の合算（Optaと一致 MAE=9.4s）
    # Ball in Play = Possession + Goal Kick + Restart の合算（Optaと一致）
    # Defence Time = BIP - Attack Time
    # =====================================================
    poss_dur = poss.copy()
    poss_dur['dur'] = poss_dur['ps_endstamp'] - poss_dur['ps_timestamp']
    poss_dur = poss_dur[poss_dur['dur'] > 0]

    scrum_dur  = df[df['actionName']=='Scrum'].copy()
    scrum_dur['dur'] = scrum_dur['ps_endstamp'] - scrum_dur['ps_timestamp']
    scrum_dur  = scrum_dur[scrum_dur['dur'] > 0]

    lo_dur     = df[df['actionName']=='Lineout Throw'].copy()
    lo_dur['dur'] = lo_dur['ps_endstamp'] - lo_dur['ps_timestamp']
    lo_dur     = lo_dur[lo_dur['dur'] > 0]

    goal_k = df[df['actionName']=='Goal Kick'].copy()
    goal_k['dur'] = goal_k['ps_endstamp'] - goal_k['ps_timestamp']
    restart_a = df[df['actionName']=='Restart'].copy()
    restart_a['dur'] = restart_a['ps_endstamp'] - restart_a['ps_timestamp']

    # Attack Time per FXID = Possession + Scrum + Lineout
    atk_m = (poss_dur.groupby(['teamName','FXID'])['dur'].sum()
             .add(scrum_dur.groupby(['teamName','FXID'])['dur'].sum(), fill_value=0)
             .add(lo_dur.groupby(['teamName','FXID'])['dur'].sum(), fill_value=0))
    atk_pg = atk_m.groupby('teamName').mean()/60

    # BIP_v2 per FXID（GK・RS 除外: Poss+Scrum+LO のみ）
    bip_fxid = {}
    for fxid in df['FXID'].unique():
        bip_fxid[fxid] = (
            poss_dur[poss_dur['FXID']==fxid]['dur'].sum() +
            scrum_dur[scrum_dur['FXID']==fxid]['dur'].sum() +
            lo_dur[lo_dur['FXID']==fxid]['dur'].sum()
        )

    bip_dict = {}
    for t in teams:
        fxids = df[df['teamName']==t]['FXID'].unique()
        bip_dict[t] = sum(bip_fxid.get(f,0) for f in fxids)/len(fxids)/60
    bip_pg = pd.Series(bip_dict)
    def_pg = bip_pg - atk_pg

    # OLD: Poss のみ（ロールバック用）
    # poss_pct = {}
    # for t in teams:
    #     a = poss_dur[poss_dur['teamName']==t].groupby('FXID')['dur'].sum()
    #     d = poss_dur[poss_dur['oppTeam']==t].groupby('FXID')['dur'].sum()
    #     c = a.index.intersection(d.index)
    #     tot = a[c].sum()+d[c].sum()
    #     poss_pct[t] = round(a[c].sum()/tot*100,1) if tot else 0
    # v2: Poss+Sc+LO / BIP_v2（マッチレポートと同一定義）
    poss_pct = {}
    for t in teams:
        fxids = df[df['teamName']==t]['FXID'].unique()
        num = sum(atk_m.get((t, f), 0) for f in fxids)
        den = sum(bip_fxid.get(f, 0) for f in fxids)
        poss_pct[t] = round(num / den * 100, 1) if den else 0

    # Territory v2: 中点座標 (x_start+x_end)/2 >50 で判定・BIP_v2 分母・ゼロサム式
    _bip_acts = ['Possession','Scrum','Lineout Throw']
    _bip_terr = df[df['actionName'].isin(_bip_acts)].copy()
    _bip_terr['dur'] = (_bip_terr['ps_endstamp'] - _bip_terr['ps_timestamp']).clip(lower=0)
    _bip_terr = _bip_terr[_bip_terr['dur'] > 0].copy()
    _has_xe = _bip_terr['x_coord_end'].notna() & _bip_terr['x_coord'].notna()
    _bip_terr['mid'] = _bip_terr['x_coord'].copy()
    _bip_terr.loc[_has_xe, 'mid'] = (_bip_terr.loc[_has_xe, 'x_coord'] + _bip_terr.loc[_has_xe, 'x_coord_end']) / 2
    _bip_terr = _bip_terr[_bip_terr['mid'].notna()].copy()
    _opp_map = df.groupby(['teamName','FXID'])['oppTeam'].first()
    _atk_fxid = _bip_terr[_bip_terr['mid'] > 50].groupby(['teamName','FXID'])['dur'].sum()
    _tot_fxid = _bip_terr.groupby(['teamName','FXID'])['dur'].sum()
    terr_v2 = {}
    for t in teams:
        fxids = df[df['teamName']==t]['FXID'].unique()
        vals = []
        for fxid in fxids:
            tn_k = _atk_fxid.get((t, fxid), 0)
            td_k = _tot_fxid.get((t, fxid), 0)
            opp_t = _opp_map.get((t, fxid))
            if opp_t is None: continue
            tn_o = _atk_fxid.get((opp_t, fxid), 0)
            td_o = _tot_fxid.get((opp_t, fxid), 0)
            den = td_k + td_o
            if den > 0: vals.append((tn_k + (td_o - tn_o)) / den * 100)
        terr_v2[t] = round(sum(vals)/len(vals), 1) if vals else 0
    terr_pct = pd.Series(terr_v2)

    # LQB: Ruckアクション(qualifier4Nameあり)が母数
    QL = ['0-1 Seconds','1-2 Seconds','2-3 Seconds']
    lqb_q = ruck[ruck['qualifier4Name'].isin(QL)].groupby('teamName').size()
    lqb_t = ruck.groupby('teamName').size()  # 全Ruck action（N/A含む）
    lqb_pct = (lqb_q/lqb_t*100).round(1)
    olqb_q  = ruck[ruck['qualifier4Name'].isin(QL)].groupby('oppTeam').size()
    olqb_t  = ruck.groupby('oppTeam').size()
    olqb_pct= (olqb_q/olqb_t*100).round(1)

    # Scrum
    SW = ['Won Outright','Won Penalty','Won Free Kick','Won Try']
    SL = ['Lost Pen Con','Lost Free Kick','Lost Outright']
    sc_w = scrum[scrum['ActionResultName'].isin(SW)].groupby('teamName').size()
    sc_l = scrum[scrum['ActionResultName'].isin(SL)].groupby('teamName').size()
    osc_w= scrum[scrum['ActionResultName'].isin(SW)].groupby('oppTeam').size()
    osc_l= scrum[scrum['ActionResultName'].isin(SL)].groupby('oppTeam').size()
    sc_pw= pen_con[pen_con['ActionTypeName']=='Scrum Offence'].groupby('oppTeam').size()
    sc_pc= pen_con[pen_con['ActionTypeName']=='Scrum Offence'].groupby('teamName').size()

    # Lineout
    lo_w = lo_throw[lo_throw['ActionResultName'].str.startswith('Won',na=False)].groupby('teamName').size()
    lo_t = lo_throw.groupby('teamName').size()
    olo_w= lo_throw[lo_throw['ActionResultName'].str.startswith('Won',na=False)].groupby('oppTeam').size()
    olo_t= lo_throw.groupby('oppTeam').size()

    # Maul
    maul_kz  = maul[(maul['x_coord']>=78)&(maul['x_coord']<=110)]

    # Turnover
    to_r = ruck_ooa[ruck_ooa['ActionTypeName']=='Turnover Won'].groupby('teamName').size()
    to_j = coll[(coll['ActionTypeName']=='Jackal')&(coll['ActionResultName']=='Success')].groupby('teamName').size()
    to_l = lo_take[lo_take['ActionTypeName'].str.contains('Steal',na=False)].groupby('teamName').size()
    to_s = df[df['actionName']=='Sequences'][df[df['actionName']=='Sequences']['ActionTypeName']=='Scrum Steal'].groupby('teamName').size()
    to_t = tackles[tackles['ActionResultName']=='Turnover Won'].groupby('teamName').size()
    to_f = tackles[tackles['ActionResultName']=='Forced in Touch'].groupby('oppTeam').size()
    to_total = to_r.add(to_j,fill_value=0).add(to_l,fill_value=0).add(to_s,fill_value=0).add(to_t,fill_value=0).add(to_f,fill_value=0)

    # FW/BK
    fw_c = carries[carries['playerpositionName'].isin(FW)].groupby('teamName').size()
    bk_c = carries[carries['playerpositionName'].isin(BK)].groupby('teamName').size()
    fw_p = passes[passes['playerpositionName'].isin(FW)].groupby('teamName').size()
    bk_p = passes[passes['playerpositionName'].isin(BK)].groupby('teamName').size()

    # LB
    lb_c = aq[aq['ActionTypeName']=='Initial Break'].groupby('teamName').size()
    db_c = aq[aq['ActionTypeName']=='Defender Beaten'].groupby('teamName').size()
    olb  = aq[aq['ActionTypeName']=='Initial Break'].groupby('oppTeam').size()
    odb  = aq[aq['ActionTypeName']=='Defender Beaten'].groupby('oppTeam').size()

    # 22m (Possession qualifier4_name ベース)
    a22_t = a22.groupby('teamName').size()
    a22_c = a22_car.groupby('teamName').size()
    a22_s = a22_sta.groupby('teamName').size()
    oa22  = a22.groupby('oppTeam').size()
    oa22c = a22_car.groupby('oppTeam').size()
    oa22s = a22_sta.groupby('oppTeam').size()

    # Attacking 22 Entry conversion (Opta standard)
    _A22_POS    = ['22 Entry Outcome - Try', '22 Entry Outcome - Penalty Goal Attempt']
    atk22_t     = atk22_ev.groupby('teamName').size()
    atk22_pos   = atk22_ev[atk22_ev['ActionTypeName'].isin(_A22_POS)].groupby('teamName').size()
    oatk22_t    = atk22_ev.groupby('oppTeam').size()
    oatk22_pos  = atk22_ev[atk22_ev['ActionTypeName'].isin(_A22_POS)].groupby('oppTeam').size()

    # Points
    ms = df.groupby('FXID').first()[['homeTeamName','awayTeamName','hometeamFTscore','awayteamFTscore']]
    pts_s,pts_c = {},{}
    for _,r in ms.iterrows():
        pts_s[r['homeTeamName']] = pts_s.get(r['homeTeamName'],0)+r['hometeamFTscore']
        pts_s[r['awayTeamName']] = pts_s.get(r['awayTeamName'],0)+r['awayteamFTscore']
        pts_c[r['homeTeamName']] = pts_c.get(r['homeTeamName'],0)+r['awayteamFTscore']
        pts_c[r['awayTeamName']] = pts_c.get(r['awayTeamName'],0)+r['hometeamFTscore']

    # Tackle
    t_made = tackles[tackles['ActionResultName']!='Missed']
    t_att  = t_made.groupby('teamName').size()+missed_t.groupby('teamName').size()
    t_succ = (t_made.groupby('teamName').size()/t_att*100).round(1)

    # Ruck to Kick: Ruck OOA 1st Entry / Kick（Optaに最も近い定義 MAE=0.317）
    ruck_act = df[df['actionName']=='Ruck']
    ro = ruck_act.groupby('teamName').size()       # Ruck action数（LQB用）
    oro= ruck_act.groupby('oppTeam').size()
    ro_ooa = ruck_ooa.groupby('teamName').size()   # Ruck OOA全体
    oro_ooa= ruck_ooa.groupby('oppTeam').size()
    # Ruck OOA 1st Entry = ラック形成数（Optaのラック数に相当）
    r1st = df[(df['actionName']=='Ruck OOA')&(df['ActionResultName']=='Own Team 1st Entry')]
    ro_1st  = r1st.groupby('teamName').size()
    oro_1st = r1st.groupby('oppTeam').size()
    ki = kicks_ip.groupby('teamName').size()   # Kicks in Play（qualifier3Nameベース）
    oki= kicks_ip.groupby('oppTeam').size()
    km = kicks_ip.groupby('teamName')['Metres'].sum()   # Kicks in Playのメートルのみ
    okm= kicks_ip.groupby('oppTeam')['Metres'].sum()
    ra_pg = ro  # Ruck action数（per game換算はm=matchesで行う）

    res = pd.DataFrame(index=teams); res.index.name='Team'

    # ---- Overview ----
    res['OV_Possession_pct']   = pd.Series(poss_pct).round(1)
    res['OV_Territory_pct']    = terr_pct
    res['OV_BallInPlay_min']   = bip_pg.round(1)
    res['OV_AttackTime_min']   = atk_pg.round(1)
    res['OV_DefenceTime_min']  = def_pg.round(1)
    res['OV_PointsScored']     = pd.Series(pts_s)
    res['OV_PointsFor_PG']     = (pd.Series(pts_s) / m).round(1)
    res['OV_TriesScored']      = tries_a.groupby('teamName').size()
    # Turnover Rate = (PossTO + LOlost + SClost) / (Poss + LOlost + SClost) × 100
    _lo_lost = lo_throw[lo_throw['ActionResultName'].str.startswith('Lost', na=False)]
    _sc_lost = scrum[scrum['ActionResultName'].isin(SL)]
    _poss_to = poss[poss['ActionResultName'].isin(['Turnover','Turnover (Scrum)'])]
    _lo_lost_n = _lo_lost.groupby('teamName').size()
    _sc_lost_n = _sc_lost.groupby('teamName').size()
    _poss_to_n = _poss_to.groupby('teamName').size()
    _poss_n    = poss.groupby('teamName').size()
    _to_den    = _poss_n.add(_lo_lost_n, fill_value=0).add(_sc_lost_n, fill_value=0)
    _to_num    = _poss_to_n.add(_lo_lost_n, fill_value=0).add(_sc_lost_n, fill_value=0)
    res['OV_TORate_pct']       = (_to_num / _to_den * 100).round(1)
    # Turnover Rate at Opposition Half (x_coord >= 50)
    poss_xok    = poss[poss['x_coord'].notna()].copy()
    poss_xok['_x'] = poss_xok['x_coord'].astype(float)
    lo_lost_xok = _lo_lost[_lo_lost['x_coord'].notna()].copy()
    lo_lost_xok['_x'] = lo_lost_xok['x_coord'].astype(float)
    sc_lost_xok = _sc_lost[_sc_lost['x_coord'].notna()].copy()
    sc_lost_xok['_x'] = sc_lost_xok['x_coord'].astype(float)
    _opp_poss   = poss_xok[poss_xok['_x'] >= 50]
    _opp_lo     = lo_lost_xok[lo_lost_xok['_x'] >= 50]
    _opp_sc     = sc_lost_xok[sc_lost_xok['_x'] >= 50]
    _opp_pto    = _opp_poss[_opp_poss['ActionResultName'].isin(['Turnover','Turnover (Scrum)'])]
    _opp_to_den = _opp_poss.groupby('teamName').size().add(_opp_lo.groupby('teamName').size(), fill_value=0).add(_opp_sc.groupby('teamName').size(), fill_value=0)
    _opp_to_num = _opp_pto.groupby('teamName').size().add(_opp_lo.groupby('teamName').size(), fill_value=0).add(_opp_sc.groupby('teamName').size(), fill_value=0)
    res['OV_OppTORate_pct']    = (_opp_to_num / _opp_to_den * 100).round(1)
    res['OV_RuckToKick']       = (ki/ro).round(3)
    res['OV_PassToKick']       = (passes_no.groupby('teamName').size()/ki).round(1)
    res['OV_KicksInPlay_PG']   = (ki/m).round(1)
    res['OV_Offload_PG']       = (offload.groupby('teamName').size()/m).round(2)
    # Offload成功（自チームに渡った）
    offload_success = passes[(passes['ActionTypeName']=='Offload')&(passes['ActionResultName']=='Own Player')]
    res['ATT_OffloadSuccess_PG'] = (offload_success.groupby('teamName').size()/m).round(2)
    res['OV_LineBreaks_PG']    = (lb_c/m).round(2)
    res['OV_DefBeaten_PG']     = (db_c/m).round(1)
    res['OV_PointsConceded']   = pd.Series(pts_c)
    res['OV_PointsAgainst_PG'] = (pd.Series(pts_c) / m).round(1)
    res['OV_TriesConceded']    = tries_a.groupby('oppTeam').size()
    res['OV_TackleSuccess_pct']= t_succ
    res['OV_TurnoverWon_PG']   = (to_total/m).round(2)
    # Turnover Conceded = Turnover action（全種）の自チーム視点
    # 約14-15/G でOptaと一致
    turnover_act = df[df['actionName']=='Turnover']
    to_conc = turnover_act.groupby('teamName').size()
    to_won_act = turnover_act.groupby('oppTeam').size()
    res['OV_TurnoverConc_PG']  = (to_conc/m).round(1)
    res['OV_LBConceded_PG']    = (olb/m).round(2)
    res['OV_DefBeatenConc_PG'] = (odb/m).round(1)
    res['OV_PenaltiesCon_PG']  = (pen_con.groupby('teamName').size()/m).round(2)
    res['OV_OwnLineout_pct']   = (lo_w/lo_t*100).round(1)
    res['OV_OppLineout_pct']   = (olo_w/olo_t*100).round(1)
    res['OV_OwnScrum_pct']     = (sc_w/(sc_w+sc_l)*100).round(1)
    res['OV_OppScrum_pct']     = (osc_w/(osc_w+osc_l)*100).round(1)
    res['TRY_22mEntry_PG']      = (a22_t/m).round(2)
    res['TRY_22mCarried_PG']    = (a22_c/m).round(2)
    res['TRY_22mStarted_PG']    = (a22_s/m).round(2)
    res['TRY_Opp22mEntry_PG']   = (oa22/m).round(2)
    res['TRY_Opp22mCarried_PG'] = (oa22c/m).round(2)
    res['TRY_Opp22mStarted_PG'] = (oa22s/m).round(2)

    # ---- Attack ----
    res['ATT_Carries_PG']      = (carries.groupby('teamName').size()/m).round(1)
    res['ATT_CarryMetres_PG']  = (carries.groupby('teamName')['Metres'].sum()/m).round(0)
    res['ATT_MetresPerCarry']  = (carries.groupby('teamName')['Metres'].sum()/carries.groupby('teamName').size()).round(2)
    res['ATT_PostContMetres_PG'] = (pd.to_numeric(carries['Metres3'], errors='coerce').groupby(carries['teamName']).sum()/m).round(1)
    res['ATT_FW_Carry_pct']    = (fw_c/(fw_c+bk_c)*100).round(1)
    res['ATT_BK_Carry_pct']    = (bk_c/(fw_c+bk_c)*100).round(1)
    # 旧: res['ATT_Gainline_pct'] = (carries[carries['qualifier3Name']=='Crossed Gain line'].groupby('teamName').size()/carries.groupby('teamName').size()*100).round(1)
    _rgl_n = ruck[ruck['qualifier3']==548].groupby('teamName').size()
    # 旧: _rgl_d = ruck[ruck['qualifier3'].isin([548,549,550,551])].groupby('teamName').size()
    _rgl_d = ruck[ruck['qualifier3'].isin([548,549,550])].groupby('teamName').size()
    res['ATT_Gainline_pct']    = (_rgl_n / _rgl_d * 100).round(1)
    res['ATT_LQB_pct']         = lqb_pct
    res['ATT_Passes_PG']       = (passes_no.groupby('teamName').size()/m).round(0)
    res['ATT_FW_Pass_pct']     = (fw_p/(fw_p+bk_p)*100).round(1)
    res['ATT_BK_Pass_pct']     = (bk_p/(fw_p+bk_p)*100).round(1)

    # ---- Defence ----
    res['DEF_TackleAtt_PG']    = (t_att/m).round(1)
    res['DEF_TackleMiss_PG']   = (missed_t.groupby('teamName').size()/m).round(1)
    res['DEF_TackleSuccess_pct']= t_succ
    _dom_t = tackles[tackles['qualifier4Name']=='Dominant Tackle']
    _t_made = tackles[tackles['ActionResultName']!='Missed']
    res['DEF_DomTackle_pct']   = (_dom_t.groupby('teamName').size() / _t_made.groupby('teamName').size() * 100).round(1)
    res['DEF_OffloadAllow_PG'] = (tackles[tackles['ActionResultName']=='Offload Allowed'].groupby('teamName').size()/m).round(2)
    _passive_t = tackles[tackles['ActionResultName']=='Passive']
    res['DEF_PassiveTackle_PG']= (_passive_t.groupby('teamName').size()/m).round(1)
    aq = df[df['actionName']=='Attacking Qualities']
    _opp_db = aq[aq['ActionTypeName']=='Defender Beaten'].groupby('oppTeam').size()
    res['DEF_OppDB_PG']        = (_opp_db/m).round(1)
    # 旧: res['DEF_GainlineConc_pct'] = (carries[carries['qualifier3Name']=='Crossed Gain line'].groupby('oppTeam').size()/carries.groupby('oppTeam').size()*100).round(1)
    _orgl_n = ruck[ruck['qualifier3']==548].groupby('oppTeam').size()
    # 旧: _orgl_d = ruck[ruck['qualifier3'].isin([548,549,550,551])].groupby('oppTeam').size()
    _orgl_d = ruck[ruck['qualifier3'].isin([548,549,550])].groupby('oppTeam').size()
    res['DEF_GainlineConc_pct']= (_orgl_n / _orgl_d * 100).round(1)
    res['DEF_LQBConc_pct']     = olqb_pct
    res['DEF_TurnoverWon_PG']  = (to_total/m).round(2)

    # ---- Kicking ----
    # Ruck to Kick: Ruck action / Kicks in Play(Goal除く全Kick)
    # Ruck to Kick (OH): Ruck OOA / Kicks from own half (x_coord<50)
    res['KICK_KicksIP_PG']     = (ki/m).round(1)
    res['KICK_KickMetres_PG']  = (km/m).round(0)
    res['KICK_KicksOppHalf_PG']= (kicks_oh.groupby('teamName').size()/m).round(1)
    res['KICK_Kicks4060_PG']   = (kicks_4060.groupby('teamName').size()/m).round(1)
    res['KICK_MetresPerKick']  = (km/ki).round(1)
    res['KICK_RuckToKick']     = (ro/ki).round(3)  # Ruck action / Kicks in Play (qualifier3Name) = Opta完全一致
    # Ruck to Kick (Opp Half): x_coord 51-110 のRuck / KIP
    ra_oh  = ruck_act[ruck_act['x_coord'].between(51,110)].groupby('teamName').size()
    kip_oh = kicks_ip[kicks_ip['x_coord'].between(51,110)].groupby('teamName').size()
    res['KICK_RuckToKickOH']   = (ra_oh/kip_oh).round(3)
    res['KICK_ContestRet_pct'] = (ret_k.groupby('teamName').size()/cont_k.groupby('teamName').size()*100).round(1)
    res['KICK_OppKicksIP_PG']  = (oki/m).round(1)
    res['KICK_OppKickMetres_PG']=(okm/m).round(0)
    res['KICK_OppKicksOH_PG']  = (kicks_oh.groupby('oppTeam').size()/m).round(1)
    res['KICK_OppKicks4060_PG']= (kicks_4060.groupby('oppTeam').size()/m).round(1)
    res['KICK_OppMetresPerKick']=(okm/oki).round(1)
    res['KICK_OppRuckToKick']  = (oro/oki).round(3)
    ora_oh  = ruck_act[ruck_act['x_coord'].between(51,110)].groupby('oppTeam').size()
    okip_oh = kicks_ip[kicks_ip['x_coord'].between(51,110)].groupby('oppTeam').size()
    res['KICK_OppRuckToKickOH']= (ora_oh/okip_oh).round(3)
    res['KICK_OppContestRet_pct']=(ret_k.groupby('oppTeam').size()/cont_k.groupby('oppTeam').size()*100).round(1)

    # ---- Set Piece ----
    res['SP_OwnLineout_pct']   = (lo_w/lo_t*100).round(1)
    res['SP_OppLineout_pct']   = (olo_w/olo_t*100).round(1)
    res['SP_OwnLineoutCnt_PG'] = (lo_t/m).round(1)
    res['SP_OppLineoutCnt_PG'] = (olo_t/m).round(1)
    res['SP_MaulTryScored']    = maul[maul['ActionResultName']=='Try Scored'].groupby('teamName').size()
    res['SP_MaulTryConc']      = maul[maul['ActionResultName']=='Try Scored'].groupby('oppTeam').size()
    # 後方互換のため per game も残す
    res['SP_MaulTryScored_PG'] = (maul[maul['ActionResultName']=='Try Scored'].groupby('teamName').size()/m).round(3)
    res['SP_MaulTryConc_PG']   = (maul[maul['ActionResultName']=='Try Scored'].groupby('oppTeam').size()/m).round(3)
    res['SP_MetrePerMaul']     = (maul.groupby('teamName')['Metres'].sum()/maul.groupby('teamName').size()).round(2)
    res['SP_MetrePerMaul22']   = (maul_kz.groupby('teamName')['Metres'].sum()/maul_kz.groupby('teamName').size()).round(2)
    res['SP_OwnScrum_pct']     = (sc_w/(sc_w+sc_l)*100).round(1)
    res['SP_OppScrum_pct']     = (osc_w/(osc_w+osc_l)*100).round(1)
    res['SP_ScrumPenWon_PG']   = (sc_pw/m).round(2)
    res['SP_ScrumPenCon_PG']   = (sc_pc/m).round(2)
    res['SP_OppMetrePerMaul']  = (maul.groupby('oppTeam')['Metres'].sum()/maul.groupby('oppTeam').size()).round(2)
    res['SP_OppMetrePerMaul22']= (maul_kz.groupby('oppTeam')['Metres'].sum()/maul_kz.groupby('oppTeam').size()).round(2)

    # ---- LB additional ----
    res['LB_BreachConv_pct']    = pd.Series({})  # detail計算後に追加
    res['LB_3Phase_pct']        = pd.Series({})
    res['LB_OppBreachConv_pct'] = pd.Series({})
    res['LB_Opp3Phase_pct']     = pd.Series({})

    # ---- 22m additional ----
    res['TRY_ScorePer22m']       = (pd.Series(pts_s)/a22_t).round(2)
    res['TRY_ScoreConcPer22m']   = (pd.Series(pts_c)/oa22).round(2)
    res['OV_22mConv_pct']        = (atk22_pos / atk22_t * 100).round(1)
    res['OV_Opp22mConv_pct']     = (oatk22_pos / oatk22_t * 100).round(1)

    # ---- Try Source ----
    res['TRY_PointsScored']     = pd.Series(pts_s)
    res['TRY_TriesScored']      = tries_a.groupby('teamName').size()
    res['TRY_FromLineout']      = poss_try[poss_try['ActionTypeName']=='Lineout'].groupby('teamName').size()
    res['TRY_FromScrum']        = poss_try[poss_try['ActionTypeName']=='Scrum'].groupby('teamName').size()
    res['TRY_FromTurnover']     = poss_try[poss_try['ActionTypeName'].isin(TO_S)].groupby('teamName').size()
    res['TRY_FromKickReturn']   = poss_try[poss_try['ActionTypeName']=='Kick Return'].groupby('teamName').size()
    res['TRY_FromQuickTap']     = poss_try[poss_try['ActionTypeName'].isin(['Tap Pen','Free Kick'])].groupby('teamName').size()
    res['TRY_FromRestarts']     = poss_try[poss_try['ActionTypeName'].isin(REST)].groupby('teamName').size()
    res['TRY_PointsConceded']   = pd.Series(pts_c)
    res['TRY_TriesConceded']    = tries_a.groupby('oppTeam').size()
    res['TRY_ConcFromLineout']  = poss_try[poss_try['ActionTypeName']=='Lineout'].groupby('oppTeam').size()
    res['TRY_ConcFromScrum']    = poss_try[poss_try['ActionTypeName']=='Scrum'].groupby('oppTeam').size()
    res['TRY_ConcFromTurnover'] = poss_try[poss_try['ActionTypeName'].isin(TO_S)].groupby('oppTeam').size()
    res['TRY_ConcFromKickRet']  = poss_try[poss_try['ActionTypeName']=='Kick Return'].groupby('oppTeam').size()
    res['TRY_ConcFromQuickTap'] = poss_try[poss_try['ActionTypeName'].isin(['Tap Pen','Free Kick'])].groupby('oppTeam').size()
    res['TRY_ConcFromRestarts'] = poss_try[poss_try['ActionTypeName'].isin(REST)].groupby('oppTeam').size()

    return res.fillna(0), df

# ============================================================
# Try/LB 詳細
# ============================================================
def compute_try_lb_detail(df):
    p2_map = df[df['period']==2].groupby('FXID')['MatchTime'].min().to_dict()
    poss     = df[df['actionName']=='Possession']
    poss_try = poss[poss['ActionResultName']=='Try']
    aq       = df[df['actionName']=='Attacking Qualities']
    lb_all   = aq[aq['ActionTypeName']=='Initial Break']

    def get_area(x):
        if x>78: return 'Opp 22'
        elif x>50: return 'Opp 1/2'
        elif x>22: return 'Own 1/2'
        return 'Own 22'
    def get_phase(n):
        if n==1: return '1 Phase'
        elif n<=3: return '2/3 Phase'
        elif n<=6: return '4-6 Phase'
        return '7+ Phase'
    def get_source(at):
        if at=='Lineout': return 'Lineout'
        elif at=='Scrum': return 'Scrum'
        elif at in TO_S: return 'Turnover'
        elif at=='Kick Return': return 'Kick Return'
        elif at in ['Tap Pen','Free Kick']: return 'Quick Tap'
        elif at in REST: return 'Restarts'
        return 'Other'
    def get_outcome(sr):
        if sr=='Try': return 'Try'
        elif sr in ['Pen Won','Penalty Goal Scored']: return 'Pen Won'
        elif 'Kick' in str(sr): return 'Kick'
        elif sr=='Pen Con': return 'Pen Con'
        elif 'Turnover' in str(sr): return 'Turnover'
        return 'Other'
    def game_min(mt,period,fxid):
        if period==1: return mt/60
        ht2=p2_map.get(fxid,mt)
        return (mt-ht2)/60+40
    def tbin(m):
        m=min(m,80)
        u=int(m//10)*10
        return f'{u}-{u+10}' if u<80 else '70-80'

    records=[]
    for team in sorted(df['teamName'].unique()):
        for _,p in poss_try[poss_try['teamName']==team].iterrows():
            fxid=p['FXID']; seq=p['sequence_id']; px=p['x_coord']
            ss=df[(df['FXID']==fxid)&(df['sequence_id']==seq)]
            ti=ss[ss['actionName']=='Try']
            rn=ss[(ss['actionName']=='Ruck')&(ss['PlayNum']<(ti['PlayNum'].values[0] if len(ti)>0 else 9999))].shape[0]
            gm=game_min(ti.iloc[0]['MatchTime'],ti.iloc[0]['period'],fxid) if len(ti)>0 else 40
            records.append({'team':team,'type':'Try Scored','source':get_source(p['ActionTypeName']),
                           'area':get_area(px),'phase':get_phase(rn+1),'time_bin':tbin(gm),'outcome':None,'y_area':None})
        for _,p in poss_try[poss_try['oppTeam']==team].iterrows():
            fxid=p['FXID']; seq=p['sequence_id']; px=p['x_coord']
            ss=df[(df['FXID']==fxid)&(df['sequence_id']==seq)]
            ti=ss[ss['actionName']=='Try']
            rn=ss[(ss['actionName']=='Ruck')&(ss['PlayNum']<(ti['PlayNum'].values[0] if len(ti)>0 else 9999))].shape[0]
            gm=game_min(ti.iloc[0]['MatchTime'],ti.iloc[0]['period'],fxid) if len(ti)>0 else 40
            records.append({'team':team,'type':'Try Conceded','source':get_source(p['ActionTypeName']),
                           'area':get_area(px),'phase':get_phase(rn+1),'time_bin':tbin(gm),'outcome':None,'y_area':None})
        for _,lb in lb_all[lb_all['teamName']==team].iterrows():
            fxid=lb['FXID']; seq=lb['sequence_id']; lbp=lb['PlayNum']
            lbx=lb['x_coord']; lby=lb['y_coord']
            ss=df[(df['FXID']==fxid)&(df['sequence_id']==seq)]
            pr=ss[ss['actionName']=='Possession']
            px=pr['x_coord'].values[0] if len(pr)>0 else lbx
            src=get_source(pr['ActionTypeName'].values[0]) if len(pr)>0 else 'Other'
            rn=ss[(ss['actionName']=='Ruck')&(ss['PlayNum']<lbp)].shape[0]
            yr='LHS 15m' if lby<=15 else ('Centre Field' if lby<=53 else 'RHS 15m')
            sr=ss[ss['actionName']=='Sequences']
            oc=get_outcome(sr['ActionResultName'].values[0]) if len(sr)>0 else 'Other'
            records.append({'team':team,'type':'LB Scored','source':src,'area':get_area(px),
                           'phase':get_phase(rn+1),'time_bin':None,'outcome':oc,'y_area':yr})
        for _,lb in lb_all[lb_all['oppTeam']==team].iterrows():
            fxid=lb['FXID']; seq=lb['sequence_id']; lbp=lb['PlayNum']
            lbx=lb['x_coord']; lby=lb['y_coord']
            ss=df[(df['FXID']==fxid)&(df['sequence_id']==seq)]
            pr=ss[ss['actionName']=='Possession']
            px=pr['x_coord'].values[0] if len(pr)>0 else lbx
            src=get_source(pr['ActionTypeName'].values[0]) if len(pr)>0 else 'Other'
            rn=ss[(ss['actionName']=='Ruck')&(ss['PlayNum']<lbp)].shape[0]
            yr='LHS 15m' if lby<=15 else ('Centre Field' if lby<=53 else 'RHS 15m')
            sr=ss[ss['actionName']=='Sequences']
            oc=get_outcome(sr['ActionResultName'].values[0]) if len(sr)>0 else 'Other'
            records.append({'team':team,'type':'LB Conceded','source':src,'area':get_area(px),
                           'phase':get_phase(rn+1),'time_bin':None,'outcome':oc,'y_area':yr})
    return pd.DataFrame(records)

# ============================================================
# HTML ビルダー
# ============================================================
def build_html(home, opp, master, detail, max_round, df=None):
    teams = list(master.index); n=len(teams)
    h_col = TEAM_COLORS.get(home,'#F97316')
    o_col = TEAM_COLORS.get(opp, '#DC2626')
    h_sht = TEAM_SHORT.get(home, home[:10])
    o_sht = TEAM_SHORT.get(opp,  opp[:10])
    h_bdg = TEAM_BADGE.get(home,'HM')
    o_bdg = TEAM_BADGE.get(opp, 'OP')
    HL    = [home, opp]

    def lg(col, asc=False):
        vals=[(t,float(master.loc[t,col])) for t in teams if col in master.columns and t in master.index]
        if not vals: return 0,1,1,0,0,[]
        vals.sort(key=lambda x:x[1],reverse=not asc)
        avg=sum(v for _,v in vals)/len(vals) if vals else 0
        hr =next((i+1 for i,(t,_) in enumerate(vals) if t==home), 1)
        or_=next((i+1 for i,(t,_) in enumerate(vals) if t==opp), 1)
        return round(avg,2),hr,or_,vals[-1][1],vals[0][1],vals

    def bw(v,mn,mx): return max(5,round((v-mn)/(mx-mn)*100)) if mx!=mn else 50
    def rc(r): return '#16A34A' if r<=3 else ('#DC2626' if r>=n-2 else '#495057')

    # KPI Dual Card (H/O左右)
    def kpi_dual(label,col,asc=False,dec=1,suf=''):
        hv=float(master.loc[home,col]) if col in master.columns else 0
        ov=float(master.loc[opp,col])  if col in master.columns else 0
        avg,hr,or_,mn,mx,_=lg(col,asc)
        hw=bw(hv,mn,mx); ow=bw(ov,mn,mx); ap=bw(avg,mn,mx)
        hg=(hv>=avg) if not asc else (hv<=avg)
        og=(ov>=avg) if not asc else (ov<=avg)
        hd=hv-avg; od=ov-avg
        hdf=f"+{hd:.{dec}f}" if hd>=0 else f"{hd:.{dec}f}"
        odf=f"+{od:.{dec}f}" if od>=0 else f"{od:.{dec}f}"
        hdc='#16A34A' if hg else '#DC2626'
        odc='#16A34A' if og else '#DC2626'
        af=f"{avg:.{dec}f}{suf}"
        return f'''<div style="background:#fff;border:1px solid #DEE2E6;border-radius:6px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.04)">
          <div style="background:#F8F9FA;padding:5px 12px;border-bottom:1px solid #DEE2E6">
            <span style="font-size:10px;color:#6C757D;text-transform:uppercase;letter-spacing:.06em;font-weight:600">{label}</span>
          </div>
          <div style="display:grid;grid-template-columns:1fr 1px 1fr">
            <div style="padding:10px 12px">
              <div style="display:flex;justify-content:space-between;margin-bottom:3px">
                <span style="font-size:9px;color:{h_col};font-weight:700">{h_sht}</span>
                <span style="font-family:'Oswald',sans-serif;font-size:11px;font-weight:700;color:{rc(hr)}">#{hr}<span style="font-size:9px;font-weight:400;color:#aaa">/{n}</span></span>
              </div>
              <div style="display:flex;align-items:baseline;gap:5px;margin-bottom:6px">
                <span style="font-family:'Oswald',sans-serif;font-size:24px;font-weight:700;color:{h_col};line-height:1">{hv:.{dec}f}{suf}</span>
                <span style="font-size:10px;font-weight:600;color:{hdc}">{hdf}{suf}</span>
              </div>
              <div style="position:relative;height:4px;background:#F1F3F5;border-radius:2px">
                <div style="position:absolute;left:0;top:0;height:100%;width:{hw}%;background:{h_col};border-radius:2px;opacity:.85"></div>
                <div style="position:absolute;top:-2px;left:{ap}%;width:2px;height:8px;background:#9CA3AF;border-radius:1px"></div>
              </div>
            </div>
            <div style="background:#F1F3F5"></div>
            <div style="padding:10px 12px">
              <div style="display:flex;justify-content:space-between;margin-bottom:3px">
                <span style="font-size:9px;color:{o_col};font-weight:700">{o_sht}</span>
                <span style="font-family:'Oswald',sans-serif;font-size:11px;font-weight:700;color:{rc(or_)}">#{or_}<span style="font-size:9px;font-weight:400;color:#aaa">/{n}</span></span>
              </div>
              <div style="display:flex;align-items:baseline;gap:5px;margin-bottom:6px">
                <span style="font-family:'Oswald',sans-serif;font-size:24px;font-weight:700;color:{o_col};line-height:1">{ov:.{dec}f}{suf}</span>
                <span style="font-size:10px;font-weight:600;color:{odc}">{odf}{suf}</span>
              </div>
              <div style="position:relative;height:4px;background:#F1F3F5;border-radius:2px">
                <div style="position:absolute;left:0;top:0;height:100%;width:{ow}%;background:{o_col};border-radius:2px;opacity:.85"></div>
                <div style="position:absolute;top:-2px;left:{ap}%;width:2px;height:8px;background:#9CA3AF;border-radius:1px"></div>
              </div>
            </div>
          </div>
          <div style="padding:3px 12px;background:#F8F9FA;border-top:1px solid #F1F3F5;text-align:center">
            <span style="font-size:9px;color:#aaa">League avg <strong style="color:#6C757D">{af}</strong></span>
          </div>
        </div>'''

    # Ranking Card
    def rank_card(label,col,asc=False,dec=1,suf=''):
        avg,_,__,mn,mx,vals=lg(col,asc)
        af=f"{avg:.{dec}f}{suf}"; rows=""
        for i,(t,v) in enumerate(vals):
            hl=t in HL
            # 旧: tc=TEAM_COLORS.get(t,'#888') if hl else '#9CA3AF'
            # 旧: bc=TEAM_COLORS.get(t,'#888') if hl else '#CBD5E1'
            # 旧: fw='font-weight:700;' if hl else ''
            tc=TEAM_COLORS.get(t,'#888') if hl else '#374151'
            bc=TEAM_COLORS.get(t,'#888') if hl else '#9CA3AF'
            fw='font-weight:700;' if hl else 'font-weight:500;'
            w=bw(v,mn,mx); vf=f"{v:.{dec}f}{suf}"
            sn=TEAM_SHORT.get(t,t[:10])
            if hl and asc is not None:
                d=v-avg; ds=(f"+{d:.{dec}f}" if d>=0 else f"{d:.{dec}f}")+suf
                good=(d>0 and not asc) or (d<0 and asc)
                dc='#16A34A' if good else '#DC2626'
                dbadge=f'<span style="font-size:8px;font-weight:700;color:{dc};flex-shrink:0;margin-left:3px;white-space:nowrap">{ds}</span>'
            else:
                dbadge=''  # asc=None（構成比など色なし）の場合もバッジなし
            # 旧: rows+=f'...(color:#aaa for rank num, #9CA3AF/#CBD5E1 for non-HL team/bar)...'
            rows+=f'<div style="display:flex;align-items:center;gap:5px;{"outline:1px solid "+tc+";border-radius:2px;" if hl else ""}padding:1px 2px"><span style="font-size:9px;color:#6B7280;width:13px;text-align:right;flex-shrink:0">{i+1}</span><span style="font-size:10px;width:72px;flex-shrink:0;color:{tc};{fw};overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{sn}</span><div style="flex:1;height:14px;background:#F1F3F5;border-radius:3px;overflow:hidden"><div style="width:{w}%;height:100%;background:{bc};border-radius:3px;display:flex;align-items:center;padding-left:4px"><span style="font-size:8px;font-weight:600;color:#fff;white-space:nowrap">{vf}</span></div></div>{dbadge}</div>'
            # avg marker >>>
            if i<len(vals)-1:
                v_next=vals[i+1][1]
                if (asc and v<=avg<v_next) or (not asc and v>=avg>v_next):
                    rows+=f'<div style="display:flex;align-items:center;height:12px;border-left:2px solid #CA8A04;background:#FEF9C3;padding:0 6px"><span style="font-size:8px;color:#92400E;font-weight:600">avg {af}</span></div>'
            # avg marker <<<
        # 旧 ヘッダ avg span: <span style="font-size:10px;color:#6C757D">avg {af}</span>  (マーカーに一本化のため削除)
        return f'''<div style="background:#fff;border:1px solid #DEE2E6;border-radius:6px;padding:12px 14px;box-shadow:0 1px 3px rgba(0,0,0,.04)">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
            <span style="font-size:10px;color:#6C757D;text-transform:uppercase;letter-spacing:.06em;font-weight:600">{label}</span>
          </div>
          <div style="display:flex;flex-direction:column;gap:2px">{rows}</div>
        </div>'''

    def kpi_grid(metrics):
        return f'<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(290px,1fr));gap:10px">' + \
               "".join(kpi_dual(l,c,a if a is not None else False,d,s) for l,c,a,d,s in metrics) + '</div>'

    def rank_grid(metrics):
        return f'<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:10px">' + \
               "".join(rank_card(l,c,a,d,s) for l,c,a,d,s in metrics) + '</div>'

    def blk(icon,title,sub,content,mt='0'):
        return f'''<div style="background:#fff;border:1px solid #DEE2E6;border-radius:8px;padding:18px;margin-bottom:14px;margin-top:{mt};box-shadow:0 1px 3px rgba(0,0,0,.04)">
          <div style="display:flex;align-items:center;gap:10px;margin-bottom:14px;padding-bottom:8px;border-bottom:1px solid #F1F3F5">
            <div style="width:26px;height:26px;border-radius:50%;background:#F8F9FA;border:1px solid #DEE2E6;display:flex;align-items:center;justify-content:center;font-size:13px;flex-shrink:0">{icon}</div>
            <div style="font-family:'Oswald',sans-serif;font-size:12px;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:#495057">{title}</div>
            <div style="font-size:10px;color:#aaa;margin-left:auto">{sub}</div>
          </div>
          {content}
        </div>'''

    def sec_hdr(txt,c='#6C757D'):
        return f'<div style="font-family:Oswald,sans-serif;font-size:11px;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:{c};padding-bottom:6px;border-bottom:2px solid #DEE2E6;margin-bottom:14px;margin-top:20px;display:flex;align-items:center;gap:6px"><span style="display:block;width:3px;height:12px;border-radius:2px;background:{c};flex-shrink:0"></span>{txt}</div>'

    # 指標定義
    # 旧 OV（2025-06実装順）:
    # ('Possession %','OV_Possession_pct',False,1,'%'), ('Territory %','OV_Territory_pct',False,1,'%'),
    # ('Ball in Play','OV_BallInPlay_min',False,1,'min'), ('Attack Time','OV_AttackTime_min',False,1,'min'),
    # ('Defence Time','OV_DefenceTime_min',True,1,'min'), ('Points Scored','OV_PointsScored',False,0,''),
    # ('Tries Scored','OV_TriesScored',False,0,''),
    # ('Turnover Rate %','OV_TORate_pct',True,1,'%'), ('Opp Half TO Rate %','OV_OppTORate_pct',True,1,'%'),
    # ('Ruck to Kick','OV_RuckToKick',None,3,''), ('Pass to Kick','OV_PassToKick',None,1,''),
    # ('Kicks in Play / G','OV_KicksInPlay_PG',False,1,''), ('Offload / G','OV_Offload_PG',False,2,''),
    # ('Line Breaks / G','OV_LineBreaks_PG',False,2,''), ('Defender Beaten / G','OV_DefBeaten_PG',False,1,''),
    # ('Points Conceded','OV_PointsConceded',True,0,''), ('Tries Conceded','OV_TriesConceded',True,0,''),
    # ('Tackle Success %','OV_TackleSuccess_pct',False,1,'%'), ('Turnover Won / G','OV_TurnoverWon_PG',False,2,''),
    # ('LB Conceded / G','OV_LBConceded_PG',True,2,''), ('Def Beaten Conc / G','OV_DefBeatenConc_PG',True,1,''),
    # ('Penalties Con / G','OV_PenaltiesCon_PG',True,2,''),
    # 旧: ('Own Lineout %','OV_OwnLineout_pct',False,1,'%'), ('Opp Lineout %','OV_OppLineout_pct',True,1,'%'),
    # 旧: ('Own Scrum %','OV_OwnScrum_pct',False,1,'%'), ('Opp Scrum %','OV_OppScrum_pct',True,1,'%'),
    OV = [
        # Game Flow
        ('Ball in Play',          'OV_BallInPlay_min',      False, 1, 'min'),
        ('Possession %',          'OV_Possession_pct',      False, 1, '%'),
        ('Territory %',           'OV_Territory_pct',       False, 1, '%'),
        # Attack
        ('Points For / G',        'OV_PointsFor_PG',        False, 1, ''),
        ('Tries Scored',          'OV_TriesScored',         False, 0, ''),
        ('Gainline %',            'ATT_Gainline_pct',       False, 1, '%'),
        ('Line Breaks / G',       'OV_LineBreaks_PG',       False, 2, ''),
        ('Kicks in Play / G',     'KICK_KicksIP_PG',        False, 1, ''),
        ('Turnover Conceded / G', 'OV_TurnoverConc_PG',     True,  1, ''),
        ('Turnover Rate %',       'OV_TORate_pct',          True,  1, '%'),
        ('Opp Half TO Rate %',    'OV_OppTORate_pct',       True,  1, '%'),
        # Defence
        ('Points Against / G',    'OV_PointsAgainst_PG',   True,  1, ''),
        ('Tries Conceded',        'OV_TriesConceded',       True,  0, ''),
        ('Tackle Success %',      'OV_TackleSuccess_pct',   False, 1, '%'),
        ('Turnover Won / G',      'OV_TurnoverWon_PG',      False, 2, ''),
        ('LB Conceded / G',       'OV_LBConceded_PG',       True,  2, ''),
        ('Penalties Con / G',     'OV_PenaltiesCon_PG',     True,  2, ''),
    ]
    # 旧 ATT（並び替え前）:
    # ('Carries / G','ATT_Carries_PG',False,1,''), ('Carry Metres / G','ATT_CarryMetres_PG',False,0,'m'),
    # ('Metres / Carry','ATT_MetresPerCarry',False,2,'m'),
    # ('FW Carry %','ATT_FW_Carry_pct',None,1,'%'), ('BK Carry %','ATT_BK_Carry_pct',None,1,'%'),
    # ('Gainline %','ATT_Gainline_pct',False,1,'%'), ('LQB %','ATT_LQB_pct',False,1,'%'),
    # ('Line Breaks / G','OV_LineBreaks_PG',False,2,''),
    # ('Offload Success / G','ATT_OffloadSuccess_PG',False,2,''),
    # ('Passes / G','ATT_Passes_PG',False,0,''),
    # ('FW Pass %','ATT_FW_Pass_pct',None,1,'%'), ('BK Pass %','ATT_BK_Pass_pct',None,1,'%'),
    ATT = [
        ('Carries / G',          'ATT_Carries_PG',         False, 1, ''),
        ('Carry Metres / G',     'ATT_CarryMetres_PG',     False, 0, 'm'),
        ('Metres / Carry',       'ATT_MetresPerCarry',     False, 2, 'm'),
        ('Line Breaks / G',      'OV_LineBreaks_PG',       False, 2, ''),
        ('Defenders Beaten / G', 'OV_DefBeaten_PG',        False, 1, ''),
        ('Post Cont Metres / G', 'ATT_PostContMetres_PG',  False, 1, 'm'),
        ('Gainline %',           'ATT_Gainline_pct',       False, 1, '%'),
        ('LQB %',                'ATT_LQB_pct',            False, 1, '%'),
        ('Offload Success / G',  'ATT_OffloadSuccess_PG',  False, 2, ''),
        ('Passes / G',           'ATT_Passes_PG',          False, 0, ''),
        ('FW Pass %',            'ATT_FW_Pass_pct',        None,  1, '%'),
        ('BK Pass %',            'ATT_BK_Pass_pct',        None,  1, '%'),
        ('FW Carry %',           'ATT_FW_Carry_pct',       None,  1, '%'),
        ('BK Carry %',           'ATT_BK_Carry_pct',       None,  1, '%'),
    ]
    DEF = [
        ('Tackle Attempts / G','DEF_TackleAtt_PG',True,1,''),
        ('Tackle Miss / G','DEF_TackleMiss_PG',True,1,''),
        ('Tackle Success %','DEF_TackleSuccess_pct',False,1,'%'),
        ('Dominant Tackle %','DEF_DomTackle_pct',False,1,'%'),
        ('Offload Allowed / G','DEF_OffloadAllow_PG',True,2,''),
        ('Passive Tackle / G','DEF_PassiveTackle_PG',True,1,''),
        ('Opp Def Beaten / G','DEF_OppDB_PG',True,1,''),
        ('Def Gainline %','DEF_GainlineConc_pct',True,1,'%'),
        ('Def LQB %','DEF_LQBConc_pct',True,1,'%'),
        ('Turnover Won / G','DEF_TurnoverWon_PG',False,2,''),
    ]
    KICK_OWN = [
        ('Kicks in Play / G',  'KICK_KicksIP_PG',     False, 1, ''),
        ('Kick Metres / G',    'KICK_KickMetres_PG',   False, 0, 'm'),
        ('Kicks Opp Half / G', 'KICK_KicksOppHalf_PG', False, 1, ''),
        ('Kicks Own10-Opp10 / G','KICK_Kicks4060_PG',  False, 1, ''),
        ('Metres / Kick',      'KICK_MetresPerKick',   False, 1, 'm'),
        ('Ruck to Kick',       'KICK_RuckToKick',      None,  3, ''),
        ('Ruck to Kick (OH)',  'KICK_RuckToKickOH',    None,  3, ''),
        # 旧: ('Contest Retained %', 'KICK_ContestRet_pct',  False, 1, '%'),
        ('Contest Retained', 'KICK_ContestRet_pct',  False, 1, '%'),
    ]
    KICK_OPP = [
        ('Opp Kicks in Play / G',  'KICK_OppKicksIP_PG',    True, 1, ''),
        ('Opp Kick Metres / G',    'KICK_OppKickMetres_PG',  True, 0, 'm'),
        ('Opp Kicks Opp Half / G', 'KICK_OppKicksOH_PG',    True, 1, ''),
        ('Opp Kicks Own10-Opp10 / G','KICK_OppKicks4060_PG', True, 1, ''),
        ('Opp Metres / Kick',      'KICK_OppMetresPerKick',  True, 1, 'm'),
        ('Opp Ruck to Kick',       'KICK_OppRuckToKick',     None, 3, ''),
        ('Opp Ruck to Kick (OH)',  'KICK_OppRuckToKickOH',   None, 3, ''),
        # 旧: ('Opp Contest Retained %', 'KICK_OppContestRet_pct', True, 1, '%'),
        ('Opp Contest Retained', 'KICK_OppContestRet_pct', True, 1, '%'),
    ]
    KICK = KICK_OWN + KICK_OPP
    SP_LINEOUT = [
        ('Own Lineout %',      'SP_OwnLineout_pct',   False, 1, '%'),
        ('Opp Lineout %',      'SP_OppLineout_pct',   True,  1, '%'),
        ('Own Lineout Cnt / G','SP_OwnLineoutCnt_PG', False, 1, ''),
        ('Opp Lineout Cnt / G','SP_OppLineoutCnt_PG', False, 1, ''),
    ]
    SP_MAUL = [
        ('Maul Try Scored',   'SP_MaulTryScored', False, 0, ''),
        ('Maul Try Conceded', 'SP_MaulTryConc',   True,  0, ''),
        ('Metres / Maul',         'SP_MetrePerMaul',     False, 2, 'm'),
        ('Metres / Maul (22m)',   'SP_MetrePerMaul22',   False, 2, 'm'),
        ('Opp Metres / Maul',     'SP_OppMetrePerMaul',  True,  2, 'm'),
        ('Opp M / Maul (22m)',    'SP_OppMetrePerMaul22',True,  2, 'm'),
    ]
    SP_SCRUM = [
        ('Own Scrum %',       'SP_OwnScrum_pct',   False, 1, '%'),
        ('Opp Scrum %',       'SP_OppScrum_pct',   True,  1, '%'),
        ('Scrum Pen Won / G', 'SP_ScrumPenWon_PG', False, 2, ''),
        ('Scrum Pen Con / G', 'SP_ScrumPenCon_PG', True,  2, ''),
    ]
    SP = SP_LINEOUT + SP_MAUL + SP_SCRUM
    TS_SCORED = [
        ('Points Scored','TRY_PointsScored',False,0,''),
        ('Tries Scored','TRY_TriesScored',False,0,''),
        ('from Lineout','TRY_FromLineout',False,0,''),
        ('from Scrum','TRY_FromScrum',False,0,''),
        ('from Turnover','TRY_FromTurnover',False,0,''),
        ('from Kick Return','TRY_FromKickReturn',False,0,''),
        ('from Quick Tap','TRY_FromQuickTap',False,0,''),
        ('from Restarts','TRY_FromRestarts',False,0,''),
    ]
    TS_CONC = [
        ('Points Conceded','TRY_PointsConceded',True,0,''),
        ('Tries Conceded','TRY_TriesConceded',True,0,''),
        ('Conc from Lineout','TRY_ConcFromLineout',True,0,''),
        ('Conc from Scrum','TRY_ConcFromScrum',True,0,''),
        ('Conc from Turnover','TRY_ConcFromTurnover',True,0,''),
        ('Conc from Kick Return','TRY_ConcFromKickRet',True,0,''),
        ('Conc from Quick Tap','TRY_ConcFromQuickTap',True,0,''),
        ('Conc from Restarts','TRY_ConcFromRestarts',True,0,''),
    ]

    # Try/LB Panel
    def get_detail(team,dtype):
        sub=detail[(detail['team']==team)&(detail['type']==dtype)]
        src=sub['source'].value_counts().to_dict()
        tbs=['0-10','10-20','20-30','30-40','40-50','50-60','60-70','70-80']
        time={b:int(sub['time_bin'].value_counts().get(b,0)) for b in tbs} if 'time_bin' in sub.columns else {}
        areas=['Opp 22','Opp 1/2','Own 1/2','Own 22']
        phases=['1 Phase','2/3 Phase','4-6 Phase','7+ Phase']
        ap=[]
        for a in areas:
            row={'area':a}
            for p in phases: row[p]=int(len(sub[(sub['area']==a)&(sub['phase']==p)]))
            ap.append(row)
        return {'total':len(sub),'source':src,'time':time,'areaphase':ap,
                'outcome':sub['outcome'].value_counts().to_dict() if 'outcome' in sub.columns else {},
                'phase':sub['phase'].value_counts().to_dict() if 'phase' in sub.columns else {},
                'y_area':sub['y_area'].value_counts().to_dict() if 'y_area' in sub.columns else {},
                'src2':sub['source'].value_counts().to_dict()}

    def src_bars(src,total,tc):
        items=sorted(src.items(),key=lambda x:-x[1]); mx=items[0][1] if items else 1; out=""
        for k,v in items:
            w=round(v/mx*100); pct=f"{v/total*100:.1f}%" if total else "0%"
            out+=f'<div style="display:flex;align-items:center;gap:5px;margin-bottom:4px"><span style="font-size:10px;width:80px;flex-shrink:0">{k}</span><div style="flex:1;height:14px;background:#F1F3F5;border-radius:3px;overflow:hidden"><div style="width:{w}%;height:100%;background:{tc};border-radius:3px;display:flex;align-items:center;padding-left:4px"><span style="font-size:9px;font-weight:600;color:#fff">{v}</span></div></div><span style="font-size:9px;color:#6C757D;width:32px;text-align:right;flex-shrink:0">{pct}</span></div>'
        return out

    def time_bars(td,tc):
        bins=['0-10','10-20','20-30','30-40','40-50','50-60','60-70','70-80']
        vals=[td.get(b,0) for b in bins]; mx=max(vals) if vals else 1; out=""
        for b,v in zip(bins,vals):
            h=round(v/mx*40) if mx else 0
            out+=f'<div style="flex:1;display:flex;flex-direction:column;align-items:center;justify-content:flex-end"><div style="font-size:8px;font-weight:600;margin-bottom:1px">{v or ""}</div><div style="width:100%;height:{h}px;background:{tc};opacity:.85;border-radius:2px 2px 0 0;min-height:2px"></div><div style="font-size:7px;color:#aaa;margin-top:2px">{b}</div></div>'
        return f'<div style="display:flex;gap:3px;align-items:flex-end;height:48px">{out}</div>'

    def ap_heatmap(ap,total,tc):
        areas=['Opp 22','Opp 1/2','Own 1/2','Own 22']; phases=['1 Phase','2/3 Phase','4-6 Phase','7+ Phase']
        apm={r['area']:r for r in ap}
        mx=max((apm.get(a,{}).get(p,0) for a in areas for p in phases),default=1)
        rows=""
        for a in areas:
            row=apm.get(a,{}); rt=sum(row.get(p,0) for p in phases); cells=""
            for p in phases:
                v=row.get(p,0)
                if v>0:
                    alpha=0.08+(v/mx)*0.72; ah=format(int(alpha*255),'02x')
                    txt='#fff' if alpha>0.45 else tc
                    cells+=f'<td style="background:{tc}{ah};color:{txt};font-weight:600;padding:4px;text-align:center;font-family:Oswald,sans-serif;font-size:11px;border:1px solid #DEE2E6">{v}</td>'
                else:
                    cells+=f'<td style="color:#ccc;padding:4px;text-align:center;font-size:11px;border:1px solid #DEE2E6">—</td>'
            rows+=f'<tr><td style="font-size:9px;color:#6C757D;padding:4px 6px;border:1px solid #DEE2E6">{a}</td>{cells}<td style="color:#6C757D;font-size:10px;padding:4px;text-align:center;border:1px solid #DEE2E6">{rt}</td></tr>'
        tots=[sum(apm.get(a,{}).get(p,0) for a in areas) for p in phases]
        rows+=f'<tr style="border-top:2px solid #DEE2E6"><td style="font-size:9px;color:#aaa;padding:4px 6px;border:1px solid #DEE2E6">Total</td>{"".join(f"<td style=color:#aaa;font-size:10px;padding:4px;text-align:center;border:1px solid #DEE2E6>{t}</td>" for t in tots)}<td style="font-weight:700;font-size:10px;padding:4px;text-align:center;border:1px solid #DEE2E6">{total}</td></tr>'
        return f'<table style="width:100%;border-collapse:collapse;margin-top:6px"><tr><th style="font-size:8px;color:#aaa;padding:2px 4px"></th><th style="font-size:8px;color:#aaa;padding:2px 4px;text-align:center">1Ph</th><th style="font-size:8px;color:#aaa;padding:2px 4px;text-align:center">2/3Ph</th><th style="font-size:8px;color:#aaa;padding:2px 4px;text-align:center">4-6Ph</th><th style="font-size:8px;color:#aaa;padding:2px 4px;text-align:center">7+Ph</th><th style="font-size:8px;color:#aaa;padding:2px 4px;text-align:center">Tot</th></tr>{rows}</table>'

    def outcome_bars(oc,total,tc,water=False):
        order=['Try','Pen Won','Kick','Pen Con','Turnover','Other']
        # 旧: colors={'Try':'#16A34A','Pen Won':tc,'Kick':'#3B82F6','Pen Con':'#DC2626','Turnover':'#D97706','Other':'#9CA3AF'}
        WATER_C={'Try':'#0369A1','Pen Won':'#0EA5E9','Kick':'#38BDF8','Pen Con':'#7DD3FC','Turnover':'#BAE6FD','Other':'#E0F2FE'}
        colors=WATER_C if water else {'Try':'#16A34A','Pen Won':tc,'Kick':'#3B82F6','Pen Con':'#DC2626','Turnover':'#D97706','Other':'#9CA3AF'}
        vals=[oc.get(k,0) for k in order]; mx=max(vals) if vals else 1; cols=""
        for k,v in zip(order,vals):
            h=round(v/mx*70) if mx else 0; pct=f"{v/total*100:.1f}%" if total else "0%"
            cols+=f'<div style="flex:1;display:flex;flex-direction:column;align-items:center;justify-content:flex-end"><div style="font-size:9px;font-weight:700;margin-bottom:1px">{v}</div><div style="font-size:8px;color:#666;margin-bottom:2px">{pct}</div><div style="width:100%;height:{h}px;background:{colors[k]};border-radius:3px 3px 0 0;min-height:3px"></div><div style="font-size:8px;color:#888;text-align:center;margin-top:3px;line-height:1.3">{k}</div></div>'
        return f'<div style="display:flex;gap:5px;align-items:flex-end;height:100px;margin-bottom:6px">{cols}</div>'

    def conv_bar(oc,total,pc,nc):
        pos=oc.get('Try',0)+oc.get('Pen Won',0)+oc.get('Kick',0); neg=total-pos
        pp=round(pos/total*100,1) if total else 0; np_=round(neg/total*100,1) if total else 0
        return f'''<div style="margin:8px 0">
          <div style="display:flex;justify-content:space-between;margin-bottom:4px;font-size:10px;font-weight:600">
            <span style="color:#6C757D">LB Conversion</span><span style="color:{pc}">Positive {pp}%</span>
          </div>
          <div style="height:20px;background:#F1F3F5;border-radius:4px;overflow:hidden;display:flex">
            <div style="width:{pp}%;background:{pc};display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:700;color:#fff">{pp}%</div>
            <div style="flex:1;background:{nc};opacity:.8;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:700;color:#fff">{np_}%</div>
          </div>
          <div style="display:flex;justify-content:space-between;margin-top:2px;font-size:9px;color:#aaa">
            <span>Try({oc.get('Try',0)}) PenWon({oc.get('Pen Won',0)}) Kick({oc.get('Kick',0)}) = {pos}</span>
            <span>PenCon({oc.get('Pen Con',0)}) TO({oc.get('Turnover',0)}) Other({oc.get('Other',0)}) = {neg}</span>
          </div>
        </div>'''

    def phase_bars(ph,tc):
        order=['1 Phase','2/3 Phase','4-6 Phase','7+ Phase']; vals=[ph.get(p,0) for p in order]; mx=max(vals) if vals else 1; out=""
        for p,v in zip(order,vals):
            h=round(v/mx*48) if mx else 0
            out+=f'<div style="flex:1;display:flex;flex-direction:column;align-items:center;justify-content:flex-end"><div style="font-size:9px;font-weight:600;margin-bottom:1px">{v}</div><div style="width:100%;height:{h}px;background:{tc};opacity:.85;border-radius:2px 2px 0 0;min-height:2px"></div><div style="font-size:8px;color:#aaa;margin-top:2px">{p.replace(" Phase","")}</div></div>'
        return f'<div style="display:flex;gap:4px;height:56px;align-items:flex-end;margin-bottom:10px">{out}</div>'

    def ya_row(ya,tc):
        return "".join(f'<div style="flex:1;background:#F8F9FA;border:1px solid #DEE2E6;border-radius:4px;padding:8px;text-align:center"><div style="font-family:Oswald,sans-serif;font-size:18px;font-weight:600;color:{tc}">{ya.get(l,0)}</div><div style="font-size:9px;color:#6C757D">{l}</div></div>' for l in ['LHS 15m','Centre Field','RHS 15m'])

    def panel_hdr(title,total,rank,avg,tc,suf=''):
        return f'''<div style="margin-bottom:12px;padding-bottom:10px;border-bottom:1px solid #DEE2E6">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:6px">
            <span style="font-family:'Oswald',sans-serif;font-size:12px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:{tc}">{title}</span>
            <span style="font-family:'Oswald',sans-serif;font-size:32px;font-weight:700;color:{tc};line-height:1">{total}</span>
          </div>
          <div style="display:flex;gap:16px">
            <div><div style="font-family:'Oswald',sans-serif;font-size:15px;font-weight:700;color:{rc(rank)}">#{rank}<span style="font-size:10px;font-weight:400;color:#aaa">/{n}</span></div><div style="font-size:9px;color:#aaa;text-transform:uppercase">League Rank</div></div>
            <div style="width:1px;background:#DEE2E6"></div>
            <div><div style="font-family:'Oswald',sans-serif;font-size:15px;font-weight:700;color:#6C757D">{avg}</div><div style="font-size:9px;color:#aaa;text-transform:uppercase">League Avg</div></div>
          </div>
        </div>'''

    def slbl(txt):
        return f'<div style="font-size:9px;color:#6C757D;text-transform:uppercase;font-weight:600;letter-spacing:.05em;margin-top:10px;margin-bottom:4px">{txt}</div>'

    # League avg
    ts_avg  = round(float(master['TRY_TriesScored'].mean()),0)
    tc_avg  = round(float(master['TRY_TriesConceded'].mean()),0)
    lb_avg  = round(float(master['OV_LineBreaks_PG'].mean())*max_round,0)
    lbc_avg = round(float(master['OV_LBConceded_PG'].mean())*max_round,0)

    def ts_rank(t):
        v=[(x,float(master.loc[x,'TRY_TriesScored'])) for x in teams]; v.sort(key=lambda x:-x[1])
        return next(i+1 for i,(x,_) in enumerate(v) if x==t)
    def tc_rank(t):
        v=[(x,float(master.loc[x,'TRY_TriesConceded'])) for x in teams]; v.sort(key=lambda x:x[1])
        return next(i+1 for i,(x,_) in enumerate(v) if x==t)
    def lb_rank(t):
        v=[(x,float(master.loc[x,'OV_LineBreaks_PG'])) for x in teams]; v.sort(key=lambda x:-x[1])
        return next(i+1 for i,(x,_) in enumerate(v) if x==t)
    def lbc_rank(t):
        v=[(x,float(master.loc[x,'OV_LBConceded_PG'])) for x in teams]; v.sort(key=lambda x:x[1])
        return next(i+1 for i,(x,_) in enumerate(v) if x==t)

    def try_panel(data,tc,title,rank,avg):
        total=data['total']
        return f'''<div style="background:#fff;border:1px solid #DEE2E6;border-radius:6px;padding:16px;box-shadow:0 1px 3px rgba(0,0,0,.04)">
          {panel_hdr(title,total,rank,int(avg),tc)}
          {slbl('Source')}{src_bars(data["source"],total,tc)}
          {slbl('Try Time (10-min)')}{time_bars(data.get("time",{}),tc)}
          {slbl('Poss Start Area × Phase (Heatmap)')}{ap_heatmap(data["areaphase"],total,tc)}
        </div>'''

    def lb_panel(data,tc,title,rank,avg,pc,nc,water=False):
        total=data['total']
        return f'''<div style="background:#fff;border:1px solid #DEE2E6;border-radius:6px;padding:16px;box-shadow:0 1px 3px rgba(0,0,0,.04)">
          {panel_hdr(title,total,rank,int(avg),tc,' LBs')}
          {conv_bar(data.get("outcome",{}),total,pc,nc)}
          {slbl('Outcome')}{outcome_bars(data.get("outcome",{}),total,tc,water)}
          {slbl('Phase of Break')}{phase_bars(data.get("phase",{}),tc)}
          {slbl('Breach Area')}<div style="display:flex;gap:6px">{ya_row(data.get("y_area",{}),tc)}</div>
          {slbl('Source')}{src_bars(data.get("src2",{}),total,tc)}
        </div>'''

    # LB Rankings & 22m Rankings
    LB_RANK = [
        ('Line Breaks / G',         'OV_LineBreaks_PG',      False, 2, ''),
        ('Defender Beaten / G',     'OV_DefBeaten_PG',       False, 1, ''),
        ('Breach Conversion %',     'LB_BreachConv_pct',     False, 1, '%'),
        ('LB within 1-3 Phase %',   'LB_3Phase_pct',         False, 1, '%'),
        ('Opp Line Breaks / G',     'OV_LBConceded_PG',      True,  2, ''),
        ('Opp Defender Beaten / G', 'OV_DefBeatenConc_PG',   True,  1, ''),
        ('Opp Breach Conv %',       'LB_OppBreachConv_pct',  True,  1, '%'),
        ('Opp LB 1-3 Phase %',      'Opp_LB_3Phase_pct',     True,  1, '%'),
    ]
    M22_RANK = [
        ('22m Entry / G',           'TRY_22mEntry_PG',       False, 2, ''),
        ('22m Strike Conv %',        'OV_22mConv_pct',        False, 1, '%'),
        ('Carried into 22m / G',    'TRY_22mCarried_PG',     False, 2, ''),
        ('Score / 22m Entry',       'TRY_ScorePer22m',       False, 2, 'pts'),
        ('Opp 22m Entry / G',       'TRY_Opp22mEntry_PG',    True,  2, ''),
        ('Opp 22m Strike Conv %',    'OV_Opp22mConv_pct',     True,  1, '%'),
        ('Opp Carried into 22m/G',  'TRY_Opp22mCarried_PG',  True,  2, ''),
        ('Score Conc / 22m Entry',  'TRY_ScoreConcPer22m',   True,  2, 'pts'),
    ]

    # Try Source ranking card
    # 旧スタイル: tc=#9CA3AF/bc=#CBD5E1/fw='' for non-HL; rank#=color:#aaa; avgマーカーなし; 差分バッジなし; ヘッダにavg span表示
    def try_src_card(label,col,asc=False):
        avg,_,__,mn,mx,vals=lg(col,asc)
        af=f"{avg:.1f}"; rows=""
        for i,(t,v) in enumerate(vals):
            hl=t in HL
            # 旧: tc=TEAM_COLORS.get(t,'#888') if hl else '#9CA3AF'
            # 旧: bc=TEAM_COLORS.get(t,'#888') if hl else '#CBD5E1'
            # 旧: fw='font-weight:700;' if hl else ''
            tc=TEAM_COLORS.get(t,'#888') if hl else '#374151'
            bc=TEAM_COLORS.get(t,'#888') if hl else '#9CA3AF'
            fw='font-weight:700;' if hl else 'font-weight:500;'
            w=bw(v,mn,mx)
            ts_c='TRY_TriesConceded' if 'Conc' in col else 'TRY_TriesScored'
            tot2=float(master.loc[t,ts_c]) if ts_c in master.columns else 1
            pct=round(v/tot2*100,1) if tot2 else 0
            sn=TEAM_SHORT.get(t,t[:10])
            if hl:
                d=v-avg; ds=(f"+{d:.0f}" if d>=0 else f"{d:.0f}")
                good=(d>0 and not asc) or (d<0 and asc)
                dc='#16A34A' if good else '#DC2626'
                dbadge=f'<span style="font-size:8px;font-weight:700;color:{dc};flex-shrink:0;margin-left:3px;white-space:nowrap">{ds}</span>'
            else:
                dbadge=''
            # 旧: rank# color=#aaa → #6B7280
            rows+=f'<div style="display:flex;align-items:center;gap:5px;{"outline:1px solid "+tc+";border-radius:2px;" if hl else ""}padding:1px 2px"><span style="font-size:9px;color:#6B7280;width:13px;text-align:right;flex-shrink:0">{i+1}</span><span style="font-size:10px;width:72px;flex-shrink:0;color:{tc};{fw};overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{sn}</span><div style="flex:1;height:14px;background:#F1F3F5;border-radius:3px;overflow:hidden"><div style="width:{w}%;height:100%;background:{bc};border-radius:3px;display:flex;align-items:center;padding-left:4px"><span style="font-size:8px;font-weight:600;color:#fff;white-space:nowrap">{int(v)} ({pct}%)</span></div></div>{dbadge}</div>'
            # avg marker >>>
            if i<len(vals)-1:
                v_next=vals[i+1][1]
                if (asc and v<=avg<v_next) or (not asc and v>=avg>v_next):
                    rows+=f'<div style="display:flex;align-items:center;height:12px;border-left:2px solid #CA8A04;background:#FEF9C3;padding:0 6px"><span style="font-size:8px;color:#92400E;font-weight:600">avg {af}</span></div>'
            # avg marker <<<
        # 旧: ヘッダに <span style="font-size:10px;color:#6C757D">avg {avg:.1f}</span> → avgマーカーに一本化のため削除
        return f'''<div style="background:#fff;border:1px solid #DEE2E6;border-radius:6px;padding:12px 14px;box-shadow:0 1px 3px rgba(0,0,0,.04)">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
            <span style="font-size:10px;color:#6C757D;text-transform:uppercase;letter-spacing:.06em;font-weight:600">{label}</span>
          </div>
          <div style="display:flex;flex-direction:column;gap:2px">{rows}</div>
        </div>'''

    # ============================================================
    # Win / Loss Analysis
    # ============================================================
    def calc_wl(team, fxid_list):
        """チームの指定試合リストから指標を計算"""
        n = len(fxid_list)
        if n == 0: return {}
        sub  = df[df['teamName'].eq(team) & df['FXID'].isin(fxid_list)].copy()
        opp  = df[df['oppTeam'].eq(team)  & df['FXID'].isin(fxid_list)].copy()
        dall = df[df['FXID'].isin(fxid_list)].copy()
        DEAD = ['Kick in Touch (Full)','Kick in Touch (Bounce)','Error - Out of Play','Error - Dead Ball','Pressure in Touch','In Goal','Try Kick']
        GOAL = ['Penalty Goal','Conversion','Drop Goal']
        QL   = ['0-1 Seconds','1-2 Seconds','2-3 Seconds']
        # 旧: CONT = ['Bomb','Low','Chip','Cross Pitch']
        CONT = ['Bomb','Low','Chip','Cross Pitch','Box']
        SW   = ['Won Outright','Won Penalty','Won Free Kick','Won Try']
        SL   = ['Lost Pen Con','Lost Free Kick','Lost Outright']

        carries = sub[sub['actionName']=='Carry']
        kicks   = sub[sub['actionName']=='Kick']
        kip     = kicks[kicks['qualifier3Name'].isin(['Kick in Play','Kick in Play (Own 22)'])]
        ruck    = sub[sub['actionName']=='Ruck']
        passes  = sub[sub['actionName']=='Pass']
        tackles = sub[sub['actionName']=='Tackle']
        miss_t  = sub[sub['actionName']=='Missed Tackle']
        aq      = sub[sub['actionName']=='Attacking Qualities']
        aq_o    = opp[opp['actionName']=='Attacking Qualities']
        lo_t    = sub[sub['actionName']=='Lineout Throw']
        lo_o    = dall[(dall['actionName']=='Lineout Throw')&(dall['oppTeam'].eq(team))]
        pen_con = sub[sub['actionName']=='Penalty Conceded']
        offload = passes[(passes['ActionTypeName']=='Offload')&(passes['ActionResultName']=='Own Player')]
        cont_k    = kip[kip['ActionTypeName'].isin(CONT)]  # CONT は5種
        # 旧: ret_k = cont_k[cont_k['ActionResultName'].isin(['Own Player - Collected','Pressure Error','Pressure Carried Over'])]
        ret_k     = cont_k[cont_k['ActionResultName'].isin(['Own Player - Collected','Pressure Error','Pressure in Touch','Try Kick'])]
        # 相手版キック4指標用
        opp_kicks  = opp[opp['actionName']=='Kick']
        opp_kip    = opp_kicks[opp_kicks['qualifier3Name'].isin(['Kick in Play','Kick in Play (Own 22)'])]
        opp_cont_k = opp_kip[opp_kip['ActionTypeName'].isin(CONT)]
        opp_ret_k  = opp_cont_k[opp_cont_k['ActionResultName'].isin(['Own Player - Collected','Pressure Error','Pressure in Touch','Try Kick'])]
        opp_ruck   = opp[opp['actionName']=='Ruck']
        coll    = sub[sub['actionName']=='Collection']
        lo_take = sub[sub['actionName']=='Lineout Take']
        scrum_a = dall[dall['actionName']=='Scrum']

        # Possession/BIP
        def get_dur(dfa, action, team_col, team_val):
            d = dfa[(dfa['actionName']==action)&(dfa[team_col].eq(team_val))].copy()
            d['dur'] = d['ps_endstamp'] - d['ps_timestamp']
            return d[d['dur']>0]

        ps   = get_dur(dall,'Possession','teamName',team)
        sc   = get_dur(dall,'Scrum','teamName',team)
        lo   = get_dur(dall,'Lineout Throw','teamName',team)
        gk   = get_dur(dall,'Goal Kick','teamName',team)
        rs   = get_dur(dall,'Restart','teamName',team)
        ps_o = get_dur(dall,'Possession','oppTeam',team)
        sc_o = get_dur(dall,'Scrum','oppTeam',team)
        lo_o2= get_dur(dall,'Lineout Throw','oppTeam',team)

        # 全BIPアクション
        ps_all = dall[dall['actionName']=='Possession'].copy(); ps_all['dur']=(ps_all['ps_endstamp']-ps_all['ps_timestamp']).clip(lower=0)
        sc_all = dall[dall['actionName']=='Scrum'].copy();      sc_all['dur']=(sc_all['ps_endstamp']-sc_all['ps_timestamp']).clip(lower=0)
        lo_all = dall[dall['actionName']=='Lineout Throw'].copy(); lo_all['dur']=(lo_all['ps_endstamp']-lo_all['ps_timestamp']).clip(lower=0)
        gk_all = dall[dall['actionName']=='Goal Kick'].copy();  gk_all['dur']=(gk_all['ps_endstamp']-gk_all['ps_timestamp']).clip(lower=0)
        rs_all = dall[dall['actionName']=='Restart'].copy();    rs_all['dur']=(rs_all['ps_endstamp']-rs_all['ps_timestamp']).clip(lower=0)

        atk_s   = (ps['dur'].sum()+sc['dur'].sum()+lo['dur'].sum())/n/60
        bip_old = (ps_all['dur'].sum()+sc_all['dur'].sum()+lo_all['dur'].sum()+gk_all['dur'].sum()+rs_all['dur'].sum())/n/60  # 旧（GK/RS込み・ロールバック用）
        bip     = (ps_all['dur'].sum()+sc_all['dur'].sum()+lo_all['dur'].sum())/n/60  # BIP_v2（GK・RS 除外）
        def_s   = bip - atk_s
        opp_atk = (ps_o['dur'].sum()+sc_o['dur'].sum()+lo_o2['dur'].sum())/n/60
        poss_pct = atk_s/(atk_s+opp_atk)*100 if (atk_s+opp_atk)>0 else 0

        # TO Won/Conceded
        to_r = sub[(sub['actionName']=='Ruck OOA')&(sub['ActionTypeName']=='Turnover Won')]
        to_j = coll[(coll['ActionTypeName']=='Jackal')&(coll['ActionResultName']=='Success')]
        to_l = lo_take[lo_take['ActionTypeName'].str.contains('Steal',na=False)]
        to_t = tackles[tackles['ActionResultName']=='Turnover Won']
        to_f = dall[(dall['actionName']=='Tackle')&(dall['oppTeam'].eq(team))&(dall['ActionResultName']=='Forced in Touch')]
        to_won = len(to_r)+len(to_j)+len(to_l)+len(to_t)+len(to_f)

        # TO Conceded = Turnover action（全種）の自チーム視点（Optaと一致 ~15/G）
        to_conc = len(dall[(dall['actionName']=='Turnover')&(dall['teamName'].eq(team))])

        t_made = tackles[tackles['ActionResultName']!='Missed']
        t_att  = len(t_made)+len(miss_t)
        # 旧: gl_ok = len(carries[carries['qualifier3Name']=='Crossed Gain line'])
        # 旧: c_tot = len(carries)
        gl_ok  = len(ruck[ruck['qualifier3']==548])
        # 旧: c_tot = len(ruck[ruck['qualifier3'].isin([548,549,550,551])])
        c_tot  = len(ruck[ruck['qualifier3'].isin([548,549,550])])
        km     = kip['Metres'].sum(); ki = len(kip)
        lo_w   = len(lo_t[lo_t['ActionResultName'].str.startswith('Won',na=False)])
        lo_tot = len(lo_t)
        olo_w  = len(lo_o[lo_o['ActionResultName'].str.startswith('Won',na=False)])
        olo_tot= len(lo_o)
        osc_w  = len(scrum_a[(scrum_a['teamName']!=team)&(scrum_a['ActionResultName'].isin(SW))])
        osc_l  = len(scrum_a[(scrum_a['teamName']!=team)&(scrum_a['ActionResultName'].isin(SL))])
        osc_d  = osc_w+osc_l

        ts = len(dall[(dall['actionName']=='Try')&(dall['teamName'].eq(team))])
        tc = len(dall[(dall['actionName']=='Try')&(dall['oppTeam'].eq(team))])

        # Territory 旧: KUBのPossessionのみで x_coord>50 / KUB総Possession時間（ロールバック用）
        ps_terr_old = ps[ps['x_coord']>50]['dur'].sum()
        ps_all2_old = ps['dur'].sum()
        terr_pct_old = round(ps_terr_old/ps_all2_old*100,1) if ps_all2_old else 0

        # Territory v2: 中点座標・BIP_v2 分母（マッチレポート手法B と同一ロジック）
        _bip_acts = ['Possession','Scrum','Lineout Throw']
        _tk = dall[dall['actionName'].isin(_bip_acts) & dall['teamName'].eq(team)].copy()
        _tk['dur'] = (_tk['ps_endstamp'] - _tk['ps_timestamp']).clip(lower=0)
        _tk = _tk[_tk['dur'] > 0].copy()
        _has_xe_k = _tk['x_coord_end'].notna() & _tk['x_coord'].notna()
        _tk['mid'] = _tk['x_coord'].copy()
        _tk.loc[_has_xe_k, 'mid'] = (_tk.loc[_has_xe_k, 'x_coord'] + _tk.loc[_has_xe_k, 'x_coord_end']) / 2
        _tk = _tk[_tk['mid'].notna()].copy()

        _to = dall[dall['actionName'].isin(_bip_acts) & dall['oppTeam'].eq(team)].copy()
        _to['dur'] = (_to['ps_endstamp'] - _to['ps_timestamp']).clip(lower=0)
        _to = _to[_to['dur'] > 0].copy()
        _has_xe_o = _to['x_coord_end'].notna() & _to['x_coord'].notna()
        _to['mid'] = _to['x_coord'].copy()
        _to.loc[_has_xe_o, 'mid'] = (_to.loc[_has_xe_o, 'x_coord'] + _to.loc[_has_xe_o, 'x_coord_end']) / 2
        _to = _to[_to['mid'].notna()].copy()

        _tn_k = _tk[_tk['mid'] > 50]['dur'].sum()
        _td_k = _tk['dur'].sum()
        _tn_o = _to[_to['mid'] > 50]['dur'].sum()
        _td_o = _to['dur'].sum()
        _terr_den_v2 = _td_k + _td_o
        _terr_num_v2 = _tn_k + (_td_o - _tn_o)  # KUB陣取り時間
        terr_pct = round(_terr_num_v2 / _terr_den_v2 * 100, 1) if _terr_den_v2 else 0

        # Ruck to Kick (Ruck action / Kicks in Play)
        ruck_s  = sub[sub['actionName']=='Ruck']
        r2k = round(len(ruck_s)/len(kip),3) if len(kip) else 0

        # Own Lineout / Own Scrum
        sc_own_s = dall[(dall['actionName']=='Scrum')&(dall['teamName'].eq(team))]
        lo_w2   = len(lo_t[lo_t['ActionResultName'].str.startswith('Won',na=False)])
        lo_tot2 = len(lo_t)
        osc_w2  = len(dall[(dall['actionName']=='Scrum')&(dall['teamName']!=team)&(dall['ActionResultName'].isin(SW))])
        osc_l2  = len(dall[(dall['actionName']=='Scrum')&(dall['teamName']!=team)&(dall['ActionResultName'].isin(SL))])
        osc_d2  = osc_w2+osc_l2
        sc_w2   = len(sc_own_s[sc_own_s['ActionResultName'].isin(SW)])
        sc_l2   = len(sc_own_s[sc_own_s['ActionResultName'].isin(SL)])
        sc_d2   = sc_w2+sc_l2

        return {
            'Ball in Play (min)':  round(bip,1),
            'Territory %':         terr_pct,
            'Possession %':        round(poss_pct,1),
            'Attack Time (min)':   round(atk_s,1),
            'Defence Time (min)':  round(def_s,1),
            'Tries Scored':        round(ts/n,2),
            'Tries Conceded':      round(tc/n,2),
            'Gainline %':          round(gl_ok/c_tot*100,1) if c_tot else 0,
            'LQB %':               round(len(ruck[ruck['qualifier4Name'].isin(['0-1 Seconds','1-2 Seconds','2-3 Seconds'])])/len(ruck)*100,1) if len(ruck) else 0,
            'Line Breaks / G':     round(len(aq[aq['ActionTypeName']=='Initial Break'])/n,2),
            'Defender Beaten / G': round(len(aq[aq['ActionTypeName']=='Defender Beaten'])/n,1),
            'Offload / G':         round(len(offload)/n,2),
            'TO Conceded / G':     round(to_conc/n,2),
            'Tackle Success %':    round(len(t_made)/t_att*100,1) if t_att else 0,
            'Turnover Won / G':    round(to_won/n,2),
            'LB Conceded / G':     round(len(aq_o[aq_o['ActionTypeName']=='Initial Break'])/n,2),
            'Penalties Con / G':   round(len(pen_con)/n,2),
            'Kicks in Play / G':      round(len(kip)/n,1),
            'Kick Metres / G':        round(kip['Metres'].sum()/n,0),
            'Ruck to Kick':           r2k,
            # 旧: 'Contest Ret %': round(len(ret_k)/len(cont_k)*100,1) if len(cont_k) else 0,
            'Contest Retained':       round(len(ret_k)/len(cont_k)*100,1) if len(cont_k) else 0,
            'Opp Kicks in Play / G':  round(len(opp_kip)/n,1),
            'Opp Kick Metres / G':    round(opp_kip['Metres'].sum()/n,0),
            'Opp Ruck to Kick':       round(len(opp_ruck)/len(opp_kip),3) if len(opp_kip) else 0,
            'Opp Contest Retained':   round(len(opp_ret_k)/len(opp_cont_k)*100,1) if len(opp_cont_k) else 0,
            'Own Lineout %':       round(lo_w2/lo_tot2*100,1) if lo_tot2 else 0,
            'Own Scrum %':         round(sc_w2/sc_d2*100,1) if sc_d2 else 0,
            'Opp Lineout %':       round(olo_w/olo_tot*100,1) if olo_tot else 0,
            'Opp Scrum %':         round(osc_w/osc_d*100,1) if osc_d else 0,
        }

    # 試合結果判定
    match_res = df.groupby('FXID').first()[['homeTeamName','awayTeamName','hometeamFTscore','awayteamFTscore']]
    home_fxids = df[df['teamName'].eq(home)]['FXID'].unique()
    win_fxids_h = []; loss_fxids_h = []
    for fxid in home_fxids:
        if fxid not in match_res.index: continue
        r = match_res.loc[fxid]
        if r['homeTeamName']==home:
            if r['hometeamFTscore']>r['awayteamFTscore']: win_fxids_h.append(fxid)
            elif r['hometeamFTscore']<r['awayteamFTscore']: loss_fxids_h.append(fxid)
        else:
            if r['awayteamFTscore']>r['hometeamFTscore']: win_fxids_h.append(fxid)
            elif r['awayteamFTscore']<r['hometeamFTscore']: loss_fxids_h.append(fxid)

    wl_home_w = calc_wl(home, win_fxids_h)
    wl_home_l = calc_wl(home, loss_fxids_h)

    WL_CATS = [
        ('⏱ Game Control', ['Ball in Play (min)','Territory %','Possession %','Attack Time (min)','Defence Time (min)']),
        ('⚡ Attack',       ['Tries Scored','Gainline %','LQB %','Line Breaks / G','Defender Beaten / G','Offload / G','TO Conceded / G']),
        ('🛡 Defence',      ['Tries Conceded','Tackle Success %','Turnover Won / G','LB Conceded / G','Penalties Con / G']),
        # 旧: ('👟 Kicking', ['Kicks in Play / G','Kick Metres / G','Ruck to Kick','Contest Ret %']),
        ('👟 Kicking',      ['Kicks in Play / G','Opp Kicks in Play / G',
                             'Kick Metres / G','Opp Kick Metres / G',
                             'Ruck to Kick','Opp Ruck to Kick',
                             'Contest Retained','Opp Contest Retained']),
        ('🏉 Set Piece',    ['Own Lineout %','Own Scrum %','Opp Lineout %','Opp Scrum %']),
    ]
    # 指標ごとに「高い方が良いか」定義
    HIGHER_BETTER = {
        'Ball in Play (min)':True,'Territory %':True,'Possession %':True,
        'Attack Time (min)':True,'Defence Time (min)':False,
        'Tries Scored':True,'Gainline %':True,'LQB %':True,'Line Breaks / G':True,
        'Defender Beaten / G':True,'Offload / G':True,'TO Conceded / G':False,
        'Tries Conceded':False,'Tackle Success %':True,'Turnover Won / G':True,
        'LB Conceded / G':False,'Penalties Con / G':False,
        # 旧: 'Kicks in Play / G':True,'Kick Metres / G':True,'Ruck to Kick':False,'Contest Ret %':True,
        # 旧: 'Kicks in Play / G':True,'Opp Kicks in Play / G':True,
        # 旧: 'Kick Metres / G':True,'Opp Kick Metres / G':True,
        # 旧: 'Ruck to Kick':False,'Opp Ruck to Kick':False,
        # 旧: 'Contest Retained':True,'Opp Contest Retained':True,
        'Kicks in Play / G':True, 'Opp Kicks in Play / G':False,
        'Kick Metres / G':True,   'Opp Kick Metres / G':False,
        'Ruck to Kick':False,     'Opp Ruck to Kick':True,
        'Contest Retained':True,  'Opp Contest Retained':False,
        'Own Lineout %':True,'Own Scrum %':True,
        'Opp Lineout %':False,'Opp Scrum %':False,
    }

    def wl_row(metric, w_val, l_val):
        diff   = w_val - l_val
        hb     = HIGHER_BETTER.get(metric, True)
        w_good = (diff > 0 and hb) or (diff < 0 and not hb)
        w_col  = '#16A34A' if w_good else '#DC2626'
        l_col  = '#DC2626' if w_good else '#16A34A'
        n_col  = '#16A34A' if w_good else '#DC2626'
        diff_s = f"+{diff:.1f}" if diff>0 else f"{diff:.1f}"
        w_bg   = '#F0FDF4' if w_good else '#FEF2F2'
        l_bg   = '#FEF2F2' if w_good else '#F0FDF4'
        return f'''<div style="display:grid;grid-template-columns:1fr 48px 1fr;align-items:center;gap:4px;margin-bottom:4px">
          <div style="background:{w_bg};border-left:3px solid {w_col};border-radius:4px;padding:4px 8px;display:flex;justify-content:space-between;align-items:center">
            <span style="font-size:10px;color:#6C757D;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:90px">{metric}</span>
            <span style="font-family:Oswald,sans-serif;font-size:18px;font-weight:700;color:{w_col};line-height:1;margin-left:6px;flex-shrink:0">{w_val}</span>
          </div>
          <div style="text-align:center;font-size:10px;font-weight:700;color:{n_col};background:{"#16A34A15" if w_good else "#DC262615"};border-radius:3px;padding:2px 2px;white-space:nowrap">{diff_s}</div>
          <div style="background:{l_bg};border-right:3px solid {l_col};border-radius:4px;padding:4px 8px;display:flex;justify-content:space-between;align-items:center">
            <span style="font-family:Oswald,sans-serif;font-size:18px;font-weight:700;color:{l_col};line-height:1;margin-right:6px;flex-shrink:0">{l_val}</span>
            <span style="font-size:10px;color:#6C757D;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:90px;text-align:right">{metric}</span>
          </div>
        </div>'''

    # スカウト対象チームのWin/Loss計算
    opp_fxids = df[df['teamName'].eq(opp)]['FXID'].unique()
    win_fxids_o = []; loss_fxids_o = []
    for fxid in opp_fxids:
        if fxid not in match_res.index: continue
        r = match_res.loc[fxid]
        if r['homeTeamName']==opp:
            if r['hometeamFTscore']>r['awayteamFTscore']: win_fxids_o.append(fxid)
            elif r['hometeamFTscore']<r['awayteamFTscore']: loss_fxids_o.append(fxid)
        else:
            if r['awayteamFTscore']>r['hometeamFTscore']: win_fxids_o.append(fxid)
            elif r['awayteamFTscore']<r['hometeamFTscore']: loss_fxids_o.append(fxid)
    wl_opp_w = calc_wl(opp, win_fxids_o)
    wl_opp_l = calc_wl(opp, loss_fxids_o)

    def make_wl_panel(team_name, team_col, team_badge, team_sht, w_stats, l_stats, win_n, loss_n):
        rows = f'''<div style="background:#fff;border:1px solid #DEE2E6;border-radius:8px;padding:20px;box-shadow:0 1px 3px rgba(0,0,0,.04)">
          <div style="display:flex;align-items:center;gap:10px;margin-bottom:14px;padding-bottom:10px;border-bottom:1px solid #DEE2E6">
            <div style="width:32px;height:32px;border-radius:50%;background:{team_col};display:flex;align-items:center;justify-content:center;font-family:Oswald,sans-serif;font-size:10px;font-weight:700;color:#fff">{team_badge}</div>
            <div style="font-family:Oswald,sans-serif;font-size:13px;font-weight:600;letter-spacing:.06em;color:{team_col}">{team_sht} — WIN vs LOSS</div>
            <div style="margin-left:auto;display:flex;gap:10px;align-items:center">
              <div style="text-align:center"><div style="font-family:Oswald,sans-serif;font-size:18px;font-weight:700;color:#16A34A">{win_n}W</div><div style="font-size:9px;color:#aaa">Wins</div></div>
              <div style="text-align:center"><div style="font-family:Oswald,sans-serif;font-size:18px;font-weight:700;color:#DC2626">{loss_n}L</div><div style="font-size:9px;color:#aaa">Losses</div></div>
            </div>
          </div>
          <div style="display:grid;grid-template-columns:1fr 48px 1fr;gap:4px;padding:4px 0;margin-bottom:6px;border-bottom:2px solid #DEE2E6">
            <div style="text-align:right;font-size:10px;font-weight:700;color:#16A34A">✦ WIN avg</div>
            <div style="text-align:center;font-size:9px;color:#aaa">Δ</div>
            <div style="font-size:10px;font-weight:700;color:#DC2626">✦ LOSS avg</div>
          </div>'''
        for cat_name, metrics in WL_CATS:
            rows += f'<div style="font-family:Oswald,sans-serif;font-size:10px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:#6C757D;padding:8px 0 3px;border-top:1px solid #F1F3F5;margin-top:6px">{cat_name}</div>'
            for m in metrics:
                rows += wl_row(m, w_stats.get(m,0), l_stats.get(m,0))
        rows += '</div>'
        return rows

    winloss_html = f'''<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
      {make_wl_panel(home, h_col, TEAM_BADGE.get(home,"HM"), h_sht, wl_home_w, wl_home_l, len(win_fxids_h), len(loss_fxids_h))}
      {make_wl_panel(opp,  o_col, TEAM_BADGE.get(opp, "OP"),  o_sht, wl_opp_w,  wl_opp_l,  len(win_fxids_o), len(loss_fxids_o))}
    </div>'''

    # ============================================================
    # AI スカウト: データ駆動で強み5点・懸念点5点を自動生成
    # ============================================================
    def ai_scout(team):
        def gv(col): return float(master.loc[team,col]) if col in master.columns else 0
        def gr(col, asc=False):
            _,hr,or_,_,_,_ = lg(col,asc)
            return hr if team==home else or_

        tc = TEAM_COLORS.get(team,'#888')
        sn = TEAM_SHORT.get(team, team)

        # 指標リスト（順位・値・強みテキスト・懸念テキスト）
        indicators = [
            ('ATT_Gainline_pct', False,
             lambda r,v: f'<strong>ゲインライン（#{r} {v:.1f}%）</strong>：キャリーの成功率が{"リーグ最上位クラス" if r<=2 else "リーグ上位"}。相手ディフェンスを継続的に押し込む力がある。',
             lambda r,v: f'<strong>ゲインライン（#{r} {v:.1f}%）</strong>：ゲインライン成功率が{"リーグ最下位クラス" if r>=11 else "リーグ下位"}。キャリーで前進できず攻撃が停滞しやすい。'),
            ('SP_OwnLineout_pct', False,
             lambda r,v: f'<strong>ラインアウト（#{r} {v:.1f}%）</strong>：自チームラインアウトが{"リーグトップ" if r<=2 else "安定"}しており、セットピース起点の攻撃が有効に機能する。',
             lambda r,v: f'<strong>ラインアウト（#{r} {v:.1f}%）</strong>：ラインアウト成功率が{"リーグ最下位" if r>=11 else "低く"}、セットピースからの攻撃起点を失いやすい。'),
            ('SP_OwnScrum_pct', False,
             lambda r,v: f'<strong>スクラム成功率（#{r} {v:.1f}%）</strong>：スクラムの安定性が{"リーグ最高水準" if r<=2 else "高く"}、FWの優位を活かした攻撃ができる。',
             lambda r,v: f'<strong>スクラム成功率（#{r} {v:.1f}%）</strong>：スクラム成功率が{"リーグ最低" if r>=11 else "低く"}、相手にペナルティ機会を多く与えてしまう。'),
            ('DEF_TurnoverWon_PG', False,
             lambda r,v: f'<strong>ターンオーバー獲得（#{r} {v:.2f}/試合）</strong>：ブレイクダウンでのボール奪取がリーグ{"最上位" if r<=2 else "上位"}。カウンターアタックの起点として機能する。',
             lambda r,v: f'<strong>ターンオーバー獲得（#{r} {v:.2f}/試合）</strong>：ボール奪取力がリーグ{"最下位" if r>=11 else "下位"}。相手の継続アタックを止める力に課題がある。'),
            ('BREACH_LineBreaks_PG', False,
             lambda r,v: f'<strong>ラインブレイク（#{r} {v:.2f}/試合）</strong>：突破力がリーグ{"最高" if r<=2 else "上位"}。ディフェンスラインを崩す能力が得点機会を創出する。',
             lambda r,v: f'<strong>ラインブレイク（#{r} {v:.2f}/試合）</strong>：突破力がリーグ{"最低" if r>=11 else "下位"}。攻撃がブロックされやすく得点機会の創出に課題がある。'),
            ('TRY_TriesScored', False,
             lambda r,v: f'<strong>得点力（#{r} {v:.0f}本）</strong>：シーズントライ数がリーグ{"最多" if r<=2 else "上位"}。フィニッシュの精度と攻撃の多彩さを示している。',
             lambda r,v: f'<strong>失点（#{r} {v:.0f}本）</strong>：トライ獲得数がリーグ{"最少" if r>=11 else "下位"}。フィニッシュの精度と攻撃の多彩さに課題がある。'),
            ('TRY_TriesConceded', True,
             lambda r,v: f'<strong>守備堅固さ（#{r} {v:.0f}本被献上）</strong>：被トライ数がリーグ{"最少" if r<=2 else "上位"}。ディフェンスシステムの安定性が高い。',
             lambda r,v: f'<strong>失点の多さ（#{r} {v:.0f}本被献上）</strong>：被トライ数がリーグ{"最多" if r>=11 else "多く"}。ディフェンス全体の見直しが必要。'),
            ('OV_TackleSuccess_pct', False,
             lambda r,v: f'<strong>タックル成功率（#{r} {v:.1f}%）</strong>：ディフェンスの基盤となるタックルがリーグ{"最高水準" if r<=2 else "高水準"}。個人・組織守備の安定性が高い。',
             lambda r,v: f'<strong>タックル成功率（#{r} {v:.1f}%）</strong>：タックル成功率がリーグ{"最低" if r>=11 else "下位"}。ミスタックルが失点に直結するリスクが高い。'),
            ('KICK_MetresPerKick', False,
             lambda r,v: f'<strong>キックメートル（#{r} {v:.1f}m/kick）</strong>：1キックあたりの飛距離がリーグ{"最長" if r<=2 else "上位"}。キックゲームで陣地を押し上げる能力が高い。',
             lambda r,v: f'<strong>キックメートル（#{r} {v:.1f}m/kick）</strong>：キック距離がリーグ{"最短" if r>=11 else "下位"}。陣地の押し上げ効率が低くゲームフローに影響する。'),
            ('KICK_ContestRet_pct', False,
             lambda r,v: f'<strong>コンテストキックリテイン（#{r} {v:.1f}%）</strong>：ハイボール再獲得率がリーグ{"最高" if r<=2 else "上位"}。キックゲームでの陣地回復・プレッシャーが有効。',
             lambda r,v: f'<strong>コンテストキックリテイン（#{r} {v:.1f}%）</strong>：ハイボール再獲得率がリーグ{"最低" if r>=11 else "下位"}。キックゲームでの陣地回復に課題がある。'),
            ('TRY_22mEntry_PG', False,
             lambda r,v: f'<strong>22mエントリー（#{r} {v:.2f}/試合）</strong>：相手22mへの侵入頻度がリーグ{"最多" if r<=2 else "上位"}。継続的に得点機会を作り出せる攻撃力がある。',
             lambda r,v: f'<strong>22mエントリー（#{r} {v:.2f}/試合）</strong>：22mエントリー数がリーグ{"最少" if r>=11 else "下位"}。相手ゴール前まで攻め込む力に課題がある。'),
            ('TRY_22mCarried_PG', False,
             lambda r,v: f'<strong>22mキャリーイン（#{r} {v:.2f}/試合）</strong>：キャリーで22mへ侵入する回数がリーグ{"最多" if r<=2 else "上位"}。アタックのドライブ力がある。',
             lambda r,v: f'<strong>22mキャリーイン（#{r} {v:.2f}/試合）</strong>：キャリーでの22m侵入がリーグ{"最少" if r>=11 else "少なく"}、ゴール前まで押し込む力に課題がある。'),
            ('SP_ScrumPenCon_PG', True,
             lambda r,v: f'<strong>スクラムペナルティ抑制（#{r} {v:.2f}/試合）</strong>：スクラムペナルティ被献上がリーグ{"最少" if r<=2 else "少なく"}、規律の高さを示している。',
             lambda r,v: f'<strong>スクラムペナルティ被献上（#{r} {v:.2f}/試合）</strong>：スクラムでのペナルティがリーグ{"最多" if r>=11 else "多く"}、相手にPG機会を与え続ける。'),
            ('OV_PenaltiesCon_PG', True,
             lambda r,v: f'<strong>ペナルティ規律（#{r} {v:.2f}/試合）</strong>：ペナルティ被献上数がリーグ{"最少" if r<=2 else "少なく"}、高い規律でゲームを管理できている。',
             lambda r,v: f'<strong>ペナルティ被献上（#{r} {v:.2f}/試合）</strong>：ペナルティ数がリーグ{"最多" if r>=11 else "多く"}、相手にフィールドポジションを渡しやすい。'),
            ('ATT_LQB_pct', False,
             lambda r,v: f'<strong>LQB（#{r} {v:.1f}%）</strong>：3秒以内のクイックボール率がリーグ{"最高" if r<=2 else "上位"}。速いテンポのアタックで相手を揺さぶれる。',
             lambda r,v: f'<strong>LQB（#{r} {v:.1f}%）</strong>：クイックボール率がリーグ{"最低" if r>=11 else "低く"}、ラック後のテンポが遅く攻撃が停滞しやすい。'),
            ('OV_LBConceded_PG', True,
             lambda r,v: f'<strong>LB被献上抑制（#{r} {v:.2f}/試合）</strong>：ラインブレイク被献上数がリーグ{"最少" if r<=2 else "少なく"}、ディフェンスラインの堅牢さを示す。',
             lambda r,v: f'<strong>LB被献上（#{r} {v:.2f}/試合）</strong>：ラインブレイクを許す頻度がリーグ{"最多" if r>=11 else "多く"}、ディフェンスの改善が必要。'),
        ]

        strengths = []
        concerns  = []
        for col, asc, pos_fn, neg_fn in indicators:
            r = gr(col, asc)
            v = gv(col)
            if r <= 4:
                strengths.append((r, pos_fn(r,v)))
            if r >= 8:
                concerns.append((r, neg_fn(r,v)))

        # 強み：順位の良い順に5つ
        pos_pts = [txt for _,txt in sorted(strengths, key=lambda x:x[0])[:5]]
        # 懸念点：順位の悪い順に5つ
        neg_pts = [txt for _,txt in sorted(concerns, key=lambda x:-x[0])[:5]]

        # 5点に満たない場合はメッセージを追加
        while len(pos_pts) < 5:
            pos_pts.append('<strong>バランスの取れた指標</strong>：突出した弱点がなく、複数のカテゴリで安定したパフォーマンスを維持している。')
        while len(neg_pts) < 5:
            neg_pts.append('<strong>継続的な改善余地</strong>：現状のパフォーマンスをさらに高めるための継続的な取り組みが必要な指標がある。')

        def pts_html(pts, icon, icon_bg, icon_c):
            return "".join(
                f'''<div style="display:flex;gap:10px;margin-bottom:12px">
                  <div style="width:22px;height:22px;border-radius:50%;background:{icon_bg};display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;color:{icon_c};flex-shrink:0;margin-top:1px">{icon}</div>
                  <div style="font-size:12px;line-height:1.6;color:#212529">{p}</div>
                </div>'''
                for p in pts
            )

        return f'''<div style="background:#fff;border:1px solid #DEE2E6;border-radius:8px;padding:20px;box-shadow:0 1px 3px rgba(0,0,0,.04)">
          <div style="display:flex;align-items:center;gap:10px;margin-bottom:16px;padding-bottom:10px;border-bottom:1px solid #DEE2E6">
            <div style="width:34px;height:34px;border-radius:50%;background:{tc};display:flex;align-items:center;justify-content:center;font-family:Oswald,sans-serif;font-size:11px;font-weight:700;color:#fff">{TEAM_BADGE.get(team,"TM")}</div>
            <div style="font-family:Oswald,sans-serif;font-size:14px;font-weight:600;letter-spacing:.06em;color:{tc}">{sn} — SCOUT ANALYSIS</div>
          </div>
          <div style="font-size:10px;color:#16A34A;text-transform:uppercase;letter-spacing:.08em;margin-bottom:10px;font-weight:600">✦ 強み / Strengths (Top 5)</div>
          {pts_html(pos_pts,"+","rgba(22,163,74,.12)","#16A34A")}
          <div style="font-size:10px;color:#DC2626;text-transform:uppercase;letter-spacing:.08em;margin-bottom:10px;margin-top:18px;font-weight:600">✦ 懸念点 / Concerns (Top 5)</div>
          {pts_html(neg_pts,"−","rgba(220,38,38,.12)","#DC2626")}
        </div>'''

    # 凡例
    legend='<div style="display:flex;flex-wrap:wrap;gap:10px;margin-bottom:16px;padding:8px 14px;background:#fff;border:1px solid #DEE2E6;border-radius:6px;font-size:11px;">'
    for t in teams:
        hl=t in HL; c=TEAM_COLORS.get(t,'#888') if hl else '#CBD5E1'; fw='font-weight:600;' if hl else ''
        legend+=f'<div style="display:flex;align-items:center;gap:4px"><div style="width:9px;height:9px;border-radius:50%;background:{c};flex-shrink:0"></div><span style="color:{c};{fw}">{TEAM_SHORT.get(t,t)}</span></div>'
    legend+='</div>'

    # Try/LB detail data
    h_ts=get_detail(home,'Try Scored'); h_tc=get_detail(home,'Try Conceded')
    h_ls=get_detail(home,'LB Scored');  h_lc=get_detail(home,'LB Conceded')
    o_ts=get_detail(opp,'Try Scored');  o_tc=get_detail(opp,'Try Conceded')
    o_ls=get_detail(opp,'LB Scored');   o_lc=get_detail(opp,'LB Conceded')

    two = 'display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:16px'

    # LB Rankings & 22m Rankings
    LB_RANK = [
        ('Line Breaks / G',         'OV_LineBreaks_PG',      False, 2, ''),
        ('Defender Beaten / G',     'OV_DefBeaten_PG',       False, 1, ''),
        ('Breach Conversion %',     'LB_BreachConv_pct',     False, 1, '%'),
        ('LB within 1-3 Phase %',   'LB_3Phase_pct',         False, 1, '%'),
        ('Opp Line Breaks / G',     'OV_LBConceded_PG',      True,  2, ''),
        ('Opp Defender Beaten / G', 'OV_DefBeatenConc_PG',   True,  1, ''),
        ('Opp Breach Conv %',       'LB_OppBreachConv_pct',  True,  1, '%'),
        ('Opp LB 1-3 Phase %',      'Opp_LB_3Phase_pct',     True,  1, '%'),
    ]
    M22_RANK = [
        ('22m Entry / G',           'TRY_22mEntry_PG',       False, 2, ''),
        ('22m Strike Conv %',        'OV_22mConv_pct',        False, 1, '%'),
        ('Carried into 22m / G',    'TRY_22mCarried_PG',     False, 2, ''),
        ('Score / 22m Entry',       'TRY_ScorePer22m',       False, 2, 'pts'),
        ('Opp 22m Entry / G',       'TRY_Opp22mEntry_PG',    True,  2, ''),
        ('Opp 22m Strike Conv %',    'OV_Opp22mConv_pct',     True,  1, '%'),
        ('Opp Carried into 22m/G',  'TRY_Opp22mCarried_PG',  True,  2, ''),
        ('Score Conc / 22m Entry',  'TRY_ScoreConcPer22m',   True,  2, 'pts'),
    ]

    # Try Source section
    # 旧: 2カラム左右分割 (Scored|Conceded 縦スタック、TS_SCORED[2:]/TS_CONC[2:] のみ、try_src_card 旧スタイル)
    # 旧: ts_src_html = f'''
    #   <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px">
    #     <div>
    #       <div style="...color:#16A34A...">✦ Tries Scored by Source</div>
    #       <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:8px">
    #         {join(try_src_card for TS_SCORED[2:])}
    #       </div>
    #     </div>
    #     <div>
    #       <div style="...color:#DC2626...">✦ Tries Conceded by Source</div>
    #       <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:8px">
    #         {join(try_src_card for TS_CONC[2:])}
    #       </div>
    #     </div>
    #   </div>'''
    ts_src_html = f'''
      <div>
        <div style="font-family:'Oswald',sans-serif;font-size:11px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:#16A34A;margin-bottom:10px;padding-bottom:5px;border-bottom:2px solid #16A34A22">✦ Tries Scored by Source</div>
        <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px">
          {"".join(rank_card(l,c,a if a is not None else False,d,s) for l,c,a,d,s in TS_SCORED[:2])}{"".join(try_src_card(l,c,a if a is not None else False) for l,c,a,_,__ in TS_SCORED[2:])}
        </div>
      </div>
      <div style="height:16px"></div>
      <div>
        <div style="font-family:'Oswald',sans-serif;font-size:11px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:#DC2626;margin-bottom:10px;padding-bottom:5px;border-bottom:2px solid #DC262622">✦ Tries Conceded by Source</div>
        <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px">
          {"".join(rank_card(l,c,a if a is not None else False,d,s) for l,c,a,d,s in TS_CONC[:2])}{"".join(try_src_card(l,c,a if a is not None else False) for l,c,a,_,__ in TS_CONC[2:])}
        </div>
      </div>'''

    # Print CSS (A4横)
    PRINT_CSS = """
@media print {
  @page { size: A4 landscape; margin: 10mm; }
  .top-bar { position: relative !important; box-shadow: none !important; }
  .nav-tabs { display: none !important; }
  .section { display: block !important; page-break-after: always; }
  .sub-tabs { display: none !important; }
  .sub-section { display: block !important; }
  body { background: #fff !important; font-size: 11px; }
  .blk { box-shadow: none !important; border: 1px solid #ccc !important; }
}"""

    CSS = f"""<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Oswald:wght@400;500;600;700&display=swap');
{PRINT_CSS}
*{{box-sizing:border-box;margin:0;padding:0;}}
body{{background:#F8F9FA;color:#212529;font-family:'Inter',sans-serif;font-size:13px;line-height:1.4;}}
.top-bar{{background:#fff;border-bottom:2px solid #DEE2E6;position:sticky;top:0;z-index:100;box-shadow:0 1px 4px rgba(0,0,0,.07);}}
.top-bar-inner{{max-width:1500px;margin:0 auto;display:flex;align-items:stretch;justify-content:space-between;padding:0 24px;}}
.nav-tabs{{display:flex;}}
.nav-btn{{padding:0 11px;height:100%;font-family:'Oswald',sans-serif;font-size:10px;font-weight:500;letter-spacing:.07em;text-transform:uppercase;color:#6C757D;background:none;border:none;border-bottom:3px solid transparent;cursor:pointer;transition:all .2s;white-space:nowrap;}}
.nav-btn:hover{{color:#212529;}}.nav-btn.active{{border-bottom-color:currentColor;}}
.main{{max-width:1500px;margin:0 auto;padding:20px 24px;}}
.section{{display:none;}}.section.active{{display:block;}}
.sub-tabs{{display:flex;gap:4px;margin-bottom:16px;flex-wrap:wrap;}}
.sub-btn{{padding:5px 12px;border-radius:20px;border:1px solid #DEE2E6;background:#fff;color:#6C757D;font-size:10px;font-weight:600;font-family:'Oswald',sans-serif;letter-spacing:.06em;text-transform:uppercase;cursor:pointer;transition:all .2s;}}
.sub-btn:hover{{border-color:#aaa;color:#212529;}}
.sub-btn.active{{background:#212529;color:#fff;border-color:#212529;}}
.sub-section{{display:none;}}.sub-section.active{{display:block;}}
.print-btn{{position:fixed;bottom:20px;right:20px;padding:10px 20px;background:{h_col};color:#fff;border:none;border-radius:6px;font-family:'Oswald',sans-serif;font-size:12px;font-weight:600;letter-spacing:.06em;cursor:pointer;box-shadow:0 2px 8px rgba(0,0,0,.2);z-index:200;}}
@media(max-width:900px){{.main{{padding:12px;}}.top-bar-inner{{flex-direction:column;height:auto;}}}}
</style>"""

    SHOW_JS = """<script>
function showSection(id,btn){
  document.querySelectorAll('.section').forEach(s=>s.classList.remove('active'));
  document.querySelectorAll('.nav-btn').forEach(b=>b.classList.remove('active'));
  document.getElementById(id).classList.add('active');btn.classList.add('active');
  const s0=document.getElementById(id).querySelector('.sub-section');
  const b0=document.getElementById(id).querySelector('.sub-btn');
  if(s0){document.getElementById(id).querySelectorAll('.sub-section').forEach(s=>s.classList.remove('active'));
         document.getElementById(id).querySelectorAll('.sub-btn').forEach(b=>b.classList.remove('active'));
         s0.classList.add('active');if(b0)b0.classList.add('active');}
}
function showSub(sid,subId,btn){
  const sec=document.getElementById(sid);
  sec.querySelectorAll('.sub-section').forEach(s=>s.classList.remove('active'));
  sec.querySelectorAll('.sub-btn').forEach(b=>b.classList.remove('active'));
  document.getElementById(subId).classList.add('active');btn.classList.add('active');
}
</script>"""

    # ===== セクション HTML =====

    # Overview - 4列縦構成（Game Flow / Attack / Defence / Set Piece）
    # 旧 OV_CATS（2025-06実装順）:
    # { 'label': 'Game Flow', 'color': '#0891B2', 'icon': '⏱',
    #   'metrics': [('Ball in Play','OV_BallInPlay_min',False,1,'min'),
    #               ('Possession %','OV_Possession_pct',False,1,'%'),
    #               ('Territory %','OV_Territory_pct',False,1,'%')] },
    # { 'label': 'Attack', 'color': h_col, 'icon': '⚡',
    #   'metrics': [('Tries Scored','OV_TriesScored',False,0,''),
    #               ('Turnover Rate %','OV_TORate_pct',True,1,'%'),
    #               ('Opp Half TO Rate %','OV_OppTORate_pct',True,1,'%'),
    #               ('Gainline %','ATT_Gainline_pct',False,1,'%'),
    #               ('Line Breaks / G','OV_LineBreaks_PG',False,2,''),
    #               ('Kicks in Play / G','KICK_KicksIP_PG',False,1,''),
    #               ('Turnover Conceded / G','OV_TurnoverConc_PG',True,2,'')] },
    # { 'label': 'Defence', 'color': '#2563EB', 'icon': '🛡',
    #   'metrics': [('Tries Conceded','OV_TriesConceded',True,0,''),
    #               ('Tackle Success %','OV_TackleSuccess_pct',False,1,'%'),
    #               ('Turnover Won / G','OV_TurnoverWon_PG',False,2,''),
    #               ('Line Break Conceded / G','OV_LBConceded_PG',True,2,''),
    #               ('Penalties Con / G','OV_PenaltiesCon_PG',True,2,'')] },
    # 旧: Set Piece カテゴリ（OV ランキングから削除、Set Piece セクションに残存）
    # { 'label': 'Set Piece', 'color': '#7C3AED', 'icon': '🏉',
    #   'metrics': [('Own Lineout %','OV_OwnLineout_pct',False,1,'%'),
    #               ('Opp Lineout %','OV_OppLineout_pct',True,1,'%'),
    #               ('Own Scrum %','OV_OwnScrum_pct',False,1,'%'),
    #               ('Opp Scrum %','OV_OppScrum_pct',True,1,'')] },
    OV_CATS = [
        {
            'label': 'Game Flow', 'color': '#0891B2', 'icon': '⏱',
            'metrics': [
                ('Ball in Play',   'OV_BallInPlay_min',  False, 1, 'min'),
                ('Possession %',   'OV_Possession_pct',  False, 1, '%'),
                ('Territory %',    'OV_Territory_pct',   False, 1, '%'),
            ]
        },
        {
            'label': 'Attack', 'color': h_col, 'icon': '⚡',
            'metrics': [
                ('Points For / G',        'OV_PointsFor_PG',    False, 1, ''),
                ('Tries Scored',          'OV_TriesScored',     False, 0, ''),
                ('Gainline %',            'ATT_Gainline_pct',   False, 1, '%'),
                ('Line Breaks / G',       'OV_LineBreaks_PG',   False, 2, ''),
                ('Kicks in Play / G',     'KICK_KicksIP_PG',    False, 1, ''),
                ('Turnover Conceded / G', 'OV_TurnoverConc_PG', True,  1, ''),
                ('Turnover Rate %',       'OV_TORate_pct',      True,  1, '%'),
                ('Opp Half TO Rate %',    'OV_OppTORate_pct',   True,  1, '%'),
            ]
        },
        {
            'label': 'Defence', 'color': '#2563EB', 'icon': '🛡',
            'metrics': [
                ('Points Against / G',      'OV_PointsAgainst_PG',  True,  1, ''),
                ('Tries Conceded',          'OV_TriesConceded',      True,  0, ''),
                ('Tackle Success %',        'OV_TackleSuccess_pct',  False, 1, '%'),
                ('Turnover Won / G',        'OV_TurnoverWon_PG',     False, 2, ''),
                ('Line Break Conceded / G', 'OV_LBConceded_PG',      True,  2, ''),
                ('Penalties Con / G',       'OV_PenaltiesCon_PG',    True,  2, ''),
            ]
        },
    ]

    # 全指標をフラットに（ランキング用）
    OV = []
    for cat in OV_CATS:
        OV.extend(cat['metrics'])

    # 旧 OV KPIグリッド: 4カラム縦構成の kpi_dual カード列。KPIカード廃止のためコメントアウト。
    # ov_cat_cols = ""
    # for cat in OV_CATS:
    #     cards = "".join(kpi_dual(l,c,a if a is not None else False,d,s) for l,c,a,d,s in cat['metrics'])
    #     ov_cat_cols += f'''<div style="display:flex;flex-direction:column;gap:8px">
    #       <div style="...background:{cat["color"]}11...">{cat["icon"]} {cat["label"]}</div>
    #       {cards}
    #     </div>'''
    # 旧 ov_html = f"""<div style="display:grid;grid-template-columns:repeat(4,1fr)...">{ov_cat_cols}</div>{legend}<div ...ranking...>"""
    # ov_html は rank_section 定義後に代入（下記 rank_section 定義の後）

    def cat_section(sid, metrics, title_kpi, title_rank):
        kpi = kpi_grid(metrics)
        rk  = rank_grid(metrics)
        return f"""
<div style="margin-bottom:14px">
  <div style="font-family:'Oswald',sans-serif;font-size:11px;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:#495057;padding-bottom:6px;border-bottom:2px solid #DEE2E6;margin-bottom:12px;display:flex;align-items:center;gap:6px">
    <span style="display:block;width:3px;height:12px;border-radius:2px;background:#495057;flex-shrink:0"></span>① {title_kpi}
  </div>
  {kpi}
</div>
{legend}
<div style="background:#fff;border:1px solid #DEE2E6;border-radius:8px;padding:18px;box-shadow:0 1px 3px rgba(0,0,0,.04)">
  <div style="display:flex;align-items:center;gap:10px;margin-bottom:14px;padding-bottom:8px;border-bottom:1px solid #F1F3F5">
    <div style="width:26px;height:26px;border-radius:50%;background:#F8F9FA;border:1px solid #DEE2E6;display:flex;align-items:center;justify-content:center;font-size:13px">🏆</div>
    <div style="font-family:'Oswald',sans-serif;font-size:12px;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:#495057">② {title_rank}</div>
  </div>
  {rk}
</div>"""

    def rank_section(sid, metrics, title_rank):
        """KPIカードなし・ランキングのみのセクション生成（cat_section から①KPI部を除いたもの）"""
        rk = rank_grid(metrics)
        return f"""
{legend}
<div style="background:#fff;border:1px solid #DEE2E6;border-radius:8px;padding:18px;box-shadow:0 1px 3px rgba(0,0,0,.04)">
  <div style="display:flex;align-items:center;gap:10px;margin-bottom:14px;padding-bottom:8px;border-bottom:1px solid #F1F3F5">
    <div style="width:26px;height:26px;border-radius:50%;background:#F8F9FA;border:1px solid #DEE2E6;display:flex;align-items:center;justify-content:center;font-size:13px">🏆</div>
    <div style="font-family:'Oswald',sans-serif;font-size:12px;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:#495057">{title_rank}</div>
  </div>
  {rk}
</div>"""

    ov_html = rank_section('ov', OV, 'League Ranking')

    # Try Analysis
    # 旧 Try Conceded 色: try_panel(h_tc,'#9CA3AF',...) / try_panel(o_tc,'#9CA3AF',...)
    # → Spears=#0EA5E9（水色）/ 相手=#4B5563（濃いグレー）に変更
    try_html = f"""
<div style="font-family:'Oswald',sans-serif;font-size:11px;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:#495057;padding-bottom:6px;border-bottom:2px solid #DEE2E6;margin-bottom:12px;display:flex;align-items:center;gap:6px">
  <span style="display:block;width:3px;height:12px;border-radius:2px;background:#16A34A;flex-shrink:0"></span>Try Scored
</div>
<div style="{two}">
  {try_panel(h_ts,h_col,h_sht+' — Try Scored',ts_rank(home),ts_avg)}
  {try_panel(o_ts,o_col,o_sht+' — Try Scored',ts_rank(opp),ts_avg)}
</div>
<div style="font-family:'Oswald',sans-serif;font-size:11px;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:#495057;padding-bottom:6px;border-bottom:2px solid #DEE2E6;margin-bottom:12px;margin-top:20px;display:flex;align-items:center;gap:6px">
  <span style="display:block;width:3px;height:12px;border-radius:2px;background:#DC2626;flex-shrink:0"></span>Try Conceded
</div>
<div style="{two}">
  {try_panel(h_tc,'#0EA5E9',h_sht+' — Try Conceded',tc_rank(home),tc_avg)}
  {try_panel(o_tc,'#4B5563',o_sht+' — Try Conceded',tc_rank(opp),tc_avg)}
</div>"""

    # 旧 LB Conceded 色: lb_panel(h_lc,'#9CA3AF',...,'#9CA3AF',h_col) / lb_panel(o_lc,'#9CA3AF',...,'#9CA3AF',o_col)
    # → Spears: tc=#0EA5E9, pc=#7DD3FC（薄・相手成功）, nc=#0EA5E9（濃・我成功）, water=True
    # → 相手:   tc=#4B5563, pc=#4B5563, nc=#6B7280
    # Line Break
    lb_html = f"""
<div style="font-family:'Oswald',sans-serif;font-size:11px;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:#495057;padding-bottom:6px;border-bottom:2px solid #DEE2E6;margin-bottom:12px;display:flex;align-items:center;gap:6px">
  <span style="display:block;width:3px;height:12px;border-radius:2px;background:#16A34A;flex-shrink:0"></span>Line Breaks Scored
</div>
<div style="{two}">
  {lb_panel(h_ls,h_col,h_sht+' — LB Scored',lb_rank(home),lb_avg,h_col,'#9CA3AF')}
  {lb_panel(o_ls,o_col,o_sht+' — LB Scored',lb_rank(opp),lb_avg,o_col,'#9CA3AF')}
</div>
<div style="font-family:'Oswald',sans-serif;font-size:11px;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:#495057;padding-bottom:6px;border-bottom:2px solid #DEE2E6;margin-bottom:12px;margin-top:20px;display:flex;align-items:center;gap:6px">
  <span style="display:block;width:3px;height:12px;border-radius:2px;background:#DC2626;flex-shrink:0"></span>Line Breaks Conceded
</div>
<div style="{two}">
  {lb_panel(h_lc,'#0EA5E9',h_sht+' — LB Conceded',lbc_rank(home),lbc_avg,'#7DD3FC','#0EA5E9',water=True)}
  {lb_panel(o_lc,'#4B5563',o_sht+' — LB Conceded',lbc_rank(opp),lbc_avg,'#4B5563','#6B7280')}
</div>"""

    # LB Rankings & 22m Rankings
    LB_RANK = [
        ('Line Breaks / G',         'OV_LineBreaks_PG',      False, 2, ''),
        ('Defender Beaten / G',     'OV_DefBeaten_PG',       False, 1, ''),
        ('Breach Conversion %',     'LB_BreachConv_pct',     False, 1, '%'),
        ('LB within 1-3 Phase %',   'LB_3Phase_pct',         False, 1, '%'),
        ('Opp Line Breaks / G',     'OV_LBConceded_PG',      True,  2, ''),
        ('Opp Defender Beaten / G', 'OV_DefBeatenConc_PG',   True,  1, ''),
        ('Opp Breach Conv %',       'LB_OppBreachConv_pct',  True,  1, '%'),
        ('Opp LB 1-3 Phase %',      'Opp_LB_3Phase_pct',     True,  1, '%'),
    ]
    M22_RANK = [
        ('22m Entry / G',           'TRY_22mEntry_PG',       False, 2, ''),
        ('22m Strike Conv %',        'OV_22mConv_pct',        False, 1, '%'),
        ('Carried into 22m / G',    'TRY_22mCarried_PG',     False, 2, ''),
        ('Score / 22m Entry',       'TRY_ScorePer22m',       False, 2, 'pts'),
        ('Opp 22m Entry / G',       'TRY_Opp22mEntry_PG',    True,  2, ''),
        ('Opp 22m Strike Conv %',    'OV_Opp22mConv_pct',     True,  1, '%'),
        ('Opp Carried into 22m/G',  'TRY_Opp22mCarried_PG',  True,  2, ''),
        ('Score Conc / 22m Entry',  'TRY_ScoreConcPer22m',   True,  2, 'pts'),
    ]

    # Try Source
    # 旧 TS KPIグリッド: ① Team KPIs — Try Source（TS_SCORED/TS_CONC の kpi_grid 2列）を廃止。
    # ロールバック時は ts_html の冒頭 <div style="margin-bottom:16px">...{legend} ブロックを復元。
    ts_html = f"""
{legend}
<div style="background:#fff;border:1px solid #DEE2E6;border-radius:8px;padding:18px;box-shadow:0 1px 3px rgba(0,0,0,.04)">
  <div style="display:flex;align-items:center;gap:10px;margin-bottom:14px;padding-bottom:8px;border-bottom:1px solid #F1F3F5">
    <div style="width:26px;height:26px;border-radius:50%;background:#F8F9FA;border:1px solid #DEE2E6;display:flex;align-items:center;justify-content:center;font-size:13px">🏆</div>
    <div style="font-family:'Oswald',sans-serif;font-size:12px;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:#495057">② League Ranking — Source of Tries</div>
  </div>
  {ts_src_html}
</div>"""

    # --- Individual Ranking section ---
    ind_html = '<div style="padding:24px;color:#aaa">データなし</div>'
    if df is not None:
        def _player_rank(df_team, cond_fn, val_col='count', n=5):
            sub = df_team[cond_fn(df_team) & df_team['playerName'].notna() & (df_team['playerName'] != '')]
            if val_col == 'count':
                g = sub.groupby('playerName').size().reset_index(name='val')
            else:
                g = sub.groupby('playerName')[val_col].sum().reset_index(name='val')
            pos_lkp = df_team[df_team['playerName'].notna()].groupby('playerName')['playerpositionName'].first()
            g['pos'] = g['playerName'].map(pos_lkp).fillna('')
            return g[g['val'] > 0].sort_values('val', ascending=False).head(n).to_dict('records')

        def _tow_cond(d):
            return (
                ((d['actionName'] == 'Tackle') & (d['ActionResultName'].isin(['Turnover Won', 'Forced in Touch']))) |
                ((d['actionName'] == 'Ruck') & (d['ActionResultName'] == 'Penalty Won')) |
                ((d['actionName'] == 'Collection') & (d['ActionTypeName'] == 'Jackal') & (d['ActionResultName'] == 'Success')) |
                ((d['actionName'] == 'Lineout Take') & (d['ActionTypeName'].str.startswith('Lineout Steal', na=False))) |
                ((d['actionName'] == 'Ruck OOA') & (d['ActionTypeName'] == 'Turnover Won'))
            )

        def _ind_card(team_color, team_short, title, recs, fmt=None):
            fmt_fn = fmt if fmt else (lambda v: str(int(round(float(v)))))
            medals = ['1st', '2nd', '3rd', '4th', '5th']
            items = ''
            for i, r in enumerate(recs[:5]):
                bg = 'background:#F8FAFC;' if i % 2 == 0 else 'background:#fff;'
                items += (
                    f'<div style="display:flex;align-items:center;gap:8px;padding:7px 12px;{bg}">'
                    f'<span style="font-size:10px;font-weight:700;color:#94A3B8;min-width:28px">{medals[i]}</span>'
                    f'<span style="font-size:13px;font-weight:700;color:#1E293B;flex:1">{r["playerName"]}</span>'
                    f'<span style="font-size:9px;color:#64748B;background:#EEF2FF;padding:1px 5px;border-radius:3px;margin-right:4px">{r["pos"]}</span>'
                    f'<span style="font-family:Oswald,sans-serif;font-size:16px;font-weight:700;color:{team_color}">{fmt_fn(r["val"])}</span>'
                    '</div>'
                )
            if not items:
                items = '<div style="padding:12px;color:#aaa;font-size:12px">No data</div>'
            return (
                '<div style="background:#fff;border:1px solid #DEE2E6;border-radius:8px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.04)">'
                f'<div style="background:#1E3A5F;padding:9px 14px;display:flex;align-items:center;gap:8px">'
                f'<span style="width:8px;height:8px;border-radius:50%;background:{team_color};display:inline-block"></span>'
                f'<span style="font-size:11px;font-weight:700;color:#fff;letter-spacing:.06em">{team_short} — {title}</span>'
                f'</div>{items}</div>'
            )

        def _ind_pair(title, recs_h, recs_o, fmt=None):
            lcard = _ind_card(h_col, h_sht, title, recs_h, fmt)
            rcard = _ind_card(o_col, o_sht, title, recs_o, fmt)
            return f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:12px">{lcard}{rcard}</div>'

        df_h = df[df['teamName'] == home]
        df_o = df[df['teamName'] == opp]

        _atk_hdr = (
            '<div style="padding:7px 14px;background:#1E3A5F;border-radius:6px;margin-bottom:12px">'
            '<span style="font-family:Oswald,sans-serif;font-size:13px;font-weight:700;color:#fff;text-transform:uppercase;letter-spacing:.1em">'
            '⚡ Attack Individual Rankings (R1–R' + str(max_round) + ')'
            '</span></div>'
        )
        _def_hdr = (
            '<div style="padding:7px 14px;background:#1E3A5F;border-radius:6px;margin-bottom:12px">'
            '<span style="font-family:Oswald,sans-serif;font-size:13px;font-weight:700;color:#fff;text-transform:uppercase;letter-spacing:.1em">'
            '\U0001f6e1 Defence Individual Rankings (R1–R' + str(max_round) + ')'
            '</span></div>'
        )

        ind_html = (
            '<div style="margin-bottom:20px">' + _atk_hdr
            + _ind_pair('Ball Carries',
                _player_rank(df_h, lambda d: d['actionName'] == 'Carry'),
                _player_rank(df_o, lambda d: d['actionName'] == 'Carry'))
            + _ind_pair('Carry Metres',
                _player_rank(df_h, lambda d: d['actionName'] == 'Carry', 'Metres'),
                _player_rank(df_o, lambda d: d['actionName'] == 'Carry', 'Metres'),
                lambda v: str(int(round(float(v)))))
            + _ind_pair('Defenders Beaten',
                _player_rank(df_h, lambda d: (d['actionName'] == 'Attacking Qualities') & (d['ActionTypeName'] == 'Defender Beaten')),
                _player_rank(df_o, lambda d: (d['actionName'] == 'Attacking Qualities') & (d['ActionTypeName'] == 'Defender Beaten')))
            + _ind_pair('Offloads',
                _player_rank(df_h, lambda d: (d['actionName'] == 'Pass') & (d['ActionTypeName'] == 'Offload') & (d['ActionResultName'] == 'Own Player')),
                _player_rank(df_o, lambda d: (d['actionName'] == 'Pass') & (d['ActionTypeName'] == 'Offload') & (d['ActionResultName'] == 'Own Player')))
            + _ind_pair('Tries Scored',
                _player_rank(df_h, lambda d: d['actionName'] == 'Try'),
                _player_rank(df_o, lambda d: d['actionName'] == 'Try'))
            + '</div><div>' + _def_hdr
            + _ind_pair('Tackles Made',
                _player_rank(df_h, lambda d: d['actionName'] == 'Tackle'),
                _player_rank(df_o, lambda d: d['actionName'] == 'Tackle'))
            + _ind_pair('Turnovers Won',
                _player_rank(df_h, _tow_cond),
                _player_rank(df_o, _tow_cond))
            + _ind_pair('Penalties Conceded',
                _player_rank(df_h, lambda d: d['actionName'] == 'Penalty Conceded'),
                _player_rank(df_o, lambda d: d['actionName'] == 'Penalty Conceded'))
            + '</div>'
        )

    # 旧: ov セクション → rank_section に変更（OV KPIカード廃止）。ロールバック時は ov_html 変数を上記コメント版に戻す。
    # 旧: atk セクション = cat_section('atk',ATT,'Attack KPIs','Attack Rankings')
    # 旧: def セクション = cat_section('def',DEF,'Defence KPIs','Defence Rankings')
    # → atk/def ともに rank_section に変更（KPIカード廃止）。ロールバック時は下の各 <div id="..."> 行を戻す。
    # 旧: sp セクション → sp_html 変数を使用（KPIカード廃止）。ロールバック時は sp_html 変数と <div id="sp"> 行を元の f'''...''' 版に戻す。
    # 旧: kick セクション → My Kicks/Opp Kicks kpi_dual ブロック廃止（ランキング部は2グループ維持）。ロールバック時は <div id="kick"> 冒頭の2ブロックを復元。
    # 旧: ts セクション → ① Team KPIs ブロック廃止（ts_src_html ランキングは維持）。ロールバック時は ts_html 冒頭の kpi_grid ブロックを復元。
    # 旧: lb22 セクション → Line Break KPIs + 22m KPIs 廃止（両ランキングは維持）。ロールバック時は <!-- 旧 LB/22m KPIs --> コメント以前のブロックを復元。
    return f"""<!DOCTYPE html><html lang="ja"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Scout Report | {h_sht} vs {o_sht} | 2025-26 R1-R{max_round}</title>
{CSS}</head><body>
<div class="top-bar"><div class="top-bar-inner">
<div style="display:flex;align-items:stretch">
  <div style="display:flex;align-items:center;gap:10px;padding:10px 14px;border-right:3px solid {h_col}">
    <div style="width:32px;height:32px;border-radius:50%;background:{h_col};display:flex;align-items:center;justify-content:center;font-family:'Oswald',sans-serif;font-size:10px;font-weight:700;color:#fff">{h_bdg}</div>
    <div><div style="font-family:'Oswald',sans-serif;font-size:14px;font-weight:700;color:{h_col}">{h_sht}</div><div style="font-size:9px;color:#aaa">{home}</div></div>
  </div>
  <div style="padding:0 14px;display:flex;align-items:center;font-family:'Oswald',sans-serif;font-size:16px;font-weight:700;color:#aaa;border-right:1px solid #DEE2E6">VS</div>
  <div style="display:flex;align-items:center;gap:10px;padding:10px 14px;border-left:3px solid {o_col}">
    <div><div style="font-family:'Oswald',sans-serif;font-size:14px;font-weight:700;color:{o_col}">{o_sht}</div><div style="font-size:9px;color:#aaa">{opp}</div></div>
    <div style="width:32px;height:32px;border-radius:50%;background:{o_col};display:flex;align-items:center;justify-content:center;font-family:'Oswald',sans-serif;font-size:10px;font-weight:700;color:#fff">{o_bdg}</div>
  </div>
  <div style="padding:0 14px;display:flex;align-items:center;font-size:10px;color:#aaa;border-left:1px solid #DEE2E6">2025-26 League One · R1–R{max_round}</div>
</div>
<div class="nav-tabs">
  <button class="nav-btn active" style="color:#495057" onclick="showSection('ov',this)">Overview</button>
  <button class="nav-btn" style="color:{h_col}" onclick="showSection('atk',this)">Attack</button>
  <button class="nav-btn" style="color:#2563EB" onclick="showSection('def',this)">Defence</button>
  <button class="nav-btn" style="color:#0891B2" onclick="showSection('kick',this)">Kicking</button>
  <button class="nav-btn" style="color:#7C3AED" onclick="showSection('sp',this)">Set Piece</button>
  <button class="nav-btn" style="color:#16A34A" onclick="showSection('try',this)">Try Analysis</button>
  <button class="nav-btn" style="color:#D97706" onclick="showSection('lb',this)">Line Break</button>
  <button class="nav-btn" style="color:#DC2626" onclick="showSection('ts',this)">Try Source</button>
  <button class="nav-btn" style="color:#0891B2" onclick="showSection('lb22',this)">LB & 22m</button>
  <button class="nav-btn" style="color:#7C3AED" onclick="showSection('ai',this)">AI Scout</button>
  <button class="nav-btn" style="color:#16A34A" onclick="showSection('winloss',this)">Win / Loss</button>
  <button class="nav-btn" style="color:#F59E0B" onclick="showSection('ind',this)">Individual Ranking</button>
</div>
</div></div>

<div class="main">
  <div id="ov"   class="section active">{ov_html}</div>
  <div id="atk"  class="section">{rank_section('atk',ATT,'Attack Rankings')}</div>
  <div id="def"  class="section">{rank_section('def',DEF,'Defence Rankings')}</div>
  <div id="kick" class="section">{f'''
    {legend}
    <div style="background:#fff;border:1px solid #DEE2E6;border-radius:8px;padding:18px;box-shadow:0 1px 3px rgba(0,0,0,.04)">
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:14px;padding-bottom:8px;border-bottom:1px solid #F1F3F5">
        <div style="font-family:Oswald,sans-serif;font-size:12px;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:#495057">🏆 League Ranking</div>
      </div>
      <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px">
        {"".join(rank_card(l,c,a if a is not None else False,d,s) for l,c,a,d,s in KICK_OWN)}
      </div>
      <div style="height:12px"></div>
      <div style="font-family:Oswald,sans-serif;font-size:11px;font-weight:600;color:#DC2626;text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px;padding-bottom:4px;border-bottom:1px solid #DC262622">Opp Kicks Rankings</div>
      <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px">
        {"".join(rank_card(l,c,a if a is not None else False,d,s) for l,c,a,d,s in KICK_OPP)}
      </div>
    </div>
  '''}</div>
  <div id="sp" class="section">{legend}
    <div style="background:#fff;border:1px solid #DEE2E6;border-radius:8px;padding:18px;box-shadow:0 1px 3px rgba(0,0,0,.04)">
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:14px;padding-bottom:8px;border-bottom:1px solid #F1F3F5">
        <div style="width:26px;height:26px;border-radius:50%;background:#F8F9FA;border:1px solid #DEE2E6;display:flex;align-items:center;justify-content:center;font-size:13px">🏆</div>
        <div style="font-family:Oswald,sans-serif;font-size:12px;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:#495057">Set Piece Rankings</div>
      </div>
      <!-- 旧 SP: repeat(3,1fr);gap:14px 3カラム、Lineout/Maul/Scrum カテゴリ見出し付き。ロールバック: git show ea9e4f4:rugby_bi.py 参照 -->
      <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px">
        {"".join(rank_card(l,c,a if a is not None else False,d,s) for l,c,a,d,s in SP_LINEOUT + SP_SCRUM + SP_MAUL)}
      </div>
    </div>
  </div>
  <div id="try"  class="section">{try_html}</div>
  <div id="lb"   class="section">{lb_html}
  </div>
  <div id="ts"   class="section">{ts_html}</div>
  <div id="lb22" class="section">
    <!-- 旧 LB KPIs: ⚡ Line Break KPIs kpi_dual グリッド廃止。ロールバック時は下記コメントを復元。 -->
    <!-- LB Rankings -->
    <div style="background:#fff;border:1px solid #DEE2E6;border-radius:8px;padding:18px;margin-bottom:16px;box-shadow:0 1px 3px rgba(0,0,0,.04)">
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:14px;padding-bottom:8px;border-bottom:1px solid #F1F3F5">
        <div style="font-family:Oswald,sans-serif;font-size:12px;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:#D97706">🏆 Line Break Rankings</div>
        <div style="font-size:10px;color:#aaa;margin-left:auto">全12チーム · ハイライト: {h_sht} / {o_sht}</div>
      </div>
      {legend}
      <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:10px">
      {"".join(rank_card(l,c,a if a is not None else False,d,s) for l,c,a,d,s in LB_RANK)}
      </div>
    </div>
    <!-- 旧 22m KPIs: 🎯 22m Strike Conversion KPIs kpi_dual グリッド廃止。ロールバック時は下記コメントを復元。 -->
    <!-- 22m Rankings -->
    <div style="background:#fff;border:1px solid #DEE2E6;border-radius:8px;padding:18px;box-shadow:0 1px 3px rgba(0,0,0,.04)">
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:14px;padding-bottom:8px;border-bottom:1px solid #F1F3F5">
        <div style="font-family:Oswald,sans-serif;font-size:12px;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:#0891B2">🏆 22m Strike Conversion Rankings</div>
        <div style="font-size:10px;color:#aaa;margin-left:auto">全12チーム · ハイライト: {h_sht} / {o_sht}</div>
      </div>
      {legend}
      <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:10px">
      {"".join(rank_card(l,c,a if a is not None else False,d,s) for l,c,a,d,s in M22_RANK)}
      </div>
    </div>
  </div>
  <div id="winloss" class="section">{winloss_html}</div>
  <div id="ind" class="section">{ind_html}</div>
  <div id="ai" class="section">
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
      {ai_scout(home)}
      {ai_scout(opp)}
    </div>
  </div>
</div>

<button class="print-btn" onclick="window.print()">🖨 Print / PDF (A4横)</button>
{SHOW_JS}</body></html>"""

# ============================================================
# メイン
# ============================================================


def cmd_scout(args):
    """Generate scouting report HTML."""
    if not HAS_PANDAS:
        sys.exit("pandas/numpy required. Install: pip install pandas numpy")

    home = args.home
    opp = args.opp
    max_round = args.round
    data_dir = args.data
    out_dir = args.out

    print(f'📊 Loading CSV from: {data_dir}')
    files = glob.glob(os.path.join(data_dir, '*_BI.csv'))
    if not files:
        print('❌ CSVが見つかりません'); sys.exit(1)
    print(f'   {len(files)} files found')

    dfs = [pd.read_csv(f) for f in files]
    all_df = pd.concat(dfs, ignore_index=True)

    print(f'\n⚙️  Computing stats (R1–R{max_round})...')
    master, df = compute_stats(all_df, max_round)
    print(f'   {len(master)}チーム × {len(master.columns)}指標')

    print(f'\n⚙️  Computing Try/LB detail...')
    detail = compute_try_lb_detail(df)
    print(f'   {len(detail)}件')

    lb_s_d = detail[detail['type']=='LB Scored']
    lb_c_d = detail[detail['type']=='LB Conceded']
    for t in list(master.index):
        sub_s = lb_s_d[lb_s_d['team']==t]
        sub_c = lb_c_d[lb_c_d['team']==t]
        pos_s = len(sub_s[sub_s['outcome'].isin(['Try','Pen Won','Kick'])])
        tot_s = len(sub_s)
        pos_c = len(sub_c[sub_c['outcome'].isin(['Try','Pen Won','Kick'])])
        tot_c = len(sub_c)
        master.loc[t,'LB_BreachConv_pct']    = round(pos_s/tot_s*100,1) if tot_s else 0
        master.loc[t,'LB_OppBreachConv_pct'] = round(pos_c/tot_c*100,1) if tot_c else 0
        e_s = len(sub_s[sub_s['phase'].isin(['1 Phase','2/3 Phase'])])
        e_c = len(sub_c[sub_c['phase'].isin(['1 Phase','2/3 Phase'])])
        master.loc[t,'LB_3Phase_pct']    = round(e_s/tot_s*100,1) if tot_s else 0
        master.loc[t,'Opp_LB_3Phase_pct'] = round(e_c/tot_c*100,1) if tot_c else 0

    print(f'\n🏉 Building report: {home} vs {opp}')
    html = build_html(home, opp, master, detail, max_round, df=df)

    os.makedirs(out_dir, exist_ok=True)
    h_s = TEAM_SHORT.get(home, home.replace(' ',''))
    o_s = TEAM_SHORT.get(opp, opp.replace(' ',''))
    fname = f'scout_{h_s}_vs_{o_s}_R{max_round}.html'
    out_path = os.path.join(out_dir, fname)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'\n✅ 完成: {out_path}')
    print(f'   ファイルサイズ: {os.path.getsize(out_path)//1024}KB')



# ═══════════════════════════════════════════════════════════════
# SECTION 5: DB BUILDER
# ═══════════════════════════════════════════════════════════════

def cmd_build(args=None):
    """Build rugby.db from CSV data."""
    import csv

    data_dir = args.data if args and hasattr(args, 'data') and args.data else "."
    HERE = os.path.abspath(data_dir) if data_dir != "." else os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rugby.db")
    TARGET = "Kubota Spears"

    def to_iso(d):
        try:
            dd, mm, yy = d.split("/")
            return f"{yy}-{mm}-{dd}"
        except Exception:
            return d

    def num(v):
        if v is None or v == "":
            return None
        try:
            return int(v)
        except ValueError:
            try:
                return float(v)
            except ValueError:
                return v

    # find qualifying CSV files
    files = []
    for f in sorted(glob.glob(os.path.join(HERE, "*.csv"))):
        with open(f, encoding="utf-8-sig", newline="") as fh:
            r = csv.DictReader(fh)
            first = next(r, None)
            if first and TARGET in (first.get("homeTeamName",""), first.get("awayTeamName","")):
                files.append((f, first))

    if not files:
        # Try BI Scouting subdirectory
        for f in sorted(glob.glob(os.path.join(HERE, "BI Scouting", "*.csv"))):
            with open(f, encoding="utf-8-sig", newline="") as fh:
                r = csv.DictReader(fh)
                first = next(r, None)
                if first and TARGET in (first.get("homeTeamName",""), first.get("awayTeamName","")):
                    files.append((f, first))

    if not files:
        sys.exit(f"No Kubota Spears matches found in {HERE}")

    if os.path.exists(db_path):
        os.remove(db_path)
    con = sqlite3.connect(db_path)
    cur = con.cursor()

    cur.execute("""
    CREATE TABLE matches (
        fxid INTEGER PRIMARY KEY, date_played TEXT, round_number INTEGER,
        season INTEGER, competition_id INTEGER, competition_name TEXT,
        home_team_id INTEGER, home_team_name TEXT, away_team_id INTEGER, away_team_name TEXT,
        home_ht_score INTEGER, away_ht_score INTEGER, home_ft_score INTEGER, away_ft_score INTEGER,
        venue_id INTEGER, venue_name TEXT, city_name TEXT, kickoff_time TEXT,
        home_coach_name TEXT, away_coach_name TEXT, referee_name TEXT,
        kubota_is_home INTEGER, kubota_score INTEGER, opponent_name TEXT,
        opponent_score INTEGER, kubota_result TEXT, source_file TEXT
    )""")

    EVENT_COLS = [
        "event_pk","fxid","row_id","plid","player_name","team_id","team_name",
        "ps_timestamp","ps_endstamp","match_time","period",
        "x_coord","y_coord","x_coord_end","y_coord_end",
        "action","action_name","action_type","action_type_name",
        "action_result","action_result_name",
        "qualifier3","qualifier3_name","qualifier4","qualifier4_name",
        "qualifier5","qualifier5_name","qualifier6","qualifier6_name",
        "qualifier7","qualifier7_name","qualifier8","qualifier8_name",
        "qualifier9","qualifier9_name","qualifier10","qualifier10_name",
        "field_zone",
        "metres","metres2","metres3","metres4",
        "utc_time","play_num","set_num","sequence_id",
        "player_advantage","score_advantage",
        "hometeam_current_score","awayteam_current_score",
        "player_shirt_number","player_position_id","player_position_name",
        "is_home","result",
        "assoc_player","assoc_player_name","assoc_player_team",
        "assoc_player_team_name","assoc_event_id",
    ]
    col_defs = ",\n    ".join(
        "event_pk INTEGER PRIMARY KEY AUTOINCREMENT" if c == "event_pk"
        else f"{c} {'INTEGER' if c == 'fxid' else 'TEXT'}"
        for c in EVENT_COLS
    )
    cur.execute(f"CREATE TABLE events (\n    {col_defs},\n    FOREIGN KEY(fxid) REFERENCES matches(fxid)\n)")

    CSV_TO_COL = {
        "ID":"row_id","PLID":"plid","playerName":"player_name",
        "team_id":"team_id","teamName":"team_name",
        "ps_timestamp":"ps_timestamp","ps_endstamp":"ps_endstamp",
        "MatchTime":"match_time","period":"period",
        "x_coord":"x_coord","y_coord":"y_coord",
        "x_coord_end":"x_coord_end","y_coord_end":"y_coord_end",
        "action":"action","actionName":"action_name",
        "ActionType":"action_type","ActionTypeName":"action_type_name",
        "Actionresult":"action_result","ActionResultName":"action_result_name",
        "qualifier3":"qualifier3","qualifier3Name":"qualifier3_name",
        "qualifier4":"qualifier4","qualifier4Name":"qualifier4_name",
        "qualifier5":"qualifier5","qualifier5Name":"qualifier5_name",
        "qualifier6":"qualifier6","qualifier6Name":"qualifier6_name",
        "qualifier7":"qualifier7","qualifier7Name":"qualifier7_name",
        "qualifier8":"qualifier8","qualifier8Name":"qualifier8_name",
        "qualifier9":"qualifier9","qualifier9Name":"qualifier9_name",
        "qualifier10":"qualifier10","qualifier10Name":"qualifier10_name",
        "Metres":"metres","Metres2":"metres2","Metres3":"metres3","Metres4":"metres4",
        "UTCTime":"utc_time","PlayNum":"play_num","SetNum":"set_num",
        "sequence_id":"sequence_id",
        "player_advantage":"player_advantage","score_advantage":"score_advantage",
        "hometeamCurrentScore":"hometeam_current_score",
        "awayteamCurrentScore":"awayteam_current_score",
        "playerShirtNumber":"player_shirt_number",
        "playerpositionID":"player_position_id",
        "playerpositionName":"player_position_name",
        "isHome":"is_home","result":"result",
        "assoc_player":"assoc_player","assoc_playerName":"assoc_player_name",
        "assoc_playerTeam":"assoc_player_team",
        "assoc_playerTeamName":"assoc_player_team_name",
        "assoc_event_id":"assoc_event_id",
    }
    insert_cols = [c for c in EVENT_COLS if c not in ("event_pk",)]
    placeholders = ",".join("?" * len(insert_cols))
    ev_sql = f"INSERT INTO events ({','.join(insert_cols)}) VALUES ({placeholders})"

    n_events = 0
    for path, first in files:
        fxid = num(first["FXID"])
        is_home = first["homeTeamName"] == TARGET
        if is_home:
            kub_score = num(first["hometeamFTscore"]); opp_score = num(first["awayteamFTscore"])
            opp_name = first["awayTeamName"]
        else:
            kub_score = num(first["awayteamFTscore"]); opp_score = num(first["hometeamFTscore"])
            opp_name = first["homeTeamName"]
        res = None if kub_score is None or opp_score is None else ("W" if kub_score > opp_score else "L" if kub_score < opp_score else "D")

        cur.execute(
            "INSERT INTO matches VALUES (" + ",".join("?" * 27) + ")",
            (fxid, to_iso(first["datePlayed"]), num(first["roundNumber"]), num(first["season"]),
             num(first["competitionID"]), first["competitionName"],
             num(first["homeTeamID"]), first["homeTeamName"],
             num(first["awayTeamID"]), first["awayTeamName"],
             num(first["hometeamHTscore"]), num(first["awayteamHTscore"]),
             num(first["hometeamFTscore"]), num(first["awayteamFTscore"]),
             num(first["venueID"]), first["venueName"], first["cityName"],
             first["kickofftime"], first["homecoachName"], first["awaycoachName"],
             first["refereeName"], 1 if is_home else 0,
             kub_score, opp_name, opp_score, res, os.path.basename(path)),
        )

        with open(path, encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                vals = [fxid]
                for col in insert_cols[1:]:
                    csv_key = next((k for k, v in CSV_TO_COL.items() if v == col), None)
                    vals.append(num(row[csv_key]) if csv_key else None)
                cur.execute(ev_sql, vals)
                n_events += 1

    # Derive field_zone from x_coord (not in CSV, computed from coordinate)
    cur.execute("""
        UPDATE events SET field_zone =
            CASE
                WHEN x_coord IS NULL OR x_coord = '' THEN NULL
                WHEN CAST(x_coord AS REAL) >= 78 THEN 'Attack 22'
                WHEN CAST(x_coord AS REAL) >= 50 THEN 'Attack 1/2'
                WHEN CAST(x_coord AS REAL) > 22 THEN 'Def 1/2'
                ELSE 'Def 22'
            END
    """)
    cur.execute("CREATE INDEX idx_events_fxid ON events(fxid)")
    cur.execute("CREATE INDEX idx_events_team ON events(team_id)")
    cur.execute("CREATE INDEX idx_events_action ON events(action_name)")
    con.commit()
    con.close()
    print(f"✅ rugby.db built: {len(files)} matches, {n_events} events")


# ═══════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Kubota Spears BI Analytics Suite",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", help="Available commands")

    p_build = sub.add_parser("build", help="Build rugby.db from CSV data")
    p_build.add_argument("--data", default="../BI Scouting", help="CSV data directory")

    p_match = sub.add_parser("match", help="Generate match report")
    p_match.add_argument("--round", type=int, help="Round number")
    p_match.add_argument("--opponent", help="Opponent team name")
    p_match.add_argument("--fxid", type=int, help="Match FXID")
    p_match.add_argument("--match-date", help="Match date (YYYY-MM-DD)")

    p_scout = sub.add_parser("scout", help="Generate scouting report")
    p_scout.add_argument("--home", default="Kubota Spears", help="Home team")
    p_scout.add_argument("--opp", required=True, help="Opponent team")
    p_scout.add_argument("--round", type=int, required=True, help="Round number")
    p_scout.add_argument("--data", default="../BI Scouting", help="CSV data directory")
    p_scout.add_argument("--out", default=".", help="Output directory")

    p_kpi = sub.add_parser("kpi", help="Generate season KPI report")

    p_all = sub.add_parser("all", help="Run build + kpi")
    p_all.add_argument("--data", default="../BI Scouting", help="CSV data directory")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(0)

    if args.command == "build":
        cmd_build(args)
    elif args.command == "match":
        cmd_match(args)
    elif args.command == "scout":
        cmd_scout(args)
    elif args.command == "kpi":
        cmd_kpi(args)
    elif args.command == "all":
        cmd_build(args)
        cmd_kpi(args)
        print("✅ All done.")


if __name__ == "__main__":
    main()
