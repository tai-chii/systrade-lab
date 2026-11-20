# -*- coding: utf-8 -*-
"""execute_mt5.py が記録（forward_s21.py）と同じ売買をするかを、偽 MT5（mock/MetaTrader5.py・Dukascopy の足をサーバー時間 EET で返す）で確かめる。
Mac で:  python テスト/test_同等性.py --start "2026-10-04 21:00+00:00" --end "2026-10-11 02:00+00:00"
（台帳・ログ・状態.json を一時フォルダに作る。本物の台帳は触らない。1 週間で 5〜10 分）"""
import argparse, os, sys, shutil, subprocess, tempfile
import pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); S21 = os.path.dirname(HERE); WS = os.path.abspath(os.path.join(S21, "..", "..", "..", ".."))
ap = argparse.ArgumentParser(); ap.add_argument("--start", required=True); ap.add_argument("--end", required=True)
ap.add_argument("--h1", default=os.path.join(WS, "作業層", "大容量", "market_data_forward", "H1"))
ap.add_argument("--spr", default="broker", choices=["broker", "ref"]); a = ap.parse_args()
tmp = tempfile.mkdtemp(prefix="s21_test_")
os.environ["MOCK_H1"] = a.h1; os.environ["MOCK_NOW"] = a.start
sys.path.insert(0, os.path.join(HERE, "mock")); sys.path.insert(0, S21)
import MetaTrader5 as mock, execute_mt5 as E                                        # noqa: E402
E.LEDGER_DIR = os.path.join(tmp, "台帳"); E.LOG_DIR = os.path.join(tmp, "ログ"); E.LEDGER = os.path.join(E.LEDGER_DIR, "trades.csv")
E.STATE = os.path.join(tmp, "状態.json"); E.CONFIG = os.path.join(tmp, "config.json")
# 記録（同じ期間・同じ凍結モデル）
subprocess.run([sys.executable, os.path.join(S21, "..", "..", "forward", "S21", "forward_s21.py"), "--h1", a.h1, "--start", a.start, "--end", a.end, "--out", os.path.join(tmp, "記録")],
               check=True, capture_output=True)
cfg = E.load_config(); cfg["spr_source"] = a.spr       # 偽 MT5 の spread は Dukascopy そのもの → broker で記録と完全一致するはず。ref は参照表で判断する本番の形
B = E.Broker(cfg, live=True)
start = pd.Timestamp(a.start).floor("h") + pd.Timedelta(hours=1, seconds=20); hours = list(pd.date_range(start, pd.Timestamp(a.end), freq="h"))
pending = None; i = 0
while i < len(hours):
    h = hours[i]
    if pending is not None and pending < h:
        mock.NOW[0] = pending; st, gi = E.run_once(B, cfg, True, now=pending, entries=False); pending = None; continue   # 週末前決済の起床: 入口は回さない（main() と同じ・2026-11-04 Q687）
    mock.NOW[0] = h; mock.advance_sl_tp(); st, gi = E.run_once(B, cfg, True, now=h)
    cl = [g[0] for g in gi.values() if g[0] is not None and g[0] > h]; pending = min(cl) if cl else None; i += 1
L = pd.read_csv(E.LEDGER); R = pd.read_csv(os.path.join(tmp, "記録", "trades_latest.csv")); R = R[R["decision"] <= str(hours[-1] - pd.Timedelta(hours=1))]
m = R.merge(L, on=["sym", "decision"], how="outer", suffixes=("_記録", "_執行"), indicator=True); b = m[m["_merge"] == "both"]
print(f"記録 {len(R)} 件・執行 {len(L)} 件・同じ足で入った {len(b)} 件・記録だけ {(m['_merge'] == 'left_only').sum()}・執行だけ {(m['_merge'] == 'right_only').sum()}")
c = b[(b["status_記録"] == "closed") & (b["status_執行"] == "closed")]
print(f"両方決済済み {len(c)} 件: 決済の理由が同じ {(c['why_記録'] == c['why_執行']).mean():.1%}・入った値段が同じ {(b['entry_px_記録'] == b['entry_px_執行']).mean():.1%}・R の差 平均 {(c['R_執行'] - c['R_記録']).mean():+.3f}（保有コスト分）")
bad = b[(b["why_記録"] != b["why_執行"]) & (b["status_記録"] == "closed")]
if len(bad): print(bad[["sym", "decision", "why_記録", "why_執行"]].to_string())
print(f"一時フォルダ: {tmp}")
