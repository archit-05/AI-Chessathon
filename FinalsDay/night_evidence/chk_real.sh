#!/bin/bash
# CHK candidate dir vs exact V8.5 dir through the REAL wrapper at the REAL clock 120+0.5.
# BINI_JOIN_S=300 only because this harness compiles many agents at once (see mgb_gate.sh).
set -u; cd ~/chess; export BINI_JOIN_S=300; unset BINI_CHK_EXEMPT
V=~/chess/venv/bin/python; L=~/chess/gates/chk_real.log
nohup $V bini_cand_chk/tools/arena_par.py --agent ~/chess/bini_cand_chk --opponent ~/chess/bini_astra_v5_noc2b \
  --games ${1:-400} --base-ms 120000 --inc-ms 500 --workers ${2:-6} --openings bini_cand_chk/tools/curated.epd --pgn-out ~/chess/gates/chk_real.pgn > "$L" 2>&1 &
echo started chk_real
