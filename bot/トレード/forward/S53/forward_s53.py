# -*- coding: utf-8 -*-
"""S53（S44 の 9 シード平均版・FX 10 本・H1・q 0.97）の仮想フォワード記録（Q628・2026-11-01）。注文は出さない。
- 凍結: 凍結/model_s*_a*.txt（シード 0〜8・2026-10-01 までで学習）。ハッシュは 凍結/hashes.json。年度の学習し直しはしない（12 か月の判定まで固定）
- 開始: 2026-11-01 21:00 UTC。これより前の取引は入れない
- 合否（事前登録_q628.md）: 12 か月で 主判定 FX 10 本・副判定 円 3 本。どちらも NW t ≥ 2 かつ PF ≥ 1.05。Holm（m=2）。Fintokei の公表コストは記述
- 停止: 累積 R の最大下落が −92R（Q627 の 9 シード平均の最悪 −61.6R × 1.5）を超えたら終了コード 3
- ラベルの計算に 120 本先の足が要るので、記録は決定から 5 営業日ほど遅れる
使い方: 作業層/大容量/venv_forward/bin/python forward_s53.py"""
import datetime, hashlib, json, os, sys
import numpy as np, pandas as pd, lightgbm as lgb
HERE = os.path.dirname(os.path.abspath(__file__)); KS = os.path.abspath(os.path.join(HERE, "..", "..", "..")); R_DIR = os.path.join(KS, "verification-lab", "financial-engineering", "s44-fx-h1-refine-q613"); sys.path.insert(0, R_DIR)
import kensho_s41_refine_q613_q614 as R
B, K, W, Q, C, P, J, E = R.B, R.K, R.W, R.Q, R.C, R.P, R.J, R.E
from fe_core.metrics import nw_t
FWD = os.path.join(os.path.dirname(KS), "作業層", "大容量", "market_data_forward", "H1"); FZ, REC = os.path.join(HERE, "凍結"), os.path.join(HERE, "記録")
START = pd.Timestamp(os.environ.get("S53_TEST_START", "2026-11-01 21:00"), tz="UTC"); TEST = "S53_TEST_START" in os.environ; Q97, STOP, SEEDS = 0.97, -92.0, range(9)
sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest(); pf = lambda r: float(r[r > 0].sum() / -r[r < 0].sum()) if (r < 0).any() else float("nan")


def main():
    h = json.load(open(os.path.join(FZ, "hashes.json"), encoding="utf-8"))
    for f in [x for x in h if x.startswith("model_s")]:
        if sha(os.path.join(FZ, f)) != h[f]: print("凍結モデルのハッシュが違う:", f); sys.exit(2)
    B.SEAL_END = "2100-01-01"   # 封印を開ける: フォワード専用（S53 の記録・事前登録_q628.md）。判定は開始より後の標本だけ
    P.H1 = FWD; T = C.rate_table(); data = B.build(T, P.SYMS); end = pd.Timestamp("2100-01-01", tz="UTC")
    Ps = [K.predict([lgb.Booster(model_file=os.path.join(FZ, f"model_s{sd}_a{a}.txt")) for a in range(len(K.ACTIONS))], data, START - Q.WARM, end) for sd in SEEDS]; Pr = {k: (Ps[0][k][0], np.mean([p[k][1] for p in Ps], axis=0)) for k in Ps[0]}; PP = J.apply_thr(data, Pr, J.thr_series(data, Pr, q=Q97), START); tr = K.run_policy(data, E.block(PP, data, 1), 0.0) if sum(len(v[0]) for v in PP.values()) else pd.DataFrame()
    last = max(o["time"].iloc[-1] for o in data.values()); st = dict(開始=str(START), データの最後=str(last), 件数=0, 平均R=None, 合計R=0.0, PF=None, NW_t=None, 最大下落R=0.0, 円3本=None, 主要7本=None, スプレッド125倍の平均R=None, 停止=[], 更新=datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
    if len(tr):
        tr["cost"] = 0.0; tr["fin_cost"] = 0.0; F = pd.read_csv(os.path.join(HERE, "..", "S44", "凍結", "fintokei_cost.csv"), index_col=0)["price"]   # Q622 と同じ表（記述）
        for s, g in tr.groupby("sym"):
            i_ = g["i"].to_numpy(); tr.loc[g.index, "cost"] = data[s]["cR"][i_ + 1]; tr.loc[g.index, "fin_cost"] = F[s] / data[s]["D"][i_]
        tr["R_fin"] = tr["R"] + tr["cost"] - tr["fin_cost"]
        ex = pd.to_datetime(tr["exit"], utc=True); dw = ex.dt.dayofweek; tr["xd"] = (ex + pd.to_timedelta(np.where(dw >= 5, 7 - dw, 0), unit="D")).dt.tz_localize(None).dt.normalize(); idx = pd.bdate_range(tr["xd"].min(), tr["xd"].max()); g = tr.groupby("xd")["R"].sum().reindex(idx, fill_value=0.0); eq = g.cumsum(); dd = float((eq - eq.cummax().clip(lower=0)).min()); jp = tr["sym"].isin(B.YEN)
        st.update(件数=int(len(tr)), 平均R=float(tr["R"].mean()), 合計R=float(tr["R"].sum()), PF=pf(tr["R"]), NW_t=float(nw_t(g.to_numpy())) if len(g) > 10 else None, 最大下落R=dd, 円3本=dict(n=int(jp.sum()), R=float(tr.loc[jp, "R"].mean()) if jp.any() else None), 主要7本=dict(n=int((~jp).sum()), R=float(tr.loc[~jp, "R"].mean()) if (~jp).any() else None), スプレッド125倍の平均R=float((tr["R"] - .25 * tr["cost"]).mean()), Fintokei=dict(平均R=float(tr["R_fin"].mean()), PF=pf(tr["R_fin"]), 合計R=float(tr["R_fin"].sum()), NW_t=float(nw_t(tr.groupby("xd")["R_fin"].sum().reindex(idx, fill_value=0.0).to_numpy())) if len(g) > 10 else None, 円3本=float(tr.loc[jp, "R_fin"].mean()) if jp.any() else None))
        if dd < STOP: st["停止"].append(f"最大下落 {dd:.1f}R が停止線 {STOP}R を超えた")
    print({k: st[k] for k in ("データの最後", "件数", "平均R", "PF", "NW_t", "最大下落R", "停止")})
    if TEST: print("試験: 保存しない"); return 0
    (tr if len(tr) else pd.DataFrame(columns=["sym", "entry", "exit", "R"])).to_csv(os.path.join(REC, "trades.csv"), index=False); json.dump(st, open(os.path.join(REC, "状態.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float)
    return 3 if st["停止"] else 0


if __name__ == "__main__":
    sys.exit(main())
