"""
Match Report Stats Generator - Final Version
Opta CSV → 試合統計集計

Usage:
    python match_stats_final.py <bi_csv_path>

Scoring: Try=5pts, Conversion=2pts(kicked only), PG=3pts(kicked only), DG=3pts(kicked only)
Turnover Won: Possession TO Won + Jackal Success (重複除外)
"""

import pandas as pd
import json
import sys

def load_data(csv_path):
    df = pd.read_csv(csv_path)
    p2_start = df[df['period']==2]['ps_timestamp'].min()
    def match_minute(row):
        ps = row['ps_timestamp']
        return ps/60 if row['period']==1 else 40+(ps-p2_start)/60
    df['match_min'] = df.apply(match_minute, axis=1)
    def quarter(m):
        if m<=20: return 'Q1'
        elif m<=40: return 'Q2'
        elif m<=60: return 'Q3'
        else: return 'Q4'
    df['quarter'] = df['match_min'].apply(quarter)
    return df

def get_match_info(df):
    row = df.iloc[0]
    return {
        'home_team':   row['homeTeamName'],
        'away_team':   row['awayTeamName'],
        'home_score':  int(row['hometeamFTscore']),
        'away_score':  int(row['awayteamFTscore']),
        'home_ht':     int(row['hometeamHTscore']),
        'away_ht':     int(row['awayteamHTscore']),
        'venue':       row['venueName'],
        'date':        row['datePlayed'],
        'round':       int(row['roundNumber']),
        'competition': row['competitionName'],
    }

def calc_pts(df, team, q=None):
    """Try=5, Conv=2(kicked), PG=3(kicked), DG=3(kicked)"""
    t = df[df['teamName']==team]
    if q: t = t[t['quarter']==q]
    tries = len(t[t['actionName']=='Try'])
    conv  = len(t[(t['actionName']=='Goal Kick') & (t['ActionTypeName']=='Conversion') & (t['ActionResultName']=='Goal Kicked')])
    pg    = len(t[(t['actionName']=='Goal Kick') & (t['ActionTypeName']=='Penalty Goal') & (t['ActionResultName']=='Goal Kicked')])
    dg    = len(t[(t['actionName']=='Goal Kick') & (t['ActionTypeName']=='Drop Goal') & (t['ActionResultName']=='Goal Kicked')])
    return tries*5 + conv*2 + pg*3 + dg*3

def calc_to_won(df, team):
    """Opta定義: Possession TO Won + Jackal重複除外"""
    poss   = df[df['actionName']=='Possession']
    poss_to = poss[(poss['teamName']==team) & (poss['ActionTypeName']=='Turnover Won')]
    jck     = df[(df['teamName']==team) & (df['actionName']=='Collection') &
                 (df['ActionTypeName']=='Jackal') & (df['ActionResultName']=='Success')]
    poss_mins = poss_to['match_min'].tolist()
    jck_mins  = jck['match_min'].tolist()
    overlap   = sum(1 for j in jck_mins if any(abs(j-p) < 0.5 for p in poss_mins))
    return len(poss_to) + len(jck) - overlap

def calc_team_stats(df, team, opp):
    t  = df[df['teamName']==team]
    op = df[df['teamName']==opp]

    carries      = t[t['actionName']=='Carry']
    kicks        = t[t['actionName']=='Kick']
    rucks        = t[t['actionName']=='Ruck']
    tackles_made = t[t['actionName']=='Tackle']
    tackles_miss = t[t['actionName']=='Missed Tackle']
    lo_throws    = t[t['actionName']=='Lineout Throw']
    att_q        = t[t['actionName']=='Attacking Qualities']
    e22          = t[t['actionName']=='Attacking 22 Entry']

    nc = len(carries); cm = int(carries['Metres'].sum())
    nk = len(kicks);   km = int(kicks['Metres'].sum())
    nr = len(rucks);   rw = len(rucks[rucks['ActionResultName'].isin(['Won Outright','Penalty Won'])])
    nt = len(tackles_made)+len(tackles_miss)
    nlo = len(lo_throws)
    lo_won = len(lo_throws[lo_throws['ActionResultName'].isin(['Won Clean Catch','Won Tap (Scrappy)'])])
    n22 = len(e22); s22 = len(e22[e22['ActionTypeName'].str.contains('Try',na=False)])

    return {
        'tries':           len(t[t['actionName']=='Try']),
        'passes':          len(t[t['actionName']=='Pass']),
        'carries':         nc,
        'metres':          cm,
        'avg_carry':       round(cm/nc,1) if nc else 0,
        'linebreaks':      len(att_q[att_q['ActionTypeName']=='Initial Break']),
        'offloads':        len(carries[carries['ActionResultName']=='Off Load']),
        'kicks':           nk,
        'kick_m':          km,
        'avg_kick':        round(km/nk,1) if nk else 0,
        'rucks':           nr,
        'ruck_pct':        round(rw/nr*100,1) if nr else 0,
        'tack_att':        nt,
        'tack_miss':       len(tackles_miss),
        'tack_pct':        round(len(tackles_made)/nt*100,1) if nt else 0,
        'lineouts':        nlo,
        'lo_won':          lo_won,
        'lo_pct':          round(lo_won/nlo*100,1) if nlo else 0,
        'lo_steal':        len(t[(t['actionName']=='Sequences')&(t['ActionTypeName']=='Lineout Steal')]),
        'scrums':          len(t[t['actionName']=='Scrum']),
        'penalties':       len(t[t['actionName']=='Penalty Conceded']),
        'to_won':          calc_to_won(df, team),
        'to_con':          len(t[t['actionName']=='Turnover']),
        'e22':             n22,
        's22':             s22,
        's22_pct':         round(s22/n22*100,1) if n22 else 0,
    }

def calc_quarter_stats(df, team, q):
    t  = df[(df['teamName']==team) & (df['quarter']==q)]
    carries = t[t['actionName']=='Carry']
    kicks   = t[t['actionName']=='Kick']
    tack    = t[t['actionName']=='Tackle']
    miss    = t[t['actionName']=='Missed Tackle']
    att_q   = t[t['actionName']=='Attacking Qualities']
    nc = len(carries); nt = len(tack)+len(miss)
    return {
        'pts':        calc_pts(df, team, q),
        'tries':      len(t[t['actionName']=='Try']),
        'carries':    nc,
        'metres':     int(carries['Metres'].sum()),
        'avg_carry':  round(carries['Metres'].sum()/nc,1) if nc else 0,
        'passes':     len(t[t['actionName']=='Pass']),
        'kicks':      len(kicks),
        'tack_att':   nt,
        'tack_miss':  len(miss),
        'tack_pct':   round(len(tack)/nt*100,1) if nt else 0,
        'linebreaks': len(att_q[att_q['ActionTypeName']=='Initial Break']),
        'penalties':  len(t[t['actionName']=='Penalty Conceded']),
        'errors':     len(t[t['actionName']=='Turnover']),
    }

def build_teamsheet(df, team):
    p2_start = df[df['period']==2]['ps_timestamp'].min()
    def mm(row):
        ps = row['ps_timestamp']
        return ps/60 if row['period']==1 else 40+(ps-p2_start)/60
    t = df[df['teamName']==team]
    players = {}
    for _, row in t.iterrows():
        name = row['playerName']
        if name not in players and pd.notna(name):
            players[name] = {
                'shirt': int(row['playerShirtNumber']) if pd.notna(row['playerShirtNumber']) else 99,
                'pos': str(row['playerpositionName']),
                'name': name,
            }
    sub_in  = df[(df['teamName']==team) & (df['actionName']=='Sub In')].copy()
    sub_out = df[(df['teamName']==team) & (df['actionName']=='Sub Out')].copy()
    sub_in['min']  = sub_in.apply(mm, axis=1)
    sub_out['min'] = sub_out.apply(mm, axis=1)
    sub_in_d  = {r['playerName']: int(r['min']) for _, r in sub_in.iterrows()}
    sub_out_d = {r['playerName']: int(r['min']) for _, r in sub_out.iterrows()}
    rows = []
    for name, info in players.items():
        if name in sub_out_d: start, end = 0, sub_out_d[name]
        elif name in sub_in_d: start, end = sub_in_d[name], 80
        else: start, end = 0, 80
        rows.append({**info, 'start': start, 'end': end, 'mins': end-start})
    return sorted(rows, key=lambda x: x['shirt'])

if __name__ == '__main__':
    csv_path = sys.argv[1] if len(sys.argv)>1 else '/mnt/user-data/uploads/945332_CRUSvHIGH_BI.csv'
    df = load_data(csv_path)
    info = get_match_info(df)
    home, away = info['home_team'], info['away_team']

    print(f"{home} {info['home_score']} vs {info['away_score']} {away}")
    print(f"Round {info['round']} | {info['date']} | {info['venue']}")
    print(f"Points: {calc_pts(df,home)} / {calc_pts(df,away)}")
    print(f"TO Won: {calc_to_won(df,home)} / {calc_to_won(df,away)}")

