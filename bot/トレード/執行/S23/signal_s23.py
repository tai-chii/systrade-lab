# -*- coding: utf-8 -*-
"""S23（暗号資産は上昇トレンドのときだけ買って持つ）の「今どちらを持つべきか」を、記録と同じプログラムで出す。売買はしない。

やり方: 記録の forward_s23.py の main() を、**データの置き場所と出力先だけ一時フォルダに替えて**そのまま走らせ、
出てきた 状態.json の「次の売買日の保有」を目標にする。判断の計算（日足の作り方・60 本の比較・停止線）を書き写さないので、
記録と執行で判断がずれるのは「取った足の時点」だけになる（S21 の signal_s21.py と同じ考え・2026-11-18 午後の自走）。

入力: Binance の 1 時間足の parquet（BTC.parquet・ETH.parquet。forward_s23.fetch と同じ形）が入ったフォルダ
出力: dict（JSON にできる）
  coins   : {BTC/ETH: {日, 終値, 六十本前, 保有(bool)}}   日＝最後に締まった営業日（21:00 UTC 区切り）。保有＝その日の終値で決めた次の始値からの保有
  record  : {通算, 最高値から, 停止(list)}                 記録と同じ計算の、FORWARD_START からの成績（停止線 −30% の判定に使う）
  closed  : 今が取引時間の外（金 21:00〜日 21:00 UTC）か。外なら執行しない（記録は週明けの始値で入る）
  last_h1 : 各銘柄の最後の確定した 1 時間足（UTC）
使い方（確認用・Mac でも動く）: python signal_s23.py [--h1 DIR] [--fetch] [--now ISO]
  --fetch を付けると Binance から取り直して DIR（既定は一時フォルダ）に置く。記録のデータの置き場所には書かない。
"""
import argparse, contextlib, io, json, os, shutil, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
FWD = os.environ.get("S23_FORWARD_DIR") or os.path.abspath(os.path.join(HERE, "..", "..", "forward"))   # 検証/トレード/forward
sys.path.insert(0, FWD); sys.path.insert(0, os.path.join(FWD, "S23"))
import common as C                                                        # noqa: E402  sys.path に検証コード（S23_CODE・S22_CODE）を足す
import numpy as np, pandas as pd                                          # noqa: E402
import forward_s23 as FS                                                  # noqa: E402  記録のプログラムそのもの
import crypto_core as CC                                                  # noqa: E402  closed_mask（取引時間）

COINS = ["BTC", "ETH"]


def closed_now(now):
    """今が取引時間の外か（記録の日足が使う取引時間＝crypto_core.closed_mask と同じ定義）。"""
    return bool(CC.closed_mask(pd.Series([pd.Timestamp(now).floor("h")]))[0])


def fetch_to(dirpath):
    """記録と同じ取得の関数（forward_s23.fetch）を、置き場所だけ dirpath に替えて呼ぶ。記録の置き場所には書かない。"""
    os.makedirs(dirpath, exist_ok=True)
    old = FS.DATA; FS.DATA = dirpath
    try:
        for c in COINS:
            FS.fetch(c)
    finally:
        FS.DATA = old


def _truncate(src, dst, now):
    """now の時点で締まっている 1 時間足だけを dst に写す（再生の試験用。本番は取った時点で締まった足だけなので同じ）。"""
    for c in COINS:
        d = pd.read_parquet(os.path.join(src, f"{c}.parquet"))
        if now is not None:
            d = d[d["time"] + pd.Timedelta(hours=1) <= pd.Timestamp(now)]
        d.to_parquet(os.path.join(dst, f"{c}.parquet"), index=False)


def decide(h1dir, now=None, start=None):
    """h1dir の足で記録のプログラムを走らせ、目標の保有を返す。h1dir には書かない（一時フォルダに写して走らせる）。"""
    now = pd.Timestamp(now) if now is not None else pd.Timestamp.now(tz="UTC")
    work = tempfile.mkdtemp(prefix="s23_sig_"); dat = os.path.join(work, "h1"); out = os.path.join(work, "out"); os.makedirs(dat); os.makedirs(out)
    try:
        _truncate(h1dir, dat, now)
        last_h1 = {c: str(pd.read_parquet(os.path.join(dat, f"{c}.parquet"))["time"].max()) for c in COINS}
        old_data, old_argv = FS.DATA, sys.argv
        FS.DATA = dat
        sys.argv = ["forward_s23.py", "--no-fetch", "--out", out] + (["--start", str(start)] if start else [])
        buf = io.StringIO(); code = 0
        try:
            with contextlib.redirect_stdout(buf):
                FS.main()
        except SystemExit as e:                                            # 停止線に達すると記録は exit 3（状態.json は書いた後）
            code = e.code if isinstance(e.code, int) else 1
        finally:
            FS.DATA, sys.argv = old_data, old_argv
        st = json.load(open(os.path.join(out, "状態.json"), encoding="utf-8"))
        daily = pd.read_csv(os.path.join(out, "daily.csv"), index_col=0) if os.path.exists(os.path.join(out, "daily.csv")) else None
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return dict(asof=str(now), coins=st["次の売買日の保有"], record=dict(通算=st["通算"], 最高値から=st["最高値から"], 停止=st["停止"], 記録日数=st["記録日数"]),
                exit_code=code, closed=closed_now(now), last_h1=last_h1, daily=daily)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--h1", default=None); ap.add_argument("--fetch", action="store_true"); ap.add_argument("--now", default=None)
    a = ap.parse_args()
    h1 = a.h1 or tempfile.mkdtemp(prefix="s23_h1_")
    if a.fetch:
        fetch_to(h1)
    r = decide(h1, a.now); r.pop("daily", None)
    print(json.dumps(r, ensure_ascii=False, indent=1, default=str))


if __name__ == "__main__":
    main()
