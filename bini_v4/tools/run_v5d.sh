#!/bin/bash
# V5 run D (Tue 8 Sept 18:30): the recipe that has actually won games this week, scaled up.
# v3b resumed and fine-tuned at a low rate on all quiet Lichess + the elite whole-game set x10
# (SF19 depth 10, the data behind v3b's +39) + the resolved endgame streams x2 (the measured hole)
# + the hard set x10. No site set, no self-play, no result blend. Checkpointed by games every epoch.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=../aichessathon-starter/.venv/bin/python
SCALE=${SCALE:-0.85}
EPOCHS=${EPOCHS:-2}
LR=${LR:-5e-4}
OUT=${OUT:-../data/nnue_v5d.safetensors}
RESUME=${RESUME:-../data/nnue_v3b.pt}
exec $PY tools/train_nnue.py \
  --data ../data/lichessq ../data/lichessq2 ../data/lichessq3 ../data/elite_labelled ../data/selfplay/eg2 ../data/selfplay/eg3 ../data/hard \
  --quiet-only \
  --oversample ../data/elite_labelled:10 --oversample ../data/selfplay/eg2:2 --oversample ../data/selfplay/eg3:2 --oversample ../data/hard:10 \
  --scale ../data/elite_labelled:$SCALE --scale ../data/selfplay:$SCALE --scale ../data/site_labelled:$SCALE --scale ../data/hard:$SCALE \
  --val ../data/site_labelled/chunk_0001.npz --val ../data/elite_labelled/chunk_0006.npz --val ../data/lichessq3/chunk_0036.npz \
  --buckets 8 --hidden 512 --act crelu --out-buckets 1 \
  --resume "$RESUME" --epochs $EPOCHS --batch 16384 --lr $LR --wdl 1.0 --pc-weight 0.0 --val-n ${VAL_N:-20000} \
  --out $OUT
