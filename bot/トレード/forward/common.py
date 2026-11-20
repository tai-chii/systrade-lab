# -*- coding: utf-8 -*-
"""フォワード記録の共通設定（2026-10-26 凍結）。パスはこのファイルからの相対で決める。"""
import os, sys, hashlib, json
HERE = os.path.dirname(os.path.abspath(__file__))
KENSHO = os.path.abspath(os.path.join(HERE, "..", ".."))                # 検証/（2026-10-28 に 検証/フォワード → 検証/トレード/forward へ移動）
WS = os.path.abspath(os.path.join(KENSHO, ".."))                        # ワークスペース/
S21_CODE = os.path.join(KENSHO, "verification-lab", "financial-engineering", "s21-h1-ml-rr-weekcap-q515")
S23_CODE = os.path.join(KENSHO, "verification-lab", "financial-engineering", "s23-crypto-uptrend-long-q529")
S22_CODE = os.path.join(KENSHO, "verification-lab", "financial-engineering", "s22-crypto-ml-fintokei-q528")
FETCH_CODE = os.path.join(KENSHO, "_データ", "fetch")
DUKA_FETCH = os.path.join(KENSHO, "学問", "金融工学", "作業", "ML自動売買")
H1_HIST = os.path.join(WS, "作業層", "大容量", "market_data", "H1")          # 検証に使った 15 銘柄（〜2026-09）
FWD_DATA = os.path.join(WS, "作業層", "大容量", "market_data_forward")      # フォワード用（19 銘柄 H1・暗号資産）
for p in [S21_CODE, S23_CODE, S22_CODE, FETCH_CODE, DUKA_FETCH]:
    if p not in sys.path:
        sys.path.insert(0, p)

SYMS15 = ["EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "USDJPY", "USDCHF", "USDCAD", "EURJPY", "GBPJPY", "EURGBP",
          "XAUUSD", "US500", "USTECH", "GER40", "JPN225"]
NEW4 = ["AUDJPY", "CADJPY", "CHFJPY", "NZDJPY"]
SYMS19 = SYMS15 + NEW4
FORWARD_START = "2026-10-25 21:00:00+00:00"   # 凍結後の最初の週明け（日曜 21:00 UTC 以降の足から）


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def write_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1, default=str)


# 互換: 検証を回した環境では tz 付き時刻列の Series.to_numpy() が datetime64（UTC・tz なし）を返していた
# （K.labels・Z.labels_wk・since_reopen がその前提）。今の pandas は Timestamp の object 配列を返すので、そこだけ揃える。
# 一致は verify_env.py（Q534 E1 の 2024 年度を再現）で確かめる。
import pandas as _pd
_orig_to_numpy = _pd.Series.to_numpy


def _to_numpy(self, *a, **k):
    if not a and not k and isinstance(self.dtype, _pd.DatetimeTZDtype):
        return _orig_to_numpy(self.dt.tz_convert(None))
    return _orig_to_numpy(self, *a, **k)


_pd.Series.to_numpy = _to_numpy
