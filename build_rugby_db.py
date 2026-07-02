#!/usr/bin/env python3
"""Build rugby.db (SQLite) from BI CSVs for Kubota Spears matches.

Tables:
  matches : one row per match Kubota Spears played in
  events  : every event row from those matches (both teams)
"""
import csv, os, sqlite3, sys
from data_paths import CSV_DIR, DB_PATH, ensure_data_dirs, list_csv_files

HERE = os.path.dirname(os.path.abspath(__file__))
DB = DB_PATH
TARGET = "Kubota Spears"

ensure_data_dirs()

def to_iso(d):
    """'22/02/2026' -> '2026-02-22'; pass through anything unexpected."""
    try:
        dd, mm, yy = d.split("/")
        return f"{yy}-{mm}-{dd}"
    except Exception:
        return d

def num(v):
    """Empty string -> None, else int if it looks like one, else original."""
    if v is None or v == "":
        return None
    try:
        return int(v)
    except ValueError:
        try:
            return float(v)
        except ValueError:
            return v

# --- find qualifying files ---------------------------------------------------
files = []
for f in list_csv_files(CSV_DIR):
    with open(f, encoding="utf-8-sig", newline="") as fh:
        r = csv.DictReader(fh)
        first = next(r, None)
        if first and TARGET in (first["homeTeamName"], first["awayTeamName"]):
            files.append((f, first))

if not files:
    sys.exit(f"No Kubota Spears matches found in {CSV_DIR}.")

# --- (re)create database -----------------------------------------------------
if os.path.exists(DB):
    os.remove(DB)
con = sqlite3.connect(DB)
cur = con.cursor()

cur.execute("""
CREATE TABLE matches (
    fxid INTEGER PRIMARY KEY,
    date_played TEXT,
    round_number INTEGER,
    season INTEGER,
    competition_id INTEGER,
    competition_name TEXT,
    league TEXT,
    home_team_id INTEGER,
    home_team_name TEXT,
    away_team_id INTEGER,
    away_team_name TEXT,
    home_ht_score INTEGER,
    away_ht_score INTEGER,
    home_ft_score INTEGER,
    away_ft_score INTEGER,
    venue_id INTEGER,
    venue_name TEXT,
    city_name TEXT,
    kickoff_time TEXT,
    home_coach_name TEXT,
    away_coach_name TEXT,
    referee_name TEXT,
    kubota_is_home INTEGER,
    kubota_score INTEGER,
    opponent_name TEXT,
    opponent_score INTEGER,
    kubota_result TEXT,
    source_file TEXT
)
""")

# event columns: per-event data (match-level fields live in matches)
EVENT_COLS = [
    "event_pk",            # autoincrement
    "fxid",                # FK -> matches
    "row_id",              # original ID column in CSV
    "plid", "player_name", "team_id", "team_name",
    "ps_timestamp", "ps_endstamp", "match_time", "period",
    "x_coord", "y_coord", "x_coord_end", "y_coord_end",
    "action", "action_name", "action_type", "action_type_name",
    "action_result", "action_result_name",
    "qualifier3", "qualifier3_name", "qualifier4", "qualifier4_name",
    "qualifier5", "qualifier5_name", "qualifier6", "qualifier6_name",
    "qualifier7", "qualifier7_name", "qualifier8", "qualifier8_name",
    "qualifier9", "qualifier9_name", "qualifier10", "qualifier10_name",
    "metres", "metres2", "metres3", "metres4",
    "utc_time", "play_num", "set_num", "sequence_id",
    "player_advantage", "score_advantage",
    "hometeam_current_score", "awayteam_current_score",
    "player_shirt_number", "player_position_id", "player_position_name",
    "is_home", "result",
    "assoc_player", "assoc_player_name", "assoc_player_team",
    "assoc_player_team_name", "assoc_event_id",
]
col_defs = ",\n    ".join(
    "event_pk INTEGER PRIMARY KEY AUTOINCREMENT" if c == "event_pk"
    else f"{c} {'INTEGER' if c == 'fxid' else 'TEXT'}"
    for c in EVENT_COLS
)
cur.execute(f"CREATE TABLE events (\n    {col_defs},\n    FOREIGN KEY(fxid) REFERENCES matches(fxid)\n)")

# maps CSV header -> events column (excluding event_pk/fxid which we set manually)
CSV_TO_COL = {
    "ID": "row_id", "PLID": "plid", "playerName": "player_name",
    "team_id": "team_id", "teamName": "team_name",
    "ps_timestamp": "ps_timestamp", "ps_endstamp": "ps_endstamp",
    "MatchTime": "match_time", "period": "period",
    "x_coord": "x_coord", "y_coord": "y_coord",
    "x_coord_end": "x_coord_end", "y_coord_end": "y_coord_end",
    "action": "action", "actionName": "action_name",
    "ActionType": "action_type", "ActionTypeName": "action_type_name",
    "Actionresult": "action_result", "ActionResultName": "action_result_name",
    "qualifier3": "qualifier3", "qualifier3Name": "qualifier3_name",
    "qualifier4": "qualifier4", "qualifier4Name": "qualifier4_name",
    "qualifier5": "qualifier5", "qualifier5Name": "qualifier5_name",
    "qualifier6": "qualifier6", "qualifier6Name": "qualifier6_name",
    "qualifier7": "qualifier7", "qualifier7Name": "qualifier7_name",
    "qualifier8": "qualifier8", "qualifier8Name": "qualifier8_name",
    "qualifier9": "qualifier9", "qualifier9Name": "qualifier9_name",
    "qualifier10": "qualifier10", "qualifier10Name": "qualifier10_name",
    "Metres": "metres", "Metres2": "metres2", "Metres3": "metres3", "Metres4": "metres4",
    "UTCTime": "utc_time", "PlayNum": "play_num", "SetNum": "set_num",
    "sequence_id": "sequence_id",
    "player_advantage": "player_advantage", "score_advantage": "score_advantage",
    "hometeamCurrentScore": "hometeam_current_score",
    "awayteamCurrentScore": "awayteam_current_score",
    "playerShirtNumber": "player_shirt_number",
    "playerpositionID": "player_position_id",
    "playerpositionName": "player_position_name",
    "isHome": "is_home", "result": "result",
    "assoc_player": "assoc_player", "assoc_playerName": "assoc_player_name",
    "assoc_playerTeam": "assoc_player_team",
    "assoc_playerTeamName": "assoc_player_team_name",
    "assoc_event_id": "assoc_event_id",
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
    if kub_score is None or opp_score is None:
        res = None
    elif kub_score > opp_score:
        res = "W"
    elif kub_score < opp_score:
        res = "L"
    else:
        res = "D"

    comp = first["competitionName"]
    league = 'd1' if 'D1' in comp else ('d2' if 'D2' in comp else 'other')

    cur.execute(
        "INSERT INTO matches VALUES (" + ",".join("?" * 28) + ")",
        (
            fxid, to_iso(first["datePlayed"]), num(first["roundNumber"]), num(first["season"]),
            num(first["competitionID"]), first["competitionName"], league,
            num(first["homeTeamID"]), first["homeTeamName"],
            num(first["awayTeamID"]), first["awayTeamName"],
            num(first["hometeamHTscore"]), num(first["awayteamHTscore"]),
            num(first["hometeamFTscore"]), num(first["awayteamFTscore"]),
            num(first["venueID"]), first["venueName"], first["cityName"],
            first["kickofftime"], first["homecoachName"], first["awaycoachName"],
            first["refereeName"], 1 if is_home else 0,
            kub_score, opp_name, opp_score, res, os.path.basename(path),
        ),
    )

    with open(path, encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            vals = [fxid]
            for col in insert_cols[1:]:  # skip fxid (already added)
                csv_key = next((k for k, v in CSV_TO_COL.items() if v == col), None)
                vals.append(num(row[csv_key]) if csv_key else None)
            cur.execute(ev_sql, vals)
            n_events += 1

cur.execute("CREATE INDEX idx_events_fxid ON events(fxid)")
cur.execute("CREATE INDEX idx_events_team ON events(team_id)")
cur.execute("CREATE INDEX idx_events_action ON events(action_name)")
con.commit()

print(f"matches: {len(files)}")
print(f"events : {n_events}")
con.close()
