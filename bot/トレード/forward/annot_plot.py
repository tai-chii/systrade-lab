# -*- coding: utf-8 -*-
"""annot_plot.py — 「変更（施策）× 損益（結果）」を 1 枚の図にする（2026-10-28）。
supermomonga 氏の MMbot ループ（Grafana アノテーション）の最小版。売買の計算には無関係・記録用コードではない。

読む元: S21/記録/trades_latest.csv（決済済みの累計 R）、S23/記録/daily.csv（資産 → 通算 %）、
        変更履歴.csv（人が書く行: 開始・規則・判断など）、S21/凍結/記録用コード_hashes.json の「修正N」（自動で拾う）
書く先: 図/変更×損益.svg（依存ライブラリなし・Obsidian／ブラウザで開く）、変更履歴.md（番号つきの一覧）
使い方: python3 annot_plot.py   （make_状態.py から毎回呼ばれる。手で回してもよい）
決まり: 記録用コード・規則・判断を変えたら 変更履歴.csv に 1 行足す（記録用コードの変更は hashes.json の 修正N に書けば自動で入る）"""
import csv, json, os, re, datetime as dt, html

D = os.path.dirname(os.path.abspath(__file__))
JST = dt.timezone(dt.timedelta(hours=9))
def p_utc(s):
    s = s.strip().replace("+00:00", "")
    return dt.datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=dt.timezone.utc).astimezone(JST)
def p_jst(s):
    s = s.strip()
    for f in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try: return dt.datetime.strptime(s, f).replace(tzinfo=JST)
        except ValueError: pass
    return None

# ---- 変更（アノテーション）
ann = []
fp = os.path.join(D, "変更履歴.csv")
if os.path.exists(fp):
    for r in csv.DictReader(open(fp, encoding="utf-8")):
        t = p_jst(r.get("日時JST", ""))
        if t: ann.append(dict(t=t, 対象=r.get("対象", ""), 種別=r.get("種別", ""), 内容=r.get("内容", ""), 出典=r.get("出典", "")))
hp = os.path.join(D, "S21", "凍結", "記録用コード_hashes.json")
if os.path.exists(hp):
    for k, v in json.load(open(hp, encoding="utf-8")).items():
        if not re.match(r"修正\d*$|記録$", k): continue
        m = re.match(r"(\d{4}-\d{2}-\d{2}) (\d{2}):(\d)[0-9x]", v)
        if not m: continue
        t = p_jst(f"{m.group(1)} {m.group(2)}:{m.group(3)}0")
        body = v[m.end():].strip(" ・")
        ann.append(dict(t=t, 対象="S21/記録用コード", 種別=k, 内容=body[:90] + ("…" if len(body) > 90 else ""), 出典="S21/凍結/記録用コード_hashes.json"))
ann.sort(key=lambda a: a["t"])
for i, a in enumerate(ann, 1): a["n"] = i

# ---- S21: 決済済みの累計 R（決済時刻順）＋含み
s21, s21_open = [], 0.0
tp = os.path.join(D, "S21", "記録", "trades_latest.csv")
if os.path.exists(tp):
    rows = list(csv.DictReader(open(tp, encoding="utf-8")))
    closed = sorted([r for r in rows if r.get("status") == "closed" and r.get("exit")], key=lambda r: r["exit"])
    s21_open = sum(float(r["R"] or 0) for r in rows if r.get("status") == "open")
    c = 0.0
    for r in closed:
        c += float(r["R"]); s21.append((p_utc(r["exit"]), c))
# ---- S23: 資産 → 通算 %
s23 = []
dp = os.path.join(D, "S23", "記録", "daily.csv")
if os.path.exists(dp):
    rows = [r for r in csv.DictReader(open(dp, encoding="utf-8")) if r.get("資産")]
    base = None
    for r in rows:
        day = r.get("") or r.get("日") or list(r.values())[0]
        t = p_jst(day[:10])
        if not t: continue
        v = float(r["資産"]); base = base if base is not None else v
        s23.append((t, (v / base - 1) * 100 if base else 0.0))

start = p_jst("2026-10-26 06:00")
now = dt.datetime.now(JST)
xs = [start, now] + [a["t"] for a in ann] + [t for t, _ in s21] + [t for t, _ in s23]
x0, x1 = min(xs), max(xs) + dt.timedelta(hours=6)

# ---- SVG
Wd, PL, PR = 1000, 70, 20; H1, H2, GAP, TOP, BOT = 250, 170, 40, 62, 40
Ht = TOP + H1 + GAP + H2 + BOT
def X(t): return PL + (t - x0).total_seconds() / max(1, (x1 - x0).total_seconds()) * (Wd - PL - PR)
def panel(y, h, series, label, unit, extra=None):
    out = []
    ys = [v for _, v in series] + [0.0] + ([extra] if extra is not None else [])
    lo, hi = min(ys), max(ys); pad = (hi - lo) * 0.15 or 1.0; lo -= pad; hi += pad
    def Y(v): return y + h - (v - lo) / (hi - lo) * h
    out.append(f'<rect x="{PL}" y="{y}" width="{Wd-PL-PR}" height="{h}" fill="#fafafa" stroke="#ddd"/>')
    out.append(f'<line x1="{PL}" x2="{Wd-PR}" y1="{Y(0):.1f}" y2="{Y(0):.1f}" stroke="#999" stroke-dasharray="3,3"/>')
    for v in (lo + pad, hi - pad):
        out.append(f'<text x="{PL-6}" y="{Y(v)+4:.1f}" font-size="11" text-anchor="end" fill="#555">{v:+.1f}{unit}</text>')
    out.append(f'<text x="{PL}" y="{y-8}" font-size="13" fill="#222" font-weight="bold">{html.escape(label)}</text>')
    if series:
        pts = [(X(start), Y(0.0))] + [(X(t), Y(v)) for t, v in series]
        out.append('<polyline fill="none" stroke="#1f77b4" stroke-width="2" points="' + " ".join(f"{a:.1f},{b:.1f}" for a, b in pts) + '"/>')
        tl, vl = series[-1]
        out.append(f'<circle cx="{X(tl):.1f}" cy="{Y(vl):.1f}" r="3.5" fill="#1f77b4"/>')
        out.append(f'<text x="{X(tl)+6:.1f}" y="{Y(vl)-6:.1f}" font-size="11" fill="#1f77b4">{vl:+.2f}{unit}</text>')
        if extra is not None:
            out.append(f'<line x1="{X(tl):.1f}" y1="{Y(vl):.1f}" x2="{X(now):.1f}" y2="{Y(extra):.1f}" stroke="#1f77b4" stroke-dasharray="4,3"/>')
            out.append(f'<text x="{X(now)-4:.1f}" y="{Y(extra)+14:.1f}" font-size="10" text-anchor="end" fill="#1f77b4">含み込み {extra:+.2f}{unit}</text>')
    else:
        out.append(f'<text x="{(PL+Wd-PR)/2}" y="{y+h/2}" font-size="12" text-anchor="middle" fill="#888">まだ記録がない</text>')
    for a in ann:
        if a["対象"].startswith("S21") and label.startswith("S23"): continue
        if a["対象"].startswith("S23") and label.startswith("S21"): continue
        col = {"開始": "#2ca02c", "規則": "#d62728", "判断": "#9467bd", "凍結": "#8c564b"}.get(a["種別"], "#ff7f0e")
        out.append(f'<line x1="{X(a["t"]):.1f}" x2="{X(a["t"]):.1f}" y1="{y}" y2="{y+h}" stroke="{col}" stroke-width="1" opacity="0.7"/>')
    return out
svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{Wd}" height="{Ht}" font-family="Hiragino Sans, Noto Sans CJK JP, sans-serif">',
       f'<rect width="{Wd}" height="{Ht}" fill="white"/>',
       f'<text x="{PL}" y="22" font-size="15" font-weight="bold" fill="#111">変更 × 損益（フォワード・生成 {now.strftime("%Y-%m-%d %H:%M")} JST）</text>',
       f'<text x="{PL}" y="38" font-size="11" fill="#666">縦線＝変更（番号は 変更履歴.md）。緑 開始・赤 規則・紫 判断・茶 凍結・橙 記録用コード。売買の計算には無関係</text>']
svg += panel(TOP, H1, s21, "S21 決済済みの累計 R（決済時刻・JST）", "R", extra=(s21[-1][1] + s21_open) if s21 else None)
svg += panel(TOP + H1 + GAP, H2, s23, "S23 通算 %（日次）", "%")
for i, a in enumerate(ann):  # 番号は上の枠の内側・近い線は上下に互い違い
    x = X(a["t"]); yy = TOP + 12 + (i % 2) * 12
    svg.append(f'<rect x="{x-7:.1f}" y="{yy-9}" width="14" height="11" rx="2" fill="white" stroke="#bbb" stroke-width="0.5"/>')
    svg.append(f'<text x="{x:.1f}" y="{yy}" font-size="9" text-anchor="middle" fill="#333">{a["n"]}</text>')
# x 軸の日付
d = x0.replace(hour=0, minute=0, second=0, microsecond=0)
while d <= x1:
    if x0 <= d <= x1:
        svg.append(f'<line x1="{X(d):.1f}" x2="{X(d):.1f}" y1="{Ht-BOT}" y2="{Ht-BOT+5}" stroke="#555"/>')
        svg.append(f'<text x="{X(d):.1f}" y="{Ht-BOT+18}" font-size="10" text-anchor="middle" fill="#333">{d.strftime("%m-%d")}</text>')
    d += dt.timedelta(days=1)
svg.append("</svg>")
open(os.path.join(D, "図", "変更×損益.svg"), "w", encoding="utf-8").write("\n".join(svg))

# ---- 一覧
L = [f"# 変更履歴（番号は 図/変更×損益.svg の縦線・生成 {now.strftime('%Y-%m-%d %H:%M')} JST）", "",
     "人が書く行は `変更履歴.csv`。記録用コードの変更は `S21/凍結/記録用コード_hashes.json` の 修正N から自動で拾う。", "",
     "| # | 日時 JST | 対象 | 種別 | 内容 | 出典 |", "|---|---|---|---|---|---|"]
for a in ann:
    L.append(f"| {a['n']} | {a['t'].strftime('%Y-%m-%d %H:%M')} | {a['対象']} | {a['種別']} | {a['内容'].replace('|', '／')} | `{a['出典']}` |")
L += ["", f"S21: 決済 {len(s21)} 件・累計 {s21[-1][1] if s21 else 0:+.2f}R・含み {s21_open:+.2f}R　／　S23: {len(s23)} 日" + (f"・通算 {s23[-1][1]:+.2f}%" if s23 else "")]
open(os.path.join(D, "変更履歴.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
print(f"変更 {len(ann)} 件・S21 {len(s21)} 件・S23 {len(s23)} 日 → 図/変更×損益.svg・変更履歴.md")
