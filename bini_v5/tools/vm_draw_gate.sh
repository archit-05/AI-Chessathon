#!/bin/bash
# Draw-policy gate part (b) on the VM: 100 games at 10 s vs Stockfish at UCI_Elo 2000 with the rule
# on, then off (V5 engine, CORR/CONT/SEEP off so only the rule differs); the draw rate must not rise.
set -uo pipefail
cd "$(dirname "$0")/.."
rsync -a --exclude __pycache__ --exclude tests/arena ./ priorcrypto-vm:chess/bini_v5/
ssh -o BatchMode=yes priorcrypto-vm "bash -s" <<'REMOTE'
cd ~/chess; mkdir -p gates
[ -x ~/.local/bin/stockfish ] || { mkdir -p ~/.local/bin; ln -sf ~/chess/Stockfish/src/stockfish ~/.local/bin/stockfish; }
export PATH=$HOME/.local/bin:$PATH
pkill -STOP -f "selfplay_sf.py --out" || true; pkill -STOP -x stockfish || true
P=../aichessathon-starter/.venv/bin/python
cd ~/chess/bini_v4final
for on in 1 0; do
  SF_ELO=2000 BINI_DRAW_BEHIND=$on BINI_CORR=0 BINI_CONT=0 BINI_SEEP=0 BINI_TT_BITS=22 nice -n 5 $P tools/arena_par.py --agent ../bini_v5 --opponent ../sparring/sf --games 100 --workers 4 --base-ms 10000 --inc-ms 100 --openings tools/curated.epd --seed $((on+3)) > ../gates/draw_${on}_sf2000.log 2>&1
  echo "draw rule $on vs SF2000: $(grep -E '^\[' ../gates/draw_${on}_sf2000.log | tail -1) | $(grep terminations ../gates/draw_${on}_sf2000.log)"
done
for p in $(pgrep -f "selfplay_sf.py --out"); do kill -CONT $p; done; for p in $(pgrep -x stockfish); do kill -CONT $p; done
REMOTE
echo "VM DRAW GATE DONE"
