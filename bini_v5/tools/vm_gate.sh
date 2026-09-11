#!/bin/bash
# Run a gate on the VM (default 10 s + 0.1 s; pass base_ms inc_ms as args 5-6) (generators paused with SIGSTOP, resumed after), 4 workers.
#   bash tools/vm_gate.sh <candidate dir name under ~/chess> <baseline dir name> <games> <tag> [env assignments...]
# Logs to ~/chess/gates/<tag>.log on the VM and mirrors the tally locally in ../data/gate_<tag>.log.
set -uo pipefail
cd "$(dirname "$0")/.."
CAND=$1; BASE=$2; GAMES=$3; TAG=$4; BASEMS=${5:-10000}; INCMS=${6:-100}; shift 6 2>/dev/null || shift $#; ENVS="$*"
rsync -a --exclude __pycache__ --exclude tests/arena "../$CAND/" "priorcrypto-vm:chess/$CAND/"
ssh -o BatchMode=yes priorcrypto-vm "bash -s" <<REMOTE
cd ~/chess
pkill -STOP -f "selfplay_sf.py --out" || true; pkill -STOP -x stockfish || true
cd bini_v4final && env $ENVS BINI_TT_BITS=22 nice -n 5 ../aichessathon-starter/.venv/bin/python tools/arena_par.py --agent ../$CAND --opponent ../$BASE --games $GAMES --workers 4 --base-ms $BASEMS --inc-ms $INCMS --openings tools/curated.epd > ../gates/$TAG.log 2>&1
pkill -CONT -f "selfplay_sf.py --out" || true; pkill -CONT -x stockfish || true
grep -E "^\[" ../gates/$TAG.log | tail -1
REMOTE
scp -q "priorcrypto-vm:chess/gates/$TAG.log" "../data/gate_$TAG.log"
echo "$(date '+%F %T') gate $TAG: $(grep -E '^\[' ../data/gate_$TAG.log | tail -1)"
