# -*- coding: utf-8 -*-
"""S21 の「今この足で何をするか」を、記録（forward_s21.py）と同じ関数・同じ凍結モデルで出す。売買はしない。

記録は FORWARD_START 以降を毎回最初から計算し直す（状態を持たない）。ここも同じ計算を「最後の確定足まで」で行い、
最後の足の判断だけを返す。だから記録と執行で判断がずれるのは、足のデータ（Dukascopy と業者）の差だけになる。

入力: H1 ディレクトリ（<銘柄>.parquet。列は Dukascopy 形式: time(UTC)・open high low close・ask_open…ask_close。
      業者の足（bid のみ＋spread）からの変換は execute_mt5.py 側で行う）
出力: dict（JSON にできる）
  asof        : 判断の足（最後の確定足）の時刻（UTC）
  fiscal_year : 使ったモデルの年度（凍結/ か 凍結_<Y>/）
  signals     : {銘柄: {bar, close, D, action, side, rr, pred_over_thr, margin, margin_a}}  action は 0〜5（None なら見送り）。margin＝予測 − 閾値の最大値（合図が無くても入る・判断には使わない）
  stale       : asof より古い足しか無かった銘柄（休場・欠損）。判断しない
  reopen_block: 次の足が「24 時間以上空いた後の最初の足」になる銘柄 → 入らない（Q534 E1）。execute 側が今の足の時刻で確かめる
使い方（確認用）: python signal_s21.py --h1 DIR [--asof ISO]
"""
import argparse, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
FWD = os.path.abspath(os.path.join(HERE, "..", "..", "forward"))          # 検証/トレード/forward
sys.path.insert(0, FWD); sys.path.insert(0, os.path.join(FWD, "S21"))
import common as C                                                        # noqa: E402  sys.path に検証コードを足す
import numpy as np, pandas as pd                                          # noqa: E402
import forward_s21 as FS                                                  # noqa: E402  prep / check_frozen / 年度
import lightgbm as lgb
_Booster = lgb.Booster
class _BoosterUtf8(_Booster):
    def __init__(self, model_file=None, **kw):
        if model_file is not None and "model_str" not in kw:
            with open(model_file, "r", encoding="utf-8") as f:
                kw["model_str"] = f.read()
            super().__init__(**kw)
        else:
            super().__init__(model_file=model_file, **kw)
lgb.Booster = _BoosterUtf8
import kensho_s21_h1_ml_rr_q515 as K                                      # noqa: E402
import kensho_s21f_newjpy_q524 as J                                       # noqa: E402  thr_series / apply_thr
import kensho_s21d_relthr_wf_q519 as Q                                    # noqa: E402  WARM

BREAK_H = FS.BREAK_H


def decide(h1dir, asof=None, syms=None):
    syms = syms or C.SYMS19
    data, stale, missing = {}, [], []
    for s in syms:
        p = os.path.join(h1dir, f"{s}.parquet")
        if not os.path.exists(p):
            missing.append(s); continue
        o = FS.prep(h1dir, s, json.load(open(os.path.join(FS.model_dir(FS.FIRST_FY), "features.json"))))
        if asof is not None:
            # asof の次の足（値の無い「場つなぎ」の 1 本。execute_mt5.bars() が今できている足の時刻で足す）までは残す。
            # H4/D1 の特徴量（M.mtf_feats）は「同じ区切りの足がまだ続くか」で前の区切りを選ぶので、次の足の有無が判断を変える（記録と同じ扱いにするため）
            keep = (o["time"] <= asof + pd.Timedelta(hours=1)).to_numpy(); n = int(keep.sum())
            if n == 0 or not (o["time"].iloc[:n] <= asof).any():
                stale.append(s); continue
            o = dict(d=o["d"].iloc[:n], D=o["D"][:n], F=o["F"].iloc[:n], time=o["time"].iloc[:n], gap_next=np.r_[o["gap_next"][:n - 1], False], sr=o["sr"][:n])
        data[s] = o
    if not data:
        sys.exit("足データが無い")
    asof = asof if asof is not None else max(o["time"][np.isfinite(o["d"]["close"].to_numpy(float))].iloc[-1] for o in data.values())
    Y = FS.fiscal_year(asof)
    models, feats = FS.check_frozen(Y)
    if models is None:
        sys.exit(f"年度 {Y} のモデルが無い（freeze_s21.py --auto を先に）→ 判断しない")
    s0, s1 = FS.fy_start(Y), FS.fy_start(Y + 1)
    d15 = {s: data[s] for s in C.SYMS15 if s in data}
    P = {}
    for s, o in data.items():
        t = o["time"]; m = ((t >= s0 - Q.WARM) & (t < s1)).to_numpy() & np.isfinite(o["D"])
        idx = np.where(m)[0]
        P[s] = (idx, np.column_stack([b.predict(o["F"].iloc[idx]) for b in models]) if len(idx) else np.zeros((0, 6)))
    thr = J.thr_series(d15, {s: P[s] for s in d15})
    PP = J.apply_thr(data, P, thr, s0)
    out = dict(asof=str(asof), fiscal_year=Y, model_dir=FS.model_dir(Y), signals={}, stale=stale, missing=missing, reopen_block=[])
    for s, o in data.items():
        real = np.where((o["time"] <= asof).to_numpy() & np.isfinite(o["d"]["close"].to_numpy(float)))[0]
        if len(real) == 0:
            stale.append(s); continue
        i = int(real[-1]); t = o["time"].iloc[i]
        if t < asof - pd.Timedelta(hours=1):                         # この銘柄の最後の足が古い（休場・欠損）→ 判断しない
            stale.append(s); continue
        idx, pr = PP[s]
        k = np.where(idx == i)[0]
        row = dict(bar=str(t), close=float(o["d"]["close"].iloc[i]), D=float(o["D"][i]) if np.isfinite(o["D"][i]) else None,
                   action=None, side=None, rr=None, pred_over_thr=None,
                   # 2026-11-16（昼の自走・案）: 合図の有無に関わらず「予測 − 閾値」の最大値とその行動（ログに残して記録側と比べる用・判断には使わない）
                   margin=float(pr[k[0]].max()) if len(k) else None, margin_a=int(pr[k[0]].argmax()) if len(k) else None)
        if len(k) and pr[k[0]].max() > 0 and row["D"]:
            a = int(pr[k[0]].argmax()); dr, rr = K.ACTIONS[a]
            row.update(action=a, side="買い" if dr == 1 else "売り", rr=rr, pred_over_thr=float(pr[k[0]].max()))
        out["signals"][s] = row
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--h1", required=True); ap.add_argument("--asof", default=None)
    a = ap.parse_args()
    r = decide(a.h1, pd.Timestamp(a.asof) if a.asof else None)
    print(json.dumps(r, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
