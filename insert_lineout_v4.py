#!/usr/bin/env python3
"""
Lineout section v4:
  - Labels: 4Man / 5Man / 5+1Man / 6Man / 6+Man / 7Man / 8Man+
  - Two-panel layout: KUBOTA SPEARS (top) + Opponent (bottom)
  - Area breakdown shows each team's own-ball throws
  - Thrower Ranking replaces Throw Direction
"""
import csv, glob, os, re, sqlite3, collections

# ── KUBOTA SPEARS season data (R1–R22, from DB) ───────────────────────────
SPEARS = {
    "name": "KUBOTA SPEARS",
    "overall": [312, 285],
    "delivery": [
        ("Off The Top",    105, 89),
        ("Catch & Drive",   99, 98),
        ("Catch & Pass",    71, 66),
        ("Catch & Run",     37, 32),
    ],
    "nums": {
        "Quick":   [23, 22],
        "4Man":    [51, 48],
        "4+1Man":  [2,  1],
        "5Man":    [25, 21],
        "5+1Man":  [103,89],
        "6Man":    [17, 16],
        "6+Man":   [68, 66],
        "7Man":    [1,   1],
        "8Man+":   [22, 21],
    },
    "areas": {
        "Own22":   [15,  14],
        "OwnHalf": [53,  47],
        "OppHalf": [147,132],
        "Opp22":   [97,  92],
    },
    "area_nums": {
        "Own22":   {"Quick":[6,6],"4Man":[7,7],"4+1Man":[1,0],"5+1Man":[1,1]},
        "OwnHalf": {"Quick":[11,11],"4Man":[11,9],"5Man":[2,2],"5+1Man":[24,20],"6Man":[3,3],"6+Man":[1,1],"8Man+":[1,1]},
        "OppHalf": {"Quick":[5,4],"4Man":[31,30],"5Man":[23,19],"5+1Man":[51,44],"6Man":[14,13],"6+Man":[8,7],"7Man":[1,1],"8Man+":[14,14]},
        "Opp22":   {"Quick":[1,1],"4Man":[2,2],"4+1Man":[1,1],"5+1Man":[27,24],"6+Man":[59,58],"8Man+":[7,6]},
    },
    "throwers": [
        ("Malcolm Marx",  171,157),
        ("Hayate Era",     65, 54),
        ("Rikuto Fukuda",  56, 54),
        ("Shaun Stevenson", 7,  7),
        ("Bernard Foley",   4,  4),
    ],
    "takes": [],        # populated at runtime from DB (see _load_spears_takes)
    "steals": [
        ("Akira Ieremia",  {"Middle":2,"Front":1,"15M+":1}),
        ("Merwe Olivier",  {"Front":3,"Middle":1}),
        ("David Bulbring", {"Middle":2,"Back":1}),
        ("Ruan Botha",     {"Front":2,"Middle":1}),
        ("Hayate Era",     {"Middle":2}),
        ("Tyler Paul",     {"Middle":1,"Front":1}),
    ],
}

# ── Per-opponent data ──────────────────────────────────────────────────────
TEAM_DATA = {
"BlackRams":{
 "name":"BlackRams Tokyo",
 "own":[291,239],
 "delivery":[("Off The Top",110,38),("Catch & Drive",84,29),("Catch & Pass",61,21),("Catch & Run",36,12)],
 "nums":{"Quick":[22,20],"4Man":[43,36],"4+1Man":[2,2],"5Man":[21,20],"5+1Man":[110,86],"6Man":[3,2],"6+Man":[35,29],"7Man":[32,26],"8Man+":[23,18]},
 "areas":{"Own22":[9,6],"OwnHalf":[70,61],"OppHalf":[127,107],"Opp22":[85,65]},
 "area_nums":{"Own22":{"Quick":[3,2],"4Man":[2,2],"5+1Man":[4,2]},"OwnHalf":{"Quick":[10,10],"4Man":[7,6],"4+1Man":[2,2],"5Man":[1,1],"5+1Man":[45,38],"6Man":[2,2],"6+Man":[1,1],"7Man":[2,1]},"OppHalf":{"Quick":[6,5],"4Man":[32,26],"5Man":[20,19],"5+1Man":[32,27],"6Man":[1,0],"6+Man":[3,3],"7Man":[26,22],"8Man+":[7,5]},"Opp22":{"Quick":[3,3],"4Man":[2,2],"5+1Man":[29,19],"6+Man":[31,25],"7Man":[4,3],"8Man+":[16,13]}},
 "throwers":[("Masashi Onishi",141,120),("Shin Ouchi",101,77),("Soonhong Lee",24,19),("Nic Souchon",8,7),("Isaac Lucas",7,6)],
 "takes":[("Reijiro Yamamoto",7,6),("Shu Yamamoto",4,4),("Michael Allardice",4,3),("Harrison Fox",4,4),("Shuhei Matsuhashi",2,2)],
 "steal_zones":{"Brodi McCurran":{"Front":1},"Michael Allardice":{"Back":1},"Reijiro Yamamoto":{"Middle":1}},
},
"BlueRevs":{
 "name":"Shizuoka BlueRevs",
 "own":[255,216],
 "delivery":[("Off The Top",97,38),("Catch & Drive",70,27),("Catch & Pass",58,23),("Catch & Run",30,12)],
 "nums":{"Quick":[14,14],"4Man":[50,38],"4+1Man":[6,3],"5Man":[29,25],"5+1Man":[80,69],"6Man":[9,8],"6+Man":[54,46],"7Man":[11,11],"8Man+":[2,2]},
 "areas":{"Own22":[14,11],"OwnHalf":[57,54],"OppHalf":[108,83],"Opp22":[76,68]},
 "area_nums":{"Own22":{"Quick":[1,1],"4Man":[11,8],"5Man":[1,1],"5+1Man":[1,1]},"OwnHalf":{"Quick":[10,10],"4Man":[13,11],"4+1Man":[2,2],"5Man":[12,11],"5+1Man":[13,13],"6Man":[3,3],"6+Man":[2,2],"7Man":[2,2]},"OppHalf":{"Quick":[3,3],"4Man":[23,16],"4+1Man":[4,1],"5Man":[13,10],"5+1Man":[39,29],"6Man":[5,5],"6+Man":[11,9],"7Man":[9,9],"8Man+":[1,1]},"Opp22":{"4Man":[3,3],"5Man":[3,3],"5+1Man":[27,26],"6Man":[1,0],"6+Man":[41,35],"8Man+":[1,1]}},
 "throwers":[("Takeshi Hino",151,128),("Shunsuke Sakuta",73,64),("Richmond Tongatama",13,8),("Sam Greene",3,3),("Siale Mahina",3,2)],
 "takes":[("Vueti Tupou",4,4),("Murray Douglas",3,3),("Kwagga Smith",3,3),("Justin Sangster",2,2),("Daniel Maiava",2,2)],
 "steal_zones":{},
},
"BraveLupus":{
 "name":"Toshiba Brave Lupus",
 "own":[264,216],
 "delivery":[("Off The Top",104,39),("Catch & Drive",75,28),("Catch & Pass",54,20),("Catch & Run",31,12)],
 "nums":{"Quick":[11,11],"4Man":[43,37],"4+1Man":[1,0],"5Man":[39,31],"5+1Man":[46,36],"6Man":[8,7],"6+Man":[28,25],"7Man":[84,68],"8Man+":[4,1]},
 "areas":{"Own22":[9,8],"OwnHalf":[59,47],"OppHalf":[120,98],"Opp22":[76,63]},
 "area_nums":{"Own22":{"Quick":[1,1],"4Man":[5,4],"5Man":[1,1],"5+1Man":[2,2]},"OwnHalf":{"Quick":[7,7],"4Man":[12,11],"4+1Man":[1,0],"5Man":[18,15],"5+1Man":[15,10],"6Man":[2,2],"7Man":[3,2],"8Man+":[1,0]},"OppHalf":{"Quick":[3,3],"4Man":[26,22],"5Man":[20,15],"5+1Man":[21,19],"6Man":[6,5],"7Man":[44,34]},"Opp22":{"5+1Man":[8,5],"6+Man":[28,25],"7Man":[37,32],"8Man+":[3,1]}},
 "throwers":[("Andrew Makalio",100,82),("Rinpei Sakaki",87,70),("Daigo Hashimoto",61,49),("Ken Hiyoshi",5,4),("Takuro Matsunaga",4,4)],
 "takes":[("Michael Stolberg",20,20),("Jacob Pierce",6,6),("Hiroki Yamamoto",6,6),("Michael Leitch",4,4),("Richie Mo'unga",2,2)],
 "steal_zones":{},
},
"D-Rocks":{
 "name":"Urayasu D-Rocks",
 "own":[255,200],
 "delivery":[("Off The Top",113,44),("Catch & Pass",68,27),("Catch & Drive",38,15),("Catch & Run",36,14)],
 "nums":{"Quick":[8,7],"4Man":[20,14],"4+1Man":[8,4],"5Man":[92,78],"5+1Man":[41,31],"6Man":[18,12],"6+Man":[42,33],"7Man":[13,9],"8Man+":[13,12]},
 "areas":{"Own22":[16,10],"OwnHalf":[60,45],"OppHalf":[110,86],"Opp22":[69,59]},
 "area_nums":{"Own22":{"Quick":[3,2],"4Man":[9,6],"4+1Man":[2,0],"5Man":[2,2]},"OwnHalf":{"Quick":[3,3],"4Man":[8,5],"4+1Man":[3,2],"5Man":[30,26],"5+1Man":[10,7],"6Man":[1,1],"6+Man":[4,1],"7Man":[1,0]},"OppHalf":{"Quick":[2,2],"4Man":[3,3],"4+1Man":[2,1],"5Man":[59,49],"5+1Man":[16,12],"6Man":[13,9],"6+Man":[4,1],"7Man":[8,6],"8Man+":[3,3]},"Opp22":{"4+1Man":[1,1],"5Man":[1,1],"5+1Man":[15,12],"6Man":[4,2],"6+Man":[34,31],"7Man":[4,3],"8Man+":[10,9]}},
 "throwers":[("Ryuji Fujimura",116,93),("Junichiro Matsushita",101,77),("Takashi Omoto",16,14),("Yang Jung Soo",9,4),("Shokei Kin",8,7)],
 "takes":[("Manaaki Selby-Rickit",6,6),("Steven Cummins",5,4),("Shin Takeuchi",4,4),("Yuzuki Sasaki",2,2),("Daishi Kojima",2,2)],
 "steal_zones":{"Steven Cummins":{"Front":1}},
},
"Dynaboars":{
 "name":"Mitsubishi Dynaboars",
 "own":[264,217],
 "delivery":[("Off The Top",96,36),("Catch & Drive",90,34),("Catch & Pass",52,20),("Catch & Run",26,10)],
 "nums":{"Quick":[6,6],"4Man":[38,32],"4+1Man":[18,16],"5Man":[35,26],"5+1Man":[86,67],"6Man":[5,5],"6+Man":[63,54],"7Man":[8,7],"8Man+":[5,4]},
 "areas":{"Own22":[17,15],"OwnHalf":[61,46],"OppHalf":[92,76],"Opp22":[94,80]},
 "area_nums":{"Own22":{"Quick":[5,5],"4Man":[9,7],"4+1Man":[1,1],"5Man":[1,1],"5+1Man":[1,1]},"OwnHalf":{"Quick":[1,1],"4Man":[12,10],"4+1Man":[5,4],"5Man":[4,4],"5+1Man":[32,21],"6Man":[1,1],"6+Man":[5,4],"7Man":[1,1]},"OppHalf":{"4Man":[17,15],"4+1Man":[11,10],"5Man":[29,21],"5+1Man":[20,18],"6Man":[4,4],"6+Man":[9,7],"7Man":[2,1]},"Opp22":{"4+1Man":[1,1],"5Man":[1,0],"5+1Man":[33,27],"6+Man":[49,43],"7Man":[5,5],"8Man+":[5,4]}},
 "throwers":[("Seunghyok Lee",149,125),("Yuki Miyazato",104,86),("Shoma Sagawa",10,5),("Shun Miyake",1,1)],
 "takes":[("Jose Seru",6,6),("Kohki Matsumoto",5,5),("Jackson Hemopo",4,4),("Gideon Koegelenberg",3,3),("Friedle Olivier",1,1)],
 "steal_zones":{},
},
"Eagles":{
 "name":"Yokohama Canon Eagles",
 "own":[247,192],
 "delivery":[("Off The Top",84,34),("Catch & Drive",73,30),("Catch & Pass",67,27),("Catch & Run",23,9)],
 "nums":{"Quick":[9,8],"4Man":[48,35],"5Man":[41,32],"5+1Man":[56,44],"6Man":[19,12],"6+Man":[45,36],"7Man":[23,21],"8Man+":[6,4]},
 "areas":{"Own22":[14,11],"OwnHalf":[55,44],"OppHalf":[108,79],"Opp22":[70,58]},
 "area_nums":{"Own22":{"Quick":[1,1],"4Man":[11,9],"5+1Man":[2,1]},"OwnHalf":{"Quick":[1,1],"4Man":[20,16],"5Man":[10,7],"5+1Man":[22,18],"6Man":[1,1],"7Man":[1,1]},"OppHalf":{"Quick":[7,6],"4Man":[17,10],"5Man":[31,25],"5+1Man":[22,15],"6Man":[15,11],"6+Man":[6,4],"7Man":[8,7],"8Man+":[2,1]},"Opp22":{"5+1Man":[10,10],"6Man":[3,0],"6+Man":[39,32],"7Man":[14,13],"8Man+":[4,3]}},
 "throwers":[("Shunta Nakamura",103,85),("Yusuke Niwai",65,48),("Liam Coltman",64,45),("Hayate Hiraishi",8,7),("Masayoshi Takezawa",2,2)],
 "takes":[("Daichi Akiyama",5,5),("Cormac Daly",4,4),("Billy Harmon",3,3),("Yusuke Kajimura",1,1)],
 "steal_zones":{},
},
"Heat":{
 "name":"Mie Honda Heat",
 "own":[264,229],
 "delivery":[("Catch & Drive",85,32),("Catch & Pass",81,31),("Catch & Run",40,15),("Off The Top",58,22)],
 "nums":{"Quick":[15,15],"4Man":[13,10],"4+1Man":[37,27],"5Man":[23,20],"5+1Man":[73,63],"6Man":[5,4],"6+Man":[58,56],"7Man":[19,15],"8Man+":[21,19]},
 "areas":{"Own22":[21,16],"OwnHalf":[51,46],"OppHalf":[106,88],"Opp22":[86,79]},
 "area_nums":{"Own22":{"Quick":[8,8],"4Man":[3,2],"4+1Man":[10,6]},"OwnHalf":{"Quick":[3,3],"4Man":[5,4],"4+1Man":[17,15],"5Man":[7,6],"5+1Man":[16,15],"6+Man":[1,1],"7Man":[2,2]},"OppHalf":{"Quick":[4,4],"4Man":[5,4],"4+1Man":[8,6],"5Man":[16,14],"5+1Man":[46,37],"6Man":[4,3],"6+Man":[9,8],"7Man":[11,9],"8Man+":[3,3]},"Opp22":{"4+1Man":[2,0],"5+1Man":[11,11],"6Man":[1,1],"6+Man":[48,47],"7Man":[6,4],"8Man+":[18,16]}},
 "throwers":[("Tevita Ikanivere",170,147),("Koki Hida",83,71),("Lomano Lemeki",5,5),("Rakuhei Yamashita",3,3)],
 "takes":[("Trevor Hosea",8,8),("Franco Mostert",4,4),("Janko Swanepoel",3,2),("Ryo Furuta",2,2),("Takuro Hojo",1,1)],
 "steal_zones":{"Janko Swanepoel":{"Front":1}},
},
"Steelers":{
 "name":"Kobelco Kobe Steelers",
 "own":[242,218],
 "delivery":[("Catch & Pass",79,33),("Catch & Drive",74,31),("Off The Top",72,30),("Catch & Run",17,7)],
 "nums":{"Quick":[17,16],"4Man":[4,2],"5Man":[35,30],"5+1Man":[60,53],"6Man":[22,21],"6+Man":[60,57],"7Man":[36,33],"8Man+":[8,6]},
 "areas":{"Own22":[13,9],"OwnHalf":[50,46],"OppHalf":[104,92],"Opp22":[75,71]},
 "area_nums":{"Own22":{"Quick":[2,1],"5Man":[1,0],"5+1Man":[9,7],"6Man":[1,1]},"OwnHalf":{"Quick":[8,8],"4Man":[1,1],"5Man":[7,5],"5+1Man":[25,24],"6Man":[7,7],"7Man":[2,1]},"OppHalf":{"Quick":[7,7],"4Man":[3,1],"5Man":[27,25],"5+1Man":[18,14],"6Man":[13,12],"6+Man":[9,8],"7Man":[25,24],"8Man+":[2,1]},"Opp22":{"5+1Man":[8,8],"6Man":[1,1],"6+Man":[51,49],"7Man":[9,8],"8Man+":[6,5]}},
 "throwers":[("Ash Dixon",106,98),("Takuya Kitade",80,70),("Sione Mau",31,27),("Kenta Matsuoka",11,9),("Shunsuke Uenobou",4,4)],
 "takes":[("Gerard Cowley-Tuioti",19,16),("Brodie Retallick",17,15),("Tiennan Costley",5,5),("Takuma Motohashi",1,1),("Seungsin Lee",1,1)],
 "steal_zones":{"Gerard Cowley-Tuioti":{"Middle":2,"Back":1},"Brodie Retallick":{"Middle":1,"Front":1}},
},
"Sungoliath":{
 "name":"Tokyo Sungoliath",
 "own":[265,244],
 "delivery":[("Off The Top",151,57),("Catch & Drive",55,21),("Catch & Run",34,13),("Catch & Pass",25,9)],
 "nums":{"Quick":[13,13],"4Man":[83,78],"5Man":[39,37],"5+1Man":[48,43],"6Man":[4,3],"6+Man":[34,30],"7Man":[36,34],"8Man+":[8,6]},
 "areas":{"Own22":[11,10],"OwnHalf":[52,51],"OppHalf":[115,104],"Opp22":[87,79]},
 "area_nums":{"Own22":{"4Man":[11,10]},"OwnHalf":{"Quick":[9,9],"4Man":[23,23],"5Man":[10,9],"5+1Man":[8,8],"7Man":[2,2]},"OppHalf":{"Quick":[4,4],"4Man":[39,35],"5Man":[29,28],"5+1Man":[20,18],"6Man":[3,2],"6+Man":[1,1],"7Man":[16,15],"8Man+":[3,1]},"Opp22":{"4Man":[10,10],"5+1Man":[20,17],"6Man":[1,1],"6+Man":[33,29],"7Man":[18,17],"8Man+":[5,5]}},
 "throwers":[("Kosuke Horikoshi",128,118),("Shodai Hirao",61,58),("Tatsuya Miyazaki",37,35),("Kienori Go",26,20),("Mikiya Takamoto",4,4)],
 "takes":[("Harry Hockings",10,10),("Kanji Shimokawa",9,8),("George Hammond",7,7),("Ryuga Hashimoto",2,2)],
 "steal_zones":{"Kanji Shimokawa":{"Back":1}},
},
"Verblitz":{
 "name":"Toyota Verblitz",
 "own":[245,217],
 "delivery":[("Off The Top",104,42),("Catch & Drive",83,34),("Catch & Pass",47,19),("Catch & Run",11,4)],
 "nums":{"Quick":[7,7],"4Man":[12,10],"5Man":[50,46],"5+1Man":[80,66],"6Man":[17,17],"6+Man":[53,46],"7Man":[15,15],"8Man+":[11,10]},
 "areas":{"Own22":[8,7],"OwnHalf":[57,52],"OppHalf":[95,85],"Opp22":[85,73]},
 "area_nums":{"Own22":{"Quick":[1,1],"4Man":[3,3],"5+1Man":[4,3]},"OwnHalf":{"Quick":[4,4],"4Man":[5,4],"5Man":[14,13],"5+1Man":[27,24],"6Man":[5,5],"6+Man":[1,1],"7Man":[1,1]},"OppHalf":{"Quick":[2,2],"4Man":[4,3],"5Man":[35,32],"5+1Man":[21,17],"6Man":[10,10],"6+Man":[5,4],"7Man":[14,14],"8Man+":[4,3]},"Opp22":{"5Man":[1,1],"5+1Man":[28,22],"6Man":[2,2],"6+Man":[47,41],"8Man+":[7,7]}},
 "throwers":[("Yoshikatsu Hikosaka",154,135),("Schalk Erasmus",53,48),("Ryusei Kato",28,24),("Shintaro Fukuzawa",3,3),("Mark Tele'a",2,2)],
 "takes":[("Lourens Erasmus",9,9),("Keito Aoki",4,4),("Josh Dickson",4,3),("Isaiah Mapusua",3,3),("Blair Ryall",3,3)],
 "steal_zones":{"Josh Dickson":{"Front":1}},
},
"WildKnights":{
 "name":"Saitama Wild Knights",
 "own":[261,220],
 "delivery":[("Off The Top",118,45),("Catch & Drive",87,33),("Catch & Pass",28,11),("Catch & Run",27,10)],
 "nums":{"Quick":[13,12],"4Man":[23,19],"4+1Man":[5,5],"5Man":[46,36],"5+1Man":[57,43],"6Man":[37,33],"6+Man":[59,53],"7Man":[18,16],"8Man+":[3,3]},
 "areas":{"Own22":[14,11],"OwnHalf":[40,36],"OppHalf":[106,87],"Opp22":[101,86]},
 "area_nums":{"Own22":{"Quick":[5,4],"4Man":[7,5],"4+1Man":[1,1],"5Man":[1,1]},"OwnHalf":{"Quick":[7,7],"4Man":[9,9],"4+1Man":[1,1],"5Man":[9,7],"5+1Man":[10,9],"6Man":[3,2],"6+Man":[1,1]},"OppHalf":{"4Man":[7,5],"4+1Man":[3,3],"5Man":[36,28],"5+1Man":[18,13],"6Man":[29,27],"6+Man":[1,1],"7Man":[12,10]},"Opp22":{"Quick":[1,1],"5+1Man":[29,21],"6Man":[5,4],"6+Man":[57,51],"7Man":[6,6],"8Man+":[3,3]}},
 "throwers":[("Atsushi Sakate",170,142),("Kenji Sato",79,66),("Koki Takeyama",4,4),("Kazuma Shimane",3,3),("Lachlan Boshier",2,2)],
 "takes":[("Liam Mitchell",11,10),("Jack Cornelsen",5,4),("Esei Haangana",5,5),("Ryuji Noguchi",1,1)],
 "steal_zones":{"Jack Cornelsen":{"Middle":1},"Liam Mitchell":{"Middle":1}},
},
}

BIOUT_DIR = "/Users/ktachikawa/Desktop/BIoutput"
DB_PATH   = os.path.join(BIOUT_DIR, "rugby.db")
CSV_DIR   = "/Users/ktachikawa/Desktop/kubota-spears-analytics"

# ── Zone breakdown data (from DB) ─────────────────────────────────────────
# Lineout Take: ActionTypeName = "Lineout Win Front" → zone "Front" etc.
TAKE_ZONES = {
    # Spears catchers — populated at runtime from DB (see _load_spears_takes)
    "Ruan Botha":     {},
    "David Bulbring": {},
    "Faulua Makisi":  {},
    "Akira Ieremia":  {},
    "Merwe Olivier":  {},
    "Tyler Paul":     {},
    # BlackRams
    "Harrison Fox":          {"Front":4},
    "Reijiro Yamamoto":      {},
    "Michael Allardice":     {},
    # BlueRevs
    "Murray Douglas":  {"Front":1,"Middle":2},
    "Kwagga Smith":    {"Front":3},
    "Justin Sangster": {"Front":2},
    "Daniel Maiava":   {"Front":2},
    # BraveLupus
    "Michael Stolberg":  {"Front":5,"Middle":12,"Back":2,"15M+":1},
    "Jacob Pierce":      {"Front":5,"Back":1},
    "Hiroki Yamamoto":   {"Front":4,"Middle":2},
    "Michael Leitch":    {"Front":2,"Back":1,"15M+":1},
    # D-Rocks
    "Manaaki Selby-Rickit": {"Front":3,"Middle":3},
    "Steven Cummins":        {},
    "Shin Takeuchi":         {"Front":4},
    # Dynaboars
    "Jose Seru":            {"Front":6},
    "Kohki Matsumoto":      {"Front":2,"Middle":2,"Back":1},
    "Jackson Hemopo":       {"Front":2,"Back":2},
    "Gideon Koegelenberg":  {"Middle":3},
    # Eagles
    "Daichi Akiyama":  {"Front":2,"Middle":1,"Back":2},
    "Cormac Daly":     {"Front":2,"Middle":2},
    "Billy Harmon":    {"Front":2,"15M+":1},
    # Heat
    "Trevor Hosea":    {"Front":1,"Middle":4},
    "Franco Mostert":  {"Middle":4},
    "Janko Swanepoel": {"Front":2,"Middle":1},
    "Ryo Furuta":      {"Front":2},
    # Steelers
    "Gerard Cowley-Tuioti": {"Front":2,"Middle":15,"Back":2},
    "Brodie Retallick":     {"Front":13,"Middle":3,"Back":1},
    "Tiennan Costley":      {},
    # Sungoliath
    "Harry Hockings":   {"Front":3,"Middle":7},
    "Kanji Shimokawa":  {"Front":8,"Back":1},
    "George Hammond":   {"Front":5,"Middle":2},
    "Ryuga Hashimoto":  {"Front":2},
    # Verblitz
    "Lourens Erasmus":  {"Front":2,"Middle":7},
    "Keito Aoki":       {"Middle":3,"Back":1},
    "Josh Dickson":     {"Front":1,"Middle":3},
    "Isaiah Mapusua":   {"Front":2,"Back":1},
    "Blair Ryall":      {"Front":3},
    # WildKnights
    "Liam Mitchell":    {"Front":1,"Middle":7,"Back":3},
    "Jack Cornelsen":   {"Middle":4,"Back":1},
    "Esei Haangana":    {"Front":3,"Middle":1,"Back":1},
}

# Lineout Throw: ActionTypeName = "Throw Front" → direction "Front" etc.
THROW_DIRS = {
    # Spears throwers
    "Malcolm Marx":    {"Front":80,"Middle":68,"Back":13,"15M+":10},
    "Hayate Era":      {"Front":18,"Middle":34,"Back":8,"15M+":5},
    "Rikuto Fukuda":   {"Front":28,"Middle":17,"Back":7,"15M+":4},
    "Shaun Stevenson": {"Quick":7},
    "Bernard Foley":   {"Quick":4},
    # BlackRams
    "Masashi Onishi":  {"Front":4,"Middle":1,"Back":2},
    "Shin Ouchi":      {"Front":10,"Middle":6,"Back":5,"15M+":2},
    "Soonhong Lee":    {},
    "Nic Souchon":     {"Front":1,"Middle":1},
    "Isaac Lucas":     {"Quick":1},
    # BlueRevs
    "Takeshi Hino":      {"Front":8,"Middle":3,"Back":2},
    "Shunsuke Sakuta":   {"Front":5,"Middle":3},
    "Richmond Tongatama":{},
    # BraveLupus
    "Andrew Makalio":    {"Front":15,"Middle":17,"Back":5,"15M+":3},
    "Rinpei Sakaki":     {"Front":2,"Middle":1,"Back":1},
    "Daigo Hashimoto":   {},
    "Takuro Matsunaga":  {"Quick":3},
    # D-Rocks
    "Ryuji Fujimura":        {"Front":7,"Middle":5,"Back":2},
    "Junichiro Matsushita":  {"Front":6,"Middle":3,"Back":1},
    "Takashi Omoto":         {},
    "Shokei Kin":            {"Back":1,"15M+":1},
    # Dynaboars
    "Seunghyok Lee":  {"Front":9,"Middle":6,"Back":3,"15M+":1},
    "Yuki Miyazato":  {},
    "Shoma Sagawa":   {"Front":3,"Middle":1},
    # Eagles
    "Shunta Nakamura": {"Front":2,"Middle":3,"Back":1,"15M+":2},
    "Yusuke Niwai":    {"Front":4,"Back":1},
    "Liam Coltman":    {},
    # Heat
    "Tevita Ikanivere":  {"Front":4,"Middle":9,"Back":1},
    "Koki Hida":         {"Front":4,"Middle":3},
    # Steelers
    "Ash Dixon":      {"Front":12,"Middle":12,"Back":3,"15M+":1},
    "Takuya Kitade":  {"Front":4,"Middle":3},
    "Sione Mau":      {},
    "Kenta Matsuoka": {"Front":4,"Middle":2,"Back":2,"15M+":1},
    # Sungoliath
    "Kosuke Horikoshi": {"Front":11,"Middle":4},
    "Shodai Hirao":     {"Front":3,"Middle":4},
    "Tatsuya Miyazaki": {"Front":4,"Middle":3},
    "Kienori Go":       {},
    # Verblitz
    "Yoshikatsu Hikosaka": {"Front":3,"Middle":6,"Back":1},
    "Schalk Erasmus":      {"Front":6,"Middle":8,"Back":1},
    "Ryusei Kato":         {"Front":2,"Middle":1},
    # WildKnights
    "Atsushi Sakate": {"Front":5,"Middle":12,"Back":2},
    "Kenji Sato":     {"Back":3},
}

ZONE_ORDER  = ["Front","Middle","Back","15M+","Quick"]
ZONE_COLORS = {
    "Front":"#2563EB","Middle":"#16A34A","Back":"#D97706",
    "15M+":"#7C3AED","Quick":"#6B7280",
}

def stacked_row(rank, name, total, max_tot, success_pct, zones):
    """Single stacked colored bar row. zones={zone:count,...}. success_pct=win% or steal%."""
    bw   = pct(total, max_tot)
    c    = wc(success_pct)
    z_total = sum(zones.values()) or 1
    segs = legend = ""
    for z in ZONE_ORDER:
        cnt = zones.get(z, 0)
        if cnt == 0:
            continue
        zc   = ZONE_COLORS[z]
        zpct = round(100 * cnt / z_total)
        segs   += f'<div style="flex:{cnt};background:{zc}" title="{z}: {cnt}"></div>'
        legend += (f'<span style="display:inline-flex;align-items:center;gap:1px;margin-right:3px">'
                   f'<span style="width:5px;height:5px;border-radius:1px;background:{zc};flex-shrink:0"></span>'
                   f'<span style="font-size:5.5px;color:{zc};font-weight:700">{z}&nbsp;{cnt}</span>'
                   f'</span>')
    bar_inner = (f'<div style="width:{bw}%;height:100%;display:flex;border-radius:2px;overflow:hidden">'
                 f'{segs}</div>') if segs else f'<div style="width:{bw}%;height:100%;background:#CED4DA;border-radius:2px"></div>'
    return (f'<div style="display:flex;align-items:center;gap:4px;margin-bottom:4px">'
            f'<span style="font-size:7px;color:#888;width:10px;text-align:right;flex-shrink:0">{rank}</span>'
            f'<span style="font-size:7.5px;font-weight:800;color:#222;width:90px;flex-shrink:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="{name}">{name}</span>'
            f'<div style="flex:1;height:11px;background:#F1F3F5;border-radius:2px;overflow:hidden">{bar_inner}</div>'
            f'<span style="font-size:8px;font-weight:800;color:{c};width:28px;text-align:right;flex-shrink:0">{success_pct}%</span>'
            f'<span style="font-size:7px;color:#888;width:18px;text-align:right;flex-shrink:0">{total}</span>'
            f'</div>'
            f'<div style="display:flex;flex-wrap:wrap;margin:0 0 3px 106px">{legend}</div>')


DLVR_COLORS = {
    "Off The Top":"#14213D","Catch & Drive":"#2563EB",
    "Catch & Pass":"#7C3AED","Catch & Run":"#D97706",
    "Catch and Drive":"#2563EB","Catch and Pass":"#7C3AED","Catch and Run":"#D97706",
}
NUM_ORDER      = ["Quick","4Man","4+1Man","5Man","5+1Man","6Man","6+Man","7Man","8Man+"]
NUM_AREA_ORDER = ["Quick","4Man","4+1Man","5Man","5+1Man","6Man","6+Man","7Man","8Man+"]
AREA_ORDER     = ["Own22","OwnHalf","OppHalf","Opp22"]
AREA_LABEL     = {"Own22":"OWN 22","OwnHalf":"OWN HALF","OppHalf":"OPP HALF","Opp22":"OPP 22"}
AREA_COLOR     = {"Own22":"#16A34A","OwnHalf":"#2563EB","OppHalf":"#D97706","Opp22":"#DC2626"}

def pct(n, d): return round(100*n/d) if d else 0
def wc(p): return "#16A34A" if p>=90 else "#2563EB" if p>=80 else "#D97706"

# ── DB team name mapping (TEAM_DATA abbr → exact DB team_name string) ─────
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

# ── Load all lineout take data from DB in one pass ─────────────────────────
def _load_all_takes_from_db():
    """
    Single DB query → per-team takes and zone breakdown.
    For Spears: all 21 matches (full season).
    For opponents: vs-Spears matches only (1–3 matches each).
    Returns {db_team_name: {"takes": [...], "zones": {...}}}
    takes  = [(player, total_take_rows, won_count), ...] sorted by won desc
    total  = Lineout Win + Lineout Steal rows for that player.
    won    = Lineout Win rows only (own-ball catches).
    zones  = {player: {zone: won_count, ...}} (own-ball wins only).
    """
    ZONE_MAP = {
        "Lineout Win Front":  "Front",
        "Lineout Win Middle": "Middle",
        "Lineout Win Back":   "Back",
        "Lineout Win Quick":  "Quick",
        "Lineout Win 15m+":   "15M+",
    }
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT team_name, player_name, action_type_name, COUNT(*) AS cnt
            FROM events
            WHERE action_name = 'Lineout Take'
            GROUP BY team_name, player_name, action_type_name
        """).fetchall()
        conn.close()
    except Exception as e:
        print("[WARN] DB read failed (%s); using empty takes." % e)
        return {}

    won_cnt   = collections.defaultdict(collections.Counter)
    total_cnt = collections.defaultdict(collections.Counter)
    zone_cnt  = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))

    for r in rows:
        tn  = r["team_name"]
        p   = r["player_name"]
        atn = r["action_type_name"]
        cnt = r["cnt"]
        total_cnt[tn][p] += cnt
        if "Lineout Win" in atn:
            won_cnt[tn][p] += cnt
            zone = ZONE_MAP.get(atn, atn.replace("Lineout Win ", ""))
            zone_cnt[tn][p][zone] += cnt

    result = {}
    for tn in total_cnt:
        takes = sorted(
            [(p, total_cnt[tn][p], won_cnt[tn].get(p, 0)) for p in won_cnt[tn]],
            key=lambda x: -x[2],
        )
        zones = {p: dict(z) for p, z in zone_cnt[tn].items()}
        result[tn] = {"takes": takes, "zones": zones}
    return result


_all_db_takes = _load_all_takes_from_db()


# ── Load Lineout Throw win stats for OPP Ball Won Rate sections ────────────
def _load_lo_stats_from_db():
    """
    Returns two dicts keyed by DB team name:
      opp_stats  — opponent's LO throws in their games vs Kubota (upper section)
      kub_stats  — Kubota's LO throws in games vs each opponent (lower section)
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        opp_rows = conn.execute("""
            SELECT team_name,
                   COUNT(*) AS total,
                   SUM(CASE WHEN action_result_name LIKE 'Won%' THEN 1 ELSE 0 END) AS won
            FROM events
            WHERE action_name = 'Lineout Throw'
              AND team_name != 'Kubota Spears'
            GROUP BY team_name
        """).fetchall()
        opp_stats = {r["team_name"]: (r["total"], r["won"]) for r in opp_rows}

        kub_rows = conn.execute("""
            SELECT m.opponent_name,
                   COUNT(*) AS total,
                   SUM(CASE WHEN e.action_result_name LIKE 'Won%' THEN 1 ELSE 0 END) AS won
            FROM events e
            JOIN matches m ON e.fxid = m.fxid
            WHERE e.action_name = 'Lineout Throw'
              AND e.team_name = 'Kubota Spears'
            GROUP BY m.opponent_name
        """).fetchall()
        kub_stats = {r["opponent_name"]: (r["total"], r["won"]) for r in kub_rows}
        conn.close()
        return opp_stats, kub_stats
    except Exception as e:
        print(f"[WARN] LO throw stats load failed: {e}")
        return {}, {}


_OPP_LO_VS_KUBOTA, _KUBOTA_LO_VS_OPP = _load_lo_stats_from_db()

# ── Apply DB data to SPEARS (DB has all 21 Spears games) ──────────────────
_sp = _all_db_takes.get("Kubota Spears", {})
if _sp.get("takes"):
    SPEARS["takes"] = _sp["takes"]
TAKE_ZONES.update(_sp.get("zones", {}))


# ── Load opponent takes from full-season CSVs (all league games, not Spears-only) ─
def _load_opp_takes_from_csvs():
    """
    Read all BI CSVs from CSV_DIR to get every team's full-season take data.
    Kubota Spears is skipped (already loaded from DB above).
    Returns {team_name: {"takes": [(player, total, won), ...], "zones": {player: {zone: n}}}}
    """
    _ZONE_MAP = {
        "Lineout Win Front":  "Front",
        "Lineout Win Middle": "Middle",
        "Lineout Win Back":   "Back",
        "Lineout Win Quick":  "Quick",
        "Lineout Win 15m+":   "15M+",
    }
    won_cnt   = collections.defaultdict(collections.Counter)
    total_cnt = collections.defaultdict(collections.Counter)
    zone_cnt  = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))

    csv_files = glob.glob(os.path.join(CSV_DIR, "*.csv"))
    if not csv_files:
        print(f"[WARN] No CSVs found in {CSV_DIR}; opponent takes unchanged.")
        return {}

    for fpath in sorted(csv_files):
        try:
            with open(fpath, encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get("actionName") != "Lineout Take":
                        continue
                    tn = row.get("teamName", "")
                    if tn == "Kubota Spears":
                        continue
                    p   = row.get("playerName", "")
                    atn = row.get("ActionTypeName", "")
                    total_cnt[tn][p] += 1
                    if atn.startswith("Lineout Win"):
                        won_cnt[tn][p] += 1
                        zone = _ZONE_MAP.get(atn, atn.replace("Lineout Win ", ""))
                        zone_cnt[tn][p][zone] += 1
        except Exception as e:
            print(f"[WARN] Skipping {os.path.basename(fpath)}: {e}")
            continue

    result = {}
    for tn in total_cnt:
        takes = sorted(
            [(p, total_cnt[tn][p], won_cnt[tn].get(p, 0)) for p in total_cnt[tn]],
            key=lambda x: -x[1],
        )
        zones = {p: dict(z) for p, z in zone_cnt[tn].items()}
        result[tn] = {"takes": takes, "zones": zones}
    return result


_csv_opp_takes = _load_opp_takes_from_csvs()

# ── Apply CSV data to all opponent teams ───────────────────────────────────
for _abbr, _db_name in _DB_TEAM_NAME.items():
    _td = _csv_opp_takes.get(_db_name, {})
    if _td.get("takes"):
        TEAM_DATA[_abbr]["takes"] = _td["takes"]
    TAKE_ZONES.update(_td.get("zones", {}))


# ── Delivery Type card ─────────────────────────────────────────────────────
def delivery_col(team):
    dlv  = team["delivery"]
    total = sum(x[1] for x in dlv)
    rows  = ""
    for name, cnt, _ in dlv:
        p = pct(cnt, total)
        c = DLVR_COLORS.get(name, "#6B7280")
        rows += (f'<div style="margin-bottom:5px">'
                 f'<div style="display:flex;justify-content:space-between;margin-bottom:1px">'
                 f'<span style="font-size:8px;color:#222;font-weight:700">{name}</span>'
                 f'<span style="font-size:8px;color:#444">{cnt}'
                 f'<span style="color:#888;font-size:7px"> ({p}%)</span></span>'
                 f'</div><div style="height:9px;background:#F1F3F5;border-radius:2px;overflow:hidden">'
                 f'<div style="width:{p}%;height:100%;background:{c};border-radius:2px"></div>'
                 f'</div></div>')
    return (f'<div style="background:#fff;border:1px solid #DEE2E6;border-radius:6px;overflow:hidden">'
            f'<div style="background:#F8F9FA;padding:4px 8px;border-bottom:1px solid #DEE2E6">'
            f'<span style="font-size:8.5px;font-weight:800;color:#14213D;text-transform:uppercase;letter-spacing:.05em">Delivery Type</span></div>'
            f'<div style="padding:8px 10px">{rows}</div></div>')


# ── Won/Lost card (own ball + opp ball won rate) ───────────────────────────
def winloss_col(team, opp_ball=None):
    tot, won = team.get("overall") or team.get("own")
    lost = tot - won
    wp   = pct(won, tot)
    lp   = 100 - wp

    def wl_block(lbl, w, tot_, won_, lp_):
        lost_ = tot_ - won_
        return (f'<div style="padding:7px 10px;border-top:1px solid #F1F3F5">'
                f'<div style="font-size:6.5px;font-weight:700;color:#888;text-transform:uppercase;letter-spacing:.06em;margin-bottom:3px">{lbl}</div>'
                f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:3px">'
                f'<span style="font-family:Oswald,sans-serif;font-size:21px;font-weight:700;color:{wc(w)}">{w}%</span>'
                f'<div style="text-align:right">'
                f'<div style="font-size:9px;font-weight:700;color:#1D4ED8">{won_} Won</div>'
                f'<div style="font-size:9px;font-weight:700;color:#DC2626">{lost_} Lost</div>'
                f'<div style="font-size:7px;color:#888">n={tot_}</div>'
                f'</div></div>'
                f'<div style="height:11px;display:flex;border-radius:3px;overflow:hidden">'
                f'<div style="width:{w}%;background:#1D4ED8"></div>'
                f'<div style="width:{lp_}%;background:#DC2626"></div>'
                f'</div></div>')

    own_block = wl_block("Own Ball", wp, tot, won, lp)

    if opp_ball:
        ob_tot, ob_won = opp_ball
        ob_wp  = pct(ob_won, ob_tot)
        ob_lp  = 100 - ob_wp
        opp_block = wl_block("OPP Ball Won Rate", ob_wp, ob_tot, ob_won, ob_lp)
    else:
        opp_block = ""

    return (f'<div style="background:#fff;border:1px solid #DEE2E6;border-radius:6px;overflow:hidden">'
            f'<div style="background:#F8F9FA;padding:4px 8px;border-bottom:1px solid #DEE2E6">'
            f'<span style="font-size:8.5px;font-weight:800;color:#14213D;text-transform:uppercase;letter-spacing:.05em">Won / Lost</span></div>'
            + own_block + opp_block + f'</div>')


# ── Numbers stacked charts ─────────────────────────────────────────────────
def num_bars_html(nums_dict, max_tot, perspective="own"):
    bars = ""
    for cat in NUM_ORDER:
        if cat not in nums_dict:
            continue
        tot, won = nums_dict[cat]
        if tot == 0:
            continue
        if perspective == "def":
            steal  = tot - won
            wp     = pct(steal, tot)
            c_won, c_lost = steal, won
        else:
            wp     = pct(won, tot)
            c_won, c_lost = won, tot - won
        c      = wc(wp)
        bar_h  = max(5, round(85 * tot / max(max_tot, 1)))
        won_h  = round(bar_h * c_won / tot) if tot else 0
        lost_h = bar_h - won_h
        bars += (f'<div style="flex:1;min-width:0;display:flex;flex-direction:column;align-items:center">'
                 f'<div style="font-size:7px;font-weight:700;color:{c};line-height:1.1">{wp}%</div>'
                 f'<div style="width:100%;height:85px;display:flex;flex-direction:column;justify-content:flex-end">'
                 f'<div style="width:88%;margin:0 auto;height:{bar_h}px;border-radius:3px 3px 0 0;overflow:hidden;display:flex;flex-direction:column">'
                 f'<div style="flex:{lost_h};background:#DC2626"></div>'
                 f'<div style="flex:{won_h};background:#1D4ED8"></div>'
                 f'</div></div>'
                 f'<div style="font-size:6px;color:#222;font-weight:700;text-align:center;line-height:1.2;margin-top:2px">{cat}</div>'
                 f'<div style="font-size:6px;color:#888;line-height:1">{tot}</div>'
                 f'</div>')
    return bars

def numbers_col(own_nums, opp_nums_raw, label):
    own_max = max((v[0] for v in own_nums.values()), default=1)
    opp_max = max((v[0] for v in opp_nums_raw.values()), default=1)
    own_bars = num_bars_html(own_nums,    own_max, "own")
    opp_bars = num_bars_html(opp_nums_raw, opp_max, "own")

    def card(title, sub, bars):
        return (f'<div style="background:#fff;border:1px solid #DEE2E6;border-radius:6px;overflow:hidden;margin-bottom:6px">'
                f'<div style="background:#F8F9FA;padding:3px 8px;border-bottom:1px solid #DEE2E6;display:flex;align-items:baseline;gap:6px">'
                f'<span style="font-size:8.5px;font-weight:800;color:#14213D;text-transform:uppercase;letter-spacing:.05em">{title}</span>'
                f'<span style="font-size:7px;color:#888">{sub}</span></div>'
                f'<div style="padding:5px 6px 4px;display:flex;gap:2px;align-items:flex-end">{bars}</div>'
                f'</div>')

    return card("OWN NUMBERS", f"{label} — blue=Won / red=Lost", own_bars) + \
           card("OPP Numbers Success %", "blue=Won / red=Lost", opp_bars)


# ── Area breakdown ──────────────────────────────────────────────────────────
def area_grid(team, team_label):
    cols = ""
    for ak in AREA_ORDER:
        a = team.get("areas", {}).get(ak)
        if not a:
            continue
        tot, won = a
        lost = tot - won
        wp   = pct(won, tot)
        lp   = 100 - wp
        c    = AREA_COLOR[ak]
        sub_nums = team.get("area_nums", {}).get(ak, {})

        num_rows = ""
        if sub_nums:
            an_max = max((v[0] for v in sub_nums.values()), default=1)
            for cat in NUM_AREA_ORDER:
                if cat not in sub_nums:
                    continue
                nt, nw = sub_nums[cat]
                nwp = pct(nw, nt)
                nc  = wc(nwp)
                bw  = max(4, round(90 * nt / an_max))
                num_rows += (
                    f'<div style="display:flex;align-items:center;gap:2px;margin-bottom:1px">'
                    f'<span style="font-size:6.5px;color:#222;width:28px;flex-shrink:0;font-weight:800">{cat}</span>'
                    f'<div style="flex:1;height:7px;background:#F1F3F5;border-radius:2px;overflow:hidden">'
                    f'<div style="width:{bw}%;height:100%;background:{nc};opacity:.85"></div></div>'
                    f'<span style="font-size:6.5px;font-weight:800;color:#222;width:24px;text-align:right">{nwp}%</span>'
                    f'<span style="font-size:6px;color:#888;width:14px;text-align:right">{nt}</span>'
                    f'</div>')

        cols += (
            f'<div style="background:#fff;border:1px solid #DEE2E6;border-radius:6px;overflow:hidden">'
            f'<div style="background:{c}15;padding:3px 8px;border-bottom:1px solid {c}25;border-left:3px solid {c}">'
            f'<span style="font-size:8px;font-weight:800;color:{c}">{AREA_LABEL[ak]}</span>'
            f'<span style="font-size:7px;color:#888;margin-left:4px">{tot} throws</span></div>'
            f'<div style="padding:6px 8px">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:3px">'
            f'<span style="font-family:Oswald,sans-serif;font-size:20px;font-weight:700;color:{wc(wp)}">{wp}%</span>'
            f'<span style="font-size:8px;font-weight:700;color:#222">{won}W / {lost}L</span></div>'
            f'<div style="height:7px;display:flex;border-radius:3px;overflow:hidden;margin-bottom:5px">'
            f'<div style="width:{wp}%;background:#1D4ED8"></div>'
            f'<div style="width:{lp}%;background:#DC2626"></div></div>'
            f'<div style="border-top:1px dashed #E9ECEF;padding-top:4px">{num_rows}</div>'
            f'</div></div>')

    return (f'<div style="margin-bottom:10px">'
            f'<div style="font-size:8.5px;font-weight:800;color:#222;text-transform:uppercase;letter-spacing:.06em;margin-bottom:5px">'
            f'Area Breakdown — {team_label} Own Ball</div>'
            f'<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px">{cols}</div>'
            f'</div>')


# ── Take Ranking card ───────────────────────────────────────────────────────
def take_ranking_card(team, label):
    takes = team.get("takes", [])
    if not takes:
        return f'<div style="background:#fff;border:1px solid #DEE2E6;border-radius:6px;padding:12px;color:#888;font-size:8px">No take data</div>'
    max_tot = takes[0][1] if takes else 1
    rows = ""
    for i, (name, tot, won) in enumerate(takes[:5], 1):
        wp    = pct(won, tot)
        zones = {k: v for k, v in TAKE_ZONES.get(name, {}).items() if v > 0}
        rows += stacked_row(i, name, tot, max_tot, wp, zones)
    return (f'<div style="background:#fff;border:1px solid #DEE2E6;border-radius:6px;overflow:hidden">'
            f'<div style="background:#F8F9FA;padding:4px 10px;border-bottom:1px solid #DEE2E6">'
            f'<span style="font-size:8.5px;font-weight:800;color:#14213D;text-transform:uppercase;letter-spacing:.05em">&#127944; Take Ranking</span>'
            f'<span style="font-size:7px;color:#888;margin-left:6px">{label} catchers (25-26)</span></div>'
            f'<div style="padding:8px 10px">{rows}</div></div>')


# ── Steal Ranking card ──────────────────────────────────────────────────────
def steal_ranking_card(team, label):
    steals_raw = team.get("steals") or team.get("steal_zones") or {}
    if isinstance(steals_raw, list):
        entries = [(name, zones) for name, zones in steals_raw if sum(zones.values()) > 0]
    else:
        entries = [(name, zones) for name, zones in steals_raw.items() if sum(zones.values()) > 0]
    if not entries:
        return (f'<div style="background:#fff;border:1px solid #DEE2E6;border-radius:6px;overflow:hidden">'
                f'<div style="background:#F8F9FA;padding:4px 10px;border-bottom:1px solid #DEE2E6">'
                f'<span style="font-size:8.5px;font-weight:800;color:#14213D;text-transform:uppercase;letter-spacing:.05em">&#128282; Steal Ranking</span>'
                f'<span style="font-size:7px;color:#888;margin-left:6px">{label} (25-26)</span></div>'
                f'<div style="padding:8px 10px;font-size:7.5px;color:#888">No steals recorded</div></div>')
    entries.sort(key=lambda x: sum(x[1].values()), reverse=True)
    max_tot = sum(entries[0][1].values())
    rows = ""
    for i, (name, zones) in enumerate(entries[:5], 1):
        tot = sum(zones.values())
        rows += stacked_row(i, name, tot, max_tot, 100, zones)
    return (f'<div style="background:#fff;border:1px solid #DEE2E6;border-radius:6px;overflow:hidden">'
            f'<div style="background:#F8F9FA;padding:4px 10px;border-bottom:1px solid #DEE2E6">'
            f'<span style="font-size:8.5px;font-weight:800;color:#14213D;text-transform:uppercase;letter-spacing:.05em">&#128282; Steal Ranking</span>'
            f'<span style="font-size:7px;color:#888;margin-left:6px">{label} (25-26)</span></div>'
            f'<div style="padding:8px 10px">{rows}</div></div>')


# ── Thrower Ranking card ────────────────────────────────────────────────────
def thrower_ranking_card(team, label):
    throwers = team.get("throwers", [])
    if not throwers:
        return ""
    max_tot = throwers[0][1] if throwers else 1
    rows = ""
    for i, (name, tot, won) in enumerate(throwers[:5], 1):
        wp    = pct(won, tot)
        zones = {k: v for k, v in THROW_DIRS.get(name, {}).items() if v > 0}
        rows += stacked_row(i, name, tot, max_tot, wp, zones)
    return (f'<div style="background:#fff;border:1px solid #DEE2E6;border-radius:6px;overflow:hidden">'
            f'<div style="background:#F8F9FA;padding:4px 10px;border-bottom:1px solid #DEE2E6">'
            f'<span style="font-size:8.5px;font-weight:800;color:#14213D;text-transform:uppercase;letter-spacing:.05em">Thrower Ranking</span>'
            f'<span style="font-size:7px;color:#888;margin-left:6px">{label} hooker success (25-26)</span></div>'
            f'<div style="padding:8px 10px">{rows}</div></div>')


# ── Spears panel ───────────────────────────────────────────────────────────
def build_panel(team, label, header_color, own_nums, opp_nums_for_def, opp_ball=None):
    top = (f'<div style="display:grid;grid-template-columns:0.65fr 0.85fr 1.5fr;gap:10px;margin-bottom:10px">'
           + delivery_col(team)
           + winloss_col(team, opp_ball=opp_ball)
           + f'<div>{numbers_col(own_nums, opp_nums_for_def, label)}</div>'
           + f'</div>')
    ag = area_grid(team, label)
    bottom = (f'<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px">'
              + take_ranking_card(team, label)
              + steal_ranking_card(team, label)
              + thrower_ranking_card(team, label)
              + f'</div>')
    return (f'<div style="background:#FAFAFA;border:1px solid #DEE2E6;border-radius:8px;padding:10px 12px;margin-bottom:12px">'
            f'<div style="display:flex;align-items:center;gap:8px;padding:5px 10px;background:{header_color}18;'
            f'border-radius:5px;border-left:4px solid {header_color};margin-bottom:10px">'
            f'<span style="font-family:Oswald,sans-serif;font-size:12px;font-weight:700;letter-spacing:.08em;'
            f'text-transform:uppercase;color:{header_color}">&#127944; {label}</span>'
            f'</div>'
            + top + ag + bottom
            + f'</div>')


# ── Single number chart card ───────────────────────────────────────────────
def single_num_card(title, sub, nums_dict, perspective="own"):
    max_tot = max((v[0] for v in nums_dict.values()), default=1)
    bars    = num_bars_html(nums_dict, max_tot, perspective)
    return (f'<div style="background:#fff;border:1px solid #DEE2E6;border-radius:6px;overflow:hidden">'
            f'<div style="background:#F8F9FA;padding:3px 8px;border-bottom:1px solid #DEE2E6;display:flex;align-items:baseline;gap:6px">'
            f'<span style="font-size:8.5px;font-weight:800;color:#14213D;text-transform:uppercase;letter-spacing:.05em">{title}</span>'
            f'<span style="font-size:7px;color:#888">{sub}</span></div>'
            f'<div style="padding:5px 6px 4px;display:flex;gap:2px;align-items:flex-end">{bars}</div>'
            f'</div>')


# ── Opp Ball Won/Lost card (opponent steal rate vs Spears) ─────────────────
def opp_steal_card(sp_overall):
    sp_tot, sp_won = sp_overall
    steal      = sp_tot - sp_won
    steal_pct  = pct(steal, sp_tot)
    retain_pct = 100 - steal_pct
    return (f'<div style="background:#fff;border:1px solid #DEE2E6;border-radius:6px;overflow:hidden;margin-bottom:8px">'
            f'<div style="background:#F8F9FA;padding:4px 8px;border-bottom:1px solid #DEE2E6">'
            f'<span style="font-size:8.5px;font-weight:800;color:#14213D;text-transform:uppercase;letter-spacing:.05em">Opp Ball Won/Lost</span>'
            f'<span style="font-size:7px;color:#888;margin-left:4px">vs Spears own ball (season)</span></div>'
            f'<div style="padding:10px 10px">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">'
            f'<div>'
            f'<span style="font-family:Oswald,sans-serif;font-size:22px;font-weight:700;color:#1D4ED8">{steal_pct}%</span>'
            f'<span style="font-size:8px;color:#888;margin-left:4px">steal rate</span>'
            f'</div>'
            f'<div style="text-align:right">'
            f'<div style="font-size:9px;font-weight:700;color:#1D4ED8">{steal} Stolen</div>'
            f'<div style="font-size:9px;font-weight:700;color:#DC2626">{sp_won} Retained</div>'
            f'<div style="font-size:8px;color:#888">n={sp_tot}</div>'
            f'</div></div>'
            f'<div style="height:13px;display:flex;border-radius:3px;overflow:hidden">'
            f'<div style="width:{steal_pct}%;background:#1D4ED8"></div>'
            f'<div style="width:{retain_pct}%;background:#DC2626"></div>'
            f'</div></div></div>')


# ── Opponent panel (same layout as Spears panel) ───────────────────────────
def build_opp_panel(opp, abbr):
    label   = opp["name"]
    hc      = "#10B981"
    db_name = _DB_TEAM_NAME.get(abbr, "")
    # Lower section: Kubota's LO win rate from their games vs this team (DB)
    kub_lo  = _KUBOTA_LO_VS_OPP.get(db_name) or (SPEARS["overall"][0], SPEARS["overall"][1])

    top = (f'<div style="display:grid;grid-template-columns:0.65fr 0.85fr 1.5fr;gap:10px;margin-bottom:10px">'
           + delivery_col(opp)
           + winloss_col(opp, opp_ball=kub_lo)
           + f'<div>{numbers_col(opp["nums"], SPEARS["nums"], label)}</div>'
           + f'</div>')

    bottom = (f'<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px">'
              + take_ranking_card(opp, label)
              + steal_ranking_card(opp, label)
              + thrower_ranking_card(opp, label)
              + f'</div>')

    return (
        f'<div style="background:#FAFAFA;border:1px solid #DEE2E6;border-radius:8px;padding:10px 12px;margin-bottom:12px">'
        f'<div style="display:flex;align-items:center;gap:8px;padding:5px 10px;background:{hc}18;'
        f'border-radius:5px;border-left:4px solid {hc};margin-bottom:10px">'
        f'<span style="font-family:Oswald,sans-serif;font-size:12px;font-weight:700;letter-spacing:.08em;'
        f'text-transform:uppercase;color:{hc}">&#127944; {label}</span>'
        f'</div>'
        + top
        + area_grid(opp, label)
        + bottom
        + f'</div>'
    )


# ── Full section ─────────────────────────────────────────────────────────────
def build_section(abbr, opp):
    db_name  = _DB_TEAM_NAME.get(abbr, "")
    # Upper section: opp's LO win rate from their games vs Kubota (DB)
    opp_lo   = _OPP_LO_VS_KUBOTA.get(db_name) or (opp["own"][0], opp["own"][1])
    sp_panel = build_panel(
        team             = SPEARS,
        label            = "Kubota Spears",
        header_color     = "#F97316",
        own_nums         = SPEARS["nums"],
        opp_nums_for_def = opp["nums"],
        opp_ball         = opp_lo,
    )
    divider = (
        f'<div style="display:flex;align-items:center;gap:8px;margin:14px 0">'
        f'<div style="flex:1;height:2px;background:linear-gradient(to right,#E9ECEF,#ADB5BD)"></div>'
        f'<span style="font-size:8px;font-weight:700;color:#6B7280;text-transform:uppercase;letter-spacing:.1em">'
        f'vs {opp["name"]}</span>'
        f'<div style="flex:1;height:2px;background:linear-gradient(to left,#E9ECEF,#ADB5BD)"></div>'
        f'</div>'
    )
    return (
        f'<div id="lo" class="section">\n'
        f'  <div style="padding:0 2px">\n'
        f'    {sp_panel}\n'
        f'    {divider}\n'
        f'    {build_opp_panel(opp, abbr)}\n'
        f'  </div>\n'
        f'</div>\n'
    )


# ── File processing ────────────────────────────────────────────────────────
def process_file(fpath, abbr):
    with open(fpath, encoding="utf-8") as f:
        content = f.read()
    opp = TEAM_DATA[abbr]
    new_section = build_section(abbr, opp)
    LO = '<div id="lo" class="section">'
    SP = '<div id="sp" class="section">'
    if LO in content:
        lo_i = content.index(LO)
        sp_i = content.index(SP, lo_i)
        content = content[:lo_i] + new_section + content[sp_i:]
    elif SP in content:
        sp_i = content.index(SP)
        if "showSection('lo'" not in content:
            ke = ">Kicking</button>"
            if ke in content:
                idx = content.index(ke) + len(ke)
                nav = '<button class="nav-btn" style="color:#10B981" onclick="showSection(\'lo\',this)">Lineout</button>'
                content = content[:idx] + "\n  " + nav + content[idx:]
        content = content[:content.index(SP)] + new_section + content[content.index(SP):]
    else:
        return False
    with open(fpath, "w", encoding="utf-8") as f:
        f.write(content)
    return True


def main():
    done = 0
    for d in [BIOUT_DIR]:
        if not os.path.isdir(d):
            continue
        for fname in sorted(os.listdir(d)):
            if not (fname.startswith("scout_Spears_vs_") and fname.endswith(".html")):
                continue
            m = re.match(r"scout_Spears_vs_(.+)_R\d+\.html", fname)
            if not m or m.group(1) not in TEAM_DATA:
                continue
            fpath = os.path.join(d, fname)
            print(f"  {fname}")
            if process_file(fpath, m.group(1)):
                done += 1
    print(f"\nDone: {done} files updated.")

if __name__ == "__main__":
    main()
