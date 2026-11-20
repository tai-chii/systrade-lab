# -*- coding: utf-8 -*-
"""bot の判断の spr_R を記録（Dukascopy）に揃えるための参照表 spr_ref.json を作る（Mac で実行・2026-11-04 taichi「A: 記録に揃える」）。

S21 のモデルは「足の終値のスプレッド ÷ D」（spr_R・重要度 1 位）を入力に使う。bot が XM のスプレッドを入れると判断が記録と別物になる
（監査B: 10 月の合図の一致 46.6%・FX の合図が 41% → 9%）。bot は XM のスプレッドの代わりに、この表の
「銘柄 × ニューヨーク時間の時（0〜23）ごとの Dukascopy の終値スプレッドの中央値」を入れる。
過去 2 か月の照合（scratchpad の sprref・XM の足）: 一致 46.6% → 68.8%（10 月）・44.7% → 71.8%（9 月）、銘柄の構成は記録どおりに戻る。
実際の Dukascopy のスプレッドを入れた上限は 75.6%・76.8%。残りは足の値の差。3 か月前の表でも 66.6% なので、作り直しは月 1 回で足りる。

入力: 作業層/大容量/market_data_forward/H1/<銘柄>.parquet（記録と同じデータ）。直近 --days 日（既定 56）。
出力: 同じフォルダの spr_ref.json（{"meta": {...}, "spr": {銘柄: [24 個・値段の単位]}}）。winnote の bot のフォルダへ配る。
使い方: python make_spr_ref.py [--days 56] [--out spr_ref.json]"""
import argparse, datetime as dt, json, os
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
H1 = os.path.join(WS, "作業層", "大容量", "market_data_forward", "H1")
SYMS = ["EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "USDJPY", "USDCHF", "USDCAD", "EURJPY", "GBPJPY", "EURGBP",
        "XAUUSD", "US500", "USTECH", "GER40", "JPN225", "AUDJPY", "CADJPY", "CHFJPY", "NZDJPY"]
TZ = "America/New_York"                  # FX の日替わり（スプレッドが開く時刻）は NY 17:00 で、米国の夏時間に付いて動く


def table(d, days):
    d = d[d["high"] != d["low"]]
    end = d["time"].max(); d = d[d["time"] > end - pd.Timedelta(days=days)]
    sp = (d["ask_close"] - d["close"]).clip(lower=0)
    h = d["time"].dt.tz_convert(TZ).dt.hour
    g = sp.groupby(h).median(); med = float(sp.median())
    return [float(g.get(k, med)) for k in range(24)], d["time"].min(), end, len(d)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--days", type=int, default=56)
    ap.add_argument("--out", default=os.path.join(HERE, "spr_ref.json")); a = ap.parse_args()
    out = {"meta": {"made_utc": f"{dt.datetime.now(dt.timezone.utc):%Y-%m-%d %H:%M}", "source": "Dukascopy H1（market_data_forward）",
                    "key": f"{TZ} の時（足の始まりの時刻）", "stat": "終値の ask−bid の中央値", "days": a.days}, "spr": {}}
    rng = []
    for s in SYMS:
        d = pd.read_parquet(os.path.join(H1, f"{s}.parquet"))
        v, t0, t1, n = table(d, a.days)
        out["spr"][s] = v; rng.append((t0, t1))
        print(f"{s:7s} {n:5d} 本  中央値 {np.median(v):.6g}  最小 {min(v):.6g}  最大 {max(v):.6g}")
    out["meta"]["from_utc"] = str(min(r[0] for r in rng)); out["meta"]["to_utc"] = str(max(r[1] for r in rng))
    json.dump(out, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"→ {a.out}（{out['meta']['from_utc']} 〜 {out['meta']['to_utc']}）")


if __name__ == "__main__":
    main()
