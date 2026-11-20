# -*- coding: utf-8 -*-
"""swap_specs_export.py — XM MT5 の全銘柄の仕様（スワップ値を含む）を CSV にして Mac へ送る（2026-10-31・Q591 の実スワップ再測定）。
読むだけ。注文は一切出さない。口座番号は書かない。S21 の bot には触らない（動いたまま実行してよい。市場が閉まっている週末が安全）。
列は 検証/トレード/forward/MT5/S21_SymbolSpecs.mq5 と同じなので、swap_from_mt5.py --specs にもそのまま渡せる。
使い方（winnote・PowerShell）:
  cd C:\\Users\\gtaic\\lab-ops; git pull; python trade\\swap_specs_export.py
  python trade\\swap_specs_export.py --no-push     # 書くだけ（確認用）
出力: lab-ops/trade/winnote/symbol_specs_<日時>.csv"""
import argparse, csv, datetime as dt, os, subprocess, sys
XM = r"C:\Program Files\XMTrading MT5\terminal64.exe"
MODE = {0: "DISABLED", 1: "POINTS", 2: "CURRENCY_SYMBOL", 3: "CURRENCY_MARGIN", 4: "CURRENCY_DEPOSIT", 5: "INTEREST_CURRENT", 6: "INTEREST_OPEN", 7: "REOPEN_CURRENT", 8: "REOPEN_BID", 9: "CURRENCY_PROFIT"}
COLS = "name,description,path,digits,point,contract_size,currency_base,currency_profit,currency_margin,swap_mode,swap_mode_name,swap_long,swap_short,swap_3days,spread_points,spread_float,bid,ask,tick_value,tick_size,volume_min,volume_step,volume_max,trade_mode,account_currency,account_leverage,server,company".split(",")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def git(*a):
    r = subprocess.run(["git", "-C", ROOT, *a], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout + r.stderr).strip()


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--path", default=XM); ap.add_argument("--no-push", action="store_true"); a = ap.parse_args()
    try:
        import MetaTrader5 as mt5
    except ImportError:
        sys.exit("MetaTrader5 が入っていません（bot と同じ python で実行してください）")
    if not mt5.initialize(path=a.path if os.path.exists(a.path) else None):
        sys.exit(f"MT5 に接続できない: {mt5.last_error()}。XMTrading MT5 を開いてログインしてからもう一度")
    try:
        ai = mt5.account_info(); ti = mt5.terminal_info(); syms = mt5.symbols_get()
        if ai is None or not syms: sys.exit(f"口座か銘柄を読めない: {mt5.last_error()}")
        print(f"接続: {ai.server}・{'デモ' if ai.trade_mode == 0 else '本番の口座'}・銘柄 {len(syms)}・接続状態 {ti.connected}", flush=True)
        rows = []
        for s in syms:
            rows.append([s.name, (s.description or "").replace(",", " "), (s.path or "").replace(",", " "), s.digits, s.point, s.trade_contract_size, s.currency_base, s.currency_profit, s.currency_margin,
                         s.swap_mode, MODE.get(s.swap_mode, f"UNKNOWN_{s.swap_mode}"), s.swap_long, s.swap_short, s.swap_rollover3days, s.spread, int(s.spread_float), s.bid, s.ask,
                         s.trade_tick_value, s.trade_tick_size, s.volume_min, s.volume_step, s.volume_max, s.trade_mode, ai.currency, ai.leverage, ai.server, ai.company])
    finally:
        mt5.shutdown()      # この python の接続を閉じるだけ。MT5 も bot も止まらない
    out = os.path.join(ROOT, "trade", "winnote"); os.makedirs(out, exist_ok=True)
    f = os.path.join(out, f"symbol_specs_{dt.datetime.now():%Y%m%d_%H%M}.csv")
    with open(f, "w", newline="", encoding="utf-8") as h:
        w = csv.writer(h); w.writerow(COLS); w.writerows(rows)
    print("書いた:", f, len(rows), "行", flush=True)
    if a.no_push: return
    rel = os.path.relpath(f, ROOT).replace("\\", "/"); git("add", "--", rel); git("commit", "-m", f"winnote: XM の銘柄仕様 {os.path.basename(f)}", "--", rel)
    for _ in range(2):
        git("pull", "--rebase", "--autostash"); rc, msg = git("push")
        if rc == 0: print("push した"); return
    sys.exit(f"push 失敗: {msg[-300:]}")


if __name__ == "__main__":
    main()
