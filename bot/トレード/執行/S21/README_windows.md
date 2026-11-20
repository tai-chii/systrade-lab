# winnote で S21 bot を動かす手順（1 回だけ・15 分）

前提: winnote に MT5（XM のデモ口座でログイン済み）と Python 3.11〜3.13 が入っている。

1. `lab-ops` を pull して `trade/S21_bot_YYYYMMDD.zip` を `C:\Users\<名前>\bot\` に展開する（中に `検証\...` のフォルダができる）。
2. PowerShell で:
   ```
   pip install MetaTrader5 pandas pyarrow lightgbm numpy
   cd C:\Users\<名前>\bot\検証\トレード\執行\S21
   python execute_mt5.py --once
   ```
   「接続: XMTrading-MT5 3 / 口座 …（デモ）」と出て、19 銘柄ぶんの「入る／見送り」の行（`[dry]`）が出れば OK。`config.json` ができる。
   - 「見つからない銘柄」が出たら `config.json` の `symbol_map` に業者の名前を書く（`python ..\..\..\verification-lab\tools\mt5\mt5_fetch.py --list US500` で探せる）。
   - MT5 のオプション → チャート → 最大バー数を Unlimited にしておく（mt5_fetch.py の README と同じ）。
3. 1 時間ほど dry で回してログを見る: `python execute_mt5.py --loop`（Ctrl+C で止まる）。
4. 問題なければ発注あり（デモ）で常時動かす: `python execute_mt5.py --loop --live`。
   - 止めない運用にするなら、タスクスケジューラで「ログオン時」に `python execute_mt5.py --loop --live`（開始: 上のフォルダ）を登録し、PC の自動再起動（Windows Update）後も戻るようにする。MT5 も自動起動にする。
5. 台帳とログは下の「状態を Mac へ送る」で 1 時間ごとに自動で Mac へ届く（2026-10-31〜。手でのコピーは不要）。

止める: ウィンドウで Ctrl+C。建玉は MT5 に残る（SL/TP つき）。bot を長く止めるなら MT5 で手で閉じる。

## よくある止まり方
- `MT5 に接続できない` → MT5 を起動してログインしてから。複数の MT5 があるなら `config.json` の `mt5_path` に `terminal64.exe` の場所。
- `実口座に接続している` → 実弾はまだ。デモ口座に切り替える。
- 足が `asof` に追いつかない（`stale` が多い）→ MT5 の接続が切れている。MT5 を再起動。
- ログに `新しい足が来ない: …` や `足が古い` が毎時続く → 足の更新が遅れている。待ち（最大 25 秒）で足りていないので MT5 の接続を確かめる（2026-11-02 の修正で足した印）。

## 状態を Mac へ送る（1 回だけ・10 分・2026-10-31）

なぜ: 台帳とログが winnote の中にしか無く、bot が止まっても帰宅して画面を見るまで気づけなかった。これを入れると、1 時間ごとに台帳・ログ・「bot が動いているか」が lab-ops 経由で Mac に届き、3 時間届かない／bot が落ちた／ログが 2 時間止まった ときに Mac の `自動実行/状態.md` と `要対応.md` に ★ が出る。照合（compare_record.py）も Mac 側で毎回自動で回る。

1. PowerShell で lab-ops を最新にし、送信スクリプトを bot のフォルダに写す:
   ```
   cd C:\Users\gtaic\lab-ops; git pull
   copy trade\S21_send_status.py C:\Users\gtaic\bot\検証\トレード\執行\S21\send_status.py
   ```
2. 手で 1 回送って確かめる:
   ```
   cd C:\Users\gtaic\bot\検証\トレード\執行\S21
   python send_status.py
   ```
   最後に **「push した」** と出れば OK。`push 失敗` と出たら、その文面を Claude に貼る（GitHub の認証が winnote に無い可能性。その場合は Git Credential Manager でログインする）。
3. 1 時間ごとに自動で回す（タスクスケジューラ）:
   ```
   $py = (Get-Command python).Source
   $sc = "C:\Users\gtaic\bot\検証\トレード\執行\S21\send_status.py"
   schtasks /Create /SC HOURLY /MO 1 /TN S21_send_status /TR "`"$py`" `"$sc`"" /F
   ```
   確認: `schtasks /Run /TN S21_send_status` → 数秒後に `ログ\send_status.log` に「push した」の行が増える。
4. ついでに bot 本体も「ログオン時に自動起動」にしておく（上の 4 の注記）。PC が再起動しても bot が戻る。

送るもの: `台帳\trades.csv`・`状態.json`・`ログ\run_<今月・前月>.log`・`heartbeat.json`（送った時刻・ログの最後の時刻・execute_mt5.py が動いているか）。口座番号や config.json は送らない。lab-ops に 1 時間 1 コミット増える。

## bot の更新（2026-11-04 に実績）
- winnote の `execute_mt5.py` を入れ替えるときは、SSH から直接止めずに `verification-lab/financial-engineering/s21-gapclose-fix/deploy/`（手元のみ・GitHub に出さない）の `deploy_when_home.sh`（Mac）→ `deploy_s21.ps1`（winnote・一回きりのタスクで実行）の形を使う。ハッシュ（旧・新）は sh の先頭に書くので、次の更新では書き換える。流れ・終了コード・winnote 側の事実（`start_s21.ps1` の中身・タスク S21_bot の設定）は同じフォルダの `README.md` の「配備」。
- 更新のたびに `トレード/forward/変更履歴.csv` に 1 行、`lab-ops/trade/S21_execute_mt5.py` を同じ版にして人が commit・push する。

## 判断のスプレッドの表 spr_ref.json（2026-11-05）

- bot は判断の spr_R に、XM のスプレッドでなく同じフォルダの `spr_ref.json` の値を入れる（記録に揃えるため・監査B の 1）。
- 表は Mac の `make_spr_ref.py` で月 1 回作り直し、このフォルダへ上書きする。bot は毎時読み直すので、再起動は要らない。
- 表が無い・読めない・45 日より古いと、ログと `状態.json` の「判断のスプレッド」に ★ が出る。
- 根拠: `verification-lab/financial-engineering/s21-sprref-align/README.md`
- 作り直しの手順（2026-11-05・Mac）: `zsh refresh_spr_ref.sh` で作って前の表と比べ、問題なければ `zsh refresh_spr_ref.sh --send` で winnote に置く。
  - 送らない条件: 表の期間の終わりが 7 日より古い、前の表と 3 倍を超えて違う銘柄 × 時がある、winnote に届かない。
  - 送った後はハッシュを照合し、`変更履歴.csv` に 1 行足す。
  - 回す時期: 毎月 2〜5 日（記録のデータが前の月の末まで揃った後）。次は 2026-12-02 ごろ。自動の呼び出し（lab_run.sh など）には入れていない（`自動実行/` の設定は人が決める）。
