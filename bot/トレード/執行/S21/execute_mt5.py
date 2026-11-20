# -*- coding: utf-8 -*-
"""S21 を MT5（Windows）で動かす執行層。毎時、確定した H1 足で判断し、成行＋SL＋TP を出す。既定は dry（発注しない）。

流れ（1 時間に 1 回・足の確定直後）:
  1. MT5 から 19 銘柄の H1 を取り（bid のみ）、記録と同じ形（ask_ 列つき parquet）に直して一時フォルダへ書く。
     ask_ のスプレッドは XM の値でなく spr_ref.json（Dukascopy の銘柄 × NY 時間の時ごとの中央値・make_spr_ref.py）を入れる。
     判断の入力 spr_R を記録に揃えるため（2026-11-04 taichi「A: 記録に揃える」・監査B の 1）。発注・SL/TP・R は XM の実際の値段のまま
  2. signal_s21.decide() で「最後の確定足」の判断を出す（記録 forward_s21.py と同じ関数・同じ凍結モデル）
  3. 出口の管理: 120 本の時間切れ → 成行で閉じる。週末（24 時間以上の休み）の前 → 最後の足が閉まる 10 分前に閉じる（この起床では決済だけ行い、入口は回さない）
  4. 入口: 同時 1 本／週 10 回／合計リスク上限（1 回のリスク × 12 本）／再開後 1 本目は入らない、を守って成行＋SL＋TP
  5. 台帳（台帳/trades.csv）に記録。決済は MT5 の約定履歴から取り込む
記録（Dukascopy）との乖離は compare_record.py で見る。

使い方（PowerShell）:
  python execute_mt5.py --once            # 今すぐ 1 回（dry）
  python execute_mt5.py --loop            # 毎時回し続ける（dry）
  python execute_mt5.py --loop --live     # 実際に発注（デモ口座で）
設定: 同じフォルダの config.json（無ければ既定値で書き出す）。業者の銘柄名の違いは mt5_fetch.py と同じ自動探索＋ config の symbol_map。
"""
import hashlib, hmac
import argparse, csv, datetime as dt, glob, json, os, sys, tempfile, time, traceback
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import numpy as np, pandas as pd
try:
    import MetaTrader5 as mt5
except ImportError:
    sys.exit("MetaTrader5 が入っていません（Windows 専用）→ pip install MetaTrader5 pandas pyarrow lightgbm")
# mt5_fetch.py（verification-lab/tools/mt5）の名前解決と時刻変換を使う
for cand in [os.path.join(HERE, "..", "..", "..", "verification-lab", "tools", "mt5"), os.path.join(HERE, "mt5")]:
    if os.path.exists(os.path.join(cand, "mt5_fetch.py")):
        sys.path.insert(0, os.path.abspath(cand)); break
import mt5_fetch as MF                                   # noqa: E402
import signal_s21 as SG                                  # noqa: E402
import common as C                                       # noqa: E402  （signal_s21 が sys.path を通す）
import kensho_s21_h1_ml_rr_q515 as K                     # noqa: E402

LEDGER_DIR = os.path.join(HERE, "台帳"); LOG_DIR = os.path.join(HERE, "ログ")
LEDGER = os.path.join(LEDGER_DIR, "trades.csv"); STATE = os.path.join(HERE, "状態.json")
CONFIG = os.path.join(HERE, "config.json"); SPR_REF = os.path.join(HERE, "spr_ref.json")
SPR_TZ = "America/New_York"                              # spr_ref.json の時の数え方（make_spr_ref.py と同じ）
DEFAULT_CONFIG = {
    "magic": 215021,                 # S21 の注文の印（他の EA・手動と区別）
    "risk_pct": 0.0004,              # 1 回のリスク量（運用規程 §1: 0.04%）
    "max_positions": 12,             # 合計リスク上限 = 1 回のリスク × 12 本（§2）
    "equity_override": None,         # 口座残高の代わりに使う元手（None なら口座の equity）
    "deviation_points": 20,          # 成行の許容滑り（ポイント）
    "close_before_gap_min": 10,      # 週末の前、最後の足が閉まる何分前に閉じるか
    "close_after_weekend_carry": True,  # 週末前決済が通らず週末を越した建玉を、開場の後の足が 1 本確定した後の回（週の途中に起動したときは起動後の最初の回）で閉じる（2026-11-15 案・記録は週末を持たない。False で今までどおり＝損切り・利確・時間切れまで持つ）
    "close_before_gap_extra_min": {"US500": 60, "USTECH": 60, "JPN225": 60},   # 銘柄ごとに、上の分にさらに足して早く閉じる分（S21 の銘柄名で）。XM の米国株の指数と日経は、金曜の取引が 21:00〜21:50 UTC に止まった後も 22:00 まで気配と M1 が続き、閉場を遅く学ぶ（11-13 に USTECH が 21:50 の Market closed で週末を越した・判断待ち 30）。config.json で上書きできる（{} で今までどおり）
    "history_bars": 2000,            # 判断に使う足の本数（28 日の閾値窓＋30 日の暖機＋特徴量 480 本 → 十分）
    "tz": "eet",                     # サーバー時間 → UTC の直し方（XM は eet。mt5_fetch.py と同じ）
    "spr_source": "ref",             # 判断に入れるスプレッド: "ref"＝spr_ref.json（記録に揃える）/ "broker"＝業者の spread 列（偽 MT5 のテスト用）
    "spr_ref_max_age_days": 45,      # spr_ref.json がこれより古ければログに ★（判断はその表のまま続ける）
    "log_margin": True,              # 2026-11-16: 毎時「余裕 足 …」の 1 行を書く（判断には使わない・切るなら false）
    "symbol_map": {},                # 例 {"US500": "US500Cash"}
    "symbols": None,                 # None なら 19 銘柄すべて
    "no_trade_symbols": [],          # 判断には入れるが発注しない銘柄（足は取り、閾値のプールにも入れるので、ほかの銘柄の判断は変わらない。小さい口座で最小ロットが大きすぎる銘柄用・2026-11-11 第 3 回）
    "min_lot_max_ratio": None,       # 最小ロットへ切り上げたときのリスクが狙いの何倍を超えたら見送るか（None なら今までどおり必ず切り上げる・第 3 回）
    "mt5_path": None, "login": None, "password": None, "server": None,
    "expect_login_hmac": None,       # つないだ口座の番号の HMAC-SHA256（鍵は winnote だけの「口座の照合.key」・16 進の先頭 16 桁以上）。違えば売買せずに止まる。番号は config にもログにも書かない。KIWAMI 極とスタンダードのようにサーバー名が同じ口座を見分ける（2026-11-15 案。None なら確かめない）
    "expect_server": None,           # つないだ先のサーバー名がこれと違えば売買せずに止まる（例 "XMTrading-MT5 3"。None なら確かめない＝今までどおり。MT5 を 2 つ並べると開いている方につながるため・監査D の 2・2026-11-13）
}
LEDGER_COLS = ["id", "sym", "broker_sym", "decision", "entry_time", "side", "rr", "a", "D", "lot", "ticket", "bar_open", "entry_px", "sl", "tp",
               "spread_pts", "status", "exit_time", "exit_px", "why", "R", "profit", "swap", "commission", "note"]


def log(msg):
    os.makedirs(LOG_DIR, exist_ok=True)
    line = f"{dt.datetime.now(dt.timezone.utc):%Y-%m-%d %H:%M:%S} {msg}"
    print(line, flush=True)
    with open(os.path.join(LOG_DIR, f"run_{dt.datetime.now(dt.timezone.utc):%Y%m}.log"), "a", encoding="utf-8") as f:
        f.write(line + "\n")


def tz_check(tz, off, now_utc):
    """config の tz（サーバー時間 → UTC の直し方）が、今測ったサーバー時間のずれ off と合うか（2026-11-05・業者替えの試験 P3）。
    合わなければ ★ の文、合う・測れない・判別できない設定なら None。now_utc は naive の UTC。
    tz を直し忘れると、米国と EU の夏時間が食い違う週（3 月・10〜11 月）に足が 1 時間ずれ、判断が変わる（偽の MT5 で 114 件中 15 件）。"""
    if off is None:
        return None
    if tz == "eet": exp = 3 if MF.eu_dst(now_utc) else 2
    elif tz == "nyclose": exp = 3 if MF.us_dst(now_utc) else 2
    elif tz == "server": exp = 0
    elif tz == "auto": return None
    else:
        try: exp = int(tz)
        except (TypeError, ValueError): return f"★ config の tz が読めない（{tz}）"
    if off == exp:
        return None
    return f"★ サーバー時間のずれ {off} 時間が config の tz={tz} の想定 {exp} 時間と違う（業者の時刻の決まりと tz が合っていない恐れ。mt5_fetch.py の --tz auto で確かめて config を直す）"


def load_config():
    if not os.path.exists(CONFIG):
        json.dump(DEFAULT_CONFIG, open(CONFIG, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    cfg = dict(DEFAULT_CONFIG); cfg.update(json.load(open(CONFIG, encoding="utf-8")))
    return cfg


def load_spr_ref(cfg):
    """spr_ref.json を読む（毎回読むので、ファイルを差し替えれば再起動なしで次の時から効く）。
    戻り値 ({銘柄: 24 個の配列}, 状態の文字列)。"ref" で表が無い・壊れているときは ({}, ★…) を返し、その銘柄は業者の spread で判断する。"""
    if cfg.get("spr_source", "ref") != "ref":
        return {}, "業者の spread（spr_source=broker）"
    try:
        j = json.load(open(SPR_REF, encoding="utf-8"))
        tab = {s: np.asarray(v, float) for s, v in j["spr"].items() if len(v) == 24}
        made = pd.Timestamp(j["meta"]["made_utc"], tz="UTC")
    except Exception as e:
        return {}, f"★ spr_ref.json を読めない（{type(e).__name__}）→ 業者の spread で判断"
    age = (pd.Timestamp.now(tz="UTC") - made).days
    return tab, f"spr_ref {j['meta']['made_utc']} 作成（{age} 日前）" + ("・★ 古い（make_spr_ref.py で作り直す）" if age > cfg.get("spr_ref_max_age_days", 45) else "")


def load_ledger():
    if os.path.exists(LEDGER):
        return pd.read_csv(LEDGER, dtype=str, keep_default_na=False)      # 文字列のまま持つ（数値は使うとき float()）
    return pd.DataFrame(columns=LEDGER_COLS)


def save_ledger(L):
    os.makedirs(LEDGER_DIR, exist_ok=True)
    L.reindex(columns=LEDGER_COLS).to_csv(LEDGER, index=False)


# ---------- MT5 ----------
class Broker:
    def __init__(self, cfg, live):
        self.cfg, self.live = cfg, live; self.forming = {}; self.spr_ref = {}
        kw = {k: v for k, v in dict(path=cfg["mt5_path"], login=cfg["login"], password=cfg["password"], server=cfg["server"]).items() if v}
        if not mt5.initialize(**kw):
            raise RuntimeError(f"MT5 に接続できない: {mt5.last_error()}（MT5 を起動して口座にログインしておく）")
        self.acc = self.check_server()                                             # つないだ先の確かめ（expect_server が無ければ account_info を返すだけ＝今までどおり）
        if self.acc is None:
            raise RuntimeError("口座にログインしていない")
        self.demo = self.acc.trade_mode == 0
        all_names = {s.name for s in (mt5.symbols_get() or [])}; self.all_names = all_names
        self.names = {}
        for s in (cfg["symbols"] or MF.S21):
            n = MF.resolve(s, all_names, cfg["symbol_map"])
            if n is None:
                log(f"見つからない銘柄: {s}（config の symbol_map で指定）"); continue
            mt5.symbol_select(n, True); self.names[s] = n
        off = None
        for s in self.names.values():
            off = MF.detect_offset(s)
            if off is not None:
                break
        self.cur_off = off
        self.tz_warn = tz_check(cfg["tz"], off, dt.datetime.now(dt.timezone.utc).replace(tzinfo=None))
        if self.tz_warn:
            log(self.tz_warn)
        log(f"接続: {self.acc.server}（{'デモ' if self.demo else '実口座'}）equity {self.acc.equity:,.0f} {self.acc.currency}・銘柄 {len(self.names)}・サーバー時間のずれ {off}")

    def check_server(self):
        """つないだ先のサーバー名が config の expect_server と同じか（監査D の 2・2026-11-13）。違う・口座を読めないなら、**接続を切ってから**例外にする
        （切らないと、繋ぎ直しで止まった後も古い入れ物が違う端末に注文を出せる。口座を読めない場合も同じ・点検 11-13 の A-1）。
        接続のときと、毎回の run_once の先頭で呼ぶ（同じ端末で口座だけ替わった形も止める）。expect_server が無ければ何も確かめない。戻り値 account_info()。"""
        acc = mt5.account_info(); exp = self.cfg.get("expect_server")
        if exp and (acc is None or acc.server != exp):
            try: mt5.shutdown()
            except Exception: pass
            raise RuntimeError(f"つないだ先が違う: {getattr(acc, 'server', '口座を読めない')}（config の expect_server は {exp}）。売買しない。別の MT5 が開いている恐れ（config の mt5_path で端末を指定する）")
        eh = str(self.cfg.get("expect_login_hmac") or "").strip().lower()
        if eh:                                                                     # 2026-11-15 案: サーバー名が同じ別の口座（KIWAMI 極とスタンダード）を見分ける
            why = login_mismatch(acc, eh)                                          # 番号の幅は狭く、ただの sha256 は総当たりで戻せる（3 回目の点検）→ winnote だけの鍵で HMAC
            if why:
                try: mt5.shutdown()
                except Exception: pass
                raise RuntimeError(f"つないだ口座が違う（{why}）。売買しない。同じサーバー名の別の口座の恐れ（config の mt5_path で端末を指定する）")
        return acc

    def utc(self, server_epoch):
        return MF.to_utc(pd.Series(server_epoch), self.cfg["tz"], self.cur_off)

    def bars(self, s, n=None, now=None):
        """H1 の確定足（今の時間の足は除く）。記録と同じ列（ask_ は bid＋スプレッド。スプレッドは spr_ref.json の値、無い銘柄は業者の spread×point）。
        形成中かどうかは足の時刻で決める。新しい足がまだ返らない銘柄で確定足を捨てると、1 本前で判断してしまう（2026-11-02・9 件中 7 件）。"""
        n = n or self.cfg["history_bars"]
        name = self.names[s]; info = mt5.symbol_info(name)
        r = mt5.copy_rates_from_pos(name, mt5.TIMEFRAME_H1, 0, n + 1)
        if r is None or len(r) < 2:
            return None, None
        d = pd.DataFrame(r).sort_values("time").reset_index(drop=True)
        hour = (now if now is not None else pd.Timestamp.now(tz="UTC")).floor("h")
        last = self.utc(pd.Series([int(d["time"].iloc[-1])])).iloc[0]; self.forming[s] = last >= hour
        if self.forming[s]:
            cur_time = last; d = d.iloc[:-1].reset_index(drop=True)       # 最後 = 今できている足
        else:
            cur_time = hour                                               # 今の時間の足がまだ無い。取れた足は全部確定している
        tu = self.utc(d["time"]).reset_index(drop=True)
        if s in self.spr_ref:                                             # 記録（Dukascopy）の時ごとの中央値（2026-11-04・監査B の 1）
            sp = pd.Series(self.spr_ref[s][tu.dt.tz_convert(SPR_TZ).dt.hour.to_numpy()])
        else:
            sp = d["spread"].astype(float) * info.point
        out = pd.DataFrame({"time": tu, "open": d["open"], "high": d["high"], "low": d["low"], "close": d["close"],
                            "volume": d["tick_volume"].astype(float), "spread": sp})
        for c in ["open", "high", "low", "close"]:
            out[f"ask_{c}"] = out[c] + sp
        # 今できている足（値はまだ決まらない）を「場つなぎ」として時刻だけ足す（signal_s21.decide の注記。H4/D1 特徴量を記録と同じ扱いにする）
        if cur_time > pd.Timestamp(out["time"].iloc[-1]):
            out = pd.concat([out, pd.DataFrame([{"time": cur_time, **{c: np.nan for c in out.columns if c != "time"}}])], ignore_index=True)
        return out, cur_time

    def m1_times(self, s, n=15000):
        """M1 の足の時刻（UTC）。週末前決済の時刻を分単位で学ぶため（2 週分ほど）。取れなければ None。"""
        r = mt5.copy_rates_from_pos(self.names[s], mt5.TIMEFRAME_M1, 0, n)
        return None if r is None or len(r) < 2 else self.utc(pd.Series(np.sort(r["time"].astype("int64")))).reset_index(drop=True)

    def last_bar(self, s):
        """MT5 が返す最新の足の時刻（UTC）。取れなければ None。"""
        r = mt5.copy_rates_from_pos(self.names[s], mt5.TIMEFRAME_H1, 0, 1)
        return None if r is None or len(r) == 0 else self.utc(pd.Series([int(r[-1]["time"])])).iloc[0]

    def quoting(self, s, now, within_min=5):
        """直近に値が来ているか（休場の銘柄を待たない・入らないため）。"""
        t = mt5.symbol_info_tick(self.names[s])
        return t is not None and t.time > 0 and now - self.utc(pd.Series([int(t.time)])).iloc[0] <= pd.Timedelta(minutes=within_min)

    def positions(self):
        """建玉（この bot の magic だけ）。MT5 の説明では positions_get はエラーのとき None を返す（建玉 0 本は空の組）。これまでは None を「建玉なし」として扱い、
        取得に失敗した回に同じ銘柄へもう 1 本入る・合計の上限を数え損ねる恐れがあった（監査A の 4・2026-11-13）。実機で 0 本のときの返り値を確かめていないので、
        None のときは last_error() を見て「成功」（1 か 0）なら建玉なし、それ以外は例外にして main の繋ぎ直しに任せる。"""
        P = mt5.positions_get()
        if P is None:
            e = mt5.last_error()
            if not (e and e[0] in (0, 1)):
                raise RuntimeError(f"建玉を取れない（positions_get が None・{e}）→ 繋ぎ直す")
            if not getattr(self, "_none_ok_logged", False):                            # 1 回だけ書く（0 本で None を返す端末かどうかがログで分かる）
                self._none_ok_logged = True; log(f"positions_get が None を返したが last_error は成功（{e}）→ 建玉なしとして扱う")
            P = ()
        return [p for p in P if p.magic == self.cfg["magic"]]

    def filling(self, info):
        fm = info.filling_mode
        if fm & 1: return mt5.ORDER_FILLING_FOK
        if fm & 2: return mt5.ORDER_FILLING_IOC
        return mt5.ORDER_FILLING_RETURN

    def fx_to_account(self, cur):
        """損益通貨 cur → 口座通貨のレート（MT5 のティックから。無ければ None）。"""
        acct = self.acc.currency
        if cur == acct:
            return 1.0
        cands = [(cur + acct, False), (acct + cur, True)]
        for pair, inv in list(cands):                                     # 接尾辞・別名の業者（USDJPY.pro など）。逆向き（USD 口座の円の損益）も探す（2026-11-05・業者替えの試験 P1）
            n = MF.resolve(pair, getattr(self, "all_names", set()), {})
            if n and n != pair: cands.append((n, inv))
        for name, inv in cands:
            info = mt5.symbol_info(name)
            if info is None:
                continue
            mt5.symbol_select(name, True); t = mt5.symbol_info_tick(name)
            if t is not None and t.bid > 0:
                return (1.0 / t.ask) if inv else t.bid
        return None

    def lot_for(self, s, D):
        """1 回のリスク量（口座通貨）÷（D の値動き 1 ロットあたりの損益）。
        損益 = D × 契約サイズ × (損益通貨→口座通貨)。XM は CFD の trade_tick_value を損益通貨のまま返す（2026-10-28 実測）ので tick_value は使わない。"""
        info = mt5.symbol_info(self.names[s])
        eq = self.cfg["equity_override"] or mt5.account_info().equity
        risk = eq * self.cfg["risk_pct"]
        rate = self.fx_to_account(info.currency_profit)
        if rate is None:
            return None, f"{info.currency_profit}→{self.acc.currency} のレートが取れない"
        per_lot = D * info.trade_contract_size * rate                     # 1 ロットで D 動いたときの損益（口座通貨）
        if per_lot <= 0:
            return None, "契約サイズが取れない"
        lot = risk / per_lot
        step = info.volume_step or 0.01
        lot_r = np.floor(lot / step) * step
        note = ""
        if lot_r < info.volume_min:
            k = self.cfg.get("min_lot_max_ratio")
            if k and risk > 0 and info.volume_min * per_lot > k * risk:               # 小さい口座で、最小ロットでもリスクが狙いの k 倍を超える銘柄は入らない（第 3 回）
                return None, f"最小ロットのリスクが狙いの {info.volume_min * per_lot / risk:.1f} 倍（上限 {k} 倍）"
            lot_r = info.volume_min; note = f"最小ロットに切り上げ（計算 {lot:.4f}・リスク {info.volume_min * per_lot:,.0f} {self.acc.currency}）"
        if lot_r > info.volume_max:
            lot_r = info.volume_max; note = "最大ロットに切り下げ"
        return float(round(lot_r, 8)), note

    def open(self, s, dr, lot, D, rr, comment):
        name = self.names[s]; info = mt5.symbol_info(name); tick = mt5.symbol_info_tick(name)
        price = tick.ask if dr == 1 else tick.bid
        sl = price - dr * D; tp = price + dr * rr * D
        req = dict(action=mt5.TRADE_ACTION_DEAL, symbol=name, volume=lot, type=mt5.ORDER_TYPE_BUY if dr == 1 else mt5.ORDER_TYPE_SELL,
                   price=price, sl=round(sl, info.digits), tp=round(tp, info.digits), deviation=self.cfg["deviation_points"], magic=self.cfg["magic"],
                   comment=comment, type_time=mt5.ORDER_TIME_GTC, type_filling=self.filling(info))
        if not self.live:
            return dict(ok=True, dry=True, price=price, sl=req["sl"], tp=req["tp"], ticket="", spread_pts=info.spread, retcode=None)
        res = mt5.order_send(req)
        ok = res is not None and res.retcode in (mt5.TRADE_RETCODE_DONE, mt5.TRADE_RETCODE_PLACED, mt5.TRADE_RETCODE_DONE_PARTIAL)
        if ok and res.price:
            # 約定値で SL/TP を置き直す（記録は入った値段から D を測る）
            price = res.price; sl = price - dr * D; tp = price + dr * rr * D
            pos = [p for p in (mt5.positions_get(symbol=name) or []) if p.magic == self.cfg["magic"]]
            if pos:
                mt5.order_send(dict(action=mt5.TRADE_ACTION_SLTP, symbol=name, position=pos[-1].ticket, sl=round(sl, info.digits), tp=round(tp, info.digits)))
                ticket = pos[-1].ticket
            else:
                ticket = res.order
            return dict(ok=True, dry=False, price=price, sl=round(sl, info.digits), tp=round(tp, info.digits), ticket=str(ticket), spread_pts=info.spread, retcode=res.retcode)
        return dict(ok=False, dry=False, retcode=getattr(res, "retcode", None), msg=getattr(res, "comment", str(mt5.last_error())))

    def close(self, p, why):
        name = p.symbol; info = mt5.symbol_info(name); tick = mt5.symbol_info_tick(name)
        dr = 1 if p.type == mt5.POSITION_TYPE_BUY else -1
        price = tick.bid if dr == 1 else tick.ask
        req = dict(action=mt5.TRADE_ACTION_DEAL, symbol=name, volume=p.volume, type=mt5.ORDER_TYPE_SELL if dr == 1 else mt5.ORDER_TYPE_BUY,
                   position=p.ticket, price=price, deviation=self.cfg["deviation_points"], magic=self.cfg["magic"], comment=why[:20],
                   type_time=mt5.ORDER_TIME_GTC, type_filling=self.filling(info))
        if not self.live:
            return dict(ok=True, dry=True, price=price)
        res = mt5.order_send(req)
        ok = res is not None and res.retcode in (mt5.TRADE_RETCODE_DONE, mt5.TRADE_RETCODE_PLACED, mt5.TRADE_RETCODE_DONE_PARTIAL)
        return dict(ok=ok, dry=False, price=getattr(res, "price", None), retcode=getattr(res, "retcode", None), msg=getattr(res, "comment", ""))

    def deals_out(self, ticket, since_utc):
        """position_id == ticket の決済 deal（無ければ None）。"""
        frm = (pd.Timestamp(since_utc) - pd.Timedelta(days=1)).to_pydatetime().replace(tzinfo=None)
        D = mt5.history_deals_get(frm, dt.datetime.now() + dt.timedelta(days=1)) or []
        outs = [d for d in D if str(d.position_id) == str(ticket) and d.entry == mt5.DEAL_ENTRY_OUT]
        return outs or None


# ---------- 週末（24 時間以上の休み）の予測 ----------
def next_gap_close(bars, cur_time, before_min):
    """過去の足から「24 時間以上空く前の最後の足」の曜日・時刻を学び、今週のその時刻（足の終わりの before_min 分前）を返す。
    戻り値 (close_at_utc, last_bar_time) か (None, None)。"""
    t = bars["time"]; gaps = np.where((t.iloc[1:].to_numpy() - t.iloc[:-1].to_numpy()) / np.timedelta64(1, "h") >= SG.BREAK_H)[0]
    if len(gaps) == 0:
        return None, None
    last = pd.Timestamp(t.iloc[gaps[-1]])                                           # 直近の休み前の最後の足（UTC）
    wd, hh = last.weekday(), last.hour
    base = pd.Timestamp(cur_time)
    cand = base.normalize() + pd.Timedelta(days=(wd - base.weekday()) % 7, hours=hh)
    if cand < base - pd.Timedelta(hours=1):
        cand += pd.Timedelta(days=7)
    T = cand + pd.Timedelta(minutes=60 - before_min)
    return T, min(cand, T.floor("h"))                                                # 早じまいで T が前の足に入るときは、その足から閉じに行く（before_min ≤ 60 なら今までと同じ）


def _project(anchor, start, tz):
    """anchor（UTC）と同じ曜日・時刻（tz の時計で）で、start（UTC）以後に最初に来る時刻（UTC）。"""
    a, s = pd.Timestamp(anchor).tz_convert(tz).tz_localize(None), pd.Timestamp(start).tz_convert(tz).tz_localize(None)
    c = s.normalize() + pd.Timedelta(days=(a.weekday() - s.weekday()) % 7) + (a - a.normalize())
    if c < s:
        c += pd.Timedelta(days=7)
    return c.tz_localize(tz, nonexistent="shift_forward", ambiguous=True).tz_convert("UTC")


WEEKEND_H = 40                                                                     # 週末の切れ目とみなす最短の長さ（時間）。週の途中の休場（25 時間ほど）と分ける


_GAP_WARNED = set()


LOGIN_KEY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "口座の照合.key")   # winnote の bot のフォルダだけに置く鍵（lab-ops・Mac へ送らない）


def login_mismatch(acc, expect, key_path=None):
    """口座の照合（2026-11-15 案）。合えば None、合わなければ理由の文（番号もハッシュも入れない）"""
    if len(expect) < 16:
        return "config の expect_login_hmac が短すぎる（16 桁以上）"
    if not all(c in "0123456789abcdef" for c in expect) or len(expect) > 64:   # 2026-11-16（4 回目の点検の 1）: 全角などの文字で compare_digest が TypeError を投げ、接続を切らずに落ちていた
        return "config の expect_login_hmac の書き方が違う（16 進の 16〜64 桁）"
    try:
        key = open(key_path or LOGIN_KEY, "rb").read().strip()
    except OSError:
        return "鍵のファイル 口座の照合.key が無い"
    if len(key) < 32:
        return "鍵が短すぎる"
    if acc is None:
        return "口座を読めない"
    got = hmac.new(key, str(getattr(acc, "login", "")).encode(), hashlib.sha256).hexdigest()
    return None if hmac.compare_digest(got[:len(expect)], expect) else "口座番号の照合が合わない"


def gap_before_min(cfg, s):
    """銘柄 s の週末前決済を、学んだ閉場の何分前にするか（close_before_gap_min ＋ 銘柄ごとの上乗せ）。2026-11-14 判断待ち 30
    2026-11-15（点検の指摘）: 上乗せの書き方の誤り（{"USTECH": null}・リスト・文字・負の数）で例外になると run_once が毎回落ち、入口も出口も
    週末前決済も止まっていた → その銘柄は既定の上乗せ（DEFAULT_CONFIG）に戻し、★ を 1 回だけログに書く。"""
    extra = cfg.get("close_before_gap_extra_min") or {}
    try:
        v = extra.get(s, 0) if isinstance(extra, dict) else None
        if v is None or isinstance(v, bool) or not float(v).is_integer() or not 0 <= int(v) <= 600:
            raise ValueError(repr(v))
        add = int(v)
    except (TypeError, ValueError) as e:
        add = int((DEFAULT_CONFIG.get("close_before_gap_extra_min") or {}).get(s, 0))
        if s not in _GAP_WARNED:
            _GAP_WARNED.add(s); log(f"★ config の close_before_gap_extra_min を {s} で読めない（{e}）→ 既定の {add} 分を使う")
    return int(cfg["close_before_gap_min"]) + add


def carried_weekend(d, entry_utc):
    """入った後の業者の H1 の足に、週末の切れ目（WEEKEND_H＝40 時間以上の空き）があるか＝週末前決済が通らずに週末を越した建玉か（2026-11-15 案）。
    11-13 に USTECH が Market closed で週を越し、月曜の開場の後は T が次の金曜へ移るので、損切り・利確・120 本の時間切れまで持ち続け、
    その間は「同時 1 本」で新しく入れず記録とずれていた。記録（forward_s21.py）は週末を持たないので、開場の後の最初の回で閉じるのが記録に近い。
    d が無い・入った後の足が 1 本以下なら False。"""
    if d is None or not len(d):
        return False
    t = pd.to_datetime(d.loc[d["close"].notna(), "time"], utc=True)              # 確定した足だけ（bars() は今の時間の足が無いとき close が空の行を足すので、週末の間に「空き」が見えてしまう）
    t = t[t >= entry_utc.floor("h")].sort_values()
    return len(t) >= 2 and bool((t.diff().dropna() >= pd.Timedelta(hours=WEEKEND_H)).any())   # 週末だけ（40 時間以上）。24 時間にすると XM だけが休むクリスマス（約 37 時間・Dukascopy には足がある）や GER40 の 5-1 で、記録は持つのに bot だけが閉じる（3 回目の点検 11-15）。週の途中の祝日は 11-04 の決め（越すのを受け入れる）のまま


def next_gap_close_m1(m1, now, before_min):
    """M1 の直近の週末の切れ目（40 時間以上・閉場が木か金）の閉場（最後の足＋1 分）を、直近の切れ目の後の再開から見て UTC とニューヨーク時間の両方で
    今週に当て、早いほうの before_min 分前を返す。
    正時の途中で閉まる銘柄・米国の夏時間の切り替えの週で、閉場の後に閉じようとする不具合を直す（2026-11-03・XM の M1 で閉じ損ねる週 375 → 65）。
    第 2 回（2026-11-04・監査A の 1 と 3）: T を過ぎても翌週へ送らない（新しい切れ目が M1 に見えるまで `休み直前` のまま。早じまいの翌週の金曜の残りで入って越す形を消す）。
    閉場の曜日と時刻は週末の切れ目だけから学ぶ（週の途中の休場で曜日を誤らない。該当が無ければ直近の切れ目）。now は使わない（呼び方を変えないため残す）。
    戻り値 (close_at_utc, その時刻を含む H1 の足) か (None, None)。祝日の早じまいは前の週から学べないので残る。"""
    t = pd.DatetimeIndex(m1); d = t[1:] - t[:-1]
    gaps = np.where(d >= pd.Timedelta(hours=SG.BREAK_H))[0]
    if len(gaps) == 0:
        return None, None
    start = t[gaps[-1] + 1]                                                        # 直近の切れ目の後の再開（今の営業の始まり）
    wk = [g for g in gaps if d[g] >= pd.Timedelta(hours=WEEKEND_H) and (t[g] + pd.Timedelta(minutes=1)).weekday() in (3, 4)]
    close = t[wk[-1] if wk else gaps[-1]] + pd.Timedelta(minutes=1)
    T = min(_project(close, start, "UTC"), _project(close, start, "America/New_York")) - pd.Timedelta(minutes=before_min)
    return T, T.floor("h")


# ---------- 1 回の実行 ----------
def run_once(B, cfg, live, now=None, entries=True):
    """entries=False は週末前決済の起床（毎時の判断ではない・2026-11-04 監査A 12）: 決済の取り込みと出口の管理だけ行い、入口は回さない。"""
    now = now or pd.Timestamp.now(tz="UTC")
    asof = now.floor("h") - pd.Timedelta(hours=1)                                  # 最後の確定足
    if cfg.get("expect_server") or cfg.get("expect_login_hmac"): B.check_server()                                  # 動いている途中に端末の口座が替わった・繋ぎ直しが違う端末に残った、を毎回ここで止める
    B.positions()                                                                  # 建玉を取れない回は、足の取得と判断の計算の前にここで止める（後で止まると一時フォルダが毎回残る・点検 11-13）
    tmp = tempfile.mkdtemp(prefix="s21_h1_")
    B.spr_ref, spr_note = load_spr_ref(cfg)
    lack = [s for s in B.names if cfg.get("spr_source", "ref") == "ref" and s not in B.spr_ref]
    if lack or "★" in spr_note:
        log(f"{spr_note}" + (f"・表に無い銘柄（業者の spread で判断）: {','.join(lack)}" if lack else ""))
    bars, cur, gapinfo = {}, {}, {}
    for s in B.names:
        d, ct = B.bars(s, now=now)
        if d is None:
            log(f"{s}: 足が取れない"); continue
        d.to_parquet(os.path.join(tmp, f"{s}.parquet"), index=False)
        bars[s], cur[s] = d, ct
        m1 = B.m1_times(s)
        gapinfo[s] = next_gap_close_m1(m1, now, gap_before_min(cfg, s)) if m1 is not None else (None, None)
        if gapinfo[s][0] is None:
            gapinfo[s] = next_gap_close(d, ct, gap_before_min(cfg, s))               # M1 が取れないときは前の決め方
    if not bars:
        # MT5 の端末が落ちる・再起動すると、MT5 の関数は例外でなく None を返す。そのまま進むと「★ 判断できない」→「済 判断 … 保有 0」を毎時書き続け、
        # 繋ぎ直さないまま動いているように見える（2026-11-11 監査A の 1）。例外にして main の繋ぎ直しに任せる
        os.rmdir(tmp)
        raise RuntimeError("全銘柄の足が取れない（MT5 との接続が切れた恐れ）→ 繋ぎ直す")
    try:
        sig = SG.decide(tmp, asof)
    except SystemExit as e:                                                        # 年度のモデルが無い・足データが無い（signal_s21 の sys.exit）。except Exception では捕まらずプロセスが終わっていた（監査B の 5）
        log(f"★ 判断できない（{e}）→ 決済の取り込みと出口の管理だけ行い、入口は回さない")
        sig = dict(asof=str(asof), fiscal_year=None, signals={}, stale=[], missing=[], reopen_block=[]); entries = False
    # 2026-11-16（昼の自走・案）: 全銘柄の「予測 − 閾値」の最大値を 1 行に残す（記録側の余裕と比べて、判断の計算の食い違いを両側から見るため）。
    #   判断・発注には使わない。書けなくても毎時の回は止めない。行は「余裕 」で始まり、compare_record.py・watch_rules.py の読む形（入る・見送り・閉じる・決済・済 判断・★）に当たらない
    if cfg.get("log_margin", True) and sig.get("signals"):
        try:
            mg = " ".join(f"{s}:{v['margin']:+.5f}/{v['margin_a']}" for s, v in sorted(sig["signals"].items()) if v.get("margin") is not None)
            if mg: log(f"余裕 足 {sig['asof']} {mg}")
        except Exception as e:
            log(f"余裕の行を書けない（{type(e).__name__}）")
    L = load_ledger(); P = B.positions(); pos_by = {}
    for p in P:
        s = next((k for k, v in B.names.items() if v == p.symbol), p.symbol); pos_by.setdefault(s, []).append(p)
    # 決済の取り込み
    for i, row in L[L["status"] == "open"].iterrows():
        outs = B.deals_out(row["ticket"], row["entry_time"]) if row["ticket"] else None
        if outs:
            o = outs[-1]; dr = 1 if row["side"] == "買い" else -1; xp = float(o.price)
            why = {mt5.DEAL_REASON_SL: "損切り", mt5.DEAL_REASON_TP: "利確"}.get(o.reason, row.get("why") if isinstance(row.get("why"), str) and row.get("why") else "手動/成行")
            L.loc[i, ["status", "exit_time", "exit_px", "why", "R", "profit", "swap", "commission"]] = [str(v) for v in [
                "closed", B.utc(pd.Series([int(o.time)])).iloc[0], xp, why, dr * (xp - float(row["entry_px"])) / float(row["D"]),
                sum(x.profit for x in outs), sum(x.swap for x in outs), sum(x.commission for x in outs)]]
            log(f"決済 {row['sym']} {why} R {float(L.loc[i, 'R']):+.2f}")
    # 出口の管理（時間切れ・週末前）
    close_ng = set()                                                                # 週末前決済が通らなかった銘柄（Market closed は除く。起き直しても通らない）
    for s, plist in pos_by.items():
        d = bars.get(s)
        for p in plist:
            entry_utc = B.utc(pd.Series([p.time])).iloc[0]
            nbars = int(((d["time"] > entry_utc) & d["close"].notna()).sum()) + 1 if d is not None else 0   # 入った足を含む確定足の本数
            why = None
            if nbars >= K.H:
                why = "時間切れ"
            elif cfg.get("close_after_weekend_carry", True) and carried_weekend(d, entry_utc):
                why = "週越しの決済"
            elif gapinfo.get(s, (None, None))[0] is not None and now >= gapinfo[s][0] - pd.Timedelta(minutes=1) and cur.get(s) is not None and cur[s] >= gapinfo[s][1]:
                why = "週末前決済"
            if why:
                r = B.close(p, why)
                log(f"{'[dry] ' if not live else ''}閉じる {s} {why} lot {p.volume} → {r}")
                gT = gapinfo.get(s, (None, None))[0]                                       # 理由を問わず、週末前の時刻を過ぎた後の決済が通らなければ起き直す（点検 B-7: 時間切れと重なる形）
                if not r.get("ok") and r.get("retcode") != 10018 and gT is not None and now >= gT - pd.Timedelta(minutes=1): close_ng.add(s)
                if r["ok"] and live:
                    m = L["ticket"].astype(str) == str(p.ticket)
                    L.loc[m, "why"] = why
    # 入口（週末前決済の起床では回さない。毎時の判断で見送った合図が同じ asof のまま遅れて入るのを防ぐ）
    n_open = len(P); week = asof.tz_convert(None).to_period("W-SUN")
    if not entries:
        log("週末前決済の起床: 入口は回さない")
    for s, v in (sig["signals"].items() if entries else ()):
        if v["action"] is None:
            continue
        a = v["action"]; dr, rr = K.ACTIONS[a]; D = v["D"]
        note = []; tid = f"{asof:%Y%m%d%H}_{s}"
        if len(L) and (L["id"] == tid).any(): note.append("この足は済み")
        if s in pos_by: note.append("同時 1 本")
        if s not in cur or (cur[s] - pd.Timestamp(v["bar"])) >= pd.Timedelta(hours=SG.BREAK_H): note.append("再開後 1 本目")
        wk = L[(L["sym"] == s) & (pd.to_datetime(L["decision"], utc=True).dt.tz_convert(None).dt.to_period("W-SUN") == week)] if len(L) else L
        if len(wk) >= K.WEEK_CAP: note.append("週 10 回")
        if n_open >= cfg["max_positions"]: note.append("合計リスク上限")
        if gapinfo.get(s, (None, None))[0] is not None and now >= gapinfo[s][0]: note.append("休み直前")
        if s in (cfg.get("no_trade_symbols") or []): note.append("発注しない銘柄")
        if not B.forming.get(s):                                                    # 今の時間の足が無い。足の遅れか休場
            if pd.Timestamp(v["bar"]) < asof: note.append("足が古い")
            elif not B.quoting(s, now): note.append("値が来ていない")
        if note:
            log(f"見送り {s} {v['side']} RR{rr}: {'・'.join(note)}"); continue
        lot, lnote = B.lot_for(s, D)
        if lot is None:
            log(f"見送り {s} {v['side']} RR{rr}: {lnote}"); continue          # ほかの見送りと同じ形（compare_record.py が合図として読める・監査C の 8）
        r = B.open(s, dr, lot, D, rr, f"S21 a{a} {asof:%m%d%H}")
        log(f"{'[dry] ' if not live else ''}入る {s} {v['side']} RR{rr} lot {lot} D {D:.5g} → {r} {lnote}")
        if r["ok"] and live:
            L = pd.concat([L, pd.DataFrame([dict(id=tid, sym=s, broker_sym=B.names[s], decision=v["bar"], entry_time=str(now), side=v["side"], rr=rr, a=a, D=D,
                                                 lot=lot, ticket=r["ticket"], bar_open=float(bars[s]["close"].dropna().iloc[-1]), entry_px=r["price"], sl=r["sl"], tp=r["tp"],
                                                 spread_pts=r["spread_pts"], status="open", note=lnote)]).astype(str)], ignore_index=True)
            n_open += 1
            save_ledger(L)                                                              # 約定のたびに保存（後の銘柄で例外が出ても、入った建玉が台帳から漏れない・監査A の 3）
    save_ledger(L)
    cl = L[L["status"] == "closed"]; Rs = cl["R"].astype(float) if len(cl) else pd.Series(dtype=float)
    try: n_now = len(B.positions())                                                # 表示用の数。ここで取れなくても、発注と台帳の保存まで済んだ回を失敗扱いにしない（点検 11-13）
    except Exception: n_now = n_open
    st = dict(更新=str(now), 判断の足=sig["asof"], 年度=sig["fiscal_year"], live=live, 口座=B.acc.server, 保有中=n_now,
              決済済み=int(len(cl)), 累計R=float(Rs.sum()) if len(cl) else 0.0, 平均R=float(Rs.mean()) if len(cl) else None,
              合図=sum(1 for v in sig["signals"].values() if v["action"] is not None), 休場=sig["stale"], 欠け=sig["missing"],
              判断のスプレッド=spr_note + (f"・業者の値: {','.join(lack)}" if lack else ""),
              足の本数_最少=min(((int(d["close"].notna().sum()), s) for s, d in bars.items()), default=None),   # MT5 が返した確定足の本数が少ない銘柄（history_bars より大きく少なければ特徴量が欠ける・監査A の 5）
              次の週末前決済={s: str(g[0]) for s, g in gapinfo.items() if g[0] is not None and s in pos_by},
              週末前決済の失敗=sorted(close_ng))
    json.dump(st, open(STATE, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    for f in glob.glob(os.path.join(tmp, "*")):
        os.remove(f)
    os.rmdir(tmp)
    return st, gapinfo


def wait_for_bars(B, now, tries=6, every=5):
    """値が来ている全銘柄で、今の時間の足が MT5 に現れるまで少し待つ（最大 25 秒。Q646 で遅れは損なので長く待たない）。"""
    hour = now.floor("h"); wait = [s for s in B.names if B.quoting(s, now)]
    for k in range(tries):
        wait = [s for s in wait if (lambda t: t is None or t < hour)(B.last_bar(s))]
        if not wait:
            return []
        if k < tries - 1:
            time.sleep(every)
    log(f"新しい足が来ない: {','.join(wait)}")
    return wait


def next_wake(now, pending_close):
    """次の起床時刻と、それが週末前決済の起床（毎時の判断 :00:20 ではない）かどうか。週末前決済の起床では入口を回さない（2026-11-04）。"""
    nxt = now.floor("h") + pd.Timedelta(hours=1, seconds=20)
    extra = pending_close is not None and pending_close < nxt
    return (pending_close if extra else nxt), extra


RETRY_S = 60                                                                       # 週末前決済が通らなかったときに起き直すまでの秒数
RETRY_MARGIN_S = 30                                                                # 起き直しは閉場と次の正時のこれだけ前まで（次の時間の毎時の判断を週末前決済の起床にしない）


def next_pending_close(gapinfo, close_ng, now, before_min):
    # before_min は分（全銘柄同じ）か、銘柄 → 分 の関数（2026-11-15: 早じまいの銘柄も学んだ閉場まで起き直す。Market closed は close_ng に入らないので害は無い）
    """次の週末前決済の起床（2026-11-13 自走・案）。これまでは「T が今より後」のものだけを残していたので、T の起床で決済が通らない
    （B.close が ok=False を返す・例外にならない）と次の起床は次の毎時 :00:20 になり、閉場（T＋before_min 分）の後で建玉が週末を越していた。
    その回に週末前決済が通らなかった銘柄（close_ng・Market closed は除く）だけ、RETRY_S 秒後に起き直す。
    ただし閉場と次の正時の早いほうの RETRY_MARGIN_S 秒前まで（点検 11-13 の B-1: 次の時間に入った起き直しが、その時間の入口を全銘柄で抜かす）。"""
    out = []
    for s, g in gapinfo.items():
        T = g[0] if g else None
        if T is None:
            continue
        if T > now:
            out.append(T)
        elif s in close_ng:
            bm_s = before_min(s) if callable(before_min) else before_min
            limit = min(T + pd.Timedelta(minutes=bm_s), now.floor("h") + pd.Timedelta(hours=1)) - pd.Timedelta(seconds=RETRY_MARGIN_S)
            r = min(now + pd.Timedelta(seconds=RETRY_S), limit)
            if r > now:
                out.append(r)
    return min(out) if out else None


def startup_pending_close(B, cfg, now=None):
    """起動の直後に、保有中の銘柄の週末前決済の時刻を 1 回だけ計算する（2026-11-12 第 3 回・監査A の 6a）。
    これまでは pending_close が起動時に None で、金曜の最後の毎時の回から週末前決済の時刻 T までの間に bot が起動し直す（Windows Update の
    自動再起動など・11-11 に実際に起きた）と、次の起床は次の毎時 :00:20 で閉場の後になり、建玉が週末を越していた。
    T を過ぎていても閉場（T＋close_before_gap_min 分）の前なら返す（すぐ起きて閉じる）。保有が無い・計算できないときは None。"""
    now = now or pd.Timestamp.now(tz="UTC"); out = []
    held = {next((k for k, v in B.names.items() if v == p.symbol), None) for p in B.positions()} - {None}
    for s in held:
        m1 = B.m1_times(s)
        T, _ = next_gap_close_m1(m1, now, gap_before_min(cfg, s)) if m1 is not None else (None, None)
        if T is not None and now < T + pd.Timedelta(minutes=gap_before_min(cfg, s)):   # 学んだ閉場まで（2026-11-15 点検の指摘: 早じまいの銘柄が 21:00〜21:50 の再起動で閉じに行かなかった。閉場の後なら Market closed で終わるだけ）
            out.append(T)
    return min(out) if out else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true"); ap.add_argument("--loop", action="store_true")
    ap.add_argument("--live", action="store_true", help="実際に発注する（付けなければ dry）")
    a = ap.parse_args(); cfg = load_config(); live = a.live
    try:
        B = Broker(cfg, live)
    except Exception as e:                                                         # 起動できない理由を run ログにも残す（画面にしか出ないと、止まった理由が後から分からない・点検 11-13 の A-2）
        log(f"★ 起動できない: {e}"); raise
    if live and not B.demo:
        sys.exit("実口座に接続している。実弾は運用規程の 6 か月時点の確認の後（taichi の承認）まで動かさない")
    if a.once or not a.loop:
        now = pd.Timestamp.now(tz="UTC")
        wait_for_bars(B, now, tries=1)
        st, _ = run_once(B, cfg, live); print(json.dumps(st, ensure_ascii=False, indent=1)); return
    try:
        pending_close = startup_pending_close(B, cfg)
        if pending_close is not None: log(f"起動: 保有中の銘柄の週末前決済 {pending_close}（UTC）に起きる")
    except Exception as e:
        pending_close = pd.Timestamp.now(tz="UTC") + pd.Timedelta(seconds=RETRY_S)     # 60 秒後に入口なしで 1 回起きて計算し直す（金曜の最後の毎時〜T の間の起動で取れなかったときに週末を越さない・点検 11-13）
        log(f"起動: 週末前決済の時刻を計算できない（{e}）。{RETRY_S} 秒後に計算し直す")
    last_hourly = pd.Timestamp.now(tz="UTC").floor("h")                            # 毎時の判断（入口あり）を最後にした時間。起動した時間は「済み」（今までと同じく次の正時から）
    while True:
        try:
            now = pd.Timestamp.now(tz="UTC"); nxt, extra = next_wake(now, pending_close)
            if now.floor("h") > last_hourly:                                           # この時間の毎時の判断をまだしていない（遅い回・例外の待ちで :00:20 をまたいだ・点検 B-6）
                nxt, extra = min(nxt, now.floor("h") + pd.Timedelta(seconds=20)), False
            time.sleep(max(1, (nxt - pd.Timestamp.now(tz="UTC")).total_seconds()))
            now = pd.Timestamp.now(tz="UTC")
            if extra and now.floor("h") > last_hourly: extra = False                   # 起き直しが新しい時間に入ったら、その回は毎時の判断として入口も回す
            wait_for_bars(B, now); now = pd.Timestamp.now(tz="UTC")
            st, gapinfo = run_once(B, cfg, live, now=now, entries=not extra)
            if not extra: last_hourly = now.floor("h")
            log(f"済 判断 {st['判断の足']} 合図 {st['合図']} 保有 {st['保有中']} 累計R {st['累計R']:+.2f}")
            ng = set(st.get("週末前決済の失敗") or ())
            pending_close = next_pending_close(gapinfo, ng, now, lambda s: gap_before_min(cfg, s))
            if ng:
                rt = next_pending_close({s: g for s, g in gapinfo.items() if s in ng}, ng, now, lambda s: gap_before_min(cfg, s))
                log(f"週末前決済が通らなかった（{','.join(sorted(ng))}）→ {rt:%H:%M:%S} UTC にやり直す" if rt is not None
                    else f"★ 週末前決済が閉場までに通らなかった（{','.join(sorted(ng))}）。建玉は週末を越す")      # 点検 B-8
        except KeyboardInterrupt:
            break
        except Exception:
            log("エラー:\n" + traceback.format_exc()); time.sleep(60)
            if pending_close is not None and pd.Timestamp.now(tz="UTC") >= pending_close + pd.Timedelta(minutes=cfg["close_before_gap_min"]):
                pending_close = None                                        # 閉場（T＋close_before_gap_min）を過ぎたら消す。T を過ぎただけで消すと、T の回の 1 回の失敗で週末を越す（2026-11-12 点検）                                        # 過ぎた週末前決済の起床を残すと、MT5 が落ちている間 1 分おきにエラーを書き続ける（第 3 回・点検の指摘）
            try:
                B = Broker(cfg, live)
            except Exception as e:
                log(f"再接続できない: {e}")


if __name__ == "__main__":
    main()
