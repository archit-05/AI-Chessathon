#!/bin/bash
# Draw-policy gates on the x86 box (V5 Plan 17:05): (a) 10 real-clock pressure games vs full-strength
# Stockfish (1.5M nodes) with the rule on and off, in parallel: draws must rise with it on;
# (b) 100 games at 10 s vs Stockfish at UCI_Elo 2000 with the rule on and off: the draw rate must
# not rise. Generators and book paused meanwhile. Run FROM THE MAC: bash tools/draw_gate.sh
set -uo pipefail
cd "$(dirname "$0")/.."
BOX=${BOX:-$(ssh -o BatchMode=yes -o ConnectTimeout=5 gcp-x86b true 2>/dev/null && echo gcp-x86b || echo gcp-x86)}
rsync -a --exclude __pycache__ --exclude tests/arena ./ $BOX:chess/bini_v5/
ssh -o BatchMode=yes $BOX "bash -s" <<'REMOTE'
cd ~/chess; mkdir -p gates
pkill -STOP -f make_book.py || true  # generators keep running: the box has 8 cores, these gates use 5
P=../aichessathon-starter/.venv/bin/python
cd ~/chess/bini_v5
( BINI_DRAW_BEHIND=1 BINI_CORR=0 BINI_CONT=0 BINI_SEEP=1 BINI_TT_BITS=24 nice -n 5 $P tests/pressure_games.py tests/pos/sharp.epd --games 10 --sf-nodes 1500000 > ../gates/draw_on_pressure.log 2>&1 ) &
( BINI_DRAW_BEHIND=0 BINI_CORR=0 BINI_CONT=0 BINI_SEEP=1 BINI_TT_BITS=24 nice -n 5 $P tests/pressure_games.py tests/pos/sharp.epd --games 10 --sf-nodes 1500000 > ../gates/draw_off_pressure.log 2>&1 ) &
( cd ~/chess/bini_v4final && SF_ELO=2000 BINI_DRAW_BEHIND=1 BINI_CORR=0 BINI_CONT=0 BINI_SEEP=1 BINI_TT_BITS=22 nice -n 5 $P tools/arena_par.py --agent ../bini_v5 --opponent ../sparring/sf --games 100 --workers 3 --base-ms 10000 --inc-ms 100 --openings tools/curated.epd > ../gates/draw_on_sf2000.log 2>&1; SF_ELO=2000 BINI_DRAW_BEHIND=0 BINI_CORR=0 BINI_CONT=0 BINI_SEEP=1 BINI_TT_BITS=22 nice -n 5 $P tools/arena_par.py --agent ../bini_v5 --opponent ../sparring/sf --games 100 --workers 3 --base-ms 10000 --inc-ms 100 --openings tools/curated.epd --seed 2 > ../gates/draw_off_sf2000.log 2>&1 ) &
wait
pkill -CONT -f make_book.py || true
for t in draw_on_pressure draw_off_pressure; do echo "$t: $(grep -E 'RESULT|min clock|score' ../gates/$t.log | tail -2 | tr '\n' ' ')"; done
for t in draw_on_sf2000 draw_off_sf2000; do echo "$t: $(grep -E '^\[' ../gates/$t.log | tail -1) | $(grep terminations ../gates/$t.log)"; done
REMOTE
echo "DRAW GATES DONE"
