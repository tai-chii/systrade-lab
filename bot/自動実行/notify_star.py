# -*- coding: utf-8 -*-
"""notify_star.py — 要対応.md に新しく足された節のうち、人が見るべきもの（★ で未解決・または自動で書かれた節）を Mac の通知に出す（2026-11-05・提案）。
なぜ: winnote の S21 bot が止まっても、Mac が ★ を書くのは make_状態.py が動くとき（1 日 1 回の記録の後）だけで、書いても要対応.md を開くまで誰も気づかない。
     heartbeat は lab-ops の pc_runner（5 分ごと）の git pull で届いているので、毎時 make_状態.py → このスクリプト、と回せば 1 時間以内に気づける（bot_watch.sh）。
やること: 節の見出しを前回までに見たもの（.notify_seen.json）と比べ、新しい節だけ通知する（1 回 3 件まで・残りは件数で 1 件にまとめる）。
     初回は今ある節をすべて「見た」にして何も通知しない（過去の ★ で溢れさせない）。通知は osascript（macOS の通知センター）。
使い方: python3 notify_star.py [--dry]（通知せずに表示）[--file 要対応.md] [--seen .notify_seen.json]"""
import argparse, hashlib, json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))


def sections(text):
    """[(見出し, 状態)]。状態行の無い古い節は状態 None。"""
    out = []
    for blk in re.split(r"\n(?=## )", text):
        if not blk.startswith("## "): continue
        title = blk.splitlines()[0][3:].strip(); m = re.search(r"^- 状態:\s*(.+)$", blk, re.M)
        out.append((title, m.group(1).strip() if m else None))
    return out


def wanted(title, state):
    """通知するか: ★ で未解決／自動で書かれた節（配備の待ち・記録の見張り・bot の停止など。解決でも知らせる）"""
    return ("★" in title and (state or "").startswith("未解決")) or "（自動" in title


def key(title):
    return hashlib.sha1(title.encode("utf-8")).hexdigest()[:16]


def notify(title, body):
    esc = lambda s: s.replace("\\", "\\\\").replace('"', '\\"')
    subprocess.run(["osascript", "-e", f'display notification "{esc(body)[:220]}" with title "{esc(title)[:60]}" sound name "Glass"'], capture_output=True, timeout=20)


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--dry", action="store_true")
    ap.add_argument("--file", default=os.path.join(HERE, "要対応.md")); ap.add_argument("--seen", default=os.path.join(HERE, ".notify_seen.json"))
    a = ap.parse_args(argv)
    secs = sections(open(a.file, encoding="utf-8").read())
    first = not os.path.exists(a.seen)
    seen = set() if first else set(json.load(open(a.seen, encoding="utf-8")))
    new = [(t, s) for t, s in secs if key(t) not in seen and wanted(t, s)]
    sent = []
    if not first:
        for t, s in new[:3]:
            body = re.sub(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2} — ", "", t).replace("★ ", "")
            sent.append(body)
            if not a.dry: notify("検証: 要対応" + ("（★）" if "★" in t else ""), body)
        if len(new) > 3:
            sent.append(f"ほか {len(new) - 3} 件"); a.dry or notify("検証: 要対応", f"ほか {len(new) - 3} 件（要対応.md）")
    json.dump(sorted(seen | {key(t) for t, _ in secs}), open(a.seen, "w", encoding="utf-8"))
    print(("初回: " if first else "") + f"節 {len(secs)}・新しく知らせるもの {len(new)}・通知 {len(sent)}" + ("（dry）" if a.dry else ""))
    for b in sent: print("  ", b)
    return 0


if __name__ == "__main__":
    sys.exit(main())
