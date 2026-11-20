# -*- coding: utf-8 -*-
"""S68（暗号資産の永久先物の横断モメンタム・週次 L/S）の記録のフォワード（注文なし）。事前登録 Q739・Q740、taichi「入れる」2026-11-16。
- 定義は Q739 の主と同じ: 毎週月曜 UTC 0 時に、前の日曜までの日足で、直近 30 日すべてに足がある銘柄の平均売買代金（出来高×終値）の上位 30、
  過去 28 日のリターン（日曜の終値 ÷ 28 日前の終値 − 1）の上位 6 を買い・下位 6 を売る（各 1/12、名目の合計 1）。約定は月曜の始値。1 週間持つ。
  日次の変化率: 月曜は 始値→終値、それ以外は 前日終値→終値。足が無くなった銘柄はその後 0。資金調達は実際の率を日ごとに合算（買いは払い・売りは受け取り）。
  売買コストは片道 0.10% × 入れ替えた名目（前週の重みとの差の絶対値の和）を週の初日に計上。
- 違い（記述）: 検証は候補を「全期間で日足 60 本以上」に絞っていた（先の情報）。ここは「直近 30 日すべてに足がある」だけ（検証で実際に効いていたのはこちら）。
  銘柄の一覧は取引所の今の一覧（USDT・永久・COIN・取引中）。test_同等性.py で検証の週と突き合わせる。
- データ: Binance の公開 API（fapi.binance.com・キー不要）。注文は出さない。
- 記録（追記だけ・前の行は書き換えない）: 記録/判断時_建玉.csv（判断の時点で書く）・記録/確定_weeks.csv・記録/daily.csv・記録/状態.json。
- 停止: 累計の損益（名目 1 あたりの和）の最高値からの下落が −1.05 を超えたら（封印期間 Q740 の最悪 −0.698 × 1.5）。標準の 3 か月 PF < 0.95 は当てない
  （Q739＋Q740 の系列で 12 か月以内に 97% 当たる・Q728 と同じ理由・Claude 方針 2026-11-16）。停止したら記録を止める。
- 終了コード: 0 正常・2 取得が途中（次の回に続き）・3 停止条件に達した（その回だけ）・5 凍結のハッシュが違う・1 例外。
使い方: python3 forward_s68.py [--now ISO] [--out DIR]
"""
import argparse, datetime as dt, hashlib, json, os, sys, time, urllib.request, urllib.parse
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
START = pd.Timestamp("2026-11-23 00:00:00", tz="UTC")       # 凍結（入れた後の最初の月曜 UTC 0 時）
TOPN, NSIDE, LOOK, WINDOW = 30, 6, 28, 30
COST = 0.0010
STOP_DD = -1.05
API = "https://fapi.binance.com"
WCOLS = ["week", "gross", "funding", "cost", "net", "turnover", "cum"]
DCOLS = ["day", "gross", "funding", "cost", "net", "cum"]
PCOLS = ["week", "recorded_at", "n_universe", "long", "short", "universe", "code_sha"]


def sha(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()


def get(path, **q):
    u = f"{API}{path}?{urllib.parse.urlencode(q)}"
    for k in range(4):
        try:
            return json.loads(urllib.request.urlopen(u, timeout=30).read())
        except Exception:
            if k == 3: raise
            time.sleep(2 + 3 * k)


def klines(sym, start=None, end=None, limit=70):
    q = dict(symbol=sym, interval="1d", limit=limit)
    if start is not None: q["startTime"] = int(start.timestamp() * 1000)
    if end is not None: q["endTime"] = int(end.timestamp() * 1000) - 1
    r = get("/fapi/v1/klines", **q)
    if not r: return pd.DataFrame(columns=["open", "close", "volume"])
    d = pd.DataFrame([x[:6] for x in r], columns=["t", "open", "high", "low", "close", "volume"])
    d.index = pd.to_datetime(d["t"], unit="ms", utc=True).dt.normalize()
    return d[["open", "close", "volume"]].astype(float)


def funding(sym, start, end):
    r = get("/fapi/v1/fundingRate", symbol=sym, startTime=int(start.timestamp() * 1000), endTime=int(end.timestamp() * 1000) - 1, limit=1000)
    if not r: return pd.Series(dtype=float)
    f = pd.DataFrame(r); t = pd.to_datetime(f["fundingTime"].astype("int64"), unit="ms", utc=True).dt.normalize()
    return f["fundingRate"].astype(float).groupby(pd.DatetimeIndex(t)).sum()   # 時刻帯（UTC）を保つ


def decide(C, V, D, cand):
    """D（月曜）の建て方。C・V は日付 × 銘柄（D より前の日だけ使う）。cand は候補の銘柄。返り値: 母集団・買い・売り・合図"""
    days = pd.date_range(D - pd.Timedelta(days=WINDOW), D - pd.Timedelta(days=1), freq="D", tz="UTC")
    Cw, Vw = C.reindex(days)[cand], V.reindex(days)[cand]
    full = Cw.notna().all() & Vw.notna().all()
    full = full[full].index.tolist()
    if len(full) < 2 * NSIDE: return None
    adv = (Vw[full] * Cw[full]).mean()
    U = adv.sort_values(ascending=False, kind="stable").index[:TOPN].tolist()
    last, past = C.loc[D - pd.Timedelta(days=1), U], C.loc[D - pd.Timedelta(days=1 + LOOK), U]
    sig = (last / past - 1)
    order = sig.sort_values(kind="stable").index.tolist()
    return dict(U=U, long=order[-NSIDE:], short=order[:NSIDE], sig=sig)


def settle(C, O, Fd, D, longs, shorts, prev_w):
    """D から 7 日の日次の損益（検証と同じ式）。C・O・Fd は日付 × 銘柄。prev_w は前週の重み（銘柄→重み・前週に足が無くなった銘柄は 0 とみなす）"""
    w = {s: 0.5 / NSIDE for s in longs}; w.update({s: -0.5 / NSIDE for s in shorts})
    sun = D - pd.Timedelta(days=1)
    prev_eff = {s: v for s, v in prev_w.items() if s in C.columns and sun in C.index and pd.notna(C.at[sun, s])}
    names = set(w) | set(prev_eff)
    turn = sum(abs(w.get(s, 0.0) - prev_eff.get(s, 0.0)) for s in names); cost = COST * turn
    rows = []
    for i in range(7):
        d = D + pd.Timedelta(days=i); g = f = 0.0
        for s, x in w.items():
            c = C.at[d, s] if d in C.index else np.nan
            if pd.isna(c): continue                                        # 足が無い日は 0（最後の終値で閉じた扱い）
            if i == 0: r = c / O.at[d, s] - 1
            else:
                p = C.at[d - pd.Timedelta(days=1), s] if (d - pd.Timedelta(days=1)) in C.index else np.nan
                r = (c / p - 1) if pd.notna(p) else 0.0
            g += x * r
            fr = Fd.at[d, s] if (d in Fd.index and s in Fd.columns and pd.notna(Fd.at[d, s])) else 0.0
            f -= x * fr
        rows.append((d, g, f, cost if i == 0 else 0.0))
    return rows, w, turn


def read_csv(p, cols):
    return pd.read_csv(p, dtype=str, keep_default_na=False) if os.path.exists(p) else pd.DataFrame(columns=cols)


def append(p, cols, rows):
    new = not os.path.exists(p)
    with open(p, "a", encoding="utf-8") as fh:
        if new: fh.write(",".join(cols) + "\n")
        for r in rows: pd.DataFrame([r], columns=cols).to_csv(fh, header=False, index=False)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--now", default=None); ap.add_argument("--out", default=os.path.join(HERE, "記録"))
    a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)
    hp = os.path.join(HERE, "凍結", "hashes.json")
    code = sha(os.path.abspath(__file__))
    if os.path.exists(hp) and json.load(open(hp, encoding="utf-8")).get("forward_s68.py") != code:
        print("★ S68: forward_s68.py が凍結のハッシュと違う。記録は止めた"); return 5
    now = pd.Timestamp(a.now) if a.now else pd.Timestamp.now(tz="UTC")
    if now.tzinfo is None: now = now.tz_localize("UTC")
    P, W, Dy, sp = (os.path.join(a.out, f) for f in ("判断時_建玉.csv", "確定_weeks.csv", "daily.csv", "状態.json"))
    st = json.load(open(sp, encoding="utf-8")) if os.path.exists(sp) else {"開始": str(START), "停止": []}
    if st.get("停止"):
        st["メモ"] = "停止済み（記録は止めた）"; st["更新"] = str(now); json.dump(st, open(sp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("S68: 停止済み"); return 0
    for p_, c_ in ((P, PCOLS), (W, WCOLS), (Dy, DCOLS)):                  # 表は最初の回に見出しだけで作る（見張りが「表が無い」にならないように）
        if not os.path.exists(p_): append(p_, c_, [])
    picks, weeks = read_csv(P, PCOLS), read_csv(W, WCOLS)
    rc = 0
    # 1. 判断（まだ書いていない月曜のうち、今より前のもの。判断は前の日曜までの日足だけ）
    mondays = [START + pd.Timedelta(weeks=k) for k in range(0, 520) if START + pd.Timedelta(weeks=k) <= now]
    todo = [D for D in mondays if D.strftime("%Y-%m-%d") not in set(picks["week"])]
    if todo:
        info = get("/fapi/v1/exchangeInfo")
        cand = sorted(x["symbol"] for x in info["symbols"] if x.get("contractType") == "PERPETUAL" and x.get("quoteAsset") == "USDT"
                      and x.get("status") == "TRADING" and x.get("underlyingType") == "COIN")
        for D in todo:
            if D < now - pd.Timedelta(days=6):                              # 1 週間以上遅れた判断は書かない（その週は記録なし・状態に残す）
                st.setdefault("書けなかった週", []).append(D.strftime("%Y-%m-%d")); continue
            C, V = {}, {}
            for s in cand:
                k = klines(s, end=D, limit=WINDOW + 10); C[s] = k["close"]; V[s] = k["volume"]; time.sleep(0.03)
            C, V = pd.DataFrame(C), pd.DataFrame(V)
            if C.empty or (D - pd.Timedelta(days=1)) not in C.index:
                print(f"S68: {D:%Y-%m-%d} の判断に要る日曜の足がまだ無い"); rc = 2; continue
            r = decide(C, V, D, [s for s in cand if s in C.columns])
            if r is None: print(f"S68: {D:%Y-%m-%d} は母集団が 12 未満で見送り"); r = dict(U=[], long=[], short=[], sig=pd.Series(dtype=float))
            sg = r["sig"]
            append(P, PCOLS, [[D.strftime("%Y-%m-%d"), str(now), len(r["U"]), " ".join(f"{s}:{sg[s]:.4f}" for s in r["long"]),
                               " ".join(f"{s}:{sg[s]:.4f}" for s in r["short"]), " ".join(r["U"]), code[:16]]])
            print(f"S68: {D:%Y-%m-%d} 判断を書いた（買い {' '.join(r['long'])}／売り {' '.join(r['short'])}）")
        picks = read_csv(P, PCOLS)
    # 2. 確定（7 日が終わった週のうち、まだ確定していないもの・古い順）
    prev_w = json.loads(st.get("前週の重み", "{}"))
    for _, row in picks.iterrows():
        D = pd.Timestamp(row["week"], tz="UTC")
        if row["week"] in set(weeks["week"]) or now < D + pd.Timedelta(days=7): continue
        longs = [x.split(":")[0] for x in row["long"].split()]; shorts = [x.split(":")[0] for x in row["short"].split()]
        if not longs:
            append(W, WCOLS, [[row["week"], 0, 0, 0, 0, 0, float(weeks["cum"].astype(float).iloc[-1]) if len(weeks) else 0.0]]); weeks = read_csv(W, WCOLS); prev_w = {}; continue
        C, O, F = {}, {}, {}
        for s in set(longs + shorts) | set(prev_w):
            k = klines(s, start=D - pd.Timedelta(days=1), end=D + pd.Timedelta(days=7), limit=10); C[s] = k["close"]; O[s] = k["open"]
            F[s] = funding(s, D, D + pd.Timedelta(days=7)) if s in longs + shorts else pd.Series(dtype=float); time.sleep(0.05)
        C, O, F = pd.DataFrame(C), pd.DataFrame(O), pd.DataFrame(F)
        last = D + pd.Timedelta(days=6)
        alive_last = [s for s in longs + shorts if s in C.columns and C[s].last_valid_index() is not None]
        if any(C[s].last_valid_index() < last for s in alive_last) and now < D + pd.Timedelta(days=9):
            print(f"S68: {row['week']} の足が最後まで無い銘柄がある（取得の遅れか廃止）。2 日待つ"); rc = 2; break
        rows, w, turn = settle(C, O, F, D, longs, shorts, prev_w)
        base = float(weeks["cum"].astype(float).iloc[-1]) if len(weeks) else 0.0
        g, f, c = sum(x[1] for x in rows), sum(x[2] for x in rows), rows[0][3]
        dold = read_csv(Dy, DCOLS); dbase = float(dold["cum"].astype(float).iloc[-1]) if len(dold) else 0.0
        drows, cum = [], dbase
        for d, gg, ff, cc in rows:
            cum += gg + ff - cc; drows.append([d.strftime("%Y-%m-%d"), gg, ff, cc, gg + ff - cc, cum])
        append(Dy, DCOLS, drows)
        append(W, WCOLS, [[row["week"], g, f, c, g + f - c, turn, base + g + f - c]])
        weeks = read_csv(W, WCOLS); prev_w = w
        print(f"S68: {row['week']} を確定 net {1e4 * (g + f - c):+.1f}bp（価格 {1e4 * g:+.1f}・資金調達 {1e4 * f:+.1f}・売買 {-1e4 * c:.1f}）")
    st["前週の重み"] = json.dumps(prev_w)
    # 3. 停止の判定（日次の累計の最高値からの下落）
    dd = read_csv(Dy, DCOLS)
    if len(dd):
        cum = dd["cum"].astype(float); m = float((cum - np.maximum(cum.cummax(), 0.0)).min())
        st.update({"確定の週": int(len(weeks)), "通算": float(cum.iloc[-1]), "最高値から（最悪）": m})
        if m <= STOP_DD:
            st["停止"].append(f"{now:%Y-%m-%d} 最高値からの下落 {m:.3f} ≤ {STOP_DD}"); rc = 3
            print(f"★ S68: 停止条件に達した（{m:.3f}）")
    st["更新"] = str(now); json.dump(st, open(sp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return rc


if __name__ == "__main__":
    try: sys.exit(main())
    except Exception as e:
        print(f"S68: 例外 {e.__class__.__name__}: {e}"); sys.exit(1)
