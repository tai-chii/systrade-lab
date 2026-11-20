# -*- coding: utf-8 -*-
"""S34（暗号資産の四半期ベーシス・現物買い＋先物売り・Q598 B1 の形を凍結）の仮想フォワード記録（Q599・2026-11-01）。
- 凍結: kensho_crypto_carry_q598.py の sim_b1（閾値 5%・限月の規則・コスト・資本 1.5・想定元本 1/3）。ハッシュは 凍結/hashes.json
- 記録: 足の日 2026-07-01 以降（封印期間の直後）の日次。注文は出さない
- 合否: 12 か月で 日次 NW t ≥ 2（同時に走る本数で Holm）。同じ期間の USD 政策金利を年率で上回るかも並べて見る
- 停止: 直近 90 日の PF < 0.95 か、累積（単純和）の最大下落が −5.37%（Q598 の最悪 −3.58% × 1.5）を超えたら終了コード 3
- 同等性: 2024-07〜2026-06 の日次が Q599 の daily_q599.csv と一致しなければ終了コード 2
使い方: 作業層/大容量/venv_forward/bin/python forward_s34.py"""
import datetime, hashlib, importlib.util, json, os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
KENSHO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
Q598 = os.path.join(KENSHO, "verification-lab", "financial-engineering", "crypto-carry-q598")
_sp = importlib.util.spec_from_file_location("q598", os.path.join(Q598, "kensho_crypto_carry_q598.py"))
K = importlib.util.module_from_spec(_sp); _sp.loader.exec_module(K)

K.SEAL = pd.Timestamp("2100-01-01")  # 封印を開ける: フォワード専用（S34 の記録・事前登録_q599.md）。判定には使わない
FWD_FIRST = pd.Timestamp("2026-07-01"); EQUIV = (pd.Timestamp("2024-07-01"), pd.Timestamp("2026-07-01"))
STOP_DD, STOP_PF, PF_DAYS = -0.0537, 0.95, 90
FREEZE = os.path.join(HERE, "凍結"); REC = os.path.join(HERE, "記録")


def sha(p):
    h = hashlib.sha256(); h.update(open(p, "rb").read()); return h.hexdigest()


def main():
    os.makedirs(REC, exist_ok=True); os.makedirs(FREEZE, exist_ok=True)
    code, hp = sha(_sp.origin), os.path.join(FREEZE, "hashes.json")
    if os.path.exists(hp):
        if json.load(open(hp, encoding="utf-8"))["q598_script"] != code:
            print("★ 凍結したコードのハッシュが違う。変えるなら別 ID で凍結し直す"); return 2
    elif os.path.exists(os.path.join(REC, "状態.json")):
        # 2026-11-12 修正14（監査B の 4）: 記録が始まった後に凍結の控えが欠けたら、今のコードのハッシュで作り直さずに止める（作り直すと「固定した設定」が跡なく入れ替わる）
        print(f"★ 凍結の控え（{hp}）が無い。記録は始まっているので作り直さずに止めた。消えたなら控えから戻す"); return 5
    else:
        json.dump({"凍結日": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "q598_script": code, "出典": "事前登録_q598.md・事前登録_q599.md"},
                  open(hp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    today = pd.Timestamp(datetime.datetime.now(datetime.timezone.utc).date())
    frames = []
    for pair in ("BTCUSD", "ETHUSD"):
        d = K.load_basis(pair); d = d[d["date"] < today].reset_index(drop=True)     # 確定した足だけ
        frames.append(K.sim_b1(d)[0])
    idx = frames[0].index.intersection(frames[1].index); frames = [f.loc[idx] for f in frames]
    net = sum((f["gross"] - f["cost"]) for f in frames) * K.NOTIONAL
    q = pd.read_csv(os.path.join(Q598, "results", "daily_q599.csv"), index_col=0, parse_dates=True)["B1"]
    gap = float((net.reindex(q.index) - q).abs().max())
    if not gap < 1e-12:
        print(f"★ Q599 の日次と一致しない（最大差 {gap:.2e}）"); return 2
    k = idx >= FWD_FIRST
    pre = sum(f["gross"] for f in frames) * K.NOTIONAL
    fixed = sum((f["fixed"] - f["cost"]) for f in frames) * K.NOTIONAL
    out = pd.DataFrame({"コスト後": net[k], "コスト前": pre[k], "枚数固定": fixed[k], "BTC保有": frames[0]["pos"][k], "ETH保有": frames[1]["pos"][k]})
    out.round(8).to_csv(os.path.join(REC, "daily.csv"), index_label="date")
    p = out["コスト後"]; eq = p.cumsum(); dd = float((eq - eq.cummax()).min()) if len(p) else 0.0
    usd = pd.read_csv(K.RATE, parse_dates=["date"], index_col="date")["policy_rate_pct"]
    rf = float(usd.reindex(p.index, method="ffill").mean()) if len(p) else float("nan")
    tail = p.iloc[-PF_DAYS:]; loss = -tail[tail < 0].sum()
    pf = float(tail[tail > 0].sum() / loss) if loss > 0 else None
    stop = []
    if dd < STOP_DD:
        stop.append(f"最大下落 {dd * 100:.2f}%")
    if len(tail) >= PF_DAYS and pf is not None and pf < STOP_PF:
        stop.append(f"直近 {PF_DAYS} 日の PF {pf:.2f}")
    st = {"記録日数": int(len(p)), "通算": round(float(eq.iloc[-1] * 100), 3) if len(p) else 0.0, "最高値から": round(float((eq.iloc[-1] - eq.max()) * 100), 3) if len(p) else 0.0,
          "最大下落": round(dd * 100, 3), "年率": round(float(p.mean() * 36500), 2) if len(p) else None, "USD政策金利の平均": round(rf, 2),
          "NW_t": round(K.nw_t(p.to_numpy()), 2) if len(p) > 30 else None, "直近PF": round(pf, 2) if pf is not None else None,
          "保有": {"BTC": float(frames[0]["pos"].iloc[-1]), "ETH": float(frames[1]["pos"].iloc[-1])},
          "データの最後": str(idx.max().date()), "更新": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "停止": stop}
    json.dump(st, open(os.path.join(REC, "状態.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(st, ensure_ascii=False))
    return 3 if stop else 0


if __name__ == "__main__":
    sys.exit(main())
