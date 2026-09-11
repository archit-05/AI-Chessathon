#!/bin/bash
# When v4b2 (new architecture + mild mix) is trained: if the v4o2 gate is clearly negative by
# 80 games (< 42%), stop it and gate v4b2 in its place; otherwise wait for v4o2 to finish first.
cd "$(dirname "$0")/.."
PY=../aichessathon-starter/.venv/bin/python
until grep -q "run_v4b2 done" ../data/ablations.log 2>/dev/null; do sleep 60; done
rm -rf ../bini_v4b2 && rsync -a --exclude __pycache__ --exclude tests/arena ../bini_v4/ ../bini_v4b2/ && cp ../data/nnue_v4b2.safetensors ../bini_v4b2/nnue.safetensors
BINI_NNUE=../bini_v4b2/nnue.safetensors $PY tests/test_nnue.py 2>&1 | grep "== reference"
f=../bini/tests/arena/v4o2_vs_v3.log
while true; do
  line=$(grep '^\[' $f 2>/dev/null | tail -1)
  n=$(echo "$line" | sed -E 's/^\[([0-9]+)\/300\].*/\1/')
  sc=$(echo "$line" | sed -E 's/.*score ([0-9.]+)%.*/\1/')
  if grep -q terminations $f 2>/dev/null; then echo "$(date '+%F %T') v4o2 gate finished: $line"; break; fi
  if [ "${n:-0}" -ge 80 ] && [ "$($PY -c "print(1 if float('${sc:-50}') < 42 else 0)")" = "1" ]; then echo "$(date '+%F %T') v4o2 clearly negative at $line; stopping it"; bash tools/stop_gate.sh ../bini_v4o2; sleep 5; break; fi
  sleep 120
done
echo "$(date '+%F %T') gate v4b2 vs V3 (two workers)"
BINI_TT_BITS=22 bash tools/gate.sh ../bini_v4b2 ../bini_v3b 300 10000 100 2 v4b2_vs_v3
echo "$(date '+%F %T') v4b2 gate done"
