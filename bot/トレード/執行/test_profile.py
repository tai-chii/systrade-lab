"""test_profile.py — broker_profile の試験（偽の MT5・本物の bot・winnote には触らない）"""
import copy, json, os, sys, tempfile, types
HERE = os.path.dirname(os.path.abspath(__file__))
V = HERE  # 2026-11-09: トレード/執行/ に置いた写し。検証/ は verification-lab のある階層まで上がって探す
while not os.path.isdir(os.path.join(V, "verification-lab")): V = os.path.dirname(V)
WS = os.path.dirname(V)
S21 = os.path.join(V, "トレード", "執行", "S21")
os.environ.setdefault("MOCK_H1", os.path.join(WS, "作業層", "大容量", "market_data_forward", "H1")); os.environ.setdefault("MOCK_NOW", "2026-10-28 08:00:20+00:00")
sys.path[:0] = [HERE, S21, os.path.join(S21, "テスト", "mock"), os.path.join(V, "verification-lab", "tools", "mt5")]
import broker_profile as BP
import MetaTrader5 as mock, execute_mt5 as E
import pandas as pd
tmp = tempfile.mkdtemp(prefix="s21_profile_")
E.LEDGER_DIR = os.path.join(tmp, "台帳"); E.LOG_DIR = os.path.join(tmp, "ログ"); E.LEDGER = os.path.join(E.LEDGER_DIR, "trades.csv"); E.STATE = os.path.join(tmp, "状態.json"); E.CONFIG = os.path.join(tmp, "config.json")
mock.NOW[0] = pd.Timestamp(os.environ["MOCK_NOW"])
R = []
def case(n, c): R.append((n, bool(c))); print(("合格 " if c else "不合格 ") + n)

XM = BP.load(os.path.join(HERE, "brokers", "XM.json")); OA = BP.load(os.path.join(HERE, "brokers", "OANDA_例.json"))
case("書式: XM と OANDA_例 は読める", XM["name"] == "XM" and OA["name"] == "OANDA_例")
bad = lambda ex: BP.validate({"name": "x", "account_currency": "JPY", "cost": {}, "exec": ex})
case("書式: 売買の規則の鍵（risk_pct）は止まる", any("売買の規則" in e for e in bad({"risk_pct": 0.01})))
case("書式: password は止まる", any("password" in e for e in bad({"password": "x"})))
case("書式: 読めない tz は止まる", any("tz" in e for e in bad({"tz": "jst"})))

# winnote の今の config＝既定値＋equity_override 1,000 万（winnote_config_変更.log の 2026-11-05 19:15）
deployed = dict(E.DEFAULT_CONFIG); deployed["equity_override"] = 10000000
case("XM: 今の config との差は 0", BP.diff(XM, deployed) == [])
case("XM: 当てても config は 1 文字も変わらない", BP.apply(XM, deployed) == deployed)
d = BP.diff(OA, deployed); new = BP.apply(OA, deployed)
case("OANDA_例: 変わるのは tz だけ（eet → nyclose）", [k for k, _, _ in d] == ["tz"] and new["tz"] == "nyclose")
case("OANDA_例: 売買の規則の鍵は元のまま", all(new[k] == deployed[k] for k in BP.STRATEGY_KEYS))
deployed2 = dict(deployed, server="XMTrading-MT5 3", login=123)
case("書いていない鍵（接続先・login）は残る", BP.apply(OA, deployed2)["server"] == "XMTrading-MT5 3" and BP.apply(OA, deployed2)["login"] == 123)
try:
    BP.apply({"exec": {"risk_pct": 0.5}}, deployed); case("書式を飛ばしても売買の規則は変えられない", False)
except AssertionError:
    case("書式を飛ばしても売買の規則は変えられない", True)

# preflight（偽の MT5・XM の形＝USD 口座 10 万ドル）
P0 = {"name": "mockXM", "account_currency": "USD", "exec": {"tz": "eet", "symbol_map": {}, "equity_override": None}, "cost": {}}
out = BP.preflight(P0, dict(E.DEFAULT_CONFIG), E, mock)
case(f"preflight: 銘柄 {out['銘柄'][0]}/19", out["銘柄"][0] == 19)
case("preflight: 口座通貨の一致を見る", out["口座通貨"][2] is True and BP.preflight(dict(P0, account_currency="JPY"), dict(E.DEFAULT_CONFIG), E, mock)["口座通貨"][2] is False)
# 最小ロットの倍率は bot の lot_for の「最小ロットに切り上げ」と食い違わない
cfg = BP.apply(P0, dict(E.DEFAULT_CONFIG)); B = E.Broker(cfg, live=False); mism = []
for s, r in out["最小ロットの倍率"].items():
    t = mock.symbol_info_tick(B.names[s]); lot, note = B.lot_for(s, t.bid * 0.005)
    if r is None or (r > 1.0) != ("最小ロット" in note): mism.append((s, r, note))
case(f"preflight: 最小ロットの倍率が bot の切り上げと一致（19 銘柄・食い違い {len(mism)}）", not mism)
print("  最小ロットの倍率（偽の MT5・USD 10 万・D=値段の 0.5%）:", {s: round(r, 2) for s, r in sorted(out["最小ロットの倍率"].items(), key=lambda x: -x[1])[:5]}, "… 1.5 倍超:", out["1.5 倍を超える"])
# 接尾辞の業者（s21-broker-swap の P1 の形）: symbol_map なしで 19/19、別名は自動探索で見つかる
ALT = dict(US500="SPX500", USTECH="NAS100", GER40="DE40", JPN225="JP225", XAUUSD="GOLD"); keep = dict(mock.NAMES)
mock.NAMES.clear(); mock.NAMES.update({s: ALT.get(s, s) + ".pro" for s in mock.SYMS})
o1 = BP.preflight(P0, dict(E.DEFAULT_CONFIG), E, mock)
case(f"preflight（接尾辞の業者）: 銘柄 {o1['銘柄'][0]}/19・最小ロットの倍率が全銘柄で出る（円の換算も取れる）", o1["銘柄"][0] == 19 and all(v is not None for v in o1["最小ロットの倍率"].values()))
mock.NAMES.clear(); mock.NAMES.update(keep)
case("手数料: 0 の業者は 0R・7 円/ロット往復で 1 ロット 1R=700 円なら 0.01R", BP.commission_R(XM, "EURUSD", 1, 700) == 0 and abs(BP.commission_R({"cost": {"commission_per_lot_round": {"FX": 7}}}, "EURUSD", 1, 700) - 0.01) < 1e-12)

bad_ = [n for n, ok in R if not ok]; print(f"\n{len(R) - len(bad_)}/{len(R)} 合格"); sys.exit(1 if bad_ else 0)
