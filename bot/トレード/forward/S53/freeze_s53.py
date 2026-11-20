# -*- coding: utf-8 -*-
"""S53 を凍結する（1 回だけ）。S44 と同じ設定（q 0.97・step 3）をシード 0〜8 で学習し、9×6 本のモデルとハッシュを 凍結/ に置く。
確認: 保存したモデルの平均予測が学習直後の平均予測と一致するか・シード 0 が S44 の凍結モデルと一致するか・検証用と記録用の足で予測が一致するか（相関）。"""
import hashlib, json, os, sys
import numpy as np, pandas as pd, lightgbm as lgb
HERE = os.path.dirname(os.path.abspath(__file__)); KS = os.path.abspath(os.path.join(HERE, "..", "..", "..")); R_DIR = os.path.join(KS, "verification-lab", "financial-engineering", "s44-fx-h1-refine-q613"); sys.path.insert(0, R_DIR)
import kensho_s41_refine_q613_q614 as R
B, K, W, Q, C, P, J, E = R.B, R.K, R.W, R.Q, R.C, R.P, R.J, R.E
FWD = os.path.join(os.path.dirname(KS), "作業層", "大容量", "market_data_forward", "H1"); FZ = os.path.join(HERE, "凍結"); S44 = os.path.join(HERE, "..", "S44", "凍結"); SEEDS = range(9); SEED0 = K.SEED
sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()
B.SEAL_END = "2026-10-01"   # 封印を開ける: フォワード用の凍結モデルの学習（判定には使わない）
T = C.rate_table(); d0 = B.build(T, P.SYMS); end = W.TS(2026); h = {}; ms = {}; s, e = pd.Timestamp("2026-08-01", tz="UTC"), pd.Timestamp("2026-09-15", tz="UTC")
for sd in SEEDS:
    K.SEED = SEED0 + 1000 * sd; m, ntr = Q.train_window(d0, end, None, step=3); ms[sd] = m; print(f"シード {sd}: 学習 {ntr} 行", flush=True)
    for a, x in enumerate(m):
        f = os.path.join(FZ, f"model_s{sd}_a{a}.txt"); x.booster_.save_model(f); h[os.path.basename(f)] = sha(f)
K.SEED = SEED0; mean = lambda L: {k: (L[0][k][0], np.mean([p[k][1] for p in L], axis=0)) for k in L[0]}
A = mean([K.predict(ms[sd], d0, s, e) for sd in SEEDS]); Bo = mean([K.predict([lgb.Booster(model_file=os.path.join(FZ, f"model_s{sd}_a{a}.txt")) for a in range(len(K.ACTIONS))], d0, s, e) for sd in SEEDS]); dif = max(float(np.abs(A[k][1] - Bo[k][1]).max()) for k in A)
s44 = K.predict([lgb.Booster(model_file=os.path.join(S44, f"model_a{a}.txt")) for a in range(len(K.ACTIONS))], d0, s, e); P0 = K.predict(ms[0], d0, s, e); dif44 = max(float(np.abs(P0[k][1] - s44[k][1]).max()) for k in P0)
for f in ("kensho_s41_refine_q613_q614.py",): h[f] = sha(os.path.join(R_DIR, f))
h["kensho_s41_h1_xmcost_q610.py"] = sha(os.path.join(R_DIR, "..", "s41-fx-h1-xmcost-q610", "kensho_s41_h1_xmcost_q610.py"))
B.SEAL_END = "2100-01-01"; P.H1 = FWD; d1 = B.build(T, P.SYMS); P1 = mean([K.predict([lgb.Booster(model_file=os.path.join(FZ, f"model_s{sd}_a{a}.txt")) for a in range(len(K.ACTIONS))], d1, s, e) for sd in SEEDS]); cs = {}
for k in P.SYMS:
    a = pd.Series(A[k][1].max(1), index=d0[k]["time"].iloc[A[k][0]].to_numpy()); b = pd.Series(P1[k][1].max(1), index=d1[k]["time"].iloc[P1[k][0]].to_numpy()); j = pd.concat([a, b], axis=1, join="inner"); cs[k] = dict(n=len(j), corr=round(float(j.corr().iloc[0, 1]), 4))
h["学習行"] = int(ntr); h["学習の終わり"] = str(end); h["保存と学習直後の平均予測の最大差"] = dif; h["シード0とS44の最大差"] = dif44; h["同等性（検証用と記録用の予測の相関）"] = cs
json.dump(h, open(os.path.join(FZ, "hashes.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1); print("差", dif, dif44, cs)
