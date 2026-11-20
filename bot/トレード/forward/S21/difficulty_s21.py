# -*- coding: utf-8 -*-
"""S21 フォワードの「その月の局面の難しさ」＝ 学習外 AUC を月ごとに記録する（Q559〜Q561 の帰結・2026-10-28 要対応 ★ の案 (A)）。
売買には一切触らない（記録の列を 1 つ足すだけ・運用規程 §4 の「変えない」には当たらない）。forward_s21.py・凍結モデルは読まない。

- 物差し: Q560 と同じ RandomForest（`kensho_s21_rf_difficulty_nocost_q560.py` の RF_PARAMS・22 特徴量・標的「買い RR1.0 がコスト抜きで勝つ」）を
  月初までのデータ（決済まで月初より前に終わった行＝S21 と同じ embargo）で拡大窓で学習し直し、その月の全足（15 銘柄プール）の学習外 AUC を出す
- いつ出るか: その月の足のラベルが全部決まってから（月末から 120 本≝約 1 週間）。報告は翌月第 2 週以降。先読みには使わない（Q561 で否定・ρ_lag 0.21）
- 参照（位置づけ）: Q560 の保存済み予測（`q560/<四半期>.pkl`・2013-01〜2025-09）を月ごとに切った 153 か月の AUC。初回に `難易度_参照.csv` を作る
  （参照は四半期ごとの学習し直し、フォワードは月ごとの学習し直し。学習の終わりが最大 2 か月違うだけで、拡大窓なのでほぼ同じ物差し）
- 読み（2×2・Q561 の解釈）: AUC が低い月に負けたら「局面」でモデルを疑う理由にならない。AUC が高いのに負けた月だけ「S21 の問題」の疑い
- 出力: `S21/記録/難易度.csv`（月ごとに 1 行・追記）・`難易度.json`（最新・report.py が読む）・`難易度_参照.csv/.json`
使い方: python3 difficulty_s21.py [--month YYYY-MM] [--init] [--smoke] [--out DIR]
  何も付けなければ「まだ無い月のうち、ラベルが決まった月」を全部出す（無ければすぐ終わる。run_forward.sh が毎日呼ぶ）"""
import argparse, json, os, pickle, shutil, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import common as C
import numpy as np, pandas as pd
import kensho_s21_h1_ml_rr_q515 as K
import kensho_s21_rf_difficulty_nocost_q560 as G     # build / train_rows / fit_rf / predict_q / auc / RF_PARAMS を流用（変更なし）

HERE = os.path.dirname(os.path.abspath(__file__))
FIRST_MONTH = "2026-10"                               # フォワード開始の月（2026-10-25〜）。暦月まるごとの AUC を出す
Q560_PKL = os.path.join(C.S21_CODE, "q560")           # Q560 の保存済み予測（四半期ごと）
Q560_RES = os.path.join(C.S21_CODE, "results", "result_q560.json")
REF_END = pd.Timestamp("2025-10-01", tz="UTC")        # Q560 の評価の終わり（含まない）
SEED = 20261028
STEP = 3                                              # Q560 と同じ（学習行の間引き）
TERCILE = (1 / 3, 2 / 3)
LAG_DAYS = 5                                          # 月末からこの日数ぶんデータが無ければ、読み込みもしない（120 本 ≈ 5 営業日）


def month_start(m):
    return pd.Timestamp(m + "-01", tz="UTC")


def next_month(m):
    return (month_start(m) + pd.DateOffset(months=1)).strftime("%Y-%m")


def qlabel(m):
    t = month_start(m); return f"{t.year}-Q{(t.month - 1) // 3 + 1}"


def _py(v):
    if isinstance(v, float) and np.isnan(v):
        return None
    return v.item() if hasattr(v, "item") else v


def merged_h1(dst, syms):
    """freeze_s21.merged_h1 と同じ: 履歴（market_data/H1）＋フォワード（market_data_forward/H1）を時刻でつなぐ（重なりはフォワード側）。"""
    os.makedirs(dst, exist_ok=True); last = {}
    for s in syms:
        parts = [pd.read_parquet(p) for p in [os.path.join(C.H1_HIST, f"{s}.parquet"), os.path.join(C.FWD_DATA, "H1", f"{s}.parquet")] if os.path.exists(p)]
        if not parts:
            sys.exit(f"{s} のデータが無い（{C.H1_HIST}・{C.FWD_DATA}/H1）")
        d = pd.concat(parts).drop_duplicates("time", keep="last").sort_values("time").reset_index(drop=True)
        d.to_parquet(os.path.join(dst, f"{s}.parquet"), index=False); last[s] = d["time"].iloc[-1]
    return last


def add_ok_D(data):
    """D（1.5×ATR24）が有効な行 ＝ AUC を測る行。y が nan なのにここが True なら「ラベルがまだ決まっていない」。"""
    for o in data.values():
        o["ok_D"] = np.isfinite(o["F"]["ret1"].to_numpy(float))
    return data


def month_rows(o, m):
    s0, s1 = month_start(m), month_start(next_month(m))
    t = o["time"]; msk = ((t >= s0) & (t < s1)).to_numpy() & o["ok_D"]
    return np.where(msk)[0]


def month_complete(data, m):
    for o in data.values():
        idx = month_rows(o, m)
        if len(idx) == 0 or not np.isfinite(o["y"][idx]).all():
            return False
    return True


# ---------------- 参照（Q560 の保存済み予測を月で切る） ----------------
def _per_month(tab):
    tab = tab[np.isfinite(tab["y"])].copy(); tab["y"] = tab["y"].astype(int)
    per_m = tab.groupby("m").apply(lambda g: pd.Series(dict(auc=G.auc(g["y"].to_numpy(), g["s"].to_numpy()), n=len(g))), include_groups=False)
    per_q = tab.groupby("q").apply(lambda g: G.auc(g["y"].to_numpy(), g["s"].to_numpy()), include_groups=False)
    return per_m, per_q


def build_reference(out, smoke_data=None, smoke_params=None):
    """難易度_参照.csv（月・AUC・n）と 難易度_参照.json（三分位など）。実データでは Q560 の pkl の index が今の履歴データと合うことを per_q_auc で確かめる。"""
    if smoke_data is None:
        res = json.load(open(Q560_RES, encoding="utf-8"))
        if res.get("smoke"):
            sys.exit("result_q560.json が smoke のもの")
        data = G.build(C.H1_HIST, list(K.SYMS), False, np.random.default_rng(SEED), REF_END)
        pks = sorted(f for f in os.listdir(Q560_PKL) if f.endswith(".pkl")); tab = []
        for f in pks:
            P, _ = pickle.load(open(os.path.join(Q560_PKL, f), "rb")); ql = f[:-4]
            for s, (idx, pr) in P.items():
                if len(idx):
                    t = data[s]["time"].iloc[idx]
                    tab.append(pd.DataFrame(dict(q=ql, m=t.dt.strftime("%Y-%m").to_numpy(), y=data[s]["y"][idx], s=pr)))
        per_m, per_q = _per_month(pd.concat(tab, ignore_index=True))
        diff = max(abs(per_q[q] - v) for q, v in res["per_q_auc"].items())          # index が合っているか
        if diff > 1e-9:
            sys.exit(f"Q560 の保存済み予測と今の履歴データの行が合わない（四半期 AUC の最大差 {diff:.2e}）。参照を作れない")
        source = f"Q560 の保存済み予測（{len(pks)} 四半期）を月で切った。四半期 AUC は result_q560.json と一致（最大差 {diff:.1e}）"
    else:                                                               # smoke: 合成データで四半期ごとに小さな RF
        tab = []
        for q in G.quarters(G.UTC("2015-04-01"), G.UTC("2015-10-01")):
            Xtr, ytr, _ = G.train_rows(smoke_data, q, STEP); m = G.fit_rf(Xtr, ytr, smoke_params, SEED)
            for s, (idx, pr) in G.predict_q(m, smoke_data, q, q + pd.DateOffset(months=3)).items():
                t = smoke_data[s]["time"].iloc[idx]
                tab.append(pd.DataFrame(dict(q=G.qlabel(q), m=t.dt.strftime("%Y-%m").to_numpy(), y=smoke_data[s]["y"][idx], s=pr)))
        per_m, per_q = _per_month(pd.concat(tab, ignore_index=True)); source = "smoke（合成データ）"
    per_m = per_m.reset_index().rename(columns={"m": "month"}); per_m["n"] = per_m["n"].astype(int)
    per_m.to_csv(os.path.join(out, "難易度_参照.csv"), index=False)
    a = per_m["auc"].to_numpy(float); qv = per_q.to_numpy(float)
    ref = dict(built_at=time.strftime("%Y-%m-%d %H:%M"), source=source, months=int(len(a)), month_range=f"{per_m['month'].iloc[0]}〜{per_m['month'].iloc[-1]}",
               month_tercile=[float(np.quantile(a, TERCILE[0])), float(np.quantile(a, TERCILE[1]))], month_mean=float(a.mean()), month_sd=float(a.std(ddof=1)),
               quarters=int(len(qv)), quarter_tercile=[float(np.quantile(qv, TERCILE[0])), float(np.quantile(qv, TERCILE[1]))], quarter_auc=[float(x) for x in qv],
               note="位置 低/中/高 は三分位。Q561: 四半期 AUC 下位 1/3 の S21 の 1 件あたり R は +0.003・上位 1/3 は +0.108")
    C.write_json(os.path.join(out, "難易度_参照.json"), ref)
    print(f"  参照: {ref['months']} か月（{ref['month_range']}）・月 AUC 平均 {ref['month_mean']:.3f} sd {ref['month_sd']:.3f}・三分位 {ref['month_tercile'][0]:.3f}/{ref['month_tercile'][1]:.3f}", flush=True)


def position(x, ref_values, terc):
    pct = float((np.asarray(ref_values, float) < x).mean() * 100)
    return pct, ("低" if x < terc[0] else ("高" if x > terc[1] else "中"))


def reading(pos, sum_R, n):
    if n == 0 or sum_R is None:
        return "S21 の決済がその月に無い"
    if pos == "低":
        return "難しい局面で負け → モデルを疑う理由にならない" if sum_R <= 0 else "難しい局面でも稼いだ"
    if pos == "高":
        return "★ 易しい局面なのに負け → S21 の問題の疑い" if sum_R <= 0 else "易しい局面で稼いだ（期待どおり）"
    return "中位 → 判断保留"


def s21_month(trades_csv, m):
    """その月に入った決済済みの S21 の売買（entry の月・Q561 と同じ切り方）。"""
    if not os.path.exists(trades_csv):
        return 0, None, None
    tr = pd.read_csv(trades_csv)
    if not len(tr):
        return 0, None, None
    tr = tr[tr["status"] == "closed"].copy(); tr["m"] = pd.to_datetime(tr["entry"], utc=True).dt.strftime("%Y-%m")
    g = tr[tr["m"] == m]
    return int(len(g)), (float(g["R"].mean()) if len(g) else None), (float(g["R"].sum()) if len(g) else None)


# ---------------- 本体 ----------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--month", help="この月だけ出し直す（YYYY-MM）"); ap.add_argument("--init", action="store_true", help="参照だけ作る")
    ap.add_argument("--smoke", action="store_true"); ap.add_argument("--out", default=os.path.join(HERE, "記録"))
    ap.add_argument("--trades", default=os.path.join(HERE, "記録", "trades_latest.csv"))
    a = ap.parse_args(); os.makedirs(a.out, exist_ok=True); t00 = time.time()
    G._compat_tz_to_numpy()
    tag = "smoke_" if a.smoke else ""
    csv = os.path.join(a.out, tag + "難易度.csv"); js = os.path.join(a.out, tag + "難易度.json")
    refdir = os.path.join(a.out, "smoke_ref") if a.smoke else a.out; os.makedirs(refdir, exist_ok=True)
    done = pd.read_csv(csv) if os.path.exists(csv) else pd.DataFrame(columns=["month"])
    params = dict(G.RF_PARAMS)

    if a.smoke:
        syms = ["EURUSD", "US500"]; params = dict(params, n_estimators=20, min_samples_leaf=50); first = "2015-10"
        data = add_ok_D(G.build(None, syms, True, np.random.default_rng(SEED), G.UTC("2030-01-01")))
        if not os.path.exists(os.path.join(refdir, "難易度_参照.csv")):
            build_reference(refdir, data, params)
    else:
        syms = list(K.SYMS); first = FIRST_MONTH
        if not os.path.exists(os.path.join(refdir, "難易度_参照.csv")):
            print("参照（Q560 の保存済み予測を月で切る）を作る", flush=True); build_reference(refdir)
        if a.init:
            return
        # 安い事前確認（毎日呼ばれるので）: 次の候補月の月末 + LAG_DAYS までフォワードのデータが無ければ、読み込まずに終わる
        cand = a.month or (next_month(str(done["month"].iloc[-1])) if len(done) else first)
        p0 = os.path.join(C.FWD_DATA, "H1", f"{syms[0]}.parquet")
        last = pd.Timestamp(pd.read_parquet(p0, columns=["time"])["time"].max()) if os.path.exists(p0) else None
        if last is not None and last.tzinfo is None:
            last = last.tz_localize("UTC")
        if last is None or last < month_start(next_month(cand)) + pd.Timedelta(days=LAG_DAYS):
            print(f"  {cand} のラベルはまだ決まらない（フォワードのデータの最後 {last}）。何もしない"); return
        tmp = os.path.join(C.WS, "作業層", "大容量", "_difficulty_h1")
        try:
            merged_h1(tmp, syms)
            data = add_ok_D(G.build(tmp, syms, False, np.random.default_rng(SEED), G.UTC("2100-01-01")))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    data_end = max(o["time"].iloc[-1] for o in data.values())
    ref = pd.read_csv(os.path.join(refdir, "難易度_参照.csv")); refj = json.load(open(os.path.join(refdir, "難易度_参照.json"), encoding="utf-8"))

    # 出す月: --month ならその月だけ。なければ「まだ無い月」を first から順に、ラベルが決まっている限り
    if a.month:
        months = [a.month]
    else:
        months = []; m = next_month(str(done["month"].iloc[-1])) if len(done) else first
        while month_start(m) < data_end and month_complete(data, m):
            months.append(m); m = next_month(m)
    if not months:
        print(f"  新しく出せる月は無い（データの最後 {data_end}）"); return
    import sklearn
    rows = []
    for m in months:
        if not month_complete(data, m):
            print(f"  {m}: ラベルが決まっていない足がある（データの最後 {data_end}）。飛ばす"); continue
        t0 = time.time(); s0, s1 = month_start(m), month_start(next_month(m))
        Xtr, ytr, _ = G.train_rows(data, s0, STEP)
        if len(Xtr) < (500 if a.smoke else G.MIN_TRAIN_ROWS) or len(np.unique(ytr)) < 2:
            print(f"  {m}: 学習行 {len(Xtr)} で飛ばす"); continue
        model = G.fit_rf(Xtr, ytr, params, SEED + s0.year * 12 + s0.month)
        ys, ss, per_sym = [], [], {}
        for s, (idx, pr) in G.predict_q(model, data, s0, s1).items():
            y = data[s]["y"][idx]; ok = np.isfinite(y); ys.append(y[ok]); ss.append(pr[ok]); per_sym[s] = G.auc(y[ok], pr[ok])
        y = np.concatenate(ys).astype(int); sc = np.concatenate(ss); au = G.auc(y, sc)
        pct, pos = position(au, ref["auc"], refj["month_tercile"])
        n_tr, mean_R, sum_R = s21_month(a.trades, m)
        row = dict(month=m, auc=round(au, 4), n=int(len(y)), pct=round(pct, 1), 位置=pos, s21_n=n_tr, s21_mean_R=None if mean_R is None else round(mean_R, 4),
                   s21_sum_R=None if sum_R is None else round(sum_R, 2), 読み=reading(pos, sum_R, n_tr), train_rows=int(len(Xtr)),
                   auc_min_sym=min(per_sym, key=per_sym.get), auc_max_sym=max(per_sym, key=per_sym.get),
                   run_at=time.strftime("%Y-%m-%d %H:%M"), sklearn=sklearn.__version__, sec=round(time.time() - t0))
        rows.append(row); done = pd.concat([done[done["month"] != m], pd.DataFrame([row])], ignore_index=True).sort_values("month", ignore_index=True)
        print(f"  {m}: AUC {au:.4f}（参照の {pct:.0f}% 位・{pos}）・n {len(y):,}・学習 {len(Xtr):,} 行・S21 {n_tr} 件{'' if sum_R is None else f' {sum_R:+.1f}R'} → {row['読み']}（{time.time()-t0:.0f}s）", flush=True)
    if not rows:
        return
    for c in ["n", "s21_n", "train_rows", "sec"]:
        done[c] = done[c].astype("Int64")
    done.to_csv(csv, index=False)
    # 最新の要約（report.py が読む）: 最新月と、その四半期の済んだ月をまとめた AUC（Q561 の対応は四半期で測ったもの）
    latest = {k: _py(v) for k, v in done.iloc[-1].to_dict().items()}; qm = done[done["month"].map(qlabel) == qlabel(latest["month"])]
    q_auc = float(np.average(qm["auc"].astype(float), weights=qm["n"].astype(float)))
    q_pct, q_pos = position(q_auc, refj["quarter_auc"], refj["quarter_tercile"])
    C.write_json(js, dict(latest=latest,
                          quarter=dict(q=qlabel(latest["month"]), months=[str(x) for x in qm["month"]], auc=round(q_auc, 4), pct=round(q_pct, 1), 位置=q_pos, 四半期三分位=refj["quarter_tercile"]),
                          reference=dict(months=refj["months"], range=refj["month_range"], tercile=refj["month_tercile"]), updated=time.strftime("%Y-%m-%d %H:%M"),
                          sec_total=round(time.time() - t00)))
    print(f"  書いた: {csv}・{js}（{time.time()-t00:.0f}s）", flush=True)


if __name__ == "__main__":
    main()
