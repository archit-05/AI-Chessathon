#!/bin/bash
# v4a: the new architecture trained from scratch on the data that already exists.
#   squared clipped ReLU, 8 output buckets by piece count, factorised king buckets, 512 hidden;
#   quiet Lichess (155M) + Elite whole-game (1M, SF19 d10, scaled) + site-labelled x10.
# Run from bini_v4/ on the Mac once the machine is free:  nohup bash tools/run_v4a.sh &
# SCALE_SF19 comes from tools/scale_fit.py (Lichess classical cp ~ k * SF19 normalised cp).
set -euo pipefail
cd "$(dirname "$0")/.."
PY=../aichessathon-starter/.venv/bin/python
SCALE_SF19=${SCALE_SF19:-0.85}   # tools/scale_fit.py: lichess_cp ~ 0.86 * sf19_cp (median 0.80), SF16 site labels share the scale
EPOCHS=${EPOCHS:-8}
HIDDEN=${HIDDEN:-512}
OUT=${OUT:-../data/nnue_v4a.safetensors}
exec $PY tools/train_nnue.py \
  --data ../data/lichessq ../data/lichessq2 ../data/lichessq3 ../data/elite_labelled ../data/site_labelled \
  --quiet-only \
  --oversample ../data/site_labelled:10 \
  --scale ../data/elite_labelled:$SCALE_SF19 --scale ../data/site_labelled:$SCALE_SF19 \
  --val ../data/site_labelled/chunk_0001.npz --val ../data/lichessq3/chunk_0036.npz \
  --buckets 8 --hidden $HIDDEN --act screlu --out-buckets 8 --factorise \
  --epochs $EPOCHS --batch 16384 --lr 2e-3 --wdl 0.85 --pc-weight 0.5 --val-n ${VAL_N:-50000} \
  --out $OUT
