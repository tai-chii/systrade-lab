"""S23 の試験用の偽 MetaTrader5（配布しない）。Binance の 1 時間足を XM 風（サーバー時間 EET・bid＝Binance の値・ask＝bid＋spread）で返す。
環境変数: MOCK_H1（BTC.parquet・ETH.parquet のフォルダ）・MOCK_NOW（UTC）・MOCK_REAL=1（実口座のふり）・MOCK_MARGIN_FREE（余剰証拠金）
今の値段＝今できている足の始値（記録の exec_px と同じ値になる）。スワップは 1 晩 0.0694%（XM の BTCUSD の仕様・2026-11-01）を決済時にまとめて付ける。"""
import numpy as np, pandas as pd, os, types
H1 = os.environ.get("MOCK_H1"); NOW = [pd.Timestamp(os.environ.get("MOCK_NOW", "2026-11-18 00:00+00:00")).tz_convert("UTC")]
TIMEFRAME_M1=1; TIMEFRAME_M5=5; TIMEFRAME_M15=15; TIMEFRAME_M30=30; TIMEFRAME_H4=16388; TIMEFRAME_D1=16408; TIMEFRAME_W1=32769; TIMEFRAME_MN1=49153; TIMEFRAME_H1 = 16385; TRADE_ACTION_DEAL = 1; TRADE_ACTION_SLTP = 6; ORDER_TYPE_BUY = 0; ORDER_TYPE_SELL = 1
ORDER_TIME_GTC = 0; ORDER_FILLING_FOK = 0; ORDER_FILLING_IOC = 1; ORDER_FILLING_RETURN = 2
TRADE_RETCODE_DONE = 10009; TRADE_RETCODE_PLACED = 10008; TRADE_RETCODE_DONE_PARTIAL = 10010; TRADE_RETCODE_MARKET_CLOSED = 10018
POSITION_TYPE_BUY = 0; POSITION_TYPE_SELL = 1; DEAL_ENTRY_IN = 0; DEAL_ENTRY_OUT = 1; DEAL_REASON_SL = 4; DEAL_REASON_TP = 5
NAMES = {"BTC": "BTCUSD", "ETH": "ETHUSD"}; SPREAD = {"BTC": 40.0, "ETH": 3.0}; SWAP_DAY = 0.000694
USDJPY = 155.0
_data = {}; _pos = []; _deals = []; _tick = [1000]; SENT = []; FAIL_NEXT = [0]; EXTRA = []
def _eu_dst(t):
    t = pd.Timestamp(t).tz_convert(None) if pd.Timestamp(t).tzinfo else pd.Timestamp(t)
    y = t.year
    s = pd.Timestamp(f"{y}-03-31") - pd.Timedelta(days=(pd.Timestamp(f"{y}-03-31").weekday() + 1) % 7) + pd.Timedelta(hours=1)
    e = pd.Timestamp(f"{y}-10-31") - pd.Timedelta(days=(pd.Timestamp(f"{y}-10-31").weekday() + 1) % 7) + pd.Timedelta(hours=1)
    return s <= t < e
def _srv(t): return int(pd.Timestamp(t).timestamp()) + (3 if _eu_dst(t) else 2) * 3600
def _load(c):
    if c not in _data: _data[c] = pd.read_parquet(os.path.join(H1, f"{c}.parquet"))
    return _data[c]
def _c(n): return next((c for c, v in NAMES.items() if v == n), None)
def initialize(**kw): return True
def shutdown(): return True
def last_error(): return (1, "Success")
ACC_SERVER = ["Mock-Demo"]
def account_info():
    mf = float(os.environ.get("MOCK_MARGIN_FREE", "9000000"))
    return types.SimpleNamespace(server=ACC_SERVER[0], login=1, trade_mode=2 if os.environ.get("MOCK_REAL") else 0, equity=10_000_000.0, balance=10_000_000.0, currency="JPY", margin_free=mf)
def symbols_get(): return [types.SimpleNamespace(name=n) for n in list(NAMES.values()) + ["USDJPY"] + EXTRA]
def symbol_select(n, f): return True
def symbol_info(n):
    if n == "USDJPY": return types.SimpleNamespace(point=0.001, digits=3, currency_profit="JPY", trade_contract_size=100000.0, volume_min=0.01, volume_max=50, volume_step=0.01, filling_mode=1, spread=20)
    c = _c(n)
    if c is None: return None
    return types.SimpleNamespace(point=0.01, digits=2, volume_min=0.01, volume_max=80, volume_step=0.01, filling_mode=1, spread=int(SPREAD[c] / 0.01),
                                 currency_profit="USD", trade_contract_size=1.0)
def _bars(c):
    d = _load(c); return d[d["time"] <= NOW[0]]                                   # 今できている足（始値だけが決まっている）を含む
def symbol_info_tick(n):
    if n == "USDJPY": return types.SimpleNamespace(time=_srv(NOW[0]), bid=USDJPY, ask=USDJPY + 0.02)
    c = _c(n); d = _bars(c)
    if len(d) == 0: return types.SimpleNamespace(time=0, bid=0, ask=0)
    r = d.iloc[-1]; return types.SimpleNamespace(time=_srv(r["time"]), bid=float(r["open"]), ask=float(r["open"]) + SPREAD[c])
STALE_H = [0]
def copy_rates_from_pos(n, tf, start, count):
    c = _c(n); d = _bars(c)
    d = d[d["time"] + pd.Timedelta(hours=1) <= NOW[0] - pd.Timedelta(hours=STALE_H[0])].tail(count)   # 確定足だけ（今の足を含めない業者の形）。STALE_H: 履歴の取り寄せ中の古い足の形
    if len(d) == 0: return None
    return np.array([(_srv(r.time), r.open, r.high, r.low, r.close, int(r.volume), int(SPREAD[c] / 0.01), 0) for r in d.itertuples()],
                    dtype=[("time", "<i8"), ("open", "<f8"), ("high", "<f8"), ("low", "<f8"), ("close", "<f8"), ("tick_volume", "<u8"), ("spread", "<i4"), ("real_volume", "<u8")])
def order_calc_margin(typ, n, lot, price): return lot * price * USDJPY / 2.0       # 仮に 2 倍（暗号資産の証拠金率は業者で確かめる）
def positions_get(symbol=None): return tuple(p for p in _pos if symbol is None or p.symbol == symbol)
GHOST = [0]      # 次の新規の注文は約定するが、返事は None（通信の瞬断の形・点検 1）
PARTIAL = [None] # 次の新規の注文はこの量だけ約定する（部分約定・点検 13）
PLACED_NOFILL = [0]  # 次の新規の注文は PLACED を返すが約定しない（点検 3）
RETCODE = [None]     # 次の注文はこの retcode で断る（10027 など・点検 10）
def order_send(req):
    SENT.append(dict(req))
    if RETCODE[0]:
        rc = RETCODE[0]; RETCODE[0] = None; return types.SimpleNamespace(retcode=rc, price=0.0, order=0, deal=0, comment="refused")
    if FAIL_NEXT[0] > 0:
        FAIL_NEXT[0] -= 1; return types.SimpleNamespace(retcode=TRADE_RETCODE_MARKET_CLOSED, price=0.0, order=0, deal=0, comment="Market closed")
    if "position" in req:
        p = next(x for x in _pos if x.ticket == req["position"]); _pos.remove(p)
        nights = max(0, (NOW[0].floor("D") - pd.Timestamp(p._open_utc).floor("D")).days)
        sw = -SWAP_DAY * nights * p.price_open * p.volume * USDJPY
        prof = (req["price"] - p.price_open) * p.volume * USDJPY
        _tick[0] += 1
        _deals.append(types.SimpleNamespace(ticket=_tick[0], position_id=p.ticket, entry=DEAL_ENTRY_OUT, price=req["price"], time=_srv(NOW[0]), reason=0, profit=prof, swap=sw, commission=-1.0, volume=p.volume, magic=p.magic))
        return types.SimpleNamespace(retcode=TRADE_RETCODE_DONE, price=req["price"], order=0, deal=_tick[0], comment="ok")
    if PLACED_NOFILL[0]:
        PLACED_NOFILL[0] = 0; _tick[0] += 1; return types.SimpleNamespace(retcode=TRADE_RETCODE_PLACED, price=0.0, order=_tick[0], deal=0, comment="placed")
    _tick[0] += 1; vol = PARTIAL[0] or req["volume"]; PARTIAL[0] = None
    p = types.SimpleNamespace(ticket=_tick[0], symbol=req["symbol"], type=req["type"], volume=vol, price_open=req["price"],
                              time=_srv(NOW[0]), magic=req["magic"], comment=req["comment"], profit=0.0, swap=0.0, _open_utc=NOW[0])
    _pos.append(p); _tick[0] += 1
    _deals.append(types.SimpleNamespace(ticket=_tick[0], position_id=p.ticket, entry=DEAL_ENTRY_IN, price=req["price"], time=_srv(NOW[0]), reason=0, profit=0.0, swap=0.0, commission=-1.0, volume=vol, magic=p.magic))
    if GHOST[0]:
        GHOST[0] = 0; return None
    return types.SimpleNamespace(retcode=TRADE_RETCODE_DONE if vol == req["volume"] else TRADE_RETCODE_DONE_PARTIAL, price=req["price"], order=p.ticket, deal=_tick[0], comment="ok")
def history_deals_get(a=None, b=None, position=None, **kw): return tuple(d for d in _deals if position is None or d.position_id == position)
