"""テスト用の偽 MetaTrader5（Dukascopy の H1 をサーバー時間 EET で返す）"""
import numpy as np, pandas as pd, os, types, time as _t
H1 = os.environ.get("MOCK_H1"); NOW = [pd.Timestamp(os.environ.get("MOCK_NOW"), tz="UTC")]
TIMEFRAME_M1=1; TIMEFRAME_M5=5; TIMEFRAME_M15=15; TIMEFRAME_M30=30; TIMEFRAME_H4=16388; TIMEFRAME_D1=16408; TIMEFRAME_W1=32769; TIMEFRAME_MN1=49153; TIMEFRAME_H1 = 16385; TRADE_ACTION_DEAL = 1; TRADE_ACTION_SLTP = 6; ORDER_TYPE_BUY = 0; ORDER_TYPE_SELL = 1
ORDER_TIME_GTC = 0; ORDER_FILLING_FOK = 0; ORDER_FILLING_IOC = 1; ORDER_FILLING_RETURN = 2
TRADE_RETCODE_DONE = 10009; TRADE_RETCODE_PLACED = 10008; TRADE_RETCODE_DONE_PARTIAL = 10010
POSITION_TYPE_BUY = 0; POSITION_TYPE_SELL = 1; DEAL_ENTRY_OUT = 1; DEAL_REASON_SL = 4; DEAL_REASON_TP = 5
SYMS = ["EURUSD","GBPUSD","AUDUSD","NZDUSD","USDJPY","USDCHF","USDCAD","EURJPY","GBPJPY","EURGBP","XAUUSD","US500","USTECH","GER40","JPN225","AUDJPY","CADJPY","CHFJPY","NZDJPY"]
NAMES = {s: (s + "Cash" if s in ("US500","USTECH","GER40","JPN225") else s) for s in SYMS}
POINT = {s: (0.001 if "JPY" in s else 0.00001) for s in SYMS}; POINT.update(XAUUSD=0.01, US500=0.01, USTECH=0.01, GER40=0.01, JPN225=1.0)
def _eu_dst(t):
    t = pd.Timestamp(t).tz_convert(None) if pd.Timestamp(t).tzinfo else pd.Timestamp(t)
    y = t.year
    s = pd.Timestamp(f"{y}-03-31") - pd.Timedelta(days=(pd.Timestamp(f"{y}-03-31").weekday() + 1) % 7) + pd.Timedelta(hours=1)
    e = pd.Timestamp(f"{y}-10-31") - pd.Timedelta(days=(pd.Timestamp(f"{y}-10-31").weekday() + 1) % 7) + pd.Timedelta(hours=1)
    return s <= t < e
def _srv(t):
    """UTC → サーバー時間（EET: 夏 +3 / 冬 +2）の epoch"""
    return int(pd.Timestamp(t).timestamp()) + (3 if _eu_dst(t) else 2) * 3600
_data = {}; _pos = []; _deals = []; _tick = [1000]
def _load(s):
    if s not in _data:
        d = pd.read_parquet(os.path.join(H1, f"{s}.parquet")); _data[s] = d
    return _data[s]
def initialize(**kw): return True
def last_error(): return (0, "")
def account_info(): return types.SimpleNamespace(server="Mock-Demo", login=1, trade_mode=0, equity=100000.0, balance=100000.0, currency="USD")
def terminal_info(): return types.SimpleNamespace(maxbars=10**6)
def symbols_get(): return [types.SimpleNamespace(name=n) for n in NAMES.values()]
def symbol_select(n, f): return True
def _s(n): return next(s for s, v in NAMES.items() if v == n)
def symbol_info(n):
    if n not in NAMES.values(): return None
    s = _s(n); p = POINT[s]; d = _load(s); spr = float(d["spread"].iloc[-1]) / p
    return types.SimpleNamespace(point=p, digits=int(round(-np.log10(p))) if p < 1 else 0, volume_min=0.01, volume_max=100, volume_step=0.01,
        trade_tick_size=p, trade_tick_value=(10.0 if "JPY" not in s else 0.066) * (p / 0.00001) if s not in ("XAUUSD","US500","USTECH","GER40","JPN225") else 1.0 * p / p, filling_mode=1, spread=int(spr), currency_profit=('JPY' if 'JPY' in s else 'USD'), trade_contract_size=(100000.0 if s not in ('XAUUSD','US500','USTECH','GER40','JPN225') else (100.0 if s=='XAUUSD' else 1.0)))
LAG = set()   # 新しい時間の足がまだ返らない銘柄（値は来ている。実際の MT5 で 2026-11-02 に見つかった形）
def _bars(s):
    d = _load(s); t = d["time"]; now = NOW[0]
    return d[t < (now.floor("h") if s in LAG else now)]
def symbol_info_tick(n):
    s = _s(n); d = _bars(s)
    if len(d) == 0: return types.SimpleNamespace(time=0, bid=0, ask=0)
    r = d.iloc[-1]; last = pd.Timestamp(r["time"])
    tm = _srv(NOW[0]) if s in LAG else _srv(last)
    return types.SimpleNamespace(time=tm, bid=float(r["open"]), ask=float(r["ask_open"]))   # 今の足の始値を今の値段とみなす
def copy_rates_from_pos(n, tf, start, count):
    s = _s(n); d = _bars(s).tail(count)
    if len(d) == 0: return None
    p = POINT[s]
    arr = np.array([(_srv(r.time), r.open, r.high, r.low, r.close, int(r.volume), int(round(r.spread / p)), 0) for r in d.itertuples()],
                   dtype=[("time","<i8"),("open","<f8"),("high","<f8"),("low","<f8"),("close","<f8"),("tick_volume","<u8"),("spread","<i4"),("real_volume","<u8")])
    return arr
def positions_get(symbol=None): return [p for p in _pos if symbol is None or p.symbol == symbol]
def order_send(req):
    if req["action"] == TRADE_ACTION_SLTP:
        for p in _pos:
            if p.ticket == req["position"]: p.sl, p.tp = req["sl"], req["tp"]
        return types.SimpleNamespace(retcode=TRADE_RETCODE_DONE)
    if "position" in req:
        p = next(x for x in _pos if x.ticket == req["position"]); _pos.remove(p)
        _deals.append(types.SimpleNamespace(position_id=p.ticket, entry=DEAL_ENTRY_OUT, price=req["price"], time=_srv(NOW[0]), reason=0, profit=0.0, swap=0.0, commission=0.0))
        return types.SimpleNamespace(retcode=TRADE_RETCODE_DONE, price=req["price"], order=0, comment="ok")
    _tick[0] += 1
    _pos.append(types.SimpleNamespace(ticket=_tick[0], symbol=req["symbol"], type=req["type"], volume=req["volume"], price_open=req["price"], sl=req["sl"], tp=req["tp"],
                                      time=_srv(NOW[0]), magic=req["magic"], comment=req["comment"], profit=0.0, swap=0.0))
    return types.SimpleNamespace(retcode=TRADE_RETCODE_DONE, price=req["price"], order=_tick[0], comment="ok")
def history_deals_get(a, b): return list(_deals)
def advance_sl_tp():
    """足が進んだとき SL/TP に触れた建玉を決済する（記録 simulate と同じ順: 窓→SL→TP）"""
    for p in list(_pos):
        s = _s(p.symbol); d = _bars(s); r = d.iloc[-2]; dr = 1 if p.type == 0 else -1
        bo, bh, bl = (float(r[c]) for c in ("open","high","low")); ao, ah, al = (float(r[f"ask_{c}"]) for c in ("open","high","low"))
        op, lo, hi = (bo, bl, bh) if dr == 1 else (ao, al, ah); x = None; why = 0
        if dr == 1:
            if op <= p.sl: x, why = op, DEAL_REASON_SL
            elif lo <= p.sl: x, why = p.sl, DEAL_REASON_SL
            elif hi >= p.tp: x, why = p.tp, DEAL_REASON_TP
        else:
            if op >= p.sl: x, why = op, DEAL_REASON_SL
            elif hi >= p.sl: x, why = p.sl, DEAL_REASON_SL
            elif lo <= p.tp: x, why = p.tp, DEAL_REASON_TP
        if x is not None:
            _pos.remove(p); _deals.append(types.SimpleNamespace(position_id=p.ticket, entry=DEAL_ENTRY_OUT, price=x, time=_srv(r["time"]) + 3599, reason=why, profit=0.0, swap=0.0, commission=0.0))
