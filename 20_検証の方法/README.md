# 検証の方法（統計・データの点検） — 検証 49 件

> この表は生成物（2026-11-20）。手法・場所・判定の型は AI が付け、迷いのあるものと抜き取りを別の目で確かめた。

[← 目次](../README.md)

| 支持 | 棄却 | 未確定 | 記述・点検 | 記載なし・未実行 |
|---|---|---|---|---|
| 21 | 15 | 6 | 4 | 3 |

場所: FX 1・複数の資産 28・日本株 1・場所によらない 19

| Q | 問い | 場所 | 判定 | 判定の文 | 学び | フォルダ |
|---|---|---|---|---|---|---|
| Q137 | データ提供元の違い（Dukascopy vs Yahoo）で順張りの合図は何割一致し、純損益はどれだけ変わるか | 複数の資産 | 支持 | 「データ源は規則の定義の一部（Korzan と同じ）」→ 確定 |  | [data-source-signal-agreement](data-source-signal-agreement/) |
| Q138 | 予測の当たりやすさ（IC）と決定の損失（コスト後の純損益）はどれだけ食い違うか | 場所によらない | 未確定 | 未確定 |  | [ic-vs-decision-loss](ic-vs-decision-loss/) |
| Q139 | 候補数 J を増やすと選択の楽観はどれだけ増え、Alonso の下側限界はそれを覆うか | 場所によらない | 支持 | 単調性「支持」・限界「使える」 |  | [selection-optimism-vs-J](selection-optimism-vs-J/) |
| Q141 | 悪い時期を重くする目的関数で選んだ順張りは、標本外の最大下落が小さいか（TradeGrad の CPRO の型） | 複数の資産 | 棄却 | 棄却（確定） |  | [bad-period-weighted-selection](bad-period-weighted-selection/) |
| Q144 | 2か月の成績はランダム売買の分布のどこに入るか、順位は次の2か月で入れ替わるか（15銘柄・TSMOM20） | 複数の資産 | 支持 | 支持（2か月では実力と運を分けられず順位も入れ替わる） |  | [two-month-live-vs-random](two-month-live-vs-random/) |
| Q146 | 並べ替え帰無の z は何回で安定するか（B と seed のぶれ。検証基盤の既定 B を決めるため） | 場所によらない | 記載なし・未実行 | — |  | [permutation-null-stability](permutation-null-stability/) |
| Q147 | 翌日の方向の的中率は「常に上」「前日の符号」の基準率を超えるか（HSAT の基準の置き方） | 複数の資産 | 棄却 | 確定 |  | [direction-accuracy-vs-base-rate](direction-accuracy-vs-base-rate/) |
| Q148 | 弱い形の効率性の検定（分散比）の結論は、設定（q・期間）でどれだけ動くか（Alahmadi・Basingab 2026 §3.5） | 場所によらない | 記述・点検 | 1年の日足では分散比検定そのものがほとんど棄却しない（名目 5% 以下）。「1つの q で非効率と出ても他の q では… |  | [variance-ratio-setting-dependence](variance-ratio-setting-dependence/) |
| Q149 | 分散比で「予測できる」と出た組は、次の期間にコスト後で儲かるか（Alahmadi 2026 §3.4.1 の変換率） | 複数の資産 | 棄却 | 前後半とも (b) の t<2 で事前の規則どおり「変換されない」。点推定も前後半とも負で、予測できる組は予測できない… |  | [predictability-to-profit-conversion](predictability-to-profit-conversion/) |
| Q150 | 15銘柄から成績の良い 8 銘柄を事後に選ぶと順張りの成績はどれだけ膨らむか（Korzan 2026 §6 の銘柄選択バイアス） | 複数の資産 | 支持 | 支持（確定）。選んだ銘柄は後半でむしろ劣る（反転）。膨らみが帰無の95%点をわずかに超えるのはその反転の裏返し（帰無は… |  | [instrument-selection-bias](instrument-selection-bias/) |
| Q154 | WRC・SPA(consistent)・SPA(conservative) の判定は同じルール群でどれだけ割れるか | 場所によらない | 支持 | 確定（棄却） |  | [wrc-spa-disagreement](wrc-spa-disagreement/) |
| Q155 | 検証とテストの間のエンバーゴ日数で順張りの標本外成績はどれだけ変わるか | 複数の資産 | 未確定 | e=0 に楽観の方向はあるが、事前登録の第一指標が有意に届かなかった |  | [embargo-length-effect](embargo-length-effect/) |
| Q168 | CPRO 本式（Yang 2026 TradeGrad の正格な実装）で順張りの参照日数を選んでも、翌年の最大下落は A と区別がつかない | 複数の資産 | 棄却 | 棄却（確定） |  | [cpro-exact-selection](cpro-exact-selection/) |
| Q171 | 順張りの参照日数 60 通りの CSCV で測った過剰適合の確率 PBO は約 0.88（Bailey 2017） | 複数の資産 | 支持 | 支持（過剰適合） |  | [pbo-cscv-tsmom](pbo-cscv-tsmom/) |
| Q171 | 順張りの参照日数60通りの CSCV で過剰適合の確率 PBO はいくつか（Bailey 2017） | 複数の資産 | 記載なし・未実行 | —（未実行） |  | [pbo-tsmom-grid](pbo-tsmom-grid/) |
| Q172 | BBC-CV のブートストラップ補正は時系列の順張り選択の楽観を取り除くか（Tsamardinos 2018） | 場所によらない | 記載なし・未実行 | —（未実行） |  | [bbc-cv-optimism](bbc-cv-optimism/) |
| Q172 | BBC-CV のブートストラップ補正は時系列の順張り選択の楽観を取り除くか（Tsamardinos 2018） | 複数の資産 | 支持 | 確定 |  | [bbc-cv-tsmom-optimism](bbc-cv-tsmom-optimism/) |
| Q175 | 15銘柄を束ねた t は日でクラスタさせると素朴な t から何割下がるか（GarciaArano 2026-3） | 複数の資産 | 支持 | 支持（確定） |  | [cluster-t-shrinkage](cluster-t-shrinkage/) |
| Q177 | 順張りの参照日数を選び直す頻度（月・四半期・半年・年）で標本外成績は変わるか（Zarrabi 2017） | 複数の資産 | 棄却 | ノイズ |  | [reselection-frequency](reselection-frequency/) |
| Q178 | 帰無モデルの選び方（並べ替え・AR(1)・GARCH型）で移動平均ルールの判定は変わるか（Brock 1992） | 場所によらない | 支持 | 確定（H1 支持: 帰無の選び方で判定はほぼ割れない） |  | [null-model-choice](null-model-choice/) |
| Q184 | 2か月窓の順張り成績はその窓の実現ボラとドリフトで説明できるか（Rashid 2026-1・Q144 の続き） | 複数の資産 | 棄却 | Rashid の「ボラに左右される」は向きが違う |  | [window-pnl-vs-vol](window-pnl-vs-vol/) |
| Q188 | 周辺パラメータの平均で選ぶ（台地選択）と最良1点で選ぶより標本外が良いか（ブログZenn2026e-2） | 場所によらない | 棄却 | H0: 選び方では変わらない |  | [parameter-plateau-selection](parameter-plateau-selection/) |
| Q189 | ランダム分割の交差検証は時系列分割より順張り選択の楽観をどれだけ膨らませるか（Roelofs 2019-2） | 複数の資産 | 棄却 | 符号は仮説と逆（ランダム分割の方が時系列分割より楽観が小さい）だが、有意ではない |  | [random-vs-chrono-split](random-vs-chrono-split/) |
| Q211 | 日足の区切り時刻（0・8・13・17・21 UTC）で順張りの純損益はどれだけ変わるか（帰無: 区切りをランダムに選ぶ） | 複数の資産 | 棄却 | 棄却 |  | [daily-cutoff-hour-dependence](daily-cutoff-hour-dependence/) |
| Q230 | 順張りの純損益は上位 1% の日に集中しているか: 最大の k 日を除くと年単位の t が 2 を切るか（15 銘柄 D1） | 複数の資産 | 未確定 | 未確定: all15 の t_full が 2 未満の期間があり集中を問えない |  | [tsmom-pnl-concentration](tsmom-pnl-concentration/) |
| Q244 | 参照日数の選択窓の長さ（1・2・3・5・8 年）で、順張りの標本外純損益は変わるか（15 銘柄） | 複数の資産 | 棄却 | 棄却: 窓の長さでは変わらない（Q177・Q188 と同じ） |  | [selection-window-length](selection-window-length/) |
| Q260 | 参照日数60通りから選んだ最良は Deflated Sharpe Ratio で補正すると何銘柄で残るか（Bailey・López de Prado 2014） | 複数の資産 | 支持 | 効果なし（支持＝最良の参照日数は DSR 補正で残らない） |  | [deflated-sharpe-lookback](deflated-sharpe-lookback/) |
| Q278 | 前後半の分割年を 2014〜2020 で動かすと「前後半とも同符号 t≥2」の判定は何割割れるか（基盤・簡単な規則群） | 場所によらない | 未確定 | 未確定寄りのトリビアル支持 |  | [split-year-sensitivity](split-year-sensitivity/) |
| Q288 | : D1_fromH1 の WTI・UKOIL・US500・USTECH にある 2011-09〜2012-01 の空白は取得失敗か提供元の欠落か | 複数の資産 | 支持 | H1 データの取得失敗が原因。提供元（Dukascopy D1）は欠落していない |  | [d1-fromh1-gap-check](d1-fromh1-gap-check/) |
| Q295 | 15 銘柄 H1 のクラスター t（時刻束ね）は naive パネル t より 30% 以上縮むか | 複数の資産 | 棄却 | ノイズ |  | [cluster-t-h1-shrinkage](cluster-t-h1-shrinkage/) |
| Q299 | 通貨強度（対ドル 6 本の L 本リターン平均・7 通貨）は、クロス 2 本（EURJPY・GBPJPY）を足した最小二乗版と H1 の L=24/120/480 時間で相関 0.99 以上か（クロスは冗長か） | FX | 支持 | 確定（支持: クロスは冗長） |  | [currency-strength-cross-redundancy](currency-strength-cross-redundancy/) |
| Q307 | 同じ特徴量の分類器で、ラベルを同日にすると上げ下げの精度は跳ね、翌日では基準率に落ちるか（HSAT の精度 0.69 はリークで再現できるか・Q306-C1） | 場所によらない | 棄却 | 翌日の予測力なし（確定）・論文の0.69の由来は未確定 |  | [same-day-label-leak](same-day-label-leak/) |
| Q310 | 月次（約 220 か月）に束ねた 15 銘柄の順張りルール群で、並べ替え帰無の下の WRC・SPA の棄却率は名目 5% を超えるか（Q154 の月次版・Q309-C1） | 場所によらない | 支持 | 支持 |  | [wrc-spa-monthly-size](wrc-spa-monthly-size/) |
| Q314 | 順張りの利益は少数の取引に集中するか: 最良 1 取引の総利益比を、同じ取引数・保有期間で入る時期だけランダムにした帰無と比べる（Q313-C1・ブログの 91% は普通か異常か） | 複数の資産 | 未確定 | 未確定 |  | [trade-profit-concentration](trade-profit-concentration/) |
| Q320 | 手元の標準の判定は、15 銘柄の順張り損益の実際の ϕ1・歪度に合わせた腕なしの合成探索で名目 5% を守るか（Canli 2026 Null Zoo の移植・Q319-C1） | 複数の資産 | 支持 | 歪みは確定。ただし原因は ϕ1・歪度（Null Zoo の筋）ではなく、銘柄間の相関を、銘柄ごとに別々の並べ替えで壊す… |  | [null-zoo-size-q320](null-zoo-size-q320/) |
| Q321 | 束ねた年内並べ替えを全銘柄共通の（日付の）並べ替えにすると、腕なしの合成でサイズが名目 5% に戻るか（Q320 の次段階） | 場所によらない | 支持 | 銘柄ごとの年内並べ替えは、現実型の帰無でも膨らむ（12.4%）。Q320 の 16% は合成の作りだけのせいではない。… |  | [common-perm-size-q321](common-perm-size-q321/) |
| Q322 | 銘柄ごとの年内並べ替えを束ねて「支持・確定」とした Q183・Q212・Q205 を、日付共通の並べ替えで再判定する（Q321 の次段階） | 場所によらない | 支持 | z は 3 件とも 0.4〜0.9 倍に縮んだ（帰無が広がった）。週末ラベルが全通貨で同じ Q212 は後半で 1/2… |  | [common-perm-rejudge-q322](common-perm-rejudge-q322/) |
| Q326 | 順張りの参照日数60本の順位表 L(j) は上位ほど悪いか・格子を広げるほど選択の翌年は悪くなるか（Wang 2026 BT-2 を手元へ・Q325-C1） | 複数の資産 | 棄却 | ノイズ（幅は選択を良くも悪くもしない、と区別できない） |  | [leaderboard-width-tsmom-q326](leaderboard-width-tsmom-q326/) |
| Q333 | WFO の「プラスの窓が60%以上」の関門は、腕のない順張りを何%通し、本物の優位を何%落とすか（Q331-C1） | 場所によらない | 支持 | 確定（使えない）。主因は検出力 |  | [wfo-window-gate-q333](wfo-window-gate-q333/) |
| Q338 | 手元の検証の全体に偽発見率の補正を当てると「効果あり」のうち何本残るか（Chang ら 2026 を自分の台帳へ・Q336-C3） | 場所によらない | 支持 | 確定 |  | [ledger-fdr-q338](ledger-fdr-q338/) |
| Q354 | Q160 の確定は評価期間の端点を ±1 年ずらした 9 通りで何通り保たれるか（方法論・確定判定の端点感度） | 複数の資産 | 支持 | 確定（Q160 の確定は端点依存。商品4 の買い側の上乗せは 9/9 で頑健だが、BTC 除外トレンド6 は最新の半年… |  | [q160-endpoint-sensitivity](q160-endpoint-sensitivity/) |
| Q416 | 関門（σ0.5%/日・14 年の最大下落 −6% 以内＋前後半 t≥2）は年率シャープ S がいくら以上の戦略を何割通すか（S07 規程モード損益の 20 日ブロック・ブートストラップで S を 0〜3 に合わせて測る） | 場所によらない | 棄却 | 棄却（関門が律速） |  | [gate-pass-probability-vs-sharpe-q416](gate-pass-probability-vs-sharpe-q416/) |
| Q417 | Runner 型の既存結果 JSON を横断し、循環シフト帰無の中心（q025 と q975 の中点）が 0 から 0.5σ 以上ずれる割合と、そのずれが z と年単位 t の食い違いを説明するか | 場所によらない | 支持 | 支持（仕組みの変更が要る） |  | [null-center-bias-runner-results-q417](null-center-bias-runner-results-q417/) |
| Q418 | 48 銘柄 D1_fromH1 の銘柄×年の足の本数の一覧と、本数 126 未満の年を年単位 t から除くと TSMOM60 等金額の前後半 t がどれだけ動くか（by_year_stats の min_rows 既定の見直し） | 複数の資産 | 支持 | 支持 |  | [bars-per-year-audit-wide48-q418](bars-per-year-audit-wide48-q418/) |
| Q428 | 関門の候補 C1（σ 目標 0.25%／0.35%/日・最大下落 −6%）と C2（最大下落 ≥ −0.75×年率 σ）は年率シャープ S の戦略を何割通し、1 年以内の −6%／−10% 到達率はいくらか（Q416 の S07 ブロック・ブートストラップを規程の変種に当てる・★ C の判断材料） | 場所によらない | 記述・点検 | ★ C の実質の選択肢は C1 の σ の値。σ0.25% なら関門が S≈1.4 で半数を通す（現行は S≈2.7）… |  | [gate-candidates-c1-c2-pass-probability-q428](gate-candidates-c1-c2-pass-probability-q428/) |
| Q449 | wide48 D1 の高ボラ局面の方向的中率の上乗せは基準率と MRS 平滑化ラベルの先読みで説明されるか | 複数の資産 | 棄却 | ノイズ |  | [wide48-regime-hitrate-baserate](wide48-regime-hitrate-baserate/) |
| Q455 | 日足戦略の封印前の純損益は特定の年に集中しているか（年別寄与の上位 1・2 年を除いた年単位 t） | 複数の資産 | 記述・点検 | 規則の上では 9 本すべて「集中あり」だが、9 本中 8 本は元の年単位 t が 2 未満で「除くと t<2」の枝が自… |  | [year-concentration-top2-q455](year-concentration-top2-q455/) |
| Q562 | 日本株・米国株の無料データ層（基盤・2026-10-28） | 日本株 | 未確定 | 価格層は基盤として通過、需給層は未達（毎日蓄積中） |  | [equities-free-data-q562](equities-free-data-q562/) |
| — | 検証ログの採点基準の事後検証 | 場所によらない | 記述・点検 | README の「主な検証」表を参照 |  | [report-scoring](report-scoring/) |
