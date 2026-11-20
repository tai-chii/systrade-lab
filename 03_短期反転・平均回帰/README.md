# 短期反転・平均回帰 — 検証 16 件

> この表は生成物（2026-11-20）。手法・場所・判定の型は AI が付け、迷いのあるものと抜き取りを別の目で確かめた。

[← 目次](../README.md)

| 支持 | 棄却 | 未確定 | 記述・点検 | 記載なし・未実行 |
|---|---|---|---|---|
| 2 | 13 | 1 | 0 | 0 |

場所: FX 3・指数・商品 3・複数の資産 7・日本株 1・暗号資産 2

| Q | 問い | 場所 | 判定 | 判定の文 | 学び | フォルダ |
|---|---|---|---|---|---|---|
| Q173 | 為替の夜間→日中の逆張りは2015年以降の主要8通貨でコスト後に残るか（DellaCorte 2015） | FX | 棄却 | 棄却 |  | [overnight-intraday-reversal-fx](overnight-intraday-reversal-fx/) |
| Q174 | ボラの変化は1日逆張りの翌日リターンを予測するか（DellaCorte 2015-3・15銘柄） | 複数の資産 | 棄却 | 棄却 |  | [vol-change-reversal](vol-change-reversal/) |
| Q180 | RSI の族は先進国通貨の日足で2016年以降も補正後に残るか（Coakley 2016-2） | FX | 棄却 | 棄却（確定） |  | [rsi-rules-fx](rsi-rules-fx/) |
| Q183 | 暗号資産の1時間足の逆張りの見返りは直前のボラで予測できるか（Farag 2024-1・11通貨） | 暗号資産 | 支持 | ボラは1時間逆張りの粗利を予測する（Farag 2024-1 の H1 版）。ただし後半で係数が3〜4倍小さくなり、保… |  | [crypto-h1-reversal-vol](crypto-h1-reversal-vol/) |
| Q215 | 1 か月の短期反転（直前 21 日の逆）は 15 銘柄の日足でコスト後に残るか（Jegadeesh 1990 の型・12-1 モメンタムと対比） | 複数の資産 | 棄却 | 棄却（粗利でも負・事前固定 z≥2 を通らず） |  | [one-month-reversal](one-month-reversal/) |
| Q237 | 終値位置 CLV が極端な日の翌日は、続くか反転するか（15 銘柄・Holm） | 複数の資産 | 棄却 | 棄却 |  | [close-location-next-day](close-location-next-day/) |
| Q240 | k 日連続同符号（k=3・5）の翌日は反転するか（15 銘柄・年内並べ替え帰無） | 複数の資産 | 棄却 | 棄却 |  | [streak-reversal](streak-reversal/) |
| Q248 | トレンド群（金・銀・原油 2・株価指数 2）の週末の窓は週内に埋まるか（Dao 2016 の FX 以外への条件の穴） | 指数・商品 | 棄却 | 棄却: 全期間の z < 2 |  | [weekend-gap-fill-trend7](weekend-gap-fill-trend7/) |
| Q270 | 株価指数・金の夜間→日中の逆張りはコスト後に残るか（DellaCorte 2015 の指数・金への移植・H1） | 指数・商品 | 棄却 | 棄却: 全期間の粗利の z<2（信号がない） |  | [overnight-intraday-reversal-indices](overnight-intraday-reversal-indices/) |
| Q271 | US500・USTECH の RSI2 押し目買いは高ボラのときだけコスト後に残るか（QuanterLab 2026-3 の追試・CFD 日足） | 指数・商品 | 棄却 | 棄却: 2 指数とも全期間 z<1 |  | [rsi2-dip-highvol-indices](rsi2-dip-highvol-indices/) |
| Q273 | ジャンプ日（／ret／>2.5σ）の翌日・翌5日は継続か反転か（15銘柄・年内並べ替え帰無） | 複数の資産 | 未確定 | 未確定・ただし 2017 を境に y1 が「継続→反転」へ、y5 が「中立→継続」へ振れている可能性 |  | [jump-day-followthrough](jump-day-followthrough/) |
| Q293 | 15 銘柄 D1 のボリンジャー平均回帰（+2σ 売り・−2σ 買い、SMA20 戻りで決済）は all15 の年単位平均 bp（コスト後）が前後半とも正か（Coakley2016-2 の D1 移植） | 複数の資産 | 棄却 | 棄却 |  | [bollinger-mean-reversion-d1](bollinger-mean-reversion-d1/) |
| Q296 | 15 銘柄 D1 の月曜ギャップ逆張り（金曜終値→月曜始値のギャップと逆方向に月曜のみ ±1、火曜以降 0）は all15 の年単位平均 bp（コスト後）が前後半とも正か（Dao2016-2 の 15 銘柄移植） | 複数の資産 | 棄却 | 棄却 |  | [weekend-gap-reversal-15](weekend-gap-reversal-15/) |
| Q304 | 暗号資産 11 通貨日足の RSI2 押し目買い（RSI2<10 かつ終値>SMA200 で買い・終値>SMA5 で手仕舞い）はコスト後に前後半とも正か | 暗号資産 | 棄却 | 棄却 |  | [crypto-rsi2-dip](crypto-rsi2-dip/) |
| Q566 | 業種内の短期反転（日本株・月次・上下 10%） | 日本株 | 棄却 | 棄却 |  | [jp-industry-reversal-q566](jp-industry-reversal-q566/) |
| — | 為替の超短期平均回帰は2015年以降の1時間足では消えたか | FX | 支持 | 消えた（支持） |  | [fx-shortterm-meanreversion](fx-shortterm-meanreversion/) |
