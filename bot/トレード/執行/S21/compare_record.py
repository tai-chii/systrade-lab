# -*- coding: utf-8 -*-
"""執行の台帳（台帳/trades.csv）と記録（forward/S21/記録/trades_latest.csv）を突き合わせる。
同じ（銘柄・判断の足）で入ったか、同じ行動か、決済の理由は同じか、入口と出口の値段の差（スプレッド＋滑り＝実測コスト）はいくらか。
2026-11-05 直し（監査B の 2）:
  - 記録はデータが UTC の昨日までなので、判断の足が「記録のデータの最後 − 1 時間」より後の取引は比べない（遅れを「執行だけ」と数えない）
  - bot の版（下の ERAS）ごとに分けて数える。前の版の不具合（1 時間古い足・XM のスプレッドで判断）の分を新しい版の一致率に混ぜない
  - 実測コストは入口と出口の両方の値段の差で見る（以前は入口だけ）。記録の R は保有コストを引くので、R の差はその分 bot に有利に出る
2026-11-10 足し（taichi 承認）:
  - 「合図の一致」＝記録が入った（銘柄・判断の足）で、bot も同じ向きの合図を出していたか（入ったか見送ったかは問わない）。bot のログ run_YYYYMM.log の「入る／見送り」から読む
    「同じ足で入った」は同時 1 本・週 10 回の規則で 1 回のずれが後ろへ連鎖するので、足の差（XM と Dukascopy）そのものはこちらで見る
  - 記録だけの取引を「bot に合図なし／合図はあったが見送り（理由）」に分けて出す
使い方: python compare_record.py [--ledger CSV] [--record CSV] [--since ISO] [--logs DIR]"""
import argparse, glob, json, os, re
import pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
REC = os.path.join(HERE, "..", "..", "forward", "S21", "記録")
# bot の版（入った足の時刻 UTC で分ける）。版を替えたら 1 行足す（トレード/forward/変更履歴.csv と同じ時刻）
ERAS = [("2026-10-31 12:00", "初版（10-31 に発注が通り始めた・1 時間古い足の不具合あり）"),
        ("2026-11-02 16:00", "足の遅れの直し（Q648）"),
        ("2026-11-04 16:00", "判断のスプレッドを記録に揃えた版（監査B の 1）"),
        ("2026-11-16 16:00", "第4回（週末前決済の再試行・指数の早じまい・週越しの決済・口座の照合〔切〕）")]


def era_of(entry_hour):
    k = -1
    for i, (t, _) in enumerate(ERAS):
        if entry_hour >= pd.Timestamp(t, tz="UTC"):
            k = i
    return k


RUN_MAX_MIN = 15   # 1 回の毎時の回の長さの上限（分）。これより前の「入る／見送り」は、その回の行と見なさない


def read_logs(dirs):
    """bot のログから、判断の足ごとの合図を読む。返り値: (ログのある判断の足の集合, {(銘柄, 判断の足): (入る/見送り, 向き, RR, 見送りの理由)})"""
    hours, sig, cur, wake = set(), {}, [], False
    paths = sorted({p for d in dirs for p in glob.glob(os.path.join(d, "run_*.log"))}, key=os.path.basename)
    for p in paths:
        for ln in open(p, encoding="utf-8", errors="replace"):
            m = re.match(r"(\S+ \S+) (入る|見送り) (\w+) (買い|売り) RR([\d.]+)(?:: (.*))?", ln)   # [dry] の行は数えない
            if m:
                cur.append((pd.Timestamp(m.group(1)), m.group(2), m.group(3), m.group(4), float(m.group(5)), (m.group(6) or "").strip() if m.group(2) == "見送り" else "")); continue
            if re.match(r"\S+ \S+ (エラー:|Traceback)", ln):                    # 回が途中で落ちた → その回の行は数えない（再点検の指摘）
                cur = []; continue
            if re.match(r"\S+ \S+ 週末前決済の起床: 入口は回さない", ln):          # 起床の回の「済 判断」は判定の足に数えない（入口を回していない）
                wake = True; continue
            m = re.match(r"(\S+ \S+) 済 判断 (\S+ \S+)", ln)
            if m:
                if wake:
                    wake = False; cur = []; continue
                d = pd.Timestamp(m.group(2)); d = d.tz_localize("UTC") if d.tzinfo is None else d.tz_convert("UTC"); hours.add(d)
                # 2026-11-16（昼の自走・別の目の点検）: 同じ回の行だけを数える。例外で「済 判断」まで行かなかった回の「入る／見送り」が、次の回の足に付かないように
                #   （1 回の毎時の回は 1〜2 分で終わる。RUN_MAX_MIN より前の行は捨てる）
                t_done = pd.Timestamp(m.group(1))
                for t, k, s, side, rr, why in cur:
                    if pd.Timedelta(0) <= t_done - t <= pd.Timedelta(minutes=RUN_MAX_MIN):
                        sig[(s, d)] = (k, side, rr, why)
                cur = []
    return hours, sig


def signal_match(r, hours, sig):
    """記録の入口 r のうち bot のログがある足について: (比べた件数, 同じ向きの合図, RR も同じ)"""
    n = same = same_rr = 0
    for x in r.itertuples():
        if x.decision not in hours:
            continue
        n += 1; g = sig.get((x.sym, x.decision))
        if g and g[1] == x.side:
            same += 1; same_rr += int(abs(g[2] - float(x.rr)) < 1e-9)
    return n, same, same_rr


# 2026-11-16（昼の自走・案）: 記録の予測が閾値を大きく超えた入口（pred_over_thr ≥ MARGIN_HI）は、足の差（XM と Dukascopy）では
#   ほぼ反転しない。今の版で 32/33（97%）一致・初版（1 時間古い足の不具合）は 2/5（40%）・足の遅れの直しの版は 5/6（83%）。
#   閾値すれすれの合図のぶれ（今の版で余裕 < 0.04 は 51%）に埋もれずに、判断の計算の食い違い（不具合）だけを見る。
#   ★ は今の版の直近 HI_N 件で一致が HI_MIN を下回ったとき（版を替えた直後の HI_N_MIN〜HI_N−1 件は HI_MIN_EARLY）。正常 97〜99% なら 1 回の判定の誤報は 20 件で 0.03% 以下（版の直後の 10〜19 件では 97% で 0.3%）、
#   前の版の不具合の形（記録側の合図すべてで 73〜74%）は 20 件で 2/3 の確率、40% なら確実に拾う。
#   片側だけ（記録が合図を出した足）を見る。bot が余計に合図を出す不具合は拾えない（../パッチ_余裕のログ/ で両側から見られるようにする案）。
MARGIN_HI, HI_N, HI_MIN, HI_N_MIN, HI_MIN_EARLY = 0.04, 20, 0.80, 10, 0.75   # 20 件そろえば 80% 未満で ★。版を替えた直後の 10〜19 件は 75% 未満で ★（別の目の点検）


def signal_match_hi(r, hours, sig):
    """記録の入口のうち余裕の大きいもの（pred_over_thr ≥ MARGIN_HI）について、判断の足の順に [一致したか] を返す"""
    if "pred_over_thr" not in r.columns:
        return []
    out = []
    for x in r.sort_values(["decision", "sym"]).itertuples():
        if x.decision not in hours or not (float(x.pred_over_thr) >= MARGIN_HI):
            continue
        g = sig.get((x.sym, x.decision)); out.append(bool(g and g[1] == x.side))
    return out


def hi_text(flags, star):
    """「・余裕の大きい合図の一致 a/b（c%）」。star のとき、直近 HI_N 件で HI_MIN 未満なら ★ を付ける"""
    if not flags:
        return ""
    t = f"・余裕 ≥{MARGIN_HI} の合図の一致 {sum(flags)}/{len(flags)}（{sum(flags) / len(flags):.0%}）"
    last = flags[-HI_N:]
    lim = HI_MIN if len(last) >= HI_N else HI_MIN_EARLY
    if star and len(last) >= HI_N_MIN and sum(last) / len(last) < lim:
        t += f"・★ 直近 {len(last)} 件で {sum(last)}/{len(last)}（{lim:.0%} 未満・判断の計算が記録と食い違っている恐れ）"
    return t


def summary(R, L):
    m = R.merge(L, on=["sym", "decision"], how="outer", suffixes=("_記録", "_執行"), indicator=True)
    both = m[m["_merge"] == "both"]
    same_a = int((both["a_記録"].astype(float) == pd.to_numeric(both["a_執行"], errors="coerce")).sum())
    n = len(R) + int((m["_merge"] == "right_only").sum())
    return m, both, same_a, n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", default=os.path.join(HERE, "台帳", "trades.csv"))
    ap.add_argument("--record", default=os.path.join(REC, "trades_latest.csv"))
    ap.add_argument("--since", default=None, help="この時刻以降の判断だけ（既定は最初の版の始まり）")
    ap.add_argument("--logs", default=None, help="bot のログ run_YYYYMM.log の置き場（既定は台帳と同じフォルダと、その隣の ログ/）")
    a = ap.parse_args()
    led_dir = os.path.dirname(os.path.abspath(a.ledger))
    hours, sig = read_logs([a.logs] if a.logs else [led_dir, os.path.join(led_dir, "..", "ログ"), os.path.join(HERE, "ログ")])
    L = pd.read_csv(a.ledger, dtype=str, keep_default_na=False); R = pd.read_csv(a.record)
    for c in ["R", "entry_px", "exit_px", "D"]:
        L[c] = pd.to_numeric(L[c], errors="coerce")
    L["decision"] = pd.to_datetime(L["decision"], utc=True); R["decision"] = pd.to_datetime(R["decision"], utc=True)
    try:
        end = pd.Timestamp(json.load(open(os.path.join(REC, "状態.json"), encoding="utf-8"))["データの最後"]) - pd.Timedelta(hours=1)
    except Exception:
        end = R["decision"].max()
    since = pd.Timestamp(a.since) if a.since else pd.Timestamp(ERAS[0][0], tz="UTC")
    L = L[(L["decision"] >= since) & (L["decision"] <= end)]; R = R[(R["decision"] >= since) & (R["decision"] <= end)]
    for X in (L, R):
        X["版"] = (X["decision"] + pd.Timedelta(hours=1)).map(era_of)
    # 1〜2 行目は make_状態.py が 状態.md に載せる（今の版・全体）
    cur = len(ERAS) - 1
    for k, label in [(cur, f"今の版「{ERAS[cur][1]}」"), (None, "全体")]:
        r, l = (R, L) if k is None else (R[R["版"] == k], L[L["版"] == k])
        _, both, same_a, n = summary(r, l)
        frm = since if k is None else max(since, pd.Timestamp(ERAS[k][0], tz="UTC"))
        if frm > end:
            print(f"{label}: {frm:%m-%d %H} UTC〜　まだ比べられない（記録のデータの最後 − 1 時間が {end:%m-%d %H} UTC）"); continue
        ns, ss, _ = signal_match(r, hours, sig)
        tail = (f"・合図の一致 {ss}/{ns}（{ss / ns:.0%}）" if ns else "") + hi_text(signal_match_hi(r, hours, sig), star=k is not None)
        print(f"{label}: {frm:%m-%d %H}〜{end:%m-%d %H} UTC　記録 {len(r)} 件・執行 {len(l)} 件・同じ足で入った {len(both)} 件（{len(both) / max(n, 1):.1%}）・同じ行動 {same_a} 件{tail}")
    print(f"（比べるのは判断の足が記録のデータの最後 − 1 時間＝{end:%Y-%m-%d %H:%M} UTC まで）")
    for k, (t, name) in enumerate(ERAS):
        r, l = R[R["版"] == k], L[L["版"] == k]
        if not len(r) and not len(l):
            continue
        m, both, same_a, n = summary(r, l)
        only_r = m[m["_merge"] == "left_only"]; only_l = m[m["_merge"] == "right_only"]
        print(f"\n[{name}・{t} UTC〜] 記録 {len(r)}・執行 {len(l)}・同じ足 {len(both)}（{len(both) / max(n, 1):.1%}）・同じ行動 {same_a}")
        ns, ss, srr = signal_match(r, hours, sig)
        if ns:
            print(f"  合図の一致: 記録の入口 {ns} 件（bot のログがある足）のうち bot も同じ向きの合図 {ss} 件（{ss / ns:.1%}）・RR も同じ {srr} 件（{srr / ns:.1%}）")
            cnt = {}
            for x in only_r.itertuples():
                g = sig.get((x.sym, x.decision))
                k = "bot のログなし" if x.decision not in hours else "bot に合図なし" if g is None else "bot は逆向きの合図" if g[1] != x.side_記録 else "発注したが台帳に無い（拒否など）" if g[0] == "入る" else f"合図はあったが見送り（{g[3] or '理由なし'}）"
                cnt[k] = cnt.get(k, 0) + 1
            if cnt: print("  記録だけの内訳:", "・".join(f"{k} {v}" for k, v in sorted(cnt.items(), key=lambda kv: -kv[1])))
        elif not hours:
            print("  合図の一致: bot のログ（run_*.log）が見つからない")
        if len(only_r): print("  記録だけ:", ", ".join(f"{x.sym} {x.decision:%m-%d %H}" for x in only_r.itertuples()))
        if len(only_l): print("  執行だけ:", ", ".join(f"{x.sym} {x.decision:%m-%d %H}" for x in only_l.itertuples()))
        cl = both[(both["status_記録"] == "closed") & (both["status_執行"] == "closed")]
        if len(cl):
            sgn = cl["side_記録"].map({"買い": 1, "売り": -1})
            dE = sgn * (cl["entry_px_執行"] - cl["entry_px_記録"]) / cl["D"]          # 入口の不利（買いは高いほど不利）
            dX = -sgn * (cl["exit_px_執行"] - cl["exit_px_記録"]) / cl["D"]           # 出口の不利（買いは安いほど不利）
            same = cl["why_記録"] == cl["why_執行"]; dR = cl["R_執行"] - cl["R_記録"]
            print(f"  両方決済済み {len(cl)} 件: 理由一致 {same.mean():.1%}・R の差 平均 {dR.mean():+.3f}（中央 {dR.median():+.3f}）")
            if same.any():
                c = (dE + dX)[same]
                print(f"  理由が同じ {int(same.sum())} 件の実測コスト: 入口 {dE[same].mean():+.4f}R・出口 {dX[same].mean():+.4f}R・計 {c.mean():+.4f}R"
                      "（参考: SL/TP を約定値から置き直すので幅の差はここに出ない。規程 §4 ③ の量は Q751 の超過コスト E＝verification-lab/financial-engineering/s21-6m-gate-q751/judge_s21_6m.py）")
            bad = cl[~same]
            if len(bad): print("  理由が違う:", ", ".join(f"{x.sym} {x.decision:%m-%d %H} {x.why_記録}→{x.why_執行}" for x in bad.itertuples()))
    print(f"\n累計 R: 記録 {R[R['status'] == 'closed']['R'].sum():+.1f}・執行 {L[L['status'] == 'closed']['R'].sum():+.1f}（同じ期間・記録は保有コスト込み）")


if __name__ == "__main__":
    main()
