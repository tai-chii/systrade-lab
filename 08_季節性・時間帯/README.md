# 季節性・時間帯 — 検証 32 件

> この表は生成物（2026-11-20）。手法・場所・判定の型は AI が付け、迷いのあるものと抜き取りを別の目で確かめた。

[← 目次](../README.md)

| 支持 | 棄却 | 未確定 | 記述・点検 | 記載なし・未実行 |
|---|---|---|---|---|
| 1 | 24 | 5 | 0 | 2 |

場所: FX 8・指数・商品 11・複数の資産 8・日本株 3・暗号資産 2

| Q | 問い | 場所 | 判定 | 判定の文 | 学び | フォルダ |
|---|---|---|---|---|---|---|
| Q153 | 15分足の1次自己相関は時刻で符号が変わるか（USDJPY・EURUSD 2021〜・Holm 補正） | FX | 棄却 | 確定（棄却） |  | [m15-autocorr-by-hour](m15-autocorr-by-hour/) |
| Q176 | 最初の1時間→最後の1時間の日中モメンタムは為替・株価指数・金で公表後に残るか（GarciaArano 2026） | 複数の資産 | 棄却 | 最初の1時間 → 最後の1時間 の日中モメンタムは、FX8・金・US株価指数2 の H1 で公表後にコスト前・コスト後… |  | [intraday-momentum-first-last](intraday-momentum-first-last/) |
| Q179 | 五十日の仲値前の円安はクロス円でも出て2021年以降に消えたか（Bessho 2023） | FX | 棄却 | 対立を支持: ドル固有 |  | [gotobi-cross-jpy](gotobi-cross-jpy/) |
| Q181 | 月替わり効果の窓は2017年以降に前倒しされたか（QuanterLab 2026・US500/USTECH/SPX） | 指数・商品 | 棄却 | 棄却: 古典窓と前倒し窓の差は見えない |  | [turn-of-month-shift](turn-of-month-shift/) |
| Q190 | 仲値後のドル円の売りは仲値前に上がった五十日だけ効くか（Bessho 2023-2・2008〜2026） | FX | 棄却 | 棄却 |  | [post-fix-conditional-sell](post-fix-conditional-sell/) |
| Q206 | 曜日効果は 15 銘柄の日足で 2017 年以降も残るか（曜日ラベル並べ替え・Holm） | 複数の資産 | 棄却 | 棄却（Q206・2026-10-10・15銘柄 D1 2008-02〜2026-07・B=500・SPLIT_YEAR… |  | [day-of-week-15](day-of-week-15/) |
| Q209 | 株価指数・金の夜間（現物取引時間外）リターンは日中より高いか（夜間プレミアム・H1・2017 年以降） | 指数・商品 | 棄却 | 棄却。夜間が日中より稼ぐように見える差は「夜間が 18 時間・日中が 6 時間」という長さの差で説明でき、14〜20 … |  | [overnight-premium-indices](overnight-premium-indices/) |
| Q212 | 暗号資産の週末（土日）はリターン・ボラ・順張りの損益が平日と違うか（11 通貨 H1） | 暗号資産 | 棄却 | 棄却 |  | [crypto-weekend-effect](crypto-weekend-effect/) |
| Q220 | アジア時間（0〜7 UTC）のレンジを欧州時間に抜けたら終値まで続くか（FX8 H1・ブレイクアウト） | FX | 棄却 | 棄却 |  | [asian-range-breakout](asian-range-breakout/) |
| Q229 | 月末のロンドン16時フィキシング前のドルの向きは、その月の US500 リターンと逆か（Melvin・Prins 2015 の型） | 指数・商品 | 棄却 | 棄却: 全期間の z > −2 |  | [month-end-fix-dollar](month-end-fix-dollar/) |
| Q238 | 「5 月に売れ」（ハロウィン効果）は 2008〜2026 の指数・商品 6 銘柄で残るか（6 か月ブロックの循環シフト帰無） | 指数・商品 | 棄却 | 棄却: 全期間の z < 2（手元の 18 年では見えない） |  | [halloween-effect](halloween-effect/) |
| Q239 | 休日前効果は SPX・NDX（2008〜2026）で残るか（祝日は欠損営業日から復元・Lakonishok・Smidt 1988 の型） | 指数・商品 | 棄却 | 棄却 |  | [pre-holiday-effect](pre-holiday-effect/) |
| Q242 | 暗号資産 11 通貨の UTC 時刻効果は、Holm 補正後に前後半で同符号で残るか | 暗号資産 | 棄却 | 棄却: 前後半で同符号に残る時刻は 0 |  | [crypto-hour-of-day](crypto-hour-of-day/) |
| Q265 | 15銘柄の月別季節性（month-of-year）は Holm 後に前後半で同符号で残るか | 複数の資産 | 棄却 | 効果なし（支持＝月別の季節性は残らない） |  | [month-of-year-15](month-of-year-15/) |
| Q266 | 年末年始効果（12月最終5営業日＋1月最初2営業日）は SPX・NDX（2008〜2026）で残るか（年内ブロック並べ替え） | 指数・商品 | 棄却 | 棄却: 全期間 z<1（SPX・NDX とも） |  | [santa-rally](santa-rally/) |
| Q267 | 金曜の最終1時間（NY 16時前）のリターンは週の向きと逆か（週末前の手仕舞い・FX8＋トレンド7 H1） | 複数の資産 | 未確定 | 未確定 |  | [friday-last-hour-reversal](friday-last-hour-reversal/) |
| Q268 | ECB 参照レート（14:15 CET）の前後にドルの V 字はあるか（Krohn 2024 のロンドン fix の移植・FX6 H1） | FX | 未確定 | 未確定 |  | [ecb-fix-vshape](ecb-fix-vshape/) |
| Q272 | 月曜（週末跨ぎ）のリターン分散は他の曜日の何倍か（取引時間 vs 暦時間・French・Roll 1986・15銘柄） | 複数の資産 | 支持 | 支持: all15 の log R の年単位平均が log1.3 未満かつ log3 に対し t≤−2（取引時間仮説） |  | [weekend-variance-ratio](weekend-variance-ratio/) |
| Q284 | 月末前4日の前倒し山は FX8 の日足に残っているか（Girgin 2026 ブログの FX 移植・Q283-C1） | FX | 棄却 | 棄却: 前後半で上位5%オフセットが一致しない |  | [turn-of-month-shift-fx8-q284](turn-of-month-shift-fx8-q284/) |
| Q285 | 日本株（Nikkei 225・TOPIX）の pre-TOM 4日効果は T+2 市場でも 2017 年以降に残るか（Q283-C2・Girgin 2026 の pre-TOM 前倒しを日本株に移植） | 日本株 | 棄却 | 棄却: 日本株の後半で S−C の z<2（前倒し窓は古典窓を上回らない） |  | [turn-of-month-shift-nikkei-topix-q285](turn-of-month-shift-nikkei-topix-q285/) |
| Q286 | 商品・BTC・FX の pre-TOM 4日効果は残るか（15銘柄パネルの非米国株13本・Q283-C3） | 複数の資産 | 棄却 | 棄却（K=0 ≤ 1）: Girgin の pre-TOM は株固有の現象で、商品・BTC・FX には及ばない |  | [turn-of-month-shift-xasset-q286](turn-of-month-shift-xasset-q286/) |
| Q289 | XAUUSD の WM/Reuters ロンドン fix（16:00 UTC）の前後に V 字はあるか | 指数・商品 | 未確定 | 未確定 |  | [xauusd-london-fix-vshape](xauusd-london-fix-vshape/) |
| Q297 | US500 / USTECH H1 の日中モメンタム（初動 1 時間 → 終盤 1 時間）は 2016 以降に減衰したか | 指数・商品 | 棄却 | ノイズ |  | [intraday-momentum-indices-decay](intraday-momentum-indices-decay/) |
| Q400 | 株価指数 13 の D1 月替わり効果（各銘柄の足で数えた月の最終営業日と翌月の最初の 3 営業日の 4 本だけ買い持ち）は 2010 年以後も残り、規程モードで封印前の前後半とも年単位 t≥2 かつ最大下落 −6% 以内か | 指数・商品 | 棄却 | 棄却 |  | [s13-idx13-turn-of-month-q400](s13-idx13-turn-of-month-q400/) |
| Q409 | S13 見直し: Q400（月替わり）・Q402（FOMC 偶数週）を穴跨ぎ足を除いて再計算 | 指数・商品 | 棄却 | 棄却 |  | [s13-gap-excluded-rerun-q409](s13-gap-excluded-rerun-q409/) |
| Q571 | S21 を東京時間のエントリーに限ると成績は上がるか（＋円クロス 4 本・深夜窓の Fintokei コスト） | 複数の資産 | 未確定 | 未確定（東京に絞る利点は示せない側） |  | [s21-tokyo-window-q571](s21-tokyo-window-q571/) |
| Q572 | 金（XAUUSD）はアジア時間（2〜7 時 UTC）の買い持ちだけでコスト後に正のドリフトがあるか | 指数・商品 | 棄却 | 棄却 |  | [gold-asia-hours-q572](gold-asia-hours-q572/) |
| Q573 | 東京カット（15:00 JST＝6 時 UTC）前後の円ペアの順張りは 24 時刻の Holm 補正後にも残るか | FX | 棄却 | 棄却 |  | [jpy-tokyo-cut-hour-q573](jpy-tokyo-cut-hour-q573/) |
| Q574 | 時間帯 × 単純ルール族の総当たり（5 窓 × 36 信号 × 26 銘柄） | 複数の資産 | 未確定 | 未確定（ロールオーバーの BID の見かけの疑い） |  | [session-rule-family-sweep-q574](session-rule-family-sweep-q574/) |
| Q702 | 日本株・米国株の同月季節性（過去 1〜5 年の同じ暦月のリターン平均）の高い方を買い低い方を売る | 日本株 | 棄却 | 棄却 |  | [jp-us-seasonality-q702](jp-us-seasonality-q702/) |
| — | 季節性（暖房株・気温相関など） | 日本株 | 記載なし・未実行 | README の「主な検証」表を参照 |  | [seasonality](seasonality/) |
| — | USDJPY の日中順張りは、ロンドン開始30分の時刻条件つきシグナルでのみ効くか | FX | 記載なし・未実行 | README の「主な検証」表を参照 |  | [usdjpy-london-open-vs-naive-momentum](usdjpy-london-open-vs-naive-momentum/) |
