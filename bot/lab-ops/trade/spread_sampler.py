# -*- coding: utf-8 -*-
"""spread_sampler.py — MT5 の実スプレッドを毎時の足の変わり目に測る（2026-11-01・Q606 の次の段階）。
読むだけ。注文は一切出さない。口座番号は書かない。S21 の bot には触らない（動いたまま実行してよい）。
なぜ: Q592・Q606 の XM のコストは一定幅の近似で、S21 が入る時間（毎時 :00）の実測が無い。他の業者のデモも同じ形で測って比べる。
やること: 開始から 60 秒、10 秒ごとに 7 回 Bid/Ask を読み、銘柄ごとに 1 行を trade/winnote/S21/spreads_<label>_<YYYYMM>.csv に足す。
送信: このフォルダは send_status.py が毎時 commit と push をするので、ここでは git に触らない。
使い方（winnote・PowerShell）:
  cd C:\\Users\\gtaic\\lab-ops; git pull; python trade\\spread_sampler.py --print        # 1 回だけ測って表示（書かない）
  $py = (Get-Command python).Source; $sc = "C:\\Users\\gtaic\\lab-ops\\trade\\spread_sampler.py"
  schtasks /Create /SC HOURLY /MO 1 /ST 00:00 /TN Spread_XM /TR "`"$py`" `"$sc`"" /F
別の業者: --path <terminal64.exe> --label <名前>。タスク名も変える。
Mac の集計: verification-lab/financial-engineering/s21-fx-venue-q606/spread_report.py"""
import argparse, csv, datetime as dt, os, re, statistics as st, sys, time
XM = r"C:\Program Files\XMTrading MT5\terminal64.exe"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SYMS = ["EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "USDJPY", "USDCHF", "USDCAD", "EURJPY", "GBPJPY", "EURGBP", "AUDJPY", "CADJPY", "CHFJPY", "NZDJPY", "XAUUSD", "US500", "USTECH", "GER40", "JPN225"]
ALIAS = {"XAUUSD": ["GOLD", "XAUUSD"], "US500": ["US500Cash", "US500", "SPX500"], "USTECH": ["US100Cash", "USTECH", "NAS100", "US100"], "GER40": ["GER40Cash", "GER40", "DE40"], "JPN225": ["JP225Cash", "JPN225", "JP225"]}
COLS = ["hour_utc", "label", "sym", "broker_sym", "n", "live", "spr_med", "spr_min", "spr_max", "mid", "rel_bp", "server"]
N, GAP = 7, 10


def resolve(names):
    """業者の銘柄名を探す。完全一致 → 記号と接尾辞を無視した前方一致（EURUSD.m・USD_JPY・USDJPYz など）の順。"""
    out = {}
    for s in SYMS:
        for c in ALIAS.get(s, [s]):
            hit = c if c in names else min((x for x in names if re.sub(r"[^A-Za-z0-9]", "", x).upper().startswith(c.upper())), key=lambda x: (x[len(c):len(c) + 1].isalnum(), len(x)), default=None)
            if hit: out[s] = hit; break
    return out


def sample(mt5, m):
    got = {s: [] for s in m}
    for i in range(N):
        for s, b in m.items():
            t = mt5.symbol_info_tick(b)
            if t is None or t.bid <= 0 or t.ask <= 0:
                continue
            got[s].append((t.bid, t.ask, getattr(t, "time_msc", t.time)))
        if i < N - 1: time.sleep(GAP)
    return got


def rows(got, m, hour, label, server):
    out = []
    for s, x in got.items():
        if not x: continue
        sp = [a - b for b, a, _ in x]; mid = st.median((a + b) / 2 for b, a, _ in x); med = st.median(sp)
        out.append([hour, label, s, m[s], len(x), int(len({t for *_, t in x}) > 1), f"{med:.8g}", f"{min(sp):.8g}", f"{max(sp):.8g}", f"{mid:.8g}", f"{med / mid * 1e4:.4f}", server])
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--path", default=XM); ap.add_argument("--label", default="XM"); ap.add_argument("--print", action="store_true", dest="show"); a = ap.parse_args()
    if not os.path.exists(a.path): sys.exit(f"端末が見つからない: {a.path}（別の業者の値を {a.label} として記録しないよう止めた）")
    try:
        import MetaTrader5 as mt5
    except ImportError:
        sys.exit("MetaTrader5 が入っていません（bot と同じ python で実行してください）")
    if not mt5.initialize(path=a.path):
        sys.exit(f"MT5 に接続できない: {mt5.last_error()}")
    try:
        ai = mt5.account_info(); syms = mt5.symbols_get()
        if ai is None or not syms: sys.exit(f"口座か銘柄を読めない: {mt5.last_error()}")
        m = resolve({s.name for s in syms}); [mt5.symbol_select(b, True) for b in m.values()]
        hour = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:00"); got = sample(mt5, m)
    finally:
        mt5.shutdown()      # この python の接続を閉じるだけ。MT5 も bot も止まらない
    R = rows(got, m, hour, a.label, ai.server); miss = [s for s in SYMS if s not in m]
    if miss: print("見つからない銘柄:", miss, flush=True)
    if a.show:
        print(*COLS, sep=","); [print(*r, sep=",") for r in R]; return
    d = os.path.join(ROOT, "trade", "winnote", "S21"); os.makedirs(d, exist_ok=True); f = os.path.join(d, f"spreads_{a.label}_{hour[:7].replace('-', '')}.csv"); new = not os.path.exists(f)
    with open(f, "a", newline="", encoding="utf-8") as h:
        w = csv.writer(h)
        if new: w.writerow(COLS)
        w.writerows(R)
    print("書いた:", f, len(R), "行", flush=True)


if __name__ == "__main__":
    main()
