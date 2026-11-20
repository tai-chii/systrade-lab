# -*- coding: utf-8 -*-
"""ots_lite.py — フォワード記録の「第三者の時刻」（OpenTimestamps）を標準ライブラリだけで取る（2026-11-18 案・入れていない）。

なぜ: 記録には戦略ごとのハッシュの鎖（chain.csv）と lab-ops への錨（trade/anchor/chain_heads.csv）があるが、lab-ops のコミット時刻は
自分で付けた時刻なので、外の人に「この記録はこの日に既にあった」と示す力が弱い。OpenTimestamps は、ファイルのハッシュだけを公開の
カレンダー（複数）に送り、数時間後にビットコインのブロックに束ねてもらう仕組み。後から誰でも公式の `ots verify` で確かめられる。
送るのは 32 バイトのハッシュ（＋ランダムの nonce を足してからのハッシュ）だけで、記録の中身・口座・名前は送らない。

使い方:
  python ots_lite.py stamp  FILE [FILE...] [--cal URL ...]    # FILE.ots を作る（カレンダーの「保留」の印つき）
  python ots_lite.py upgrade FILE.ots [...]                    # 保留にビットコインの印を足す（数時間〜1 日後。済みのものは何もしない）
  python ots_lite.py info FILE.ots                             # 木を表示（保留の URI・ビットコインのブロックの高さ）
  python ots_lite.py check FILE FILE.ots                       # FILE のハッシュが .ots の元と同じか
  python ots_lite.py verify FILE.ots                           # ビットコインの印を公開のブロック表（blockstream.info・mempool.space）と照らし、ブロックの時刻を出す（送るのはブロックの高さだけ）
形式は公式の opentimestamps-client と同じ（.ots の先頭の印・版 1・sha256・append/prepend/sha256 の命令・保留 83dfe30d2ef90c8e・ビットコイン 0588960d73d71901）。

2026-11-18 別の目の点検（Opus）を反映: 命令の結果と引数は 4,096 バイトまで（hexlify を重ねた応答でメモリを食い尽くさない）／upgrade は保留 1 つごとに
失敗を受け流す（壊れた応答 1 つでファイル全体が止まらない）／問い合わせ先は既知のカレンダーの https だけ・転送はたどらない／保留は消さずに残し、
ビットコインの印を足す（偽の印を掴まされても、後から公式の道具で upgrade し直せる）／同じ命令の枝は束ねる（公式が読むと片方を落とす形を作らない）。
"""
import argparse, hashlib, io, os, re, secrets, sys, urllib.parse, urllib.request

MAGIC = b"\x00OpenTimestamps\x00\x00Proof\x00\xbf\x89\xe2\xe8\x84\xe8\x92\x94"
CALENDARS = ["https://a.pool.opentimestamps.org", "https://b.pool.opentimestamps.org", "https://a.pool.eternitywall.com"]
ALLOWED_HOST_SUFFIX = (".calendar.opentimestamps.org", ".pool.opentimestamps.org", ".calendar.eternitywall.com", ".pool.eternitywall.com", ".calendar.catallaxy.com")
PENDING = bytes.fromhex("83dfe30d2ef90c8e"); BITCOIN = bytes.fromhex("0588960d73d71901")
OPS = {0xf0: "append", 0xf1: "prepend", 0x08: "sha256", 0x02: "sha1", 0x03: "ripemd160", 0xf2: "reverse", 0xf3: "hexlify"}
MAX_MSG = 4096                                                                   # 命令の結果・append/prepend の引数の上限（点検 1）
UA = {"User-Agent": "ots-lite/1", "Accept": "application/vnd.opentimestamps.v1"}


# ---------- 直列化 ----------
def w_varuint(n):
    out = bytearray()
    while True:
        b = n & 0x7f; n >>= 7
        out.append(b | (0x80 if n else 0))
        if not n: return bytes(out)


def r_varuint(f):
    n, s = 0, 0
    while True:
        b = f.read(1)
        if not b: raise ValueError("途中で終わった")
        n |= (b[0] & 0x7f) << s; s += 7
        if s > 63: raise ValueError("数が大きすぎる")
        if not b[0] & 0x80: return n


def r_varbytes(f, maxlen=8192, minlen=0):
    n = r_varuint(f)
    if n > maxlen or n < minlen: raise ValueError("長さが範囲の外")
    b = f.read(n)
    if len(b) != n: raise ValueError("途中で終わった")
    return b


def apply(op, arg, msg):
    if op == 0xf0: r = msg + arg
    elif op == 0xf1: r = arg + msg
    elif op == 0x08: r = hashlib.sha256(msg).digest()
    elif op == 0x02: r = hashlib.sha1(msg).digest()
    elif op == 0x03: r = hashlib.new("ripemd160", msg).digest()
    elif op == 0xf2: r = msg[::-1]
    elif op == 0xf3: r = msg.hex().encode()
    else: raise ValueError(f"この道具が扱わない命令 0x{op:02x}")
    if len(r) > MAX_MSG: raise ValueError("命令の結果が長すぎる")
    return r


class Timestamp:
    """msg に対する証明の木。items は ("att", tag, payload) か ("op", op, arg, 子の Timestamp)。"""
    def __init__(self, msg):
        self.msg, self.items = msg, []

    @classmethod
    def read(cls, f, msg, depth=0):
        if depth > 256: raise ValueError("深すぎる")
        t = cls(msg)
        while True:
            tag = f.read(1)
            if not tag: raise ValueError("途中で終わった")
            fork = tag[0] == 0xff
            if fork:
                tag = f.read(1)
                if not tag: raise ValueError("分かれ道の後で終わった")
            t.items.append(cls._item(f, tag[0], msg, depth))
            if not fork: return t

    @classmethod
    def _item(cls, f, tag, msg, depth):
        if tag == 0x00:
            at = f.read(8)
            if len(at) != 8: raise ValueError("途中で終わった")
            pl = r_varbytes(f); return ("att", at, pl)
        if tag not in OPS: raise ValueError(f"知らない命令 0x{tag:02x}")
        arg = r_varbytes(f, MAX_MSG, 1) if tag in (0xf0, 0xf1) else b""
        return ("op", tag, arg, cls.read(f, apply(tag, arg, msg), depth + 1))

    def write(self):
        out = bytearray()
        for i, it in enumerate(self.items):
            if i < len(self.items) - 1: out.append(0xff)
            if it[0] == "att":
                out.append(0x00); out += it[1] + w_varuint(len(it[2])) + it[2]
            else:
                out.append(it[1])
                if it[1] in (0xf0, 0xf1): out += w_varuint(len(it[2])) + it[2]
                out += it[3].write()
        return bytes(out)

    def walk(self, depth=0):
        for it in self.items:
            if it[0] == "att": yield depth, self, it
            else: yield from it[3].walk(depth + 1)

    def merge(self, items):
        """items を足す。同じ命令・同じ引数の枝は 1 つに束ね、同じ印は重ねない（公式が辞書で読むと片方の枝を落とす形を作らない・点検 4）。"""
        for it in items:
            if it[0] == "att":
                if not any(x[0] == "att" and x[1] == it[1] and x[2] == it[2] for x in self.items): self.items.append(it)
                continue
            same = next((x for x in self.items if x[0] == "op" and x[1] == it[1] and x[2] == it[2]), None)
            if same: same[3].merge(it[3].items)
            else: self.items.append(it)

    def has_bitcoin(self):
        return any(a[1] == BITCOIN for _, _, a in self.walk())


def write_ots(path, digest, ts):
    with open(path, "wb") as f:
        f.write(MAGIC + w_varuint(1) + b"\x08" + digest + ts.write())


def read_ots(path):
    f = io.BytesIO(open(path, "rb").read())
    if f.read(len(MAGIC)) != MAGIC: raise ValueError("OpenTimestamps の印が無い")
    if r_varuint(f) != 1: raise ValueError("版が 1 でない")
    if f.read(1) != b"\x08": raise ValueError("元のハッシュが sha256 でない")
    digest = f.read(32)
    if len(digest) != 32: raise ValueError("途中で終わった")
    ts = Timestamp.read(f, digest)
    if f.read(1): raise ValueError("後ろに余りがある")
    return digest, ts


# ---------- カレンダー ----------
class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k): return None                            # 転送はたどらない（https → http に落とされない・点検 3）


_OPENER = urllib.request.build_opener(_NoRedirect)


def uri_ok(uri):
    """問い合わせてよい保留の URI か（既知のカレンダーの https・試験の 127.0.0.1 だけ・点検 3）。"""
    if not isinstance(uri, str) or len(uri) > 100: return False
    u = urllib.parse.urlsplit(uri)
    if u.query or u.fragment or u.username or u.password or u.path not in ("", "/"): return False
    host = (u.hostname or "")
    if not re.fullmatch(r"[a-z0-9.-]+", host): return False
    if u.scheme == "https" and u.port in (None, 443):
        return host.endswith(ALLOWED_HOST_SUFFIX) or ("." + host).endswith(ALLOWED_HOST_SUFFIX)
    return bool(os.environ.get("OTS_ALLOW_HTTP")) and u.scheme == "http" and host == "127.0.0.1"


def _http(url, data=None, timeout=20):
    req = urllib.request.Request(url, data=data, headers=UA, method="POST" if data is not None else "GET")
    with _OPENER.open(req, timeout=timeout) as r:
        return r.status, r.read(10000)


def stamp(paths, calendars=CALENDARS, min_ok=2):
    """各ファイルに FILE.ots を書く。nonce を足してからハッシュしたものをカレンダーへ送る（中身が推測されないように・公式と同じ）。
    min_ok 個以上のカレンダーが受けなければ書かない（例外）。"""
    out = []
    for p in paths:
        digest = hashlib.sha256(open(p, "rb").read()).digest(); nonce = secrets.token_bytes(16)
        root = Timestamp(digest); t1 = Timestamp(digest + nonce); root.items.append(("op", 0xf0, nonce, t1))
        msg = hashlib.sha256(digest + nonce).digest(); t2 = Timestamp(msg); t1.items.append(("op", 0x08, b"", t2))
        got = []
        for c in calendars:
            try:
                st, body = _http(c.rstrip("/") + "/digest", msg)
                if st == 200:
                    sub = Timestamp.read(io.BytesIO(body), msg)
                    pend = [a for _, _, a in sub.walk() if a[1] == PENDING]
                    if not pend: raise ValueError("保留の印が無い")
                    t2.merge(sub.items); got.append(c)
            except Exception as e:
                print(f"  {c}: 受けない（{type(e).__name__}）", file=sys.stderr)
        if len(got) < min_ok:
            raise RuntimeError(f"{p}: カレンダーが {len(got)} 個しか受けない（{min_ok} 個以上要る）")
        write_ots(p + ".ots", digest, root); out.append((p, got))
    return out


def _pendings(root):
    """(保留のある節, 保留の印, その節の下にビットコインの印があるか) の一覧。"""
    return [(node, it, node.has_bitcoin()) for _, node, it in root.walk() if it[1] == PENDING]


def needs_upgrade(ots_path):
    """ビットコインの印がまだ付いていない保留があるか。"""
    _, root = read_ots(ots_path)
    return any(not hb for _, _, hb in _pendings(root))


def upgrade(ots_path):
    """まだビットコインの印の無い保留ごとに、カレンダーに問い合わせて印を足す（保留は残す）。保留 1 つの失敗は受け流す。
    戻り値 (足した数, まだ印の無い保留の数)。"""
    digest, root = read_ots(ots_path); done = left = 0
    for node, it, hb in _pendings(root):
        if hb: continue
        try:
            uri = r_varbytes(io.BytesIO(it[2]), 1000).decode("ascii")
            if not uri_ok(uri): raise ValueError(f"問い合わせない宛先 {uri[:60]}")
            st, body = _http(uri.rstrip("/") + "/timestamp/" + node.msg.hex())
            if st != 200: raise ValueError(f"HTTP {st}")
            sub = Timestamp.read(io.BytesIO(body), node.msg)
            if not sub.has_bitcoin(): raise ValueError("まだブロックに入っていない")
            node.merge(sub.items); done += 1
        except Exception as e:
            left += 1
            if os.environ.get("OTS_VERBOSE"): print(f"  保留のまま（{type(e).__name__}: {e}）", file=sys.stderr)
    if done:
        tmp = ots_path + ".tmp"; write_ots(tmp, digest, root); os.replace(tmp, ots_path)
    return done, left


def info(ots_path):
    digest, root = read_ots(ots_path); lines = [f"元の sha256 {digest.hex()}"]
    for depth, node, it in root.walk():
        if it[1] == PENDING:
            try: uri = r_varbytes(io.BytesIO(it[2]), 1000).decode("ascii", "replace")
            except ValueError: uri = "（読めない）"
            lines.append(f"  保留{'（ビットコインの印あり）' if node.has_bitcoin() else ''}: {uri}（この時点の値 {node.msg.hex()[:16]}…）")
        elif it[1] == BITCOIN:
            lines.append(f"  ビットコイン: ブロックの高さ {r_varuint(io.BytesIO(it[2]))}（merkle root {node.msg[::-1].hex()[:16]}…）")
        else: lines.append(f"  ほかの印 {it[1].hex()}")
    return "\n".join(lines)


EXPLORERS = ["https://blockstream.info/api", "https://mempool.space/api"]


def _explorers():
    t = os.environ.get("OTS_EXPLORER")                                           # 試験の偽のブロック表（127.0.0.1 だけ）
    if t and urllib.parse.urlsplit(t).hostname == "127.0.0.1": return [t]
    return EXPLORERS


def verify(ots_path):
    """ビットコインの印ごとに、その高さのブロックの merkle root が証明の値と同じかを公開のブロック表で確かめる。
    戻り値 [(高さ, 合う True/False/None〔確かめられない〕, ブロックの時刻 UTC の文字列 or 理由)]。ブロック表は 2 つのうち先に答えた方。"""
    import json, datetime
    _, root = read_ots(ots_path); out = []
    for _, node, it in root.walk():
        if it[1] != BITCOIN: continue
        h = r_varuint(io.BytesIO(it[2])); mine = node.msg[::-1].hex(); res = None
        for base in _explorers():
            try:
                st, bh = _http(f"{base}/block-height/{h}")
                if st != 200: continue
                bh = bh.decode("ascii").strip()
                if not re.fullmatch(r"[0-9a-f]{64}", bh): continue
                st, bj = _http(f"{base}/block/{bh}")
                if st != 200: continue
                j = json.loads(bj); ok = j.get("merkle_root") == mine
                res = (h, ok, datetime.datetime.fromtimestamp(int(j["timestamp"]), datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC") if ok else f"merkle root が違う（表 {str(j.get('merkle_root'))[:16]}… 証明 {mine[:16]}…）")
                break
            except Exception as e:
                res = (h, None, f"確かめられない（{type(e).__name__}）")
        out.append(res or (h, None, "確かめられない"))
    return out


def check(path, ots_path):
    digest, _ = read_ots(ots_path)
    return hashlib.sha256(open(path, "rb").read()).digest() == digest


def main():
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="cmd", required=True)
    a = sp.add_parser("stamp"); a.add_argument("files", nargs="+"); a.add_argument("--cal", nargs="*", default=None); a.add_argument("--min-ok", type=int, default=2)
    b = sp.add_parser("upgrade"); b.add_argument("files", nargs="+")
    c = sp.add_parser("info"); c.add_argument("file")
    d = sp.add_parser("check"); d.add_argument("file"); d.add_argument("ots")
    e = sp.add_parser("verify"); e.add_argument("file")
    x = ap.parse_args()
    if x.cmd == "stamp":
        for p, got in stamp(x.files, x.cal or CALENDARS, x.min_ok): print(f"{p}.ots（受けたカレンダー {len(got)}）")
    elif x.cmd == "upgrade":
        for p in x.files: print(p, "足した %d・印の無い保留 %d" % upgrade(p))
    elif x.cmd == "info":
        print(info(x.file))
    elif x.cmd == "verify":
        r = verify(x.file)
        for h, ok, t in r: print(f"ブロック {h}: " + ("合う・" + t if ok else ("★ " if ok is False else "") + t))
        if not r: print("ビットコインの印がまだ無い（upgrade の後に）")
        sys.exit(0 if r and all(ok for _, ok, _ in r) else 1)
    else:
        ok = check(x.file, x.ots); print("同じ" if ok else "★ 違う"); sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
