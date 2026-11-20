# -*- coding: utf-8 -*-
"""S44 を凍結する（1 回だけ）。Q613 の設定（q 0.97・step 3・1 シード）で 2026-10-01 までの全期間を学習し、6 行動のモデルとハッシュを 凍結/ に置く。
確認: 検証用データと記録用データの同じ足で予測が一致するか（相関）。"""
import hashlib, json, os, sys
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); KS = os.path.abspath(os.path.join(HERE, "..", "..", "..")); R_DIR = os.path.join(KS, "verification-lab", "financial-engineering", "s44-fx-h1-refine-q613"); sys.path.insert(0, R_DIR)
import kensho_s41_refine_q613_q614 as R
B, K, W, Q, C, P, J, E = R.B, R.K, R.W, R.Q, R.C, R.P, R.J, R.E
FWD = os.path.join(os.path.dirname(KS), "作業層", "大容量", "market_data_forward", "H1"); FZ = os.path.join(HERE, "凍結")
sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()
B.SEAL_END = "2026-10-01"   # 封印を開ける: フォワード用の凍結モデルの学習（判定には使わない）
T = C.rate_table(); d0 = B.build(T, P.SYMS); end = W.TS(2026); m, ntr = Q.train_window(d0, end, None, step=3); h = {}
for a, x in enumerate(m):
    f = os.path.join(FZ, f"model_a{a}.txt"); x.booster_.save_model(f); h[os.path.basename(f)] = sha(f)
for f in ("kensho_s41_refine_q613_q614.py",): h[f] = sha(os.path.join(R_DIR, f))
h["kensho_s41_h1_xmcost_q610.py"] = sha(os.path.join(R_DIR, "..", "s41-fx-h1-xmcost-q610", "kensho_s41_h1_xmcost_q610.py"))
B.SEAL_END = "2100-01-01"; P.H1 = FWD; d1 = B.build(T, P.SYMS); s, e = pd.Timestamp("2026-08-01", tz="UTC"), pd.Timestamp("2026-09-15", tz="UTC"); P0, P1 = K.predict(m, d0, s, e), K.predict(m, d1, s, e); cs = {}
for k in P.SYMS:
    a = pd.Series(P0[k][1].max(1), index=d0[k]["time"].iloc[P0[k][0]].to_numpy()); b = pd.Series(P1[k][1].max(1), index=d1[k]["time"].iloc[P1[k][0]].to_numpy()); j = pd.concat([a, b], axis=1, join="inner"); cs[k] = dict(n=len(j), corr=round(float(j.corr().iloc[0, 1]), 4))
h["学習行"] = int(ntr); h["学習の終わり"] = str(end); h["同等性（検証用と記録用の予測の相関）"] = cs
json.dump(h, open(os.path.join(FZ, "hashes.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1); print(ntr, cs)
