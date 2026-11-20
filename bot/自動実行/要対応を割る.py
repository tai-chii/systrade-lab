#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""要対応を割る.py — 要対応.md の古い解決済みの節を、月ごとの置き場（要対応_過去/要対応_YYYY-MM.md）へ移す（2026-11-19・Fable・taichi「台帳の整理が先」）。

なぜ: 要対応.md は追記だけで 400KB を超え、人も Claude も全体を読めなくなった。読むのは未解決と直近だけなので、解決済みの古い節を別のファイルへ分ける。
      要対応.md の場所・名前・節の書式は変えない（記録用コードを含む多くの書き手が、この道に追記している）。

動かす節  : 状態が「解決…」（太字の「**解決…」も）か、状態行の無い節で、見出しの日付が（今日 − keep_days）より前のもの。
動かさない: ・未解決の節・日付の新しい節
            ・状態が「解決」で始まらない節（対処中・配備待ち・一部解決など。人が状態を直せば次の回に動く）
            ・見出しに PROTECT の語を含む節。重複よけを「題や道が 要対応.md のどこかにあるか」で決める書き手のため
              （seal_check.py は一度載せたファイルを足さない。make_状態.py の Q751 の節は 1 回だけ書く）
            ・残す節と見出しの日時が同じ節、日時の並びが乱れている日の節（つなぎ直したときに順番が変わるため。乱れの元が片づけば次の回に動く）
やらないこと: 節の中身を書き換えない。順番を変えない。

安全: 既定は表示だけ。--apply のときだけ書く。書く前に次を確かめ、1 つでも外れたら何も書かない。
      ① 読んだ文字列を節に分けてつなぎ直すと、元と 1 文字も違わない
      ② 残す節と動かす節を元の順に戻すと、元の節の並びと同じになる
      ③ 未解決の節の見出しの並びが、前と後で同じ
      ④ 毎朝のページ（make_要対応ページ.py の merge_youtaiou）から見た見出しの並びが、前と後で同じ
      ⑤ 書く直前に 要対応.md を読み直し、読んだ時から変わっていない（ほかの書き手との衝突よけ）
      書く順は 控え → 過去の置き場 → 要対応.md（途中で止まっても節は失われない。二重になるだけ）。
読む側: make_要対応ページ.py は 要対応_過去/ もあわせて読む（read_youtaiou_all）。ほかの読み手（make_状態.py・notify_star.py・weekly_digest.py）は未解決と新しい節しか使わない。

使い方: python3 要対応を割る.py [--keep-days 2] [--apply] [--file 要対応.md] [--out 要対応_過去]
戻し方: 要対応_過去/_控え/ の控え（要対応.md と、その回に変わった月のファイル）を書き戻す。控えの後に 要対応.md に足された節は手で写す。"""
import argparse, datetime, glob, importlib.util, os, re, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROTECT = ("seal_check", "Q751）")
NOT_DONE = ("解決待ち", "解決して", "解決でき", "解決は", "解決の見込み", "解決せず", "解決しない")   # 「解決」で始まるが、済んでいない書き方
POINTER_MARK = "要対応_過去/"
POINTER = "- 解決済みの古い節は `要対応_過去/要対応_YYYY-MM.md` にある（`要対応を割る.py` が月ごとに移す。未解決の節と直近の節はここに残る・2026-11-19）。"
ARCH_HEAD = "# 要対応の過去の節（{m}）\n\n`自動実行/要対応.md` から `要対応を割る.py` が移した、解決済みの節。見出しの日時の順。中身は書き換えていない。\n"


def split(text):
    """(前書き, [節])。join で元に戻る。前書きが無ければ None。"""
    blks = re.split(r"\n(?=## )", text)
    if blks and blks[0].startswith("## "):
        return None, blks
    return blks[0], blks[1:]


def join(head, secs):
    return "\n".join(([] if head is None else [head]) + secs)


def info(blk):
    title = blk.split("\n", 1)[0][3:].strip()
    m = re.search(r"^- 状態:\s*(.+)$", blk, re.M)
    d = re.match(r"(\d{4}-\d{2}-\d{2})", title)
    return title, (m.group(1).strip() if m else None), (d.group(1) if d else None)


def key(blk):
    m = re.match(r"## (\d{4}-\d{2}-\d{2})(?: (\d{2}:\d{2}))?", blk)
    return (m.group(1), m.group(2) or "") if m else ("", "")


def done(state):
    if state is None: return True                       # 状態行の無い節（make_状態.py も解決扱い）
    s = state.lstrip("*").lstrip()                      # 「**解決（…）**」のように太字で書かれた状態も解決に数える
    return s.startswith("解決") and not s.startswith(NOT_DONE)


def movable(blk, cutoff):
    title, state, date = info(blk)
    if date is None or date >= cutoff: return False
    if any(p in title for p in PROTECT): return False
    return done(state)


def open_titles(secs):
    return [info(b)[0] for b in secs if (info(b)[1] or "").startswith("未解決")]


def add_pointer(head):
    if head is None or POINTER_MARK in head: return head
    k = head.rfind("\n\n---")
    if k < 0: return head.rstrip("\n") + "\n" + POINTER + "\n"
    return head[:k] + "\n" + POINTER + head[k:]


def merge_by_key(a, b):
    """節の並び a・b を、それぞれの中の順は変えずに見出しの日時の早い方から取る（同じなら a が先）。"""
    out, i, j = [], 0, 0
    while i < len(a) or j < len(b):
        if j >= len(b) or (i < len(a) and key(a[i]) <= key(b[j])): out.append(a[i]); i += 1
        else: out.append(b[j]); j += 1
    return out


def arch_text(month, secs):
    return ARCH_HEAD.format(m=month).rstrip("\n") + "\n" + "".join("\n" + b.rstrip("\n") + "\n" for b in secs)


def page_merge():
    sp = importlib.util.spec_from_file_location("youtaiou_page", os.path.join(HERE, "make_要対応ページ.py"))
    m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m)
    return m.merge_youtaiou


def titles(text):
    return [b.split("\n", 1)[0] for b in re.split(r"\n(?=## )", text) if b.startswith("## ")]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep-days", type=int, default=2, help="今日を含めず、この日数ぶんは解決済みでも残す（既定 2＝今日・昨日・一昨日が残る）")
    ap.add_argument("--apply", action="store_true"); ap.add_argument("--file", default=os.path.join(HERE, "要対応.md"))
    ap.add_argument("--out", default=os.path.join(HERE, "要対応_過去")); ap.add_argument("--today", default=None, help="試験用（YYYY-MM-DD）")
    a = ap.parse_args(argv)
    today = datetime.date.fromisoformat(a.today) if a.today else datetime.date.today()
    cutoff = (today - datetime.timedelta(days=a.keep_days)).isoformat()
    orig = open(a.file, encoding="utf-8").read()
    head, secs = split(orig)
    if join(head, secs) != orig: print("① 分けてつなぎ直すと元と違う。やめる"); return 2
    flags = [movable(b, cutoff) for b in secs]
    kept_keys = {key(b) for b, f in zip(secs, flags) if not f}
    tie = [i for i, (b, f) in enumerate(zip(secs, flags)) if f and key(b) in kept_keys]
    for i in tie: flags[i] = False                      # 残す節と同じ日時の節は動かさない
    old_files = {os.path.basename(p)[4:11]: open(p, encoding="utf-8").read() for p in sorted(glob.glob(os.path.join(a.out, "要対応_????-??.md")))}
    try: mg = page_merge(); t0 = titles(mg(orig, [old_files[m] for m in sorted(old_files)])); mg_err = None
    except Exception as e: mg, t0, mg_err = None, None, f"確かめられない（{type(e).__name__}: {e}）"
    held = []                                           # 並びを保つために残した節（日付の一覧）
    while True:
        moved = [b for b, f in zip(secs, flags) if f]; kept = [b for b, f in zip(secs, flags) if not f]
        new_text = join(add_pointer(head), kept)
        if not new_text.endswith("\n"): new_text += "\n"
        by_month = {}
        for b in moved: by_month.setdefault(info(b)[2][:7], []).append(b)
        new_files = dict(old_files)
        for m, v in by_month.items():
            new_files[m] = arch_text(m, merge_by_key(split(old_files[m])[1] if m in old_files else [], v))
        if mg is None: page_ok, page_msg = False, mg_err; break
        t1 = titles(mg(new_text, [new_files[m] for m in sorted(new_files)]))
        if t0 == t1: page_ok, page_msg = True, f"{len(t1)} 節"; break
        if sorted(t0) != sorted(t1): page_ok, page_msg = False, "節の集合が変わる"; break
        bad = {(re.match(r"## (\d{4}-\d{2}-\d{2})", x) or [None, None])[1] for x, y in zip(t0, t1) if x != y} | {(re.match(r"## (\d{4}-\d{2}-\d{2})", y) or [None, None])[1] for x, y in zip(t0, t1) if x != y}
        idx = [i for i, f in enumerate(flags) if f and info(secs[i])[2] in bad]
        if not idx: page_ok, page_msg = False, "並びが変わるが、残して直せる節が無い"; break
        for i in idx: flags[i] = False                  # 日時の並びが乱れている日の節は、乱れの元（未解決の節など）が片づくまで動かさない
        held += sorted(bad - set(held))
    it_m, it_k = iter(moved), iter(kept)
    if [next(it_m) if f else next(it_k) for f in flags] != secs: print("② 元の並びに戻らない。やめる"); return 2
    if open_titles(kept) != open_titles(secs): print("③ 未解決の節の並びが変わる。やめる"); return 2
    kb = lambda bs: round(sum(len(x.encode("utf-8")) for x in bs) / 1024, 1)
    prot = [b for b in kept if info(b)[2] and info(b)[2] < cutoff and any(p in info(b)[0] for p in PROTECT)]
    odd = [b for b in kept if info(b)[2] and info(b)[2] < cutoff and info(b)[1] and not info(b)[1].startswith("未解決") and b not in prot and not done(info(b)[1])]
    print(f"今日 {today}・残す日付 {cutoff} 以降・節 {len(secs)}（{round(len(orig.encode('utf-8')) / 1024)} KB）")
    print(f"動かす {len(moved)} 節（{kb(moved)} KB）: " + "・".join(f"{m} に {len(v)} 節 {kb(v)} KB" for m, v in sorted(by_month.items())))
    print("  動かす節の状態の書き出し: " + "・".join(sorted({(info(b)[1] or "（状態行なし）").lstrip("*").lstrip()[:2] for b in moved})))
    print(f"残す   {len(kept)} 節（{round(len(new_text.encode('utf-8')) / 1024)} KB）: 未解決 {len(open_titles(kept))}・新しい {sum(1 for b in kept if (info(b)[2] or '9') >= cutoff)}・保護 {len(prot)}・状態が解決でない古い節 {len(odd)}・同じ日時で残した {len(tie)}")
    for b in odd: print(f"    状態「{info(b)[1][:22]}」 {info(b)[0][:60]}")
    if held: print(f"  並びを保つために、この日付の節は今回は動かさない: {'・'.join(held)}")
    print(f"④ 毎朝のページから見た並びが前と同じ: {'はい' if page_ok else 'いいえ'}（{page_msg}）")
    if not moved: print("動かす節が無い"); return 0
    if not page_ok: print("④ が外れた。何も書かずに終わる"); return 2
    if not a.apply:
        print("（表示だけ。書くには --apply）"); return 0
    if open(a.file, encoding="utf-8").read() != orig: print("⑤ 読んだ後に 要対応.md が変わった。何も書かずに終わる（もう一度回す）"); return 3
    stamp = f"{datetime.datetime.now():%Y%m%d_%H%M%S}"; bak_dir = os.path.join(a.out, "_控え", f"割る前_{stamp}"); n = 1
    while os.path.exists(bak_dir): n += 1; bak_dir = os.path.join(a.out, "_控え", f"割る前_{stamp}_{n}")   # 同じ秒の 2 回目が控えを上書きしない
    os.makedirs(bak_dir)
    shutil.copy2(a.file, os.path.join(bak_dir, "要対応.md"))
    for m in by_month:
        p = os.path.join(a.out, f"要対応_{m}.md")
        if os.path.exists(p): shutil.copy2(p, os.path.join(bak_dir, f"要対応_{m}.md"))
    for m in sorted(by_month):
        open(os.path.join(a.out, f"要対応_{m}.md"), "w", encoding="utf-8").write(new_files[m])
    if open(a.file, encoding="utf-8").read() != orig:
        for m in sorted(by_month):                      # 要対応.md が変わっていたら、過去の置き場を元に戻して終わる
            p = os.path.join(a.out, f"要対応_{m}.md"); b = os.path.join(bak_dir, f"要対応_{m}.md")
            shutil.copy2(b, p) if os.path.exists(b) else os.remove(p)
        print("⑤ 書いている間に 要対応.md が変わった。過去の置き場を元に戻し、何も変えずに終わる（もう一度回す）"); return 3
    open(a.file, "w", encoding="utf-8").write(new_text)
    print(f"書いた。控え: {bak_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
