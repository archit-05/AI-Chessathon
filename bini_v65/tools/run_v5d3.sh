#!/bin/bash
# V5 run D3 (diagnostic, 19:35): v3b's exact recipe with the current trainer, one fully annealed
# pass: resume v3b, all quiet Lichess + elite whole-game x10, labels UNSCALED (as v3b was trained),
# lr 3e-4. If this holds 50% in games the trainer is sound; if not, the old trainer comes back.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=../aichessathon-starter/.venv/bin/python
EPOCHS=${EPOCHS:-1}; LR=${LR:-3e-4}; OUT=${OUT:-../data/nnue_v5d3.safetensors}; RESUME=${RESUME:-../data/nnue_v3b.pt}
exec $PY tools/train_nnue.py \
  --data ../data/lichessq ../data/lichessq2 ../data/lichessq3 ../data/elite_labelled \
  --quiet-only --oversample ../data/elite_labelled:10 \
  --val ../data/site_labelled/chunk_0001.npz --val ../data/elite_labelled/chunk_0006.npz --val ../data/lichessq3/chunk_0036.npz \
  --buckets 8 --hidden 512 --act crelu --out-buckets 1 \
  --resume "$RESUME" --epochs $EPOCHS --batch 16384 --lr $LR --wdl 1.0 --pc-weight 0.0 --val-n ${VAL_N:-20000} \
  --out $OUT
