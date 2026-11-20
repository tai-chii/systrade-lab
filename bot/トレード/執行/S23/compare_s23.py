# -*- coding: utf-8 -*-
"""S23 の執行（winnote の台帳）と記録（Binance の始値で入る・出る）の突き合わせ（Mac・読むだけ）。2026-11-18 午後の自走（案）。
点検（Opus）の指摘 5 を受けて、**記録の保有の区間**を軸にする（bot の台帳の行だけを回すと、bot が入らなかった区間が見えないため）。

記録の区間 = 記録の保有が 0→1 になった日 d（その日の終値で決め、次の始値 exec_px[d] で入る）から 1→0 になった日 e（exec_px[e] で出る）まで。
各区間に、同じ銘柄で「判断の日が d」の台帳の行を当てる（無ければ「取りこぼし」）。台帳の行のうち、どの区間にも当たらない行は「記録に無い保有」。
1 区間ごとに:
  記録の率   = exec_px[e] / exec_px[d] − 1 − 往復コスト（BTC 0.04%・ETH 0.15%）
  bot の率   = 約定の出口 / 約定の入口 − 1（業者の値段・スプレッド込み）
  スワップ率 = 台帳のスワップ ÷ 名目（名目が空の取り込みの行は 入口 × ロット × 円換算が無いので空）
  超過コスト = 記録の率 − (bot の率 + スワップ率)   … 正＝bot のほうが損
  入口の遅れ = 台帳の entry_time − 判断の日の締め（21:00 UTC。金曜の判断は日曜 21:00 UTC）
  区間のずれ = bot の出る判断の日が記録の e と違う・手で閉じた（出る判断の日が空）
合図の一致 = 記録の区間の始まりのうち、bot が同じ判断の日に入った割合。
使い方: python compare_s23.py [--ledger lab-ops/trade/winnote/S23/trades.csv] [--h1 market_data_forward/crypto_h1] [--line]
"""
import argparse, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
FWD = os.environ.get("S23_FORWARD_DIR") or os.path.abspath(os.path.join(HERE, "..", "..", "forward"))
sys.path.insert(0, FWD); sys.path.insert(0, os.path.join(FWD, "S23"))
import common as C                                                        # noqa: E402
import numpy as np, pandas as pd                                          # noqa: E402
import run_q529 as R                                                      # noqa: E402

KENSHO = C.KENSHO; L_LOOK = 60


def record_intervals(h1dir, start=None):
    """記録と同じ計算（daily_series・tsmom 60）の保有の区間。{coin: [(d, e or None, exec_d, exec_e)]} と exec の表。"""
    first = (pd.Timestamp(start or C.FORWARD_START) + R.C.SHIFT).tz_convert(None).normalize()
    out, ex = {}, {}
    for c in ("BTC", "ETH"):
        b = R.daily_series(h1dir, c)
        last_h1 = pd.read_parquet(os.path.join(h1dir, f"{c}.parquet"))["time"].max()          # 締まっていない最後の日を落とす（記録の forward_s23.py と同じ・2 回目の点検 10）
        b = b[b["g"] - R.C.SHIFT + pd.Timedelta(days=1) <= last_h1 + pd.Timedelta(hours=1)].reset_index(drop=True)
        days = pd.to_datetime(b["day"]).dt.tz_localize(None) if pd.to_datetime(b["day"]).dt.tz is not None else pd.to_datetime(b["day"])
        pos = R.tsmom(b, L_LOOK); px = b["exec_px"].to_numpy(float); keys = days.dt.strftime("%Y-%m-%d").to_numpy()
        ex[c] = pd.Series(px, index=keys); iv, prev, s = [], 0, None
        for k, dday, p in zip(keys, days, pos):
            if dday < first:                                                    # 記録の始まりより前は持っていない扱い（始まりの日に 1 なら、そこで入る）
                prev = 0; continue
            if p == 1 and prev == 0: s = k
            if p == 0 and prev == 1 and s is not None: iv.append((s, k)); s = None
            prev = p
        if s is not None: iv.append((s, None))
        out[c] = iv
    return out, ex


def day_close(d):
    """判断の日 d の締め（21:00 UTC）の後で入れる最初の時刻。金曜の判断は日曜 21:00 UTC（取引時間の外を飛ばす）。"""
    t = pd.Timestamp(d, tz="UTC") + pd.Timedelta(hours=21)
    return t + pd.Timedelta(days=2) if t.weekday() == 4 else t


def compare(L, h1dir, start=None):
    iv, ex = record_intervals(h1dir, start); rows, used = [], set()
    L = L.copy(); L["_i"] = range(len(L))
    for c, lst in iv.items():
        for d, e in lst:
            inr = L["decision_day"].between(d, e or "9999-12-31", inclusive="left") if e else (L["decision_day"] >= d)   # 区間 [d, e) に判断の日がある最初の行（遅れて入った・入り直し・取り込みも結ぶ・2 回目の点検 2）
            m = L[(L["coin"] == c) & inr & (L["status"] != "void") & ~L["_i"].isin(used)].sort_values("decision_day")
            r = dict(coin=c, 記録_入る日=d, 記録_出る日=e or "", 記録の入口=ex[c].get(d), 記録の出口=ex[c].get(e) if e else np.nan)
            if not len(m):
                rows.append(dict(r, 状態="取りこぼし")); continue
            x = m.iloc[0]; used.add(int(x["_i"]))
            r.update(状態=x["status"], bot_入る日=x["decision_day"], bot_入口=float(x["entry_px"]), bot_出る日=x["exit_decision_day"], 入口の遅れ_h=(pd.Timestamp(x["entry_time"]) - day_close(d)).total_seconds() / 3600)
            r["入口の差"] = float(x["entry_px"]) / r["記録の入口"] - 1 if r["記録の入口"] and np.isfinite(r["記録の入口"]) else np.nan
            if x["status"] == "closed" and x["exit_px"]:
                xp = float(x["exit_px"]); r["bot_出口"] = xp; r["bot_の率"] = xp / float(x["entry_px"]) - 1
                notional = float(x["notional"]) if x["notional"] else np.nan
                r["スワップ率"] = float(x["swap"] or 0) / notional if np.isfinite(notional) and notional else np.nan
                r["区間のずれ"] = "手で閉じた・業者が閉じた" if not x["exit_decision_day"] else ("" if x["exit_decision_day"] == e else f"bot は {x['exit_decision_day']} に出た")
                if x["decision_day"] != d and not r["区間のずれ"]: r["区間のずれ"] = f"bot は {x['decision_day']} の判断で入った（遅れ・入り直し）"
                if e and r["記録の出口"] and np.isfinite(r["記録の出口"]) and not r["区間のずれ"]:
                    r["記録の率"] = r["記録の出口"] / r["記録の入口"] - 1 - 2 * R.HALF[c]
                    r["出口の差"] = 1 - xp / r["記録の出口"]
                    if np.isfinite(r.get("スワップ率", np.nan)): r["超過コスト"] = r["記録の率"] - (r["bot_の率"] + r["スワップ率"])
            rows.append(r)
    for _, x in L[~L["_i"].isin(used) & (L["status"] != "void")].iterrows():
        rows.append(dict(coin=x["coin"], 記録_入る日="", 状態="記録に無い保有", bot_入る日=x["decision_day"], bot_入口=float(x["entry_px"]), note=x["note"]))
    return pd.DataFrame(rows)


def summary(T, since=None):
    """since（最初の bot の entry_time）より後に始まった記録の区間だけで、合図の一致と取りこぼしを数える。"""
    R_ = T[T["記録_入る日"] != ""]
    if since is not None:
        R_ = R_[R_["記録_入る日"].map(lambda d: day_close(d) >= since - pd.Timedelta(hours=1))]
    hit = int((R_["状態"] != "取りこぼし").sum()); miss = int((R_["状態"] == "取りこぼし").sum())
    cl = T[T["超過コスト"].notna()] if "超過コスト" in T else T.iloc[0:0]
    extra = int((T["状態"] == "記録に無い保有").sum()); shift = int(T["区間のずれ"].fillna("").ne("").sum()) if "区間のずれ" in T else 0
    return dict(区間=len(R_), 一致=hit, 取りこぼし=miss, 記録に無い保有=extra, 区間のずれ=shift, 比べた決済=len(cl),
                超過=float(cl["超過コスト"].mean()) if len(cl) else np.nan, 入口=float(cl["入口の差"].mean()) if len(cl) else np.nan,
                出口=float(cl["出口の差"].mean()) if len(cl) else np.nan, スワップ=float(-cl["スワップ率"].mean()) if len(cl) else np.nan,
                遅れ=float(T["入口の遅れ_h"].median()) if "入口の遅れ_h" in T and T["入口の遅れ_h"].notna().any() else np.nan)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", default=os.path.join(KENSHO, "lab-ops", "trade", "winnote", "S23", "trades.csv"))
    ap.add_argument("--h1", default=os.path.join(C.FWD_DATA, "crypto_h1"))
    ap.add_argument("--line", action="store_true", help="状態.md 用の 1 行だけ")
    a = ap.parse_args()
    if not os.path.exists(a.ledger):
        print("S23 執行: 台帳が無い（まだ動かしていない）"); return
    L = pd.read_csv(a.ledger, dtype=str, keep_default_na=False)
    if not len(L):
        print("S23 執行: 台帳 0 行"); return
    T = compare(L, a.h1); since = pd.to_datetime(L["entry_time"], utc=True, errors="coerce").min()
    s = summary(T, since)
    line = (f"S23 執行: 記録の区間 {s['区間']}（bot が同じ日に入った {s['一致']}・取りこぼし {s['取りこぼし']}）・記録に無い保有 {s['記録に無い保有']}・区間のずれ {s['区間のずれ']}"
            + (f"・比べた決済 {s['比べた決済']} 本の超過コスト 平均 {s['超過'] * 100:+.2f}%/本（入口 {s['入口'] * 100:+.2f}%・出口 {s['出口'] * 100:+.2f}%・スワップ {s['スワップ'] * 100:+.2f}%）" if s["比べた決済"] else "")
            + (f"・入口の遅れ 中央 {s['遅れ']:.1f} 時間" if np.isfinite(s["遅れ"]) else ""))
    if a.line:
        print(line); return
    pd.set_option("display.width", 220); pd.set_option("display.max_columns", 30)
    print(T.round(5).to_string(index=False)); print("\n" + line)


if __name__ == "__main__":
    main()
