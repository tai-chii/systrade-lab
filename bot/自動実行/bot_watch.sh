#!/bin/zsh
# bot_watch.sh — 毎時: 状態.md を作り直し（winnote の S21 bot の heartbeat・ファイルの照合・判断のスプレッドを見て、止まっていれば要対応.md に ★）、
#   要対応.md に新しく足された ★／自動の節を Mac の通知に出す（2026-11-05・提案）。heartbeat は lab-ops の pc_runner（5 分ごと）の git pull で届く。
# 入れ方（taichi の承認の後）: cp _設定案/com.taichi.bot-watch.plist ~/Library/LaunchAgents/ && launchctl load ~/Library/LaunchAgents/com.taichi.bot-watch.plist
# やめ方: launchctl unload ~/Library/LaunchAgents/com.taichi.bot-watch.plist（plist は残してよい）
DIR=${0:A:h}
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
print -r -- "$(date '+%m-%d %H:%M') bot_watch"
# スリープから起きて 15 分以内は飛ばす（heartbeat の git pull が間に合わず「届いていない」と誤報するため）
wake=$(sysctl -n kern.waketime 2>/dev/null | sed -E 's/.*sec = ([0-9]+).*/\1/'); now=$(date +%s)
if [[ "$wake" == <-> ]] && (( wake > 0 && now - wake < 900 )); then print -r -- "  起きて $(( (now - wake) / 60 )) 分。この回は飛ばす"; exit 0; fi
python3 "$DIR/make_状態.py" >/dev/null 2>&1 || print -r -- "  make_状態.py が失敗"
python3 "$DIR/notify_star.py"
