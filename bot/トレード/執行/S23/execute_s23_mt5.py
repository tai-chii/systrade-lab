# -*- coding: utf-8 -*-
"""S23（BTC・ETH の日足の上昇トレンド買い）を MT5（Windows）で動かす執行層。既定は dry（発注しない）。2026-11-18 午後の自走（案・入れていない）。

流れ（毎時 :01:00 に 1 回・起動の直後と例外の後もすぐ 1 回・発注が通らなかった時間は 5 分おきに起き直す）:
  0. この bot の建玉（magic）なのに台帳に開いた行が無いもの（返事が失敗でも約定していた）を台帳に取り込む。台帳では開いているのに建玉も約定も無い行は void にする
  1. Binance の 1 時間足を取る（記録と同じ forward_s23.fetch・置き場所はこのフォルダの 足/。記録のデータには書かない）。最後の足が 1 時間より古ければ動かない
  2. signal_s23.decide() ＝ 記録のプログラム forward_s23.py をその足で走らせ、「最後に締まった営業日の終値で決めた保有」を目標にする。前に動いた判断の日より古い日の目標では動かない
  3. 取引時間の外（金 21:00〜日 21:00 UTC・記録の日足と同じ）なら何もしない。記録は週明けの始値で入る・出るので、bot も週明けの最初の回に動く
  4. 目標と建玉が違えば成行で入る／閉じる。SL・TP は置かない（記録に無い）。手で閉じた建玉は、目標が 1 のままなら次の回で入り直す（記録に合わせる作り）
  5. 記録の停止線（最高値から −30%）に達したら全部閉じ、以後は入らない。記録の「最高値から」は全期間の最小なので、一度達すると記録も bot も止まったまま（再開は規程を変えて別 ID にするとき）
  6. 台帳（台帳/trades.csv）に 1 保有 1 行。決済は MT5 の約定履歴から損益・スワップ・手数料（入口と出口の両方）を取り込む
記録との乖離は compare_s23.py（Mac）で見る。

使い方（PowerShell）:
  python execute_s23_mt5.py --once            # 今すぐ 1 回（dry）
  python execute_s23_mt5.py --loop            # 回し続ける（dry）
  python execute_s23_mt5.py --loop --live     # 実際に発注する（デモ口座だけ。config の expect_server が要る。実口座なら止まる）
設定: 同じフォルダの config.json（無ければ既定値で書き出す）。同時に 2 つは動かない（鍵ファイル 実行中.lock）。

S21 と同じ口座で動かしてよい作り: 建玉は magic（215023）で分ける。S21 の「合計 12 本」「1 銘柄 1 本」は S21 の magic だけを数えるので、
S23 の建玉は S21 の判断に効かない。効くのは証拠金だけなので、入る前に「必要証拠金 ≤ 余剰証拠金 × max_margin_frac」を確かめる。
2026-11-18 別の目の点検（Opus）の指摘 1〜13 を反映（各所の注記）。
"""
import argparse, datetime as dt, hashlib, hmac, json, os, sys, time, traceback
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import numpy as np, pandas as pd
try:
    import MetaTrader5 as mt5
except ImportError:
    sys.exit("MetaTrader5 が入っていません（Windows 専用）→ pip install MetaTrader5 pandas pyarrow")
for cand in [os.path.join(HERE, "..", "..", "..", "verification-lab", "tools", "mt5"), os.path.join(HERE, "mt5"),
             os.path.join(HERE, "..", "S21", "mt5")]:
    if os.path.exists(os.path.join(cand, "mt5_fetch.py")):
        sys.path.insert(0, os.path.abspath(cand)); break
import mt5_fetch as MF                                   # noqa: E402  名前解決（BTCUSD/ETHUSD の別名）・時刻の直し方
import signal_s23 as SG                                  # noqa: E402

LEDGER_DIR = os.path.join(HERE, "台帳"); LOG_DIR = os.path.join(HERE, "ログ"); H1_DIR = os.path.join(HERE, "足")
LEDGER = os.path.join(LEDGER_DIR, "trades.csv"); STATE = os.path.join(HERE, "状態.json"); CONFIG = os.path.join(HERE, "config.json")
STOP_FLAG = os.path.join(HERE, "停止.flag"); LOCK = os.path.join(HERE, "実行中.lock")
INTENT = os.path.join(HERE, "発注の控え.json")                                    # 発注の前に「どの判断の日の・何の注文か」を控える（返事が失敗でも約定した建玉を取り込むとき使う・2 回目の点検 3・4）
LOGIN_KEY = os.path.join(HERE, "..", "S21", "口座の照合.key")                      # S21 と同じ鍵（winnote の bot のフォルダだけ・送らない）
COIN_SYM = {"BTC": "BTCUSD", "ETH": "ETHUSD"}
WAKE_S = 60                                                                        # 毎時 :01:00（点検 6: PC の時計が進んでいても締まる前の足を使わない）
NO_RETRY = {10017, 10019, 10027}                                                   # 取引不可・資金不足・自動売買オフ: 起き直しても通らない（点検 10）
DEFAULT_CONFIG = {
    "magic": 215023,                 # S23 の注文の印（S21 は 215021）
    "notional_per_coin": 150000,     # 1 銘柄の名目（口座通貨）。記録は「半分ずつ・名目 1 倍」なので、元手 30 万円相当の半分。デモの記録との比べはリターン（率）で行うので額に依らない
    "max_margin_frac": 0.3,          # 入る前に 必要証拠金 ≤ 余剰証拠金 × これ（S21 の発注の余地を残す）
    "deviation_spread_mult": 1.0,    # 成行の許容滑り＝その時のスプレッド（ポイント）× これ（銘柄ごと・点検 9。BTC と ETH で幅を揃える）
    "deviation_points_min": 50,
    "retry_min": 5,                  # 発注が通らなかった・足が古いとき、何分後に起き直すか（同じ時間の中だけ）
    "fetch_tries": 3,                # Binance から取れないときの試行（forward_s23.fetch の中でも 4 回まで試す）
    "max_bar_age_h": 1,              # Binance の最後の確定足が「今の正時 − これ時間」より古ければ動かない（点検 2）
    "tz": "eet",                     # サーバー時間 → UTC（XM は eet。約定の時刻を UTC に直すだけに使う）
    "symbol_map": {},                # 例 {"BTCUSD": "BTCUSD#"}
    "coins": ["BTC", "ETH"],
    "check_mt5_bars": True,          # 業者の H1 でも同じ判断を計算してログに 1 行（判断には使わない・足の差の見張り）
    "mt5_path": None, "login": None, "password": None, "server": None,
    "expect_server": None,           # つないだ先のサーバー名。--live では必須（点検 8）。違えば売買せずに止まる
    "expect_login_hmac": None,       # 口座番号の HMAC（S21 と同じ鍵・同じ書き方）。None なら確かめない
}
LEDGER_COLS = ["id", "coin", "broker_sym", "decision_day", "entry_time", "entry_px", "lot", "notional", "ticket", "status",
               "exit_decision_day", "exit_time", "exit_px", "why", "ret", "profit", "swap", "commission", "note"]


def log(msg):
    os.makedirs(LOG_DIR, exist_ok=True)
    line = f"{dt.datetime.now(dt.timezone.utc):%Y-%m-%d %H:%M:%S} {msg}"
    print(line, flush=True)
    with open(os.path.join(LOG_DIR, f"run_{dt.datetime.now(dt.timezone.utc):%Y%m}.log"), "a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_config():
    if not os.path.exists(CONFIG):
        json.dump(DEFAULT_CONFIG, open(CONFIG, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    cfg = dict(DEFAULT_CONFIG); cfg.update(json.load(open(CONFIG, encoding="utf-8")))
    return cfg


def load_ledger():
    if os.path.exists(LEDGER):
        return pd.read_csv(LEDGER, dtype=str, keep_default_na=False)
    return pd.DataFrame(columns=LEDGER_COLS)


def save_ledger(L):
    """一時ファイルに書いてから置き換える（書きかけで落ちても台帳が壊れない・点検 13）。"""
    os.makedirs(LEDGER_DIR, exist_ok=True); tmp = LEDGER + ".tmp"
    L.reindex(columns=LEDGER_COLS).to_csv(tmp, index=False); os.replace(tmp, LEDGER)


def load_intent():
    try: return json.load(open(INTENT, encoding="utf-8"))
    except Exception: return {}


def save_intent(c, side, **kw):
    j = load_intent(); j.setdefault(c, {})[side] = dict(kw, time=str(pd.Timestamp.now(tz="UTC")))
    tmp = INTENT + ".tmp"; json.dump(j, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1); os.replace(tmp, INTENT)


def load_state():
    try: return json.load(open(STATE, encoding="utf-8"))
    except Exception: return {}


def single_instance():
    """同時に 2 つ動かない（点検 7）。鍵を取れなければ例外。戻り値の file を開いたままにする間だけ鍵が効く。"""
    f = open(LOCK, "a+")
    try:
        if os.name == "nt":
            import msvcrt; f.seek(0); msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl; fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        f.close(); raise RuntimeError("別の execute_s23_mt5.py が動いている（実行中.lock）。二重発注を避けるため止まる")
    return f


def login_mismatch(acc, expect, key_path=None):
    """口座の照合（S21 の execute_mt5.login_mismatch と同じ）。合えば None、合わなければ理由の文（番号もハッシュも入れない）"""
    if len(expect) < 16: return "config の expect_login_hmac が短すぎる（16 桁以上）"
    if not all(c in "0123456789abcdef" for c in expect) or len(expect) > 64: return "config の expect_login_hmac の書き方が違う（16 進の 16〜64 桁）"
    try: key = open(key_path or LOGIN_KEY, "rb").read().strip()
    except OSError: return "鍵のファイル 口座の照合.key が無い"
    if len(key) < 32: return "鍵が短すぎる"
    if acc is None: return "口座を読めない"
    got = hmac.new(key, str(getattr(acc, "login", "")).encode(), hashlib.sha256).hexdigest()
    return None if hmac.compare_digest(got[:len(expect)], expect) else "口座番号の照合が合わない"


# ---------- MT5 ----------
class Broker:
    def __init__(self, cfg, live):
        self.cfg, self.live = cfg, live
        kw = {k: v for k, v in dict(path=cfg["mt5_path"], login=cfg["login"], password=cfg["password"], server=cfg["server"]).items() if v}
        if not mt5.initialize(**kw):
            raise RuntimeError(f"MT5 に接続できない: {mt5.last_error()}（MT5 を起動して口座にログインしておく）")
        self.acc = self.check_server()
        if self.acc is None:
            raise RuntimeError("口座にログインしていない")
        self.demo = self.acc.trade_mode == 0
        all_names = {s.name for s in (mt5.symbols_get() or [])}; self.all_names = all_names
        self.names = {}
        for c in cfg["coins"]:
            n = MF.resolve(COIN_SYM[c], all_names, cfg["symbol_map"])
            if n is None:
                log(f"★ 見つからない銘柄: {COIN_SYM[c]}（config の symbol_map で指定）"); continue
            mt5.symbol_select(n, True); self.names[c] = n
        self.cur_off = None
        for n in self.names.values():
            self.cur_off = MF.detect_offset(n)
            if self.cur_off is not None:
                break
        ex = {c: getattr(mt5.symbol_info(n), "trade_exemode", None) for c, n in self.names.items()}
        log(f"接続: {self.acc.server}（{'デモ' if self.demo else '実口座'}）equity {self.acc.equity:,.0f} {self.acc.currency}・銘柄 {self.names}・執行方式 {ex}・サーバー時間のずれ {self.cur_off}")

    def check_server(self):
        """つないだ先のサーバー名と口座番号の照合（S21 と同じ）。違えば接続を切ってから例外。"""
        acc = mt5.account_info(); exp = self.cfg.get("expect_server")
        if self.live and acc is not None and acc.trade_mode != 0:                     # 2 回目の点検 1: 繋ぎ直し・毎回の確かめでも実口座なら止める（起動時だけでなく）
            try: mt5.shutdown()
            except Exception: pass
            raise RuntimeError("実口座に繋がっている（trade_mode が 0 でない）。S23 の執行はデモだけ。売買しない")
        if exp and (acc is None or acc.server != exp):
            try: mt5.shutdown()
            except Exception: pass
            raise RuntimeError(f"つないだ先が違う: {getattr(acc, 'server', '口座を読めない')}（config の expect_server は {exp}）。売買しない")
        eh = str(self.cfg.get("expect_login_hmac") or "").strip().lower()
        if eh:
            why = login_mismatch(acc, eh)
            if why:
                try: mt5.shutdown()
                except Exception: pass
                raise RuntimeError(f"つないだ口座が違う（{why}）。売買しない")
        return acc

    def utc(self, server_epoch):
        return MF.to_utc(pd.Series(server_epoch), self.cfg["tz"], self.cur_off)

    def positions(self):
        """この bot の建玉（magic）。取れない（None かつ last_error が成功でない）ときは例外（S21 の監査A の 4 と同じ）。"""
        P = mt5.positions_get()
        if P is None:
            e = mt5.last_error()
            if not (e and e[0] in (0, 1)):
                raise RuntimeError(f"建玉を取れない（positions_get が None・{e}）→ 繋ぎ直す")
            P = ()
        return [p for p in P if p.magic == self.cfg["magic"]]

    def deals_of(self, ticket):
        """position_id == ticket の約定（IN・OUT とも）。"""
        D = mt5.history_deals_get(position=int(ticket)) if str(ticket).isdigit() else None
        if D is None:                                                                # 古い端末で position= が効かないとき
            frm = dt.datetime.now() - dt.timedelta(days=400)
            D = [d for d in (mt5.history_deals_get(frm, dt.datetime.now() + dt.timedelta(days=1)) or []) if str(d.position_id) == str(ticket)]
        return list(D or [])

    def filling(self, info):
        fm = info.filling_mode
        if fm & 1: return mt5.ORDER_FILLING_FOK
        if fm & 2: return mt5.ORDER_FILLING_IOC
        return mt5.ORDER_FILLING_RETURN

    def deviation(self, info):
        return int(max(self.cfg["deviation_points_min"], (info.spread or 0) * float(self.cfg["deviation_spread_mult"])))

    def fx_to_account(self, cur):
        acct = self.acc.currency
        if cur == acct:
            return 1.0
        cands = [(cur + acct, False), (acct + cur, True)]
        for pair, inv in list(cands):
            n = MF.resolve(pair, self.all_names, {})
            if n and n != pair: cands.append((n, inv))
        for name, inv in cands:
            info = mt5.symbol_info(name)
            if info is None:
                continue
            mt5.symbol_select(name, True); t = mt5.symbol_info_tick(name)
            if t is not None and t.bid > 0:
                return (1.0 / t.ask) if inv else t.bid
        return None

    def lot_for(self, c):
        """名目 notional_per_coin（口座通貨）÷（価格 × 契約サイズ × 損益通貨→口座通貨）。最小ロット未満は最小ロットへ切り上げて note に残す。"""
        name = self.names[c]; info = mt5.symbol_info(name); tick = mt5.symbol_info_tick(name)
        if info is None or tick is None or tick.ask <= 0:
            return None, None, "値段が取れない"
        rate = self.fx_to_account(info.currency_profit)
        if rate is None:
            return None, None, f"{info.currency_profit}→{self.acc.currency} のレートが取れない"
        per_lot = tick.ask * info.trade_contract_size * rate
        if per_lot <= 0:
            return None, None, "契約サイズが取れない"
        want = float(self.cfg["notional_per_coin"]); lot = want / per_lot
        step = info.volume_step or 0.01; lot_r = np.floor(lot / step + 1e-9) * step; note = ""
        if lot_r < info.volume_min:
            lot_r = info.volume_min; note = f"最小ロットに切り上げ（計算 {lot:.4f}・名目 {lot_r * per_lot:,.0f} {self.acc.currency}）"
        if lot_r > info.volume_max:
            lot_r = info.volume_max; note = "最大ロットに切り下げ"
        return float(round(lot_r, 8)), float(lot_r * per_lot), note

    def notional_of(self, p):
        """建玉の名目（口座通貨）。取れなければ None。"""
        try:
            info = mt5.symbol_info(p.symbol); rate = self.fx_to_account(info.currency_profit)
            return float(p.volume * p.price_open * info.trade_contract_size * rate) if rate else None
        except Exception:
            return None

    def margin_ok(self, c, lot):
        name = self.names[c]; tick = mt5.symbol_info_tick(name); acc = mt5.account_info()
        need = mt5.order_calc_margin(mt5.ORDER_TYPE_BUY, name, lot, tick.ask) if tick is not None else None
        if need is None or acc is None:
            return False, f"必要証拠金を計算できない（{mt5.last_error()}）"
        lim = acc.margin_free * float(self.cfg["max_margin_frac"])
        return need <= lim, f"必要証拠金 {need:,.0f}・余剰 {acc.margin_free:,.0f} × {self.cfg['max_margin_frac']}"

    def buy(self, c, lot, comment, known):
        """成行の買い。返事に依らず、約定は建玉で確かめる（点検 1・3: 返事が失敗でも約定している・PLACED でも約定しない形がある）。
        known は台帳に既にある ticket の集合（新しく現れた建玉だけを今回の約定とみなす）。"""
        name = self.names[c]; info = mt5.symbol_info(name); tick = mt5.symbol_info_tick(name)
        req = dict(action=mt5.TRADE_ACTION_DEAL, symbol=name, volume=lot, type=mt5.ORDER_TYPE_BUY, price=tick.ask,
                   deviation=self.deviation(info), magic=self.cfg["magic"], comment=comment[:20],
                   type_time=mt5.ORDER_TIME_GTC, type_filling=self.filling(info))
        if not self.live:
            return dict(ok=True, dry=True, price=tick.ask, ticket="", volume=lot, spread_pts=info.spread, retcode=None)
        res = mt5.order_send(req); rc = getattr(res, "retcode", None)
        new = []
        for k in range(4):                                                          # 返事の後に建玉が現れるまで少し待つ（最大 3 秒）
            new = [p for p in (mt5.positions_get(symbol=name) or []) if p.magic == self.cfg["magic"] and str(p.ticket) not in known]
            if new or rc in NO_RETRY or (res is not None and rc not in (mt5.TRADE_RETCODE_DONE, mt5.TRADE_RETCODE_PLACED, mt5.TRADE_RETCODE_DONE_PARTIAL)):
                break
            time.sleep(1)
        if new:
            p = new[-1]
            return dict(ok=True, dry=False, price=p.price_open, ticket=str(p.ticket), volume=float(p.volume), spread_pts=info.spread, retcode=rc,
                        note="" if rc in (mt5.TRADE_RETCODE_DONE, mt5.TRADE_RETCODE_DONE_PARTIAL) else f"返事 {rc} でも約定していた")
        return dict(ok=False, dry=False, retcode=rc, msg=getattr(res, "comment", str(mt5.last_error())) if res is not None else f"返事なし（{mt5.last_error()}）")

    def close(self, p, why):
        name = p.symbol; info = mt5.symbol_info(name); tick = mt5.symbol_info_tick(name)
        req = dict(action=mt5.TRADE_ACTION_DEAL, symbol=name, volume=p.volume, type=mt5.ORDER_TYPE_SELL, position=p.ticket, price=tick.bid,
                   deviation=self.deviation(info), magic=self.cfg["magic"], comment=why[:20],
                   type_time=mt5.ORDER_TIME_GTC, type_filling=self.filling(info))
        if not self.live:
            return dict(ok=True, dry=True, price=tick.bid)
        res = mt5.order_send(req); rc = getattr(res, "retcode", None)
        P2 = mt5.positions_get(symbol=name)                                                # 返事に依らず建玉が消えたかで決める。一覧を取れなければ「分からない」＝失敗扱い（2 回目の点検 4）
        gone = P2 is not None and not any(x.ticket == p.ticket for x in P2)
        return dict(ok=gone, dry=False, price=getattr(res, "price", None), retcode=rc, msg=getattr(res, "comment", "") if res is not None else "返事なし")

    def h1_frame(self, c, now, n=2600):
        """業者の H1（bid）を Binance の形に直す（照合だけに使う）。今できている足は除く。"""
        r = mt5.copy_rates_from_pos(self.names[c], mt5.TIMEFRAME_H1, 0, n)
        if r is None or len(r) < 2:
            return None
        d = pd.DataFrame(r).sort_values("time").reset_index(drop=True)
        t = self.utc(d["time"]).reset_index(drop=True)
        out = pd.DataFrame({"time": t, "open": d["open"].astype(float), "high": d["high"].astype(float), "low": d["low"].astype(float),
                            "close": d["close"].astype(float), "volume": d["tick_volume"].astype(float), "qvol": 0.0, "trades": 0, "taker_base": 0.0})
        out = out[out["time"] + pd.Timedelta(hours=1) <= now].reset_index(drop=True)
        need = now.floor("h") - pd.Timedelta(hours=int(self.cfg["max_bar_age_h"]))      # 2026-11-18 配った日: 銘柄を選んだ直後は MT5 が古い履歴（10-30 まで）を返し、照合が ★ 違う になった
        if len(out) == 0 or out["time"].max() < need:
            return None
        return out


# ---------- 判断の材料 ----------
_FETCHED = {"at": None}


def get_signal(cfg, now, refetch=True):
    """Binance から取り直して記録のプログラムで判断。取れない・走らない・足が古い回は (None, 理由)。
    refetch=False（同じ時間の起き直し）は、15 分以内に取った足が今の正時まで揃っていれば取り直さない（点検 10 の連打を減らす）。"""
    fresh = _FETCHED["at"] is not None and now - _FETCHED["at"] < pd.Timedelta(minutes=15)
    for k in range(int(cfg["fetch_tries"])):
        try:
            if refetch or not fresh:
                SG.fetch_to(H1_DIR); _FETCHED["at"] = now
            sig = SG.decide(H1_DIR, now - pd.Timedelta(seconds=60))                 # 2 回目の点検 9: PC の時計が進んでいても締まる前の足を使わない（起動の直後・例外の後のすぐの回も）
        except SystemExit as e:
            return None, f"判断の計算が終了した（{e}）"
        except Exception as e:
            log(f"判断の材料を取れない（{k + 1} 回目・{type(e).__name__}: {e}）"); time.sleep(10 * (k + 1)); continue
        need = now.floor("h") - pd.Timedelta(hours=int(cfg["max_bar_age_h"]))
        old = {c: t for c, t in sig["last_h1"].items() if pd.Timestamp(t) < need}
        if old:                                                                      # 点検 2: 途中までしか返らないと前の日の判断に戻る
            if k < int(cfg["fetch_tries"]) - 1:
                time.sleep(10 * (k + 1)); refetch = True; continue
            return None, f"Binance の足が古い（{old}・要るのは {need} 以降）"
        return sig, None
    return None, "Binance から足を取れない"


def mt5_check(B, sig, now):
    """業者の H1 で同じ判断を出して、記録の足（Binance）の判断と比べた 1 行を書く（判断には使わない）。"""
    import tempfile, shutil
    tmp = tempfile.mkdtemp(prefix="s23_mt5_")
    try:
        for c in B.names:
            d = B.h1_frame(c, now)
            if d is None:                                                            # 履歴の取り寄せ中は古い足が返る。少し待って 1 回だけ取り直す
                time.sleep(5); d = B.h1_frame(c, now)
            if d is None:
                log(f"照合 {c}: 業者の足が取れないか古い（MT5 が履歴を取り寄せている途中の形・判断には使っていない）"); return
            d.to_parquet(os.path.join(tmp, f"{c}.parquet"), index=False)
        for c in [c for c in SG.COINS if c not in B.names]:                          # 片方しか無い業者でも走らせる（無い方は Binance の足で埋める＝比べない）
            pd.read_parquet(os.path.join(H1_DIR, f"{c}.parquet")).to_parquet(os.path.join(tmp, f"{c}.parquet"), index=False)
        m = SG.decide(tmp, now); parts = []
        for c in B.names:
            a, b = sig["coins"][c], m["coins"][c]
            parts.append(f"{c} 記録の足 {int(a['保有'])}（{a['日']} 終値 {a['終値']:.2f}・60 本前 {a['六十本前']:.2f}）業者の足 {int(b['保有'])}（{b['日']} 終値 {b['終値']:.2f}・60 本前 {b['六十本前']:.2f}）"
                         + ("" if a["保有"] == b["保有"] and a["日"] == b["日"] else " ★ 違う"))
        log("照合 " + " / ".join(parts))
    except Exception as e:
        log(f"照合を書けない（{type(e).__name__}: {e}）")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------- 1 回の実行 ----------
def reconcile(B, L, P, now, state):
    """台帳と建玉の突き合わせ。① 決済の取り込み ② 建玉も約定も無い開いた行は void ③ 台帳に無い建玉を取り込む（点検 1・3）。"""
    pos_tk = {str(p.ticket) for p in P}; intents = load_intent()
    for i, row in L[L["status"] == "open"].iterrows():
        tk = row["ticket"]
        if tk in pos_tk:
            continue
        D = B.deals_of(tk) if tk else []
        outs = [d for d in D if d.entry != mt5.DEAL_ENTRY_IN]; ins = [d for d in D if d.entry == mt5.DEAL_ENTRY_IN]   # 出口は OUT・INOUT・OUT_BY（相殺）も（2 回目の点検 5）
        if outs:
            o = outs[-1]; xp = float(o.price)
            L.loc[i, ["status", "exit_time", "exit_px", "ret", "profit", "swap", "commission"]] = [str(v) for v in [
                "closed", B.utc(pd.Series([int(o.time)])).iloc[0], xp, xp / float(row["entry_px"]) - 1,
                sum(x.profit for x in outs), sum(x.swap for x in D), sum(x.commission for x in D)]]           # 手数料・スワップは入口と出口の両方（点検 13）
            if not L.loc[i, "why"]:
                it = (intents.get(row["coin"]) or {}).get("out")                       # 2 回目の点検 4: bot が閉じに行った控えがあり、決済が入った後なら bot の決済
                if it and pd.Timestamp(it["time"]) >= pd.Timestamp(row["entry_time"]) and getattr(o, "magic", B.cfg["magic"]) == B.cfg["magic"]:
                    L.loc[i, ["why", "exit_decision_day"]] = [it["why"] + "（返事は失敗でも閉じていた）", it["day"]]
                else:
                    L.loc[i, "why"] = "手動/業者"
            log(f"決済 {row['coin']} {L.loc[i, 'why']} 率 {float(L.loc[i, 'ret']) * 100:+.2f}% スワップ {float(L.loc[i, 'swap']):,.0f}")
        elif not ins:
            L.loc[i, ["status", "note"]] = ["void", (row["note"] + "・" if row["note"] else "") + f"建玉も約定も無い（{now:%m-%d %H:%M} に void）"]
            log(f"★ 台帳の {row['coin']}（ticket {tk}）は建玉も約定も無いので void にした（PLACED のまま約定しなかった等）")
    known = set(L.loc[L["status"] == "open", "ticket"])
    for p in P:
        if str(p.ticket) in known:
            continue
        c = next((k for k, v in B.names.items() if v == p.symbol), p.symbol)
        it = (intents.get(c) or {}).get("in"); t_open = B.utc(pd.Series([int(p.time)])).iloc[0]
        mine = it and abs((pd.Timestamp(it["time"]) - t_open).total_seconds()) < 3600 and p.magic == B.cfg["magic"]
        day_ = it["day"] if mine else (state.get("動いた判断の日") or {}).get(c, "")     # 2 回目の点検 3: 発注の控えの判断の日を使う（無ければ前に動いた日）
        L = pd.concat([L, pd.DataFrame([dict(id=f"{day_}_{c}_取り込み_{p.ticket}", coin=c, broker_sym=p.symbol, decision_day=day_,
                                             entry_time=str(t_open), entry_px=p.price_open, lot=p.volume, notional=B.notional_of(p) or "",
                                             ticket=str(p.ticket), status="open",
                                             note="後から取り込み（" + ("発注の返事は失敗でも約定していた" if mine else "手で建てた・控えが無い") + "）")]).astype(str)], ignore_index=True)
        log(f"★ 台帳に無い建玉を取り込んだ: {c} ticket {p.ticket} lot {p.volume}（返事が失敗でも約定していた・手で建てた等）")
    return L


def run_once(B, cfg, live, now=None, refetch=True):
    """戻り値 (状態, 起き直しが要るか)。"""
    now = now or pd.Timestamp.now(tz="UTC")
    if cfg.get("expect_server") or cfg.get("expect_login_hmac"): B.check_server()
    P = B.positions()                                                                # 取れない回はここで止まる（判断の前）
    state = load_state(); L = load_ledger()
    if live:
        L = reconcile(B, L, P, now, state); save_ledger(L)
    sig, why = get_signal(cfg, now, refetch)
    held = {c: [p for p in P if p.symbol == n] for c, n in B.names.items()}
    st = dict(更新=str(now), live=live, 口座=B.acc.server, 保有={c: len(v) for c, v in held.items()}, 動いた判断の日=state.get("動いた判断の日") or {})
    if sig is None:
        log(f"★ この回は何もしない（{why}）・建玉はそのまま")
        st["判断"] = "取れない"; st["理由"] = why; json.dump(st, open(STATE, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
        return st, True
    if cfg.get("check_mt5_bars", True):
        mt5_check(B, sig, now)
    rec = sig["record"]; stopped = bool(rec["停止"]) or os.path.exists(STOP_FLAG)
    if rec["停止"] and not os.path.exists(STOP_FLAG):
        open(STOP_FLAG, "w", encoding="utf-8").write(f"{now} 記録の停止線: {rec['停止']}\n")
        log(f"★ 記録の停止線に達した（{rec['停止']}）→ 全部閉じて以後は入らない（記録も止まったまま。再開は規程を変えて別 ID にするとき）")
    retry = False
    tgt = {c: (False if stopped else bool(sig["coins"][c]["保有"])) for c in B.names}
    day = {c: sig["coins"][c]["日"] for c in B.names}; acted = dict(st["動いた判断の日"])
    if sig["closed"]:
        log(f"取引時間の外（記録は週明けの始値で動く）: 目標 {tgt}・保有 {st['保有']}")
    else:
        known = set(L.loc[L["status"] == "open", "ticket"])
        for c in B.names:
            have = held[c]
            if acted.get(c) and day[c] < acted[c]:                                   # 点検 2: 前に動いた日より古い判断では動かない
                log(f"★ 見送り {c}: 判断の日 {day[c]} が前に動いた日 {acted[c]} より古い（足の取り違えの恐れ）"); retry = True; continue
            if len(have) > 1:
                log(f"★ {c} の建玉が {len(have)} 本ある（1 本のはず）→ 入らない。多い分は人が見る")
            if tgt[c] and not have:
                if len(L) and ((L["coin"] == c) & (L["status"] == "open")).any():
                    log(f"★ 見送り {c}: 台帳では保有が開いているのに建玉が見えない（次の回の突き合わせで決済の取り込みか void になる）"); retry = True; continue
                lot, notional, lnote = B.lot_for(c)
                if lot is None:
                    log(f"見送り {c} 買い: {lnote}"); retry = True; continue
                ok_m, mnote = B.margin_ok(c, lot)
                if not ok_m:
                    log(f"★ 見送り {c} 買い: 証拠金が足りない（{mnote}）"); continue
                if live: save_intent(c, "in", day=day[c])
                r = B.buy(c, lot, f"S23 {c} {day[c][5:].replace('-', '')}", known)
                log(f"{'[dry] ' if not live else ''}入る {c} 買い lot {lot} 名目 {notional:,.0f}（判断の日 {day[c]}）→ {r} {lnote}")
                if not r["ok"]:
                    retry = retry or r.get("retcode") not in NO_RETRY
                    if r.get("retcode") in NO_RETRY: log(f"★ {c} の買いは起き直しても通らない形（retcode {r.get('retcode')}）→ 次の正時まで待つ")
                else:
                    acted[c] = day[c]
                    if live:
                        vol = r.get("volume", lot); notional_r = notional * vol / lot if lot else notional
                        L = pd.concat([L, pd.DataFrame([dict(id=f"{day[c]}_{c}_{now:%m%d%H%M}", coin=c, broker_sym=B.names[c], decision_day=day[c], entry_time=str(now),
                                                             entry_px=r["price"], lot=vol, notional=notional_r, ticket=r["ticket"], status="open",
                                                             note="・".join(x for x in [lnote, r.get("note", ""), "部分約定" if vol < lot else ""] if x))]).astype(str)], ignore_index=True)
                        known.add(r["ticket"]); save_ledger(L)
            elif not tgt[c] and have:
                why = "停止線" if stopped else "上昇トレンドの終わり"
                for p in have:
                    if live: save_intent(c, "out", day=day[c], why=why)
                    r = B.close(p, why)
                    log(f"{'[dry] ' if not live else ''}閉じる {c}（判断の日 {day[c]}・{why}）lot {p.volume} → {r}")
                    if not r["ok"]:
                        retry = retry or r.get("retcode") not in NO_RETRY
                    elif live:
                        m = L["ticket"].astype(str) == str(p.ticket)
                        L.loc[m, "why"] = why; L.loc[m, "exit_decision_day"] = day[c]
                if not any(x.symbol == B.names[c] for x in B.positions()):             # 全部閉じられたときだけ、この日の判断は済み
                    acted[c] = day[c]
                if live: save_ledger(L)
            else:
                acted[c] = day[c]                                                    # 目標と建玉が合っている＝この日の判断は済み
    if live: save_ledger(L)
    try: now_held = {c: len([p for p in B.positions() if p.symbol == n]) for c, n in B.names.items()}
    except Exception: now_held = st["保有"]
    cl = L[L["status"] == "closed"]
    st.update(判断の日=day, 目標=tgt, 保有=now_held, 取引時間の外=sig["closed"], 停止=stopped, 動いた判断の日=acted,
              記録と同じ計算=dict(通算=rec["通算"], 最高値から=rec["最高値から"], 記録日数=rec["記録日数"]),
              決済済み=int(len(cl)), 率の合計=float(cl["ret"].astype(float).sum()) if len(cl) else 0.0,
              スワップの合計=float(cl["swap"].astype(float).sum()) if len(cl) else 0.0, 最後の足=sig["last_h1"], 発注の失敗=retry)
    json.dump(st, open(STATE, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    return st, retry


def next_wake(now, retry, retry_min):
    nxt = now.floor("h") + pd.Timedelta(hours=1, seconds=WAKE_S)
    if retry:
        r = now + pd.Timedelta(minutes=retry_min)
        if r < nxt - pd.Timedelta(seconds=60):
            return r, True
    return nxt, False


def connect(cfg, live, once):
    """起動の接続。--loop では MT5 が起きるまで 60 秒おきに試す（ログオン時のタスクが 1 回で終わらないように・点検 4）。"""
    while True:
        try:
            return Broker(cfg, live)
        except Exception as e:
            log(f"★ 起動できない: {e}")
            if once: raise
            time.sleep(60)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true"); ap.add_argument("--loop", action="store_true")
    ap.add_argument("--live", action="store_true", help="実際に発注する（付けなければ dry）")
    a = ap.parse_args(); cfg = load_config(); live = a.live
    if live and not cfg.get("expect_server"):
        sys.exit("--live には config.json の expect_server（例 \"XMTrading-MT5 3\"）が要る（つないだ先の取り違えを防ぐ・点検 8）")
    lock = single_instance()                                                         # noqa: F841  開いたままにする
    once = a.once or not a.loop
    B = connect(cfg, live, once)
    if live and not B.demo:
        sys.exit("実口座に接続している。S23 の執行はデモだけ（実弾は taichi の承認の後）")
    if once:
        st, _ = run_once(B, cfg, live); print(json.dumps(st, ensure_ascii=False, indent=1, default=str)); return
    last_hourly, retry, extra = None, False, False
    while True:
        try:
            now = pd.Timestamp.now(tz="UTC")
            if last_hourly is not None and now.floor("h") <= last_hourly:            # その時間の回は済み → 次の :01:00 か起き直し
                nxt, extra = next_wake(now, retry, cfg["retry_min"])
                time.sleep(max(1, (nxt - pd.Timestamp.now(tz="UTC")).total_seconds()))
                now = pd.Timestamp.now(tz="UTC")
                if now.floor("h") > last_hourly: extra = False
            st, retry = run_once(B, cfg, live, now=now, refetch=not extra)          # 起動の直後・例外の後・正時をまたいだ回はすぐ回す（何度回しても同じ結果になる作り）
            last_hourly = now.floor("h")
            log(f"済 判断 {st.get('判断の日')} 目標 {st.get('目標')} 保有 {st.get('保有')} 外 {st.get('取引時間の外')}" + (" ★ 起き直す" if retry else ""))
        except KeyboardInterrupt:
            break
        except Exception:
            log("エラー:\n" + traceback.format_exc()); time.sleep(60); retry = False
            last_hourly = None                                                       # 繋ぎ直したらすぐ回す（点検 4）
            B = connect(cfg, live, once=False)


if __name__ == "__main__":
    main()
