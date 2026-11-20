# -*- coding: utf-8 -*-
"""S30（日本株 横断 ML・月次 L/S・Q582 の形を凍結）の仮想フォワード記録（Q586・2026-10-31）。
- 凍結: Q582 の特徴量 20・LightGBM の設定・種 3・上位下位 10%・1 日待ち・JP 片道 10bp・適格の規則。Q582 の関数を import して使う（写さない）。
- 学習: 手仕舞い x < 2026-01-01 の行（Q583 の 2026 年モデルと同じ学習集合）。初回に学習して 凍結/ に保存し、以後は読むだけ（ハッシュで点検）。
- 記録: 判断日 t ≥ 2026-07-01（最初は 2026-07-31 の月末）から、月ごとの コスト後 L−S bp/日・IC（Spearman）・入れ替え率・建玉。閉じていない月は「未確定」。
- 合否: 12 か月で IC t ≥ 2（Q583 と同じ主）。停止の目安: 累積 L−S（単純和）の最大下落が Q583 封印期間の最悪 × 1.5（−0.486）を超えたら ★（終了コード 3）。
- 同等性: 凍結モデルで 2026-01〜06 の日次 L−S を出し、Q583 の daily_jp_q583.csv と比べる（各月の最初の日＝コスト日は除く）。
- 確定した月の固定（2026-11-09・判断待ち 9 の A・修正11）: 月が閉じた最初の回に、その月の行・日次・建玉を追記だけの表（記録/確定_monthly.csv・確定_daily.csv・確定_建玉/）に書き、
  以後の monthly.csv・daily.csv・建玉_YYYYMM.csv・状態.json の確定した月はそこから読む（価格の取り直しで配当調整が動いても記録の値は変わらない）。
  今回の再計算との差は 状態.json の「確定の固定」に記述だけ残す。追記だけの表が前回の保存から変わっていたら（手で触った・壊れた）何も書かずに終了コード 4。
使い方: 作業層/大容量/venv_forward/bin/python forward_s30.py [--out DIR]（lightgbm が要る。所要 2〜4 分）"""
import argparse, datetime, hashlib, importlib.util, json, os, shutil, sys, time
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
KENSHO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))                    # 検証/
FE = os.path.join(KENSHO, "verification-lab", "financial-engineering")
sys.path.insert(0, os.path.join(KENSHO, "verification-lab", "tools"))
import equities_free as ef
ef.DIR = os.path.join(ef.DIR, "s30")   # 2026-11-03: S30 専用の写し（update_prices_s30.py が伸ばす）。検証の共有 jp_daily.parquet は書き換えない（監査E の 3）
_sp =importlib.util.spec_from_file_location("q582", os.path.join(FE, "jp-us-ml-xsec-q582", "kensho_ml_xsec_q582.py"))
M = importlib.util.module_from_spec(_sp); _sp.loader.exec_module(M); B = M.B

TRAIN_END = pd.Timestamp("2026-01-01")      # 学習は x < これ（凍結＝2026 年 1 月時点のモデル）
FWD_FIRST_T = pd.Timestamp("2026-07-01")    # 判断日 t がこれ以降を記録（最初は 2026-07-31）
PRED_FROM = pd.Timestamp("2025-12-01")      # 予測はここから（2026-01 の入れ替え率の計算に前月の建玉が要る）
EQUIV = (pd.Timestamp("2026-01-01"), pd.Timestamp("2026-07-01"))
Q583_DAILY = os.path.join(FE, "jp-ml-xsec-holdout-q583", "results", "daily_jp_q583.csv")
STOP_DD = -0.486                             # Q583 封印期間の累積 L−S（単純和）の最悪 −0.324 × 1.5
FREEZE = os.path.join(HERE, "凍結"); REC = os.path.join(HERE, "記録"); CFG = M.CFG["jp"]

# 確定した月の固定（追記だけの表。a.out の下）
FIXED_M, FIXED_D, FIXED_POS, FIXED_H = "確定_monthly.csv", "確定_daily.csv", "確定_建玉", "確定_hashes.json"
FIX_COLS = ("ls_bp_日", "ls_累積bp", "IC", "入れ替え率", "銘柄数", "買い", "売り", "日数", "買いのみ_bp_日")   # 再計算との差を見る列
EXIT_TAMPER = 4
DECIDED_POS = "判断時_建玉"   # 2026-11-12 修正15（監査B の 7）: 判断した月の建玉を、最初に計算した回に一度だけ写す（判断時の建玉の証拠・記録の計算には使わない）


def sha(p):
    h = hashlib.sha256(); h.update(open(p, "rb").read()); return h.hexdigest()


def log(*a): print(datetime.datetime.now().strftime("%H:%M:%S"), *a, flush=True)


def _now(): return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")


def _ym(t): return str(t)[:4] + str(t)[5:7]   # "2026-07-31" → "202607"


def fixed_check(out):
    """起動時の見張り: 追記だけの表が前回の保存（確定_hashes.json）から変わっていないか。変わった・無くなったファイルの一覧を返す（空なら異常なし）。"""
    hp = os.path.join(out, FIXED_H)
    if not os.path.exists(hp): return []
    h = json.load(open(hp, encoding="utf-8"))
    return [n for n, s in h["files"].items() if not os.path.exists(os.path.join(out, n)) or sha(os.path.join(out, n)) != s]


def fixed_save_hashes(out):
    files = {}
    for n in (FIXED_M, FIXED_D):
        if os.path.exists(os.path.join(out, n)): files[n] = sha(os.path.join(out, n))
    for sub in (FIXED_POS, DECIDED_POS):                     # 修正15: 判断時の建玉の写しも、追記だけの表として見張る
        pd_ = os.path.join(out, sub)
        if os.path.isdir(pd_):
            for f in sorted(os.listdir(pd_)):
                if f.endswith(".csv") and (sub != DECIDED_POS or f.startswith("建玉_")): files[os.path.join(sub, f)] = sha(os.path.join(pd_, f))   # 写した日時.csv（追記の記録）は控えに入れない
    json.dump({"更新": _now(), "files": files, "決まり": "確定した月の行・日次・建玉は一度だけ追記し、以後は変えない。変わっていたら forward_s30.py は何も書かずに終了コード 4"},
              open(os.path.join(out, FIXED_H), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def _differs(a, b):
    if pd.isna(a) and pd.isna(b): return False
    if pd.isna(a) or pd.isna(b): return True
    return abs(float(a) - float(b)) > 1e-9


def fix_closed(out, rows, F, posmap):
    """確定した月を固定し、出力に使う月の表・日次・建玉を組み立てる。
    rows: 今回計算した月の行（dict の list・t は "YYYY-MM-DD"・確定 0/1）、F: 今回計算した日次（index 日付・列に t〔Timestamp〕・確定）、posmap: {t: 建玉 DataFrame（sym・側・p）}。
    返す: mon（確定した月は固定済みの値・未確定は今回の値）、F_out（同）、pos_out {t: DataFrame}（同）、info（状態.json の「確定の固定」）。"""
    pm, pdp, pos_dir = os.path.join(out, FIXED_M), os.path.join(out, FIXED_D), os.path.join(out, FIXED_POS)
    fm = pd.read_csv(pm, dtype={"t": str}) if os.path.exists(pm) else pd.DataFrame()
    fixed_ts = set(fm["t"]) if len(fm) else set()
    newly, drift = [], []
    for r in rows:
        if not r["確定"]: continue
        t = r["t"]
        if t not in fixed_ts: newly.append(t); continue
        f0 = fm[fm["t"] == t].iloc[0]
        diffs = {k: [None if pd.isna(f0[k]) else float(f0[k]), None if pd.isna(r[k]) else float(r[k])] for k in FIX_COLS if k in f0 and _differs(f0[k], r[k])}
        pf = os.path.join(pos_dir, f"建玉_{_ym(t)}.csv"); nd = None
        if os.path.exists(pf) and t in posmap:
            a = set(map(tuple, pd.read_csv(pf)[["sym", "側"]].astype(str).values)); b = set(map(tuple, posmap[t][["sym", "側"]].astype(str).values))
            nd = int(len(a ^ b))
        if diffs or nd: drift.append({"t": t, "値の差（固定, 今回）": diffs, "建玉の入れ替わり（銘柄×側）": nd})
    if newly:
        os.makedirs(pos_dir, exist_ok=True); now = _now()
        add_m = pd.DataFrame([dict(r, 固定日時=now) for r in rows if r["t"] in newly])
        add_m.to_csv(pm, mode="a", header=not os.path.exists(pm), index=False)
        add_d = F[F["t"].isin([pd.Timestamp(t) for t in newly])]
        add_d.to_csv(pdp, mode="a", header=not os.path.exists(pdp))
        for t in newly:
            pf = os.path.join(pos_dir, f"建玉_{_ym(t)}.csv")
            if not os.path.exists(pf) and t in posmap: posmap[t].to_csv(pf, index=False)
        fixed_save_hashes(out)
        fm = pd.read_csv(pm, dtype={"t": str}); fixed_ts = set(fm["t"])
    # 出力の組み立て
    cols = [k for k in rows[0].keys()] if rows else [c for c in fm.columns if c != "固定日時"]
    mon_fixed = fm[cols] if len(fm) else pd.DataFrame(columns=cols)
    mon_open = pd.DataFrame([r for r in rows if r["t"] not in fixed_ts], columns=cols)
    mon = pd.concat([mon_fixed, mon_open], ignore_index=True)
    if len(mon): mon = mon.sort_values("t").reset_index(drop=True)
    if os.path.exists(pdp):
        fd = pd.read_csv(pdp, index_col=0, parse_dates=True, float_precision="round_trip"); fd["t"] = pd.to_datetime(fd["t"])   # round_trip: 書き戻しても桁が変わらない
        F_out = pd.concat([fd, F[~F["t"].isin(fd["t"].unique())]]).sort_index()
    else: F_out = F
    pos_out = {}
    for t, p in posmap.items():
        pf = os.path.join(pos_dir, f"建玉_{_ym(t)}.csv")
        pos_out[t] = pd.read_csv(pf, float_precision="round_trip") if (t in fixed_ts and os.path.exists(pf)) else p
    info = {"固定済みの月": sorted(fixed_ts), "今回固定した月": newly, "再計算との差（記述・記録は固定の値）": drift, "見張り": "異常なし（追記だけの表は前回の保存と一致）"}
    return mon, F_out, pos_out, info


def load_models(tr, data_last):
    """凍結/model_seed<k>.txt が揃っていれば読む（ハッシュ点検）。無ければ学習して保存。"""
    import lightgbm as lgb
    paths = [os.path.join(FREEZE, f"model_seed{s}.txt") for s in M.SEEDS]; hp = os.path.join(FREEZE, "hashes.json")
    if all(os.path.exists(p) for p in paths) and os.path.exists(hp):
        h = json.load(open(hp, encoding="utf-8"))
        for p in paths:
            if sha(p) != h["models"][os.path.basename(p)]:
                raise SystemExit(f"★ 凍結モデルのハッシュが違う: {p}。変えるなら別 ID で凍結し直す")
        return [lgb.Booster(model_file=p) for p in paths], h
    if os.path.exists(os.path.join(REC, "状態.json")):
        # 2026-11-12 修正14（監査B の 4）: 記録が始まった後に凍結が欠けたら、作り直さずに止める（今のデータで学習し直すと「結果を見る前に固定した設定」が跡なく入れ替わる。
        #   11-05 の容量整理のような誤削除で起こりうる）。作り直すのは taichi が決めたときだけ（記録/状態.json を別の場所へ動かしてから・別 ID で凍結し直すのが筋）
        miss = [os.path.basename(p) for p in paths + [hp] if not os.path.exists(p)]
        raise SystemExit(f"★ 凍結が欠けている（{'・'.join(miss)}）。記録は始まっているので作り直さずに止めた。消えたなら控えから戻す")
    os.makedirs(FREEZE, exist_ok=True); log("凍結モデルが無い → 学習（1 回だけ）", len(tr), "行")
    boosters = []
    for s, p in zip(M.SEEDS, paths):
        m = lgb.LGBMRegressor(**M.LGB, random_state=s); m.fit(tr[M.FEATS].values, tr["y"].values); m.booster_.save_model(p); boosters.append(m.booster_)
    h = {"凍結日": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "学習の規則": f"x < {TRAIN_END.date()}", "学習行数": int(len(tr)),
         "学習の t の範囲": [str(tr["t"].min().date()), str(tr["t"].max().date())], "凍結時のデータの最後": str(data_last.date()),
         "config": dict(LGB=M.LGB, seeds=list(M.SEEDS), feats=M.FEATS, frac=M.FRAC, min_names=M.MIN_NAMES, lookback=M.LOOKBACK, cfg=CFG, wait="1日待ち"),
         "models": {os.path.basename(p): sha(p) for p in paths}, "q582_script": sha(_sp.origin),
         "forward_s30.py": sha(os.path.abspath(__file__))}
    json.dump(h, open(hp, "w", encoding="utf-8"), ensure_ascii=False, indent=1); return boosters, h


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default=REC); a = ap.parse_args(); os.makedirs(a.out, exist_ok=True); t0 = time.time()
    bad = fixed_check(a.out)
    if bad:
        print("★ S30 の確定済みの記録（追記だけの表）が前回の保存から変わっている・無くなっている:", bad)
        print("   何も書かずに止める。手で触ったなら元に戻す（Syncthing の版・git）。壊れたなら 自動実行/要対応.md に ★。終了コード", EXIT_TAMPER); sys.exit(EXIT_TAMPER)
    C = ef.load("jp", "close", end=None)    # 封印を開ける: フォワード専用（S30 の記録・事前登録_q586.md）。判定には使わない
    V = ef.load("jp", "volume", end=None)   # 封印を開ける: 同上
    data_last = C.index.max(); log("データの最後", data_last.date(), "銘柄", C.shape[1])
    R = C.pct_change(fill_method=None); R = R.where(R.abs() < 0.5)
    months = M.build_months(C, V, CFG)
    # 閉じた月: x が「t の翌月」より後の月に入っている（build_months は最後の月の x をデータの最後で代用する）
    closed = {t: (x.to_period("M") > t.to_period("M") + 1) for t, e, x, el in months}
    P = M.panel(C, V, months); del V
    P.loc[~P["t"].map(closed), ["y_raw", "y"]] = np.nan
    log("表", P.shape, "月", len(months), "閉じていない月", sum(1 for v in closed.values() if not v))
    tr = P[(P["x"] < TRAIN_END) & P["y"].notna()]
    boosters, H = load_models(tr, data_last)
    Q = P[P["t"] >= PRED_FROM].copy()
    pred = pd.Series(np.mean([b.predict(Q[M.FEATS].values) for b in boosters], axis=0), index=Q.index)
    d = M.run_ls(R, Q, pred, CFG["cost"])                        # 日次: ls・long_mkt・mkt・turn・n
    # 日 → 判断月 t
    spans = [(t, e, x) for t, e, x, el in months if t >= PRED_FROM]
    day_t = pd.Series(pd.NaT, index=d.index)
    for t, e, x in spans: day_t[(d.index > e) & (d.index <= x)] = t
    d["t"] = day_t; d["確定"] = d["t"].map(closed).fillna(False).astype(int)
    # 同等性（2026-01〜06 vs Q583）
    eq = {}
    if os.path.exists(Q583_DAILY):
        q = pd.read_csv(Q583_DAILY, index_col=0, parse_dates=True)["ls"]
        mine = d[(d["t"] >= EQUIV[0]) & (d["t"] < EQUIV[1])]
        first = mine.groupby("t").apply(lambda g: g.index.min()); mine = mine[~mine.index.isin(first.values)]
        both = pd.concat([mine["ls"].rename("s30"), q.rename("q583")], axis=1, join="inner")
        if len(both):
            diff = (both["s30"] - both["q583"]).abs()
            eq = dict(n_days=int(len(both)), max_abs_diff_bp=round(1e4 * float(diff.max()), 3), mean_abs_diff_bp=round(1e4 * float(diff.mean()), 3),
                      corr=round(float(both["s30"].corr(both["q583"])), 4), 一致=bool(both["s30"].corr(both["q583"]) >= 0.995),   # 2026-10-31: 価格の取り直しで配当調整が少し動くので完全一致ではなく相関で見る（凍結直後は 94 日 差 0.0bp＝記録/run_初回.log）
                      期間=[str(both.index.min().date()), str(both.index.max().date())])
    # フォワード（t ≥ 2026-07-01）
    F = d[d["t"] >= FWD_FIRST_T].copy()
    D = Q.assign(p=pred)
    rows = []; posmap = {}
    for t, e, x in spans:
        if t < FWD_FIRST_T: continue
        g = D[D["t"] == t].dropna(subset=["p"]); dd_ = F[F["t"] == t]
        if not len(g) or not len(dd_): continue
        q_ = max(1, int(len(g) * M.FRAC)); o = np.argsort(g["p"].values)
        L, S = g.iloc[o[-q_:]], g.iloc[o[:q_]]
        pos = pd.concat([L.assign(側="買い"), S.assign(側="売り")])[["sym", "側", "p"]].sort_values(["側", "p"], ascending=[True, False])
        posmap[str(t.date())] = pos
        ic = float(g["p"].corr(g["y"], method="spearman")) if closed[t] and g["y"].notna().sum() > 30 else np.nan
        rows.append(dict(t=str(t.date()), e=str(e.date()), x=str(x.date()) if closed[t] else "", 確定=int(closed[t]), 銘柄数=int(len(g)), 買い=int(len(L)), 売り=int(len(S)),
                         入れ替え率=round(float(dd_["turn"].iloc[0]), 3), 日数=int(len(dd_)), ls_bp_日=round(1e4 * float(dd_["ls"].mean()), 2), ls_累積bp=round(1e4 * float(dd_["ls"].sum()), 1),
                         買いのみ_bp_日=round(1e4 * float(dd_["long_mkt"].mean()), 2), IC=round(ic, 4) if np.isfinite(ic) else None))
    # 判断時の建玉の写し（2026-11-12・修正15・監査B の 7）: 月の建玉は、月が閉じるまで毎回計算し直して上書きされ、判断した時点の建玉が残らなかった。
    #   最初に計算した回に一度だけ 判断時_建玉/ に写し（写した日時とデータの最後は 写した日時.csv に追記）、以後は変えない。記録の計算（日次の損益）には使わない
    jd = os.path.join(a.out, DECIDED_POS); os.makedirs(jd, exist_ok=True); snap_new, snap_diff = [], {}
    for t, pos in posmap.items():
        pf = os.path.join(jd, f"建玉_{_ym(t)}.csv")
        if not os.path.exists(pf):
            pos.to_csv(pf, index=False); snap_new.append(t)
        else:
            a0 = set(map(tuple, pd.read_csv(pf)[["sym", "側"]].astype(str).values)); b0 = set(map(tuple, pos[["sym", "側"]].astype(str).values))
            if a0 != b0: snap_diff[t] = int(len(a0 ^ b0))
    if snap_new:
        lp = os.path.join(jd, "写した日時.csv")
        pd.DataFrame([dict(t=t, 写した日時=_now(), データの最後=str(data_last.date()), 判断日からの日数=int((data_last - pd.Timestamp(t)).days)) for t in snap_new]).to_csv(lp, mode="a", header=not os.path.exists(lp), index=False)
    # 確定した月の固定（2026-11-09・修正11）: 閉じた月は追記だけの表に一度だけ書き、以後はそこから読む
    mon, F, posmap, fixinfo = fix_closed(a.out, rows, F, posmap)
    if snap_new: fixed_save_hashes(a.out)                     # 修正15: 新しく写した判断時の建玉も見張りの控えに入れる
    fixinfo["判断時の建玉"] = {"今回写した月": snap_new, "判断時から入れ替わった銘柄×側（記述）": snap_diff}
    for t, pos in posmap.items(): pos.to_csv(os.path.join(a.out, f"建玉_{_ym(t)}.csv"), index=False)
    mon.to_csv(os.path.join(a.out, "monthly.csv"), index=False)
    F.to_csv(os.path.join(a.out, "daily.csv")); d.to_csv(os.path.join(a.out, "daily_since_2025-12.csv"))
    closed_m = mon[mon["確定"] == 1] if len(mon) else mon
    ics = closed_m["IC"].dropna() if len(closed_m) else pd.Series(dtype=float)
    Fc = F[F["確定"] == 1]; cum = Fc["ls"].cumsum(); maxdd = float((cum - cum.cummax()).min()) if len(cum) else 0.0
    st = {"更新": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "データの最後": str(data_last.date()), "凍結": {"凍結日": H.get("凍結日"), "学習の規則": H.get("学習の規則"), "学習行数": H.get("学習行数")},
          "記録月数（確定）": int(len(closed_m)), "未確定の月": [r["t"] for r in rows if not r["確定"]],
          "IC平均": round(float(ics.mean()), 4) if len(ics) else None, "IC_t": round(float(ics.mean() / ics.std(ddof=1) * np.sqrt(len(ics))), 2) if len(ics) >= 2 and ics.std(ddof=1) > 0 else None,
          "平均bp_日（確定）": round(1e4 * float(Fc["ls"].mean()), 2) if len(Fc) else None, "累計bp（確定）": round(1e4 * float(Fc["ls"].sum()), 1) if len(Fc) else None,
          "最大下落（累積・単純和）": round(maxdd, 4), "停止線": STOP_DD, "停止": [f"最大下落 {maxdd:.3f}（停止線 {STOP_DD}）"] if maxdd <= STOP_DD else [],
          "合否の主": "12 か月で IC t ≥ 2（Q583 と同じ）", "同等性（2026-01〜06 vs Q583）": eq, "確定の固定": fixinfo,
          "次の判断日": str((data_last + pd.offsets.MonthEnd(0)).date()) if data_last != data_last + pd.offsets.MonthEnd(0) else str((data_last + pd.offsets.MonthEnd(1)).date()),
          "秒": round(time.time() - t0)}
    json.dump(st, open(os.path.join(a.out, "状態.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    print(json.dumps(st, ensure_ascii=False, indent=1, default=str)); print(mon.to_string(index=False) if len(mon) else "（記録する月はまだ無い）")
    if st["停止"]: print("★ 停止条件に達した"); sys.exit(3)


if __name__ == "__main__":
    main()
