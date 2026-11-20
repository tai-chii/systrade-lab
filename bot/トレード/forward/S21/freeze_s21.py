# -*- coding: utf-8 -*-
"""S21 候補形（Q533 D2＋Q534 E1）を学習して凍結する。学習は 15 銘柄（円クロス 4 本は学習に入れない＝検証どおり）。週末前決済のラベル（Q533 D2）。
2026-10-27 追記（運用規程 §4・Q546）: 毎年 10-01 に、その日までの全データで同じ手順で学習し直す。年度 Y のモデルは 凍結_<Y>/
（2026 年度だけは既存の 凍結/）。学習の手順・ハイパーパラメータ・銘柄は 2026 年度と同じで、変えるのは学習の終わりだけ。
出力: <out>/model_a{0..5}.txt・features.json・config.json・hashes.json（作った後は触らない）
使い方:
  python3 freeze_s21.py                 2026 年度の凍結（既存。既に hashes.json があれば止まる）
  python3 freeze_s21.py --auto          いまの年度のモデルが無く、9 月末までのデータがそろっていれば作る（run_forward.sh が毎日呼ぶ）
  python3 freeze_s21.py --year Y [--out DIR]   年度 Y のモデルを作る（手で作り直すとき・試験用）"""
import argparse, os, sys, time, json, shutil
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import common as C
import pandas as pd
import kensho_s21_h1_ml_rr_q515 as K
import kensho_s21d_relthr_wf_q519 as Q
import kensho_s21f_newjpy_q524 as J
import kensho_s21_noweekend_q533 as Z

HERE = os.path.dirname(os.path.abspath(__file__))
FIRST_FY = 2026
MAX_LAG_DAYS = 4          # 9 月末の最後の足（週末なら金曜）からこの日数以内までデータがあれば「そろった」とみなす


def fy_start(Y):
    return pd.Timestamp(f"{Y}-10-01", tz="UTC")


def fiscal_year(ts):
    ts = pd.Timestamp(ts); return ts.year if ts.month >= 10 else ts.year - 1


def model_dir(Y):
    return os.path.join(HERE, "凍結") if Y <= FIRST_FY else os.path.join(HERE, f"凍結_{Y}")


def merged_h1(dst):
    """検証用の履歴（market_data/H1・〜2026-09）とフォワード用（market_data_forward/H1・2026-05〜）を時刻でつないだ 15 銘柄の parquet を dst に書く。
    重なる期間は同じ Dukascopy の値（2026-10-27 に 3 銘柄で差 0 を確認）。重なりはフォワード側を残す。"""
    os.makedirs(dst, exist_ok=True); last = {}
    for s in C.SYMS15:
        parts = [pd.read_parquet(p) for p in [os.path.join(C.H1_HIST, f"{s}.parquet"), os.path.join(C.FWD_DATA, "H1", f"{s}.parquet")] if os.path.exists(p)]
        d = pd.concat(parts).drop_duplicates("time", keep="last").sort_values("time").reset_index(drop=True)
        d.to_parquet(os.path.join(dst, f"{s}.parquet"), index=False); last[s] = d["time"].iloc[-1]
    return last


def freeze(train_end, out, h1dir):
    os.makedirs(out, exist_ok=True)
    if os.path.exists(os.path.join(out, "hashes.json")):
        sys.exit(f"既に凍結済み（{out}/hashes.json がある）。作り直さない。")
    t0 = time.time(); dataw = {}
    for s in C.SYMS15:
        o = J.make(K.load(h1dir, s), s); Rw, Xw = Z.labels_wk(o["d"], s)
        dataw[s] = dict(time=o["time"], R=Rw, X=Xw, F=o["F"]); del o
        print(f"  {s} 準備 {time.time()-t0:.0f}s", flush=True)
    models, ntr = Q.train_window(dataw, train_end, None)
    feats = list(dataw[C.SYMS15[0]]["F"].columns)
    for a, m in enumerate(models):
        m.booster_.save_model(os.path.join(out, f"model_a{a}.txt"))
    C.write_json(os.path.join(out, "features.json"), feats)
    cfg = dict(strategy="S21 候補形 = Q533 D2（週末前決済で学習・週末前に決済）＋ Q534 E1（再開後 1 本目は入らない）",
               frozen_at=time.strftime("%Y-%m-%d %H:%M:%S %Z"), train_end=str(train_end), train_rows=int(ntr), train_syms=C.SYMS15,
               trade_syms=C.SYMS19, forward_start=C.FORWARD_START, actions=[list(x) for x in K.ACTIONS], k_atr=K.K_ATR, horizon_bars=K.H,
               week_cap=K.WEEK_CAP, one_position_per_symbol=True, threshold="直近 28 暦日（20 日×1.4）の 15 銘柄プール予測最大値の 90 パーセンタイル（J.thr_series）",
               reopen_block_bars=1, weekend_close="次の足まで 24 時間以上空く足の終値で決済", hold_rate=K.HOLD_RATE, lgb_params=K.LGB_PARAMS, seed=K.SEED,
               lightgbm_version=__import__("lightgbm").__version__, pandas_version=pd.__version__, elapsed_s=round(time.time() - t0),
               fiscal_year=fiscal_year(train_end), applies_to=f"{train_end.date()} 〜 {fy_start(fiscal_year(train_end) + 1).date()} の判断", h1_source=h1dir)
    C.write_json(os.path.join(out, "config.json"), cfg)
    code = [os.path.join(C.S21_CODE, f) for f in ["kensho_s21_h1_ml_rr_q515.py", "kensho_s21d_relthr_wf_q519.py", "kensho_s21f_newjpy_q524.py",
                                                   "kensho_s21f_mtf_wf_q521.py", "kensho_s21_noweekend_q533.py", "kensho_s21_reopen_q534.py",
                                                   "kensho_s21_walkforward_q518.py"]]
    hashes = {os.path.basename(p): C.sha256(p) for p in [os.path.join(out, f"model_a{a}.txt") for a in range(6)] + [os.path.join(out, "features.json"), os.path.join(out, "config.json"), os.path.abspath(__file__)] + code}
    C.write_json(os.path.join(out, "hashes.json"), hashes)
    print(f"凍結 完了 {out} 学習行 {ntr:,} {time.time()-t0:.0f}s", flush=True)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--auto", action="store_true"); ap.add_argument("--year", type=int); ap.add_argument("--out")
    ap.add_argument("--now", help="試験用: いまの時刻（UTC・ISO）")
    a = ap.parse_args()
    if not a.auto and a.year is None:                       # 2026 年度（既存の挙動のまま）
        return freeze(fy_start(FIRST_FY), model_dir(FIRST_FY), C.H1_HIST)
    Y = a.year if a.year is not None else fiscal_year(pd.Timestamp(a.now) if a.now else pd.Timestamp.now(tz="UTC"))
    out = a.out or model_dir(Y)
    if a.auto and (Y <= FIRST_FY or os.path.exists(os.path.join(out, "hashes.json"))):
        print(f"  年度 {Y} のモデルはある（{out}）"); return
    tmp = os.path.join(C.WS, "作業層", "大容量", f"_freeze_h1_{Y}")
    last = merged_h1(tmp); need = fy_start(Y) - pd.Timedelta(days=MAX_LAG_DAYS)
    short = {s: str(t) for s, t in last.items() if t < need}
    if short:
        msg = f"年度 {Y} の学習に要る 9 月末までのデータがそろっていない: {short}"
        if a.auto:
            print("  " + msg + "（次の周回で再び試す）"); shutil.rmtree(tmp, ignore_errors=True); sys.exit(5)
        sys.exit(msg)
    try:
        freeze(fy_start(Y), out, tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
