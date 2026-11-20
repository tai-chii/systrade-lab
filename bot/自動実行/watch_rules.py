# -*- coding: utf-8 -*-
"""watch_rules.py — make_状態.py の「執行（winnote の S21）」の見張りで使う判定（2026-11-11・監査C の 1・2・3・7 の直し）。
ファイルも時計も読まない関数だけを置く（試験しやすくするため）。呼ぶのは make_状態.py。

直すもの:
  1 既知の形の拒否（指数の日々の休みの Market closed・Q682）で節が開いたままになり、その間に bot が本当に止まっても新しい節も通知も出なかった
  2 「ループは回っているが売買できていない」（★ 判断できない・エラーの繰り返し・全銘柄の足が取れない）をどの見張りも見ていなかった
  3 二重起動（heartbeat の bot.n が 2 以上）を毎時の見張りが見ていなかった
  7 拒否の ★ が、直っても最後の 1 件から 48 時間残っていた

「今」には、ログ・状態.json と同じ写し（手元の作業ツリー）の heartbeat の sent_at を渡す。Mac の時計や origin の新しい heartbeat を渡すと、
pull だけ止まったときに古い写しを新しい時刻で見て誤報になる（2026-11-11 点検の指摘）。
"""
import datetime as dt
import re

TS = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (.*)$")
ORDER = re.compile(r"^(?:\[dry\] )?(入る|閉じる) (\S+) ")
SETTLED = re.compile(r"^決済 (\S+) ")  # 2026-11-16: bot が建玉の消えたのを見つけた行（業者側の損切り・利確、または bot の決済）
MC = "Market closed"


def _t(s):
    try:
        return dt.datetime.strptime(s, "%Y-%m-%d %H:%M:%S").replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return None


def parse(lines):
    """ログの行 → [(時刻 UTC, 本文)]。時刻で始まらない行（トレースバックの続き）は前の行の時刻を引き継ぐ。時刻が壊れた行は続きの行として扱う。"""
    out = []; last = None
    for ln in lines:
        m = TS.match(ln); t = _t(m.group(1)) if m else None
        if t is not None:
            last = t; out.append((last, m.group(2)))
        elif last is not None and ln.strip():
            out.append((last, ln))
    return out


def reject_report(lines, now, window_h=48, closed_grace_h=3, other_h=24):
    """注文の拒否（'ok': False・dry でない）の扱い。返り値 (★ にする文のリスト, 知らせるだけの文のリスト)。
    - 理由が Market closed（その銘柄の市場が閉まっている）の拒否: その後にどの銘柄でも実際の注文が通っていれば ★ にしない（指数の日々の休み・Q682 の形）。
      通っていなくても closed_grace_h 時間は様子を見る（次の足で通ることが多い）。それを過ぎても 1 件も通っていなければ ★。
    - ほかの理由（AutoTrading 無効・証拠金・ストップの距離など）の拒否: すぐ ★。その銘柄の注文が次に通るか、other_h 時間たつまで ★ のまま。"""
    ev = []; P = parse(lines)
    for i, (t, body) in enumerate(P):
        m = ORDER.match(body)
        if not m or "'dry': False" not in body or t > now or (now - t).total_seconds() >= window_h * 3600:
            continue
        if "'ok': False" in body:
            why = re.search(r"'msg': '([^']+)'", body)
            ev.append((t, m.group(2), False, why.group(1) if why else "?", m.group(1), i))
        elif "'ok': True" in body:
            ev.append((t, m.group(2), True, "", m.group(1), i))
    rej = [e for e in ev if not e[2]]
    if not rej:
        return [], []
    # 2026-11-16（昼の自走）: 閉じる注文が Market closed で拒否された後、その銘柄の建玉が別の形で閉じていれば（「決済 X …」の行）、
    # その拒否はもう効かない（閉じる相手が無い）。11-14〜15 に週越しの USTECH を 46 回閉じに行って拒否され、11-15 23:55 UTC に
    # 業者側の損切りで閉じた後も、合図 0 が続いて「注文が通る」が来ず ★ が残った（誤報）。入る注文の拒否は今までどおり。
    # 前後は時刻でなく行の順で比べる（bot は 1 回の中で「決済の取り込み」→「閉じる」の順に書くので、同じ秒の「決済 X」→「閉じる X の拒否」は
    # 決済の後にまだ残っている建玉の拒否＝解除しない。別の目の点検 2026-11-16 の指摘）
    settled = [(i, m.group(1)) for i, (t, body) in enumerate(P) if (m := SETTLED.match(body)) and t <= now]
    moot = {e for e in rej if e[3] == MC and e[4] == "閉じる" and any(s[1] == e[1] and s[0] > e[5] for s in settled)}
    oks = [e for e in ev if e[2]]
    last_ok = max((e[0] for e in oks), default=None)
    probs, infos = [], []
    other = [e for e in rej if e[3] != MC and (now - e[0]).total_seconds() < other_h * 3600 and not any(o[1] == e[1] and o[0] > e[0] for o in oks)]
    if other:
        syms = "・".join(sorted({e[1] for e in other}))
        probs.append(f"注文が業者に拒否されている（{len(other)} 件・{syms}・理由 {other[-1][3]}）。AutoTrading 無効なら MT5 のアルゴリズム取引ボタンを緑に")
    mc = [e for e in rej if e[3] == MC]
    # 2026-11-16（昼の自走・別の目の点検の「元からある穴」）: 閉じる注文の拒否は、ほかの銘柄の注文が通っても解除しない
    # （週末前決済が拒否され、その後にほかの銘柄が通ると ★ が消えて、週末を越す建玉が黙って残った）。
    # 解除するのは、その銘柄の建玉が閉じた（moot）か、その銘柄の閉じる注文が後で通ったときだけ。入る注文の拒否は今までどおり Q682 の形。
    def _cleared(e):
        if e[4] == "閉じる":
            return any(o[1] == e[1] and o[4] == "閉じる" and o[5] > e[5] for o in oks)
        return any(o[5] > e[5] for o in oks)                               # 行の順で後に、どれかの注文が通った（Q682 の形）
    stuck = [e for e in mc if not _cleared(e) and e not in moot]
    by_close = [e for e in mc if e[4] == "閉じる" and e not in moot and e not in stuck]   # 同じ銘柄の閉じる注文が後で通った
    if stuck:
        syms = "・".join(sorted({e[1] for e in stuck}))
        if any((now - e[0]).total_seconds() >= closed_grace_h * 3600 for e in stuck):
            cl = sorted({e[1] for e in stuck if e[4] == "閉じる"})
            if cl:
                probs.append(f"{MC} で閉じられないまま {closed_grace_h} 時間を過ぎた建玉がある（{len(stuck)} 件・{syms}・閉じる注文 {'・'.join(cl)}）。週末を越した恐れ。MT5 で建玉と取引時間を確かめる")
            else:
                probs.append(f"{MC} の拒否の後、{closed_grace_h} 時間たっても 1 件も通っていない（{len(stuck)} 件・{syms}）。MT5 の取引時間と AutoTrading を確かめる")
        else:
            infos.append(f"{MC} の拒否 {len(stuck)} 件（{syms}）は {closed_grace_h} 時間は様子見（その間に注文が通れば消える・通らなければ ★ にする）")
    if moot and not probs and not infos:
        syms = "・".join(sorted({e[1] for e in moot}))
        infos.append(f"閉じる注文の拒否 {len(moot)} 件（{syms}・理由 {MC}）は、その後に建玉が閉じたので ★ にしない（週末前決済が通らなかったかは 昼_20261113/週末前決済の確かめ.py を手で回して見る）")
    if by_close and not probs and not infos:
        syms = "・".join(sorted({e[1] for e in by_close}))
        infos.append(f"閉じる注文の拒否 {len(by_close)} 件（{syms}・理由 {MC}）は、その後に同じ銘柄の閉じる注文が通ったので ★ にしない")
    cleared = [e for e in mc if e not in stuck and e not in moot and e not in by_close]
    if cleared and not probs and not infos:
        syms = "・".join(sorted({e[1] for e in cleared}))
        infos.append(f"注文の拒否 {len(cleared)} 件（{syms}・理由 {MC}）は、その後に注文が通っているので ★ にしない（休場などその銘柄だけの拒否・Q682 の形）")
    return probs, infos


def log_anomalies(lines, now, window_h=3):
    """直近 window_h 時間のログから「回っているが売買できていない」印を拾う。返り値は ★ にする文のリスト。
    エラーと「再接続できない」は、その後に「済 判断」が出ていれば数えない（繋ぎ直して回復した）。"""
    rows = [(t, b) for t, b in parse(lines) if 0 <= (now - t).total_seconds() < window_h * 3600]
    probs = []
    cant = [b for _, b in rows if b.startswith("★ 判断できない")]
    if cant:
        probs.append(f"bot が判断できていない（直近 {window_h} 時間で {len(cant)} 回: {cant[-1][:60]}）。MT5 が落ちている・年度のモデルが無い、のどちらか")
    done = max((t for t, b in rows if b.startswith("済 判断")), default=None)
    live = [(t, b) for t, b in rows if done is None or t > done]
    n_err = sum(1 for _, b in live if b.startswith("エラー:"))
    if n_err:
        probs.append(f"bot のログにエラーが出たまま、その後の判断が終わっていない（{n_err} 回）。ログの末尾のトレースバックを読む")
    n_re = sum(1 for _, b in live if b.startswith("再接続できない"))
    if n_re:
        probs.append(f"bot が MT5 に再接続できていない（{n_re} 回）。MT5 を起動して口座にログインする")
    by_t = {}
    for t, b in rows:
        if b.endswith(": 足が取れない"):
            by_t.setdefault(t.replace(minute=0, second=0), set()).add(b.split(":")[0])
    many = [k for k, v in by_t.items() if len(v) >= 10]
    if many and not cant and not n_err:
        probs.append(f"ほぼ全銘柄の足が取れない回がある（直近 {window_h} 時間で {len(many)} 回）。MT5 との接続を確かめる")
    return probs


def double_boot(bot):
    """heartbeat の bot.n（コマンドラインに execute_mt5.py を含む python の数）が 2 以上なら ★ の文、問題なければ None。
    手で --once を打っている間・別の業者の bot を試している間も 2 になる。"""
    n = (bot or {}).get("n")
    if isinstance(n, int) and n > 1:
        return f"execute_mt5.py が {n} 個動いている（二重起動なら同じ銘柄に 2 本入り、台帳の行が消える恐れ。手の --once や試験でなければ 1 個だけ残して閉じる）"
    return None


def state_stale(state_updated, sent_at, lines=(), max_h=2.5):
    """状態.json の「更新」（毎時の判断の終わりに書く）が、同じ写しの heartbeat を送った時点で max_h 時間より古ければ ★ の文。
    どちらかが無い・更新の後に bot が起動し直している（ログに「接続:」・再起動の直後は次の判断まで更新されない）なら None。"""
    if state_updated is None or sent_at is None:
        return None
    h = (sent_at - state_updated).total_seconds() / 3600
    if h <= max_h:
        return None
    if any(b.startswith("接続:") and t > state_updated for t, b in parse(lines)):
        return None
    return f"状態.json が送信の時点で {h:.1f} 時間更新されていない（毎時の判断が最後まで終わっていない恐れ）"


# 種類: 節が開いている間に「別の種類の異常」が出たかを比べるためのまとめ方。止まった系（届かない・bot が落ちた・ログが止まった・状態が古い）は
# 1 回の停止で時間をおいて順に出るので 1 種類にまとめる（節が 2〜3 個に分かれないように）
KINDS = [("停止", r"届いていない|受け取れていない|heartbeat を読めない|動いていない|落ちた|ログが .*止まっていた|状態\.json が"), ("dry", r"dry"),
         ("拒否", r"拒否"), ("売買できていない", r"判断できていない|足が取れない|ログにエラー|再接続できていない"), ("二重起動", r"個動いている"),
         ("ファイル", r"ファイル|正本|spr_ref|スプレッド")]


def kinds(texts):
    """文のリスト → 異常の種類の集合。"""
    out = set()
    for x in texts:
        out.add(next((name for name, pat in KINDS if re.search(pat, x)), "その他"))
    return out


def open_node_kinds(ytxt, auto_title):
    """要対応.md の中の、未解決の自動の節（見出しに auto_title・状態が未解決）に、make_状態.py が書いた異常の種類。節が無ければ None。
    読むのは「- 状態:」の次の行から「- 見ること」の行の手前まで（その後ろの手書きの追記・見立ては種類に数えない）。"""
    found = None
    for blk in re.split(r"\n(?=## )", ytxt):
        if not (blk.startswith("## ") and auto_title in blk.splitlines()[0] and re.search(r"^- 状態: 未解決", blk, re.M)):
            continue
        body = []
        for ln in blk.splitlines()[2:]:
            if ln.startswith("- 見ること"):
                break
            if ln.startswith("- ") and not ln.startswith("- 前の未解決の節"):
                body.append(ln[2:])
        found = (found or set()) | kinds(body)
    return found


def need_new_node(ytxt, probs, auto_title):
    """異常があるとき、要対応.md に新しい節を足すか。返り値 (足すか, 前の未解決の節に無い種類の集合)。
    未解決の自動の節が無ければ足す。あれば、そこに書かれていない種類の異常が出たときだけ足す（1 回の停止に 1 節・別の異常には別の節）。"""
    if not probs:
        return False, set()
    old = open_node_kinds(ytxt, auto_title)
    if old is None:
        return True, set()
    new = kinds(probs) - old
    return bool(new), new


def ledger_mismatch(n_open_rows, n_held):
    """2026-11-18 判断待ち 52: 台帳（trades.csv）の開いた行の数と、bot の状態.json の保有中の数（magic の建玉）が合わなければ ★ の文。
    どちらも bot が同じ回の終わりに書くので、普段は一致する（11-18 時点 5 と 5）。合わない形: 発注の返事が失敗・無しでも約定した建玉が台帳に無い／
    PLACED などで約定しなかった行が開いたまま／手で bot の magic の建玉を触った。数が読めなければ None。"""
    if n_open_rows is None or n_held is None:
        return None
    if int(n_open_rows) == int(n_held):
        return None
    return (f"台帳の開いた行 {int(n_open_rows)} と bot の保有中 {int(n_held)} が合わない（返事が失敗でも約定した建玉が台帳に無い・約定しなかった行が開いたまま・手で触った のどれか。"
            "lab-ops の trades.csv と MT5 の建玉を見比べる）")
