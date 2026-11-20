# -*- coding: utf-8 -*-
"""judge_fx12m.py — S44・S53 の 12 か月の前向き判定（Q616・Q622・Q628）の計算を、取引が 0 件のうちに固定する（2026-11-03・Fable）。
読み方の追記: verification-lab/financial-engineering/s44-fx-h1-refine-q613/事前登録_判定の読み方_20261103.md（Q616・Q622・Q628 の曖昧な点だけを決める。基準は変えない）
- 標本: 入った時刻が [2026-11-01 21:00, 2027-11-01 21:00) UTC の取引（記録の trades.csv）。決済は終わりより後でよい
- 実行の条件: 記録のデータの最後 ≥ 2027-11-10 00:00 UTC（最後の取引のラベルが決まる）・FX 10 本の 2027-10 の月ファイルが _raw にある・依存のハッシュが控えと同じ。
  満たさなければ終了コード 2（--preview なら数字は出すが保存しない）
- 正の数字（Q616・Q628）: XM の実測の倍率 m で直した R ＝ R − cost × (m − 1)。m は銘柄 × 入る時刻（UTC の時）ごとに
  「実測の Ask−Bid の和 ÷ 記録の仮定の幅の和」（同じ足どうし・期間内の live の行）。分母は記録のコストの土台（max(Dukascopy の幅, XMREL × 価格) を 1 本ずらす）で、
  spread_report.py の m（分母が Dukascopy の生の幅）ではない。その時刻の比較が 20 未満なら銘柄の m、銘柄の比較が 40 未満なら m ＝ 1 で「実測不足」
- Q622（S44 のみ）: Fintokei の公表コストの R_fin（記録の列のまま）。Fintokei の実測は手数料が CSV に無いので合否に使わない（記述のみ）
- 日次: 決済日（土日は月曜）に R を足し、開始日〜最後の決済日の営業日で 0 埋め。NW t は lag 5（fe_core.metrics.nw_t）。PF は取引の R
- Holm: 片側・α 0.05・p ＝ 1 − Φ(t)。S44 は 3 本（Q616 主・Q616 副・Q622 主）、S53 は 2 本（Q628 主・副）。合格 ＝ Holm で棄却 かつ t ≥ 2 かつ PF ≥ 1.05
使い方: 作業層/大容量/venv_forward/bin/python judge_fx12m.py --bot S44|S53 [--preview] ／ --snapshot（依存のハッシュを S44/凍結/deps_hashes.json に書く。凍結より後に変わったファイルがあれば書かない）"""
import argparse, datetime, glob, hashlib, json, math, os, sys
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); KS = os.path.abspath(os.path.join(HERE, "..", "..")); WS = os.path.dirname(KS); FE = os.path.join(KS, "verification-lab", "financial-engineering")
FWD = os.path.join(WS, "作業層", "大容量", "market_data_forward"); SPR_DIR = os.path.join(KS, "lab-ops", "trade", "winnote", "S21"); DEPS = os.path.join(HERE, "S44", "凍結", "deps_hashes.json")
sys.path.insert(0, os.path.join(KS, "verification-lab", "tools"))   # 2026-11-16 Q736: fe_core を読めるように（前は --preview も本番も ModuleNotFoundError で落ちていた）
START, END, READY = (pd.Timestamp(x, tz="UTC") for x in ("2026-11-01 21:00", "2027-11-01 21:00", "2027-11-10 00:00"))
FREEZE = datetime.datetime(2026, 11, 1, 13, 48)   # S44 の凍結（JST）。依存がこれより後に変わっていたら控えを作らない
FX = ["EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "USDJPY", "USDCHF", "USDCAD", "EURJPY", "GBPJPY", "EURGBP"]; YEN = ["USDJPY", "EURJPY", "GBPJPY"]
MIN_SH, MIN_S, ALPHA, T_MIN, PF_MIN = 20, 40, 0.05, 2.0, 1.05
FAMILY = {"S44": [("Q616 主 FX 10 本", "R_xm", FX), ("Q616 副 円 3 本", "R_xm", YEN), ("Q622 主 FX 10 本 Fintokei", "R_fin", FX)],
          "S53": [("Q628 主 FX 10 本", "R_xm", FX), ("Q628 副 円 3 本", "R_xm", YEN)]}
DATA_FILES = [os.path.join(FE, "fx-traprepeat-q591", "results", f) for f in ("cost_table.json", "swap_real_q591.json")] + sorted(glob.glob(os.path.join(KS, "_データ", "raw", "rates", "policy_*.csv"))) + [os.path.join(HERE, "S44", "凍結", "fintokei_cost.csv")]
sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest(); pf = lambda r: float(r[r > 0].sum() / -r[r < 0].sum()) if (r < 0).any() else float("nan")


def dep_files():
    """記録が実行時に読むモジュール（verification-lab の下）とデータ。forward_s44.py と同じ import をして sys.modules から拾う。"""
    sys.path.insert(0, os.path.join(FE, "s44-fx-h1-refine-q613")); import kensho_s41_refine_q613_q614  # noqa: F401
    from fe_core import metrics  # noqa: F401
    vl = os.path.join(KS, "verification-lab"); mods = sorted({os.path.abspath(m.__file__) for m in list(sys.modules.values()) if getattr(m, "__file__", None) and os.path.abspath(m.__file__).startswith(vl)})
    return mods + [p for p in DATA_FILES if os.path.exists(p)]


def snapshot():
    fs = dep_files(); late = [f for f in fs if datetime.datetime.fromtimestamp(os.path.getmtime(f)) > FREEZE and not f.endswith("fintokei_cost.csv")]   # fintokei_cost.csv は凍結の 1 時間後に作った（監査D の 3）
    if late: print("凍結より後に変わった依存があるので控えを書かない:", *[os.path.relpath(f, KS) for f in late], sep="\n  "); return 2
    json.dump({os.path.relpath(f, KS): sha(f) for f in fs}, open(DEPS, "w", encoding="utf-8"), ensure_ascii=False, indent=1); print(f"控え {len(fs)} 本 → {os.path.relpath(DEPS, KS)}"); return 0


def check_deps():
    if not os.path.exists(DEPS): return ["依存の控え（deps_hashes.json）が無い"]
    h = json.load(open(DEPS, encoding="utf-8")); return [f"依存が変わった: {k}" for k, v in h.items() if not os.path.exists(os.path.join(KS, k)) or sha(os.path.join(KS, k)) != v]


def assumed_spread(s):
    """記録のコストの土台と同じ幅（kensho_s41_h1_xmcost_q610.py:23）: max(Dukascopy の終値の幅, XMREL × 終値) を 1 本ずらす。"""
    rel = json.load(open(DATA_FILES[0], encoding="utf-8"))["rel"][s]; d = pd.read_parquet(os.path.join(FWD, "H1", f"{s}.parquet"), columns=["time", "close", "ask_close"]); d["time"] = pd.to_datetime(d["time"], utc=True)
    return pd.Series(np.maximum((d["ask_close"] - d["close"]).clip(lower=0), rel * d["close"]).shift(1).bfill().to_numpy(), index=d["time"])


def multipliers(label="XM"):
    """銘柄 × 時（UTC）の m と、その出どころ。実測が無ければ空。"""
    fs = sorted(glob.glob(os.path.join(SPR_DIR, f"spreads_{label}_*.csv")))
    if not fs: return {}, {}
    d = pd.concat(pd.read_csv(f) for f in fs); d = d[(d["live"] == 1) & (d["label"] == label) & d["sym"].isin(FX)].copy();   # 2026-11-16: spreads_XM_*.csv は KIWAMI 極（spreads_XM_KIWAMI_*）も拾うので label で絞る
    if d.duplicated(["hour_utc", "sym"]).any(): raise SystemExit(f"spreads_{label} に同じ時刻・銘柄の行が 2 つ以上ある（別の口座を同じ label で記録した恐れ）。判定しない")   # 2026-11-16 点検の指摘 3
    d["t"] = pd.to_datetime(d["hour_utc"], utc=True); d = d[(d["t"] >= START) & (d["t"] < END)]; m, src = {}, {}
    for s, g in d.groupby("sym"):
        a = assumed_spread(s); g = g.assign(u=a.reindex(g["t"]).to_numpy()).dropna(subset=["u"]); g = g[(g["u"] > 0) & (g["spr_med"] > 0)]
        if len(g) < MIN_S: continue
        ms = float(g["spr_med"].sum() / g["u"].sum()); src[s] = dict(比較=len(g), m=round(ms, 3))
        for h, gh in g.groupby(g["t"].dt.hour): m[(s, h)] = float(gh["spr_med"].sum() / gh["u"].sum()) if len(gh) >= MIN_SH else ms
        for h in range(24): m.setdefault((s, h), ms)
    return m, src


def stats(t, col):
    if not len(t): return dict(n=0, 平均R=None, 合計R=0.0, PF=None, NW_t=None)
    r = t[col].to_numpy(float)
    g = t.groupby("xd")[col].sum().reindex(pd.bdate_range(START.tz_localize(None).normalize(), t["xd"].max()), fill_value=0.0)
    from fe_core.metrics import nw_t
    return dict(n=len(r), 平均R=float(r.mean()), 合計R=float(r.sum()), PF=pf(pd.Series(r)), NW_t=float(nw_t(g.to_numpy())) if len(g) > 10 else None, 最大下落R=float((g.cumsum() - g.cumsum().cummax().clip(lower=0)).min()))


def holm(rows):
    """片側 p ＝ 1 − Φ(t)。小さい順に α/(m−k) と比べ、初めて超えたところで止める。"""
    p = [0.5 * math.erfc(r["NW_t"] / math.sqrt(2)) if r["NW_t"] is not None else 1.0 for r in rows]; m = len(rows); ok = [False] * m
    for k, i in enumerate(sorted(range(m), key=lambda i: p[i])):
        if p[i] > ALPHA / (m - k): break
        ok[i] = True
    for r, pi, o in zip(rows, p, ok): r.update(p片側=pi, Holm=o, 合格=bool(o and r["NW_t"] >= T_MIN and r["PF"] is not None and r["PF"] >= PF_MIN))
    return rows


def judge(bot, preview, trades=None):
    tr = pd.read_csv(trades or os.path.join(HERE, bot, "記録", "trades.csv")); st = json.load(open(os.path.join(HERE, bot, "記録", "状態.json"), encoding="utf-8")); why = []
    last = pd.Timestamp(st["データの最後"]); last = last.tz_localize("UTC") if last.tzinfo is None else last
    if last < READY: why.append(f"データの最後 {last} が {READY} より前")
    miss = [s for s in FX for sd in ("BID", "ASK") if not os.path.exists(os.path.join(FWD, "_raw", s, f"{sd}_2027_10.bi5"))]
    if miss: why.append(f"2027-10 の月ファイルが無い（{len(miss)} 本）")
    why += check_deps()
    if len(tr):
        tr["entry"] = pd.to_datetime(tr["entry"], utc=True); tr = tr[(tr["entry"] >= START) & (tr["entry"] < END)].copy()
    if len(tr):
        ex = pd.to_datetime(tr["exit"], utc=True); dw = ex.dt.dayofweek; tr["xd"] = (ex + pd.to_timedelta(np.where(dw >= 5, 7 - dw, 0), unit="D")).dt.tz_localize(None).dt.normalize()
    m, src = multipliers(); short = [s for s in FX if s not in src]
    tr["m"] = [m.get((s, e.hour), 1.0) for s, e in zip(tr["sym"], tr["entry"])] if len(tr) else []
    if len(tr): tr["R_xm"] = tr["R"] - tr["cost"] * (tr["m"] - 1); tr["R_125"] = tr["R"] - 0.25 * tr["cost"]
    rows = holm([dict(判定=name, 列=col, **stats(tr[tr["sym"].isin(syms)] if len(tr) else tr, col)) for name, col, syms in FAMILY[bot]])
    out = dict(bot=bot, 期間=[str(START), str(END)], データの最後=str(last), 実行=datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), 予行=bool(why), 満たさない条件=why, 実測不足の銘柄=short, 倍率=src, 判定=rows,
               記述=dict(仮定の幅のまま=stats(tr, "R") if len(tr) else None, スプレッド125倍=stats(tr, "R_125") if len(tr) else None, Fintokei_円3本=stats(tr[tr["sym"].isin(YEN)], "R_fin") if bot == "S44" and len(tr) else None))
    for r in rows: print(f"{r['判定']}: n {r['n']}・平均 {r['平均R']}・PF {r['PF']}・NW t {r['NW_t']}・p {r['p片側']:.4f}・Holm {r['Holm']}・合格 {r['合格']}")
    if short: print("実測不足（m ＝ 1）:", ", ".join(short))
    if why:
        print("条件を満たさない:", *why, sep="\n  ")
        if not preview: return 2
        print("予行: 保存しない"); return 0
    json.dump(out, open(os.path.join(HERE, bot, "記録", "判定_12か月.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float); return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--bot", choices=list(FAMILY)); ap.add_argument("--preview", action="store_true"); ap.add_argument("--snapshot", action="store_true"); ap.add_argument("--trades", help="試験用: trades.csv の代わり"); a = ap.parse_args()
    sys.exit(snapshot() if a.snapshot else judge(a.bot, a.preview, a.trades))
