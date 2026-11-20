# -*- coding: utf-8 -*-
"""stamp_daily.py — 1 日 1 回、「事前登録・凍結・運用規程・記録の鎖の頭」のハッシュ一覧（manifest）を作り、OpenTimestamps で第三者の時刻を取る（2026-11-18 案）。
あわせて、前の日までの .ots のうちビットコインの印がまだ無いものに印を足す（upgrade）。

なぜ 1 枚の一覧か: 送るのは一覧のハッシュ 1 つで足り、一覧に載った全部のファイルが「その時刻に既にこの中身だった」と言える。
外の人に見せるときは「一覧（manifest_YYYYMMDD.txt）・その .ots・見せたいファイル」の 3 つを渡す →
  ① `shasum -a 256 ファイル` が一覧の行と同じ ② `ots verify manifest_YYYYMMDD.txt.ots`（公式）がビットコインのブロックの時刻を返す。
一覧はこの Mac にだけ置く（パスも中身も外へ出さない）。外へ出るのは一覧の sha256 に乱数を足してからのハッシュだけ。

使い方: python stamp_daily.py [--root 検証] [--out トレード/forward/証拠/第三者の時刻] [--dry]（--dry は一覧を作るだけで送らない）
終了コード: 0 済み（記録の回が動いていて見送った回も 0）・1 送れなかった（一覧は残す・次の回がまた送る）・2 一覧に載せるものが 0 本
2026-11-18 別の目の点検（Opus）を反映: 事前登録は 検証/ の下の全部（kaggle・学問・設計の下書きも）・依存の控え・凍結の json・S30 の確定の控えも載せる／
同じ日の 2 回目は、その日の最後の一覧と中身が同じなら送らない（別名を作った後も）／upgrade は 120 日以内の印の無い .ots 全部／
記録の回（run_forward.sh の鍵 トレード/forward/ログ/.lock）が動いていれば一覧を作らずに見送る（書き途中の鎖を載せない）。
"""
import argparse, datetime, glob, hashlib, os, re, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import ots_lite as O

# 検証/ からの相対の glob。事前登録は結果より前にあったことを示したいもの、凍結と規程と控えは「後から変えていない」を示したいもの
PATTERNS = [
    "**/*事前登録*.md",
    "トレード/運用規程*.md",
    "トレード/forward/*/凍結/*.json", "トレード/forward/*/凍結*/hashes.json",
    "トレード/forward/_依存の控え/*.json",
    "トレード/forward/S30/記録/確定_hashes.json",
    "トレード/forward/_写し/*/chain.csv",
    "lab-ops/trade/anchor/chain_heads.csv",
]
SKIP = re.compile(r"(^|/)(\.git|venv|\.venv|node_modules|__pycache__)(/|$)")


def manifest(root):
    rows, seen = [], set()
    for pat in PATTERNS:
        for p in sorted(glob.glob(os.path.join(root, pat), recursive=True)):
            rel = os.path.relpath(p, root)
            if os.path.isfile(p) and p not in seen and not SKIP.search(rel):
                seen.add(p); rows.append((hashlib.sha256(open(p, "rb").read()).hexdigest(), rel))
    return rows


def lock_busy(root):
    """記録の回（run_forward.sh）が動いているか（鍵のフォルダがあり、12 時間より新しい）。"""
    lk = os.path.join(root, "トレード", "forward", "ログ", ".lock")
    return os.path.isdir(lk) and time.time() - os.path.getmtime(lk) < 720 * 60


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.path.abspath(os.path.join(HERE, "..", "..", "..")))     # 置き場所 トレード/forward/証拠/ から見た 検証/
    ap.add_argument("--out", default=None); ap.add_argument("--dry", action="store_true"); ap.add_argument("--cal", nargs="*", default=None)
    a = ap.parse_args(); out = a.out or os.path.join(a.root, "トレード", "forward", "証拠", "第三者の時刻"); os.makedirs(out, exist_ok=True)
    now = datetime.datetime.now(); logp = os.path.join(out, "log.txt")
    def log(m):
        line = f"{now:%Y-%m-%d %H:%M} {m}"; print(line); open(logp, "a", encoding="utf-8").write(line + "\n")
    # 1 前の .ots にビットコインの印を足す（今日の分の前に。新しい保留は数時間はブロックに入らない）
    if not a.dry:
        cutoff = (now - datetime.timedelta(days=120)).strftime("%Y%m%d")
        for p in sorted(glob.glob(os.path.join(out, "manifest_*.txt.ots"))):
            if os.path.basename(p)[9:17] < cutoff: continue
            try:
                if O.needs_upgrade(p):
                    d, l = O.upgrade(p)
                    if d:
                        log(f"upgrade {os.path.basename(p)}: 印を足した {d}・印の無い保留 {l}")
                        for h, ok, t in O.verify(p):                               # 足した印を公開のブロック表と照らす（送るのはブロックの高さだけ）
                            log(f"  ブロック {h}: " + ("合う・" + t if ok else ("★ 合わない・" if ok is False else "") + t))
            except Exception as e:
                log(f"upgrade {os.path.basename(p)}: 失敗（{type(e).__name__}）")
    # 2 今日の一覧（記録の回が動いていれば見送る）
    if lock_busy(a.root):
        log("記録の回が動いている（トレード/forward/ログ/.lock）ので、今日の一覧は次の回に回す"); return
    rows = manifest(a.root)
    if not rows: log("★ 一覧に載せるものが 0 本"); sys.exit(2)
    body = "".join(f"{h}  {r}\n" for h, r in rows)
    todays = sorted(glob.glob(os.path.join(out, f"manifest_{now:%Y%m%d}*.txt")))
    if todays and os.path.exists(todays[-1] + ".ots") and open(todays[-1], encoding="utf-8").read().split("\n", 1)[1] == body:
        log(f"今日の一覧は送り済みで中身も同じ（{len(rows)} 本・{os.path.basename(todays[-1])}）"); return
    mp = os.path.join(out, f"manifest_{now:%Y%m%d}.txt")
    if os.path.exists(mp + ".ots"):                                                    # 同じ日に中身が変わった → 時刻つきの別名
        mp = os.path.join(out, f"manifest_{now:%Y%m%d_%H%M}.txt")
    open(mp, "w", encoding="utf-8").write(f"# 第三者の時刻の一覧（stamp_daily.py・{now:%Y-%m-%d %H:%M} JST・{len(rows)} 本・sha256 と 検証/ からのパス）\n" + body)
    if a.dry: log(f"一覧だけ作った（--dry）: {os.path.basename(mp)}・{len(rows)} 本"); return
    try:
        res = O.stamp([mp], a.cal or O.CALENDARS)
        log(f"送った: {os.path.basename(mp)}・{len(rows)} 本・受けたカレンダー {len(res[0][1])}")
    except Exception as e:
        log(f"★ 送れなかった（{e}）: 一覧は残した。次の回がまた送る"); sys.exit(1)


if __name__ == "__main__":
    main()
