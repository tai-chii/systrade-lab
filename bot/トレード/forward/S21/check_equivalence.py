# -*- coding: utf-8 -*-
"""forward_s21.run（フォワード用の再実装）が、検証のコード（labels_wk＋run_policy＋block）と同じ売買を出すかの確認。
検証用 H1（15 銘柄）・凍結モデル・2026-03〜2026-09 で比べる（データの終わり近くは検証側が判断を除くので 2026-09-15 までの約定で比較）。"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import common as C
import numpy as np, pandas as pd
import kensho_s21_h1_ml_rr_q515 as K, kensho_s21d_relthr_wf_q519 as Q, kensho_s21f_newjpy_q524 as J
import kensho_s21_noweekend_q533 as Z, kensho_s21_reopen_q534 as E
import forward_s21 as F
S0 = pd.Timestamp("2026-03-01", tz="UTC"); CUT = pd.Timestamp("2026-09-15", tz="UTC")
models, feats = F.check_frozen()
dataw = {}
for s in C.SYMS15:
    o = J.make(K.load(C.H1_HIST, s), s); Rw, Xw = Z.labels_wk(o["d"], s)
    dataw[s] = dict(o, R=Rw, X=Xw, _sr=E.since_reopen(o["d"]))
P = K.predict(models, dataw, S0 - Q.WARM, pd.Timestamp("2026-10-01", tz="UTC"))
PP = J.apply_thr(dataw, P, J.thr_series(dataw, P), S0)
A = K.run_policy(dataw, E.block(PP, dataw, 1), 0.0)
A = A[A["entry"] < CUT][["sym", "entry", "a", "R"]].reset_index(drop=True)
B, _ = F.run(C.H1_HIST, S0, None, C.SYMS15)
B = B[(B["entry"] < CUT)][["sym", "entry", "a", "R", "status"]].reset_index(drop=True)
m = A.merge(B, on=["sym", "entry"], how="outer", suffixes=("_検証", "_再実装"), indicator=True)
both = m[m["_merge"] == "both"]
print(f"検証 {len(A)} 件 / 再実装 {len(B)} 件 / 一致 {len(both)} 件 / 行動の不一致 {(both['a_検証'] != both['a_再実装']).sum()} / R の最大差 {np.abs(both['R_検証'] - both['R_再実装']).max():.2e}")
print("片方だけ:", m[m["_merge"] != "both"].head(10).to_string())
