#!/bin/bash
# fx_自走.sh — FX bot の検証・制作を後ろで回し続ける（2026-11-18・taichi「fx bot検証を claude code で基本的にずっと後ろで進めている状況にしたい」）
#   対話で「fx bot制作を N 時間自走で」と頼んでいたものを、launchd（com.taichi.fx-jisou）が常駐させて 1 回ずつ繰り返す。
#   1 回 = claude -p（Opus・手順/fx_自走_手順.md）を新しいセッションで FX_SESSION_MIN 分。終わったら FX_GAP_MIN 分あけて次の回。
#   利用上限 → 「resets …」の 2 分後まで待つ（読めなければ FX_LIMIT_WAIT_MIN 分）。やることが無い（.fx_自走_idle）→ FX_IDLE_MIN 分待つ。
#   3 回続けて失敗 → 要対応.md に ★ を 1 回書いて 120 分待つ。Mac がスリープ中は止まり、起きたら続きから。
# 使い方:
#   bash fx_自走.sh status        … 動いているか・今の回・直近の回
#   bash fx_自走.sh off           … 今の回が終わったら止まる（ログインし直しても止まったまま）
#   bash fx_自走.sh on            … 再開（launchd に登録して起こす）
#   bash fx_自走.sh pause 3       … 3 時間、新しい回を始めない（対話で自走するとき・使用量を空けたいとき）。resume で解除
#   bash fx_自走.sh run           … launchd が呼ぶ本体（手では呼ばない）
# 環境変数（plist の EnvironmentVariables で変える）: FX_SESSION_MIN=120 FX_GAP_MIN=10 FX_IDLE_MIN=240 FX_LIMIT_WAIT_MIN=60 FX_MODEL=opus
set -u
export LANG=ja_JP.UTF-8 LC_ALL=ja_JP.UTF-8
DIR="$(cd "$(dirname "$0")" && pwd)"; V="$(cd "$DIR/.." && pwd)"; WS="$(cd "$V/.." && pwd)"
export PATH="$HOME/.local/bin:$HOME/.claude/local:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
LABEL="com.taichi.fx-jisou"; PLIST="$HOME/Library/LaunchAgents/${LABEL}.plist"
LOGD="$DIR/ログ/自走"; LIST="$LOGD/回の一覧.tsv"; PROMPT="$DIR/手順/fx_自走_手順.md"; Y="$DIR/要対応.md"
STOP="$DIR/自走を止める"; PAUSE="$DIR/.fx_自走_pause"; IDLE="$DIR/.fx_自走_idle"; PIDF="$DIR/.fx_自走.pid"; NOWF="$DIR/.fx_自走_now"
SESSION_MIN="${FX_SESSION_MIN:-120}"; GAP="${FX_GAP_MIN:-10}"; IDLE_MIN="${FX_IDLE_MIN:-240}"; LIMIT_WAIT="${FX_LIMIT_WAIT_MIN:-60}"; MODEL="${FX_MODEL:-opus}"
mkdir -p "${LOGD}"
running() { [ -f "${PIDF}" ] && kill -0 "$(cat "${PIDF}")" 2>/dev/null; }
ts() { date '+%Y-%m-%d %H:%M'; }

case "${1:-}" in
  status)
    if running; then echo "動いている（pid $(cat "${PIDF}")）"; else echo "動いていない"; fi
    [ -f "${STOP}" ] && echo "止める印あり（${STOP}）。再開は: bash $0 on"
    if [ -f "${PAUSE}" ]; then u="$(cat "${PAUSE}")"; [ "$(date +%s)" -lt "${u}" ] && echo "一時停止中: $(date -r "${u}" '+%m-%d %H:%M') まで"; fi
    [ -f "${IDLE}" ] && { echo "前の回の「やることが無い」:"; sed 's/^/  /' "${IDLE}"; }
    [ -f "${NOWF}" ] && echo "今: $(cat "${NOWF}")"
    [ -f "${LIST}" ] && { echo "直近の回（開始・終了・結果・記録）:"; tail -5 "${LIST}" | sed 's/^/  /'; }
    exit 0;;
  off) touch "${STOP}"; echo "止める印を置いた。今の回が終わったら止まる（すぐ止めるなら: launchctl bootout gui/$(id -u)/${LABEL}）"; exit 0;;
  on)
    rm -f "${STOP}"
    if launchctl print "gui/$(id -u)/${LABEL}" >/dev/null 2>&1; then launchctl kickstart "gui/$(id -u)/${LABEL}"
    else launchctl bootstrap "gui/$(id -u)" "${PLIST}"; fi
    echo "オン。状態は: bash $0 status"; exit 0;;
  pause) h="${2:-3}"; echo $(( $(date +%s) + h * 3600 )) > "${PAUSE}"; echo "${h} 時間、新しい回を始めない（今の回は最後まで続く）。解除: bash $0 resume"; exit 0;;
  resume) rm -f "${PAUSE}"; echo "一時停止を解除"; exit 0;;
  run) ;;
  *) sed -n 2,14p "$0"; exit 0;;
esac

# ---- 本体（launchd から）----
[ -f "${STOP}" ] && { echo "$(ts) 止める印があるので始めない"; exit 0; }
running && { echo "$(ts) もう動いている（pid $(cat "${PIDF}")）"; exit 0; }
echo $$ > "${PIDF}"
trap 'rm -f "${PIDF}" "${NOWF}"; echo "$(ts) 中断"; exit 0' INT TERM
# 分単位で待つ。止める印が置かれたら抜ける
nap() { local m; for ((m=0; m<$1; m++)); do [ -f "${STOP}" ] && return; sleep 60; done; }
state() { make_py="$DIR/make_状態.py"; python3 "${make_py}" >/dev/null 2>&1 || "$WS/作業層/大容量/venv_forward/bin/python" "${make_py}" >/dev/null 2>&1; }
fail=0
echo "$(ts) === 自走 開始（1 回 ${SESSION_MIN} 分・間 ${GAP} 分・モデル ${MODEL}）"
while :; do
  [ -f "${STOP}" ] && { echo "$(ts) 止める印で終了"; break; }
  if [ -f "${PAUSE}" ]; then
    u="$(cat "${PAUSE}")"; left=$(( (u - $(date +%s)) / 60 ))
    if [ "${left}" -gt 0 ]; then echo "$(ts) 一時停止中（あと ${left} 分）"; echo "一時停止中 $(date -r "${u}" '+%m-%d %H:%M') まで" > "${NOWF}"; nap "${left}"; continue; fi
    rm -f "${PAUSE}"
  fi
  rid="$(date +%Y%m%d_%H%M)"; rd="$LOGD/${rid}"; mkdir -p "${rd}"; log="${rd}/セッション.log"
  end_hm="$(date -v+"${SESSION_MIN}"M '+%H:%M')"
  echo "回 ${rid}（${end_hm} まで）・記録 ${rd}/記録.md" > "${NOWF}"
  rm -f "${IDLE}"
  printf '# %s 後ろの自走 %s（持ち時間 %s 分・%s まで・fx_自走.sh）\n\n' "$(ts)" "${rid}" "${SESSION_MIN}" "${end_hm}" > "${rd}/記録.md"
  head="この回: 開始 $(ts)・持ち時間 ${SESSION_MIN} 分・終わりの時刻 ${end_hm}（その 10 分前に書き終える）・記録の置き場 自動実行/ログ/自走/${rid}/（記録.md は作ってある）"
  echo "$(ts) ▶ 回 ${rid}"
  ( cd "$V" && caffeinate -i perl -e 'alarm shift; exec @ARGV' $(( (SESSION_MIN + 20) * 60 )) \
      claude -p "${head}

$(cat "${PROMPT}")" --model "${MODEL}" --output-format json --permission-mode acceptEdits \
      --allowedTools "Bash" "Read" "Edit" "Write" "Glob" "Grep" "Agent" "Task" "TodoWrite" \
      --disallowedTools "Bash(rm:*)" "Bash(git:*)" "Bash(sudo:*)" "Bash(launchctl:*)" "Bash(crontab:*)" "Bash(ssh:*)" "Bash(scp:*)" ) \
      > "${log}.json" 2>&1 < /dev/null
  rc=$?
  python3 "$DIR/tok_record.py" "${log}.json" --out "${log}" --qid "自走${rid}" --model "${MODEL}" --kind jisou >/dev/null 2>&1 || cp "${log}.json" "${log}"
  last="$(grep -v '^\s*$' "${log}" | tail -3 | tr '\n' ' ' | cut -c1-300)"
  printf '%s\t%s\t%s\t%s\t%s\n' "${rid}" "$(ts)" "rc=${rc}" "${last}" "ログ/自走/${rid}/" >> "${LIST}"
  echo "$(ts) ◀ 回 ${rid} 終了 rc=${rc}: ${last}"
  state
  # 利用上限
  if grep -qiE "usage limit|rate.?limit|limit reached|session limit|hit your .*limit|利用上限" "${log}" 2>/dev/null; then
    wait_min="${LIMIT_WAIT}"
    reset="$(grep -ohiE "resets [0-9]{1,2}(:[0-9]{2})?(am|pm)" "${log}" | head -1 | awk '{print $2}')"
    if [ -n "${reset}" ]; then
      secs="$(python3 - "${reset}" <<'PY'
import sys, datetime, re
m = re.match(r'(\d{1,2})(?::(\d{2}))?(am|pm)', sys.argv[1].lower())
h, mi, ap = int(m.group(1)), int(m.group(2) or 0), m.group(3)
h = h % 12 + (12 if ap == 'pm' else 0)
now = datetime.datetime.now(); t = now.replace(hour=h, minute=mi, second=0, microsecond=0)
if t <= now: t += datetime.timedelta(days=1)
print(int((t - now).total_seconds()))
PY
)"
      [ -n "${secs}" ] && [ "${secs}" -le 86400 ] && wait_min=$(( secs / 60 + 2 ))
    fi
    echo "$(ts) 利用上限（resets ${reset:-不明}）→ ${wait_min} 分待つ"; echo "利用上限で待ち（resets ${reset:-不明}）" > "${NOWF}"; nap "${wait_min}"; continue
  fi
  if [ "${rc}" -ne 0 ] && ! grep -q '"type":"result"' "${log}.json" 2>/dev/null; then
    fail=$(( fail + 1 )); echo "$(ts) 失敗 ${fail} 回目"
    if [ "${fail}" -ge 3 ]; then
      if ! grep -A1 -F -- "（自動・fx_自走.sh）" "${Y}" | grep -q '^- 状態: 未解決'; then
        printf '\n## %s — ★ 後ろの自走が 3 回続けて失敗した（自動・fx_自走.sh）\n- 状態: 未解決\n- 直近の回: `自動実行/ログ/自走/%s/セッション.log`（終了コード %s）。ログインが切れているなら Mac の Terminal アプリで `claude` を起動して `/login`。\n- 120 分ごとにやり直している。止めるなら `bash 検証/自動実行/fx_自走.sh off`。\n' "$(ts)" "${rid}" "${rc}" >> "${Y}"
      fi
      echo "120 分待ち（3 回続けて失敗）" > "${NOWF}"; nap 120; fail=0; continue
    fi
    nap 10; continue
  fi
  fail=0
  if [ -f "${IDLE}" ]; then
    echo "$(ts) やることが無い → ${IDLE_MIN} 分待つ: $(head -1 "${IDLE}")"; echo "やることが無いので待ち（${IDLE_MIN} 分）" > "${NOWF}"; nap "${IDLE_MIN}"; continue
  fi
  echo "次の回まで ${GAP} 分" > "${NOWF}"; nap "${GAP}"
done
rm -f "${PIDF}" "${NOWF}"; echo "$(ts) === 自走 終了"
