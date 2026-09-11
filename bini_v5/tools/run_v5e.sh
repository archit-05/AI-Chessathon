#!/bin/bash
# V5 run E: v3b's recipe scaled up: resume v3b, all quiet Lichess + ALL elite whole-game chunks
# (the original 1.05M plus the 3M labelled tonight, copied into data/elite_labelled as chunk_1xxx)
# x6, labels unscaled, one annealed pass at 3e-4 (current trainer). Judged by 200 games.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=../aichessathon-starter/.venv/bin/python
EPOCHS=${EPOCHS:-1}; LR=${LR:-3e-4}; OUT=${OUT:-../data/nnue_v5e.safetensors}; RESUME=${RESUME:-../data/nnue_v3b.pt}; K=${K:-6}
exec $PY tools/train_nnue.py \
  --data ../data/lichessq ../data/lichessq2 ../data/lichessq3 ../data/elite_labelled \
  --quiet-only --oversample ../data/elite_labelled:$K \
  --val ../data/site_labelled/chunk_0001.npz --val ../data/elite_labelled/chunk_0006.npz --val ../data/lichessq3/chunk_0036.npz \
  --buckets 8 --hidden 512 --act crelu --out-buckets 1 \
  --resume "$RESUME" --epochs $EPOCHS --batch 16384 --lr $LR --wdl 1.0 --pc-weight 0.0 --val-n ${VAL_N:-20000} \
  --out $OUT
