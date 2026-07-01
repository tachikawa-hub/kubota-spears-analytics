# Opta Rugby Union BI Event Data 定義書（v2.0.0）

ソース: `Rugby Union - BI Event Data 2.0.0.pdf`（Stats Perform / 2025-03-20）

---

## データ構造（主要列）

| 列名 | 説明 |
|------|------|
| action / actionName | メインアクションのID・名称 |
| actionType / actionTypeName | 第1修飾子（アクション種別）のID・名称 |
| actionResult / ActionResultName | 第2修飾子（アクション結果）のID・名称 |
| qualifier3〜10 | 追加修飾子（種別ごとに意味が異なる） |
| Metres | ゲインラインからの獲得メートル |
| x_coord / y_coord | イベント発生座標（x=0:自陣トライライン、x=100:相手トライライン） |
| player_advantage | フィールド上の数的差（シンビン等による） |
| score_advantage | イベント発生時の得点差（正=リード、負=ビハインド） |
| result | 試合結果（W=勝利、L=敗北、D=引き分け）※イベントを所有するチーム視点 |
| assoc_playerName | 関連プレーヤー名（タックルした選手など） |

---

## アクション別定義

### ACTION ID = 1 ｜ CARRIES（キャリー）
ボールを持って相手と明確に接触を試みたプレー。

**ActionTypeName（キャリー種別）**

| 名称 | 説明 |
|------|------|
| Pick and Go | ラック・モール・スクラムの根元からのキャリー |
| One Out Drive | ラック等から1パス後、ディフェンスとのコンタクトを想定したキャリー |
| Kick Return | 相手キックの直後フェーズでのキャリー |
| Restart Return | 相手リスタートキック後のキャリー |
| Support Carry | 同フェーズの前キャリアをサポートしたキャリー（オフロード受けなど） |
| Other Carry | 上記以外のキャリー |

**ActionResultName（キャリー結果）**

| 名称 | 説明 |
|------|------|
| Tackled Ineffective | タックルされ、コンタクトで大きく不利になった |
| Tackled Neutral | タックルされ、コンタクトで優劣なし |
| Tackled Dominant | タックルされたが、コンタクトでキャリアが優勢 |
| Try Scored | キャリアがトライを決めた |
| Off Load | キャリア中にオフロードパス |
| Pass | キャリア後にパス |
| Kick | キャリア後にキック |
| Error | キャリア後にエラー |
| Pen Conceded | キャリア中にペナルティを与えた |
| Penalty Won | キャリア中にペナルティを獲得した |
| Other | 上記以外 |

**Qualifier3（ゲインライン）**

| 名称 | 説明 |
|------|------|
| Crossed Gain Line | ゲインラインを越えてタックルされた |
| Neutral Gain Line | ゲインライン上でタックルされた |
| Failed Gain Line | ゲインライン手前でタックルされた |

---

### ACTION ID = 2 ｜ TACKLES（タックル）
相手ボールキャリアを止めるか、ボールを奪おうとした試み。

**ActionTypeName（タックル種別）**

| 名称 | 説明 |
|------|------|
| Line Tackle | ディフェンスラインの一員としてのタックル |
| Edge Tackle | 15mチャンネル付近、エッジ部でのタックル |
| Guard Tackle | ラック形成後、横に構えたガードポジションからのタックル |
| Chase Tackle | キックの後追いでのタックル |
| Cover Tackle | ブレイクした相手や退いてのタックル |
| Other Tackle | 上記以外（スクラムからのフランカータックル等） |

**ActionResultName（タックル結果）**

| 名称 | 説明 |
|------|------|
| Complete | タックラーが相手を倒してタックル完結 |
| Passive | タックラーが接触戦で負け、相手が優勢な体勢 |
| Offload Allowed | タックル中に相手のオフロードを許した |
| Turnover Won | 相手からボールを奪った |
| Forced in Touch | 相手をタッチラインに追い出した |
| Pen Conceded | タックル中にペナルティを与えた |
| Try Saver | 卓越したプレーでトライを直接阻止した |
| Sack | 接触戦で優勢、相手をドミネート |
| Ineffective | タックルは完結したが相手にトライを許したか、よりポストに近い位置でのトライを防いだにとどまった |
| Missed | 合理的にタックルが期待できる状況でミスした |

---

### ACTION ID = 3 ｜ PASSES（パス）
意図を持ってチームメートにボールを投げた。

**ActionTypeName（パス種別）**

| 名称 | 説明 |
|------|------|
| Complete | 意図したターゲットにきれいにキャッチされた |
| Break | 受け手が直接ラインブレイクをもたらしたパス |
| Forward | レフリーによりフォワードパスと判定された |
| Incomplete | ターゲットにきれいに届かなかったパス（バウンド受け、誤ったレシーバー、キャッチ失敗など） |
| Intercepted | 相手にインターセプトされた |
| Off Target | 受け手が大きく動いたり手を伸ばす必要があったパス |
| Try | 受け手が直接トライしたパス |
| Error | 直接エラーになったパス（タッチに出たなど） |
| Offload | タックル中に投げたパス（オフロード） |

**ActionResultName（オフロード結果）**

| 名称 | 説明 |
|------|------|
| Own Player | 直接味方の手に渡った |
| To Ground | 地面を経由してから味方に渡った |
| To Opposition | 相手に渡った（直接または地面経由） |

---

### ACTION ID = 4 ｜ KICKS（キック）
足でボールを蹴った。

**ActionTypeName（キック種別）**

| 名称 | 説明 |
|------|------|
| Bomb | 高く蹴り上げ、キッキングチームが相手に圧力をかけるか自ら確保するためのキック |
| Chip | ディフェンスライン越しに短く重みをつけたキック（攻撃選手が走り込む） |
| Cross Pitch | キッカーとは反対サイドへの横方向のキック |
| Territorial | フィールドポジションを得ることを目的としたキック |
| Low | 低い弾道のキック（攻撃選手が走り込む） |
| Box | ラック・モール・スクラム・ラインアウトの根元から直接蹴るキック |
| Touch Kick | ペナルティキックや終了間際にタッチラインを越えることを意図したキック |

**ActionResultName（キック結果）**

| 名称 | 説明 |
|------|------|
| Kick in Touch (Bounce) | フィールド内でバウンドした後にタッチラインを越えた |
| Kick in Touch (Full) | 自陣22m内からまたはペナルティキックでダイレクトにタッチに出た |
| Error - Charged Down | 相手にチャージダウンされた |
| Error - Out of Play | 22m外からのキックがノーバウンドでタッチに出た（エラー） |
| Error - Territorial Loss | ペナルティキックがタッチを外れ守備側のラインアウトになった、または後方へ蹴りターンオーバーとなった |
| Error - Dead Ball | ボールがデッドボールラインを越えた |
| Caught Full | 相手にノーバウンドでキャッチされた |
| Collected Bounce | ボールが地面に触れた後に相手に確保された |
| In Goal | ボールが相手インゴールエリアに落ちてグラウンディングされた |
| Own Player - Collected | 同チームの選手が確保した |
| Own Player - Failed | 同チームの選手がボールに触れたが確保できなかった |
| Pressure Carried Over | 相手がボールを自陣ゴールライン越しに運ぶよう追い込まれた |
| Pressure in Touch | 相手がボールをタッチラインを越えて持ち込んだ |
| Pressure Error | 相手がボールを確保できずエラーとなった |
| Try Kick | キックが直接トライにつながった |

**Qualifier3（キック起点）**

| 名称 | 説明 |
|------|------|
| Kick in Play | 22m外またはボールを22m内に持ち帰った状況からのキック |
| Kick in Play (Own 22) | 自陣22m内からのキック |
| Penalty Kick | ペナルティを獲得したチームによるランニングキック |

**Qualifier4（特殊キック判定）**

| 名称 | 説明 |
|------|------|
| 22/50 | 22/50のキックが成功した |
| 50/22 | 50/22のキックが成功した |

---

### ACTION ID = 5 ｜ SCRUMS（スクラム）
レフリーの「セット」の合図から有効。

**ActionResultName（スクラム結果）**

| 名称 | 説明 |
|------|------|
| Won Outright | 投入チームがボールを確保してプレー続行 |
| Won Free Kick | 投入チームがフリーキックを獲得 |
| Won Penalty | 投入チームがペナルティを獲得 |
| Won Penalty Try | スクラムから直接ペナルティトライ |
| Won Try | スクラムから直接トライ（スクラムを崩さずスコア） |
| Reset | エンゲージ後にスクラムのやり直し |
| Lost Outright | ディフェンス側がボールを確保してプレー続行 |
| Lost Free Kick | 投入チームがフリーキックを与えた |
| Lost Pen Con | 投入チームがペナルティを与えた |
| Lost Reversed | スクラムが90度以上回転し、相手に投入権が移った |

**ActionTypeName（スクラムオプション）**

| 名称 | 説明 |
|------|------|
| No 8 Pass | No.8がスクラム根元からパス |
| No 8 Pick Up | No.8がボールを持って突進 |
| Scrum Half Pass | SHがスクラム根元から直接パス |
| Scrum Half Kick | SHがスクラム根元から直接キック |
| Scrum Half Run | SHがボールを持って突進 |

---

### ACTION ID = 6 ｜ LINEOUT THROW（ラインアウト投入）

**ActionTypeName（投入距離）**

| 名称 | 説明 |
|------|------|
| Throw Front | ラインアウト前方（5m線直上付近）への投入 |
| Throw Middle | ラインアウト中央への投入 |
| Throw Back | ラインアウト後方（15m線内）への投入 |
| Throw 15m+ | 15m線を越えての投入 |
| Throw Quick | ラインアウト未形成での素早い投入 |

**ActionResultName（ラインアウト結果）**

| 名称 | 説明 |
|------|------|
| Won Clean | 攻撃チームがきれいにボールを確保 |
| Won Tap | 攻撃チームがタップダウンでボールを確保（不安定） |
| Won Penalty | 攻撃チームがペナルティを獲得 |
| Won Free Kick | 攻撃チームがフリーキックを獲得 |
| Won Other | その他の方法で攻撃チームが獲得 |
| Lost Not Straight | スロワーがまっすぐ投げず、相手スクラムに |
| Lost Handling Error | ハンドリングエラーで失った |
| Lost Clean | ディフェンス側がきれいにスチール |
| Lost Free Kick | ディフェンス側がフリーキックを獲得 |
| Lost Penalty | ディフェンス側がペナルティを獲得 |
| Lost Not 5m | 投入が5m以上届かなかった |
| Lost Overthrown | 投げすぎてディフェンス側に渡った |
| Lost Other | その他の方法でディフェンス側が獲得 |

---

### ACTION ID = 7 ｜ PENALTY CONCEDED（ペナルティ）

**ActionTypeName（ペナルティ種別）**

| 名称 | 説明 |
|------|------|
| Not Releasing | タックルされた選手がボールを放さなかった |
| Hands in Ruck | ラック形成後にボールに手を入れた |
| Wrong Side at Ruck | ラックのゲートを通らずに入った |
| Wrong Side at Maul | モールのゲートを通らずに入った |
| Offside | オフサイドポジションにいてプレーに影響を与えた |
| Offside at Kick | キッカーの前にいてプレーに影響を与えた（引かずにいた） |
| Collapsing Maul | モールを意図的に崩した |
| Scrum Offence | スクラムでの反則 |
| Lineout Offence | ラインアウトでの反則 |
| Off Feet at Ruck | ラックで倒れてボールの出を妨害した |
| Not Rolling Away | タックラーが離れず/転がらずにいた |
| Preventing Release | ボールキャリアがボールを放せないよう妨害した |
| Foul Play - Foot Contact | スタンピング・キック・トリッピング等の足による接触 |
| Foul Play - Mid Air Tackle | 空中の選手（ボールあり/なし問わず）を倒した |
| Foul Play - High Tackle | 肩より上へのタックル |
| Foul Play - Other | その他のファウルプレー |
| Deliberate Knock On | 意図的なノックオン |
| Obstruction | 相手選手を意図的にブロック・妨害 |
| Dissent | 審判への抗議・不適切な発言 |
| Foul Play - Fighting | 格闘行為 |
| Foul Play - Dangerous Throw | 危険なスロー |
| Foul Play - Late Tackle | 遅いタックル（ボールを放した後に大幅に遅れて） |
| Charging into Ruck | ラック/モールに危険な方法でバインドせず突入 |
| Maul Obstruction | 攻撃側選手がモール前で守備を妨害 |
| Other Offence | 上記以外の反則 |

**ActionResultName（ペナルティへの処分）**

| 名称 | 説明 |
|------|------|
| No Action | ペナルティのみで処分なし |
| Yellow Card | イエローカード |
| Red Card | レッドカード |
| Penalty Try | ペナルティトライ |

---

### ACTION ID = 8 ｜ TURNOVERS（ターンオーバー）
エラーにより相手にボールが渡った。

**ActionTypeName（ターンオーバー種別）**

| 名称 | 説明 |
|------|------|
| Attempted Intercept | インターセプト未遂（ボールに触れたが成功しなかった） |
| Bad Offload | 失敗したオフロード |
| Bad Pass | 失敗したパス |
| Carried Over | 選手がボールを自陣ゴールライン越しにグラウンディング |
| Carried in Touch | 選手がボールをタッチラインを越えて持ち込んだ |
| Dropped Ball Unforced | 相手のコンタクトなしにボールをドロップ |
| Forward Pass | フォワードパス |
| Lost Ball Forced | コンタクト/ボールスチールで強制的にボールを失った |
| Accidental Offside | 意図せずオフサイドポジションに入ってしまった |
| Lost in Ruck or Maul | ラック/モールで相手にボールを奪われた |
| Kick Error | 不必要なターンオーバーにつながるキックエラー |
| Failure to Find Touch | ペナルティキックでタッチを外した |
| Accidental Knock On | タックル中に偶発的なノックオン |
| Offside at Restart | リスタートキック時にボール前にいた |
| Other Error | その他のエラー |
| 5 Second Rule | ラック根元でボールが出て5秒以内にSHが使わなかった |

**ActionResultName（ターンオーバー状況）**

| 名称 | 説明 |
|------|------|
| Error on Attack | 自チームがボールを持っている時のエラー |
| Error on Defence | 相手がボールを持っている時のエラー |

---

### ACTION ID = 9 ｜ TRY（トライ）

**ActionTypeName（トライ種別）**

| 名称 | 説明 |
|------|------|
| Penalty Try | レフリーがペナルティトライを宣告 |
| Regular Try | 通常のトライ |

---

### ACTION ID = 10 ｜ ATTACKING QUALITIES（アタッキングクオリティ）

**ActionTypeName（攻撃イベント種別）**

| 名称 | 説明 |
|------|------|
| Initial Break | ボールキャリアが最初のディフェンスラインを突破 |
| Supported Break | ラインブレイクした選手をサポートしてボールを受け継続 |
| Defender Beaten | ディフェンスをかわした（逃げた・フィジカルで勝った・走り込みで抜いた）。1選手あたり1回カウント |
| Try Assist | トライに大きく貢献 |
| Break Assist | ラインブレイクに大きく貢献 |
| Decoy | デコイランで守備ラインの突破を試みた |
| Snake | ボールキャリアの前進または後退防止を助けた |

**ActionResultName（ラインブレイク種別）**

| 名称 | 説明 |
|------|------|
| Line Break | ランでラインを突破 |
| Kick Line Break | ラインの上/間を通るキックでラインを突破 |
| Intercepted Break | インターセプトでラインを突破 |

---

### ACTION ID = 11 ｜ GOAL KICKS（ゴールキック）

**ActionTypeName（ゴールキック種別）**

| 名称 | 説明 |
|------|------|
| Conversion | コンバージョン |
| Penalty Goal | ペナルティゴール |
| Drop Goal | ドロップゴール |

**ActionResultName（ゴールキック結果）**

| 名称 | 説明 |
|------|------|
| Goal Kicked | キック成功 |
| Goal Missed | キック失敗 |
| Timed Out | タイムアップで未蹴了 |
| Declined | チームがキックを選択しなかった |

---

### ACTION ID = 12 ｜ MISSED TACKLE（ミスタックル）

**ActionTypeName（ミスタックル原因）**

| 名称 | 説明 |
|------|------|
| Bumped Off | アタッカーのフィジカルに弾き飛ばされた |
| Stepped | アタッカーのフットワークや回避でかわされた |
| Outpaced | アタッカーの速さで抜かれた |
| Positional | ポジショニングの誤りまたはシステムエラー |

**ActionResultName（ミスタックル後の結果）**

| 名称 | 説明 |
|------|------|
| Tackled | ミス後すぐに別のディフェンダーがタックル |
| Clean Break | ミスが直接クリーンブレイクにつながった |
| Try | ミスが直接トライにつながった |

---

### ACTION ID = 14 ｜ RESTART KICK（リスタートキック）
前後半開始、トライ後、ゴールキック後等のリスタート。

**ActionTypeName（リスタート種別）**

| 名称 | 説明 |
|------|------|
| 50m Restart | ハーフウェイラインからのリスタート |
| 22m Restart | 自陣22m内からのリスタート |
| Goal Line Restart | 自陣インゴールエリアからのリスタート |

**ActionResultName（リスタート結果）**

| 名称 | 説明 |
|------|------|
| Restart Retained | キック側チームがボールを確保 |
| Restart Opp Error | 受け側チームがエラーを犯した |
| Restart Opp Collection | 受け側チームが安全にボールを確保 |
| Restart Own Error | キック側チームがエラーまたはルール違反のキック |
| Kick in Touch | リスタートキックがタッチラインを越えた（受け側チームのラインアウトに） |

---

### ACTION ID = 15 ｜ POSSESSIONS（ポゼッション）
チームがボールを完全にコントロールしている期間。

**ActionTypeName（ポゼッション開始）**

| 名称 | 説明 |
|------|------|
| 50m Restart | 相手の50mリスタートから |
| 50m Restart Retained | 自チームの50mリスタートを保持 |
| 22m Restart | 相手の22mリスタートから |
| 22m Restart Retained | 自チームの22mリスタートを保持 |
| Free Kick | フリーキックのタップから |
| Kick Return | 相手キック（ミスペナルティ・ドロップ等含む）のフィールドキャッチから |
| Turnover Won | オープンプレーでのターンオーバー |
| Lineout | 自チームのラインアウト勝利から |
| Lineout Steal | 相手のラインアウトをスチール |
| Scrum | 自チームのスクラム勝利から |
| Scrum Steal | アゲインストヘッドでのスクラム勝利 |
| Tap Pen | ペナルティのタップから |
| Goal Line Restart | 相手のゴールラインリスタートから |
| Goal Line Restart Retained | 自チームのゴールラインリスタートを保持 |

**ActionResultName（ポゼッション終了）**

| 名称 | 説明 |
|------|------|
| Try | トライ（またはペナルティトライ）で終了 |
| Drop Goal | ドロップゴール成功で終了 |
| Kick Out of Play | キックがタッチに出て終了 |
| Kick Error | エラーキックで相手にボールが渡った |
| Kick in Play | 相手にフィールド内でキックを確保された |
| Kick in Goal | ボールが相手インゴールに蹴り込まれタッチダウンされた |
| Pen Won | ペナルティ獲得で終了 |
| Scrum | スクラムが与えられた |
| Pen Con | ペナルティを与えた |
| Turnover | エラーによりボールを失った（プレー継続） |
| Turnover (Scrum) | エラーによりボールを失い相手スクラムに |
| Own Lineout | 自チームがラインアウトを獲得（例：ボールが相手に当たりタッチへ） |
| Other | その他 |
| End of Play | ハーフタイムまたはフルタイム |
| Drop Goal Missed | ドロップゴール失敗で終了 |

---

### ACTION ID = 18 ｜ COLLECTION（コレクション）
通常のパスキャッチ以外で、ボール確保が保証されない状況での確保試み。

**ActionTypeName（コレクション種別）**

| 名称 | 説明 |
|------|------|
| Interception | 相手のパスをインターセプトしようとした |
| In Goal Touchdown | 自陣インゴールでグラウンディングしようとした |
| Mark | 自陣22m内でマークを呼びながらキャッチしようとした |
| Attacking Catch | 自チームのキックをキャッチしようとした |
| Attacking Loose Ball | 攻撃側がグラウンドボールを確保しようとした |
| Defensive Catch | 相手キックをキャッチしようとした |
| Defensive Loose Ball | ディフェンス側がグラウンドボールを確保しようとした |
| Restart Catch | リスタートキックをキャッチしようとした |
| Jackal | ラックでハンドを使い相手からボールを奪おうとした |
| Tap Back | 自チームにタップバックしようとした |
| Charge Down | 相手のキックをチャージダウンしようとした |
| General Catch | 自チームがすでにポゼッションを持っている状況でのキャッチや拾い上げ |

**ActionResultName**

| 名称 | 説明 |
|------|------|
| Success | 確保成功 |
| Fail | 確保失敗 |

---

### ACTION ID = 21 ｜ RUCKS（ラック）

**ActionTypeName（ラック結果）**

| 名称 | 説明 |
|------|------|
| Won Outright | 攻撃チームがボールを確保 |
| Lost Outright | ディフェンス側がボールを確保 |
| Penalty Won | 攻撃チームがペナルティを獲得 |
| Penalty Conceded | 攻撃チームがペナルティを与えた |
| Penalty Try | ラック直後にペナルティトライ |
| Unplayable | アンプレイアブル（攻撃アドバンテージ中にディフェンスがボールを確保した場合も含む） |

---

### ACTION ID = 22 ｜ MAULS（モール）

**ActionResultName（モール結果）**

| 名称 | 説明 |
|------|------|
| Won Outright | 攻撃チームがボールを確保 |
| Lost Outright | 攻撃チームがボールを失った |
| Penalty Won | 攻撃チームがペナルティを獲得 |
| Penalty Conceded | 攻撃チームがペナルティを与えた |
| Try Scored | モールから直接トライ |
| Penalty Try | モールから直接ペナルティトライ |
| Unplayable | アンプレイアブル |

---

### ACTION ID = 23 ｜ SEQUENCES（シーケンス）
ボールがインプレー状態の期間（どちらのチームがポゼッションを持つかは問わない）。

**ActionTypeName（シーケンス開始）**

| 名称 | 説明 |
|------|------|
| 50m Restart | 50mリスタートで開始 |
| 22m Restart | 22mリスタートで開始 |
| Free Kick | フリーキックのタップで開始 |
| Lineout | ラインアウトで開始 |
| Scrum | スクラムで開始 |
| Tap Pen | タップペナルティで開始 |
| Goal Line Restart | ゴールラインリスタートで開始 |
| Penalty Kick Touch | フィールドに残ったペナルティキックtoタッチで開始 |
| Penalty Goal | フィールドに残ったペナルティゴール試みで開始 |
| Scrum Reset | 不完全スクラムのやり直しで開始 |
| Lineout Steal | スチールラインアウトで開始 |
| Scrum Steal | アゲインストヘッドスクラムで開始 |

**ActionResultName（シーケンス終了）**
ポゼッションの終了と同様（Try / Drop Goal / Kick Out of Play / Pen Won 等）。

---

### ACTION ID = 24 ｜ LINEOUT CATCH（ラインアウトキャッチ）

**ActionTypeName（キャッチ位置）**

| 名称 | 説明 |
|------|------|
| Lineout Win Front/Middle/Back/15m+/Quick | 投入チームがそれぞれの位置でボールを確保 |
| Lineout Steal Front/Middle/Back/15m+/Quick | ディフェンスチームがそれぞれの位置でスチール |

---

### ACTION ID = 27 ｜ DEFENSIVE ACTIONS（ディフェンシブアクション）

**ActionTypeName**

| 名称 | 説明 |
|------|------|
| Tackle Arrival | タックルできる位置にいるが意図的にタックルしないことを選択 |
| Aerial Kick Contest | 空中のボールを争ったがコンタクトなし |
| Ball Steal Maul | モールでボールを奪取した |

---

### ACTION ID = 31 ｜ COUNTERATTACK（カウンターアタック）
ディフェンシブな位置でボールを受け、カウンターアタックを試みた。

**ActionTypeName（結果）**

| 名称 | 説明 |
|------|------|
| Outcome - Try Scored | カウンターからトライ |
| Outcome - Penalty Won | カウンターからペナルティ獲得 |
| Outcome - Penalty Conceded | カウンターからペナルティ失う |
| Outcome - Kick To Opposition | カウンターからキックで相手にボール渡した |
| Outcome - Kicked Out | カウンターからタッチに蹴り出した |
| Outcome - Lineout Won | カウンターからラインアウト獲得 |
| Outcome - Scrum Won | カウンターからスクラム獲得 |
| Outcome - Turnover | カウンターからターンオーバー |
| Outcome - Drop Goal | カウンターからドロップゴール |

---

### ACTION ID = 32 ｜ DEFENSIVE EXITS（ディフェンシブエグジット）
自陣22m内でボールを受け、エグジットを試みた。

**ActionTypeName**

| 名称 | 説明 |
|------|------|
| Failed Exit From 22 | エグジット失敗（22m内でボールを失った） |
| Carried out of 22 | キャリーで22mを脱出成功 |
| Kicked out of 22 | キックで22mを脱出成功 |

---

### ACTION ID = 33 ｜ ATTACKING 22 ENTRY（アタッキング22エントリー）
相手22mに侵入（1ポゼッション1回のみカウント）。

**ActionTypeName（結果）**

| 名称 | 説明 |
|------|------|
| 22 Entry Outcome - Try | 22m侵入後にトライで終了 |
| 22 Entry Outcome - Penalty Won | 22m侵入後にペナルティ獲得 |
| 22 Entry Outcome - Penalty Conceded | 22m侵入後にペナルティ失う |
| 22 Entry Outcome - Penalty Goal Attempt | 22m侵入後にペナルティゴール試み |
| 22 Entry Outcome - Lineout Won | 22m侵入後にラインアウト獲得 |
| 22 Entry Outcome - Scrum Won | 22m侵入後にスクラム獲得 |
| 22 Entry Outcome - Kick Turnover | 22m侵入後にキックでターンオーバー |
| 22 Entry Outcome - Turnover | 22m侵入後にターンオーバー |
| 22 Entry Outcome - Drop Goal | 22m侵入後にドロップゴール |

**ActionResultName（22エントリー得点）**

| 名称 | 説明 |
|------|------|
| 22 Entry Points - Try and Conversion | トライ＋コンバージョン成功 |
| 22 Entry Points - Try without Conversion | トライのみ（コンバージョン失敗） |
| 22 Entry Points - Penalty Try | ペナルティトライ |
| 22 Entry Points - Penalty Goal | ペナルティゴール |
| 22 Entry Points - Drop Goal | ドロップゴール |

---

### ACTION ID = 34 ｜ PLAYMAKER OPTIONS（プレーメーカーオプション）
ブレイクダウンまたはセットピースの根元でボールを受けるか、最初の3レシーバー。

**ActionTypeName**

| 名称 | 説明 |
|------|------|
| Halfback at Breakdown | 指定SHがブレイクダウン/セットピースからボールを出す |
| Acting Halfback at Breakdown | SH以外の選手がSHとして機能 |
| First Receiver | 第1レシーバー |
| Second Receiver | 第2レシーバー |
| Third Receiver | 第3レシーバー |

**ActionResultName**

| 名称 | 説明 |
|------|------|
| Playmaker Option - Carry | プレーメーカーポジションからキャリー |
| Playmaker Option - Kick | プレーメーカーポジションからキック |
| Playmaker Option - Pass | プレーメーカーポジションからパス |

---

## 共通 Qualifier：チームの移動方向（Team Movement）

スクラム・ラインアウト・ラックなどの後に使用。次ブレイクダウン/ポゼッション終了地点の相対位置。

| 名称 | 説明 |
|------|------|
| Wide Left/Right Open Movement | 前ブレイクダウンから30m超、左/右、オープンサイド |
| Mid Left/Right Open Movement | 10〜30m、左/右、オープンサイド |
| Mid Left/Right Blindside Movement | 10〜30m、左/右、ブラインドサイド |
| Close Left/Right Open Movement | 2〜10m、左/右、オープンサイド |
| Close Left/Right Blindside Movement | 2〜10m、左/右、ブラインドサイド |
| Tight Left/Right Open Movement | 0〜2m、左/右、オープンサイド |
| Tight Left/Right Blindside Movement | 0〜2m、左/右、ブラインドサイド |
| N/A Movement | 同地点からのプレー |

---

## よく使うフィルター例

```python
# Box/Bomb キックのみ（Spears）
df[(df['actionName'] == 'Kick') & (df['ActionTypeName'].isin(['Box', 'Bomb']))]

# 相手22m侵入イベント
df[df['actionName'] == 'Attacking 22 Entry']

# ラインブレイク
df[(df['actionName'] == 'Attacking Qualities') & (df['ActionTypeName'] == 'Initial Break')]

# ポゼッション集計（攻撃チーム視点）
df[df['actionName'] == 'Possession']

# ペナルティ（相手に与えた）
df[(df['actionName'] == 'Penalty Conceded') & (df['team_id'] == KUBO_TEAM_ID)]
```
