# 時系列モメンタム（トレンド） — 検証 51 件

> この表は生成物（2026-11-20）。手法・場所・判定の型は AI が付け、迷いのあるものと抜き取りを別の目で確かめた。

[← 目次](../README.md)

| 支持 | 棄却 | 未確定 | 記述・点検 | 記載なし・未実行 |
|---|---|---|---|---|
| 3 | 29 | 17 | 1 | 1 |

場所: FX 6・指数・商品 11・複数の資産 24・日本株 1・米国株 1・暗号資産 8

| Q | 問い | 場所 | 判定 | 判定の文 | 学び | フォルダ |
|---|---|---|---|---|---|---|
| Q136 | トレンドの持続時間が長い期間ほど、順張りはコスト後に儲かるか | 複数の資産 | 棄却 | H1・H2 とも棄却 |  | [trend-persistence-vs-tf-pnl](trend-persistence-vs-tf-pnl/) |
| Q143 | 順張りの純損益の減衰は指数か、それとも最初から0か（Feng 2026 の半減期を FX8・トレンド7 で） | 複数の資産 | 未確定 | 主 TSMOM20: FX8 は「未確定（Q063 と同じ）」／トレンド7 は「一定（減衰ではない）」（副 ドンチャン… |  | [trend-pnl-half-life](trend-pnl-half-life/) |
| Q151 | 12か月リターン>0 かつ 200日線上で保有・外れたら現金の規則は、循環シフトの帰無より下落が浅いか（Korzan の規則を15銘柄で） | 複数の資産 | 支持 | 確定 |  | [tsmom12m-ma200-cash-rule](tsmom12m-ma200-cash-rule/) |
| Q152 | 順張りの利益は買い側だけか: 売り側はコスト後に0と区別できるか | 複数の資産 | 未確定 | 未確定（売り側に利益なしは確定。買い側の順張りは機械判定では支持だが、BTC・後半・ドンチャンに依存） |  | [long-short-decomposition](long-short-decomposition/) |
| Q182 | 複数の順張り指標が一致したときだけ売買すると的中率と純損益は上がるか（Loubaris 2026-2） | 複数の資産 | 棄却 | 棄却（Loubaris と同じ非有意） |  | [indicator-confirmation](indicator-confirmation/) |
| Q186 | 週足の順張りは日足より強いか（Neely 2003-3・15銘柄・2008〜2026） | 複数の資産 | 棄却 | 棄却（前後半のどちらかで ／t／<2） |  | [weekly-vs-daily-tsmom](weekly-vs-daily-tsmom/) |
| Q207 | ・Q224 危機アルファ：US500 の下落局面で順張りは正の損益か（Hurst・Ooi・Pedersen 2017 の型） | 指数・商品 | 未確定 | 原典型 TSMOM（1/3/12か月合成・σ60値幅目標）は US500 の下落局面で合計 +189 bp・6 局面中… |  | [crisis-alpha-tsmom](crisis-alpha-tsmom/) |
| Q208 | ドル因子（6 通貨の対ドル等加重）の順張りは個別ペアの順張りの平均より強いか（Verdelhan 2018 の型） | FX | 棄却 | 棄却 |  | [dollar-factor-momentum](dollar-factor-momentum/) |
| Q216 | 出来高（ティック数）が多い日のリターンは翌日に続きやすく、少ない日は反転しやすいか（Campbell・Grossman・Wang 1993 の型・15 銘柄） | 複数の資産 | 棄却 | 棄却（CGW の型の反転は FX+コモディティ+指数の日足では前後半揃って再現しない） |  | [volume-return-interaction](volume-return-interaction/) |
| Q223 | 参照日数の集合（20・60・120・250 の合図平均）は最良単一の参照日数より標本外で良いか（Baltas・Kosowski の型） | 複数の資産 | 棄却 | ノイズ: 合図平均と最良単一の差は前後半で揃わず事前固定の t≥2 または t≤−2 のどちらも通らない |  | [lookback-ensemble-tsmom](lookback-ensemble-tsmom/) |
| Q235 | ティック出来高の急増つきドンチャン・ブレイクアウトは、継続率と純損益を上げるか（15 銘柄・H1 出来高から日足） | 複数の資産 | 棄却 | 棄却 |  | [volume-confirmed-breakout](volume-confirmed-breakout/) |
| Q249 | 順張りの合図強度（／ret_L／/σ）の3分位で翌日の純損益は単調に増えるか（15銘柄・sign と強度の対比） | 複数の資産 | 棄却 | 棄却 |  | [signal-strength-terciles](signal-strength-terciles/) |
| Q253 | トレンドの年齢（合図反転からの経過日数）が短いほど翌日の順張り損益は高いか（15銘柄） | 複数の資産 | 未確定 | 未確定 |  | [trend-age-pnl](trend-age-pnl/) |
| Q257 | 順張り束の月次損益は US500 月次リターンの 2 次関数（スマイル）か（Fung・Hsieh 2001／Moskowitz 2012 の型） | 複数の資産 | 棄却 | 棄却: 全期間 z<1 |  | [tsmom-smile-quadratic](tsmom-smile-quadratic/) |
| Q261 | トレンド7 の H4 順張り（TSMOM 30/60/120 本）はコスト後に残るか（為替で消えた H4 の条件の穴） | 複数の資産 | 支持 | 支持: trend7 全期間 純損益 t<2 または z<2（H4 には無い） |  | [h4-tsmom-trend7](h4-tsmom-trend7/) |
| Q262 | 暗号資産11通貨の日足順張り（TSMOM 20/60/120）は 2022 年以降もコスト後に残るか | 暗号資産 | 棄却 | 最初から無い: 前半 t<2（別の確定） |  | [crypto-d1-tsmom](crypto-d1-tsmom/) |
| Q264 | 暗号資産11通貨の H1 の分散比は 2022 年以降に 1 へ近づいたか（適応的市場仮説の移植） | 暗号資産 | 棄却 | 棄却 |  | [crypto-variance-ratio-trend](crypto-variance-ratio-trend/) |
| Q290 | 暗号資産 11 通貨 H1 の 24 本 TSMOM（L=24）はコスト後に前後半とも正か（Neely2003-3 の暗号 H1 移植） | 暗号資産 | 棄却 | 棄却 |  | [crypto-h1-tsmom](crypto-h1-tsmom/) |
| Q291 | FX8 H1 の 3 指標（TSMOM24・SMA50・RSI14 符号）が同符号のときだけ売買すると、束ねた t はコスト後に単独 TSMOM24 を上回るか（Loubaris2026-2 の H1 移植） | FX | 棄却 | 棄却 |  | [fx8-h1-triple-indicator](fx8-h1-triple-indicator/) |
| Q292 | 15 銘柄 D1 の二周期ローテーション規則（L=20 と L=120 の TSMOM が同符号時のみ ±1）は、単独 TSMOM60 より all15 の年単位平均 bp（コスト後）が高いか（Korzan2026-1 の規則の移植） | 複数の資産 | 未確定 | 15 銘柄平均で見ると支持だが、群で分かれる |  | [dual-lookback-rotation](dual-lookback-rotation/) |
| Q294 | 15 銘柄 D1 の 1 次自己相関は高ボラ月で低ボラ月より高いか | 複数の資産 | 棄却 | 棄却 |  | [vol-regime-autocorr](vol-regime-autocorr/) |
| Q298 | 暗号資産 11 通貨 H1 の 3 ルール群（TSMOM24・SMA50・RSI14 の 50 水準順張り）はコスト後に全て前後半で正か（Neely2003-2 の暗号 H1 移植） | 暗号資産 | 棄却 | 棄却 |  | [crypto-h1-rules-battery](crypto-h1-rules-battery/) |
| Q302 | 暗号資産 11 通貨日足の 200 日線（終値>SMA200 で買い・下で現金）の最大下落は同じ露出の循環シフトより浅いか（Q097/Q098 の暗号資産への移植） | 暗号資産 | 棄却 | 棄却 |  | [crypto-ma200-drawdown](crypto-ma200-drawdown/) |
| Q303 | FX8 日足の TSMOM60 で円の組 3 本の純損益はドルの組 5 本を上回るか（円の組の 4 時間足の知見の日足版・組ラベルの全 56 通り帰無） | FX | 未確定 | 未確定 |  | [yen-vs-dollar-tsmom-d1](yen-vs-dollar-tsmom-d1/) |
| Q346 | 直前の経路が滑らか（R² 高・FIP 連続的）なほど翌月の時系列モメンタム純損益は大きいか（15 銘柄・Clenow／Da ほか 2014 の移植） | 複数の資産 | 棄却 | 棄却で機械判定と同じ |  | [path-smoothness-tsmom-q346](path-smoothness-tsmom-q346/) |
| Q355 | TREND7 の D1 TSMOM 本体（L=60）は、封印前の前後半とも年単位 t≥2 で純損益がコスト後に正か（S01 の中央関門） | 指数・商品 | 未確定 | 未確定: pre t=0.61、post t=1.12 — 両方 t<2 のため S01 ゲート未通過 |  | [trend7-d1-tsmom-core-q355](trend7-d1-tsmom-core-q355/) |
| Q356 | TREND7 D1 TSMOM の L ∈ {20,60,120,250} の掃引で、main（L=60）は Holm m=4 補正後も封印前の前後半で t≥2 を保つか（S01 の lookback 頑健性） | 指数・商品 | 未確定 | 未確定 |  | [trend7-d1-tsmom-lookback-sensitivity-q356](trend7-d1-tsmom-lookback-sensitivity-q356/) |
| Q357 | TREND7 D1 TSMOM(L=60) の収益は商品 4（XAU/XAG/WTI/UKOIL）と株＋BTC 3（US500/USTECH/BTC）のどちらが担うか | 指数・商品 | 棄却 | 棄却 |  | [trend7-subgroup-carrier-q357](trend7-subgroup-carrier-q357/) |
| Q358 | Moskowitz 原著の 12m-1m（L=252、skip=21）TSMOM は、TREND7 D1 で封印前の前後半とも年単位 t≥2 で正か | 指数・商品 | 未確定 | 未確定 |  | [trend7-d1-moskowitz-skip1m-q358](trend7-d1-moskowitz-skip1m-q358/) |
| Q359 | TREND7 の H4 TSMOM で L を広げる（120/240/480 本 ≒ 20/40/80 日）と、Q261 の L=60（≒10 日）不支持は改善するか | 指数・商品 | 棄却 | 棄却: 広い L でも全期間 t<1 かつ前後半ともに t<2（H4 自体の問題。lookback 不足ではない） |  | [trend7-h4-tsmom-wide-l-q359](trend7-h4-tsmom-wide-l-q359/) |
| Q360 | TREND7 D1 TSMOM(L=60) を週次（月曜のみ）でリバランスしても、封印前の前後半で年単位 t≥2 を保つか（コスト低減の効果） | 指数・商品 | 未確定 | 未確定 |  | [trend7-d1-weekly-rebalance-q360](trend7-d1-weekly-rebalance-q360/) |
| Q361 | TREND7 D1 TSMOM(L=60) を long-only と short-only に分けると、どちらが bp>0 を担うか（long-only で足りるか） | 指数・商品 | 未確定 | 未確定 |  | [trend7-d1-long-vs-short-q361](trend7-d1-long-vs-short-q361/) |
| Q363 | TREND7 D1 で TSMOM 符号の等重みアンサンブル（L=20/60/120/250 の平均）は、単発 L=60 と比べて封印前の前後半で年単位 t≥2 を取りやすいか | 指数・商品 | 未確定 | 未確定 |  | [trend7-d1-tsmom-ensemble-q363](trend7-d1-tsmom-ensemble-q363/) |
| Q364 | TREND7 D1 で TSMOM(L=60) と SMA200 の上下による順張りは、封印前の前後半で年単位 t≥2 を取る合図形式がどちらか | 指数・商品 | 棄却 | TSMOM(L=60) が前後半とも年単位 t<1（pre t=0.61, post t=0.66）。SMA200 は… |  | [trend7-d1-sma200-vs-tsmom60-q364](trend7-d1-sma200-vs-tsmom60-q364/) |
| Q367 | 48 銘柄 wide48 の D1 TSMOM60（σ60 ボラ正規化・等リスク束）は封印前（〜2024-06）の前後半とも年単位 t≥2 か | 複数の資産 | 棄却 | 棄却 |  | [wide48-tsmom60-vol-target](wide48-tsmom60-vol-target/) |
| Q368 | 48 銘柄 wide48 の D1 プレーン TSMOM L=60（ボラ正規化なし・等重み）は封印前の前後半とも年単位 t≥2 か | 複数の資産 | 棄却 | 棄却 |  | [wide48-tsmom-l60-plain](wide48-tsmom-l60-plain/) |
| Q369 | 48 銘柄 wide48 の D1 プレーン TSMOM L=120（約6ヶ月・ボラ正規化なし）は封印前の前後半とも年単位 t≥2 か | 複数の資産 | 未確定 | 未確定 |  | [wide48-tsmom-l120-plain](wide48-tsmom-l120-plain/) |
| Q370 | 48 銘柄 wide48 の D1 プレーン TSMOM L=250（約12ヶ月・ボラ正規化なし）は封印前の前後半とも年単位 t≥2 か | 複数の資産 | 棄却 | 棄却 |  | [wide48-tsmom-l250-plain](wide48-tsmom-l250-plain/) |
| Q385 | BTC＋ETH の D1（H1→D1・UTC 0 時区切り・週末込み）TSMOM L∈{60,120} は規程モード（暗号版）で封印前の前半（〜2020）・後半（2021〜2024-06）とも年単位 t≥2 かつ最大下落 −6% 以内か | 暗号資産 | 未確定 | 未確定 |  | [s08-crypto2-d1-tsmom-q385](s08-crypto2-d1-tsmom-q385/) |
| Q386 | 暗号資産 11 通貨の D1（H1→D1・UTC 0 時区切り・週末込み）TSMOM L∈{60,120} は規程モード（暗号版）で封印前の前半（〜2020）・後半（2021〜2024-06）とも年単位 t≥2 かつ最大下落 −6% 以内か | 暗号資産 | 棄却 | 棄却 |  | [s08-crypto11-d1-tsmom-q386](s08-crypto11-d1-tsmom-q386/) |
| Q390 | FX22 D1 の TSMOM60 にスワップ（政策金利差 − 年 0.75% マークアップ）を損益に含めると、S07 のスワップなし（棄却）より規程モードの封印前の前後半 t・最大下落が改善し関門を通るか | FX | 棄却 | 棄却 |  | [s09-fx22-tsmom60-with-swap-q390](s09-fx22-tsmom60-with-swap-q390/) |
| Q394 | 株価指数 13＋債券 3 の D1 で、債券の 250 日リターン符号で株を持ち・株の 250 日リターンの逆符号で債券を持つクロスアセット TSMOM は規程モードで封印前の前後半（境 2021）とも年単位 t≥2 かつ最大下落 −6% 以内か | 指数・商品 | 棄却 | 棄却 |  | [s10-xasset-bond-equity-tsmom-q394](s10-xasset-bond-equity-tsmom-q394/) |
| Q395 | US500 の TSMOM60 符号が負の日は円・フランを買い（USDJPY/USDCHF/AUDJPY/NZDJPY/CADJPY 売り）正の日は逆、のリスクオフ・レジーム戦略は規程モードで封印前の前後半とも年単位 t≥2 かつ最大下落 −6% 以内か | 複数の資産 | 未確定 | 未確定 |  | [s10-equity-trend-safe-haven-fx-q395](s10-equity-trend-safe-haven-fx-q395/) |
| Q412 | 15 銘柄 H1→D1 の出来高加重 TSMOM60（直近 60 日の Σ ret_i × v_i/v̄_250 の符号）は素の TSMOM60 より規程モードの前後半 t≥2・最大下落 −6% 以内に近づくか | 複数の資産 | 未確定 | 未確定 |  | [s14-volume-weighted-tsmom60-all15-q412](s14-volume-weighted-tsmom60-all15-q412/) |
| Q529 | S23：暗号資産は上昇トレンドのときだけ買って持つ（BTCUSD・ETHUSD・TSMOM60・ロングのみ）（ほか 4 件: q537・q548・q556…） | 暗号資産 | 未確定 | 未確定 |  | [s23-crypto-uptrend-long-q529](s23-crypto-uptrend-long-q529/) |
| Q567 | 2 本 SMA クロスの総当たり（190 組×15 銘柄×D1/H4）: スペック §1 の再現合格数は偶然の範囲か・前半 TOP5 の等ウェイトは後半で勝つか | 複数の資産 | 支持 | 確定（(C) で「前半 TOP5 の bot は後半で等ウェイトに勝たない」。(A) は帰無が 0 点に潰れた退化で、… |  | [sma-cross-grid-spec-pass-q567](sma-cross-grid-spec-pass-q567/) |
| Q579 | MA 整列の局面では翌 24 本の分散比が 1 を超え、整列していない局面では 1 を下回るか（トレンド bot × トラリピ切替の前提） | 複数の資産 | 棄却 | 棄却 |  | [ma-alignment-regime-vr-q579](ma-alignment-regime-vr-q579/) |
| Q705 | 日本株・米国株の個別株の時系列モメンタム（12-1 か月リターンの符号で全買い／全売り） | 日本株 | 棄却 | 棄却 |  | [jp-us-stock-tsmom-q705](jp-us-stock-tsmom-q705/) |
| — | MAクロス 全パターン検証（EURUSD 4時間足） | FX | 記載なし・未実行 | — |  | [ma-cross-eurusd](ma-cross-eurusd/) |
| — | 200日移動平均線ルールの下落防御は、タイミングの効果か市場露出が減るだけか（約100年・米株） | 米国株 | 記述・点検 | README の「主な検証」表を参照 |  | [ma200-timing-vs-exposure](ma200-timing-vs-exposure/) |
| — | USDJPY 日足ドンチャンの「優位な売買方向」は5年窓をずらしても符号が保たれるか（Q353） | FX | 棄却 | ノイズ（確定） |  | [usdjpy-donchian-side-window-stability](usdjpy-donchian-side-window-stability/) |
