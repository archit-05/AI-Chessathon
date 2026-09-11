#!/bin/bash
# Gate the gentle-recipe net v4o3 against V3 as soon as its training finishes (two workers).
cd "$(dirname "$0")/.."
PY=../aichessathon-starter/.venv/bin/python
until grep -q "v4o3 done" ../data/after_ablations.log 2>/dev/null; do sleep 60; done
rm -rf ../bini_v4o3 && rsync -a --exclude __pycache__ --exclude tests/arena ../bini_v4/ ../bini_v4o3/ && cp ../data/nnue_v4o3.safetensors ../bini_v4o3/nnue.safetensors
BINI_NNUE=../bini_v4o3/nnue.safetensors $PY tests/test_nnue.py 2>&1 | grep "== reference"
while true; do l=$(uptime | sed 's/.*load averages*: *//' | cut -d' ' -f1 | tr -d ','); ok=$($PY -c "print(1 if float('$l') <= 12 else 0)"); [ "$ok" = "1" ] && break; sleep 120; done
echo "$(date '+%F %T') gate v4o3 vs V3 (two workers)"
BINI_TT_BITS=22 bash tools/gate.sh ../bini_v4o3 ../bini_v3b 300 10000 100 2 v4o3_vs_v3
echo "$(date '+%F %T') v4o3 gate done"
