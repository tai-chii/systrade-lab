# -*- coding: utf-8 -*-
"""send_status.py — winnote の S21 執行の状態を lab-ops に送る（2026-10-31 新設・標準ライブラリだけ）。
なぜ: 台帳とログが winnote の中にしか無く、bot が止まっても帰宅して画面を見るまで誰も気づけなかった（2026-10-31）。
やること（1 回の起動で）:
  1. 台帳/trades.csv・状態.json・ログ/run_<今月>.log と <前月>.log を lab-ops/trade/winnote/S21/ に写す
  2. 同じ場所に heartbeat.json を書く: 送った時刻・PC 名・ログの最後の行の時刻・台帳の行数・execute_mt5.py が動いているか（--live 付きか）
     ・bot が読むファイルのハッシュ（files。CR を除いた sha256 の先頭 16 文字。Mac の make_状態.py が正本と比べる・2026-11-05 監査B の 6）
     ・Windows Update の再起動の予報（win_update。再起動待ち・一時停止の期限・アクティブ時間・自動ログイン・起動の時刻。読むだけ・2026-11-16）
  3. その 1 フォルダだけを git add → commit → pull --rebase --autostash → push（失敗したら 1 回やり直す）
Mac 側: 自動実行/make_状態.py が heartbeat.json を読み、古い・bot が動いていないときに 状態.md と 要対応.md に ★ を出す。
使い方（winnote・PowerShell）:
  python send_status.py                    # 送る（lab-ops の場所は既定 C:\\Users\\<名前>\\lab-ops。違えば --lab-ops）
  python send_status.py --no-push          # 写すだけ（確認用）
定期実行（1 時間ごと・1 回だけ登録）: README_windows.md の「状態を Mac へ送る」"""
import argparse, datetime as dt, json, os, re, shutil, socket, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(HERE, "ログ")
SUB = os.path.join("trade", "winnote", "S21")


def utcnow():
    return dt.datetime.now(dt.timezone.utc)


def mylog(msg):
    os.makedirs(LOG_DIR, exist_ok=True)
    line = f"{utcnow():%Y-%m-%d %H:%M:%S} {msg}"
    print(line, flush=True)
    with open(os.path.join(LOG_DIR, "send_status.log"), "a", encoding="utf-8") as f:
        f.write(line + "\n")


def last_log_time():
    """ログ（run_YYYYMM.log）の最後の行の先頭の時刻（UTC）。execute_mt5.log() の書式 'YYYY-mm-dd HH:MM:SS 本文'"""
    logs = sorted(x for x in os.listdir(LOG_DIR) if re.match(r"run_\d{6}\.log$", x)) if os.path.isdir(LOG_DIR) else []
    for name in reversed(logs):
        try:
            with open(os.path.join(LOG_DIR, name), "rb") as f:
                f.seek(0, 2); n = f.tell(); f.seek(max(0, n - 8192))
                tail = f.read().decode("utf-8", "replace").splitlines()
        except OSError:
            continue
        for ln in reversed(tail):
            m = re.match(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) ", ln)
            if m:
                return m.group(1) + "Z", ln[20:160]
    return None, None


def bot_process():
    """execute_mt5.py を実行中の python があるか。Windows は PowerShell の Win32_Process、他は ps。分からなければ None"""
    try:
        if os.name == "nt":
            cmd = ["powershell", "-NoProfile", "-Command",
                   "Get-CimInstance Win32_Process -Filter \"Name like 'python%'\" | ForEach-Object { $_.CommandLine }"]
        else:
            cmd = ["ps", "-eo", "args"]
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=60, encoding="utf-8", errors="replace").stdout
        lines = [x for x in out.splitlines() if "execute_mt5.py" in x and "send_status" not in x]
        return {"running": bool(lines), "live": any("--live" in x for x in lines), "loop": any("--loop" in x for x in lines), "n": len(lines)}
    except Exception as e:
        return {"running": None, "error": str(e)[:200]}


# bot が判断と発注に使うファイル（検証/ からの相対パス）。Mac の正本と同じであるべきもの（2026-11-05・監査B の 6）
WATCH = ["トレード/執行/S21/execute_mt5.py", "トレード/執行/S21/signal_s21.py", "トレード/執行/S21/spr_ref.json",
         "トレード/forward/common.py", "トレード/forward/S21/forward_s21.py",
         *[f"トレード/forward/S21/凍結/{f}" for f in ["model_a0.txt", "model_a1.txt", "model_a2.txt", "model_a3.txt", "model_a4.txt", "model_a5.txt", "features.json", "config.json", "hashes.json"]],
         *[f"verification-lab/financial-engineering/s21-h1-ml-rr-weekcap-q515/{f}" for f in ["kensho_s21_h1_ml_rr_q515.py", "kensho_s21_m1_resolve_q523.py", "kensho_s21_walkforward_q518.py",
                                                                                         "kensho_s21d_relthr_wf_q519.py", "kensho_s21f_mtf_wf_q521.py", "kensho_s21f_newjpy_q524.py"]],
         "_データ/fetch/convert_histdata_m15.py", "verification-lab/tools/mt5/mt5_fetch.py"]


def file_hashes(root=None):
    """WATCH の各ファイルの、CR を除いた sha256 の先頭 16 文字（無ければ None）。root は 検証/（既定はこのファイルの 3 つ上）。"""
    import hashlib
    root = root or os.path.abspath(os.path.join(HERE, "..", "..", ".."))
    out = {}
    for rel in WATCH:
        p = os.path.join(root, *rel.split("/"))
        try:
            out[rel] = hashlib.sha256(open(p, "rb").read().replace(b"\r", b"")).hexdigest()[:16]
        except OSError:
            out[rel] = None
    return out


def win_update(reg=None, now=None):
    """Windows Update の再起動の予報（2026-11-16・判断待ち 20 の残りの穴）。読むだけ・設定は変えない。
    なぜ: 11-11 03:48 JST に更新の自動再起動が来て、誰もログインしないまま bot が 13 時間 40 分止まった。自動の再起動はアクティブ時間の外
    （winnote は 7:00〜1:00 → 1:00〜7:00 JST＝市場の開いている時間）に来るので、「再起動待ち」が立った時点で Mac に ★ を出し、土日に手で再起動できるようにする。
    返り値（heartbeat の win_update）: reboot_required・reboot_pending（再起動待ちの印のキーがあるか）・pause_until・pause_quality_until（一時停止の期限の文字列）
    ・active_hours（[始, 終] 時・winnote の時計）・auto_logon（自動ログインが入か。値 AutoAdminLogon だけを読み、パスワードの値は読まない）
    ・boot_at（最後に起動した時刻 UTC）・utc_offset_h（winnote の時計の UTC からのずれ）。分からない項目は None。Windows でなければ None。
    どこで失敗しても例外を外へ出さない（heartbeat を送るのが本来の役目なので、ここで止めない）。reg は試験用（偽の winreg）。"""
    try:
        if reg is None:
            if os.name != "nt":
                return None
            import winreg as reg
        H = reg.HKEY_LOCAL_MACHINE
        acc = reg.KEY_READ | getattr(reg, "KEY_WOW64_64KEY", 0)                         # 32 ビットの python でも 64 ビットの側を読む

        def exists(path):
            try:
                k = reg.OpenKey(H, path, 0, acc); reg.CloseKey(k); return True
            except FileNotFoundError:
                return False
            except OSError:
                return None

        def val(path, name):
            try:
                k = reg.OpenKey(H, path, 0, acc)
                try:
                    return reg.QueryValueEx(k, name)[0]
                finally:
                    reg.CloseKey(k)
            except OSError:                                                              # 無い（FileNotFoundError）も読めないも None
                return None

        UX = r"SOFTWARE\Microsoft\WindowsUpdate\UX\Settings"
        s, e = val(UX, "ActiveHoursStart"), val(UX, "ActiveHoursEnd")
        al = val(r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon", "AutoAdminLogon")
        pu, pq = val(UX, "PauseUpdatesExpiryTime"), val(UX, "PauseQualityUpdatesEndTime")
        out = {"reboot_required": exists(r"SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired"),
               "reboot_pending": exists(r"SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending"),
               "pause_until": None if pu is None else str(pu),
               "pause_quality_until": None if pq is None else str(pq),
               "active_hours": [s, e] if isinstance(s, int) and isinstance(e, int) else None,
               "auto_logon": None if al is None else str(al).strip() == "1",
               "boot_at": None, "utc_offset_h": None}
        try:
            out["utc_offset_h"] = dt.datetime.now().astimezone().utcoffset().total_seconds() / 3600
        except Exception:
            pass
        try:
            import ctypes
            f = ctypes.windll.kernel32.GetTickCount64; f.restype = ctypes.c_ulonglong
            out["boot_at"] = ((now or utcnow()) - dt.timedelta(milliseconds=int(f()))).strftime("%Y-%m-%dT%H:%M:%SZ")
        except Exception:
            pass
        return out
    except Exception as ex:
        return {"error": str(ex)[:200]}


def ledger_rows(p):
    try:
        with open(p, encoding="utf-8") as f:
            return max(0, sum(1 for _ in f) - 1)
    except OSError:
        return None


def git(repo, *args):
    r = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
    return r.returncode, (r.stdout + r.stderr).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lab-ops", default=os.path.join(os.path.expanduser("~"), "lab-ops"))
    ap.add_argument("--no-push", action="store_true")
    a = ap.parse_args()
    repo = a.lab_ops
    if not os.path.isdir(os.path.join(repo, ".git")):
        mylog(f"lab-ops が見つからない: {repo}（--lab-ops で場所を指定）"); sys.exit(1)
    dst = os.path.join(repo, SUB); os.makedirs(dst, exist_ok=True)
    now = utcnow(); prev = (now.replace(day=1) - dt.timedelta(days=1))
    copied = []
    for src, name in [(os.path.join(HERE, "台帳", "trades.csv"), "trades.csv"), (os.path.join(HERE, "状態.json"), "状態.json"),
                      (os.path.join(LOG_DIR, f"run_{prev:%Y%m}.log"), f"run_{prev:%Y%m}.log"),
                      (os.path.join(LOG_DIR, f"run_{now:%Y%m}.log"), f"run_{now:%Y%m}.log")]:
        if os.path.exists(src):
            shutil.copyfile(src, os.path.join(dst, name)); copied.append(name)
    t_last, line_last = last_log_time()
    hb = {"pc": socket.gethostname(), "sent_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "last_log_at": t_last, "last_log_line": line_last,
          "ledger_rows": ledger_rows(os.path.join(HERE, "台帳", "trades.csv")), "bot": bot_process(), "copied": copied, "files": file_hashes(), "win_update": win_update(),
          "note": "send_status.py が 1 時間ごとに書く。sent_at が古い＝PC か送信が止まっている／last_log_at が古い・bot.running=false＝bot が止まっている"}
    json.dump(hb, open(os.path.join(dst, "heartbeat.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    mylog(f"写した {copied}・ログの最後 {t_last}・bot {hb['bot']}")
    if a.no_push:
        return
    rc, out = git(repo, "add", "--", SUB)
    if rc: mylog(f"git add 失敗: {out[:300]}"); sys.exit(1)
    if git(repo, "diff", "--cached", "--quiet", "--", SUB)[0] != 0:  # 変わったものがあるときだけ commit（heartbeat は毎回変わる）
        rc, out = git(repo, "commit", "-q", "-m", f"winnote: S21 執行の状態 {now:%Y-%m-%d %H:%M}Z", "--", SUB)
        if rc: mylog(f"git commit 失敗: {out[:300]}"); sys.exit(1)
    for i in range(2):
        rc1, o1 = git(repo, "pull", "--rebase", "--autostash", "-q")
        rc2, o2 = git(repo, "push", "-q") if rc1 == 0 else (rc1, o1)
        if rc1 == 0 and rc2 == 0:
            mylog("push した"); return
        mylog(f"push 失敗（{i + 1} 回目）: {(o1 + ' ' + o2)[:300]}")
    sys.exit(1)


if __name__ == "__main__":
    main()
