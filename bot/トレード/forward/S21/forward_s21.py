# -*- coding: utf-8 -*-
"""S21 候補形のフォワード記録（週 1 回）。凍結モデルで FORWARD_START 以降の売買を毎回最初から計算し直す（状態を持たない）。
- 判断: 各 H1 足の確定時。相対閾値（15 銘柄プール・直近 28 暦日の 90 パーセンタイル）を超えた最大の行動。週明け再開の最初の足では入らない
- 出口: SL 1.5×ATR24・TP RR×SL・週末前（次の足まで 24 時間以上空く足）の終値・120 本で時間切れ。保有コスト差し引き
- 1 銘柄 同時 1 本・週 10 回まで。R 単位（1 回 = 1R）で記録
- 判定: 運用規程_フォワード_20261025.md（停止 −130R・12 か月で累計 ≤ 0・6 か月時点の確認）
- モデル（2026-10-27 追記・運用規程 §4・Q546）: 年度 Y（Y-10-01〜Y+1-10-01）の判断は、年度 Y のモデル（freeze_s21.py が Y-10-01 までで学習。
  2026 年度は 凍結/、以降は 凍結_<Y>/）で行う。相対閾値は検証（Q534 E1）と同じく、その年度のモデルの予測で作る。
  ある年度のモデルが無ければ、その年度の始まり以降は判断しない（古いモデルで続けない）→ 終了コード 4・要対応に ★
使い方: python3 forward_s21.py [--h1 DIR] [--start ISO] [--end ISO] [--out DIR]"""
import argparse, json, os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import common as C
import numpy as np, pandas as pd, lightgbm as lgb
import kensho_s21_h1_ml_rr_q515 as K
import kensho_s21f_mtf_wf_q521 as M
import kensho_s21f_newjpy_q524 as J          # 円クロス 4 本の CLASS もここで設定される
import kensho_s21d_relthr_wf_q519 as Q

HERE = os.path.dirname(os.path.abspath(__file__)); FROZEN = os.path.join(HERE, "凍結")
FIRST_FY = 2026


def fy_start(Y):
    return pd.Timestamp(f"{Y}-10-01", tz="UTC")


def fiscal_year(ts):
    ts = pd.Timestamp(ts); return ts.year if ts.month >= 10 else ts.year - 1


def model_dir(Y):
    return FROZEN if Y <= FIRST_FY else os.path.join(HERE, f"凍結_{Y}")
BREAK_H = 24
STOP_DD_R = -130.0
EXPECTED_PER_YEAR = 2536 + 516          # 15 銘柄（Q534 E1）＋円クロス 4 本（Q524）


def check_frozen(Y=FIRST_FY):
    """年度 Y のモデルを読む（ハッシュを確かめる）。無ければ (None, None)。"""
    D = model_dir(Y)
    if not os.path.exists(os.path.join(D, "hashes.json")):
        return None, None
    H = json.load(open(os.path.join(D, "hashes.json")))
    bad = [f for f in [f"model_a{a}.txt" for a in range(6)] + ["features.json", "config.json"] if C.sha256(os.path.join(D, f)) != H[f]]
    if bad:
        sys.exit(f"凍結ファイルが変わっている（{D}）: {bad}（記録を止める）")
    return [lgb.Booster(model_file=os.path.join(D, f"model_a{a}.txt")) for a in range(6)], json.load(open(os.path.join(D, "features.json")))


def prep(h1dir, s, feats):
    d = K.load(h1dir, s)
    d = d[d["high"] != d["low"]].reset_index(drop=True)
    bh, bl, bc = (d[c].to_numpy(float) for c in ["high", "low", "close"])
    pc = np.r_[bc[0], bc[:-1]]
    tr = np.maximum(bh - bl, np.maximum(np.abs(bh - pc), np.abs(bl - pc)))
    D = K.K_ATR * pd.Series(tr).rolling(24, min_periods=24).mean().to_numpy()
    F = pd.concat([K.features(d, D, s).reset_index(drop=True), M.mtf_feats(d, D).reset_index(drop=True)], axis=1)[feats]
    t = d["time"].to_numpy()                                    # tz なし UTC（common の互換）
    gap_next = np.r_[(t[1:] - t[:-1]) / np.timedelta64(1, "h") >= BREAK_H, False]   # 最後の足の次は未知 → False
    re = np.r_[True, (t[1:] - t[:-1]) / np.timedelta64(1, "h") >= BREAK_H]
    sr = np.zeros(len(d), int); c = 10**6
    for j in range(len(d)):
        c = 0 if re[j] else c + 1; sr[j] = c
    return dict(d=d, D=D, F=F, time=d["time"].reset_index(drop=True), gap_next=gap_next, sr=sr)


def simulate(o, s, i, a):
    """足 i で決めて i+1 の始値で入る。戻り値: dict（status=closed/open）"""
    d = o["d"]; n = len(d); dr, rr = K.ACTIONS[a]; e = i + 1; Dv = o["D"][i]
    bo, bh, bl, bc = (d[c].to_numpy(float) for c in ["open", "high", "low", "close"])
    ao, ah, al, ac = (d[f"ask_{c}"].to_numpy(float) for c in ["open", "high", "low", "close"])
    P = ao[e] if dr == 1 else bo[e]; SL = P - dr * Dv; TP = P + dr * rr * Dv
    exitp = None; xj = None; why = None
    for k in range(K.H):
        j = e + k
        if j >= n:
            break
        if dr == 1:
            op, lo, hi = bo[j], bl[j], bh[j]
            if op <= SL: exitp, why = op, "窓で損切り"
            elif lo <= SL: exitp, why = SL, "損切り"
            elif hi >= TP: exitp, why = TP, "利確"
        else:
            op, lo, hi = ao[j], al[j], ah[j]
            if op >= SL: exitp, why = op, "窓で損切り"
            elif hi >= SL: exitp, why = SL, "損切り"
            elif lo <= TP: exitp, why = TP, "利確"
        if exitp is None and o["gap_next"][j]:
            exitp, why = (bc[j] if dr == 1 else ac[j]), "週末前決済"
        if exitp is None and k == K.H - 1:
            exitp, why = (bc[j] if dr == 1 else ac[j]), "時間切れ"
        if exitp is not None:
            xj = j; break
    t = o["time"]; cls = K.CLASS[s]
    if xj is None:                                              # まだ持っている（最後の終値で評価）
        j = n - 1; mark = bc[j] if dr == 1 else ac[j]
        held = (t.iloc[j] - t.iloc[e]).total_seconds() / 3600
        Rv = dr * (mark - P) / Dv - K.HOLD_RATE[cls] / 8760 * held * P / Dv
        return dict(status="open", exit_j=None, exit_time=None, exit_px=None, why="保有中", R=Rv, P=P, SL=SL, TP=TP)
    held = (t.iloc[xj] - t.iloc[e]).total_seconds() / 3600
    Rv = dr * (exitp - P) / Dv - K.HOLD_RATE[cls] / 8760 * held * P / Dv
    return dict(status="closed", exit_j=xj, exit_time=t.iloc[xj], exit_px=exitp, why=why, R=Rv, P=P, SL=SL, TP=TP)


def run(h1dir, start, end=None, syms=None):
    models0, feats = check_frozen(fiscal_year(start)); syms = syms or C.SYMS19
    if models0 is None:
        sys.exit(f"記録の始まりの年度 {fiscal_year(start)} のモデルが無い")
    data = {}; run.missing = []; run.model_missing = None
    for s in syms:
        if not os.path.exists(os.path.join(h1dir, f"{s}.parquet")):
            run.missing.append(s); continue
        o = prep(h1dir, s, feats)
        if end is not None:
            keep = (o["time"] < end).to_numpy(); n = int(keep.sum())
            o = dict(d=o["d"].iloc[:n], D=o["D"][:n], F=o["F"].iloc[:n], time=o["time"].iloc[:n], gap_next=np.r_[o["gap_next"][:n - 1], False], sr=o["sr"][:n])
        data[s] = o
    if not any(s in data for s in C.SYMS15):
        return pd.DataFrame(), None
    d15 = {s: data[s] for s in C.SYMS15 if s in data}
    data_end = max(o["time"].iloc[-1] for o in data.values())
    PP = {s: (np.zeros(0, int), np.zeros((0, 6))) for s in data}
    for Y in range(fiscal_year(start), fiscal_year(data_end) + 1):        # 年度ごとに、その年度のモデルで予測・閾値
        s0, s1 = max(start, fy_start(Y)), fy_start(Y + 1)
        models, fy = (models0, feats) if Y == fiscal_year(start) else check_frozen(Y)
        if models is None:
            run.model_missing = Y; break                                  # この年度の始まり以降は判断しない
        if fy != feats:
            sys.exit(f"年度 {Y} のモデルの特徴量が 2026 年度と違う（記録を止める）")
        P = {}
        for s, o in data.items():
            t = o["time"]; m = ((t >= s0 - Q.WARM) & (t < s1)).to_numpy() & np.isfinite(o["D"])
            idx = np.where(m)[0]
            P[s] = (idx, np.column_stack([b.predict(o["F"].iloc[idx]) for b in models]) if len(idx) else np.zeros((0, 6)))
        thr = J.thr_series(d15, {s: P[s] for s in d15})
        for s, (idx, pr) in J.apply_thr(data, P, thr, s0).items():
            keep = (data[s]["time"].iloc[idx] < s1).to_numpy()
            PP[s] = (np.r_[PP[s][0], idx[keep]], np.r_[PP[s][1], pr[keep]])
    rows = []
    for s, (idx, pr) in PP.items():
        o = data[s]; n = len(o["d"]); t = o["time"]
        week = t.dt.tz_convert(None).dt.to_period("W-SUN").to_numpy()
        busy = -1; wk = None; cnt = 0
        for k, i in enumerate(idx):
            if i + 1 >= n or o["sr"][i + 1] < 1:               # 入る足が未到来 or 週明け再開の最初の足
                continue
            if week[i] != wk:
                wk = week[i]; cnt = 0
            if i < busy or cnt >= K.WEEK_CAP or pr[k].max() <= 0:
                continue
            a = int(pr[k].argmax()); r = simulate(o, s, i, a); dr, rr = K.ACTIONS[a]
            rows.append(dict(sym=s, decision=t.iloc[i], entry=t.iloc[i + 1], side="買い" if dr == 1 else "売り", rr=rr, a=a, pred_over_thr=float(pr[k].max()),
                             entry_px=r["P"], sl=r["SL"], tp=r["TP"], exit=r["exit_time"], exit_px=r["exit_px"], why=r["why"], status=r["status"], R=float(r["R"])))
            cnt += 1
            if r["status"] == "open":
                break
            busy = r["exit_j"]
    tr = pd.DataFrame(rows)
    return tr.sort_values(["entry", "sym"]).reset_index(drop=True) if len(tr) else tr, data_end


def judge(tr, start, data_end):
    cl = tr[tr["status"] == "closed"] if len(tr) else tr
    days = max((data_end - start).total_seconds() / 86400, 0) if data_end is not None else 0.0
    cum = cl.sort_values("exit")["R"].cumsum() if len(cl) else pd.Series(dtype=float)
    peak = max(0.0, float(cum.max())) if len(cum) else 0.0
    total = float(cum.iloc[-1]) if len(cum) else 0.0
    dd = min(0.0, float((cum - cum.cummax().clip(lower=0)).min())) if len(cum) else 0.0
    exp_n = EXPECTED_PER_YEAR * days / 365
    stop = []
    if dd <= STOP_DD_R: stop.append(f"最高値から {dd:.0f}R（停止線 {STOP_DD_R:.0f}R）")
    if days >= 365 and total <= 0: stop.append("12 か月で累計 R ≤ 0")
    six = None
    if days >= 182:
        six = {"件数が期待の±30%内": bool(abs(len(cl) - exp_n) <= 0.3 * exp_n), "平均R正": bool(len(cl) and cl["R"].mean() > 0), "停止に触れていない": not stop,
                   "実測コスト": "デモ口座の約定記録が必要（未）"}
    return dict(経過日数=round(days, 1), 決済済み=int(len(cl)), 保有中=int((tr["status"] == "open").sum()) if len(tr) else 0, 期待件数=round(exp_n),
                平均R=float(cl["R"].mean()) if len(cl) else None, 勝率=float((cl["R"] > 0).mean()) if len(cl) else None, 累計R=total, 最高値R=peak, 最高値からR=dd,
                停止=stop, 六か月の確認=six, データの最後=str(data_end), 欠けた銘柄=getattr(run, "missing", []),
                モデルが無い年度=getattr(run, "model_missing", None))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--h1", default=os.path.join(C.FWD_DATA, "H1")); ap.add_argument("--start", default=C.FORWARD_START)
    ap.add_argument("--end", default=None); ap.add_argument("--out", default=os.path.join(HERE, "記録"))
    a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)
    start = pd.Timestamp(a.start); end = pd.Timestamp(a.end) if a.end else None
    tr, data_end = run(a.h1, start, end)
    j = judge(tr, start, data_end)
    tr.to_csv(os.path.join(a.out, "trades_latest.csv"), index=False)
    C.write_json(os.path.join(a.out, "状態.json"), j)
    runs = os.path.join(a.out, "runs.csv"); hdr = not os.path.exists(runs)
    with open(runs, "a", encoding="utf-8") as f:
        if hdr: f.write("run_at,data_end,closed,open,mean_R,total_R,dd_R,stop\n")
        f.write(f"{time.strftime('%Y-%m-%d %H:%M')},{data_end},{j['決済済み']},{j['保有中']},{j['平均R'] if j['平均R'] is not None else ''},{j['累計R']:.2f},{j['最高値からR']:.2f},{'|'.join(j['停止'])}\n")
    print(json.dumps(j, ensure_ascii=False, indent=1, default=str))
    if j["停止"]:
        print("★ 停止条件に達した: 運用規程どおり記録を打ち切り、原因を確認する"); sys.exit(3)
    if j["モデルが無い年度"] is not None:
        print(f"★ 年度 {j['モデルが無い年度']} のモデルが無い: その年度の始まり以降は判断していない（freeze_s21.py --auto）"); sys.exit(4)


if __name__ == "__main__":
    main()
