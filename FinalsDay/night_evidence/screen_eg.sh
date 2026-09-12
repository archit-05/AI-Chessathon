#!/bin/bash
# pod: endgame-draw-knowledge screen. Same build both sides; BINI_EG_DRAW=1 (new) vs 0 (old behaviour). 30k nodes, 576 games.
set -u; cd ~/chess; S=~/chess/logs/screen_queue.status; V=~/chess/venv/bin/python; E=~/chess/cand_sfbook_eg; NG=~/chess/bini_v65/tools/node_gate.py; O=~/chess/bini_v65/tools/curated.epd
while ps -eo args | grep -q "[n]ode_gate.py --engine"; do sleep 30; done
$V $NG --engine $E --a "BINI_EG_DRAW=1" --b "BINI_EG_DRAW=0" --openings $O --games 576 --nodes 30000 --workers 4 --tt-bits 22 --out ~/chess/gates/eg_30k > ~/chess/gates/eg_30k.stdout 2>&1
echo "$(date '+%F %T') SHAPE eg_draw=1 vs eg_draw=0 (same net, 30k): $(grep -E '^\S+ \[' ~/chess/gates/eg_30k.log | tail -1)" >> $S
rsync -az -e "ssh -o StrictHostKeyChecking=no" ~/chess/gates/ forge@8.228.62.35:~/chess/data/stage/nets_night/ 2>/dev/null
