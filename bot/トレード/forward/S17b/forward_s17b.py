# -*- coding: utf-8 -*-
"""S17b-F（指数 8 本の買い持ち・XM の先物 CFD の形）の観察枠の記録（日次・注文なし）。事前登録 Q729。
置き場（入れた後）: 検証/トレード/forward/S17b/forward_s17b.py（`..` の common.py・fetch_forward.py を使う）
- データ: Dukascopy の Bid。US500・USTECH・GER40・JPN225 は S21 の取得（fetch_forward.py）の H1 をそのまま読む。
  US30・UK100・FRA40・SUI20 はこの台本が fetch_forward.py と同じ部品（日ごとの 1 分足）で開始の 7 日前から Bid だけ取り、
  S17b 専用のフォルダ（<data>/H1_s17b/）に置く（修正18c・18d。19 銘柄の H1 のフォルダには書かない）。
- 日足: UTC の暦日の最後の H1 の終値（日曜の足・高値＝安値の日を除く）。Q725 の fe_core.load_d1 と同じ作り。
- 損益（名目 1 倍・その通貨建てのリターン）: その日に値のある銘柄の等金額の平均リターン − 保有コスト F の平均 / 252。
  F = max(政策金利, 0) + 0.5% + ロール（往復 3 bp × 年 4 回・FRA40 は年 12 回）。政策金利は _データ/raw/rates の前日までの値（無ければ最後の値）。
  注意: 金利の表は 2026-10-13 で止まっていて、S44・S53 の依存の控えに入っているので更新しない。観察の間の F は 10-13 の金利のまま（事前登録 Q729 の追記）。
- 確定する日: 8 本すべてのデータがある最後の日まで（取得が遅れた銘柄があれば、その日以降は次の回に回す）。
  記録は追記だけ: 前の回までに書いた日は計算し直さず、ファイルの末尾に足すだけ。
- 終了コード: 0 正常・2 追加 4 本の取得が途中・3 停止条件に達した（その回だけ）・4 データが古い（8 本そろった最後の日が 4 営業日より前）・1 例外。
- 停止: 最高値から −28%（名目 1 倍。ホールドアウト 2024-07〜2026-06 の最悪 −18.8% × 1.5。taichi 承認 2026-11-14「27 入れて」）。3 か月の PF の停止は当てない（Q728）。
  停止したら記録を止める（次の回からは何も足さずに終了コード 0。状態.json の「停止」は残す）。
使い方: python3 forward_s17b.py [--start ISO] [--out DIR] [--data DIR] [--no-fetch] [--since YYYY-MM-DD] [--budget 秒]
"""
import argparse, datetime as dt, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); FWD = os.path.join(HERE, "..")
if not os.path.exists(os.path.join(FWD, "common.py")):                       # パッチの置き場から試すとき
    FWD = os.path.join(HERE, "..", "..", "..", "..", "トレード", "forward")
sys.path.insert(0, os.path.abspath(FWD))
import common as C
import numpy as np, pandas as pd

SYMS = {"US500": "USD", "USTECH": "USD", "US30": "USD", "GER40": "EUR", "JPN225": "JPY", "UK100": "GBP", "FRA40": "EUR", "SUI20": "CHF"}
# Dukascopy のコードは _データ/fetch/fetch_dukascopy_d1.py と同じ。値の範囲は桁の判定用で、上下の比を 10 未満に保って広げた（修正18d・観察の 12 か月で超えないように）
EXTRA = [("US30", "USA30IDXUSD", (20000, 150000)), ("UK100", "GBRIDXGBP", (5000, 30000)),
         ("FRA40", "FRAIDXEUR", (4000, 25000)), ("SUI20", "CHEIDXCHF", (6000, 40000))]
EXTRA_NAMES = [x[0] for x in EXTRA]
ROLLS = {s: 4 for s in SYMS}; ROLLS["FRA40"] = 12
ROLL_BP, FUND_ADD = 3.0, 0.005
STOP_DD = -0.28
STALE_BDAYS = 4
START = "2026-11-16 00:00:00+00:00"   # 凍結（2026-11-14 に入れた後の最初の月曜 00:00 UTC・事前登録 Q729）
RATES = os.path.join(C.KENSHO, "_データ", "raw", "rates")
COLS = ["day", "n", "gross", "cost", "net", "cum"]


def h1_path(data_dir, sym):
    return os.path.join(data_dir, "H1_s17b" if sym in EXTRA_NAMES else "H1", f"{sym}.parquet")


def missing_days(raw, name, since, today):
    """since から昨日（UTC）までで、日ごとの 1 分足のキャッシュ（_raw/<銘柄>/day/BID_*.bi5）がまだ無い日の数（修正18f・取る順番に使う）。"""
    n, d = 0, since
    while d < today:
        n += not os.path.exists(os.path.join(raw, name, "day", f"BID_{d:%Y%m%d}.bi5")); d += dt.timedelta(days=1)
    return n


def fetch_extra(data_dir, since, budget):
    """US30・UK100・FRA40・SUI20 の Bid の H1 を、since の日から昨日（UTC）まで日ごとの 1 分足で取る（キャッシュは fetch_forward.py と同じ場所）。
    budget 秒を超えたら止めて残りを次の回に回す。1 ファイルの取得は最悪 10 分ほどかかるので、budget は run_forward.sh の打ち切り 1200 秒の半分以下にする。
    銘柄ごとに例外を受け止め、失敗した銘柄の名前を返す（修正18d）。"""
    import time
    import fetch_forward as FF, fetch_dukascopy as FD
    FF.RAW = os.path.join(data_dir, "_raw"); out = os.path.join(data_dir, "H1_s17b"); os.makedirs(out, exist_ok=True)
    today = dt.datetime.now(dt.timezone.utc).date(); t0 = time.time(); bad = []
    for name, code, rng in sorted(EXTRA, key=lambda x: -missing_days(FF.RAW, x[0], since, today)):   # 修正18f: 取れていない日の多い銘柄から（同じなら US30→UK100→FRA40→SUI20）
        try:
            rows = []; d = since; ok = True
            while d < today:
                if time.time() - t0 > budget:
                    ok = False; break
                p = os.path.join(FF.RAW, name, "day", f"BID_{d:%Y%m%d}.bi5")
                url = f"https://datafeed.dukascopy.com/datafeed/{code}/{d.year}/{d.month - 1:02d}/{d.day:02d}/BID_candles_min_1.bi5"
                raw = FF.get_cached(p, url, cache_empty=(today - d).days > FF.RECENT_DAYS)
                if raw is None:
                    ok = False; break
                rows.extend(FF.to_hour(FF.decode_day(raw, d)))
                d += dt.timedelta(days=1)
            if not ok or not rows:
                bad.append(name); continue
            df = pd.DataFrame(rows, columns=["time", "open", "high", "low", "close", "volume"]).drop_duplicates("time").sort_values("time")
            f = FD.detect_factor(df["close"].tail(2000).tolist(), rng)
            for c in ("open", "high", "low", "close"):
                df[c] = df[c] / f
            df = df[df["volume"] > 0]
            df.to_parquet(os.path.join(out, f"{name}.parquet"), index=False)
        except Exception as e:                                             # 取得の想定外の失敗は、その銘柄だけ次の回に回す
            print(f"  {name}: 取得の例外 {e.__class__.__name__}: {str(e)[:120]}"); bad.append(name)
    return bad


def daily(data_dir, sym):
    h = pd.read_parquet(h1_path(data_dir, sym), columns=["time", "high", "low", "close"])
    h["time"] = pd.to_datetime(h["time"], utc=True); h["d"] = h["time"].dt.floor("D")
    g = h.groupby("d").agg(high=("high", "max"), low=("low", "min"), close=("close", "last"))
    g = g[(g.index.weekday != 6) & (g["high"] != g["low"])]
    return g["close"]


def policy(ccy, days):
    p = pd.read_csv(os.path.join(RATES, f"policy_{ccy}.csv"), parse_dates=["date"]).dropna().set_index("date")["policy_rate_pct"] / 100
    p.index = p.index.tz_localize("UTC")
    full = p.reindex(pd.date_range(p.index.min(), max(days.max(), p.index.max()), freq="D", tz="UTC")).ffill().shift(1)
    return full.reindex(days).clip(lower=0)


def write_state(path, st):
    st["更新"] = dt.datetime.now().strftime("%Y-%m-%d %H:%M"); C.write_json(path, st)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--start", default=START); ap.add_argument("--out", default=os.path.join(HERE, "記録"))
    ap.add_argument("--data", default=C.FWD_DATA); ap.add_argument("--no-fetch", action="store_true")
    ap.add_argument("--since", default=None, help="取得の始まりの日（既定は開始の 7 日前）"); ap.add_argument("--budget", type=float, default=450, help="取得に使う秒数の上限（修正18e: 500→300。上限は新しいファイルを取り始めないだけで、取得中の 1 ファイルは最悪 約 580 秒かかるため。修正18f: 300→450。300 秒では 1 日に約 5 本しか取れず、毎日増える 4 本との差が 1 本で、遅れを取り戻せない。最悪 450＋580 ≒ 1030 秒で打ち切り 1200 秒の内）")
    ap.add_argument("--today", default=None, help="試験用: 今日の日付（データが古いかの判定）")
    a = ap.parse_args(); os.makedirs(a.out, exist_ok=True); start = pd.Timestamp(a.start)
    dp = os.path.join(a.out, "daily.csv"); sp = os.path.join(a.out, "状態.json")
    if not os.path.exists(dp):                                           # 修正18d: 取得の前に表を作る（取得で落ちても見張りが「表が無い」にならない）
        pd.DataFrame(columns=COLS).to_csv(dp, index=False)
    prev = json.load(open(sp, encoding="utf-8")) if os.path.exists(sp) else {}
    if prev.get("停止"):                                                 # 修正18d: 停止したら記録を止める（毎日 ★ を出し直さない）
        prev["メモ"] = "停止済み（記録は止めた・事前登録 Q729）"; write_state(sp, prev); print("S17b: 停止済み。記録は止めた"); return 0
    if not prev:
        write_state(sp, {"開始": str(start), "記録日数": 0, "通算": 0.0, "最高値から": 0.0, "停止": []})
    since = pd.Timestamp(a.since).date() if a.since else (start - pd.Timedelta(days=7)).date()
    bad = [] if a.no_fetch else fetch_extra(a.data, since, a.budget)
    today = pd.Timestamp(a.today).date() if a.today else dt.datetime.now(dt.timezone.utc).date()
    miss = [s for s in SYMS if not os.path.exists(h1_path(a.data, s))]
    if miss:                                                             # 追加の銘柄の H1 がまだ無い（初回の取得が途中）: 表は消さずに次の回へ
        st = json.load(open(sp, encoding="utf-8")); st.update({"取得失敗": sorted(set(bad) | set(miss)), "H1 が無い銘柄": miss})
        write_state(sp, st)
        if today > (start + pd.Timedelta(days=7)).date():                  # 修正18e: 開始の 7 日後を過ぎても H1 ができないなら、黙って 2 を返し続けず ★（終了コード 4）
            print(f"★ S17b: 開始の 7 日後を過ぎても H1 が無い銘柄 {miss}（取得が通らない）"); return 4
        print(f"S17b: H1 が無い銘柄 {miss}（初回の取得が途中）。記録は次の回で続ける"); return 2
    closes = {s: daily(a.data, s) for s in SYMS}
    last_day = min(c.index.max() for c in closes.values())          # 8 本そろった最後の日
    old = pd.read_csv(dp, dtype=str, keep_default_na=False)           # 修正18d: 前の行は文字列のまま読む（書き戻さない・末尾に足すだけ）
    done = pd.Timestamp(old["day"].iloc[-1], tz="UTC") if len(old) else None
    R = pd.DataFrame({s: c.pct_change() for s, c in closes.items()})   # 銘柄ごとに自分の前の日からのリターン
    R = R[(R.index >= start.floor("D")) & (R.index <= last_day)]
    if done is not None:
        R = R[R.index > done]                                          # 追記だけ（前の回までの行は計算し直さない）
    num = lambda s: pd.to_numeric(s, errors="coerce") if len(s) else pd.Series(dtype=float)
    net_old = num(old["net"])
    new = pd.DataFrame(columns=COLS)
    if len(R):
        days = R.index
        F = pd.DataFrame({s: policy(c, days) + FUND_ADD + ROLLS[s] * ROLL_BP / 1e4 for s, c in SYMS.items()})
        have = R.notna()
        gross = R.mean(axis=1, skipna=True); cost = F.where(have).mean(axis=1, skipna=True) / 252; net_new = (gross - cost).fillna(0.0)
        base = float(net_old.sum()) if len(old) else 0.0
        new = pd.DataFrame({"day": days.strftime("%Y-%m-%d"), "n": have.sum(axis=1).to_numpy(), "gross": gross.to_numpy(), "cost": cost.to_numpy(),
                            "net": net_new.to_numpy(), "cum": base + net_new.cumsum().to_numpy()})
        with open(dp, "a", encoding="utf-8") as f:                         # 追記だけ（前の行は触らない）
            new[COLS].to_csv(f, header=False, index=False)
    net = pd.concat([net_old, num(new["net"])], ignore_index=True) if len(new) else net_old
    allday = list(old["day"]) + list(new["day"])
    costs = pd.concat([num(old["cost"]), num(new["cost"])], ignore_index=True)
    ns = pd.concat([num(old["n"]), num(new["n"])], ignore_index=True)
    n = len(net); cum = net.cumsum(); dd = cum - cum.cummax().clip(lower=0) if n else pd.Series(dtype=float)
    stops = []
    if n and dd.min() <= STOP_DD:
        stops.append(f"最高値から {dd.min():.1%}（線 {STOP_DD:.0%}）・{allday[int(np.argmin(dd.to_numpy()))]}")
    today = pd.Timestamp(a.today).date() if a.today else dt.datetime.now(dt.timezone.utc).date()
    lag = int(np.busday_count(last_day.date(), today)) if today > last_day.date() else 0
    stale = today > (start + pd.Timedelta(days=7)).date() and lag > STALE_BDAYS
    st = {"開始": str(start), "データの最後": str(last_day.date()) + ("" if n else "（まだ記録の日が無い）"), "記録日数": int(n),
          "通算": round(float(cum.iloc[-1] * 100), 3) if n else 0.0, "最高値から": round(float(dd.iloc[-1] * 100), 3) if n else 0.0,
          "最大下落": round(float(dd.min() * 100), 3) if n else 0.0, "日次平均_bp": round(float(net.mean() * 1e4), 3) if n else None,
          "年率_pct（記述）": round(float(net.mean() * 252 * 100), 2) if n else None,
          "Sharpe（記述）": (round(float(net.mean() / net.std(ddof=1) * np.sqrt(252)), 2) if n > 20 else None),
          "保有コストの年率_pct（平均）": round(float(costs.mean() * 252 * 100), 3) if n else None,
          "8 本そろわなかった日": int((ns < 8).sum()) if n else 0, "停止": stops, "取得失敗": bad, "データの遅れ_営業日": lag,
          "単位": "通算・最高値から・最大下落は百分率（名目 1 倍）", "枠": "観察枠（記録だけ・注文なし・Q729・終わりの日 2027-11-30）",
          "銘柄ごとの最後の日": {s: str(c.index.max().date()) for s, c in closes.items()}}
    write_state(sp, st)
    print(f"S17b: 記録 {n} 日（今回 {len(new)} 日）・通算 {st['通算']:+.2f}%・最高値から {st['最高値から']:+.2f}%・データの最後 {st['データの最後']}" + (f"・取得が途中 {bad}" if bad else ""))
    if stops:
        print("★ S17b 停止:", stops[0]); return 3
    if stale:
        print(f"★ S17b のデータが古い（8 本そろった最後の日 {last_day.date()}・{lag} 営業日遅れ）"); return 4
    return 2 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
