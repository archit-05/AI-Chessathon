#!/bin/bash
# Gate the v4o ablation net against V3 as soon as its fine-tune finishes (two workers).
cd "$(dirname "$0")/.."
PY=../aichessathon-starter/.venv/bin/python
until grep -q "run_v4o done" ../data/ablations.log 2>/dev/null; do sleep 60; done
rm -rf ../bini_v4o && rsync -a --exclude __pycache__ --exclude tests/arena ../bini_v4/ ../bini_v4o/ && cp ../data/nnue_v4o.safetensors ../bini_v4o/nnue.safetensors
BINI_NNUE=../bini_v4o/nnue.safetensors $PY tests/test_nnue.py 2>&1 | grep "== reference"
echo "$(date '+%F %T') gate v4o vs V3 (two workers)"
BINI_TT_BITS=22 bash tools/gate.sh ../bini_v4o ../bini_v3b 300 10000 100 2 v4o_vs_v3
echo "$(date '+%F %T') v4o gate done"
