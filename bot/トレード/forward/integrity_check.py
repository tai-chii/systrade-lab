# -*- coding: utf-8 -*-
"""フォワード記録の改ざん・ずれを毎日見張る（提案・2026-11-05 夜間 P5・監査D の 3 と 9）。記録・凍結のファイルは読むだけ。
置き場所の案: トレード/forward/integrity_check.py。run_forward.sh の最後（make_状態.py の前）で 1 回呼ぶ。

1. 依存の照合（監査D の 3）: 記録が実行時に読む検証側のモジュールとデータのハッシュを、凍結時の控えと毎日比べる。
   - S21: 控え S21/凍結/deps_hashes.json（無ければ --snapshot S21 で作る。凍結より後に変わったファイルがあれば作らない）
   - S44・S53: 既存の控え S44/凍結/deps_hashes.json（judge_fx12m.py --snapshot で 2026-11-03 に作った）。今まで照合は 12 か月の判定の時だけだった
2. 記録の写しの鎖（監査D の 9）: 各戦略の取引の表を、毎日その日の写し（gzip）に残し、ハッシュを前の行のハッシュとつないだ鎖（chain.csv）に 1 行足す。
   前の写しと比べて、前回すでに確定していた取引（S21 は決済済みの行、S44/S53 は入った時刻が前回の「データの最後 − 余裕」より前の行）が変わった・消えた行を数える。
   記録は毎回すべて計算し直して上書きするので、データの差し替えで過去が変わったときの跡がここに残る。
出力: 1 戦略 1 行（★ は異常）。--out の integrity.json に結果。終了コード 0 異常なし・1 異常あり。
使い方: python integrity_check.py [--snap-dir DIR] [--out JSON] ／ python integrity_check.py --snapshot S21"""
import argparse, datetime, glob, gzip, hashlib, io, json, os, subprocess, sys
import pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
KS = HERE
while os.path.basename(KS) != "検証" and os.path.dirname(KS) != KS: KS = os.path.dirname(KS)     # 検証/（置き場所に依らず上へたどる）
FWD = os.path.join(KS, "トレード", "forward"); PY = sys.executable
sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()
# 戦略: 取引の表・状態・入った時刻の列・確定までの余裕（ラベルに要る足。S44/S53 は 120 本先の足が要るので 8 日）
BOTS = {"S21": dict(trades="S21/記録/trades_latest.csv", state="S21/記録/状態.json", entry="entry", margin_days=8, deps="S21/凍結/deps_hashes.json", freeze=datetime.datetime(2026, 10, 26, 0, 40),
                    probe="import sys, os; sys.path.insert(0, os.path.join(r'{F}', 'S21')); sys.path.insert(0, r'{F}'); import forward_s21"),
        "S44": dict(trades="S44/記録/trades.csv", state="S44/記録/状態.json", entry="entry", margin_days=8, deps="S44/凍結/deps_hashes.json"),
        "S53": dict(trades="S53/記録/trades.csv", state="S53/記録/状態.json", entry="entry", margin_days=8, deps="S44/凍結/deps_hashes.json"),
        # 2026-11-11 修正13（監査B の 3）: 日次・月次の表も写しと鎖に入れる。データ元を毎回取り直す表（S23・S34）は過去の行が変わりうるので、
        #   まず「数えて出すだけ」（star=False）で始め、数週間ぶんの跡を見てから ★ にするかを決める。S30 の確定の表は追記だけ（修正11）なので ★ にする
        "S23": dict(trades="S23/記録/daily.csv", entry="Unnamed: 0", kind="daily", star=False),
        "S34": dict(trades="S34/記録/daily.csv", entry="date", kind="daily", star=False),
        "S30日次": dict(trades="S30/記録/確定_daily.csv", entry="date", kind="daily", keep_last=True, star=True),
        "S30月次": dict(trades="S30/記録/確定_monthly.csv", entry="t", kind="daily", keep_last=True, star=True),
        # 2026-11-14 修正18（Q729）: S17b の観察枠の日次の表。追記だけで書くので S30 と同じく前の行が変われば ★（取得の依存は「取得」の控えで見る）
        "S17b": dict(trades="S17b/記録/daily.csv", entry="day", kind="daily", keep_last=True, star=True),
        # 2026-11-16（Q739・Q740）: S68 の週次の記録。判断の表・確定の表とも追記だけで書くので、前の行が変われば ★
        "S68判断": dict(trades="S68/記録/判断時_建玉.csv", entry="week", kind="daily", keep_last=True, star=True),
        "S68週次": dict(trades="S68/記録/確定_weeks.csv", entry="week", kind="daily", keep_last=True, star=True)}
# 2026-11-13 修正16（監査B の 5・判断待ち 19 の d）: 鎖を持たない依存の控え。S23・S30・S34 と、全部の FX が使う取得（fetch_forward.py）が
#   トレード/ の外で読むコード（run_q529.py・crypto_core.py・equities_free.py・composite_gate.py・fetch_dukascopy.py）。
#   S30・S34 の本体のスクリプト（q582・q598）は importlib で読むので sys.modules に載らないが、各自の 凍結/hashes.json で毎回照合している。
#   fetch_binance_basis.py は run_forward.sh がスクリプトとして直接呼ぶので probe に出ない → files で足す。freeze はその記録の始まり
_P = "import sys, os; sys.path.insert(0, os.path.join(r'{F}', '{D}')); sys.path.insert(0, r'{F}'); import {M}"
DEPS_ONLY = {"S23": dict(deps="_依存の控え/S23.json", freeze=datetime.datetime(2026, 10, 26, 0, 40), probe=_P.replace("{D}", "S23").replace("{M}", "forward_s23")),
             "S30": dict(deps="_依存の控え/S30.json", freeze=datetime.datetime(2026, 10, 31, 22, 36), probe=_P.replace("{D}", "S30").replace("{M}", "forward_s30"),
                         files=["verification-lab/financial-engineering/jp-us-ml-xsec-q582/kensho_ml_xsec_q582.py",       # 修正17: importlib で読むので
                                "verification-lab/financial-engineering/jp-us-high-volume-premium-q578/kensho_high_volume_premium_q578.py"]),  # 子プロセスの読み込みに映らない（点検 11-13 の 3）
             "S34": dict(deps="_依存の控え/S34.json", freeze=datetime.datetime(2026, 11, 1, 9, 20), probe=_P.replace("{D}", "S34").replace("{M}", "forward_s34"),
                         files=["_データ/fetch/fetch_binance_basis.py"]),
             "取得": dict(deps="_依存の控え/取得.json", freeze=datetime.datetime(2026, 10, 26, 0, 40), probe=_P.replace("{D}", ".").replace("{M}", "fetch_forward"))}
LEDGER = "S21/凍結/記録用コード_hashes.json"
ANCHOR_COLS = ["time", "bot", "rows", "link"]      # 修正16（監査B の 6）: 外の錨の 1 行＝その時点の鎖の行数と最後の link
SKIP_COLS = ("i",)            # 足の位置の番号。過去に足が 1 本増減すると、取引が同じでもその銘柄の全行で変わるので比べない（修正13・点検の指摘）
PROVISIONAL = "取得が途中"     # run_forward.sh が、データの取得が途中だった回に 記録_最新.md の末尾へ足す印（修正10）


def dep_files(bot):
    """記録の import を子プロセスで行い、verification-lab と _データ の下で読み込んだモジュールを返す（記録用コード自体は 記録用コード_hashes.json の役目）。"""
    b = DEPS_ONLY.get(bot) or BOTS[bot]                                         # 修正16: S23 は鎖（BOTS）と依存（DEPS_ONLY）の両方にあり、依存は DEPS_ONLY を読む
    code = b["probe"].format(F=FWD) + "\nimport json\nprint(json.dumps(sorted({os.path.abspath(m.__file__) for m in list(sys.modules.values()) if getattr(m, '__file__', None) and os.path.exists(m.__file__)})))"
    out = subprocess.run([PY, "-B", "-c", code], capture_output=True, text=True, timeout=300, cwd=FWD)
    if out.returncode != 0: raise RuntimeError(out.stderr[-300:])
    roots = [os.path.join(KS, "verification-lab"), os.path.join(KS, "_データ")] + ([os.path.join(KS, "学問")] if bot in DEPS_ONLY else [])   # 修正16: fetch_dukascopy.py は 学問/ の下
    fs = [f for f in json.loads(out.stdout.strip().splitlines()[-1]) if any(f.startswith(r) for r in roots)]
    return sorted(set(fs + [os.path.join(KS, x) for x in b.get("files", [])]))


def snapshot_deps(bot, path=None, redo=None):
    """依存の控えを作る。redo（理由の文）を渡すと作り直し（点検の指摘 2: 依存を正しく直した後）: 古い控えを _依存の控え/_旧/ へ退け、
    凍結より後の日付のファイルも受け入れて今の版で作り、帳簿の控えのハッシュと「依存の作り直し_<時刻>」の行を更新する（S23・S30・S34・取得だけ）。"""
    b = DEPS_ONLY.get(bot) or BOTS[bot]; fs = dep_files(bot)
    if redo:
        if bot not in DEPS_ONLY: print("作り直しは S23・S30・S34・取得 だけ（S21・S44・S53 の控えは凍結の一部）"); return 2
        p = os.path.join(FWD, b["deps"]); now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        if os.path.exists(p):
            od = os.path.join(os.path.dirname(p), "_旧"); os.makedirs(od, exist_ok=True); os.replace(p, os.path.join(od, f"{bot}_{now}.json"))
        json.dump({os.path.relpath(f, KS): sha(f) for f in fs}, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        lp = os.path.join(FWD, LEDGER); d = json.load(open(lp, encoding="utf-8")); k = os.path.relpath(p, KS)
        if k in d: d[k] = sha(p)
        d[f"依存の作り直し_{now}"] = f"{bot}: {redo}"; json.dump(d, open(lp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"作り直した {len(fs)} 本 → {p}（古い控えは _旧/・帳簿を更新）"); return 0
    late = [f for f in fs if datetime.datetime.fromtimestamp(os.path.getmtime(f)) > b["freeze"]]
    if late: print("凍結より後に変わった依存があるので控えを書かない:", *[os.path.relpath(f, KS) for f in late], sep="\n  "); return 2
    p = path or os.path.join(FWD, b["deps"])
    if os.path.exists(p): print(f"控えは既にある（上書きしない）: {p}"); return 2
    os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump({os.path.relpath(f, KS): sha(f) for f in fs}, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1); print(f"控え {len(fs)} 本 → {p}"); return 0


def check_deps(bot, table=None):
    b = (table or BOTS)[bot]
    if "deps" not in b: return 0, []                                            # 日次・月次の表（修正13）は依存の控えを持たない
    p = os.path.join(FWD, b["deps"])
    if not os.path.exists(p): return None, ["依存の控えが無い（--snapshot で作る）"]
    h = json.load(open(p, encoding="utf-8"))
    ok = approved_swaps()                                                       # 修正20: 凍結の控えは書き換えず、taichi が承認した差し替えだけを通す
    bad = [f"変わった: {k}" if os.path.exists(os.path.join(KS, k)) else f"無い: {k}" for k, v in h.items()
           if (not os.path.exists(os.path.join(KS, k)) or sha(os.path.join(KS, k)) != v)
           and not (os.path.exists(os.path.join(KS, k)) and any(s.get("旧") == v and s.get("新") == sha(os.path.join(KS, k)) for s in ok.get(k, [])))]
    return len(h), bad


APPROVED = "_依存の控え/承認済みの差し替え.json"


def approved_swaps():
    """修正20: 承認済みの依存の差し替え {道: [{"旧": 控えの sha, "新": 今の sha, "理由": ..., "承認": ...}, ...]}。
    控えが「旧」で今のファイルが「新」のときだけ一致とみなす（さらに後で変われば ★ に戻る）。このファイル自体は 記録用コード_hashes.json で守る。"""
    p = os.path.join(FWD, APPROVED)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}


def _changed(x, y):
    """2 つの列の、行ごとの「違う」。数として読める行は差 1e-9 超、そうでない行は文字列が違う（どちらも空なら同じ）。"""
    nx, ny = pd.to_numeric(x, errors="coerce"), pd.to_numeric(y, errors="coerce"); num = nx.notna() & ny.notna()
    d = pd.Series(False, index=x.index); d[num] = (nx[num] - ny[num]).abs() > 1e-9
    d[~num] = ~((x[~num].astype(str) == y[~num].astype(str)) | (x[~num].isna() & y[~num].isna()))
    return d


def diff_tables(old, new, b, last_end):
    """前回の写し old と今の表 new を比べる（修正13 で関数に出した・監査B の 2）。返り値 dict。
    確定済み: status の列があれば前回の決済済みの行（S21）、日次・月次の表なら前回の行（データ元を取り直す表は最後の 1 行を除く）、
              それ以外（S44/S53 は決済済みの行だけを書く）は前回のデータの最後 − 余裕より前に入った行。
    数えるもの: 確定済みで消えた・R が変わった（今までどおり）、R 以外の列が変わった・保有中で消えた・過去に増えた（修正13）。"""
    ent = b["entry"]; res = {}
    if not len(old) or ent not in old or ent not in new: return res
    daily = b.get("kind") == "daily"
    fixed = pd.Timestamp(last_end) - pd.Timedelta(days=b.get("margin_days", 0)) if isinstance(last_end, str) and last_end not in ("", "nan", "None") else None
    if daily: o = old if b.get("keep_last") else old.iloc[:-1]
    elif "status" in old: o = old[old["status"] == "closed"]
    elif fixed is not None: o = old[pd.to_datetime(old[ent], utc=True) < fixed]
    else: return res
    key = [c for c in ("sym", ent) if c in old]; m = o.merge(new, on=key, how="left", suffixes=("", "_新"), indicator=True)
    gone = int((m["_merge"] == "left_only").sum()); cols = [c for c in o.columns if c not in key and f"{c}_新" in m and c not in SKIP_COLS]
    both = m[m["_merge"] == "both"]
    chg = int(_changed(both["R"], both["R_新"]).sum()) if "R" in cols else 0
    oth = pd.Series(False, index=both.index)
    for c in cols:
        if c != "R": oth |= _changed(both[c], both[f"{c}_新"])
    res.update(確定済み=int(len(o)), 確定済みで消えた=gone, 確定済みでRが変わった=chg, 確定済みで他の列が変わった=int(oth.sum()))
    newkeys = set(map(tuple, new[key].astype(str).to_numpy())); oldkeys = set(map(tuple, old[key].astype(str).to_numpy()))
    if "status" in old and not daily:                                           # 保有中だった行が、決済済みにもならずに消えた
        op = old[old["status"] != "closed"]; res["保有中で消えた"] = int(sum(1 for k in map(tuple, op[key].astype(str).to_numpy()) if k not in newkeys))
    if not daily and fixed is not None:                                         # 前回すでに載っているはずの時刻に、新しい行が増えた（データの差し替えで過去の取引が増えた）
        # S21 は入った足が来れば載る。S44/S53 は 120 本先（5 営業日）がそろってから載る。週末と年末年始の休場をまたぐと暦では 8 日を超えうるので、余裕にさらに 4 日足す
        cut = pd.Timestamp(last_end) if "status" in old else fixed - pd.Timedelta(days=4)
        nn = new[[tuple(k) not in oldkeys for k in new[key].astype(str).to_numpy()]]
        res["過去に増えた"] = int((pd.to_datetime(nn[ent], utc=True) <= cut).sum()) if len(nn) else 0
    return res


def chain(bot, snap_dir, today, provisional=False):
    """その日の写しを残し、鎖に 1 行足し、前の写しから確定済みの行が変わったかを数える。
    provisional（取得が途中の回）は写しも鎖も残さず、比べない: 遅れた銘柄の取引が欠けた表が鎖に入ると、次の回でその取引が「過去に増えた」と数えられるため。"""
    b = BOTS[bot]; tp = os.path.join(FWD, b["trades"])
    if provisional: return dict(写し="暫定の回（データの取得が途中）なので、写しと鎖は残さず比べていない") if os.path.exists(tp) else dict(写し="★ 表が無い（記録の表のファイルが見つからない）")
    if not os.path.exists(tp): return dict(写し="★ 表が無い（記録の表のファイルが見つからない）")   # 修正13: 表が無いのは異常として出す
    raw = open(tp, "rb").read(); h = hashlib.sha256(raw).hexdigest()
    if b.get("kind") == "daily":
        try: end = str(pd.read_csv(io.BytesIO(raw))[b["entry"]].max())
        except Exception: end = None
    else:
        try: end = pd.Timestamp(json.load(open(os.path.join(FWD, b["state"]), encoding="utf-8"))["データの最後"])
        except Exception: end = None
    d = os.path.join(snap_dir, bot); os.makedirs(d, exist_ok=True); cp = os.path.join(d, "chain.csv")
    C = pd.read_csv(cp, dtype=str, keep_default_na=False) if os.path.exists(cp) else pd.DataFrame(columns=["date", "file_sha", "data_end", "prev", "link", "snap"])
    prev_link = C["link"].iloc[-1] if len(C) else "0" * 64
    res = dict(行=raw.count(b"\n") - 1 if raw else 0)
    if len(C):
        last = C.iloc[-1]
        if last["file_sha"] == h: res["前回から"] = "同じ"
        else:
            sp0 = os.path.join(d, last["snap"])
            if not os.path.exists(sp0): res["前回から"] = "★ 前回の写しが無い（比べられない）"                # 修正13: 写しが消えていたら異常として出す
            else:
                old = pd.read_csv(io.BytesIO(gzip.decompress(open(sp0, "rb").read()))); new = pd.read_csv(io.BytesIO(raw))
                res.update(diff_tables(old, new, b, last["data_end"]))
                res["前回から"] = "変わった（新しい行・保有中の更新は普通）"
    if end is None:                                                                # 修正17（点検 11-13 の 2）: "None" を鎖に入れると翌日から読めなくなる
        res["写し"] = "★ データの最後が読めない（状態.json か表）。今回は写しも鎖も残していない"
    elif not len(C) or C["date"].iloc[-1] != today or C["file_sha"].iloc[-1] != h:
        sn = f"{today}_{h[:12]}.csv.gz"; open(os.path.join(d, sn), "wb").write(gzip.compress(raw))
        link = hashlib.sha256((prev_link + h + today + str(end)).encode()).hexdigest()
        C = pd.concat([C, pd.DataFrame([dict(date=today, file_sha=h, data_end=str(end), prev=prev_link, link=link, snap=sn)])], ignore_index=True); C.to_csv(cp, index=False)
    # 鎖そのものの照合（誰かが途中の行や写しを書き換えていないか）
    pl = "0" * 64; broken = []
    for r in C.itertuples():
        if r.prev != pl or hashlib.sha256((r.prev + r.file_sha + r.date + r.data_end).encode()).hexdigest() != r.link: broken.append(r.date)
        sp = os.path.join(d, r.snap)
        if os.path.exists(sp):
            try: ok = hashlib.sha256(gzip.decompress(open(sp, "rb").read())).hexdigest() == r.file_sha
            except Exception: ok = False                                           # 修正17: 途中で切れた .gz で見張り全体を落とさない
            if not ok: broken.append(f"{r.date} の写し")
        else: broken.append(f"{r.date} の写しが無い")                              # 修正17（点検 A-6）: 鎖の途中の写しが消えても ★ にする（今の本物で欠けは 0）
        pl = r.link
    res["鎖"] = f"{len(C)} 行・切れ目なし" if not broken else "★ 切れている: " + ", ".join(broken)
    return res


def read_anchor(path):
    """錨のファイルを厳しく読む（点検の指摘 3）。返り値 (行のリスト, 崩れの文 or None)。行は dict(time, bot, rows:int, link)。
    見出しが ANCHOR_COLS と違う・列の数が 4 でない・rows が正の整数でない・link が 64 桁の 16 進でない、のどれかなら崩れ。"""
    import csv
    try: raw = open(path, encoding="utf-8").read()
    except Exception as e: return [], f"読めない（{e.__class__.__name__}）"
    lines = raw.splitlines()
    if not lines or lines[0].split(",") != ANCHOR_COLS: return [], "見出しが無い・違う"
    rows = []
    for k, r in enumerate(csv.reader(lines[1:]), start=2):
        if not r: continue
        if len(r) != 4 or not r[2].isdigit() or int(r[2]) < 1 or len(r[3]) != 64 or any(c not in "0123456789abcdef" for c in r[3]):
            return rows, f"{k} 行目が崩れている"
        rows.append(dict(time=r[0], bot=r[1], rows=int(r[2]), link=r[3]))
    return rows, None


def anchor(snap_dir, path, now, write=True, skip=()):
    """外の錨（修正16・監査B の 6）。鎖（chain.csv）は記録と同じ場所にあるので、消すと「初回」として通り、末尾を削っても残りは正しい鎖になる。
    そこで毎回、各戦略の鎖の行数と最後の link を、記録の外の追記だけのファイル path に 1 行残し、次の回からそれと照らす。
    ★ の条件: 錨のファイルが無い（入れるときに見出しだけで作るので、無いのは消えた印）・書式が崩れている／
              錨に載っている行数より鎖が短い（消した・削った）／錨の行数の位置の link が違う（作り直した）。
    足さない: write=False（暫定の回）・★ の戦略・skip（鎖そのものが ★ の戦略・点検の指摘）・錨のファイルが崩れているとき。
    返り値 ({戦略 or "ファイル": 文}, 足した行数)。"""
    if not os.path.exists(path): return {"ファイル": "★ 錨のファイルが無い（消えた？ 入れるときに見出しだけで作ってある）"}, 0
    A, broken = read_anchor(path)
    res = {} if not broken else {"ファイル": f"★ 錨のファイルの書式: {broken}（崩れた行より前だけで照らし、今回は足さない）"}
    add = []
    for bot in BOTS:
        cp = os.path.join(snap_dir, bot, "chain.csv")
        try: C = pd.read_csv(cp, dtype=str) if os.path.exists(cp) else pd.DataFrame(columns=["link"])
        except Exception: C = pd.DataFrame(columns=["link"])
        a = [r for r in A if r["bot"] == bot]; bad = None
        for r in a:
            n = r["rows"]
            if len(C) < n: bad = f"鎖が {len(C)} 行で、錨の {n} 行より短い"; break
            if C["link"].iloc[n - 1] != r["link"]: bad = f"{n} 行目の link が錨と違う（作り直された）"; break
        res[bot] = "★ " + bad if bad else (f"錨 {len(a)} 行と一致" if a else "錨はまだ無い（初回）")
        if write and not broken and not bad and bot not in skip and len(C) and (not a or (len(C), C["link"].iloc[-1]) != (a[-1]["rows"], a[-1]["link"])):
            add.append(dict(time=now, bot=bot, rows=str(len(C)), link=C["link"].iloc[-1]))
    if add:
        with open(path, "rb") as f:
            f.seek(0, 2); size = f.tell(); tail_nl = True
            if size: f.seek(size - 1); tail_nl = f.read(1) == b"\n"
        with open(path, "a", encoding="utf-8") as f:                              # 追記だけ（ファイル全体を書き直さない）
            if not tail_nl: f.write("\n")                                       # 前の行の末尾に改行が無いところへ足して 2 行がつながるのを防ぐ
            for r in add: f.write(",".join(r[c] for c in ANCHOR_COLS) + "\n")
    return res, len(add)


def check_ledger(path):
    """記録用コードの帳簿（記録用コード_hashes.json）のうち、ファイルの道になっている鍵を今のファイルと照合する（修正13・監査B の 5。今までは人の手だけ）。
    返り値 (照合した本数, 違う・無いファイルの文のリスト)。帳簿が無ければ (None, [...])。"""
    if not os.path.exists(path): return None, ["記録用コードの帳簿が無い"]
    d = json.load(open(path, encoding="utf-8")); n = 0; bad = []
    for k, v in d.items():
        if "/" not in k or not isinstance(v, str) or len(v) != 64: continue        # 「修正N」などの説明の行は飛ばす
        n += 1; f = os.path.join(KS, k)
        if not os.path.exists(f): bad.append(f"無い: {k}")
        elif sha(f) != v: bad.append(f"変わった: {k}")
    return n, bad


def main():
    global FWD
    ap = argparse.ArgumentParser(); ap.add_argument("--snapshot", choices=["S21"] + list(DEPS_ONLY))
    ap.add_argument("--anchor", default=None, help="外の錨のファイル（修正16。無指定なら錨は使わない）")
    ap.add_argument("--redo", default=None, help="--snapshot と一緒に: 依存の控えの作り直し（理由の文。依存を正しく直した後に人が打つ）"); ap.add_argument("--snap-dir", default=os.path.join(FWD, "_写し"))
    ap.add_argument("--out", default=None); ap.add_argument("--today", default=datetime.date.today().isoformat())
    ap.add_argument("--fwd", default=None, help="記録の根（試験用。既定は トレード/forward）"); ap.add_argument("--deps-path", default=None, help="--snapshot の書き先（試験用）")
    ap.add_argument("--ledger", default=None, help="記録用コードの帳簿（試験用。既定は S21/凍結/記録用コード_hashes.json）")
    ap.add_argument("--provisional", choices=["auto", "yes", "no"], default="auto", help="取得が途中の回か（既定は 記録_最新.md の印を読む）"); a = ap.parse_args()
    if a.fwd: FWD = a.fwd
    if a.snapshot: return snapshot_deps(a.snapshot, a.deps_path, a.redo)
    out = {}; bad = False
    try: prov = a.provisional == "yes" or (a.provisional == "auto" and PROVISIONAL in open(os.path.join(FWD, "記録_最新.md"), encoding="utf-8").read()[-600:])
    except Exception: prov = False
    if prov: print("暫定の回（データの取得が途中）: 写しと鎖は残さない。依存と帳簿の照合だけ行う")
    for bot in BOTS:
        try: n, dbad = check_deps(bot)
        except Exception as e: n, dbad = None, [f"依存を照らせなかった（{e.__class__.__name__}: {str(e)[:80]}）"]   # 修正17
        try: c = chain(bot, a.snap_dir, a.today, prov)
        except Exception as e: c = {"鎖": f"★ 写しと鎖を照らせなかった（{e.__class__.__name__}: {str(e)[:80]}）"}
        retro = c.get("確定済みで消えた", 0) + c.get("確定済みでRが変わった", 0)
        retro2 = c.get("確定済みで他の列が変わった", 0) + c.get("保有中で消えた", 0) + c.get("過去に増えた", 0)     # 修正13 で足した数え
        if not BOTS[bot].get("star", True): retro = retro2 = 0                                                    # 記述だけの表（S23・S34）は数えて出すが ★ にしない
        star = bool(dbad) or retro > 0 or retro2 > 0 or "★" in c.get("鎖", "") or "★" in str(c.get("写し", "")) or "★" in c.get("前回から", "")
        bad |= star; out[bot] = dict(依存=dict(本数=n, 異常=dbad), 写し=c, 異常=star)
        print(f"{'★ ' if star else ''}{bot}: 依存 {n if n is not None else '控えなし'} 本" + (f"（{'・'.join(dbad[:3])}）" if dbad else "・一致")
              + f"・表 {c.get('行', '?')} 行・{c.get('前回から', '初回')}" + (f"・確定済み {c['確定済み']} 行のうち消えた {c['確定済みで消えた']}・R が変わった {c['確定済みでRが変わった']}・他の列が変わった {c.get('確定済みで他の列が変わった', 0)}"
                 + (f"・保有中で消えた {c['保有中で消えた']}" if "保有中で消えた" in c else "") + (f"・過去に増えた {c['過去に増えた']}" if "過去に増えた" in c else "") if "確定済み" in c else "")
              + (f"・{c['写し']}" if "写し" in c else "")
              + f"・鎖 {c.get('鎖', '')}")
    for name in DEPS_ONLY:                                                      # 修正16: 鎖を持たない依存の控え
        try: n, dbad = check_deps(name, DEPS_ONLY)
        except Exception as e: n, dbad = None, [f"依存を照らせなかった（{e.__class__.__name__}: {str(e)[:80]}）"]   # 修正17
        bad |= bool(dbad); out[f"依存_{name}"] = dict(本数=n, 異常=dbad)
        print(f"{'★ ' if dbad else ''}依存 {name}: {n if n is not None else '控えなし'} 本" + (f"（{'・'.join(dbad[:3])}）" if dbad else "・一致"))
    if a.anchor:                                                                # 修正16: 外の錨
        try: ar, nadd = anchor(a.snap_dir, a.anchor, datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), write=not prov,
                               skip={b for b, v in out.items() if isinstance(v, dict) and "★" in str(v.get("写し", {}).get("鎖", ""))})
        except Exception as e: ar, nadd = {"ファイル": f"★ 錨を照らせなかった（{e.__class__.__name__}: {str(e)[:80]}）"}, 0   # 点検の指摘 3: 見張り全体を落とさない
        abad = {k: v for k, v in ar.items() if v.startswith("★")}; bad |= bool(abad); out["錨"] = ar
        print(f"{'★ ' if abad else ''}外の錨: " + ("・".join(f"{k} {v}" for k, v in abad.items()) if abad else f"{len(ar)} 本とも一致")
              + (f"（今回の鎖の先頭 {nadd} 本を足した）" if nadd else "（足したものなし）"))
    try: ln, lbad = check_ledger(a.ledger or os.path.join(FWD, LEDGER))
    except Exception as e: ln, lbad = None, [f"帳簿を照らせなかった（{e.__class__.__name__}: {str(e)[:80]}）"]   # 修正17               # 修正13: 記録用コードの帳簿の照合
    bad |= bool(lbad); out["記録用コード"] = dict(本数=ln, 異常=lbad)
    print(f"{'★ ' if lbad else ''}記録用コード: 帳簿 {ln if ln is not None else 'なし'} 本" + (f"（{'・'.join(lbad[:4])}）" if lbad else "・一致"))
    if a.out: json.dump(out, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
