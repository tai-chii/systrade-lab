# -*- coding: utf-8 -*-
"""フォワード用データの取得（Dukascopy・19 銘柄・H1・Bid/Ask）。
- 終わった月は月の 1 時間足ファイル、まだ月ファイルが無い月（当月など）は日ごとの 1 分足を 1 時間足にまとめる
- 取得済みはキャッシュ（_raw）から読むので、毎週の実行は新しい日の分だけ取りにいく
- 出力: 作業層/大容量/market_data_forward/H1/<sym>.parquet（列は検証用 H1 と同じ）
使い方: python3 fetch_forward.py [--from 2026-05] [--symbols EURUSD,...]"""
import argparse, datetime as dt, json, lzma, os, struct, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C
import fetch_dukascopy as FD

INSTR = list(FD.INSTRUMENTS) + [("AUDJPY", "AUDJPY", (40, 200)), ("CADJPY", "CADJPY", (50, 200)),
                                ("CHFJPY", "CHFJPY", (60, 300)), ("NZDJPY", "NZDJPY", (40, 180))]
RAW = os.path.join(C.FWD_DATA, "_raw"); H1 = os.path.join(C.FWD_DATA, "H1")
RECENT_DAYS = 3          # 直近 3 日の空ファイルはキャッシュしない（配信前の可能性）


def get_cached(path, url, cache_empty=True):
    if os.path.exists(path):
        return open(path, "rb").read()
    data = FD.fetch(url)
    if data is None:
        return None
    if data or cache_empty:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "wb").write(data)
    return data


def decode_day(raw, day):
    if not raw:
        return []
    try:
        buf = lzma.decompress(raw, format=lzma.FORMAT_ALONE)
    except lzma.LZMAError:
        return []
    base = dt.datetime(day.year, day.month, day.day, tzinfo=dt.timezone.utc); out = []
    for i in range(0, len(buf) - len(buf) % 24, 24):
        off, o, c, lo, hi, v = struct.unpack(">IIIIIf", buf[i:i + 24])
        out.append((base + dt.timedelta(seconds=off), o, hi, lo, c, v))
    return out


def to_hour(rows):
    """1 分足 → 1 時間足（整数ポイントのまま）
    2026-11-03: 出来高 0 の 1 分足（前の値段のまま）を飛ばす。月ファイルと同じ足になり、月が替わっても記録が書き換わらない（10 月の 19 銘柄 × Bid/Ask で差 0 本・監査C 2-3）"""
    H = {}
    for t, o, h, l, c, v in rows:
        if v <= 0:
            continue
        k = t.replace(minute=0, second=0, microsecond=0)
        if k not in H:
            H[k] = [k, o, h, l, c, v]
        else:
            x = H[k]; x[2] = max(x[2], h); x[3] = min(x[3], l); x[4] = c; x[5] += v
    return [tuple(x) for x in sorted(H.values(), key=lambda r: r[0])]


def month_rows(name, code, side, y, m, today):
    """終わった月は月ファイル。無ければ（または当月は）日ファイルから。失敗は None。"""
    cur = (y, m) == (today.year, today.month)
    if not cur:
        p = os.path.join(RAW, name, f"{side}_{y}_{m:02d}.bi5")
        raw = get_cached(p, FD.url_for(code, side, y, m), cache_empty=False)
        if raw:
            r = FD.decode(raw, y, m)
            if r:
                return r
    rows = []; d = dt.date(y, m, 1)
    while d.month == m and d < today:
        p = os.path.join(RAW, name, "day", f"{side}_{d:%Y%m%d}.bi5")
        url = f"https://datafeed.dukascopy.com/datafeed/{code}/{y}/{m-1:02d}/{d.day:02d}/{side}_candles_min_1.bi5"
        raw = get_cached(p, url, cache_empty=(today - d).days > RECENT_DAYS)
        if raw is None:
            return None
        rows.extend(to_hour(decode_day(raw, d)))
        d += dt.timedelta(days=1)
    return rows


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--from", dest="f", default="2026-05"); ap.add_argument("--symbols", default="")
    a = ap.parse_args()
    y0, m0 = map(int, a.f.split("-")); today = dt.datetime.now(dt.timezone.utc).date()
    months = [(y, m) for y in range(y0, today.year + 1) for m in range(1, 13) if (y0, m0) <= (y, m) <= (today.year, today.month)]
    todo = [i for i in INSTR if not a.symbols or i[0] in a.symbols.split(",")]
    os.makedirs(H1, exist_ok=True); mp = os.path.join(C.FWD_DATA, "manifest.json")
    man = json.load(open(mp)) if os.path.exists(mp) else {}; bad = []
    for name, code, rng in todo:
        t0 = time.time(); rows = {s: [] for s in FD.SIDES}; ok = True
        for side in FD.SIDES:
            for y, m in months:
                r = month_rows(name, code, side, y, m, today)
                if r is None:
                    ok = False; break
                rows[side].extend(r)
            if not ok:
                break
        if not ok:
            print(f"[{name}] 取得失敗（次回の実行で続きから）", flush=True); bad.append(name); continue
        df, factor = FD.build(name, rng, rows)
        df.to_parquet(os.path.join(H1, f"{name}.parquet"), index=False)
        man[name] = dict(code=code, factor=factor, rows=int(len(df)), to=str(df["time"].iloc[-1]), fetched_at=dt.datetime.now().isoformat(timespec="seconds"))
        C.write_json(mp, man)
        print(f"[{name}] {len(df):,} 本 〜{df['time'].iloc[-1]}  {time.time()-t0:.0f}s", flush=True)
    if bad:
        print("未完了:", ",".join(bad)); sys.exit(2)


if __name__ == "__main__":
    main()
