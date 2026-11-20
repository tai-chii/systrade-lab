# -*- coding: utf-8 -*-
"""S23（暗号資産は上昇トレンドのときだけ買って持つ）のフォワード記録（日次）。検証（Q529）と同じ関数を使う。
- データ: Binance 現物 BTCUSDT・ETHUSDT の 1 時間足（REST）→ Fintokei の取引時間（週末休み）だけ残して 21:00 UTC 区切りの日足
- 規則: 日足終値が 60 本前より高ければ次の始値から保有（ロングのみ）。BTC・ETH 半分ずつ・名目 1 倍。コスト BTC 0.02%／ETH 0.075%（片道）
- 停止: 最高値から −30%（名目 1 倍換算）
使い方: python3 forward_s23.py [--start ISO] [--out DIR]"""
import argparse, json, os, sys, time, urllib.request
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import common as C
import numpy as np, pandas as pd
import run_q529 as R

HERE = os.path.dirname(os.path.abspath(__file__)); DATA = os.path.join(C.FWD_DATA, "crypto_h1")
L = 60; STOP_DD = -0.30; HIST_FROM = "2026-01-01"


def fetch(coin):
    url = "https://api.binance.com/api/v3/klines?symbol={}USDT&interval=1h&limit=1000&startTime={}"
    t = int(pd.Timestamp(HIST_FROM, tz="UTC").timestamp() * 1000); rows = []
    now_ms = int(time.time() * 1000)
    while True:
        for k in range(4):
            try:
                b = json.loads(urllib.request.urlopen(url.format(coin, t), timeout=30).read()); break
            except Exception:
                time.sleep(2 + 3 * k)
        else:
            raise RuntimeError(f"{coin}: Binance から取れない")
        if not b:
            break
        rows += [r for r in b if r[6] < now_ms]          # 終わった足だけ
        if len(b) < 1000:
            break
        t = b[-1][0] + 3600_000
    df = pd.DataFrame({"time": pd.to_datetime([r[0] for r in rows], unit="ms", utc=True), "open": [float(r[1]) for r in rows],
                       "high": [float(r[2]) for r in rows], "low": [float(r[3]) for r in rows], "close": [float(r[4]) for r in rows],
                       "volume": [float(r[5]) for r in rows], "qvol": [float(r[7]) for r in rows], "trades": [int(r[8]) for r in rows],
                       "taker_base": [float(r[9]) for r in rows]}).drop_duplicates("time").sort_values("time")
    os.makedirs(DATA, exist_ok=True); df.to_parquet(os.path.join(DATA, f"{coin}.parquet"), index=False)
    return df


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--start", default=C.FORWARD_START); ap.add_argument("--out", default=os.path.join(HERE, "記録"))
    ap.add_argument("--no-fetch", action="store_true"); a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)
    start = pd.Timestamp(a.start)
    parts, pos_tab, last_sig = [], {}, {}
    for coin in ["BTC", "ETH"]:
        h1 = fetch(coin) if not a.no_fetch else None
        b = R.daily_series(DATA, coin)
        last_h1 = pd.read_parquet(os.path.join(DATA, f"{coin}.parquet"))["time"].max()
        day_end = b["g"] - R.C.SHIFT + pd.Timedelta(days=1)          # その日足が締まる時刻（UTC）
        b = b[day_end <= last_h1 + pd.Timedelta(hours=1)].reset_index(drop=True)   # 締まっていない日を落とす
        pos = R.tsmom(b, L)
        pnl = R.backtest(b, pos, R.HALF[coin])
        pnl.iloc[-1] = 0.0 if not np.isfinite(b["exec_px"].iloc[-1]) else pnl.iloc[-1]
        parts.append(pnl.rename(coin)); pos_tab[coin] = pd.Series(pos, index=b["day"].to_numpy())
        last_sig[coin] = dict(日=str(b["day"].iloc[-1])[:10], 終値=float(b["close"].iloc[-1]), 六十本前=float(b["close"].iloc[-1 - L]), 保有=bool(pos[-1]))
    # backtest の損益 t = 「t の終値で決めた保有 × 次の始値→その次の始値」。最後の日の分はまだ確定していないので除く
    df = pd.concat(parts, axis=1).iloc[:-1].fillna(0.0)
    first_day = (start + R.C.SHIFT).tz_convert(None).normalize()
    idx = pd.DatetimeIndex(pd.to_datetime(df.index)).tz_localize(None) if pd.DatetimeIndex(pd.to_datetime(df.index)).tz is not None else pd.DatetimeIndex(pd.to_datetime(df.index))
    df.index = idx; df = df[df.index >= first_day]
    df["合成"] = df[["BTC", "ETH"]].mean(axis=1)
    eq = (1 + df["合成"]).cumprod() if len(df) else pd.Series(dtype=float)
    dd = float((eq / eq.cummax().clip(lower=1.0) - 1).min()) if len(eq) else 0.0
    total = float(eq.iloc[-1] - 1) if len(eq) else 0.0
    for coin in pos_tab:
        p = pos_tab[coin]; p.index = pd.DatetimeIndex(pd.to_datetime(p.index)).tz_localize(None) if pd.DatetimeIndex(pd.to_datetime(p.index)).tz is not None else pd.DatetimeIndex(pd.to_datetime(p.index))
        df[f"保有_{coin}"] = p.reindex(df.index)
    df.assign(資産=eq).to_csv(os.path.join(a.out, "daily.csv"))
    st = dict(記録日数=int(len(df)), 通算=total, 最高値から=dd, 停止=[f"最高値から {dd*100:.1f}%（停止線 −30%）"] if dd <= STOP_DD else [],
              次の売買日の保有=last_sig, 更新=time.strftime("%Y-%m-%d %H:%M"))
    C.write_json(os.path.join(a.out, "状態.json"), st)
    print(json.dumps(st, ensure_ascii=False, indent=1, default=str))
    if st["停止"]:
        print("★ 停止条件に達した"); sys.exit(3)


if __name__ == "__main__":
    main()
