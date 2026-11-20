#!/bin/zsh
# S21 bot の判断のスプレッドの表 spr_ref.json を作り直し、前の表と比べ、--send のときだけ winnote の bot のフォルダへ置く（2026-11-05 夜間 P4）。
# 月 1 回（記録のデータが前の月の末まで揃った後・毎月 2〜5 日ごろ）に回す想定。bot は毎時 spr_ref.json を読み直すので再起動は要らない。
# 送る前の歯止め: ① 作った表の期間の終わりが 7 日より古ければ送らない（記録のデータが止まっている）② 前の表との比が 3 倍を超える
#   銘柄 × 時があれば送らない（データの異常か、業者側の大きな変化。人が見る）③ winnote に届かなければ送らない。
# 使い方: zsh refresh_spr_ref.sh（作って比べるだけ）／ zsh refresh_spr_ref.sh --send（歯止めを通れば送る）
# 終了コード: 0 済み・2 歯止めで止めた・3 winnote に届かない・4 送った後の照合が合わない
HERE=${0:A:h}; PY=${PY:-$HERE/../../../../作業層/大容量/venv_forward/bin/python}
NEW=$HERE/spr_ref_new.json; CUR=$HERE/spr_ref.json; HIST=$HERE/../../forward/変更履歴.csv
DST='C:/Users/gtaic/bot/検証/トレード/執行/S21/spr_ref.json'
set -e
$PY -B $HERE/make_spr_ref.py --out $NEW
set +e
$PY -B - "$CUR" "$NEW" <<'EOF'
import json, sys, numpy as np, pandas as pd
cur, new = (json.load(open(p, encoding="utf-8")) for p in sys.argv[1:3])
end = pd.Timestamp(new["meta"]["to_utc"]); age = (pd.Timestamp.now(tz="UTC") - end).days
worst = []
for s, v in new["spr"].items():
    o = np.asarray(cur["spr"].get(s, [np.nan] * 24), float); n = np.asarray(v, float); r = n / o
    k = int(np.nanargmax(np.abs(np.log(r)))); worst.append((abs(np.log(r[k])), s, k, r[k]))
worst.sort(reverse=True)
print(f"新しい表: {new['meta']['from_utc'][:10]}〜{new['meta']['to_utc'][:10]}（終わりは {age} 日前）・前の表: {cur['meta']['from_utc'][:10]}〜{cur['meta']['to_utc'][:10]}")
print("前の表との比が大きい銘柄 × 時（NY）: " + "・".join(f"{s} {k} 時 {r:.2f} 倍" for _, s, k, r in worst[:5]))
bad = [f"{s} {k} 時 {r:.2f} 倍" for x, s, k, r in worst if x > np.log(3)]
if age > 7: print(f"★ 止める: 表の期間の終わりが {age} 日前（記録のデータが止まっている恐れ）"); sys.exit(2)
if bad: print("★ 止める: 前の表と 3 倍を超えて違う: " + "・".join(bad)); sys.exit(2)
EOF
rc=$?
(( rc != 0 )) && { echo "送らない（rc $rc）。$NEW は残す"; exit 2 }
[[ "$1" == "--send" ]] || { echo "比べるだけ（--send なし）。$NEW は残す"; exit 0 }
ssh -o ConnectTimeout=5 winnote 'exit 0' 2>/dev/null || { echo "winnote に届かない"; exit 3 }
scp -q "$NEW" "winnote:$DST.tmp" && ssh winnote "Move-Item -Force '$DST.tmp' '$DST'" || { echo "送れない"; exit 3 }
h1=$(shasum -a 256 "$NEW" | cut -c1-64); h2=$(ssh winnote "(Get-FileHash '$DST' -Algorithm SHA256).Hash.ToLower()" | tr -d '\r\n ')
[[ "$h1" == "$h2" ]] || { echo "★ 送った後のハッシュが違う（$h1 / $h2）"; exit 4 }
cp "$CUR" "$HERE/spr_ref_$(date +%Y%m%d)_前.json"; mv "$NEW" "$CUR"
print -r -- "$(TZ=Asia/Tokyo date '+%Y-%m-%d %H:%M'),S21,執行,判断のスプレッドの表 spr_ref.json を作り直して winnote へ置いた（refresh_spr_ref.sh・sha256 ${h1:0:12}・判断の式と bot は不変）,執行/S21/spr_ref.json" >> "$HIST"
echo "送った: $DST（${h1:0:12}）。次の毎時の判断から効く（状態.json の「判断のスプレッド」の作成日で確かめる）"
