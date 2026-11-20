# -*- coding: utf-8 -*-
"""状態.md の「執行（winnote の S23）」の節（2026-11-18 案・make_状態.py から呼ぶ）。
winnote の send_status_s23.py が lab-ops の trade/winnote/S23/ に送る heartbeat.json・状態.json・ログを読み、
止まった・dry のまま・停止線・照合の食い違い・発注の失敗を ★ にする。★ があれば要対応.md に節を 1 つ（未解決の同じ題が無いときだけ）、消えたら自動で解決。
配っていない（heartbeat が無い）間は節を出さない。"""
import datetime, glob, json, os, re, subprocess, sys

AUTO_T = "winnote の S23 執行に異常（自動・make_状態.py）"


def _utc(x):
    try: return datetime.datetime.fromisoformat(str(x).replace("Z", "").replace(" ", "T")).replace(tzinfo=datetime.timezone.utc)
    except Exception: return None


def _bad_lines(tail):
    """ログの ★/エラー/Traceback の行。2026-11-19 案（後ろの自走 20261119_2350）: 「照合」の行の ★（記録の足と業者の足が違う）は、
    その後に ★ の無い「照合」の行があれば数えない（後の回で一致した＝取り寄せの前の初回などの一時の食い違い）。
    S21 の「Market closed の後に注文が通れば ★ にしない」（watch_rules.py）と同じ考え。照合以外の ★・エラー・Traceback は今までどおり。
    第 2 版（別の目の点検の後）: 消すのは **起動（「接続:」の行）の後の最初の照合** の ★ だけ（業者が履歴を取り寄せる前の形）。動いている途中の ★ はたまに出ても残す。
    「一致」と数えるのは BTC と ETH の両方を比べた行（「照合 BTC 記録の足 … / ETH 記録の足 …」）で ★ の無いものだけ（「業者の足が取れないか古い」の行は一致に数えない）。"""
    full = re.compile(r" 照合 BTC 記録の足 .* / ETH 記録の足 ")
    last_ok = max((i for i, l in enumerate(tail) if full.search(l) and "★" not in l), default=-1)
    first_after_start, seen = set(), True                                         # 窓の先頭は起動の後かどうか分からないので「最初」に数えない
    for i, l in enumerate(tail):
        if " 接続: " in l: seen = False
        elif " 照合 " in l:
            if not seen: first_after_start.add(i)
            seen = True
    return [l for i, l in enumerate(tail)
            if re.search(r"Traceback|エラー|★", l)
            and not (full.search(l) and "★" in l and "Traceback" not in l and "エラー" not in l and i in first_after_start and i < last_ok)]


def lines(V, now=None, py=None):
    """戻り値 (状態.md に足す行のリスト, ★ の文のリスト)。"""
    WN = os.path.join(V, "lab-ops", "trade", "winnote", "S23"); hbp = os.path.join(WN, "heartbeat.json")
    if not os.path.exists(hbp):
        return [], []
    now = now or datetime.datetime.now(datetime.timezone.utc); out = ["", "## 執行（winnote の S23・XM MT5 デモ）"]; probs = []
    hb = json.load(open(hbp, encoding="utf-8")); bot = hb.get("bot") or {}
    ts, tl = _utc(hb.get("sent_at")), _utc(hb.get("last_log_at"))
    a_s = (now - ts).total_seconds() / 3600 if ts else 999
    a_l = (ts - tl).total_seconds() / 3600 if (ts and tl) else 999                # ログの止まりは送った時刻から測る（S21 と同じ・Mac が受け取れていない回を誤報にしない）
    st = "動いている" if bot.get("running") else ("動いていない" if bot.get("running") is False else "不明")
    if bot.get("running"): st += "（" + ("live" if bot.get("live") else "**dry**") + ("・loop" if bot.get("loop") else "・**loop なし**") + "）"
    out.append(f"- 最後に届いた {ts:%m-%d %H:%M} UTC（{a_s:.1f} 時間前）・送った時点でログの最後から {a_l:.1f} 時間・bot {st}" if ts else "- heartbeat の時刻が読めない")
    if a_s > 3: probs.append(f"S23 の状態が {a_s:.1f} 時間届いていない（winnote か送信が止まった・S21 の節も見る）")
    if a_l > 2: probs.append(f"S23 のログが送った時点で {a_l:.1f} 時間止まっている")
    if bot.get("running") is False: probs.append("S23 の bot（execute_s23_mt5.py）が動いていない")
    if bot.get("running") and (bot.get("n") or 1) != 1: probs.append(f"S23 の bot が {bot.get('n')} 個")
    try:
        s = json.load(open(os.path.join(WN, "状態.json"), encoding="utf-8"))
        rec = s.get("記録と同じ計算") or {}
        out.append(f"- 判断の日 {s.get('判断の日')}・目標 {s.get('目標')}・保有 {s.get('保有')}・停止 {s.get('停止')}・記録と同じ計算の通算 {rec.get('通算', float('nan')) * 100:+.1f}%（最高値から {rec.get('最高値から', float('nan')) * 100:+.1f}%）"
                   f"・決済 {s.get('決済済み')}・スワップの合計 {s.get('スワップの合計', 0):,.0f}")
        if s.get("停止"): probs.append("S23 が停止線（最高値から −30%）で止まっている（停止.flag・再開は人）")
        if s.get("発注の失敗"): probs.append("S23 の直近の回で発注が通らなかった（ログの「入る」「閉じる」の行）")
        if s.get("判断") == "取れない": probs.append("S23 の直近の回で Binance から足を取れなかった")
        tg, hd = s.get("目標") or {}, s.get("保有") or {}
        if s.get("live") and tg and hd and not s.get("取引時間の外") and any(bool(tg.get(c)) != bool(hd.get(c)) for c in tg):
            probs.append(f"S23 の目標 {tg} と保有 {hd} が違う（発注の失敗か手動の決済）")
    except Exception as e:
        out.append(f"- 状態.json を読めない（{type(e).__name__}）")
    logs = sorted(glob.glob(os.path.join(WN, "run_*.log")))[-2:]; tail = []
    for lp in logs: tail += open(lp, encoding="utf-8", errors="replace").read().splitlines()
    bad = _bad_lines(tail[-80:])
    if bad: probs.append(f"S23 のログに ★/エラー {len(bad)} 行（最後: {bad[-1][20:130]}）")
    try:
        cmp = os.path.join(V, "トレード", "執行", "S23", "compare_s23.py")
        vf = os.path.expanduser("~/ワークスペース/作業層/大容量/venv_forward/bin/python")      # 照合は parquet を読むので pyarrow のある python（素の python3 で呼ばれる回があるため）
        r = subprocess.run([py or (vf if os.path.exists(vf) else sys.executable), cmp, "--ledger", os.path.join(WN, "trades.csv"), "--line"], capture_output=True, text=True, timeout=120)
        if r.stdout.strip(): out.append(f"  - 照合: {r.stdout.strip().splitlines()[-1][:220]}")
        elif r.returncode: out.append(f"  - 照合: 動かなかった（{(r.stderr.strip().splitlines() or ['?'])[-1][:160]}）")
    except Exception as e:
        out.append(f"  - 照合: 動かなかった（{type(e).__name__}）")
    for p in probs: out.append(f"- ★ {p}")
    return out, probs


def write_node(yp, probs, now_str):
    """★ があれば要対応.md に節を 1 つ（未解決の同じ題が無いときだけ）、無くなれば解決にする。"""
    y = open(yp, encoding="utf-8").read()
    has_open = re.search(rf"^## [^\n]*{re.escape(AUTO_T)}\n- 状態: 未解決", y, re.M)
    if probs and not has_open:
        y = y.rstrip("\n") + f"\n\n## {now_str[:16]} — ★ {AUTO_T}\n- 状態: 未解決\n" + "".join(f"- {x}\n" for x in probs) + \
            "- 見ること: `lab-ops/trade/winnote/S23/` のログ・状態.json。S21 の bot には触らない。異常が消えたら次の回でこの節は自動で解決になる\n"
        open(yp, "w", encoding="utf-8").write(y)
    elif not probs and has_open:
        y2 = re.sub(rf"(## [^\n]*{re.escape(AUTO_T)}\n- 状態: )未解決", rf"\g<1>解決（自動・{now_str} に正常を確認）", y)
        open(yp, "w", encoding="utf-8").write(y2)
