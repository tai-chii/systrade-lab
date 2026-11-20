# -*- coding: utf-8 -*-
"""XM の実測の仕様の偽 MT5（mock_xm）で、bot のロットの計算と、業者プロファイルの事前確認（preflight）のロットの式の検算を確かめる。
本物の bot・台帳・MT5・winnote には触れない（台帳とログは一時フォルダ）。python は venv_forward。
  python 試験_xm仕様.py              → bot は今の正本（トレード/執行/S21/execute_mt5.py）
  EXEC_DIR=<フォルダ> python …       → bot をそのフォルダの execute_mt5.py に替える（配る前の版の確かめ）"""
import os, sys, tempfile, types, importlib
HERE = os.path.dirname(os.path.abspath(__file__)); V = HERE
while not os.path.isdir(os.path.join(V, "verification-lab")):                                # 検証/（置き場所に依らず上へたどる。test_profile.py と同じ）
    if os.path.dirname(V) == V: sys.exit("検証/ の下に置いて回す（verification-lab が見つからない）")
    V = os.path.dirname(V)
WS = os.path.dirname(V); S21 = os.path.join(V, "トレード", "執行", "S21")
BPDIR = HERE if os.path.exists(os.path.join(HERE, "broker_profile.py")) else os.path.join(V, "トレード", "執行")
MOCKDIR = os.path.join(HERE, "mock_xm") if os.path.isdir(os.path.join(HERE, "mock_xm")) else os.path.join(S21, "テスト", "mock_xm")
os.environ.setdefault("MOCK_H1", os.path.join(WS, "作業層", "大容量", "market_data_forward", "H1")); os.environ.setdefault("MOCK_NOW", "2026-10-28 08:00:20+00:00")
sys.path[:0] = [BPDIR, os.environ.get("EXEC_DIR", S21), S21, MOCKDIR, os.path.join(V, "verification-lab", "tools", "mt5")]
import numpy as np, pandas as pd
import broker_profile as BP
import MetaTrader5 as mock, execute_mt5 as E
assert hasattr(mock, "SPEC"), "mock_xm が読み込まれていない"
tmp = tempfile.mkdtemp(prefix="s21_xm_")
E.LEDGER_DIR = os.path.join(tmp, "台帳"); E.LOG_DIR = os.path.join(tmp, "ログ"); E.LEDGER = os.path.join(E.LEDGER_DIR, "trades.csv"); E.STATE = os.path.join(tmp, "状態.json"); E.CONFIG = os.path.join(tmp, "config.json")
mock.NOW[0] = pd.Timestamp(os.environ["MOCK_NOW"])
R = []
def case(n, c): R.append((n, bool(c))); print(("合格 " if c else "不合格 ") + n)

cfg = dict(E.DEFAULT_CONFIG); cfg["equity_override"] = 10000000                    # winnote の今の config と同じ（元手 1,000 万円・1 回 0.04% = 4,000 円）
B = E.Broker(cfg, live=False); risk = cfg["equity_override"] * cfg["risk_pct"]
case(f"1 XM の銘柄名で 19/19（GOLD・US100Cash・JP225Cash など）", len(B.names) == 19 and B.names["XAUUSD"] == "GOLD" and B.names["USTECH"] == "US100Cash" and B.names["JPN225"] == "JP225Cash" and B.names["GER40"] == "GER40Cash")
case("2 口座通貨は JPY", B.acc.currency == "JPY")
conv = {c: B.fx_to_account(c) for c in ("USD", "EUR", "GBP", "CHF", "CAD", "JPY")}
case(f"3 損益通貨 6 種の円への換算が取れる（{ {k: round(v, 2) for k, v in conv.items()} }）", all(v is not None and v > 0 for v in conv.values()) and conv["JPY"] == 1.0)

# 4〜6 ロット: 刻みの倍数・最小と最大の間・損切りの損が狙いのリスクを超えない（最小ロットへの切り上げは注記つき）。損は MT5 の側の計算（order_calc_profit）で測る
bad_step, bad_range, bad_risk, rows = [], [], [], []
for k in (0.002, 0.005, 0.02):                                                     # D＝値段の 0.2%・0.5%・2%
    for s, n in B.names.items():
        info = mock.symbol_info(n); t = mock.symbol_info_tick(n); D = t.bid * k; lot, note = B.lot_for(s, D)
        if lot is None: bad_range.append((s, k, note)); continue
        q = lot / info.volume_step
        if abs(q - round(q)) > 1e-6: bad_step.append((s, k, lot, info.volume_step))
        if lot < info.volume_min - 1e-9 or lot > info.volume_max + 1e-9: bad_range.append((s, k, lot))
        loss = -mock.order_calc_profit(mock.ORDER_TYPE_BUY, n, lot, t.ask, t.ask - D); one_step = -mock.order_calc_profit(mock.ORDER_TYPE_BUY, n, info.volume_step, t.ask, t.ask - D)
        ok = (loss <= risk * 1.001 and loss > risk - one_step - 1) or ("最小ロット" in note and abs(lot - info.volume_min) < 1e-9) or ("最大ロット" in note)
        if not ok: bad_risk.append((s, k, lot, round(loss), note))
        rows.append((s, k, lot, round(loss), note[:12]))
case(f"4 ロットは刻みの倍数（19 銘柄 × 3 つの D・食い違い {len(bad_step)}）", not bad_step)
case(f"5 ロットは最小と最大の間（食い違い {len(bad_range)}）", not bad_range)
case(f"6 損切りの損は狙い {risk:,.0f} 円以下で、刻み 1 つ分より下には離れない（最小ロットへの切り上げは注記つき・食い違い {len(bad_risk)}）", not bad_risk)
for x in (bad_step + bad_range + bad_risk)[:6]: print("   ", x)
idx = [r for r in rows if r[0] in ("US500", "USTECH", "GER40", "JPN225") and r[1] == 0.005]
case(f"7 指数は刻み 0.1 で切り捨てている（{[(r[0], r[2]) for r in idx]}）", all(abs(r[2] * 10 - round(r[2] * 10)) < 1e-6 for r in idx))

# 8〜11 業者プロファイルの事前確認: ロットの式の検算
P0 = {"name": "mockXM", "account_currency": "JPY", "exec": {"tz": "eet", "symbol_map": {}, "equity_override": 10000000}, "cost": {}}
out = BP.preflight(P0, dict(E.DEFAULT_CONFIG), E, mock)
ck = out["ロットの式の検算"]
case(f"8 XM の仕様では 19 銘柄とも式が合う（比 {min(ck.values()):.4f}〜{max(ck.values()):.4f}）", out["式が合わない"] == [] and out["検算できない"] == [] and len(ck) == 19)
mock.CALC_OVERRIDE["JP225Cash"] = 10.0                                             # 先物型の真似: 1 ロット・1 円あたり 10 円（契約サイズ 1 の式では 1 円）
o2 = BP.preflight(P0, dict(E.DEFAULT_CONFIG), E, mock); mock.CALC_OVERRIDE.clear()
case(f"9 損益の出方が式と違う銘柄は「式が合わない」に出る（JPN225・比 {o2['ロットの式の検算']['JPN225']:.1f}）", o2["式が合わない"] == ["JPN225"])
keep = mock.order_calc_profit; del mock.order_calc_profit
o3 = BP.preflight(P0, dict(E.DEFAULT_CONFIG), E, mock); mock.order_calc_profit = keep
case("10 order_calc_profit が無い環境では落ちずに「検算できない」に 19 銘柄", o3["式が合わない"] == [] and len(o3["検算できない"]) == 19)
mock.order_calc_profit = lambda *a, **k: None
o4 = BP.preflight(P0, dict(E.DEFAULT_CONFIG), E, mock); mock.order_calc_profit = keep
case("11 MT5 が None を返す銘柄も「検算できない」", len(o4["検算できない"]) == 19)
case("12 口座通貨・銘柄・最小ロットの倍率は今までどおり出る", out["口座通貨"][2] is True and out["銘柄"][0] == 19 and all(v is not None for v in out["最小ロットの倍率"].values()))
print("  最小ロットの倍率（XM の仕様・元手 1,000 万円・D=値段の 0.5%）の上位:", {s: round(r, 2) for s, r in sorted(out["最小ロットの倍率"].items(), key=lambda x: -x[1])[:5]})
# 13〜15 preflight の命令（本物の MT5 で打つ形）: 読める形で出し、終了コードで知らせ、bot の台帳・ログの場所を一時フォルダに向ける
lines = []; E.LOG_DIR = "/本物のログの場所"; rc = BP.preflight_cli(P0, dict(E.DEFAULT_CONFIG), mt5mod=mock, E=E, out=lines.append)
case(f"13 命令: 式が合えば終了 0（偽 MT5 の時計のずれで tz の ★ が出る回は 3）・つないだ先と検算の行が出る", rc in (0, 3) and any(l.startswith("つないだ先: XMTrading-MT5 3") for l in lines) and any("ロットの式の検算" in l for l in lines) and not any("★ 式が合わない" in l for l in lines))   # 偽 MT5 の時計と実際の時刻の差で tz の ★ が出る回がある（式の ★ だけを見る）
case("14 命令: bot のログ・台帳の場所を一時フォルダに向けている（本物に書かない）", "s21_preflight_" in E.LOG_DIR and "s21_preflight_" in E.LEDGER and "s21_preflight_" in E.STATE)
mock.CALC_OVERRIDE["GER40Cash"] = 25.0; lines = []; rc = BP.preflight_cli(P0, dict(E.DEFAULT_CONFIG), mt5mod=mock, E=E, out=lines.append); mock.CALC_OVERRIDE.clear()
case("15 命令: 式が合わない銘柄があれば終了 1 と ★ の行（GER40）", rc == 1 and any("★ 式が合わない" in l and "GER40" in l for l in lines))
case("16 プロファイルに expect_server（つないだ先の確かめ）を書ける・書式で止まらない", BP.validate({"name": "x", "account_currency": "JPY", "cost": {}, "exec": {"expect_server": "XMTrading-MT5 3"}}) == [] and BP.apply({"exec": {"expect_server": "S"}}, dict(E.DEFAULT_CONFIG))["expect_server"] == "S")
case("18 命令: 業者の名前が違う銘柄の対応を出す（XAUUSD→GOLD・USTECH→US100Cash など 5 本）", any(l.startswith("銘柄の対応") and "XAUUSD→GOLD" in l and "USTECH→US100Cash" in l and "JPN225→JP225Cash" in l and "EURUSD→" not in l for l in lines))
P1 = dict(P0, exec=dict(P0["exec"], expect_server="OANDA-Japan MT5 Demo")); lines = []; rc = BP.preflight_cli(P1, dict(E.DEFAULT_CONFIG), mt5mod=mock, E=E, out=lines.append)
case("17 命令: つないだ先が狙い（expect_server）と違えば終了 1 と ★（別の MT5 を検算して「よい」と出さない）", rc == 1 and any("★" in l and "つないだ先が違う" in l for l in lines))
bad_ = [n for n, ok in R if not ok]; print(f"\n{len(R) - len(bad_)}/{len(R)} 合格"); sys.exit(1 if bad_ else 0)
