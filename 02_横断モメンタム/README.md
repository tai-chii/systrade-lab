# 横断モメンタム — 検証 13 件

> この表は生成物（2026-11-20）。手法・場所・判定の型は AI が付け、迷いのあるものと抜き取りを別の目で確かめた。

[← 目次](../README.md)

| 支持 | 棄却 | 未確定 | 記述・点検 | 記載なし・未実行 |
|---|---|---|---|---|
| 0 | 10 | 3 | 0 | 0 |

場所: FX 2・複数の資産 4・日本株 6・暗号資産 1

| Q | 問い | 場所 | 判定 | 判定の文 | 学び | フォルダ |
|---|---|---|---|---|---|---|
| Q214 | 52 週高値への近さは 15 銘柄の翌月リターンを 12 か月モメンタムより予測するか（George・Hwang 2004 の型） | 複数の資産 | 棄却 | 棄却側の確定 |  | [52week-high-vs-momentum](52week-high-vs-momentum/) |
| Q218 | 横断モメンタム（15 銘柄の上位 5 買い・下位 5 売り）は時系列モメンタムとコスト後にどれだけ違うか（Moskowitz ほか 2012 の型） | 複数の資産 | 棄却 | ノイズ（前後半で揃った差はない） |  | [cross-sectional-vs-ts-momentum](cross-sectional-vs-ts-momentum/) |
| Q255 | ドル因子を除いた残差の順張りは生の順張りより強いか（FX6・Blitz 2011 の残差モメンタムの移植） | FX | 棄却 | 棄却: 差は見えない |  | [residual-momentum-fx](residual-momentum-fx/) |
| Q263 | アルトコインの対 BTC 相対強弱（4 週）は翌週の相対リターンを予測するか（10 通貨の横断・順位並べ替え帰無） | 暗号資産 | 棄却 | 棄却: 全期間 z<2 |  | [alt-btc-relative-strength](alt-btc-relative-strength/) |
| Q300 | 7 通貨の強度ランキングの最強−最弱スプレッド（4H・L=30 本・ボラ正規化）の上位五分位は、翌 6 本（1 日）の合成リターンがコスト後に継続か反転か | FX | 棄却 | 棄却 |  | [currency-strength-spread-quintile](currency-strength-spread-quintile/) |
| Q371 | 48 銘柄 wide48 の D1 横断モメンタム L=60（上位1/3買い・下位1/3売り）は封印前の前後半とも年単位 t≥2 か | 複数の資産 | 未確定 | 未確定 |  | [wide48-cross-sectional-mom60](wide48-cross-sectional-mom60/) |
| Q448 | ランキング学習（LambdaMART）対 過去リターン並べ（JT）：wide48 月次・上下10・コスト後 | 複数の資産 | 棄却 | 棄却 |  | [ltr-lambdamart-vs-jt-wide48-monthly-q448](ltr-lambdamart-vs-jt-wide48-monthly-q448/) |
| Q563 | 日本株・米国株の横断モメンタム（12-1 か月・月次・上下 10%・等金額 L/S） | 日本株 | 棄却 | 棄却 |  | [jp-us-xs-momentum-q563](jp-us-xs-momentum-q563/) |
| Q564 | 残差モメンタム（市場 1 因子の残差・12-1 か月・残差 σ で割る・月次・上下 10%）：日本株・米国株 | 日本株 | 棄却 | 棄却 |  | [jp-us-residual-momentum-q564](jp-us-residual-momentum-q564/) |
| Q700 | 日本株・米国株の 52 週高値への近さ（終値÷52 週高値）の上位 10% 買い・下位 10% 売り | 日本株 | 棄却 | 棄却 |  | [jp-us-52wh-q700](jp-us-52wh-q700/) |
| Q704 | 日本株・米国株の業種モメンタム（上位 3 業種買い・下位 3 業種売り） | 日本株 | 未確定 | 未確定 |  | [jp-us-industry-mom-q704](jp-us-industry-mom-q704/) |
| Q706 | 日本株・米国株の中間モメンタム（12-7 か月リターン・上下 10%） | 日本株 | 未確定 | 未確定 |  | [jp-us-mom-12-7-q706](jp-us-mom-12-7-q706/) |
| Q707 | 日本株・米国株の夜間リターンの持続（過去 12-1 か月の夜間リターンの和・上下 10%） | 日本株 | 棄却 | 棄却 |  | [jp-us-overnight-mom-q707](jp-us-overnight-mom-q707/) |
