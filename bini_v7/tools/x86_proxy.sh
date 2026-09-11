#!/bin/bash
# Real-clock proxy on the x86 box: our engine (candidate dir) through the real wrapper at
# 120 s + 0.5 s against Stockfish at <nodes> nodes with the 4%-of-clock habit; two processes of
# <games>/2 games each; generators and book workers paused meanwhile. Run FROM THE MAC:
#   bash tools/x86_proxy.sh <candidate dir name> <games> <nodes> <tag>
set -uo pipefail
cd "$(dirname "$0")/.."
BOX=${BOX:-$(ssh -o BatchMode=yes -o ConnectTimeout=5 gcp-x86b true 2>/dev/null && echo gcp-x86b || echo gcp-x86)}
CAND=$1; GAMES=$2; NODES=$3; TAG=$4; HALF=$((GAMES/2))
rsync -a --exclude __pycache__ --exclude tests/arena "../$CAND/" "$BOX:chess/$CAND/"
ssh -o BatchMode=yes $BOX "bash -s" <<REMOTE
cd ~/chess; mkdir -p gates
pkill -STOP -f "selfplay_sf.py --out" || true; pkill -STOP -f make_book.py || true
for p in \$(pgrep -x stockfish); do kill -STOP \$p; done
cd $CAND
( BINI_TT_BITS=24 nice -n 5 ../aichessathon-starter/.venv/bin/python tools/proxy_match.py --games $HALF --nodes $NODES --start 0 --stockfish ~/chess/Stockfish/src/stockfish > ../gates/${TAG}_a.log 2>&1 ) &
( BINI_TT_BITS=24 nice -n 5 ../aichessathon-starter/.venv/bin/python tools/proxy_match.py --games $HALF --nodes $NODES --start $HALF --stockfish ~/chess/Stockfish/src/stockfish > ../gates/${TAG}_b.log 2>&1 ) &
wait
pkill -CONT -f "selfplay_sf.py --out" || true; pkill -CONT -f make_book.py || true
for p in \$(pgrep -x stockfish); do kill -CONT \$p; done
grep "PROXY MATCH" ../gates/${TAG}_a.log ../gates/${TAG}_b.log
REMOTE
