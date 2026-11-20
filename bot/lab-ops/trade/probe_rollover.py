# -*- coding: utf-8 -*-
"""probe_rollover.py — XM の日替わり（サーバーの 00:00＝冬 22 UTC・夏 21 UTC）の前後の幅を、MT5 の過去のティックから 1 回だけ読む（2026-11-16・Q736 の残り）。
読むだけ: 注文しない・symbol_select で気配の一覧を変えない（一覧に無い銘柄は飛ばす）・bot の記録と設定に書かない。
つなぎ方は採取器（Spread_XM）と同じ initialize(path) → shutdown() で、bot の端末に別のプロセスとしてつなぐだけ（bot は止まらない）。
出すもの: lab-ops/trade/winnote/S21/rollover_<label>_<実行日>.csv（send_status が次の :34 に Mac へ送る）と同じ名前の .json（メタ）。
  行: 平日のサーバーの日付 × 銘柄 × 区切り（サーバーの 00:00 からの秒。−80 分〜−5 分と +10 分〜+70 分は 60 秒、−5 分〜+10 分は 10 秒）ごとの
  ティックの本数・幅（ask−bid）の中央・最小・最大と、区切りの終わりの時点の最後の気配の幅（last_spr）とその古さ（last_age_s）。
  bot が :00:20 に読むのは「その時点の最後の気配」なので、ティックの無い区切りも last_spr で埋まる（点検の指摘 1）。
  dst_differ＝1 は米国と EU の夏時間が食い違う日（10 月末・3 月中ごろの週）。その日は NY 17:00 がサーバーの 23:00 になる（指摘 2）。
  名前を spreads_ / ticks_ で始めない（Mac の集計の glob に入れない）。
時刻: MT5 はサーバーの時刻を UTC のつもりで返す・受け取る（probe_m1_close.py と同じ作法）。日替わりはサーバーの 00:00 なので、夏時間に関係なく同じ窓で読める。
  サーバーと UTC のずれは、最後のティックの時刻と今の UTC の差から別に出して .json に書く（読み方の確かめ用）。
使い方（winnote・bot と同じ python・1〜3 分・毎時 :10〜:45 の間だけ）: python probe_rollover.py --days 28   （--print で書かずに件数だけ）"""
import argparse, csv, datetime as dt, json, os, re, statistics as st, sys
XM = r"C:\Program Files\XMTrading MT5\terminal64.exe"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # lab-ops（trade/ の 1 つ上）に置いて動かす前提
SYMS = ["EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "USDJPY", "USDCHF", "USDCAD", "EURJPY", "GBPJPY", "EURGBP", "AUDJPY", "CADJPY", "CHFJPY", "NZDJPY", "XAUUSD", "US500", "USTECH", "GER40", "JPN225"]
ALIAS = {"XAUUSD": ["GOLD", "XAUUSD"], "US500": ["US500Cash", "US500", "SPX500"], "USTECH": ["US100Cash", "USTECH", "NAS100", "US100"], "GER40": ["GER40Cash", "GER40", "DE40"], "JPN225": ["JP225Cash", "JPN225", "JP225"]}
COLS = ["date_srv", "label", "sym", "broker_sym", "dst_differ", "bin_s", "width_s", "n", "spr_med", "spr_min", "spr_max", "mid", "last_spr", "last_age_s"]
PRE_MIN, POST_MIN = 80, 70   # 窓（サーバーの 00:00 の前後の分）
LEAD_MIN = 30                # 窓の始まりの最後の気配を知るために、さらに前から取り寄せる


def bins():
    """(始まりの秒, 幅の秒) の並び。サーバーの 00:00 が 0。"""
    return [(s, 60) for s in range(-PRE_MIN * 60, -300, 60)] + [(s, 10) for s in range(-300, 600, 10)] + [(s, 60) for s in range(600, POST_MIN * 60, 60)]


def us_dst(d):
    """米国の夏時間か（3 月の第 2 日曜〜11 月の第 1 日曜）。"""
    a = dt.date(d.year, 3, 8); a += dt.timedelta(days=(6 - a.weekday()) % 7); b = dt.date(d.year, 11, 1); b += dt.timedelta(days=(6 - b.weekday()) % 7)
    return a <= d < b


def eu_dst(d):
    """EU の夏時間か（3 月の最終日曜〜10 月の最終日曜）。XM のサーバーはこちらに従う。"""
    a = dt.date(d.year, 3, 31); a -= dt.timedelta(days=(a.weekday() + 1) % 7); b = dt.date(d.year, 10, 31); b -= dt.timedelta(days=(b.weekday() + 1) % 7)
    return a <= d < b


def resolve(names):
    out = {}
    for s in SYMS:
        for c in ALIAS.get(s, [s]):
            hit = c if c in names else min((x for x in names if re.sub(r"[^A-Za-z0-9]", "", x).upper().startswith(c.upper())), key=lambda x: (x[len(c):len(c) + 1].isalnum(), len(x)), default=None)
            if hit: out[s] = hit; break
    return out


def summarize(day, label, s, b, tk):
    """tk: (time_msc, bid, ask) の並び（サーバーの時刻の epoch ms・時刻の順）。day: サーバーの日付（その日の 00:00 が日替わり）。"""
    z = int(dt.datetime(day.year, day.month, day.day, tzinfo=dt.timezone.utc).timestamp() * 1000); out = []
    B = bins(); lo, hi = B[0][0] * 1000, (B[-1][0] + B[-1][1]) * 1000; per = {}
    good = sorted((tm - z, ask - bid) for tm, bid, ask in tk if bid > 0 and ask >= bid); j = 0; last = None   # 区切りの終わりの最後の気配
    ends = {}
    for st0, w in B:
        e = (st0 + w) * 1000
        while j < len(good) and good[j][0] < e: last = good[j]; j += 1
        ends[st0] = (f"{last[1]:.8g}", (e - last[0]) // 1000) if last else ("", "")
    dd = int(us_dst(day) != eu_dst(day))
    for tm, bid, ask in tk:
        r = tm - z
        if not (lo <= r < hi) or bid <= 0 or ask < bid: continue
        sec = r // 1000; w = 10 if -300 <= sec < 600 else 60   # 区切りの境目はどれも幅の倍数
        per.setdefault(sec // w * w, []).append((ask - bid, (ask + bid) / 2))
    for st0, w in B:
        v = per.get(st0)
        if not v: out.append([str(day), label, s, b, dd, st0, w, 0, "", "", "", "", *ends[st0]]); continue
        sp = [x for x, _ in v]
        out.append([str(day), label, s, b, dd, st0, w, len(v), f"{st.median(sp):.8g}", f"{min(sp):.8g}", f"{max(sp):.8g}", f"{st.median(m for _, m in v):.8g}", *ends[st0]])
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--path", default=XM); ap.add_argument("--label", default="XM"); ap.add_argument("--days", type=int, default=28)
    ap.add_argument("--print", action="store_true", dest="show"); ap.add_argument("--anytime", action="store_true", help="時刻の歯止めを外す（試験用）")
    ap.add_argument("--syms", default="", help="読む銘柄を絞る（例 EURUSD,USDJPY・初回の試しに）"); a = ap.parse_args()
    if not os.path.exists(a.path): sys.exit(f"端末が見つからない: {a.path}")
    nw = dt.datetime.now(dt.timezone.utc)
    if not a.anytime and not (10 <= nw.minute < 45 and nw.weekday() <= 3):
        sys.exit(f"UTC の月〜木の毎時 :10〜:45 の間だけ始める（今 {nw:%a} :{nw.minute:02d}）。bot の毎時の判断（:00〜:01）・採取（:00〜:05）・金曜の週末前決済に、過去のティックの取り寄せを重ねないため")
    import MetaTrader5 as mt5
    if not mt5.initialize(path=a.path): sys.exit(f"MT5 に接続できない: {mt5.last_error()}")
    rows, meta = [], dict(label=a.label, 実行のUTC=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), days=a.days, 銘柄={}, 日付=[])
    try:
        ai = mt5.account_info(); syms = mt5.symbols_get()
        if ai is None or not syms: sys.exit(f"口座か銘柄を読めない: {mt5.last_error()}")
        meta["server"] = ai.server; vis = {x.name for x in syms if getattr(x, "visible", True)}; m = resolve(vis)
        if a.syms: m = {s: b for s, b in m.items() if s in a.syms.split(",")}
        last = max((t.time_msc for t in (mt5.symbol_info_tick(b) for b in m.values()) if t is not None), default=None)
        if last: meta["サーバーとUTCのずれ_時間"] = round((last / 1000 - dt.datetime.now(dt.timezone.utc).timestamp()) / 3600, 2)   # 最後のティックが新しいとき（平日）だけ意味がある
        today = dt.datetime.now(dt.timezone.utc).date()
        days = [today - dt.timedelta(days=k) for k in range(1, a.days + 1)]
        days = [d for d in days if d.weekday() in (1, 2, 3, 4)]   # サーバーの火〜金の 00:00（＝月〜木の日替わり。月の 00:00 は週明けの開場なので除く）
        meta["日付"] = [str(d) for d in sorted(days)]; meta["夏時間が食い違う日"] = [str(d) for d in sorted(days) if us_dst(d) != eu_dst(d)]
        for s, b in m.items():
            got = 0
            if not a.anytime and dt.datetime.now(dt.timezone.utc).minute >= 50:   # 長引いたら、次の :00 の前に読んだ分だけ書いて終わる
                meta["途中で止めた"] = f"{s} の前（:50 を過ぎた）"; break
            for d in sorted(days):
                t00 = dt.datetime(d.year, d.month, d.day, tzinfo=dt.timezone.utc); t0 = t00 - dt.timedelta(minutes=PRE_MIN + LEAD_MIN); t1 = t00 + dt.timedelta(minutes=POST_MIN)
                tk = mt5.copy_ticks_range(b, t0, t1, mt5.COPY_TICKS_ALL)
                if tk is None or len(tk) == 0: continue
                got += 1; rows += summarize(d, a.label, s, b, [(int(x["time_msc"]), float(x["bid"]), float(x["ask"])) for x in tk])
            meta["銘柄"][s] = dict(broker_sym=b, 日数=got)
    finally:
        mt5.shutdown()
    print("日数:", {s: v["日数"] for s, v in meta["銘柄"].items()}, "ずれ:", meta.get("サーバーとUTCのずれ_時間"), flush=True)
    if a.show: print("行:", len(rows), "（--print では書かない）"); return
    d = os.path.join(ROOT, "trade", "winnote", "S21"); os.makedirs(d, exist_ok=True); stem = f"rollover_{a.label}_{dt.datetime.now(dt.timezone.utc):%Y%m%d}"
    with open(os.path.join(d, stem + ".csv"), "w", newline="", encoding="utf-8") as h:
        w = csv.writer(h); w.writerow(COLS); w.writerows(rows)
    with open(os.path.join(d, stem + ".json"), "w", encoding="utf-8") as h: json.dump(meta, h, ensure_ascii=False, indent=1)
    print("書いた:", stem, len(rows), "行", flush=True)


if __name__ == "__main__":
    main()
