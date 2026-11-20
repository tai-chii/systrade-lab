# -*- coding: utf-8 -*-
"""send_status_s23.py — winnote の S23 執行の状態を lab-ops の trade/winnote/S23/ に送る（2026-11-18 案・標準ライブラリだけ）。
S21 の send_status.py と同じ形（台帳・状態・今月と前月のログ・heartbeat.json を写して、その 1 フォルダだけ commit・push）。
Windows Update の予報は S21 の heartbeat に出ているので、ここでは送らない。
使い方（winnote・PowerShell）: python send_status_s23.py [--lab-ops C:\\Users\\<名前>\\lab-ops] [--no-push]
定期実行: S21 と同じく 1 時間ごと（タスク名 S23_send_status）。"""
import argparse, datetime as dt, hashlib, json, os, re, shutil, socket, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(HERE, "ログ")
SUB = os.path.join("trade", "winnote", "S23")
KENSHO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
WATCH = ["トレード/執行/S23/execute_s23_mt5.py", "トレード/執行/S23/signal_s23.py", "トレード/forward/common.py", "トレード/forward/S23/forward_s23.py",
         "verification-lab/financial-engineering/s23-crypto-uptrend-long-q529/run_q529.py", "verification-lab/financial-engineering/s22-crypto-ml-fintokei-q528/crypto_core.py"]


def utcnow():
    return dt.datetime.now(dt.timezone.utc)


def mylog(msg):
    os.makedirs(LOG_DIR, exist_ok=True)
    line = f"{utcnow():%Y-%m-%d %H:%M:%S} {msg}"
    print(line, flush=True)
    with open(os.path.join(LOG_DIR, "send_status.log"), "a", encoding="utf-8") as f:
        f.write(line + "\n")


def last_log_time():
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
    try:
        if os.name == "nt":
            cmd = ["powershell", "-NoProfile", "-Command",
                   "Get-CimInstance Win32_Process -Filter \"Name like 'python%'\" | ForEach-Object { $_.CommandLine }"]
        else:
            cmd = ["ps", "-eo", "args"]
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=60, encoding="utf-8", errors="replace").stdout
        lines = [x for x in out.splitlines() if "execute_s23_mt5.py" in x and "send_status" not in x]
        return {"running": bool(lines), "live": any("--live" in x for x in lines), "loop": any("--loop" in x for x in lines), "n": len(lines)}
    except Exception as e:
        return {"running": None, "error": str(e)[:200]}


def file_hashes():
    """bot が読むファイルのハッシュ（CR を除いた sha256 の先頭 16 文字・S21 と同じ書き方）。Mac の正本と比べる。"""
    out = {}
    for rel in WATCH:
        p = os.path.join(KENSHO, *rel.split("/"))
        try:
            out[rel] = hashlib.sha256(open(p, "rb").read().replace(b"\r", b"")).hexdigest()[:16]
        except OSError:
            out[rel] = None
    return out


def git(repo, *args):
    r = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
    return r.returncode, (r.stdout + r.stderr).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lab-ops", default=os.path.join(os.path.expanduser("~"), "lab-ops"))
    ap.add_argument("--no-push", action="store_true")
    a = ap.parse_args(); repo = a.lab_ops
    if not os.path.isdir(os.path.join(repo, ".git")):
        mylog(f"lab-ops が見つからない: {repo}（--lab-ops で場所を指定）"); sys.exit(1)
    dst = os.path.join(repo, SUB); os.makedirs(dst, exist_ok=True)
    now = utcnow(); prev = (now.replace(day=1) - dt.timedelta(days=1)); copied = []
    for src, name in [(os.path.join(HERE, "台帳", "trades.csv"), "trades.csv"), (os.path.join(HERE, "状態.json"), "状態.json"),
                      (os.path.join(LOG_DIR, f"run_{prev:%Y%m}.log"), f"run_{prev:%Y%m}.log"), (os.path.join(LOG_DIR, f"run_{now:%Y%m}.log"), f"run_{now:%Y%m}.log")]:
        if os.path.exists(src):
            shutil.copyfile(src, os.path.join(dst, name)); copied.append(name)
    t_last, line_last = last_log_time()
    hb = {"pc": socket.gethostname(), "sent_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "last_log_at": t_last, "last_log_line": line_last,
          "bot": bot_process(), "copied": copied, "files": file_hashes(),
          "note": "send_status_s23.py が 1 時間ごとに書く。S23 は毎時 :00:30 に 1 行以上ログを書くので、last_log_at が 2 時間より古ければ止まっている"}
    json.dump(hb, open(os.path.join(dst, "heartbeat.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    mylog(f"写した {copied}・ログの最後 {t_last}・bot {hb['bot']}")
    if a.no_push:
        return
    rc, out = git(repo, "add", "--", SUB)
    if rc: mylog(f"git add 失敗: {out[:300]}"); sys.exit(1)
    if git(repo, "diff", "--cached", "--quiet", "--", SUB)[0] != 0:
        rc, out = git(repo, "commit", "-q", "-m", f"winnote: S23 執行の状態 {now:%Y-%m-%d %H:%M}Z", "--", SUB)
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
