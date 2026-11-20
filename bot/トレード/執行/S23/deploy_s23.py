# -*- coding: utf-8 -*-
"""winnote へ運ぶ S23 の zip を作る（標準ライブラリだけ・2026-11-18 案）。S21 の deploy.py と同じ形（ワークスペースからの相対パスを保つ）。
中身: forward の common.py と S23/forward_s23.py（判断は記録のプログラムそのもの）・検証コード（run_q529.py・crypto_core.py）・
      tools/mt5/mt5_fetch.py・執行/S23/ の .py と README。業者のデータ・台帳・config.json は入れない。
Windows 側では S21 と同じ C:\\Users\\<名前>\\bot\\ に展開する（S21 のファイルは上書きしない＝共通の common.py・mt5_fetch.py は中身が同じ版であること）。
使い方: python3 deploy_s23.py [--out PATH]（既定 lab-ops/trade/S23_bot_YYYYMMDD.zip）"""
import argparse, glob, hashlib, os, zipfile, datetime as dt
HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
ITEMS = [
    "検証/トレード/forward/common.py", "検証/トレード/forward/S23/forward_s23.py",
    "検証/verification-lab/financial-engineering/s23-crypto-uptrend-long-q529/run_q529.py",
    "検証/verification-lab/financial-engineering/s22-crypto-ml-fintokei-q528/crypto_core.py",
    "検証/verification-lab/tools/mt5/mt5_fetch.py",
    "検証/トレード/執行/S23/*.py", "検証/トレード/執行/S23/README.md",
]


SHARED = {"検証/トレード/forward/common.py": "トレード/forward/common.py", "検証/verification-lab/tools/mt5/mt5_fetch.py": "verification-lab/tools/mt5/mt5_fetch.py"}   # S21 も読むファイル（heartbeat の files の鍵）


def check_shared(ws):
    """S21 と共有のファイルが、winnote の S21 が今読んでいる版（lab-ops の heartbeat の files・CR を除いた sha256 の先頭 16）と同じか（点検 12）。
    違えば止める（S23 の zip が S21 の版を黙って入れ替えないように）。heartbeat に載っていないファイルは winnote 側の台本が置き先と比べる。"""
    import json
    hb = os.path.join(ws, "検証", "lab-ops", "trade", "winnote", "S21", "heartbeat.json")
    if not os.path.exists(hb):
        print("注意: S21 の heartbeat が無い（共有のファイルの確かめは winnote 側の台本だけ）"); return
    files = json.load(open(hb, encoding="utf-8")).get("files") or {}
    for rel, key in SHARED.items():
        if key is None or key not in files: continue
        mine = hashlib.sha256(open(os.path.join(ws, rel), "rb").read().replace(b"\r", b"")).hexdigest()[:16]
        if files[key] and files[key] != mine:
            raise SystemExit(f"止める: {rel} が winnote の S21 の版（{files[key]}）と違う（Mac {mine}）。先に S21 の配備で揃える")
    print("共有のファイルは winnote の S21 の版と同じ")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default=None); ap.add_argument("--ws", default=WS); a = ap.parse_args()
    check_shared(a.ws)
    out = a.out or os.path.join(a.ws, "検証", "lab-ops", "trade", f"S23_bot_{dt.date.today():%Y%m%d}.zip")
    os.makedirs(os.path.dirname(out), exist_ok=True); n = 0; miss = []
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for pat in ITEMS:
            files = sorted(glob.glob(os.path.join(a.ws, pat)))
            if not files:
                miss.append(pat)
            for f in files:
                if os.path.isfile(f):
                    z.write(f, os.path.relpath(f, a.ws)); n += 1
                    print(f"  {hashlib.sha256(open(f, 'rb').read()).hexdigest()[:12]} {os.path.relpath(f, a.ws)}")
    print(f"{n} ファイル → {out}（{os.path.getsize(out) / 1e6:.2f} MB）")
    if miss:
        print("見つからない: " + "・".join(miss)); raise SystemExit(1)


if __name__ == "__main__":
    main()
