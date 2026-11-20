#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S30 の仮想フォワード用に、無料層の日本株日足（作業層/大容量/equities_free/jp_daily.parquet）を yfinance で伸ばす（Q586・2026-10-31）。
- 直近 DAYS（既定 450）日ぶんを全銘柄で取り直し、その期間の行を差し替える（調整後終値の遡及修正を 1 配当周期ぶん吸収）。
- 2026-10-31 修正: 差し替えただけだと、窓より古い行が古い調整のまま残り、分割銘柄の継ぎ目に偽の −50% が入った（6036.T・6787.T）。
  窓の最初の重なり 5 日の 新/旧 の中央値を、窓より古い行の OHLC（出来高は 旧/新 側の倍率）に掛けて尺度をそろえる。
- 場中に回しても未確定の足を取り込まない（今日の足は 16:00 JST までは捨てる）。
- 新しいデータの無い銘柄は旧データを残す。継ぎ目の不一致（|新/旧 − 1| > 0.5%）の銘柄数をログに残す。
- 銘柄表は parquet にある銘柄（現構成・生存バイアスはそのまま）。新規上場は足さない。
- 2026-11-03 修正（監査E の 3・4）: 書くのは S30 専用の写し（equities_free/s30/jp_daily.parquet。11-03 に共有のファイルからバイト一致で複写）。検証の共有 jp_daily.parquet は書き換えない。
  200 銘柄の塊を 3 回とも取り損ねたら書かずに終了コード 1（一部の銘柄だけ古いまま黙って通さない。run_forward.sh は印を付けず次の回に取り直す）。
- 2026-11-18 修正21（案・判断待ち 51）: 11-14 の回で 230 銘柄（7.4%）が「新データ無し」のまま書かれ、印も付いた（yfinance が時差の控えの sqlite を
  多数のスレッドで同時に開けず、例外にならずに空の列で返した見立て）。
  ① 時差の控えを S30 専用の場所にする（初回は今の控えを写して、全銘柄の時差を取り直す混み合いを避ける）
  ② 塊の中で取れなかった銘柄は、スレッドなしで 2 回まで取り直す。ただし塊の半分を超えて取れないとき（回数制限・ネットの切れ）は取り直さずに失敗にする（打ち切りの 1 時間を使い切らない）
  ③ 直近 30 日に値のあった銘柄のうち、新しいデータの最後が全体の最後から 3 営業日より古いもの（取れない・途中で切れた）が 1% を超えたら、書かずに終了コード 1
  ④ 書かなかった回も データ更新.jsonl に理由と取れなかった銘柄の全部を残し、要対応.md に ★ の節を 1 つ（未解決の同じ題が無いときだけ）。最後に書けた回から 10 日を超えても ★
  取れた銘柄の計算は前と同じ（同じ入力なら同じ出力を試験で確かめた）。2026-11-18 の別の目の点検の指摘を反映。
使い方: 作業層/venv_equities/bin/python update_prices_s30.py [--days 450] [--dry]"""
import argparse, datetime as dt, json, os, sys, time
import pandas as pd

WS = os.path.expanduser("~/ワークスペース"); OUT = os.path.join(WS, "作業層", "大容量", "equities_free")
P = os.path.join(OUT, "s30", "jp_daily.parquet"); HERE = os.path.dirname(os.path.abspath(__file__))
COLS = ["date", "symbol", "open", "high", "low", "close", "volume"]
MAX_MISSING = 0.01                                                              # 修正21: 直近 30 日に値のあった銘柄のうち、取れない・途中で切れた銘柄の上限（割合）
LIVE_DAYS, LAG_BDAYS, STALE_DAYS = 30, 3, 10
TZ_CACHE = os.path.join(OUT, "s30", ".yf_tz_cache")                             # 修正21: 時差の控えの専用の場所
YOTAIOU = os.environ.get("S30_YOTAIOU") or os.path.abspath(os.path.join(HERE, "..", "..", "..", "自動実行", "要対応.md"))
STAR_T = "S30 の価格の取り直しが通っていない（自動・update_prices_s30.py）"
DRY = [False]                                                                    # --dry の回は jsonl と要対応に書かない


def frames(d, ch):
    """yf.download の結果から、値のある銘柄の行だけを返す（dict 銘柄 → DataFrame）。今の版の行の作り方と同じ。"""
    out = {}
    for s in ch:
        try: x = d[s].dropna(how="all")
        except KeyError: continue
        if not len(x): continue
        x = x.reset_index().rename(columns=str.lower); x["symbol"] = s
        out[s] = x[[c for c in COLS if c in x.columns]]
    return out


def star(body):
    """要対応.md に ★ の節（未解決の同じ題が無いときだけ・run_forward.sh の TODO_STAR と同じ形）。要対応.md が無ければ何もしない。"""
    try:
        if not os.path.exists(YOTAIOU): return
        y = open(YOTAIOU, encoding="utf-8").read(); i = y.find(f"— ★ {STAR_T}")
        while i >= 0:
            if y[i:].split("\n", 2)[1].startswith("- 状態: 未解決"): print("  要対応に同じ未解決の節がある（足さない）", flush=True); return
            i = y.find(f"— ★ {STAR_T}", i + 1)
        with open(YOTAIOU, "a", encoding="utf-8") as f:
            f.write(f"\n## {dt.datetime.now():%Y-%m-%d %H:%M} — ★ {STAR_T}\n- 状態: 未解決\n- {body}\n")
    except Exception as e:
        print("  要対応に書けない:", e, flush=True)


def log_jsonl(info):
    os.makedirs(os.path.join(HERE, "記録"), exist_ok=True)
    with open(os.path.join(HERE, "記録", "データ更新.jsonl"), "a", encoding="utf-8") as f: f.write(json.dumps(info, ensure_ascii=False) + "\n")


def last_written():
    """データ更新.jsonl のうち、書けた回の最後の時刻（無ければ None）。"""
    try:
        t = None
        for ln in open(os.path.join(HERE, "記録", "データ更新.jsonl"), encoding="utf-8"):
            j = json.loads(ln)
            if not j.get("書かなかった"): t = j.get("更新")
        return dt.datetime.strptime(t, "%Y-%m-%d %H:%M") if t else None
    except Exception:
        return None


def give_up(reason, missing, t0, extra=None):
    """書かずに終了コード 1。jsonl に残し、★ を出す（run_forward.sh は印を付けず次の回に取り直す）。"""
    info = {"更新": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "書かなかった": reason, "取れない銘柄の数": len(missing), "取れない銘柄": sorted(missing), "秒": round(time.time() - t0)}
    if extra: info.update(extra)
    print(json.dumps({k: v for k, v in info.items() if k != "取れない銘柄"}, ensure_ascii=False), flush=True)
    if DRY[0]: print("--dry: 書かない（jsonl・要対応にも書かない）"); sys.exit(1)
    log_jsonl(info)
    lw = last_written()
    star(f"{reason}。書かずに終了した（記録は手元の古い価格で続く・印は付けないので次の記録の回に取り直す）。取れない銘柄 {len(missing)}（例 {', '.join(sorted(missing)[:5])}）。"
         f"最後に書けた回 {lw:%Y-%m-%d %H:%M}" if lw else f"{reason}。書かずに終了した。最後に書けた回は記録に無い")
    sys.exit(1)


def main():
    import yfinance as yf, shutil
    try:
        os.makedirs(TZ_CACHE, exist_ok=True)
        old_db = os.path.expanduser("~/Library/Caches/py-yfinance/tkr-tz.db")         # 修正21: 初回は今の控えを写す（全銘柄の時差を一度に取り直す混み合いを避ける・点検 3）
        if not os.path.exists(os.path.join(TZ_CACHE, "tkr-tz.db")) and os.path.exists(old_db): shutil.copy2(old_db, os.path.join(TZ_CACHE, "tkr-tz.db"))
        yf.set_tz_cache_location(TZ_CACHE)
    except Exception as e: print("時差の控えの場所を替えられない（既定のまま）:", e, flush=True)
    lw = last_written()
    if lw and dt.datetime.now() - lw > dt.timedelta(days=STALE_DAYS) and "--dry" not in sys.argv:                # 修正21: 最後に書けた回から 10 日を超えた（取れない日が続いている）
        star(f"最後に価格を書けた回が {lw:%Y-%m-%d %H:%M}（{(dt.datetime.now() - lw).days} 日前）。記録は古い価格で続いている")
    ap = argparse.ArgumentParser(); ap.add_argument("--days", type=int, default=450); ap.add_argument("--dry", action="store_true"); a = ap.parse_args(); DRY[0] = a.dry
    t0 = time.time(); df = pd.read_parquet(P, columns=COLS); df["date"] = pd.to_datetime(df["date"])
    last = df["date"].max(); start = (last - pd.Timedelta(days=a.days)).normalize()
    syms = sorted(df["symbol"].unique()); print(f"旧: {len(df)} 行・{len(syms)} 銘柄・最後 {last.date()}・取り直し {start.date()}〜", flush=True)
    rows = []; failed = []; rescued = 0
    for i in range(0, len(syms), 200):
        ch = syms[i:i + 200]
        for attempt in range(3):
            try:
                d = yf.download(ch, start=str(start.date()), auto_adjust=True, progress=False, threads=True, group_by="ticker"); break
            except Exception as e:
                print("retry", i, e, flush=True); time.sleep(20)
        else:
            failed.append(i); continue
        got = frames(d, ch); miss = [s for s in ch if s not in got]
        if len(miss) > len(ch) / 2:                                             # 修正21: 塊の半分を超えて空＝回数制限・ネットの切れ。取り直さずに失敗（点検 1）
            print(f"  {i}: 塊の {len(miss)}/{len(ch)} 銘柄が空。取り直さずに失敗にする", flush=True); failed.append(i); continue
        for k in range(2):                                                      # 修正21: 取れなかった銘柄はスレッドなしで取り直す（上場廃止は何度でも空なので 2 回まで）
            if not miss: break
            time.sleep(10)
            try:
                d2 = yf.download(miss, start=str(start.date()), auto_adjust=True, progress=False, threads=False, group_by="ticker")
                g2 = frames(d2, miss); got.update(g2); rescued += len(g2); miss = [s for s in miss if s not in g2]
            except Exception as e:
                print("retry(取り直し)", i, e, flush=True)
        rows.extend(got.values())
        print(f"  {i + len(ch)}/{len(syms)} {time.strftime('%H:%M:%S')}" + (f"・取れない {len(miss)}" if miss else ""), flush=True)
    if failed:
        give_up(f"取り損ねた塊 {len(failed)} 個（先頭の番号 {failed}）", [s for i in failed for s in syms[i:i + 200]], t0)
    new =pd.concat(rows, ignore_index=True); new["date"] = pd.to_datetime(new["date"]).dt.tz_localize(None).dt.normalize()
    new = new[new["date"] >= start].dropna(subset=["close"]).drop_duplicates(["date", "symbol"])
    now = dt.datetime.now(); cut = pd.Timestamp(now.date()) + (pd.Timedelta(days=1) if now.hour >= 16 else pd.Timedelta(0))   # 16:00 前は今日の足を捨てる（Mac は JST）
    n0 = len(new); new = new[new["date"] < cut]; dropped_today = n0 - len(new)
    # 継ぎ目の点検: 旧と新の重なる (date, symbol) で終値の不一致
    old_ov = df[df["date"] >= start][["date", "symbol", "close"]]
    m = old_ov.merge(new[["date", "symbol", "close"]], on=["date", "symbol"], suffixes=("_old", "_new"))
    m["dev"] = (m["close_new"] / m["close_old"] - 1).abs()
    bad = m[m["dev"] > 0.005].groupby("symbol")["dev"].max()
    have_new = set(new["symbol"])
    # 修正21: 直近 30 日に値のあった銘柄のうち、新しいデータの最後が全体の最後から 3 営業日より古いもの（取れない・途中で切れた・点検 2）
    live = set(df.loc[df["date"] >= last - pd.Timedelta(days=LIVE_DAYS), "symbol"])
    new_last = new["date"].max(); need = new_last - pd.offsets.BDay(LAG_BDAYS)
    nl = new.groupby("symbol")["date"].max()
    live_missing = sorted(s for s in live if s not in nl.index or nl[s] < need)
    # 窓より古い行の尺度を窓に合わせる（銘柄ごとに、最初の重なり 5 日の倍率の中央値）
    ov = df[df["date"] >= start][["date", "symbol", "close", "volume"]].merge(new[["date", "symbol", "close", "volume"]], on=["date", "symbol"], suffixes=("_old", "_new")).sort_values(["symbol", "date"])
    head = ov.groupby("symbol").head(5)
    fp = (head["close_new"] / head["close_old"]).groupby(head["symbol"]).median()
    hv = head[(head["volume_old"] > 0) & (head["volume_new"] > 0)]
    fv = (hv["volume_new"] / hv["volume_old"]).groupby(hv["symbol"]).median()
    fp = fp[(fp - 1).abs() > 1e-4]; fv = fv[(fv - 1).abs() > 0.05]            # 丸めの揺れは触らない
    before = df["date"] < start
    pm = df["symbol"].map(fp).where(before).fillna(1.0)
    for c in ["open", "high", "low", "close"]: df[c] = df[c] * pm
    df["volume"] = df["volume"] * df["symbol"].map(fv).where(before).fillna(1.0)
    keep_old = df[(df["date"] < start) | (~df["symbol"].isin(have_new))]
    out = pd.concat([keep_old, new], ignore_index=True).sort_values(["symbol", "date"]).reset_index(drop=True)
    info = {"更新": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "旧の最後": str(last.date()), "新の最後": str(new["date"].max().date()),
            "取り直し開始": str(start.date()), "旧行数": int(len(df)), "新行数": int(len(out)), "新データのある銘柄": len(have_new), "新データの無い銘柄": int(len(set(syms) - have_new)),
            "継ぎ目の不一致（>0.5%）銘柄数": int(len(bad)), "不一致の最大": float(bad.max()) if len(bad) else 0.0, "不一致の例": {k: round(float(v), 4) for k, v in bad.sort_values(ascending=False).head(10).items()},
            "古い行の尺度を直した銘柄数": int(len(fp)), "出来高の尺度を直した銘柄数": int(len(fv)), "捨てた今日の足": int(dropped_today),
            "取り直しで取れた銘柄": int(rescued), "直近に値があったのに取れない・途中で切れた銘柄": len(live_missing), "その全部": live_missing,
            "秒": round(time.time() - t0)}
    print(json.dumps({k: v for k, v in info.items() if k != "その全部"}, ensure_ascii=False, indent=1), flush=True)
    if len(live_missing) > MAX_MISSING * max(1, len(live)):                      # 修正21: 黙って古いまま書かない
        give_up(f"直近 30 日に値のあった {len(live)} 銘柄のうち {len(live_missing)} 銘柄（{len(live_missing) / max(1, len(live)):.1%}）が取れない・途中で切れた（上限 {MAX_MISSING:.0%}）",
                live_missing, t0, {"取り直しで取れた銘柄": int(rescued)})
    if a.dry: print("--dry: 書かない"); return
    tmp = P + ".tmp"; out.to_parquet(tmp, index=False); os.replace(tmp, P)
    log_jsonl(info)
    print("書いた:", P)


if __name__ == "__main__":
    main()
