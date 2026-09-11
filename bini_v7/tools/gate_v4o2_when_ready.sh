#!/bin/bash
# When v4o2 (old architecture + mild mix) finishes: stop the v4o gate (its verdict is clear by
# then), build the v4o2 candidate, verify exactness, gate it against V3 at two workers.
cd "$(dirname "$0")/.."
PY=../aichessathon-starter/.venv/bin/python
until grep -q "run_v4o2 done" ../data/ablations.log 2>/dev/null; do sleep 60; done
echo "$(date '+%F %T') v4o2 trained; stopping the v4o gate at: $(grep '^\[' ../bini/tests/arena/v4o_vs_v3.log | tail -1 | cut -c1-60)"
bash tools/stop_gate.sh ../bini_v4o
rm -rf ../bini_v4o2 && rsync -a --exclude __pycache__ --exclude tests/arena ../bini_v4/ ../bini_v4o2/ && cp ../data/nnue_v4o2.safetensors ../bini_v4o2/nnue.safetensors
BINI_NNUE=../bini_v4o2/nnue.safetensors $PY tests/test_nnue.py 2>&1 | grep "== reference"
echo "$(date '+%F %T') gate v4o2 vs V3 (two workers)"
BINI_TT_BITS=22 bash tools/gate.sh ../bini_v4o2 ../bini_v3b 300 10000 100 2 v4o2_vs_v3
echo "$(date '+%F %T') v4o2 gate done"
