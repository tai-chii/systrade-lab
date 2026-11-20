#!/bin/bash
# run_forward.sh — S21・S23 ほかのフォワード記録（2026-11-14 修正18 で S17b の観察枠を足した・2026-11-16 S68 を足した）（1 日 1 回。lab_run.sh の 0.55 から呼ばれる。手で回すなら bash run_forward.sh --force）
#   1. 必要なライブラリの確認（無ければ 作業層/大容量/venv_forward を作って入れる）
#   2. 初回だけ: 記録用コードが検証のコードと同じ売買を出すかを確認（check_equivalence.py）。違えば止めて要対応へ
#   3. データ取得（Dukascopy 19 銘柄 H1）→ S21 の年度のモデル（10-01 以降に無ければ作る）→ S21 記録 → S23 記録 → 記録_最新.md
set -u
D="$(cd "$(dirname "$0")" && pwd)"; V="$(cd "$D/../.." && pwd)"; WS="$(cd "$V/.." && pwd)"   # D=検証/トレード/forward（2026-10-28 移動）
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
mkdir -p "$D/ログ"; STAMP="$D/ログ/.last_run"; TODAY="$(date +%Y%m%d)"
if [ "${1:-}" != "--force" ] && [ "$(cat "$STAMP" 2>/dev/null)" = "$TODAY" ]; then echo "  今日は記録済み（--force で再実行）"; exit 0; fi
LOCK="$D/ログ/.lock"; if ! mkdir "$LOCK" 2>/dev/null; then if [ -n "$(find "$LOCK" -maxdepth 0 -mmin +720 2>/dev/null)" ]; then rmdir "$LOCK"; mkdir "$LOCK"; else echo "  別の記録が実行中（${LOCK}）"; exit 0; fi; fi; trap 'rmdir "$LOCK" 2>/dev/null' EXIT
LOG="$D/ログ/forward_$(date +%Y%m%d_%H%M).log"; exec > >(tee -a "$LOG") 2>&1
TO() { perl -e 'alarm shift; exec @ARGV' "$@"; }
TODO() { case "$1" in "★ "*) local m="${1#★ }"; TODO_STAR "${m%%。*}" "$1"; return 0;; esac   # 修正17: ★ の行は通知と 状態.md に出る形で書く（点検 11-13 の 1）
  printf '\n## %s フォワード記録（run_forward.sh）\n- %s\n' "$(date '+%Y-%m-%d %H:%M')" "$1" >> "$V/自動実行/要対応.md"; }
# 2026-11-11 修正12: 見出しに ★ と「（自動」、次の行に「状態: 未解決」を書く形（notify_star.py が通知し、make_状態.py が「人の判断待ち」に数える。TODO の形はどちらにも拾われない）。
#   $1 見出し（★ の後）・$2 本文。同じ見出しの未解決の節があれば足さない（1 回の停止に 1 節）。直ったら人か Claude が「- 状態: 解決（日付）」に書き換える
TODO_STAR() { local y="$V/自動実行/要対応.md" t="$1（自動・run_forward.sh）"
  if grep -A1 -F -- "— ★ $t" "$y" 2>/dev/null | grep -q '^- 状態: 未解決'; then echo "  要対応に同じ未解決の節がある（足さない）: $1"; return 0; fi
  printf '\n## %s — ★ %s\n- 状態: 未解決\n- %s\n' "$(date '+%Y-%m-%d %H:%M')" "$t" "$2" >> "$y"; }

PY=python3
if ! $PY -c "import lightgbm, sklearn, pyarrow, pandas" 2>/dev/null; then
  VENV="$WS/作業層/大容量/venv_forward"
  if [ ! -x "$VENV/bin/python" ]; then
    # 2026-10-28: Mac 標準の python3 は 3.9 で lightgbm 4.7.0（Python 3.10 以上）が入らない → uv で 3.11 の venv を作る
    echo "  ライブラリが無い → $VENV を作る（uv・Python 3.11）"
    if command -v uv >/dev/null; then uv venv -q --python 3.11 "$VENV" && uv pip install -q --python "$VENV/bin/python" pandas pyarrow lightgbm==4.7.0 scikit-learn
    else python3 -m venv "$VENV" && "$VENV/bin/pip" install -q pandas pyarrow lightgbm==4.7.0 scikit-learn; fi || { TODO "venv を作れなかった（uv が無い・ネット・Python 3.10 未満のどれか）。ログ: $LOG"; exit 1; }
  fi
  PY="$VENV/bin/python"
fi
echo "  python: $PY"

OK="$D/S21/凍結/同等性_OK.txt"
if [ ! -f "$OK" ]; then
  echo "--- 初回の確認: 記録用コード ＝ 検証のコード か"
  out="$(TO 1800 $PY "$D/S21/check_equivalence.py" 2>&1 | grep -E '^検証 [0-9]+ 件')"; echo "$out"
  if echo "$out" | grep -qE "行動の不一致 0 / R の最大差 0\.00e\+00" && echo "$out" | awk '{if ($2==$6 && $6==$10 && $2>0) ok=1} END{exit !ok}'; then
    { date '+%Y-%m-%d %H:%M'; echo "$PY"; echo "$out"; } > "$OK"
  else
    TODO "記録用コードと検証のコードで売買が一致しない（この環境のライブラリ差の可能性）。記録は止めた。ログ: $LOG"; exit 1
  fi
fi

echo "--- データ取得（19 銘柄 H1・上限 ${FETCH_TO:-2400} 秒）"; TO "${FETCH_TO:-2400}" $PY "$D/fetch_forward.py" | tail -21; rf=${PIPESTATUS[0]}
[ "$rf" -ne 0 ] && echo "  取得が途中（Dukascopy の回数制限など）。次の周回で続きから取る（今日の印は付けない）"
echo "--- S21 年度のモデル（毎年 10-01 に学習し直す・運用規程 §4）"; TO 3600 $PY "$D/S21/freeze_s21.py" --auto; rz=$?
[ $rz -ne 0 ] && [ $rz -ne 5 ] && TODO "★ S21 の年度のモデルを作れなかった。freeze_s21.py --auto・終了コード ${rz}。ログ: $LOG"
echo "--- S21"; TO 900 $PY "$D/S21/forward_s21.py"; r21=$?
echo "--- S21 局面（月次の学習外 AUC・売買には無関係・2026-10-28）"; TO 1800 $PY "$D/S21/difficulty_s21.py"; rdf=$?
[ $rdf -ne 0 ] && TODO "S21 の局面（difficulty_s21.py）が終了コード $rdf で止まった（売買の記録には無関係）。ログ: $LOG"
echo "--- S23"; TO 600 $PY "$D/S23/forward_s23.py"; r23=$?
# 2026-10-31（Q586）: S30 日本株 横断 ML の仮想フォワード。月 1 回しか動かないので、価格の取り直し（yfinance・venv_equities・数十分）は 7 日に 1 回、記録は毎回（30 秒）
echo "--- S30（日本株 横断 ML・月次・仮想フォワード）"; r30=0
S30STAMP="$D/S30/記録/.update_last"; EQPY="$WS/作業層/venv_equities/bin/python"
if [ "${S30_UPDATE:-1}" = "1" ] && [ -x "$EQPY" ] && [ -z "$(find "$S30STAMP" -mtime -7 2>/dev/null)" ]; then
  TO 3600 "$EQPY" "$D/S30/update_prices_s30.py" | tail -3; ru=${PIPESTATUS[0]}   # 2026-11-03: tail の終了コードで成功扱いにしていた（監査E の 4）
  if [ "$ru" -eq 0 ]; then date +%Y%m%d > "$S30STAMP"; else echo "  S30 の価格の取り直しが失敗（終了コード ${ru}・yfinance・ネット・取り損ねた塊）。印は付けず次の回に取り直す。記録は手元のデータで続ける"; fi
else echo "  価格の取り直しは 7 日に 1 回（前回 $(cat "$S30STAMP" 2>/dev/null || echo なし)）"; fi
TO 900 $PY "$D/S30/forward_s30.py" | tail -8; r30=${PIPESTATUS[0]}
[ "$r30" -eq 3 ] && TODO_STAR "S30 が停止条件に達した" "累積 L−S の最大下落が Q583 封印期間の最悪 ×1.5 を超えた（2026-11-12 修正14 で通知に出る形に）。$D/S30/記録/状態.json"
[ "$r30" -eq 4 ] && TODO_STAR "S30 の確定済みの記録が変わった" "記録/確定_monthly.csv・確定_daily.csv・確定_建玉/・判断時_建玉/ のどれかが前回の保存から変わっている・無くなっている（手で触った・Excel で保存した・Syncthing の衝突・壊れた）。forward_s30.py は何も書かずに止めた（修正11・15）。$D/S30/記録/確定_hashes.json と前回の控えを比べて元に戻す。ログ: $LOG"
[ "$r30" -ne 0 ] && [ "$r30" -ne 3 ] && [ "$r30" -ne 4 ] && TODO_STAR "S30 のフォワード記録が止まった" "forward_s30.py が終了コード $r30 で止まった（凍結が欠けた・例外・打ち切りのどれか・2026-11-12 修正14 で通知に出る形に）。ログ: $LOG"
# 2026-11-01（Q599）: S34 暗号資産の四半期ベーシスの仮想フォワード。価格は Binance の公開 API（無料・キー不要）。取得に失敗したら手元のデータで記録する
echo "--- S34（暗号資産 四半期ベーシス・日次・仮想フォワード）"
TO 300 $PY "$V/_データ/fetch/fetch_binance_basis.py" | tail -2; [ "${PIPESTATUS[0]}" -ne 0 ] && echo "  S34 の価格の取得が失敗（ネット・Binance の制限？）。記録は手元のデータで続ける"
TO 300 $PY "$D/S34/forward_s34.py" | tail -3; r34=${PIPESTATUS[0]}
[ "$r34" -eq 3 ] && TODO "★ S34 が停止条件に達した。$D/S34/記録/状態.json"
[ "$r34" -ne 0 ] && [ "$r34" -ne 3 ] && TODO_STAR "S34 のフォワード記録が止まった" "forward_s34.py が終了コード $r34 で止まった（5 は凍結の控えが無い・修正14）。ログ: $LOG"
# 2026-11-01（Q616）: S44 FX 10 本 H1 の仮想フォワード。データは S21 と同じ Dukascopy H1。注文は出さない。
echo "--- S44（FX 10 本 H1・XM の実コスト・q 0.97・仮想フォワード）"
TO 900 $PY "$D/S44/forward_s44.py" | tail -2; r44=${PIPESTATUS[0]}
[ "$r44" -eq 3 ] && TODO "★ S44 が停止条件に達した。$D/S44/記録/状態.json"
[ "$r44" -ne 0 ] && [ "$r44" -ne 3 ] && TODO_STAR "S44 のフォワード記録が止まった" "forward_s44.py が終了コード $r44 で止まった。ログ: $LOG"
# 2026-11-01（Q628）: S53 S44 の 9 シード平均版の仮想フォワード。データは S44 と同じ。注文は出さない。
echo "--- S53（S44 の 9 シード平均版・仮想フォワード）"
TO 900 $PY "$D/S53/forward_s53.py" | tail -2; r53=${PIPESTATUS[0]}
[ "$r53" -eq 3 ] && TODO "★ S53 が停止条件に達した。$D/S53/記録/状態.json"
[ "$r53" -ne 0 ] && [ "$r53" -ne 3 ] && TODO_STAR "S53 のフォワード記録が止まった" "forward_s53.py が終了コード $r53 で止まった。ログ: $LOG"
# 2026-11-14 修正18（Q729・taichi「27 入れて」）: S17b 指数 8 本の買い持ち（XM の先物 CFD の形）の観察枠の記録（日次・追記だけ・注文なし）。
#   US500・USTECH・GER40・JPN225 は上の取得の H1、US30・UK100・FRA40・SUI20 は forward_s17b.py が同じ部品で取る（H1_s17b/）。0 正常・2 取得が途中・3 停止・4 データが古い
echo "--- S17b（指数 8 本の買い持ち・観察枠・日次）"
TO 1200 $PY "$D/S17b/forward_s17b.py" | tail -3; r17=${PIPESTATUS[0]}
[ "$r17" -eq 2 ] && echo "  S17b の追加 4 本の取得が途中（Dukascopy の回数制限など）。記録は 8 本そろった日まで（次の回で続きから）"
[ "$r17" -eq 3 ] && TODO_STAR "S17b が停止条件に達した" "最高値から −28%（観察枠の停止の線・Q729・taichi 承認 2026-11-14）。$D/S17b/記録/状態.json"
[ "$r17" -eq 4 ] && TODO_STAR "S17b の記録のデータが古い" "8 本そろった最後の日が 4 営業日より前（追加 4 本の取得が追いつかない・Dukascopy の回数制限など）。$D/S17b/記録/状態.json"
[ "$r17" -ne 0 ] && [ "$r17" -ne 2 ] && [ "$r17" -ne 3 ] && [ "$r17" -ne 4 ] && TODO_STAR "S17b の観察枠の記録が止まった" "forward_s17b.py が終了コード $r17 で止まった（例外・1200 秒の打ち切りのどれか）。ログ: $LOG"
# 2026-11-16（Q739・Q740・taichi「入れる」）: S68 暗号資産の永久先物の横断モメンタムの記録のフォワード（週次の判断・注文なし）。Binance の公開 API（キー不要）。
#   月曜の最初の回で判断を書き、7 日たった週を確定する。取得が途中なら終了コード 2 で次の回に続ける（今日の印には効かない）
echo "--- S68（暗号資産の永久先物の横断モメンタム・週次・記録のフォワード）"
TO 900 $PY "$D/S68/forward_s68.py" | tail -4; r68=${PIPESTATUS[0]}
[ "$r68" -eq 2 ] && echo "  S68 の取得が途中（日曜の足がまだ・Binance の制限など）。次の回で続きから"
[ "$r68" -eq 3 ] && TODO_STAR "S68 が停止条件に達した" "累計の最高値からの下落が −1.05 を超えた（Q740 の最悪 −0.698 × 1.5）。$D/S68/記録/状態.json"
[ "$r68" -ne 0 ] && [ "$r68" -ne 2 ] && [ "$r68" -ne 3 ] && TODO_STAR "S68 の記録が止まった" "forward_s68.py が終了コード $r68 で止まった（5 は凍結のハッシュ違い・1 は例外・900 秒の打ち切り）。ログ: $LOG"
[ $r21 -eq 3 ] && TODO "★ S21 が停止条件に達した（運用規程_フォワード_20261025.md §5）。$D/S21/記録/状態.json"
[ $r21 -eq 4 ] && TODO "★ S21 の今の年度のモデルが無いので、年度の始まり以降は判断していない（9 月末までのデータがそろうと freeze_s21.py --auto が作る）。$D/S21/記録/状態.json"
[ $r23 -eq 3 ] && TODO "★ S23 が停止条件に達した。$D/S23/記録/状態.json"
# 2026-11-11 修正12（監査B の 1）: S21・S23 の記録がその他の終了コードで止まったときも要対応へ（凍結ファイルの不一致・例外・打ち切りが、どこにも出ずに黙って止まっていた）
[ $r21 -ne 0 ] && [ $r21 -ne 3 ] && [ $r21 -ne 4 ] && TODO_STAR "S21 のフォワード記録が止まった" "forward_s21.py が終了コード $r21 で止まった（凍結ファイルの不一致・例外・900 秒の打ち切りのどれか）。この回の S21 の記録は書かれていない。直るまで 12:20・15:20・21:20 の枠でやり直す。ログ: $LOG"
[ $r23 -ne 0 ] && [ $r23 -ne 3 ] && TODO_STAR "S23 のフォワード記録が止まった" "forward_s23.py が終了コード $r23 で止まった（データ元が取れない・例外のどれか）。この回の S23 の記録は書かれていない。直るまで次の枠でやり直す。ログ: $LOG"
rec_ok=1; { [ $r21 -ne 0 ] && [ $r21 -ne 3 ] && [ $r21 -ne 4 ]; } && rec_ok=0; { [ $r23 -ne 0 ] && [ $r23 -ne 3 ]; } && rec_ok=0   # 止まった回は今日の印を付けない（次の枠でやり直す）
$PY "$D/report.py" && [ "$rf" -eq 0 ] && [ "$rec_ok" -eq 1 ] && echo "$TODAY" > "$STAMP"
# 2026-11-0x 修正10（監査C の 3）: 取得が途中の回は、記録_最新.md に「暫定」と印を付ける（読むだけ・売買の計算には無関係）
[ "$rf" -ne 0 ] && printf '\n- ★ この回はデータの取得が途中（Dukascopy の回数制限など）。S21・S44・S53 の数字は暫定で、次の周回で直近の取引が変わることがある\n' >> "$D/記録_最新.md"
# 2026-11-05 修正9（監査D の 3・9・taichi「全部進めて」）: 記録が読む依存のハッシュと、取引の表の写しの鎖を毎日照合する（読むだけ・売買の計算には無関係）
echo "--- 記録の見張り（integrity_check.py）"; IO=$(TO 600 $PY "$D/integrity_check.py" --out "$D/ログ/integrity.json" --anchor "$V/lab-ops/trade/anchor/chain_heads.csv" 2>&1); ri=$?; printf '%s\n' "$IO"
# 修正17（点検 11-13 の A-1）: 見出しに ★ の付いた名前（S44・依存 S30・外の錨・記録用コード など）を入れる。同じ組み合わせが続く間は 1 節、変われば新しい節と通知
if [ $ri -ne 0 ]; then IN=$(printf '%s\n' "$IO" | sed -n 's/^★ \([^:]*\):.*/\1/p' | LC_ALL=C sort -u | awk 'NR>1{printf "・"}{printf "%s",$0}'); [ -n "$IN" ] || IN="終了コード ${ri}"; [ $ri -ne 1 ] && case "$IN" in 終了コード*) ;; *) IN="${IN}・終了コード ${ri}";; esac   # 並びは C の順（手で回しても同じ見出し）・途中で落ちた（1 以外）は終了コードも
  TODO_STAR "記録の見張りで異常（${IN}）" "依存の変更・確定済みの取引の消失や R の変化・写しの鎖の切れ目・錨・帳簿のどれか。$D/ログ/integrity.json・ログ: $LOG"; fi
python3 "$V/自動実行/make_状態.py" >/dev/null 2>&1 || true   # 2026-10-28: 状態.md の更新（売買の計算には無関係）
