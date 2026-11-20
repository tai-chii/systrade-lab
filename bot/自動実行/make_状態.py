# -*- coding: utf-8 -*-
"""make_状態.py — 「今の状態」を手書きせず生成する（2026-10-28）。
出力: 自動実行/状態.md。新しいチャットはまずこれを読む（引き継ぎ_*.md の「今の状態」節の代わり）。
読む元: トレード/forward/*/記録/状態.json・記録_最新.md、_基盤/戦略台帳.md（段階がフォワード以降の行）、
       自動実行/要対応.md（★ と未解決）、kensho_queue.py show（キューの件数）、daemon の pid、直近の 1ボタン レポート。
使い方: python3 make_状態.py   （lab_run.sh の最後と run_forward.sh の後に呼ばれる。手で回してもよい）"""
import os, re, json, glob, subprocess, datetime, sys
try:
    from zoneinfo import ZoneInfo; _TZ = ZoneInfo("Asia/Tokyo")
except Exception: _TZ = None
D = os.path.dirname(os.path.abspath(__file__)); V = os.path.dirname(D)
OUT = os.path.join(D, "状態.md"); L = []
now = datetime.datetime.now(_TZ).strftime("%Y-%m-%d %H:%M JST")
def rd(p):
    try: return open(p, encoding="utf-8").read()
    except Exception: return ""
def sec(title): L.append(""); L.append(f"## {title}")

L.append(f"# 今の状態（生成 {now}・make_状態.py）")
L.append("")
try:  # 2026-11-05: 稼働の 1 行判定（稼働.py）。11-01〜03 の空転・停止に気づけなかった対策
    import importlib.util as _iu; _sp = _iu.spec_from_file_location("kadou", os.path.join(D, "稼働.py")); _k = _iu.module_from_spec(_sp); _sp.loader.exec_module(_k)
    L.append("稼働: " + _k.line()); L.append("")
except Exception as _e: L.append(f"稼働: 判定できず（{_e}）"); L.append("")
L.append("手で書かない。元データを直せばここも変わる。決まり（運用のルール）は `_基盤/知識/運用の決まり.md`、台帳は `_基盤/戦略台帳.md`、人の判断待ちの本文は `自動実行/要対応.md`。")

# --- 自動実行
sec("自動実行")
pidf = os.path.join(D, ".lab_daemon.pid"); run = False
if os.path.exists(pidf):
    try: os.kill(int(rd(pidf).strip()), 0); run = True
    except Exception: run = False
L.append(f"- daemon: {'動いている（pid ' + rd(pidf).strip() + '）' if run else '止まっている'}" + ("・「止める」予約あり" if os.path.exists(os.path.join(D, "止める")) else ""))
reps = sorted(glob.glob(os.path.join(D, "レポート", "1ボタン_*.md")))
if reps: L.append(f"- 直近の 1ボタン レポート: `レポート/{os.path.basename(reps[-1])}`")
L.append(f"- 週次設計: {'オン' if os.path.exists(os.path.join(D, '週次設計.on')) else 'オフ'}（`週次設計.on`）")

# --- 検証キュー
sec("検証キュー（kensho_queue.py show）")
try:
    out = subprocess.run([sys.executable, os.path.join(V, "verification-lab", "tools", "kensho_queue.py"), "show"], capture_output=True, text=True, timeout=60).stdout
    cnt = {}
    for ln in out.splitlines():
        c = [x.strip() for x in ln.split("|")]
        if len(c) > 3 and c[1].startswith("Q"): cnt[c[2]] = cnt.get(c[2], 0) + 1
    L.append("- " + ("、".join(f"{k} {v}" for k, v in sorted(cnt.items())) if cnt else "行なし（待ち 0）"))
    if cnt.get("実行中"): L.append("- **実行中の行がある**＝別のセッションが動いているか、落ちた残り。勝手に release しない（AGENTS.md 並行運用 1）")
except Exception as e: L.append(f"- 取れなかった（{e}）")

# --- 生きている戦略（台帳）
sec("生きている戦略（戦略台帳で段階がフォワード以降）")
tb = rd(os.path.join(V, "_基盤", "戦略台帳.md")); n = 0
for ln in tb.splitlines():
    if not ln.startswith("| S"): continue
    c = [x.strip() for x in ln.split("|")]
    if len(c) < 6: continue
    st = c[5]
    if ("フォワード" in st or "本番" in st) and "棄却" not in st and "閉じ" not in st:
        name = c[2].replace("**", "")[:70]
        n += 1; L.append(f"- **{c[1]}** — {name}… ／ 段階: {st[:80]}")
if n == 0: L.append("- なし")

# --- フォワード
sec("フォワード記録（トレード/forward）")
fw = os.path.join(V, "トレード", "forward")
m = re.search(r"[（(](\d{4}-\d{2}-\d{2} \d{2}:\d{2}) 更新[）)]", rd(os.path.join(fw, "記録_最新.md")))
L.append(f"- 記録_最新.md: {m.group(1) + ' 更新' if m else '無し'}（`トレード/forward/記録_最新.md`）")
for sdir in sorted(glob.glob(os.path.join(fw, "S*", "記録", "状態.json"))):
    sid = os.path.basename(os.path.dirname(os.path.dirname(sdir)))
    try:
        j = json.load(open(sdir, encoding="utf-8")); stop = j.get("停止") or []
        if "累計R" in j:
            L.append(f"- {sid}: 経過 {j.get('経過日数')} 日・決済 {j.get('決済済み')} 件・累計 {j.get('累計R', 0):+.1f}R・最高値から {j.get('最高値からR', 0):+.1f}R・データの最後 {str(j.get('データの最後', ''))[:16]}" + (f"・欠けた銘柄 {j['欠けた銘柄']}" if j.get("欠けた銘柄") else "") + (f"・**停止 {stop}**" if stop else ""))
        elif "平均R" in j:   # 2026-11-01 S44（H1・仮想フォワード）
            L.append(f"- {sid}: {j.get('件数')} 件・合計 {j.get('合計R', 0):+.1f}R・PF {j.get('PF')}・最大下落 {j.get('最大下落R', 0):.1f}R・データの最後 {str(j.get('データの最後', ''))[:16]}・更新 {j.get('更新', '')}" + (f"・**停止 {j.get('停止')}**" if j.get("停止") else ""))
        elif "IC平均" in j:   # 2026-10-31 S30（月次・仮想フォワード）
            L.append(f"- {sid}: 確定 {j.get('記録月数（確定）')} か月・IC 平均 {j.get('IC平均')}（t {j.get('IC_t')}）・累計 {j.get('累計bp（確定）')} bp・最大下落 {j.get('最大下落（累積・単純和）')}・更新 {j.get('更新', '')}" + (f"・**停止 {stop}**" if stop else ""))
        else:
            k = 100 if sid == "S23" else 1   # S23 は割合・S34 は百分率で持つ（監査C の 4・2026-11-05）
            L.append(f"- {sid}: 記録 {j.get('記録日数')} 日・通算 {j.get('通算', 0) * k:+.1f}%・最高値から {j.get('最高値から', 0) * k:+.1f}%・更新 {j.get('更新', '')}" + (f"・**停止 {stop}**" if stop else ""))
    except Exception as e: L.append(f"- {sid}: 状態.json を読めない（{e}）")
# 2026-10-28: 変更（施策）× 損益（結果）の図。supermomonga 氏の MMbot ループ（Grafana アノテーション）の最小版。売買の計算には無関係
try:
    ap = subprocess.run([sys.executable, os.path.join(fw, "annot_plot.py")], capture_output=True, text=True, timeout=120)
    L.append(f"- 変更×損益: `トレード/forward/図/変更×損益.svg`・一覧 `トレード/forward/変更履歴.md`（{ap.stdout.strip() or ap.stderr.strip()[-120:]}）")
    ch = rd(os.path.join(fw, "変更履歴.md")).splitlines()
    rows = [x for x in ch if x.startswith("| ") and not x.startswith("| #")]
    for x in rows[-3:]:
        c = [y.strip() for y in x.split("|")]
        if len(c) > 6: L.append(f"  - #{c[1]} {c[2]} {c[3]}・{c[4]}: {c[5][:70]}")
except Exception as e: L.append(f"- 変更×損益: 作れなかった（{e}）")

# --- 執行（winnote）2026-10-31: winnote の send_status.py が 1 時間ごとに lab-ops へ送る heartbeat を見る。止まっていたら 要対応.md に ★（1 日 1 節）
sec("執行（winnote の S21・XM MT5 デモ）")
WN = os.path.join(V, "lab-ops", "trade", "winnote", "S21"); hbp = os.path.join(WN, "heartbeat.json")
AUTO_T = "winnote の S21 執行が止まっている恐れ（自動・make_状態.py）"
def _utc(x):
    try: return datetime.datetime.fromisoformat(str(x).replace("Z", "").replace(" ", "T")).replace(tzinfo=datetime.timezone.utc)
    except Exception: return None
def _jst(t): return t.astimezone(_TZ).strftime("%m-%d %H:%M") if (t and _TZ) else str(t)
probs = []; recv_mac = False
probs_cr, cr_ok = [], False
q751_gate = None   # 2026-11-18（Q751・案）: 判定の日を過ぎて本番の判定が通った回だけ、判定の全文を入れる（下で要対応に 1 回だけ ★ の節）    # 2026-11-16（昼の自走・案）: 照合の「余裕の大きい合図が記録と食い違う」★ も probs と分け、専用の節に書く（数日消えない ★ を止まった系の節に混ぜない）
probs_wu, wu_seen = [], False   # 2026-11-16（判断待ち 38）: Windows Update の再起動の予報は probs と分け、専用の自動の節に書く
if not os.path.exists(hbp):
    L.append("- まだ届いていない（winnote で `send_status.py` の登録待ち・`トレード/執行/S21/README_windows.md` の「状態を Mac へ送る」）")
else:
    try:
        hb = json.load(open(hbp, encoding="utf-8")); nu = datetime.datetime.now(datetime.timezone.utc)
        # 2026-11-06（s21-recv-watch）: lab-ops を fetch して origin の heartbeat も読み、「Mac が受け取れていない」と「winnote が止まった」を分ける。
        # ログの止まりは今の時刻でなく送った時刻（sent_at）から測る。11-06 02:40 の誤報（Mac の再起動で受け取れていなかった）の対策
        import recv_check as RCV
        hb_local = hb                                                            # 手元の写しの heartbeat（ログ・状態.json と同じ時点。2026-11-11 watch_rules.py の「今」に使う）
        kind, rmsgs, hb2 = RCV.check(os.path.join(V, "lab-ops")); hb = hb2 or hb; recv_mac = kind == "mac"
        ts, tl = _utc(hb.get("sent_at")), _utc(hb.get("last_log_at")); bot = hb.get("bot") or {}
        a_s = (nu - ts).total_seconds() / 3600 if ts else 999; a_l = (nu - tl).total_seconds() / 3600 if tl else 999
        st = "動いている" if bot.get("running") else ("動いていない" if bot.get("running") is False else "不明")
        if bot.get("running"): st += "（" + ("live" if bot.get("live") else "**dry**") + ("・loop" if bot.get("loop") else "・**loop なし**") + "）"
        L.append(f"- 最後に届いた {_jst(ts)}（{a_s:.1f} 時間前）・bot のログの最後 {_jst(tl)}（{a_l:.1f} 時間前）・bot {st}・台帳 {hb.get('ledger_rows')} 行")
        if recv_mac: L.append(f"- Mac 側: {rmsgs[0]}（winnote の ★ にはしない）")
        else: probs += rmsgs   # 届いていない・bot が落ちた・dry・送った時点でログが止まっていた（recv_check.judge）
        # 2026-11-05（監査B の 6・taichi「全部進めて」）: winnote の bot のファイルが正本と同じか・判断のスプレッドの ★（check_files.py・files の無い古い heartbeat では何も出ない）
        try: import check_files as CF; probs += CF.diff(hb, V) + CF.spr_note(V)
        except Exception as e: probs.append(f"ファイルの照合（check_files.py）が動かない（{e}）")
        # 2026-11-11（監査C の 1・2・3・7・watch_rules.py）: 拒否は「Market closed で、その後に注文が通っていれば ★ にしない」（指数の日々の休みで節が開いたままになり、
        #   その間の本物の停止を見逃す形を消す）。「回っているが売買できていない」印（★ 判断できない・エラー・再接続できない・全銘柄の足が取れない）・二重起動・状態.json の古さも見る。
        #   「今」は手元の写しの heartbeat の sent_at（ログ・状態.json と同じ時点。pull だけ止まったときに古い写しを新しい時刻で見て誤報にしない）
        try:
            import watch_rules as WR
            wl = []
            for lp in sorted(glob.glob(os.path.join(WN, "run_*.log")))[-2:]: wl += rd(lp).splitlines()
            wn = _utc(hb_local.get("sent_at")) or nu
            rp, ri = WR.reject_report(wl, wn); probs += rp + WR.log_anomalies(wl, wn)
            for x in ri: L.append(f"- {x}")
            db = WR.double_boot(hb_local.get("bot") or {})
            if db: probs.append(db)
            try: su = datetime.datetime.fromisoformat(str(json.load(open(os.path.join(WN, "状態.json"), encoding="utf-8")).get("更新")))
            except Exception: su = None
            ss = WR.state_stale(su, wn, wl) if (su is not None and su.tzinfo is not None) else None
            if ss: probs.append(ss)
            try:                                                                    # 2026-11-18 判断待ち 52: 台帳の開いた行と保有中の数
                import csv as _csv
                _no = sum(1 for r in _csv.DictReader(open(os.path.join(WN, "trades.csv"), encoding="utf-8")) if r.get("status") == "open")
                _lm = WR.ledger_mismatch(_no, json.load(open(os.path.join(WN, "状態.json"), encoding="utf-8")).get("保有中"))
                if _lm: probs.append(_lm)
            except FileNotFoundError: pass
        except Exception as e: probs.append(f"見張りの判定（watch_rules.py）が動かない（{e}）")
        # 2026-11-16（判断待ち 38・winupdate_rules.py）: Windows Update の再起動待ち・一時停止の期限・次の月例の前の一時停止を ★ にする（win_update の無い古い heartbeat では何も出ない）
        try:
            import winupdate_rules as WUR
            _wu = hb_local.get("win_update"); wu_seen = isinstance(_wu, dict) and not _wu.get("error")
            wp, wi = WUR.judge(_wu, _utc(hb_local.get("sent_at")) or nu); probs_wu += wp
            for x in wi: L.append(f"- {x}")
        except Exception as e: probs_wu.append(f"Windows Update の見張り（winupdate_rules.py）が使えない（{e}）")
        led = os.path.join(WN, "trades.csv"); cr = None
        if os.path.exists(led) and (hb.get("ledger_rows") or 0) > 0:
            try: cr = subprocess.run([sys.executable, os.path.join(V, "トレード", "執行", "S21", "compare_record.py"), "--ledger", led], capture_output=True, text=True, timeout=120)
            except Exception as e:   # 2026-11-16（昼の自走・再点検）: タイムアウトなどで照合が動かない回を「heartbeat.json を読めない」（止まった系の節）にしない
                cr = None; L.append(f"  - 照合: 動かなかった（{type(e).__name__}）")
        if cr is not None:
            for ln in (cr.stdout.strip().splitlines() or [cr.stderr.strip()[-150:]])[:2]: L.append(f"  - 照合: {ln[:220]}")
            # 2026-11-16（昼の自走・案）: 今の版の行（1 行目）の「余裕 ≥… の合図の一致 a/b」と ★ を読む。解決に数えるのは、照合が正常に終わり、
            #   今の版の行に 10 件以上の判定があるときだけ（照合が落ちた回・版を替えた直後で件数が足りない回は「消えた」と数えない）
            l1 = (cr.stdout.strip().splitlines() or [""])[0]
            if "★ 直近" in l1: probs_cr.append("照合: " + l1[l1.index("★ 直近") + 2:][:160])
            mh = re.search(r"余裕 ≥[\d.]+ の合図の一致 \d+/(\d+)", l1)
            cr_ok = cr.returncode == 0 and l1.startswith("今の版") and bool(mh) and int(mh.group(1)) >= 10
        # 2026-11-18（深夜の自走・Q751・案）: 規程 §4 ③（実測コスト）の量＝超過コスト E を 1 行。読むだけ・★ にしない（判定は 2027-04-25 以降の 1 回）。
        #   parquet を読むので pyarrow のある venv_forward で回す。動かなくても状態.md の他の行は止めない
        try:
            _jq = os.path.join(V, "verification-lab", "financial-engineering", "s21-6m-gate-q751", "judge_s21_6m.py")
            _py = os.path.join(os.path.dirname(V), "作業層", "大容量", "venv_forward", "bin", "python")
            if os.path.exists(_jq) and os.path.exists(_py) and os.path.exists(led):
                jq = subprocess.run([_py, _jq, "--line", "--boot", "500", "--ledger", led], capture_output=True, text=True, timeout=120)   # 182 日を過ぎたら本番の判定の行
                if jq.returncode == 0:
                    try:
                        _full = subprocess.run([_py, _jq, "--ledger", led], capture_output=True, text=True, timeout=180)
                        if _full.returncode == 0: q751_gate = _full.stdout.strip()
                    except Exception: pass
                if jq.returncode == 2:                                                                                                    # まだ判定の日ではない → 予行
                    jq = subprocess.run([_py, _jq, "--preview", "--line", "--boot", "500", "--ledger", led], capture_output=True, text=True, timeout=120)
                if jq.returncode == 0 and jq.stdout.strip(): L.append(f"  - {jq.stdout.strip().splitlines()[-1][:220]}")
        except Exception as e:
            L.append(f"  - 超過コスト E（Q751）: 動かなかった（{type(e).__name__}）")
    except Exception as e:
        probs.append(f"heartbeat.json を読めない（{e}）")
for pmsg in probs: L.append(f"- ★ {pmsg}")
for pmsg in probs_wu: L.append(f"- ★ {pmsg}")
for pmsg in probs_cr: L.append(f"- ★ {pmsg}")
try:
    yp = os.path.join(D, "要対応.md"); ytxt = rd(yp); today = datetime.datetime.now(_TZ).strftime("%Y-%m-%d")
    try: import watch_rules as WR2; add, newk = WR2.need_new_node(ytxt, probs, AUTO_T)   # 未解決の自動の節が無いとき、または節に無い種類の異常が出たときに足す（2026-11-11・監査C の 1）
    except Exception: add, newk = bool(probs) and not re.search(rf"^## [^\n]*{re.escape(AUTO_T)}\n- 状態: 未解決", ytxt, re.M), set()
    if probs and add:
        ytxt = ytxt.rstrip("\n") + f"\n\n## {now[:16]} — ★ {AUTO_T}\n- 状態: 未解決\n" + "".join(f"- {x}\n" for x in probs) + \
               (f"- 前の未解決の節には無い種類の異常が出たので節を分けた（{'・'.join(sorted(newk))}）\n" if newk else "") + \
               "- 見ること（winnote）: MT5 がログイン中か・bot のウィンドウ（`python execute_mt5.py --loop --live`）が開いているか。異常が消えたら次の回（1 時間以内）でこの節は自動で解決になる\n"
        open(yp, "w", encoding="utf-8").write(ytxt)
    elif not probs and not recv_mac and os.path.exists(hbp) and AUTO_T in ytxt:   # Mac が受け取れていない間は「正常を確認」と書かない
        ytxt2 = re.sub(rf"(## [^\n]*{re.escape(AUTO_T)}\n- 状態: )未解決", rf"\g<1>解決（自動・{now} に正常を確認）", ytxt)
        if ytxt2 != ytxt: open(yp, "w", encoding="utf-8").write(ytxt2)
except Exception as e: L.append(f"- 要対応への書き込みに失敗（{e}）")
# 2026-11-16（判断待ち 38）: 再起動の予報の節は「止まっている恐れ」の節と分ける（別の目の点検: 混ぜると、予報が何日も残る間に本物の停止の 2 回目が新しい節にも通知にもならない）。
#   解決にするのは、win_update を読めた heartbeat で ★ が消えたときだけ（古い heartbeat・読めなかった回は「消えた」と数えない）
try:
    try: import winupdate_rules as WUR2; AUTO_WU = WUR2.AUTO_TITLE
    except Exception: AUTO_WU = "winnote の Windows Update の再起動の予報（自動・make_状態.py）"
    yp = os.path.join(D, "要対応.md"); ytxt = rd(yp)
    try: add_wu = WUR2.need_node(ytxt, probs_wu, AUTO_WU)          # 種類（再起動待ち／月例・一時停止）は winupdate_rules で分ける（点検 2 回目）
    except Exception: add_wu = bool(probs_wu) and not re.search(rf"^## [^\n]*{re.escape(AUTO_WU)}\n- 状態: 未解決", ytxt, re.M)
    if probs_wu and add_wu:
        ytxt = ytxt.rstrip("\n") + f"\n\n## {now[:16]} — ★ {AUTO_WU}\n- 状態: 未解決\n" + "".join(f"- {x}\n" for x in probs_wu) + \
               "- 見ること（winnote）: 設定 → Windows Update の「一時停止」の期限と「再起動が必要です」の表示。手で更新・再起動するのは市場の閉まっている土曜 7:00〜月曜 6:00 JST、再起動の後にログイン → MT5 → bot を起こす。印が消えたら次の回（1 時間以内）でこの節は自動で解決になる\n"
        open(yp, "w", encoding="utf-8").write(ytxt)
    elif not probs_wu and wu_seen and not recv_mac and AUTO_WU in ytxt:
        ytxt2 = re.sub(rf"(## [^\n]*{re.escape(AUTO_WU)}\n- 状態: )未解決", rf"\g<1>解決（自動・{now} に印が消えたのを確認）", ytxt)
        if ytxt2 != ytxt: open(yp, "w", encoding="utf-8").write(ytxt2)
except Exception as e: L.append(f"- 要対応への書き込み（再起動の予報）に失敗（{e}）")
# 2026-11-16（昼の自走・案・別の目の点検）: 照合の ★（余裕の大きい合図が記録と食い違う）は専用の節。直近 20 件が入れ替わるまで数日残るので、
#   止まった系の節に混ぜると、その間の 2 回目の停止が新しい節にも通知にもならない（判断待ち 38 の予報と同じ穴）
AUTO_CR = "winnote の S21 の判断が記録と食い違っている恐れ（自動・make_状態.py・照合）"
try:
    yp = os.path.join(D, "要対応.md"); ytxt = rd(yp)
    if probs_cr and not re.search(rf"^## [^\n]*{re.escape(AUTO_CR)}\n- 状態: 未解決", ytxt, re.M):
        ytxt = ytxt.rstrip("\n") + f"\n\n## {now[:16]} — ★ {AUTO_CR}\n- 状態: 未解決\n" + "".join(f"- {x}\n" for x in probs_cr) + \
               "- 見ること（Mac）: `python トレード/執行/S21/compare_record.py --ledger lab-ops/trade/winnote/S21/trades.csv` の出力と、最後に配った版（`compare_record.py` の ERAS）。記録の余裕が大きいのに bot が合図を出していない足は、bot の足（MT5 の H1）・spr_ref.json・凍結モデルのファイルの照合（check_files）を見る。直近の一致が戻れば次の回でこの節は自動で解決になる\n"
        open(yp, "w", encoding="utf-8").write(ytxt)
    elif not probs_cr and cr_ok and AUTO_CR in ytxt:
        ytxt2 = re.sub(rf"(## [^\n]*{re.escape(AUTO_CR)}\n- 状態: )未解決", rf"\g<1>解決（自動・{now} に照合で一致が戻ったのを確認）", ytxt)
        if ytxt2 != ytxt: open(yp, "w", encoding="utf-8").write(ytxt2)
except Exception as e: L.append(f"- 要対応への書き込み（照合）に失敗（{e}）")
# 2026-11-18（深夜の自走・Q751・案）: 事前登録 5「判定の日の結果は ★ で要対応に書く」。判定の日を過ぎた最初の回で 1 回だけ（同じ題の節があれば書かない）
AUTO_Q751 = "S21 の 6 か月時点の確認の結果（自動・make_状態.py・Q751）"
try:
    if q751_gate:
        yp = os.path.join(D, "要対応.md"); ytxt = rd(yp)
        if AUTO_Q751 not in ytxt:
            ytxt = ytxt.rstrip("\n") + f"\n\n## {now[:16]} — ★ {AUTO_Q751}\n- 状態: 未解決\n" + \
                   "- 規程 §4 の 4 条件（①件数 ②平均 R ③超過コスト E ④停止）。満たしても学生の間は実弾へ進まない（2026-11-05 の方針）。taichi が読んで、解決にする\n" + \
                   "".join(f"    {x}\n" for x in q751_gate.splitlines())
            open(yp, "w", encoding="utf-8").write(ytxt)
except Exception as e: L.append(f"- 要対応への書き込み（Q751）に失敗（{e}）")

# --- 執行（winnote の S23）2026-11-18 案（判断待ち 48）: 配った後（lab-ops/trade/winnote/S23/heartbeat.json がある）だけ節が出る。★ は要対応に 1 節（消えたら自動で解決）
try:
    import s23_status as S23S
    _l23, _p23 = S23S.lines(V); L.extend(_l23)
    if _l23: S23S.write_node(os.path.join(D, "要対応.md"), _p23, now)
except Exception as e: L.append(f"- S23 の執行の節を作れない（{type(e).__name__}: {e}）")

# --- 要対応
sec("人の判断待ち（要対応.md の ★ で未解決）")
yt = rd(os.path.join(D, "要対応.md")); star, open_, nost = [], 0, 0
for blk in re.split(r"\n(?=## )", yt):
    if not blk.startswith("## "): continue
    title = blk.splitlines()[0][3:].strip()
    sm = re.search(r"^- 状態:\s*(.+)$", blk, re.M)
    if not sm: nost += 1; continue          # 状態行の無い節＝書式が決まる前（2026-10-21 以前）の古い節。数えない
    if sm.group(1).startswith("未解決"):
        open_ += 1
        if "★" in blk: star.append(title)
for t in star[-15:]: L.append(f"- ★ {t[:110]}")
if not star: L.append("- なし")
L.append(f"- 未解決の節: {open_}（★ {len(star)}）" + (f"・状態行なしの古い節 {nost}（解決扱い）" if nost else ""))

open(OUT, "w", encoding="utf-8").write("\n".join(L) + "\n"); print(OUT)
