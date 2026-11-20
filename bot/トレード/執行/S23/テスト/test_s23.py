# -*- coding: utf-8 -*-
"""S23 の執行層の試験（Mac・偽の MT5・本物の bot・記録には触らない）。
使い方: 作業層/大容量/venv_forward/bin/python test_s23.py [--quick]
  1 判断の同等性: 記録の期間（2026-10-25 21:00〜）を 1 時間ずつ、signal_s23.decide の目標が記録の daily.csv の保有と全部同じか
  2 執行の再生: 偽の MT5（Binance の足・今の値段＝今の足の始値）で execute を 1 時間ずつ回し、台帳の保有の区間・入口・出口の値段が記録と同じか
  3〜9 場面: dry は発注しない／実口座なら --live で止まる／証拠金の歯止め／停止線／Binance が取れない／建玉が 2 本／台帳と建玉の食い違い／発注の失敗の起き直し
"""
import os, sys, shutil, tempfile, types, json, importlib, argparse
HERE = os.path.dirname(os.path.abspath(__file__)); S23 = os.path.abspath(os.path.join(HERE, ".."))
REAL_FWD = os.path.abspath(os.path.expanduser("~/ワークスペース/検証/トレード/forward"))
REC_H1 = os.path.expanduser("~/ワークスペース/作業層/大容量/market_data_forward/crypto_h1")
os.environ.setdefault("S23_FORWARD_DIR", REAL_FWD)
WORK = tempfile.mkdtemp(prefix="s23_test_"); H1 = os.path.join(WORK, "h1"); shutil.copytree(REC_H1, H1)   # 記録のデータは写しだけ読む
os.environ["MOCK_H1"] = H1
sys.path.insert(0, os.path.join(HERE, "mock")); sys.path.insert(0, S23)
sys.path.insert(0, os.path.expanduser("~/ワークスペース/検証/verification-lab/tools/mt5"))      # 本物の置き場所（トレード/執行/S23）なら execute が相対で見つける
import pandas as pd, numpy as np
import MetaTrader5 as M
import signal_s23 as SG
import execute_s23_mt5 as E

OK, NG = [], []
def check(name, cond, info=""):
    (OK if cond else NG).append(name); print(("ok   " if cond else "NG   ") + name + (f"  {info}" if info else ""), flush=True)


def fresh(tag):
    """台帳・ログ・状態・停止の置き場所を試験ごとの一時フォルダに替え、偽 MT5 を空にする。"""
    d = os.path.join(WORK, tag); os.makedirs(d, exist_ok=True)
    E.LEDGER_DIR = os.path.join(d, "台帳"); E.LEDGER = os.path.join(E.LEDGER_DIR, "trades.csv"); E.LOG_DIR = os.path.join(d, "ログ")
    E.STATE = os.path.join(d, "状態.json"); E.STOP_FLAG = os.path.join(d, "停止.flag"); E.CONFIG = os.path.join(d, "config.json"); E.H1_DIR = H1
    E.LOCK = os.path.join(d, "実行中.lock"); E.INTENT = os.path.join(d, "発注の控え.json")
    M._pos.clear(); M._deals.clear(); M.SENT.clear(); M.FAIL_NEXT[0] = 0; os.environ.pop("MOCK_REAL", None); os.environ.pop("MOCK_MARGIN_FREE", None)
    M.GHOST[0] = 0; M.PARTIAL[0] = None; M.PLACED_NOFILL[0] = 0; M.RETCODE[0] = None; M.ACC_SERVER[0] = "Mock-Demo"
    E.SG.fetch_to = lambda d: None                                                   # 取得はしない（H1 の写しを now で切って使う）
    importlib.reload(SG) if False else None
    return d


def intent_at(c, side, t, **kw):
    """発注の控えを、偽 MT5 の時刻 t で書く（本物は壁の時計で書く）。"""
    E.save_intent(c, side, **kw); j = E.load_intent(); j[c][side]["time"] = str(t); json.dump(j, open(E.INTENT, "w", encoding="utf-8"), ensure_ascii=False)


def record_daily(start=None):
    """記録と同じ計算の daily.csv（今の写しのデータで forward_s23 を走らせる）。start は記録の開始を前に置く長い再生用。"""
    r = SG.decide(H1, pd.Timestamp(pd.read_parquet(os.path.join(H1, "BTC.parquet"))["time"].max()) + pd.Timedelta(hours=1), start=start)
    return r["daily"]


def t1_signal(hours):
    rec = record_daily(); ng = []; n = 0
    real = pd.read_csv(os.path.join(REAL_FWD, "S23", "記録", "daily.csv"), index_col=0)   # 本物の記録（読むだけ）
    same = all(int(real.loc[k, f"保有_{c}"]) == int(rec.loc[k, f"保有_{c}"]) for k in real.index if k in rec.index for c in ("BTC", "ETH"))
    check("1a 写しのデータで走らせた記録の保有が本物の記録の daily.csv と同じ", same, f"{len(real)} 日")
    for now in hours:
        r = SG.decide(H1, now)
        for c in ("BTC", "ETH"):
            d = r["coins"][c]["日"]
            if d in rec.index:
                n += 1
                if int(r["coins"][c]["保有"]) != int(rec.loc[d, f"保有_{c}"]):
                    ng.append((str(now), c, d))
    check("1b 1 時間ずつの判断の目標が記録の保有と全部同じ", not ng and n > 0, f"{n} 件・違い {ng[:3]}")


def t2_replay(hours, start=None, tag="2"):
    fresh("replay" + tag); cfg = E.load_config(); cfg["check_mt5_bars"] = False
    real_decide = SG.decide
    if start:
        E.SG.decide = lambda h, n, start_=None: real_decide(h, n, start=start)
    B = E.Broker(cfg, live=True)
    bad_closed = []; n_sent = 0
    for now in hours:
        M.NOW[0] = now
        st, failed = E.run_once(B, cfg, True, now=now)
        if st.get("取引時間の外") and len(M.SENT) != n_sent:
            bad_closed.append(str(now))
        n_sent = len(M.SENT)
    E.SG.decide = real_decide
    L = pd.read_csv(E.LEDGER, dtype=str, keep_default_na=False) if os.path.exists(E.LEDGER) else pd.DataFrame()
    rec = record_daily(start)
    # 記録の保有の区間（保有 0→1 の日 d に入る＝exec_px[d]、1→0 の日 e に出る＝exec_px[e]）
    want = []
    for c in ("BTC", "ETH"):
        b = SG.FS.R.daily_series(H1, c); b = b.set_index(b["day"].astype(str).str[:10])
        p = rec[f"保有_{c}"].astype(int); prev = 0; s0 = None
        for d, v in p.items():
            if v == 1 and prev == 0: s0 = d
            if v == 0 and prev == 1: want.append((c, s0, d, float(b.loc[s0, "exec_px"]), float(b.loc[d, "exec_px"])))
            prev = v
        if prev == 1: want.append((c, s0, None, float(b.loc[s0, "exec_px"]), None))
    # 記録の最初の日に保有 1 で始まる区間は、記録の開始（FORWARD_START）より前に入ったもの。bot は最初の回に入るので入口の値段は比べない
    got = sorted([(r.coin, r.decision_day, r.exit_decision_day or None, float(r.entry_px), float(r.exit_px) if r.exit_px else None) for r in L.itertuples()], key=lambda x: (x[0], x[1]))
    want = sorted(want, key=lambda x: (x[0], x[1]))
    check(tag + "a 台帳の保有の区間（入る日・出る日）が記録と同じ", [(w[0], w[1], w[2]) for w in want] == [(g[0], g[1], g[2]) for g in got], f"記録 {[(w[0], w[1], w[2]) for w in want]} 台帳 {[(g[0], g[1], g[2]) for g in got]}")
    first = str(rec.index[0])
    px_ok = all(abs(g[3] - (w[3] + M.SPREAD[w[0]])) < 1e-6 and (w[4] is None or abs(g[4] - w[4]) < 1e-6) for w, g in zip(want, got) if w[1] != first)
    check(tag + "b 入口＝記録の始値＋スプレッド・出口＝記録の始値（偽 MT5 の今の値段の定義どおり）", px_ok and len(want) == len(got))
    pos_n = max((sum(1 for p in M._pos if p.symbol == s) for s in ("BTCUSD", "ETHUSD")), default=0)
    check(tag + "c 取引時間の外の回では 1 回も発注していない", not bad_closed, f"{bad_closed[:3]}")
    check(tag + "d 1 銘柄の建玉は最大 1 本", pos_n <= 1)
    sw = L[L["status"] == "closed"]["swap"].astype(float) if len(L) else pd.Series(dtype=float)
    check(tag + "e 決済の取り込みでスワップが台帳に入る（偽 MT5 は 1 晩 0.0694%）", len(sw) > 0 and (sw < 0).all(), f"{list(sw.round(0))}")
    print(f"   {tag}: 区間 {len(want)}・台帳 {len(got)}")
    import compare_s23 as CMP
    T = CMP.compare(L, H1, start); sm = CMP.summary(T); cl = T[T["超過コスト"].notna()]
    ok_in = np.allclose(T["入口の差"].to_numpy(float), [M.SPREAD[c] / x for c, x in zip(T["coin"], T["記録の入口"])], atol=1e-9, equal_nan=True)
    check(tag + "f 照合（compare_s23）: 区間が全部一致・取りこぼし 0・入口の差＝スプレッド÷値段・出口の差 0・超過コストが出る",
          ok_in and np.allclose(cl["出口の差"].to_numpy(float), 0, atol=1e-12) and len(cl) > 0 and sm["取りこぼし"] == 0 and sm["記録に無い保有"] == 0 and sm["一致"] == len(want),
          f"{sm['区間']} 区間・超過 平均 {sm['超過'] * 100:+.3f}%/本")
    L2 = L.iloc[1:].copy(); L2.loc[L2.index[0], "exit_decision_day"] = ""; T2 = CMP.compare(L2, H1, start); s2 = CMP.summary(T2)
    check(tag + "g 照合: 台帳の行が無い区間は取りこぼし・手で閉じた行は区間のずれ", s2["取りこぼし"] == 1 and s2["区間のずれ"] == 1)
    return L, want


def t2c_no_trade_in_closed():
    """取引時間の外（土曜）で、目標と建玉が違っても発注しない。"""
    fresh("closed"); cfg = E.load_config(); cfg["check_mt5_bars"] = False; B = E.Broker(cfg, live=True)
    now = pd.Timestamp("2026-11-08 12:00+00:00"); M.NOW[0] = now                    # 土曜
    E.run_once(B, cfg, True, now=now)
    check("2c 取引時間の外（土曜）では発注しない", len(M.SENT) == 0, f"送った {len(M.SENT)}")


def scenarios():
    now = pd.Timestamp("2026-11-03 21:01:00+00:00")                                 # 火曜。BTC・ETH とも目標 1 の日（記録 11-03）
    # 3 dry
    fresh("dry"); cfg = E.load_config(); cfg["check_mt5_bars"] = False; M.NOW[0] = now; B = E.Broker(cfg, live=False)
    st, _ = E.run_once(B, cfg, False, now=now)
    check("3 dry は発注しない・台帳に書かない", len(M.SENT) == 0 and not os.path.exists(E.LEDGER), f"目標 {st.get('目標')}")
    # 4 実口座
    fresh("nolive"); sys.argv = ["x", "--once", "--live"]
    try:
        E.main(); check("4a --live で config に expect_server が無ければ止まる", False)
    except SystemExit as e:
        check("4a --live で config に expect_server が無ければ止まる", "expect_server" in str(e) and len(M.SENT) == 0)
    fresh("real"); os.environ["MOCK_REAL"] = "1"; json.dump({"expect_server": "Mock-Demo"}, open(E.CONFIG, "w"))
    try:
        E.main(); check("4 実口座で --live なら止まる", False)
    except (SystemExit, RuntimeError) as e:
        check("4 実口座で --live なら止まる", "実口座" in str(e) and len(M.SENT) == 0)
    os.environ.pop("MOCK_REAL", None)
    # 5 証拠金
    fresh("margin"); os.environ["MOCK_MARGIN_FREE"] = "1000"; cfg = E.load_config(); cfg["check_mt5_bars"] = False; B = E.Broker(cfg, live=True)
    E.run_once(B, cfg, True, now=now)
    log = open(os.path.join(E.LOG_DIR, os.listdir(E.LOG_DIR)[0]), encoding="utf-8").read()
    check("5 余剰証拠金が足りなければ入らない（★）", len(M.SENT) == 0 and "証拠金が足りない" in log)
    os.environ.pop("MOCK_MARGIN_FREE", None)
    # 6 停止線
    fresh("stop"); cfg = E.load_config(); cfg["check_mt5_bars"] = False; B = E.Broker(cfg, live=True)
    E.run_once(B, cfg, True, now=now); n_in = len(M._pos)
    real_decide = E.SG.decide
    def stopped(h1, nw, start=None):
        r = real_decide(h1, nw); r["record"]["停止"] = ["最高値から -31.0%（停止線 −30%）"]; return r
    E.SG.decide = stopped
    E.run_once(B, cfg, True, now=now + pd.Timedelta(hours=1)); n_after = len(M._pos)
    E.SG.decide = real_decide
    E.run_once(B, cfg, True, now=now + pd.Timedelta(hours=2)); n_after2 = len(M._pos)
    check("6 停止線で全部閉じ、停止.flag があれば記録が戻っても入らない", n_in == 2 and n_after == 0 and n_after2 == 0 and os.path.exists(E.STOP_FLAG), f"{n_in}→{n_after}→{n_after2}")
    # 7 Binance が取れない
    fresh("nofetch"); cfg = E.load_config(); cfg["check_mt5_bars"] = False; cfg["fetch_tries"] = 1; B = E.Broker(cfg, live=True)
    E.run_once(B, cfg, True, now=now); n_in = len(M._pos)
    def boom(d): raise RuntimeError("BTC: Binance から取れない")
    E.SG.fetch_to = boom; E.time.sleep = lambda s: None
    st, _ = E.run_once(B, cfg, True, now=now + pd.Timedelta(days=2))                # 11-05 は目標 1 のまま（取れなければ何もしない）
    check("7 Binance が取れない回は何もしない（建玉はそのまま・状態に「取れない」）", len(M._pos) == n_in == 2 and st.get("判断") == "取れない")
    # 8 建玉が 2 本
    fresh("dup"); cfg = E.load_config(); cfg["check_mt5_bars"] = False; B = E.Broker(cfg, live=True)
    for _ in range(2):
        M.order_send(dict(action=M.TRADE_ACTION_DEAL, symbol="BTCUSD", volume=0.01, type=0, price=70000.0, magic=cfg["magic"], comment="x"))
    M.SENT.clear()
    E.run_once(B, cfg, True, now=now)
    btc_buys = [r for r in M.SENT if r["symbol"] == "BTCUSD" and "position" not in r]
    later = pd.Timestamp("2026-11-12 21:01:00+00:00"); M.NOW[0] = later              # BTC の目標 0 の日（記録 11-12 は 0）
    E.run_once(B, cfg, True, now=later)
    check("8 建玉が 2 本なら入らず、目標 0 で 2 本とも閉じる", not btc_buys and sum(1 for p in M._pos if p.symbol == "BTCUSD") == 0)
    # 9 台帳は開いているのに建玉が無い
    fresh("ghost"); cfg = E.load_config(); cfg["check_mt5_bars"] = False; B = E.Broker(cfg, live=True); M.NOW[0] = now
    E.save_ledger(pd.DataFrame([dict(id="x", coin="BTC", broker_sym="BTCUSD", decision_day="2026-11-02", entry_time="2026-11-02 21:00", entry_px="1", lot="0.01",
                                     notional="1", ticket="999999", status="open", note="")]))
    E.run_once(B, cfg, True, now=now)
    Lg = pd.read_csv(E.LEDGER, dtype=str, keep_default_na=False)
    check("9a 台帳が開いたまま建玉も約定も無い行は void にして、その回に入り直す", (Lg.loc[Lg["ticket"] == "999999", "status"] == "void").all() and any(r["symbol"] == "BTCUSD" for r in M.SENT))
    fresh("lag"); cfg = E.load_config(); cfg["check_mt5_bars"] = False; B = E.Broker(cfg, live=True); M.NOW[0] = now
    M._deals.append(types.SimpleNamespace(ticket=1, position_id=888888, entry=M.DEAL_ENTRY_IN, price=1.0, time=0, reason=0, profit=0.0, swap=0.0, commission=0.0, volume=0.01, magic=cfg["magic"]))
    E.save_ledger(pd.DataFrame([dict(id="y", coin="BTC", broker_sym="BTCUSD", decision_day="2026-11-02", entry_time="2026-11-02 21:00", entry_px="1", lot="0.01",
                                     notional="1", ticket="888888", status="open", note="")]))
    E.run_once(B, cfg, True, now=now)
    check("9b 入口の約定はあるが建玉も出口も見えない（履歴の遅れ）なら開いたまま・その銘柄は入らない（ETH は入る）",
          not any(r["symbol"] == "BTCUSD" for r in M.SENT) and any(r["symbol"] == "ETHUSD" for r in M.SENT))
    # 10 発注の失敗 → 5 分後に起き直し
    fresh("retry"); cfg = E.load_config(); cfg["check_mt5_bars"] = False; B = E.Broker(cfg, live=True); M.FAIL_NEXT[0] = 1
    st, failed = E.run_once(B, cfg, True, now=now)
    w = E.next_wake(now, failed, cfg["retry_min"])[0]
    st2, failed2 = E.run_once(B, cfg, True, now=now + pd.Timedelta(minutes=5))
    check("10 発注が通らなければ 5 分後に起き直し、次で入る", failed and w == now + pd.Timedelta(minutes=5) and not failed2 and len(M._pos) == 2)
    # 11 業者の足の照合の行
    fresh("check"); cfg = E.load_config(); cfg["check_mt5_bars"] = True; B = E.Broker(cfg, live=False); M.NOW[0] = now
    E.run_once(B, cfg, False, now=now)
    log = open(os.path.join(E.LOG_DIR, os.listdir(E.LOG_DIR)[0]), encoding="utf-8").read()
    check("11 業者の足でも同じ判断を出して照合の行を書く（偽 MT5 は同じ足なので一致）", "照合 BTC 記録の足 1" in log and "★ 違う" not in log)
    fresh("checkstale"); cfg = E.load_config(); cfg["check_mt5_bars"] = True; B = E.Broker(cfg, live=False); M.NOW[0] = now; M.STALE_H[0] = 24 * 19
    E.run_once(B, cfg, False, now=now); M.STALE_H[0] = 0
    log = open(os.path.join(E.LOG_DIR, os.listdir(E.LOG_DIR)[0]), encoding="utf-8").read()
    check("11b 業者の足が古い（履歴の取り寄せ中）なら照合を見送り、★ 違う を出さない", "業者の足が取れないか古い" in log and "★ 違う" not in log)
    # 12 返事が None でも約定していた
    fresh("ghostfill"); cfg = E.load_config(); cfg["check_mt5_bars"] = False; B = E.Broker(cfg, live=True); M.NOW[0] = now; M.GHOST[0] = 1
    E.run_once(B, cfg, True, now=now); E.run_once(B, cfg, True, now=now + pd.Timedelta(hours=1))
    Lg = pd.read_csv(E.LEDGER, dtype=str, keep_default_na=False); buys = [r for r in M.SENT if "position" not in r]
    check("12 返事が失敗（None）でも約定していれば、建玉で確かめて台帳に載せる・二重に買わない", len(buys) == 2 and len(Lg) == 2 and Lg["note"].str.contains("でも約定していた").any())
    # 13 部分約定
    fresh("partial"); cfg = E.load_config(); cfg["check_mt5_bars"] = False; B = E.Broker(cfg, live=True); M.NOW[0] = now; M.PARTIAL[0] = 0.005
    E.run_once(B, cfg, True, now=now); Lg = pd.read_csv(E.LEDGER, dtype=str, keep_default_na=False)
    check("13 部分約定なら台帳のロットは約定した量・note に部分約定", (Lg["lot"].astype(float) == 0.005).any() and Lg["note"].str.contains("部分約定").any())
    # 14 PLACED のまま約定しない
    fresh("placed"); cfg = E.load_config(); cfg["check_mt5_bars"] = False; B = E.Broker(cfg, live=True); M.NOW[0] = now; M.PLACED_NOFILL[0] = 1
    st, rt = E.run_once(B, cfg, True, now=now); Lg = pd.read_csv(E.LEDGER, dtype=str, keep_default_na=False)
    st2, rt2 = E.run_once(B, cfg, True, now=now + pd.Timedelta(minutes=5)); Lg2 = pd.read_csv(E.LEDGER, dtype=str, keep_default_na=False)
    check("14 PLACED でも建玉が現れなければ失敗として起き直し、台帳に開いた行を残さない・次で入る", rt and len(Lg) == 1 and not rt2 and len(Lg2) == 2 and len(M._pos) == 2)
    # 15 直らない拒否
    fresh("noretry"); cfg = E.load_config(); cfg["check_mt5_bars"] = False; B = E.Broker(cfg, live=True); M.NOW[0] = now; M.RETCODE[0] = 10027
    _real = E.SG.decide
    E.SG.decide = (lambda real: (lambda h, n, start=None: (lambda r: (r["coins"].__setitem__("ETH", dict(r["coins"]["ETH"], 保有=False)), r)[1])(real(h, n))))(_real)
    st, rt = E.run_once(B, cfg, True, now=now); E.SG.decide = _real                # 元に戻す（E.SG と SG は同じモジュールなので、SG.decide で戻すと差し替えたままになる）
    check("15 自動売買オフ（10027）は起き直さない（★）", not rt and len(M._pos) == 0)
    # 16 Binance の足が古い
    fresh("stale"); cfg = E.load_config(); cfg["check_mt5_bars"] = False; cfg["fetch_tries"] = 2; B = E.Broker(cfg, live=True); M.NOW[0] = now
    st, rt = E.run_once(B, cfg, True, now=now + pd.Timedelta(days=30))              # 足は 11-17 まで・now は 12-03 → 古い
    check("16 Binance の最後の足が古ければ動かない（起き直す）", rt and st.get("判断") == "取れない" and "古い" in st.get("理由", "") and len(M.SENT) == 0)
    # 17 前に動いた日より古い判断
    fresh("older"); cfg = E.load_config(); cfg["check_mt5_bars"] = False; B = E.Broker(cfg, live=True); M.NOW[0] = now
    json.dump({"動いた判断の日": {"BTC": "2026-11-05", "ETH": "2026-11-05"}}, open(E.STATE, "w"))
    st, rt = E.run_once(B, cfg, True, now=now)
    check("17 前に動いた判断の日より古い日の目標では動かない", len(M.SENT) == 0 and rt)
    # 18 二重起動
    fresh("lock"); k1 = E.single_instance()
    try: E.single_instance(); check("18 同時に 2 つは動かない（鍵）", False)
    except RuntimeError: check("18 同時に 2 つは動かない（鍵）", True)
    k1.close()
    # 19 台帳に無い建玉の取り込み
    fresh("orphan"); cfg = E.load_config(); cfg["check_mt5_bars"] = False; B = E.Broker(cfg, live=True); M.NOW[0] = now
    M.order_send(dict(action=M.TRADE_ACTION_DEAL, symbol="ETHUSD", volume=0.4, type=0, price=3000.0, magic=cfg["magic"], comment="x")); M.SENT.clear()
    E.run_once(B, cfg, True, now=now); Lg = pd.read_csv(E.LEDGER, dtype=str, keep_default_na=False)
    check("19 台帳に無い自分の建玉は取り込み、二重に買わない（BTC だけ買う）", Lg["note"].str.contains("後から取り込み").sum() == 1 and [r["symbol"] for r in M.SENT if "position" not in r] == ["BTCUSD"])
    # 20 起きる時刻
    check("20 毎時 :01:00 に起きる（時計の進みに備える）", E.next_wake(pd.Timestamp("2026-11-18 21:00:10+00:00"), False, 5)[0] == pd.Timestamp("2026-11-18 22:01:00+00:00"))
    # 22 途中で実口座に替わる
    fresh("toreal"); cfg = E.load_config(); cfg["check_mt5_bars"] = False; cfg["expect_server"] = "Mock-Demo"; B = E.Broker(cfg, live=True); M.NOW[0] = now
    os.environ["MOCK_REAL"] = "1"
    try: E.run_once(B, cfg, True, now=now); check("22 動いている途中に実口座へ替わったら売買せずに止まる", False)
    except RuntimeError as e: check("22 動いている途中に実口座へ替わったら売買せずに止まる", "実口座" in str(e) and len(M.SENT) == 0)
    os.environ.pop("MOCK_REAL", None)
    # 23 発注の控えを使った取り込み（返事は失敗でも約定していた形）
    fresh("intent_in"); cfg = E.load_config(); cfg["check_mt5_bars"] = False; B = E.Broker(cfg, live=True); M.NOW[0] = now
    intent_at("ETH", "in", now, day="2026-11-02"); M.order_send(dict(action=M.TRADE_ACTION_DEAL, symbol="ETHUSD", volume=0.4, type=0, price=3000.0, magic=cfg["magic"], comment="S23 ETH 1102"))
    E.run_once(B, cfg, True, now=now); Lg = pd.read_csv(E.LEDGER, dtype=str, keep_default_na=False); r_ = Lg[Lg["coin"] == "ETH"].iloc[0]
    check("23 取り込みの行は発注の控えの判断の日と名目を持つ", r_["decision_day"] == "2026-11-02" and "返事は失敗でも約定" in r_["note"] and float(r_["notional"]) > 0)
    # 24 返事は失敗でも閉じていた決済
    later = pd.Timestamp("2026-11-12 21:01:00+00:00"); M.NOW[0] = later
    intent_at("ETH", "out", later, day="2026-11-11", why="上昇トレンドの終わり")
    p_ = next(x for x in M._pos if x.symbol == "ETHUSD"); M.order_send(dict(action=M.TRADE_ACTION_DEAL, symbol="ETHUSD", volume=p_.volume, type=1, position=p_.ticket, price=2000.0, magic=cfg["magic"], comment="x"))
    E.run_once(B, cfg, True, now=later); Lg = pd.read_csv(E.LEDGER, dtype=str, keep_default_na=False); r_ = Lg[Lg["coin"] == "ETH"].iloc[0]
    check("24 bot が閉じに行った控えの後の決済は bot の決済（出る判断の日つき）", r_["status"] == "closed" and "閉じていた" in r_["why"] and r_["exit_decision_day"] == "2026-11-11")
    # 25 相殺（OUT_BY）の決済も出口とみなす
    fresh("outby"); cfg = E.load_config(); cfg["check_mt5_bars"] = False; B = E.Broker(cfg, live=True); M.NOW[0] = now
    E.save_ledger(pd.DataFrame([dict(id="z", coin="BTC", broker_sym="BTCUSD", decision_day="2026-11-02", entry_time="2026-11-02 21:01:00+00:00", entry_px="100000", lot="0.01",
                                     notional="1", ticket="777777", status="open", note="")]))
    M._deals += [types.SimpleNamespace(ticket=1, position_id=777777, entry=M.DEAL_ENTRY_IN, price=100000.0, time=0, reason=0, profit=0.0, swap=0.0, commission=0.0, volume=0.01, magic=cfg["magic"]),
                 types.SimpleNamespace(ticket=2, position_id=777777, entry=3, price=101000.0, time=M._srv(now), reason=0, profit=1.0, swap=-5.0, commission=0.0, volume=0.01, magic=0)]
    E.run_once(B, cfg, True, now=now); Lg = pd.read_csv(E.LEDGER, dtype=str, keep_default_na=False)
    check("25 相殺（OUT_BY）でも決済として取り込み、その銘柄に入り直せる", (Lg.loc[Lg["ticket"] == "777777", "status"] == "closed").all() and any(r["symbol"] == "BTCUSD" and "position" not in r for r in M.SENT))
    # 26 照合: 遅れて入った区間も結ぶ
    import compare_s23 as CMP
    Lx = pd.DataFrame([dict(id="a", coin="BTC", broker_sym="BTCUSD", decision_day="2026-10-27", entry_time="2026-10-27 21:01:00+00:00", entry_px="114000", lot="0.01", notional="170000",
                            ticket="1", status="closed", exit_decision_day="2026-11-12", exit_time="2026-11-12 21:01:00+00:00", exit_px="101000", why="上昇トレンドの終わり", ret="", profit="", swap="-2000", commission="", note="")])
    T_ = CMP.compare(Lx, H1); b_ = T_[(T_["coin"] == "BTC") & (T_["記録_入る日"] == "2026-10-26")].iloc[0]
    check("26 照合: 1 日遅れて入った保有も区間に結び、取りこぼしにしない（区間のずれに遅れと出る）", b_["状態"] == "closed" and "遅れ" in str(b_["区間のずれ"]) and b_["入口の遅れ_h"] > 20)
    # 21 許容滑りは銘柄ごと（スプレッド × 倍率）
    check("21 許容滑りはスプレッドに比例（BTC 4000・ETH 300 ポイント）", B.deviation(M.symbol_info("BTCUSD")) == 4000 and B.deviation(M.symbol_info("ETHUSD")) == 300)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--quick", action="store_true"); a = ap.parse_args()
    import mt5_fetch as MF
    end = pd.read_parquet(os.path.join(H1, "BTC.parquet"))["time"].max() + pd.Timedelta(hours=1)
    hours = list(pd.date_range("2026-10-25 21:01:00+00:00", end, freq="h"))
    if a.quick:
        hours = [h for h in hours if h.hour in (20, 21, 22)]
    t1_signal(hours)
    t2c_no_trade_in_closed()
    t2_replay([h for h in hours if h >= pd.Timestamp("2026-10-26 21:01:00+00:00")])   # 記録の最初の日（10-26）の判断から
    long_h = [h for h in pd.date_range("2026-04-06 21:01:00+00:00", hours[-1], freq="h") if h.hour in (20, 21, 22) or (a.quick is False and h.hour % 6 == 0)]
    t2_replay(long_h, start="2026-04-05 21:00:00+00:00", tag="2L")                 # 長い再生（記録の開始を 4 月に置いた計算と比べる・区間が多い）
    scenarios()
    print(f"\n{len(OK)}/{len(OK) + len(NG)} 合格" + (f"・NG: {NG}" if NG else ""))
    shutil.rmtree(WORK, ignore_errors=True)
    sys.exit(1 if NG else 0)


if __name__ == "__main__":
    main()
