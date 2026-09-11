#!/bin/bash
# v4o3: the gentle recipe. v3b (old architecture) nudged, not overwritten: the full quiet Lichess
# set stays in the mix, self-play thinned (keep 30% of positions with |cp| < 25), site x4, hard
# x10, no result blend, no piece weight, lr 2e-4, one epoch.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=../aichessathon-starter/.venv/bin/python
SCALE_SF19=${SCALE_SF19:-0.85}
OUT=${OUT:-../data/nnue_v4o3.safetensors}
VAL_SP=$(ls ../data/selfplay/chunk_w0_*.npz | head -1)
exec $PY tools/train_nnue.py \
  --data ../data/lichessq ../data/lichessq2 ../data/lichessq3 ../data/selfplay ../data/site_all ../data/elite_labelled ../data/hard \
  --quiet-only \
  --thin-flat ../data/selfplay:0.3:25 \
  --oversample ../data/site_all:4 --oversample ../data/hard:10 \
  --scale ../data/selfplay:$SCALE_SF19 --scale ../data/elite_labelled:$SCALE_SF19 --scale ../data/site_all:$SCALE_SF19 --scale ../data/site_labelled:$SCALE_SF19 --scale ../data/hard:$SCALE_SF19 \
  --val ../data/site_labelled/chunk_0001.npz --val ../data/site_all/chunk_0001.npz --val "$VAL_SP" --val ../data/lichessq3/chunk_0036.npz \
  --buckets 8 --hidden 512 --act crelu --out-buckets 1 \
  --resume ../data/nnue_v3b.pt --epochs 1 --batch 16384 --lr 2e-4 --wdl 1.0 --pc-weight 0.0 --val-n ${VAL_N:-50000} \
  --out $OUT
