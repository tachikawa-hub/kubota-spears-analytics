# Kubota Spears Analytics

Kubota Spears のBI CSVデータから、シーズンKPIレポート、マッチレポート、スカウティングレポートを生成する分析ツールです。

このリポジトリでは、共有用のHTMLレポートと生成スクリプトを管理します。元CSVデータと `rugby.db` はローカル環境で管理し、GitHubには含めません。

現在は、ローカルデータの正本をこのリポジトリ内の `data/` に統一する運用です。
`data/BI Scouting/` を受信口にしつつ、`data/competitions/` に大会別・ディビジョン別・シーズン別で整理していきます。

## 主なファイル

- `rugby_bi.py` - メインCLI。DB作成、KPI、マッチレポート、スカウティングレポート生成を行います。
- `build_rugby_db.py` - CSVから `rugby.db` を作成する旧/補助スクリプトです。
- `match_report_template.html` - マッチレポートのテンプレートです。
- `index.html` - 共有用トップページです。
- `season_kpi_v2.html` - シーズンKPIレポートです。
- `season_kpi_a4.html` - A4レイアウト版のシーズンKPIレポートです。
- `match_report_*.html` - 各試合のマッチレポートです。
- `scout_*.html` - 対戦相手別のスカウティングレポートです。
- `sr_*.html` / `sr_index.html` - Super Rugby 関連レポートです。
- `videos/` - 共有ページで使用する動画素材です。
- `data/` - ローカル専用データ置き場です。`data/BI Scouting/` に受信CSV、`data/competitions/` に整理済みCSV、`data/rugby.db` にDBを置きます。
- `csv_data/` - Super Rugby 補助データ用ディレクトリです。

## GitHubに含めないもの

`.gitignore` により、以下はGitHubに上げない運用です。

- `*.csv`
- `rugby.db`
- `node_modules/`
- `.claude/`
- macOSやエディタの一時ファイル

元データは大きく、再生成可能で、共有範囲にも注意が必要なため、各自のローカル環境で管理します。

## CSV配置場所

基本の想定配置は、リポジトリ直下の `data/` を正本にする形です。

```text
kubota-spears-analytics/
├── data/
│   ├── BI Scouting/
│   │   ├── match_001_BI.csv
│   │   ├── match_002_BI.csv
│   │   └── ...
│   ├── competitions/
│   │   ├── league_one/
│   │   │   ├── d1/
│   │   │   │   └── 2026/
│   │   │   └── d2/
│   │   │       └── 2026/
│   │   ├── super_rugby/
│   │   ├── urc/
│   │   ├── top14/
│   │   └── international/
│   └── rugby.db
├── rugby_bi.py
├── index.html
└── ...
```

この配置の場合、コマンドでは `--data "./data"` を指定します。

```bash
python3 rugby_bi.py build --data "./data"
```

別の場所にCSVを置く場合は、`--data` にそのフォルダパスを指定できます。ただし通常運用では `data/` 配下に寄せるのをおすすめします。

```bash
python3 rugby_bi.py build --data "/path/to/BI Scouting"
```

CSVファイルはGitHubには上げません。ローカルで保管し、必要に応じて別途バックアップします。

## 基本コマンド

通常は、以下の順番で生成します。

### 1. CSVからDBを作成

```bash
python3 organize_bi_csvs.py
python3 rugby_bi.py build --data "./data"
```

このコマンドで、`data/rugby.db` が作られます。`rugby.db` はGitHubには上げません。

### 2. シーズンKPIレポートを生成

```bash
python3 rugby_bi.py kpi
```

出力ファイル:

- `season_kpi_v2.html`

### 3. A4版のシーズンKPIレポートを生成

```bash
python3 rugby_bi.py kpi-a4
```

出力ファイル:

- `season_kpi_a4.html`

### 4. 指定ラウンドのマッチレポートを生成

```bash
python3 rugby_bi.py match --round 22
```

出力ファイル例:

- `match_report_2026-06-07_Kobelco_Kobe_Steelers.html`

### 5. 対戦相手別のスカウティングレポートを生成

```bash
python3 rugby_bi.py scout --opp "Kobelco Kobe Steelers" --round 22 --data "./data"
```

出力ファイル例:

- `scout_Spears_vs_Steelers_R22.html`

### 6. DB作成とKPI生成をまとめて実行

```bash
python3 rugby_bi.py all --data "./data"
```

`all` は `build` と `kpi` をまとめて実行します。マッチレポートやスカウティングレポートは、必要なラウンドや対戦相手を指定して別途生成します。

### 0. 受信CSVを大会別に整理

```bash
python3 organize_bi_csvs.py
```

このコマンドで、`data/BI Scouting/` のCSVを `data/competitions/` 配下へ大会別・ディビジョン別・シーズン別にコピー整理します。

## 安全な作業手順

コードやレポートを変更する前に、必ず現在の状態を確認します。

```bash
git status --short --branch
```

変更後は、差分を確認します。

```bash
git diff
```

Pythonファイルを触った場合は、最低限の構文チェックを行います。

```bash
python3 -m py_compile rugby_bi.py
```

生成結果を更新した場合は、意図しないHTMLが大量に変わっていないか確認します。

```bash
git status --short
```

## Codex / Claude Code 併用ルール

両方を使う場合は、同じタイミングで同じファイルを編集しないようにします。

基本方針:

- 重要ファイルの編集はCodexのみで行います。
- KPI解釈、レポート文言、コーチ向け説明、分析アイデアはCodex / Claude Codeのどちらにも相談できます。
- 採用する内容をファイルへ反映する作業はCodexが行います。
- GitHubへの反映前に、Codexが `git status` / `git diff` を確認します。

おすすめの役割分担:

- Codex - 実装、コード整理、バグ修正、差分確認、テスト、READMEや運用手順の整備、KPI解釈案
- Claude Code - 分析アイデア、レポート文言、コーチ向け説明、見せ方の相談、追加KPI案
- GitHub - 正本管理、共有、変更履歴の確認

### ファイルごとの担当

| 対象 | 主担当 | ルール |
| --- | --- | --- |
| `README.md` | Codex | Claude Codeで出した案も、最終反映はCodexが行います。 |
| `rugby_bi.py` | Codexのみ | コード修正はCodexのみで行います。Claude Codeでは直接編集しません。 |
| `build_rugby_db.py` | Codexのみ | CSV取り込みやDB作成ロジックの修正はCodexのみで行います。 |
| `match_report_template.html` | Codexのみ | テンプレート修正はCodexのみで行います。文言案はCodex / Claude Codeで相談できます。 |
| `index.html` | Codexのみ | 共有トップページの反映はCodexのみで行います。構成案はCodex / Claude Codeで相談できます。 |
| `season_kpi_*.html` | Codexのみ | 基本は生成物として扱い、手編集しません。更新する場合は生成コマンドで作り直します。 |
| `match_report_*.html` | Codexのみ | 基本は生成物として扱い、手編集しません。必要な試合だけ再生成します。 |
| `scout_*.html` | Codexのみ | 基本は生成物として扱い、手編集しません。必要な対戦相手だけ再生成します。 |
| `videos/` | 手動管理 | 動画素材は不用意に置き換えません。変更前にバックアップします。 |
| `*.csv` | 手動管理 | GitHubには上げません。ローカルで管理し、別途バックアップします。 |
| `rugby.db` | 自動生成 | GitHubには上げません。CSVから再生成します。 |

### GitHubへの反映ルール

GitHubへ反映する作業は、Codexが差分を確認してから行います。

基本フロー:

```text
1. CodexまたはClaude Codeでアイデア、分析文言、改善案を相談する
2. 採用する内容だけを箇条書きに整理する
3. Codexに「この内容だけ反映」と依頼する
4. Codexが対象ファイルを編集する
5. Codexが git status / git diff を確認する
6. 問題なければGitHubに反映する
```

同じファイルをCodexとClaude Codeで同時に編集しません。特に `rugby_bi.py` と生成済みHTMLは、どちらか一方の作業が終わって差分確認が済むまで触らないようにします。

作業前にはバックアップを取り、作業単位を小さくします。最初はREADME追加、コマンド整理、KPI定義一覧化など、壊れにくい変更から進めます。

## バックアップ

大きな変更の前には、リポジトリとローカルCSVフォルダを別々に圧縮して保存します。

例:

```bash
tar -czf kubota-spears-analytics-backup.tar.gz kubota-spears-analytics
```

CSVや `rugby.db` はGitHubに含まれないため、ローカル側で別途バックアップしてください。

## Lineoutプルダウン設計メモ

スカウティングレポートの `Lineout` タブに、試合別表示用のプルダウンを追加する予定です。

目的:

- 現在の全試合集計を `All` として残す
- 各試合を選択したときに、その試合だけのLineout状況を表示する
- Kubota Spears とスカウティング対象チームのLineoutを、同じタブ内で比較できるようにする

想定UI:

```text
Lineout

Match: [ All ▼ ]

All
R1 vs Kobelco Kobe Steelers
R2 vs BlackRams Tokyo
R3 vs Tokyo Sungoliath
...
R22 vs Kobelco Kobe Steelers
```

`All` を選んだ場合は、現在と同じ全試合集計を表示します。特定試合を選んだ場合は、その試合だけの数値に切り替えます。

表示切り替え対象:

- Delivery Type
- Won / Lost
- Own Numbers
- Opp Numbers Success %
- Area Breakdown
- Take Ranking
- Steal Ranking
- Thrower Ranking

実装対象ファイル:

- `insert_lineout_v4.py` - LineoutタブのHTML生成元。主な実装対象です。
- `rugby_bi.py` - スカウティングレポート生成フロー確認用。必要な場合のみ触ります。
- `insert_kicktest.py` - 既存の試合選択UIの参考実装です。基本は参照のみです。

必要データ:

- `rugby.db` または元CSV
- `matches` テーブルの `fxid`, `round_number`, `date_played`, `opponent_name`
- `events` テーブルの `Lineout Throw`, `Lineout Take`
- `team_name`, `action_type_name`, `action_result_name`, `qualifier4_name`, `x_coord`, `player_name`

データ構造案:

```text
LINEOUT_DATA = {
  "all": {
    "label": "All",
    "kubota": { ... },
    "opponent": { ... }
  },
  "fxid": {
    "label": "R22 vs Kobelco Kobe Steelers",
    "kubota": { ... },
    "opponent": { ... }
  }
}
```

各 `kubota` / `opponent` には、既存のLineoutカードで使っている以下の集計を入れます。

```text
overall
delivery
nums
areas
area_nums
throwers
takes
steals
opp_ball
opp_nums
```

安全方針:

- 生成済み `scout_*.html` は原則手編集しません。
- まず `insert_lineout_v4.py` に生成ロジックを追加します。
- その後、必要な `scout_*.html` を再生成します。
- 再生成後は `git status --short` と `git diff` で、想定外のHTMLが変わっていないか確認します。
- 正しい試合別数値を出すには、Codexから `rugby.db` または元CSVが読める状態にする必要があります。

## 今後の改善候補

- KPI定義を1か所に集約する
- レポート生成コマンドをスクリプト化する
- READMEにCSV配置例を追加する
- 生成前後のチェック手順を自動化する
- HTMLレポート一覧を自動更新する
- 将来的に簡易Webアプリ化する
