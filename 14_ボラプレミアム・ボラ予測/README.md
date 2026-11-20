# ボラプレミアム・ボラ予測 — 検証 13 件

> この表は生成物（2026-11-20）。手法・場所・判定の型は AI が付け、迷いのあるものと抜き取りを別の目で確かめた。

[← 目次](../README.md)

| 支持 | 棄却 | 未確定 | 記述・点検 | 記載なし・未実行 |
|---|---|---|---|---|
| 2 | 8 | 2 | 1 | 0 |

場所: FX 1・指数・商品 2・複数の資産 10

| Q | 問い | 場所 | 判定 | 判定の文 | 学び | フォルダ |
|---|---|---|---|---|---|---|
| Q187 | 為替のボラ予測で損失関数の差はモデルの差の何倍に見えるか（Tokajuk 2026-1 の為替移植） | FX | 棄却 | 棄却（H0 支持: 為替では損失関数の差はモデルの差より小さい・Tokajuk の構図は為替で再現しない） |  | [vol-forecast-loss-vs-model](vol-forecast-loss-vs-model/) |
| Q222 | Parkinson のレンジボラは終値ボラより翌日の実現ボラをよく予測するか（15 銘柄・QLIKE・HAR 型） | 複数の資産 | 支持 | 支持: Parkinson のレンジは終値より翌日の実現ボラをよく予測する |  | [parkinson-vol-forecast](parkinson-vol-forecast/) |
| Q234 | XAUUSD の実測スプレッドの変化は、HAR に足すと翌時間の実現ボラの QLIKE を下げるか | 指数・商品 | 棄却 | 棄却: 前後半のどちらかで t > −2 または z > −2 |  | [spread-change-vol-forecast](spread-change-vol-forecast/) |
| Q247 | ボラの非対称性の向きは群で違うか（株価指数は負・金は正・FX は無し。HAR に符号項・15 銘柄） | 複数の資産 | 未確定 | 未確定 |  | [vol-asymmetry-by-group](vol-asymmetry-by-group/) |
| Q259 | HAR 予測の分散でのボラ・ターゲティングは σ60 版よりシャープが高いか（Q222×Q205 の連鎖） | 複数の資産 | 棄却 | 棄却: 差は見えない |  | [har-vol-targeting](har-vol-targeting/) |
| Q274 | 15銘柄をプールしたパネル HAR は銘柄別 HAR より翌日の QLIKE を下げるか | 複数の資産 | 棄却 | 棄却: 差は見えない（支持にも逆向きにも届かない） |  | [pooled-har-vs-individual](pooled-har-vs-individual/) |
| Q275 | HAR の持続基準に対する優位は予測期間（1・5・22 日）で広がるか縮むか（15銘柄・QLIKE） | 複数の資産 | 記述・点検 | 逆向きで確定: 前後半とも t≤−2（短いほど効く） |  | [har-horizon-advantage](har-horizon-advantage/) |
| Q276 | HAR の係数を 2 年の rolling で推定し直すと拡大窓より QLIKE は下がるか（15銘柄） | 複数の資産 | 棄却 | 棄却: 差は見えない（支持にも逆向きにも届かない） |  | [har-rolling-vs-expanding](har-rolling-vs-expanding/) |
| Q376 | 48 銘柄 D1 の翌 5 日実現ボラ予測（σ20・σ60・HAR・リッジ全特徴・GBM 全特徴）は QLIKE で σ60 に勝ち、σ̂ を size_weights に渡すと S07 TSMOM60 の規程モードで最大下落が浅くシャープが上がるか | 複数の資産 | 棄却 | 棄却 |  | [s04b-vol-forecast-sizing-q376](s04b-vol-forecast-sizing-q376/) |
| Q387 | 48 銘柄 D1 の翌 5 日実現分散の予測を水準で学習する HAR-RV（銘柄別・Corsi 原型）・プール水準 HAR・EWMA λ0.94・log-HAR スミアリング補正は、較正（実現/予測の平均 0.8〜1.25）を満たした上で QLIKE で σ60 に勝つか（Q376 の中央値偏りの再設計） | 複数の資産 | 棄却 | 2015 年 1 年への依存が強く、残り 12 年では σ60 と差がない。平均 QLIKE の半減は 2015 の外… |  | [s04b-vol-forecast-calibrated-q387](s04b-vol-forecast-calibrated-q387/) |
| Q397 | 48 銘柄 D1 で実測スプレッドの 5 日平均 z は翌 5 日の実現ボラ／σ60 の比を予測するか（σ60 に無い情報・年単位 IC の t） | 複数の資産 | 未確定 | 未確定 |  | [s11-spread-predicts-relative-vol-q397](s11-spread-predicts-relative-vol-q397/) |
| Q451 | BB幅収縮度のボラ予測への増分（wide48 D1） | 複数の資産 | 棄却 | 実質的に増分なし |  | [bb-squeeze-vol-increment-wide48-q451](bb-squeeze-vol-increment-wide48-q451/) |
| Q568 | VIX の期間構造の逆転（VIX/VIX3M ≥ 1）の後 20 営業日は、株価指数 10 本の平均リターンが高いか | 指数・商品 | 支持 | 確定（逆転後 20 日の指数の平均リターンは高い）。ただしシャープの上乗せは後半で消え、S17b と相関 0.79 で… |  | [vix-term-inversion-index-q568](vix-term-inversion-index-q568/) |
