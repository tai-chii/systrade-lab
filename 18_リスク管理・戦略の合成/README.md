# リスク管理・戦略の合成 — 検証 28 件

> この表は生成物（2026-11-20）。手法・場所・判定の型は AI が付け、迷いのあるものと抜き取りを別の目で確かめた。

[← 目次](../README.md)

| 支持 | 棄却 | 未確定 | 記述・点検 | 記載なし・未実行 |
|---|---|---|---|---|
| 4 | 13 | 7 | 3 | 1 |

場所: 指数・商品 3・複数の資産 22・日本株 1・米国株 1・暗号資産 1

| Q | 問い | 場所 | 判定 | 判定の文 | 学び | フォルダ |
|---|---|---|---|---|---|---|
| Q142 | 高ボラ局面では順張りの的中率と純損益が下がるか（15銘柄・GARCH なしの実現ボラ） | 複数の資産 | 未確定 | 未確定（事後発見の向きは4通り一致、大きさは半期では届かず・全期間は2/4 で ／z／≥2・主に XAUUSD と v… |  | [vol-regime-trend-following](vol-regime-trend-following/) |
| Q145 | 戦略の日次ポジションを平均の向きに圧縮したとき、向きが離れたペアは履歴の相関も低いか（Nunes 2026 を 12 戦略 × 15銘柄で） | 複数の資産 | 支持 | 向きの選別は履歴の違いを保証しないが、基準率より改善する（Nunes と同じ） |  | [signal-direction-compression](signal-direction-compression/) |
| Q161 | XAUUSD 単銘柄・直前20〜60日の実現ボラが高い日に翌日の順張り損益が下がるか（ドリフト除去・前後半） | 指数・商品 | 未確定 | 未確定（6/6 で向き一致・／z／≥2 達成は 3/6 で窓40・60日に偏る・ドリフト除去は結論を変えない） |  | [xauusd-vol-regime-single](xauusd-vol-regime-single/) |
| Q204 | ATR 倍の損切りは 15 銘柄の日足順張りの純損益と最大下落を改善するか（Kaminski・Lo 2014 の型） | 複数の資産 | 未確定 | 未確定（純損益の改善なし）／最大下落は確実に改善（記述） |  | [atr-stop-loss-tsmom](atr-stop-loss-tsmom/) |
| Q205 | ボラ・ターゲティング（σ60 で規模調整）は 15 銘柄の日足順張りの年ごとのシャープを上げるか（Harvey ほか 2018 の追試） | 複数の資産 | 支持 | 支持（確定・事前登録どおり） |  | [vol-targeting-tsmom](vol-targeting-tsmom/) |
| Q210 | エクイティカーブ・トレーディング（戦略の直近損益で規模を変える）は 15 銘柄の順張りの標本外成績を上げるか | 複数の資産 | 棄却 | 棄却 |  | [equity-curve-trading](equity-curve-trading/) |
| Q221 | 合図の確認フィルタ（k 日連続同符号で入る）は 15 銘柄の順張りのホイップソーを減らし純損益を上げるか | 複数の資産 | 未確定 | 未確定 |  | [signal-confirmation-filter](signal-confirmation-filter/) |
| Q232 | Parkinson レンジボラでのボラ・ターゲティングは終値 σ60 版よりシャープが高いか（Q222 × Q205 の連鎖） | 複数の資産 | 棄却 | 棄却 |  | [parkinson-vol-targeting](parkinson-vol-targeting/) |
| Q246 | ADX(14) > 25 の局面に限ると、順張りの純損益は上がるか（15 銘柄・月ブロック並べ替え帰無） | 複数の資産 | 棄却 | 棄却: 局面フィルタでは変わらない（Q142・Q221 と同じ） |  | [adx-filter-tsmom](adx-filter-tsmom/) |
| Q250 | ヒステリシス帯（±θσ の不感帯）は順張りの合図反転を減らし純損益を上げるか（15銘柄） | 複数の資産 | 棄却 | 棄却: 差は見えない |  | [hysteresis-band-tsmom](hysteresis-band-tsmom/) |
| Q251 | 時間ストップ（N 日で強制手仕舞い・再合図まで待つ）は順張りの純損益と最大下落を改善するか（15銘柄） | 複数の資産 | 支持 | 支持: 時間ストップは最大下落を浅くするが純損益は上げない（Q204 と同じ型） |  | [time-stop-tsmom](time-stop-tsmom/) |
| Q252 | 利食い目標（k·ATR）は順張りの純損益を上げるか下げるか（15銘柄・Q204 の損切りの対） | 複数の資産 | 記述・点検 | Q204 と同じ「保険」型 |  | [profit-target-tsmom](profit-target-tsmom/) |
| Q254 | 逆エクイティカーブ（直近20日損益が負なら規模1.5）は Q210 の負の自己相関を利益に変えるか（15銘柄） | 複数の資産 | 棄却 | 棄却: Q210 の負の自己相関は利益にできない |  | [anti-equity-curve](anti-equity-curve/) |
| Q258 | 15銘柄の直近60日平均ペア相関が高い月は順張り束のシャープが低いか（相関レジーム） | 複数の資産 | 棄却 | 棄却 |  | [correlation-regime-tsmom](correlation-regime-tsmom/) |
| Q305 | TREND7 日足の買い持ちを直前 20 日実現ボラの逆数で規模調整するとシャープは同じ重み分布の循環シフトより高いか（Moreira–Muir の CFD 移植） | 指数・商品 | 未確定 | 未確定 |  | [vol-managed-buyhold-trend7](vol-managed-buyhold-trend7/) |
| Q377 | 予測ボラを上振れだけ使う非対称サイジング（σ_used=max(σ̂_HAR, σ60)）は対称版・σ60 版より S07 TSMOM60 の規程モードで最大下落が浅く、シャープを落とさないか | 複数の資産 | 記載なし・未実行 | — |  | [s04b-asymmetric-vol-sizing-q377](s04b-asymmetric-vol-sizing-q377/) |
| Q382 | 48 銘柄 D1 の TSMOM60 × SMA200 同符号ゲート × 時間ストップ 20 日の合成（部品は既存値で固定・掃引なし）は規程モードの封印前の前後半で t≥2 かつ最大下落 −6% 以内か | 複数の資産 | 棄却 | 棄却 |  | [s02-tsmom60-sma200-timestop-wide48-q382](s02-tsmom60-sma200-timestop-wide48-q382/) |
| Q388 | 水準 HAR-RV（銘柄別 OLS）の σ̂ を size_weights の σ に渡した S07 TSMOM60 の規程モードは、σ60 版より最大下落が浅く Sharpe が高いか（較正を前提条件とし σ̂ 並べ替え帰無で判定。Q376 の偏りを除いた再判定・Q377 の前提） | 複数の資産 | 棄却 | 棄却 |  | [s04b-vol-sizing-calibrated-q388](s04b-vol-sizing-calibrated-q388/) |
| Q396 | 48 銘柄 D1 の TSMOM60 に実測スプレッドの z（250 日）>2 の日は休む流動性ゲートを足すと、ゲートなし（S07 本体と同じ合図）より規程モードの最大下落が浅く前後半の t が高いか | 複数の資産 | 棄却 | 棄却 |  | [s11-spread-stress-gate-tsmom-q396](s11-spread-stress-gate-tsmom-q396/) |
| Q411 | 15 銘柄 H1→D1 の TSMOM60 を tick 出来高の増加（V20/V250 ≥ 1）の日だけ持つゲートは、ゲートなしより規程モードの前後半 t と最大下落を改善するか | 複数の資産 | 棄却 | 棄却 |  | [s14-volume-gate-tsmom60-all15-q411](s14-volume-gate-tsmom60-all15-q411/) |
| Q425 | 弱い正の 3 族（キャリー符号 FX22・BTC/ETH TSMOM60・FX22 TSMOM60）を事前固定の等リスク 1/3 合成にした 1 本は、規程モードで封印前の前後半とも年単位 t≥2 かつ最大下落 −6% 以内か（S16 本体・合成 1 本のみ・掃引しない） | 複数の資産 | 未確定 | 未確定 |  | [s16-three-family-equal-risk-composite-q425](s16-three-family-equal-risk-composite-q425/) |
| Q461 | 選び直す WFO で直前窓の全候補が負なら休むと、常に最良を選ぶより標本外は良くなるか | 複数の資産 | 棄却 | 全候補が負なら休む規則は、15 銘柄の日足 TSMOM の選び直し WFO では純損益も最大下落もほとんど変えない（B… |  | [wfo-rest-if-all-negative-q461](wfo-rest-if-all-negative-q461/) |
| Q469 | S18 低相関 4 族（キャリー符号 FX22・BTC/ETH TSMOM60・FX22 TSMOM60・株価指数 10 の買い持ち β）の事前固定 1/4 等リスク合成は、規程モード C1（σ0.25%/日）で封印前の前後半とも年単位 t≥2 かつ最大下落 −6% 以内か（合成 1 本のみ） | 複数の資産 | 未確定 | 初めて max_dd の関門（−6%）を通り、等金額の z も 2 を超えたが、年単位 t が前半 0.97・後半 1… |  | [s18-four-family-equal-risk-composite-c1-q469](s18-four-family-equal-risk-composite-c1-q469/) |
| Q473 | S19 VIX リスクオフ・ゲート: 株価指数 10 の買い持ち β を VIX（t−1）が直近 250 観測の 80 分位以下の日だけ持つと、常時買い持ち（Q468 params 1）より規程 C1 で t_all・max_dd が良くなり、C1 関門（前後半 t≥2・max_dd −6%）を通るか | 指数・商品 | 棄却 | VIX の水準ゲートは株価指数の買い持ちを改善しない。むしろ高 VIX 日を外すことで平均リターンの高い日を捨て、t … |  | [s19-vix-riskoff-gate-index-beta-c1-q473](s19-vix-riskoff-gate-index-beta-c1-q473/) |
| Q569 | 暗号資産の四半期先物の年率ベーシスが高い日に S23 を休むと、S23 の損益は上がるか | 暗号資産 | 棄却 | 棄却（機械判定どおり） |  | [crypto-basis-gate-s23-q569](crypto-basis-gate-s23-q569/) |
| Q586 | S30 の composite 関門（生き残り 3 本との相関・等リスク合成）と仮想フォワード記録スクリプト | 日本株 | 支持 | 通過 | 相関は源が違えば自然に低い（−0.07／0.04／0.03）。問題は単体の強さで、重なりの切り方で Sharpe が 1.15 にも 0.28 にも見える。合成の判定は 12 か月の前向き系列で 1 回だけ | [s30-composite-gate-q586](s30-composite-gate-q586/) |
| — | リバランス頻度とリスク尺度のどちらが成績差を支配するか（米国セクター ETF） | 米国株 | 記述・点検 | README の「主な検証」表を参照 |  | [rebalance-frequency](rebalance-frequency/) |
| — | 生き残り 3 本（S17b・S21 候補形・S23）の相関と合成（記述・2026-10-29） | 複数の資産 | 記述・点検 | — |  | [survivors-correlation-composite](survivors-correlation-composite/) |
