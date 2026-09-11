#!/bin/bash
# Draw-policy gate part (a) on an x86 box: 10 real-clock games vs full-strength Stockfish (1.5M
# nodes) with the rule on and off in parallel (2 cores); draws must rise with the rule on.
set -uo pipefail
cd "$(dirname "$0")/.."
BOX=${BOX:-gcp-x86b}
rsync -a --exclude __pycache__ --exclude tests/arena ./ $BOX:chess/bini_v5/
ssh -o BatchMode=yes $BOX "bash -s" <<'REMOTE'
cd ~/chess/bini_v5; mkdir -p ../gates
P=../aichessathon-starter/.venv/bin/python
( BINI_DRAW_BEHIND=1 BINI_CORR=0 BINI_CONT=0 BINI_SEEP=0 BINI_TT_BITS=24 nice -n 5 $P tests/pressure_games.py tests/pos/sharp.epd --games 10 --sf-nodes 1500000 > ../gates/draw_on_pressure.log 2>&1 ) &
( BINI_DRAW_BEHIND=0 BINI_CORR=0 BINI_CONT=0 BINI_SEEP=0 BINI_TT_BITS=24 nice -n 5 $P tests/pressure_games.py tests/pos/sharp.epd --games 10 --sf-nodes 1500000 > ../gates/draw_off_pressure.log 2>&1 ) &
wait
for t in draw_on_pressure draw_off_pressure; do echo "$t: $(grep -E 'results|min clock' ../gates/$t.log | tail -1)"; done
REMOTE
echo "PRESSURE GATE DONE"
