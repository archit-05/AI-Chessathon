#!/bin/bash
# v4c: from scratch on the full mix (the tournament distribution present from epoch zero).
#   Lichess quiet + every self-play stream + site_all + hard set + Elite; 4 epochs.
# Run from bini_v4/ Tuesday night:  nohup bash tools/run_v4c.sh > ../data/train_v4c.log &
set -euo pipefail
cd "$(dirname "$0")/.."
PY=../aichessathon-starter/.venv/bin/python
SCALE_SF19=${SCALE_SF19:-0.85}
EPOCHS=${EPOCHS:-4}
HIDDEN=${HIDDEN:-512}
BUCKETS=${BUCKETS:-8}
OUT=${OUT:-../data/nnue_v4c.safetensors}
VAL_SP=$(ls ../data/selfplay/chunk_w0_*.npz | head -1)
exec $PY tools/train_nnue.py \
  --data ../data/lichessq3 ../data/selfplay ../data/site_all ../data/elite_labelled ../data/hard \
  --quiet-only \
  --oversample ../data/selfplay:2 --oversample ../data/site_all:12 --oversample ../data/hard:20 \
  --scale ../data/selfplay:$SCALE_SF19 --scale ../data/elite_labelled:$SCALE_SF19 --scale ../data/site_all:$SCALE_SF19 --scale ../data/site_labelled:$SCALE_SF19 --scale ../data/hard:$SCALE_SF19 \
  --val ../data/site_labelled/chunk_0001.npz --val ../data/site_all/chunk_0001.npz --val "$VAL_SP" --val ../data/lichessq3/chunk_0036.npz \
  --buckets $BUCKETS --hidden $HIDDEN --act screlu --out-buckets 8 --factorise \
  --epochs $EPOCHS --batch 16384 --lr 2e-3 --wdl 0.85 --pc-weight 0.5 --val-n ${VAL_N:-50000} \
  --out $OUT
