# 統計的裁定（ペア・リードラグ） — 検証 8 件

> この表は生成物（2026-11-20）。手法・場所・判定の型は AI が付け、迷いのあるものと抜き取りを別の目で確かめた。

[← 目次](../README.md)

| 支持 | 棄却 | 未確定 | 記述・点検 | 記載なし・未実行 |
|---|---|---|---|---|
| 0 | 7 | 0 | 1 | 0 |

場所: FX 1・指数・商品 1・複数の資産 4・日本株 1・米国株 1

| Q | 問い | 場所 | 判定 | 判定の文 | 学び | フォルダ |
|---|---|---|---|---|---|---|
| Q213 | USTECH の直前 1 時間のリターンは BTC の次の 1 時間を予測するか（リード・ラグ・2020 年以降・H1） | 複数の資産 | 棄却 | 棄却 |  | [ustech-btc-leadlag](ustech-btc-leadlag/) |
| Q233 | 金銀比・Brent−WTI の z スコア逆張り（ペアトレード）は 2015 年以降コスト後に残るか | 指数・商品 | 棄却 | 棄却: どの組も残らない |  | [ratio-pairs-mean-reversion](ratio-pairs-mean-reversion/) |
| Q236 | 4 組（XAU→XAG・WTI→UKOIL・BTC→ETH・US500→USTECH）の H1 リード・ラグは、両方向のどちらが強いか | 複数の資産 | 棄却 | 棄却: 1 組以下 |  | [cross-market-leadlag-h1](cross-market-leadlag-h1/) |
| Q241 | 原油→USDCAD・金→AUDUSD の日次リード・ラグは、両方向のどちらが強いか（Chen・Rogoff・Rossi 2010 の逆向き） | 複数の資産 | 棄却 | 棄却: どちらの組も一方向の先導なし |  | [commodity-currency-leadlag](commodity-currency-leadlag/) |
| Q256 | クロス・シグナル（金→銀・WTI→UKOIL・US500→USTECH・BTC→ETH）の日足順張りは自身の合図より良いか | 複数の資産 | 棄却 | 棄却: 主はリードしない（4 組とも全期間 ／z／<2） |  | [cross-signal-tsmom](cross-signal-tsmom/) |
| Q577 | 日本株・米国株の距離法ペア取引（12 か月形成・6 か月取引・上位 20 ペア・2σ・1 日待ち） | 日本株 | 棄却 | 棄却 |  | [jp-us-pairs-distance-q577](jp-us-pairs-distance-q577/) |
| Q611 | S42 FX の 21 ペアの共和分の平均回帰 | FX | 棄却 | 棄却 | 条件を通るのが年 8 件。戻るのは 2 割 | [s42-fx-pairs-q611](s42-fx-pairs-q611/) |
| — | ペアトレード（IEF/TLT, NVDA/AMD） | 米国株 | 記述・点検 | README の「主な検証」表を参照 |  | [pair-trading](pair-trading/) |
