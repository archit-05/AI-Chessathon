#!/bin/bash
# pod: draw-shape screen of contempt 40 vs 20 with the SAME engine and net (V8.5 + fc_b), 30k nodes, 576 games.
# Fixed nodes: strength is an upper bound, but the W/D/L shape is what this measures. Runs after any other node_gate.
set -u; cd ~/chess; S=~/chess/logs/screen_queue.status; V=~/chess/venv/bin/python; E=~/chess/bini_astra_v5_noc2b; NG=~/chess/bini_v65/tools/node_gate.py; O=~/chess/bini_v65/tools/curated.epd
while ps -eo args | grep -q "[n]ode_gate.py --engine"; do sleep 30; done
$V $NG --engine $E --a "BINI_CONTEMPT=40" --b "BINI_CONTEMPT=20" --openings $O --games 576 --nodes 30000 --workers 4 --tt-bits 22 --out ~/chess/gates/c40_30k > ~/chess/gates/c40_30k.stdout 2>&1
echo "$(date '+%F %T') SHAPE contempt40 vs contempt20 (same net, 30k): $(grep -E '^\S+ \[' ~/chess/gates/c40_30k.log | tail -1)" >> $S
rsync -az -e "ssh -o StrictHostKeyChecking=no" ~/chess/gates/ forge@8.228.62.35:~/chess/data/stage/nets_night/ 2>/dev/null
