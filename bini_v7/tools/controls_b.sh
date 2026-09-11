#!/bin/bash
# Two controls on box B (Archit, 19:45): (a) v3b.pt re-exported through the current export path,
# no training, vs the original v3b file; (b) v3b vs itself. 40 games each at 5 s, 4 workers each,
# in parallel, generators paused.
set -uo pipefail
cd "$(dirname "$0")/.."
ssh -o BatchMode=yes gcp-x86b "bash -s" <<'REMOTE'
cd ~/chess
pkill -STOP -f "selfplay_sf.py --out" || true; pkill -STOP -x stockfish || true
P=../aichessathon-starter/.venv/bin/python
cd ~/chess/bini_v5
~/chess/venv/bin/python tools/export_from_pt.py ~/chess/data/nnue_v3b.pt ~/chess/data/nnue_v3b_reexport.safetensors --buckets 8 --hidden 512 --act crelu --out-buckets 1 --out-scale 1.0 2>&1 | tail -1
rm -rf ~/chess/bini_ctrl_reexport ~/chess/bini_ctrl_v3b
rsync -a --exclude __pycache__ --exclude tests/arena ~/chess/bini_v4final/ ~/chess/bini_ctrl_reexport/ && cp ~/chess/data/nnue_v3b_reexport.safetensors ~/chess/bini_ctrl_reexport/nnue.safetensors
rsync -a --exclude __pycache__ --exclude tests/arena ~/chess/bini_v4final/ ~/chess/bini_ctrl_v3b/
cmp ~/chess/bini_ctrl_v3b/nnue.safetensors ~/chess/bini_v4final/nnue.safetensors && echo "control b: identical files"
cd ~/chess/bini_v4final
( BINI_TT_BITS=22 nice -n 5 $P tools/arena_par.py --agent ../bini_ctrl_reexport --opponent ../bini_v4final --games 40 --workers 4 --base-ms 5000 --inc-ms 50 --openings tools/curated.epd > ../gates/ctrl_reexport.log 2>&1 ) &
( BINI_TT_BITS=22 nice -n 5 $P tools/arena_par.py --agent ../bini_ctrl_v3b --opponent ../bini_v4final --games 40 --workers 4 --base-ms 5000 --inc-ms 50 --openings tools/curated.epd --seed 7 > ../gates/ctrl_self.log 2>&1 ) &
wait
pkill -CONT -f "selfplay_sf.py --out" || true; pkill -CONT -x stockfish || true
echo "control a (re-export vs v3b): $(grep -E '^\[' ../gates/ctrl_reexport.log | tail -1)"
echo "control b (v3b vs v3b):       $(grep -E '^\[' ../gates/ctrl_self.log | tail -1)"
REMOTE
echo "CONTROLS DONE"
