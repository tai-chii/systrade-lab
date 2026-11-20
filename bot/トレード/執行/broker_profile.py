"""broker_profile.py — 業者ごとの違いを 1 枚のプロファイル（brokers/<名前>.json）に寄せる（提案・2026-11-06 昼の自走 P4・未導入）

運用の決まり 2026-11-05「業者を替えやすい作り」のため。今は業者の違いが 4 か所に散っている。
  - bot の config.json（tz・symbol_map・接続先・equity_override・deviation_points）… winnote で手で書き換え（winnote_config_変更.log）
  - 実測スプレッドのラベル（spread_sampler.py --label）と集計（spread_report.py --label）
  - 手数料（ECN 口座）… どこにも無い（compare_record の実測コストに入らない・s21-broker-swap の「限り」）
  - 最小ロットのゆがみ（s21-demo-lot）… 業者の volume_min と契約サイズで変わるのに、配備後にしか分からない
プロファイルはこれらを 1 枚に持ち、bot の config には「業者の鍵」だけを書き込む。売買の規則の鍵（magic・risk_pct・max_positions など）は
プロファイルから変えられない（変えようとしたら止まる）＝業者を替えても戦略は変わらないことを作りで守る。

使い方（Mac で確かめる・winnote へは配備の道具 s21-deploy-kit の --config で送る）:
  python broker_profile.py diff  brokers/XM.json  <今の config.json>      # 業者の鍵の差だけを出す（XM なら差 0 のはず）
  python broker_profile.py apply brokers/OANDA.json <今の config.json> -o 新しい config.json
preflight(profile, cfg, mt5) は MT5（本物か偽）につないで、銘柄 19/19・tz の見張り・口座通貨・最小ロットの倍率・ロットの式の検算 を返す（--once の前の確かめ）。
  python broker_profile.py preflight brokers/<業者>.json <config.json>     # 業者を替える日に、その業者の MT5 を開いた PC で（注文は出さない・bot の記録には書かない・2026-11-13）
"""
import argparse
import copy
import json
import math
import sys

BROKER_KEYS = {"server", "mt5_path", "login", "password", "tz", "symbol_map", "equity_override", "deviation_points", "expect_server"}   # expect_server: つないだ先の確かめ（bot の第 4 回・2026-11-13）
STRATEGY_KEYS = {"magic", "risk_pct", "max_positions", "close_before_gap_min", "history_bars", "spr_source", "spr_ref_max_age_days", "symbols"}
TZ_OK = {"eet", "nyclose", "server", "auto"}
SECRET = {"login", "password"}            # プロファイル（Mac の git 管理外でも）に書かない。winnote の config にだけ置く
INDEX = ("US500", "USTECH", "GER40", "JPN225")


def load(path):
    p = json.load(open(path, encoding="utf-8"))
    errs = validate(p)
    if errs:
        raise ValueError(f"{path}: " + "／".join(errs))
    return p


def validate(p):
    e = []
    for k in ("name", "account_currency", "exec", "cost"):
        if k not in p:
            e.append(f"{k} が無い")
    ex = p.get("exec", {})
    bad = set(ex) - BROKER_KEYS
    if bad & STRATEGY_KEYS:
        e.append(f"売買の規則の鍵はプロファイルで変えられない: {sorted(bad & STRATEGY_KEYS)}")
    elif bad:
        e.append(f"知らない鍵: {sorted(bad)}")
    if set(ex) & SECRET:
        e.append("login・password はプロファイルに書かない（winnote の config にだけ置く）")
    tz = ex.get("tz")
    if tz is not None and tz not in TZ_OK:
        try:
            int(tz)
        except (TypeError, ValueError):
            e.append(f"tz が読めない: {tz}")
    if not isinstance(ex.get("symbol_map", {}), dict):
        e.append("symbol_map は {S21 の名前: 業者の名前}")
    return e


def apply(profile, cfg):
    """今の config に業者の鍵だけを書き込んだ新しい config を返す。売買の規則の鍵は元のまま（変わっていたら止まる）。
    プロファイルに書いていない鍵は触らない（winnote の config の接続先・login はそのまま残る）"""
    new = copy.deepcopy(cfg)
    for k, v in profile["exec"].items():
        new[k] = copy.deepcopy(v)
    changed = [k for k in STRATEGY_KEYS if cfg.get(k) != new.get(k)]
    if changed:
        raise AssertionError(f"売買の規則の鍵が変わった: {changed}")
    return new


def diff(profile, cfg):
    """業者の鍵で、プロファイルと今の config が違うもの [(鍵, 今, プロファイル)]"""
    return [(k, cfg.get(k), v) for k, v in profile["exec"].items() if cfg.get(k) != v]


def asset_class(s):
    return "IDX" if s in INDEX else ("METAL" if s.startswith("XAU") else "FX")


def commission_R(profile, s, lot, per_lot_D):
    """往復の手数料を R に直す（ECN 口座の分。compare_record の実測コストに足す用）。per_lot_D は 1 ロットで D 動いたときの損益（口座通貨）"""
    c = profile["cost"].get("commission_per_lot_round", {}).get(asset_class(s), 0) or 0
    return 0.0 if c == 0 else c / per_lot_D           # ロット数は分子（手数料 × lot）と分母（1R × lot）で消える


LOT_TOL = 0.02   # ロットの式の検算で許すずれ（買値と売値の差・為替の bid/ask の分。XM の実績 119 件では 0.3% 以内だった）


def preflight(profile, cfg, E, mt5mod, D_of=None):
    """MT5（本物か偽）につないで、プロファイルを当てた config で bot が動けるかを確かめる（注文はしない）。
    E は execute_mt5 のモジュール。D_of(s, B) は D（1R の値動き）を返す関数（無ければ今の値段の 0.5%）。
    戻り値 dict: 銘柄（見つかった数と見つからない名前）・tz の ★・口座通貨の一致・最小ロットの倍率（狙いのリスクに対する最小ロットのリスク）・
    ロットの式の検算（2026-11-13・監査D の 5）: MT5 が自分で計算する損益（order_calc_profit・注文は出さない）÷ bot の式「D × 契約サイズ × 損益通貨→口座通貨」。
    先物型の指数など「値幅 × 契約サイズ」で損益が出ない銘柄では比が 1 から外れる（桁でずれる）。LOT_TOL を超えた銘柄は「式が合わない」に入る。"""
    c = apply(profile, cfg)
    B = E.Broker(c, live=False)
    out = {"つないだ先": B.acc.server, "銘柄の対応": dict(B.names), "銘柄": (len(B.names), sorted(set(c.get("symbols") or E.MF.S21) - set(B.names))),
           "tz": B.tz_warn, "口座通貨": (B.acc.currency, profile["account_currency"], B.acc.currency == profile["account_currency"])}
    ratio = {}; check = {}
    eq = c["equity_override"] or mt5mod.account_info().equity
    risk = eq * c["risk_pct"]
    for s, n in B.names.items():
        info = mt5mod.symbol_info(n)
        t = mt5mod.symbol_info_tick(n)
        D = D_of(s, B) if D_of else (t.bid * 0.005 if t and t.bid else None)
        rate = B.fx_to_account(info.currency_profit)
        if not D or rate is None:
            ratio[s] = None; check[s] = None
            continue
        per = D * info.trade_contract_size * rate
        ratio[s] = info.volume_min * per / risk
        calc = getattr(mt5mod, "order_calc_profit", None); px = t.ask if t and t.ask else None       # 検算: 1 ロットを買って D 下がったときの損（口座通貨）
        got = calc(mt5mod.ORDER_TYPE_BUY, n, 1.0, px, px - D) if (calc and px) else None
        check[s] = (abs(got) / per) if (got is not None and per > 0) else None
    out["最小ロットの倍率"] = ratio
    out["ロットの式の検算"] = check
    out["式が合わない"] = sorted(s for s, r in check.items() if r is not None and abs(r - 1) > LOT_TOL)
    out["検算できない"] = sorted(s for s, r in check.items() if r is None)
    out["1.5 倍を超える"] = sorted([s for s, r in ratio.items() if r is not None and r > 1.5], key=lambda s: -ratio[s])
    return out


def preflight_cli(p, cfg, bot_dir=None, mt5mod=None, E=None, out=print):
    """本物の MT5 で preflight を回して読める形で出す（業者を替える日・注文は出さない・2026-11-13）。
    bot の台帳・ログ・状態.json は一時フォルダに向けるので、動いている bot の記録には何も書かない。終了コード: 0 よい／1 式が合わない・銘柄が欠ける・口座通貨が違う・つないだ先が違う／2 検算できない銘柄がある／3 サーバー時間の ★ だけ。
    login を書いた config を、動いている bot と同じ端末に向けて打たない（口座が切り替わる恐れ・点検 11-13）。"""
    import os, tempfile
    if E is None:
        here = os.path.dirname(os.path.abspath(__file__)); bd = bot_dir or os.path.join(here, "S21")
        sys.path[:0] = [bd, os.path.join(here, "..", "..", "verification-lab", "tools", "mt5")]
        import execute_mt5 as E
    if mt5mod is None:
        import MetaTrader5 as mt5mod
    tmp = tempfile.mkdtemp(prefix="s21_preflight_")
    E.LEDGER_DIR = os.path.join(tmp, "台帳"); E.LOG_DIR = os.path.join(tmp, "ログ"); E.LEDGER = os.path.join(E.LEDGER_DIR, "trades.csv"); E.STATE = os.path.join(tmp, "状態.json")
    try:
        r = preflight(p, cfg, E, mt5mod)
    except RuntimeError as e:                                                      # 第 4 回の bot は、つないだ先が expect_server と違うと接続で止まる。読める 1 行にして終える（点検 B-3）
        out(f"★ {e}"); return 1
    want = (p.get("exec") or {}).get("expect_server") or cfg.get("expect_server")
    out(f"つないだ先: {r['つないだ先']}" + (f"（expect_server {want}）" if want else "（expect_server が無いので、狙った業者の端末かは上の名前を目で確かめる。プロファイルの exec に expect_server を書くと自動で比べる）"))
    if want and r["つないだ先"] != want:
        out(f"★ つないだ先が違う（狙い {want}）。別の MT5 を検算している。config の mt5_path で端末を指定して打ち直す"); return 1
    out(f"業者 {p['name']}: 銘柄 {r['銘柄'][0]} 本" + (f"・見つからない {r['銘柄'][1]}" if r["銘柄"][1] else "") + f"・口座通貨 {r['口座通貨'][0]}（プロファイル {r['口座通貨'][1]}）" + (f"・{r['tz']}" if r["tz"] else ""))
    diff_names = {s: n for s, n in r["銘柄の対応"].items() if n != s}                  # 名前の自動探索は別の商品（先物・micro など）に当たりうる（監査D の 6）。違う名前に当たった銘柄を全部出して目で確かめる
    out("銘柄の対応（業者の名前が違うもの・先物やミニでないかを目で確かめる）: " + ("・".join(f"{s}→{n}" for s, n in sorted(diff_names.items())) if diff_names else "全部同じ名前"))
    ck = {s: v for s, v in r["ロットの式の検算"].items() if v is not None}
    if ck:
        out(f"ロットの式の検算（MT5 の計算 ÷ bot の式・1 なら合う・1 より大きいと bot のロットが大きすぎる）: {min(ck.values()):.4f}〜{max(ck.values()):.4f}（{len(ck)} 銘柄）")
    if r["式が合わない"]:
        out("★ 式が合わない（この業者ではロットが桁でずれる。発注しない銘柄に入れるか、式を直すまで動かさない）: " + "・".join(f"{s} {r['ロットの式の検算'][s]:.3f}" for s in r["式が合わない"]))
    if r["検算できない"]:
        out("検算できない（MT5 が損益を返さない・値が来ていない。開場中に打ち直す）: " + "・".join(r["検算できない"]))
    top = sorted(((v, s) for s, v in r["最小ロットの倍率"].items() if v is not None), reverse=True)[:5]
    out("最小ロットのリスク ÷ 狙いのリスク（上位）: " + "・".join(f"{s} {v:.2f}" for v, s in top) + (f"　1.5 倍を超える: {r['1.5 倍を超える']}" if r["1.5 倍を超える"] else ""))
    if r["式が合わない"] or r["銘柄"][1] or not r["口座通貨"][2]:
        return 1
    if r["検算できない"]:
        return 2
    return 3 if r["tz"] else 0                                                     # 3: サーバー時間の ★ だけ（config の tz を直してから動かす・点検 B-2）


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["diff", "apply", "check", "preflight"])
    ap.add_argument("profile")
    ap.add_argument("config", nargs="?")
    ap.add_argument("-o", "--out")
    ap.add_argument("--bot-dir", default=None, help="preflight: execute_mt5.py のあるフォルダ（既定は このファイルの隣の S21）")
    a = ap.parse_args()
    p = load(a.profile)
    if a.cmd == "check":
        print(f"{p['name']}: 書式 OK")
        return 0
    cfg = json.load(open(a.config, encoding="utf-8"))
    if a.cmd == "preflight":
        return preflight_cli(p, cfg, a.bot_dir)
    if a.cmd == "diff":
        d = diff(p, cfg)
        for k, now, new in d:
            print(f"{k}: {json.dumps(now, ensure_ascii=False)} → {json.dumps(new, ensure_ascii=False)}")
        print(f"差 {len(d)}")
        return 0
    new = apply(p, cfg)
    if not a.out:
        print(json.dumps(new, ensure_ascii=False, indent=1))
    else:
        json.dump(new, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"書いた: {a.out}（差 {len(diff(p, cfg))}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
