# 第三者の時刻（OpenTimestamps）— 判断待ち 50 の案（2026-11-18 午後の自走・Opus 5.5・入れていない）

## なぜ
記録にはハッシュの鎖（`トレード/forward/_写し/*/chain.csv`）と lab-ops への錨（`lab-ops/trade/anchor/chain_heads.csv`）があるが、lab-ops のコミット時刻は自分で付けた時刻なので、外の人（就職先・論文の査読者など）に「この事前登録・この記録はこの日に既にあった」と示す力が弱い。探索の地図の注記「証拠は第三者の時刻＝OpenTimestamps／GitHub push で作る・未実装」の実装。

## 中身
| ファイル | 役割 |
|---|---|
| `ots_lite.py` | 標準ライブラリだけの OpenTimestamps の道具（stamp・upgrade・info・check）。形式は公式と同じ |
| `stamp_daily.py` | 毎日 1 回: 事前登録（検証/ の下の全部・196 本）・運用規程・凍結の json・依存の控え・S30 の確定の控え・記録の鎖（10 本）・錨の sha256 の一覧（225 行）を作り、その一覧に OpenTimestamps を付ける。前の日までの .ots の保留をビットコインの印に置き換える |
| `com.taichi.stamp-daily.plist.案` | launchd（毎日 10:40・22:40。run_forward.sh の 9:20 の回の後） |
| `テスト/` | 偽のカレンダー（127.0.0.1）での試験 `test_ots.py` 18/18・`test_stamp_daily.py` 10/10 |

## 外に出るもの
一覧ファイルの sha256 に 16 バイトの乱数を足してもう一度 sha256 したもの（32 バイト）だけ。送り先は公開のカレンダー 3 つ（a/b.pool.opentimestamps.org・a.pool.eternitywall.com）。一覧そのもの・パス・記録の中身・口座・名前は送らない。一覧と .ots は `トレード/forward/証拠/第三者の時刻/` に残る（この Mac だけ）。

## 公式との互換（確かめたこと）
- 公式の `opentimestamps-client`（scratchpad の一時的な venv に入れた・ネットには送っていない）の `ots info` が、この道具で作った .ots（保留 → 偽のビットコインの印に置き換え済み）を正しく読み、merkle root もこの道具の表示と一致した。
- 逆に、公式のライブラリで組んだ .ots（append・sha256・prepend・保留・ビットコインの印の分かれ道つき）を、この道具がバイトまで同じに読み書きできた。

## 外の人に見せるとき
`manifest_YYYYMMDD.txt`・その `.ots`・見せたいファイル（例 `事前登録_q751.md`）の 3 つを渡す。
1. `shasum -a 256 事前登録_q751.md` が一覧の行と同じ
2. `ots verify manifest_YYYYMMDD.txt.ots`（公式・ビットコインのノードかブロックの表を見る）がブロックの時刻を返す
→ その事前登録はその時刻より前にこの中身で存在した。

## 入れ方（承認の後）
`zsh 入れる.sh`（`トレード/forward/証拠/` に 2 本を置き、`--dry` で一覧が作れることを確かめる）→ `launchctl load`（入れる.sh が最後に表示する 1 行）。戻すのは `戻す.sh`。

## 別の目の点検（2026-11-18・Opus）を反映
重いもの: ① 命令の結果に上限が無く、hexlify を重ねた応答でメモリを食い尽くせた → 4,096 バイトまで ② upgrade で 1 つのカレンダーの壊れた応答がファイル全体を止めた → 保留ごとに受け流す ③ 保留の URI ならどこへでも問い合わせ、ビットコインの印 1 つで保留を消していた → 既知のカレンダーの https だけ・転送はたどらない・保留は残して印を足す ④ 同じ命令の枝が並ぶと公式が片方を落とす → 束ねる ⑤ 一覧に kaggle・学問・設計の下書きの事前登録、依存の控え、S30 の確定の控えが漏れていた → 足した。同じ日の 2 回目・120 日の upgrade・記録の回との重なりも直した。公式クライアントは直した後の .ots（保留とビットコインの印を束ねた形）も正しく読む。

## 照らす（verify・17:2x 追加）
`python ots_lite.py verify manifest_YYYYMMDD.txt.ots` は、ビットコインの印ごとに、その高さのブロックの merkle root を公開のブロック表（blockstream.info・mempool.space）と照らし、合えばブロックの時刻を出す。送るのはブロックの高さだけ。stamp_daily は印を足した回に照らしてログに残す（合わなければ ★）。外の人は公式の `ots verify` を使えばよい。
