# -*- coding: utf-8 -*-
"""この環境で検証と同じ数字が出るかの確認: Q534 E1 の 2024 年度（2024-10〜2025-09）を再現する。
記録値: n=2694 mean_R=0.0325 sum=87（run_q534.log）"""
import os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import common as C
import kensho_s21_h1_ml_rr_q515 as K, kensho_s21_walkforward_q518 as W, kensho_s21d_relthr_wf_q519 as Q
import kensho_s21f_newjpy_q524 as J, kensho_s21_noweekend_q533 as Z, kensho_s21_reopen_q534 as E
t0 = time.time(); dataw = {}
for s in C.SYMS15:
    o = J.make(K.load(C.H1_HIST, s), s); Rw, Xw = Z.labels_wk(o["d"], s)
    dataw[s] = dict(o, R=Rw, X=Xw, _sr=E.since_reopen(o["d"]))
print("準備", round(time.time() - t0), flush=True)
Y = 2024; s0, s1 = W.TS(Y), W.TS(Y + 1)
mw, _ = Q.train_window(dataw, s0, None)
Pw = K.predict(mw, dataw, s0 - Q.WARM, s1); PPw = J.apply_thr(dataw, Pw, J.thr_series(dataw, Pw), s0)
tr = K.run_policy(dataw, E.block(PPw, dataw, 1), 0.0)
print(f"再現 n={len(tr)} mean_R={tr['R'].mean():.4f} sum={tr['R'].sum():.0f}  記録 n=2694 mean_R=0.0325 sum=87  {time.time()-t0:.0f}s", flush=True)
