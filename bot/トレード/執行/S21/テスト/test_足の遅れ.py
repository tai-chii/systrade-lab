# -*- coding: utf-8 -*-
"""新しい時間の足が MT5 からまだ返らない銘柄でも、最新の確定足で判断することを確かめる（2026-11-02 の不具合の再発防止）。
Mac で:  python テスト/test_足の遅れ.py [--start "2026-10-05 08:00:20+00:00"] [--hours 24]
修正前のコードで落ちることの確認は EXEC_DIR に修正前の execute_mt5.py のフォルダを渡す。"""
import argparse, inspect, json, os, sys, tempfile, shutil, time
import pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); S21 = os.path.dirname(HERE); WS = os.path.abspath(os.path.join(S21, "..", "..", "..", ".."))
ap = argparse.ArgumentParser(); ap.add_argument("--start", default="2026-10-05 08:00:20+00:00"); ap.add_argument("--hours", type=int, default=24)
ap.add_argument("--h1", default=os.path.join(WS, "作業層", "大容量", "market_data_forward", "H1")); a = ap.parse_args()
tmp = tempfile.mkdtemp(prefix="s21_lag_")
os.environ["MOCK_H1"] = a.h1; os.environ["MOCK_NOW"] = a.start
sys.path[:0] = [os.environ.get("EXEC_DIR", S21), S21, os.path.join(HERE, "mock"), os.path.join(WS, "検証", "verification-lab", "tools", "mt5")]
import MetaTrader5 as mock, execute_mt5 as E                                        # noqa: E402
E.LEDGER_DIR = os.path.join(tmp, "台帳"); E.LOG_DIR = os.path.join(tmp, "ログ"); E.LEDGER = os.path.join(E.LEDGER_DIR, "trades.csv")
E.STATE = os.path.join(tmp, "状態.json"); E.CONFIG = os.path.join(tmp, "config.json")
cfg = E.load_config(); B = E.Broker(cfg, live=False); ALL = list(B.names); fixed = "now" in inspect.signature(B.bars).parameters


def decide(h):
    d = tempfile.mkdtemp(prefix="s21_h1_", dir=tmp); kw = dict(now=h) if fixed else {}
    for s in ALL:
        x, _ = B.bars(s, **kw); x.to_parquet(os.path.join(d, f"{s}.parquet"), index=False)
    return E.SG.decide(d, h.floor("h") - pd.Timedelta(hours=1))["signals"]


# 1. 足の遅れがあっても判断は変わらない（足の時刻・行動とも）
bad, n = [], 0; h0 = pd.Timestamp(a.start)
for k in range(a.hours):
    h = h0 + pd.Timedelta(hours=k); mock.NOW[0] = h; mock.LAG.clear(); base = decide(h); mock.LAG.update(ALL[2:]); lag = decide(h); mock.LAG.clear(); n += 1
    for s in ALL[2:]:
        x, y = base.get(s), lag.get(s)
        if x is None or y is None or x["bar"] != y["bar"] or x["action"] != y["action"]: bad.append((str(h), s, x and x["bar"], y and y["bar"], x and x["action"], y and y["action"]))
print(f"1 足の遅れ: {n} 時間 × {len(ALL) - 2} 銘柄で不一致 {len(bad)} 件"); [print("  ", b) for b in bad[:6]]
if fixed:
    # 2. 待ちは全銘柄を見て、足が来ていれば待たない・来なければ名前を返す
    h = h0; mock.NOW[0] = h; s0 = time.time(); r0 = E.wait_for_bars(B, h, tries=2, every=0); mock.LAG.add(ALL[-1]); r1 = E.wait_for_bars(B, h, tries=2, every=0); mock.LAG.clear()
    ok2 = r0 == [] and r1 == [ALL[-1]]; print("2 待ち:", "OK" if ok2 else f"NG {r0} {r1}")
    # 3. 足が 2 本遅れ、値だけ来ている銘柄には入らない（判断の足が古い）。休場（値も足も来ない）は待たない
    s = ALL[0]; mock.NOW[0] = h
    real = mock._bars; mock._bars = lambda x: real(x).iloc[:-1] if x == s else real(x); mock.LAG.add(s); B.bars(s, now=h); st = (B.forming[s], B.quoting(s, h)); mock._bars = real; mock.LAG.clear()
    ok3 = st == (False, True); print("3 足が古い銘柄の印:", "OK" if ok3 else f"NG {st}")
    q = B.quoting(s, h + pd.Timedelta(hours=3)); ok4 = q is False; print("4 値が 3 時間来ない銘柄は休場扱い:", "OK" if ok4 else "NG")
else:
    ok2 = ok3 = ok4 = True
shutil.rmtree(tmp, ignore_errors=True)
print("合格" if not bad and ok2 and ok3 and ok4 else "不合格"); sys.exit(0 if not bad and ok2 and ok3 and ok4 else 1)
