#!/bin/zsh
# 配置の試験: zip を作って別の場所に展開し、本番と同じ並び（bot/検証/トレード/執行/S23）で --once（dry・偽 MT5・Binance は本物から読むだけ）が動くか
set -e
HERE=${0:A:h}; S23=${HERE:h}; V=$HOME/ワークスペース/検証; PY=$HOME/ワークスペース/作業層/大容量/venv_forward/bin/python
T=$(mktemp -d); WS=$T/ws; BOT=$T/bot
for f in トレード/forward/common.py トレード/forward/S23/forward_s23.py verification-lab/financial-engineering/s23-crypto-uptrend-long-q529/run_q529.py \
         verification-lab/financial-engineering/s22-crypto-ml-fintokei-q528/crypto_core.py verification-lab/tools/mt5/mt5_fetch.py; do
  mkdir -p $WS/検証/${f:h}; cp $V/$f $WS/検証/$f; done
mkdir -p $WS/検証/トレード/執行/S23; cp $S23/*.py $S23/README.md $WS/検証/トレード/執行/S23/ 2>/dev/null || cp $S23/*.py $WS/検証/トレード/執行/S23/
$PY -B $S23/deploy_s23.py --ws $WS --out $T/S23_bot.zip | tail -2
mkdir -p $BOT && (cd $BOT && unzip -q $T/S23_bot.zip)
H=$(mktemp -d); cp $HOME/ワークスペース/作業層/大容量/market_data_forward/crypto_h1/*.parquet $H/
cd $BOT/検証/トレード/執行/S23
env -u S23_FORWARD_DIR PYTHONPATH=$HERE/mock MOCK_H1=$H MOCK_NOW="$(date -u '+%Y-%m-%d %H:%M:00+00:00')" $PY -B execute_s23_mt5.py --once 2>&1 | grep -v "^ \|^{\|^}" | head -20
test -f config.json && echo "config.json を書いた" && test -d 足 && echo "足/ に Binance の足を置いた（記録のデータには書かない）" && ls 足
test ! -e 台帳/trades.csv && echo "dry なので台帳は書かない"
rm -rf $T $H
