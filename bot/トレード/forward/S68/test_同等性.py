# -*- coding: utf-8 -*-
"""forward_s68.py の decide・settle が検証（Q740 の封印期間の週）と同じ建て方・損益を出すか。データは検証の取得（作業層/大容量/crypto_xs の *_seal）。
使い方: python3 test_同等性.py  → 週ごとの一致の数と、損益の差の最大を出す。終了コード 0 = 全週の建て方が一致し |差| < 1e-9"""
import os, sys, warnings; warnings.simplefilter("ignore")
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import forward_s68 as F
WS = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
DATA = os.path.join(WS, "作業層", "大容量", "crypto_xs")
REF = os.path.join(WS, "検証", "verification-lab", "financial-engineering", "s68-crypto-xs-momentum-q739", "results", "weeks_q740.csv")
TRADFI = {"XAUUSDT", "XAGUSDT", "EURUSDT", "TSLAUSDT", "AAPLUSDT", "NVDAUSDT", "COINUSDT", "MSTRUSDT", "CRCLUSDT", "HOODUSDT", "INTCUSDT", "AMZNUSDT", "GOOGLUSDT", "METAUSDT", "QQQUSDT", "SPYUSDT"}
TRADFI |= set(open(os.path.join(os.path.dirname(REF), "..", "tradfi_symbols_20261116.txt")).read().split())   # 検証と同じ除外（2026-11-16 の直し）
C, O, V, Fd = {}, {}, {}, {}
for sub, fsub in (("klines", "funding"), ("klines_seal", "funding_seal")):
    for fn in os.listdir(os.path.join(DATA, sub)):
        s = fn[:-4]
        if s in TRADFI or not s.endswith("USDT"): continue
        d = pd.read_csv(os.path.join(DATA, sub, fn), parse_dates=["date"]); d.index = pd.to_datetime(d["date"]).dt.tz_localize("UTC")
        for D_, col in ((C, "close"), (O, "open"), (V, "volume")): D_[s] = pd.concat([D_.get(s, pd.Series(dtype=float)), d[col]])
        fp = os.path.join(DATA, fsub, fn)
        if os.path.exists(fp):
            f = pd.read_csv(fp, parse_dates=["time"]); t = f["time"].dt.tz_localize("UTC").dt.normalize()
            Fd[s] = pd.concat([Fd.get(s, pd.Series(dtype=float)), f["rate"].groupby(pd.DatetimeIndex(t)).sum()])
dedup = lambda x: x[~x.index.duplicated(keep="last")].sort_index()
C = pd.DataFrame({k: dedup(v) for k, v in C.items()}); O = pd.DataFrame({k: dedup(v) for k, v in O.items()})
V = pd.DataFrame({k: dedup(v) for k, v in V.items()}); Fd = pd.DataFrame({k: v.groupby(level=0).sum() for k, v in Fd.items()})
C, O, V = (x[x.index < pd.Timestamp("2026-07-01", tz="UTC")] for x in (C, O, V))
ref = pd.read_csv(REF); ref = ref[ref["signal"] == "main"] if "signal" in ref else ref
cand = sorted(C.columns); prev = {}; same = 0; diffs = []; bad = []
for _, r in ref.iterrows():
    D = pd.Timestamp(r["week"], tz="UTC")
    if D + pd.Timedelta(days=6) >= pd.Timestamp("2026-07-01", tz="UTC"): break        # 最後の 2 日だけの週は比べない
    x = F.decide(C, V, D, cand)
    L = sorted(t.split(":")[0] for t in r["long"].split()); S = sorted(t.split(":")[0] for t in r["short"].split())
    ok = x is not None and sorted(x["long"]) == L and sorted(x["short"]) == S
    same += ok
    if not ok: bad.append((r["week"], sorted(set(L) ^ set(x["long"] if x else [])), sorted(set(S) ^ set(x["short"] if x else []))))
    rows, w, turn = F.settle(C, O, Fd, D, L, S, prev)        # 損益は検証の建て方で比べる（建て方の差と式の差を分けるため）
    g, f, c = sum(z[1] for z in rows), sum(z[2] for z in rows), rows[0][3]
    dd_=max(abs(g - r["gross"]), abs(f - r["funding"]), abs(c - r["cost"]), abs(g + f - c - r["net"]))
    if dd_>1e-9: bad.append((r["week"],"損益",round(g-r["gross"],5),round(f-r["funding"],5),round(c-r["cost"],5)))
    diffs.append(max(abs(g - r["gross"]), abs(f - r["funding"]), abs(c - r["cost"]), abs(g + f - c - r["net"])))
    prev = w
n = len(diffs)
print(f"建て方の一致 {same}/{n} 週・損益の差の最大 {max(diffs):.2e}")
for b in bad[:10]: print("  違う週:", b)
# 既知の差（2026-11-16）: 検証は「全期間で日足 60 本以上」（先の情報）で上場直後の銘柄を外していた。記録は外さない（直近 30 日の足だけ）。2026-06-08 の BILLUSDT がそれ
KNOWN = {"2026-06-08"}
odd = {b[0] for b in bad if b[1] != "損益"} - KNOWN
sys.exit(0 if not odd and max(diffs) < 1e-9 else 1)
