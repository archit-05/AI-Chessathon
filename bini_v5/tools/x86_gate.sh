#!/bin/bash
# Fast gate on the x86 box: pause generators and book workers, play <games> at <base>+<inc> ms with
# 8 workers on the curated openings, resume. Run FROM THE MAC:
#   bash tools/x86_gate.sh <candidate dir name> <baseline dir name> <games> <tag> [base_ms inc_ms] [ENV=..]
set -uo pipefail
cd "$(dirname "$0")/.."
BOX=${BOX:-$(ssh -o BatchMode=yes -o ConnectTimeout=5 gcp-x86b true 2>/dev/null && echo gcp-x86b || echo gcp-x86)}
CAND=$1; BASE=$2; GAMES=$3; TAG=$4; BASEMS=${5:-5000}; INCMS=${6:-50}; shift 6 2>/dev/null || shift $#; ENVS="$*"
rsync -a --exclude __pycache__ --exclude tests/arena "../$CAND/" "$BOX:chess/$CAND/"
rsync -a --exclude __pycache__ --exclude tests/arena "../$BASE/" "$BOX:chess/$BASE/"
ssh -o BatchMode=yes $BOX "bash -s" <<REMOTE
cd ~/chess; mkdir -p gates
# one gate at a time per box: wait for any running arena to finish
while pgrep -f "arena_par.py" > /dev/null; do sleep 30; done
pkill -STOP -f "selfplay_sf.py --out" || true; pkill -STOP -x stockfish || true; pkill -STOP -f make_book.py || true
cd bini_v4final && env $ENVS BINI_TT_BITS=22 nice -n 5 ../aichessathon-starter/.venv/bin/python tools/arena_par.py --agent ../$CAND --opponent ../$BASE --games $GAMES --workers 8 --base-ms $BASEMS --inc-ms $INCMS --openings tools/curated.epd > ../gates/$TAG.log 2>&1
pkill -CONT -f "selfplay_sf.py --out" || true; pkill -CONT -x stockfish || true; pkill -CONT -f make_book.py || true
grep -E "^\[" ../gates/$TAG.log | tail -1
REMOTE
scp -q "$BOX:chess/gates/$TAG.log" "../data/gate_$TAG.log"
echo "$(date '+%F %T') gate $TAG: $(grep -E '^\[' ../data/gate_$TAG.log | tail -1)"
