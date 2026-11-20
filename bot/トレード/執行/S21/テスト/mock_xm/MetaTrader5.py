"""テスト用の偽 MetaTrader5（XM の実測の仕様版・2026-11-13）。元の偽 MT5（トレード/執行/S21/テスト/mock/MetaTrader5.py）をそのまま読み込み、
監査D が指摘した実測（lab-ops/trade/winnote/symbol_specs_20261101_0006.csv）との食い違いだけを上書きする:
  口座通貨 JPY（元は USD）・XM の銘柄名（GOLD・US100Cash・JP225Cash）・指数の最小ロットと刻み 0.1（元は 0.01）・最大ロット（50〜11,940）・
  損益通貨（GER40＝EUR・EURGBP＝GBP・USDCHF＝CHF・USDCAD＝CAD・JPN225＝JPY。元は全部 USD か JPY）。
あわせて order_calc_profit（MT5 が自分で計算する損益・口座通貨）を足す。bot のロットの式とは別の道（銘柄ごとの計算の型）で出すので、検算の物差しになる。"""
import os as _os
_V = _os.path.dirname(_os.path.abspath(__file__))
while not _os.path.isdir(_os.path.join(_V, "verification-lab")):                             # 検証/（置き場所に依らず上へたどる）
    if _os.path.dirname(_V) == _V: raise ImportError("mock_xm は 検証/ の下に置いて使う（verification-lab が見つからない）")
    _V = _os.path.dirname(_V)
_ORIG = _os.path.join(_V, "トレード", "執行", "S21", "テスト", "mock", "MetaTrader5.py")
exec(compile(open(_ORIG, encoding="utf-8").read(), _ORIG, "exec"))

# 実測（symbol_specs_20261101_0006.csv・XMTrading-MT5 3・口座通貨 JPY）: 名前・損益通貨・契約サイズ・最小ロット・刻み・最大ロット
SPEC = {s: (s, ("JPY" if s.endswith("JPY") else s[3:]), 100000.0, 0.01, 0.01, 50.0) for s in SYMS if s not in ("XAUUSD", "US500", "USTECH", "GER40", "JPN225")}
SPEC.update(XAUUSD=("GOLD", "USD", 100.0, 0.01, 0.01, 50.0), US500=("US500Cash", "USD", 1.0, 0.1, 0.1, 870.0), USTECH=("US100Cash", "USD", 1.0, 0.1, 0.1, 240.0),
            GER40=("GER40Cash", "EUR", 1.0, 0.1, 0.1, 150.0), JPN225=("JP225Cash", "JPY", 1.0, 0.1, 0.1, 11940.0))
NAMES = {s: v[0] for s, v in SPEC.items()}
ACCOUNT = "JPY"; EQUITY = [10000000.0]
CALC_OVERRIDE = {}   # 試験用: {業者の銘柄名: 1 ロット・値段 1 単位あたりの口座通貨の損益}（先物型など「値幅 × 契約サイズ」で損益が出ない銘柄の真似）


def account_info(): return types.SimpleNamespace(server="XMTrading-MT5 3（偽）", login=1, trade_mode=0, equity=EQUITY[0], balance=EQUITY[0], currency=ACCOUNT)


def _to_acct(cur):
    """損益通貨 → 口座通貨（JPY）。<cur>JPY の今の bid（bot の fx_to_account と同じ値になるが、ここは MT5 の側の計算）。"""
    if cur == ACCOUNT: return 1.0
    t = symbol_info_tick(NAMES[cur + ACCOUNT]); return float(t.bid)


def symbol_info(n):
    if n not in NAMES.values(): return None
    s = _s(n); p = POINT[s]; d = _load(s); spr = float(d["spread"].iloc[-1]) / p; name, cur, cs, vmin, vstep, vmax = SPEC[s]
    fx = cs == 100000.0
    return types.SimpleNamespace(point=p, digits=int(round(-np.log10(p))) if p < 1 else 0, volume_min=vmin, volume_max=vmax, volume_step=vstep, trade_tick_size=p,
        trade_tick_value=cs * p * (_to_acct(cur) if fx else 1.0),      # 実測: FX は口座通貨、CFD（指数・金）は損益通貨のまま
        filling_mode=1, spread=int(spr), currency_profit=cur, trade_contract_size=cs)


def order_calc_profit(action, symbol, volume, price_open, price_close):
    """MT5 の order_calc_profit の真似: 口座通貨の損益。銘柄が無ければ None。"""
    if symbol not in NAMES.values(): return None
    s = _s(symbol); dr = 1 if action == ORDER_TYPE_BUY else -1
    if symbol in CALC_OVERRIDE: return dr * (price_close - price_open) * volume * CALC_OVERRIDE[symbol]
    return dr * (price_close - price_open) * volume * SPEC[s][2] * _to_acct(SPEC[s][1])
