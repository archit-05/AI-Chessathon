#!/bin/bash
# Grade one exported net on the VM: copy it there, run the net diagnostic (held-out site chunk,
# label scale 0.85) and the 300-position grader at 1.5 s, both under the dev-copy engine.
#   bash tools/grade_export.sh ../data/nnue_v4a.safetensors v4a_e0
set -euo pipefail
cd "$(dirname "$0")/.."
net=$1; tag=$2
rsync -az "$net" priorcrypto-vm:~/chess/nets/$tag.safetensors
ssh -o BatchMode=yes priorcrypto-vm "cd ~/chess/bini_v4cache && export BINI_NNUE=~/chess/nets/$tag.safetensors && nice -n 5 ~/chess/venv/bin/python tools/net_diag.py ~/chess/data/site_labelled/chunk_0001.npz --scale 0.85 > ~/chess/nets/$tag.diag.txt 2>&1 && nice -n 5 ~/chess/venv/bin/python tools/grade.py --n 300 --ms 1500 --stockfish ~/chess/Stockfish/src/stockfish --tag $tag > ~/chess/nets/$tag.grade.txt 2>&1; grep -E 'positions:' ~/chess/nets/$tag.diag.txt; grep -A9 '^by piece' ~/chess/nets/$tag.diag.txt | grep -E '9-12|17-20|29-32'; grep GRADE ~/chess/nets/$tag.grade.txt" < /dev/null
