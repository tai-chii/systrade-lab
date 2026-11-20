# -*- coding: utf-8 -*-
"""winnote（Windows）へ運ぶ zip を作る。標準ライブラリだけ（Mac でも device の Linux でも動く）。
中身（ワークスペースからの相対パスをそのまま保つ。Windows 側では C:\\Users\\<名前>\\bot\\ に展開する）:
  検証/トレード/forward/common.py・S21/forward_s21.py・S21/凍結/
  検証/トレード/執行/S21/（signal_s21.py・execute_mt5.py・compare_record.py・README）
  検証/verification-lab/financial-engineering/s21-h1-ml-rr-weekcap-q515/*.py・tools/mt5/mt5_fetch.py
  検証/_データ/fetch/*.py・検証/学問/金融工学/作業/ML自動売買/*.py（common.py が sys.path に足すもの）
出力: 検証/lab-ops/trade/S21_bot_YYYYMMDD.zip（private リポジトリ。業者のデータは入れない）
使い方: python3 deploy.py [--out PATH]"""
import argparse, glob, os, zipfile, datetime as dt
HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
ITEMS = [
    "検証/トレード/forward/common.py", "検証/トレード/forward/S21/forward_s21.py", "検証/トレード/forward/S21/凍結/*",
    "検証/トレード/執行/README.md", "検証/トレード/執行/S21/*.py", "検証/トレード/執行/S21/README_windows.md",
    "検証/verification-lab/financial-engineering/s21-h1-ml-rr-weekcap-q515/*.py", "検証/verification-lab/tools/mt5/mt5_fetch.py",
    "検証/_データ/fetch/*.py", "検証/学問/金融工学/作業/ML自動売買/*.py",
]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default=None); a = ap.parse_args()
    out = a.out or os.path.join(WS, "検証", "lab-ops", "trade", f"S21_bot_{dt.date.today():%Y%m%d}.zip")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    n = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for pat in ITEMS:
            files = sorted(glob.glob(os.path.join(WS, pat)))
            if not files:
                print(f"見つからない: {pat}")
            for f in files:
                if os.path.isfile(f):
                    z.write(f, os.path.relpath(f, WS)); n += 1
    print(f"{n} ファイル → {out}（{os.path.getsize(out) / 1e6:.1f} MB）")


if __name__ == "__main__":
    main()
