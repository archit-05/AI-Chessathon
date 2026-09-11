#!/bin/bash
# v4d: the final-net recipe. From scratch, 20 epochs with the one-cycle decaying schedule, on the
# tournament-weighted mix: site_all (x12, the site's own depth-16 positions, weighted above
# Lichess), every self-play stream (x2, quiet-resolved, results kept), the hard set (x20),
# Elite whole-game, and Lichess capped to 9 chunks (~7M) so it no longer dominates.
# Run from bini_v4/:  nohup bash tools/run_v4d.sh > ../data/train_v4d.log &
set -euo pipefail
cd "$(dirname "$0")/.."
PY=../aichessathon-starter/.venv/bin/python
SCALE_SF19=${SCALE_SF19:-0.85}
EPOCHS=${EPOCHS:-20}
HIDDEN=${HIDDEN:-512}
BUCKETS=${BUCKETS:-8}
LICHESS_CHUNKS=${LICHESS_CHUNKS:-9}
OUT=${OUT:-../data/nnue_v4d.safetensors}
VAL_SP=$(ls ../data/selfplay/chunk_w0_*.npz | head -1)
exec $PY tools/train_nnue.py \
  --data ../data/lichessq3 ../data/selfplay ../data/site_all ../data/elite_labelled ../data/hard \
  --max-chunks ../data/lichessq3:$LICHESS_CHUNKS \
  --quiet-only \
  --oversample ../data/selfplay:2 --oversample ../data/site_all:12 --oversample ../data/hard:20 \
  --scale ../data/selfplay:$SCALE_SF19 --scale ../data/elite_labelled:$SCALE_SF19 --scale ../data/site_all:$SCALE_SF19 --scale ../data/site_labelled:$SCALE_SF19 --scale ../data/hard:$SCALE_SF19 \
  --val ../data/site_labelled/chunk_0001.npz --val ../data/site_all/chunk_0001.npz --val "$VAL_SP" --val ../data/lichessq3/chunk_0036.npz \
  --buckets $BUCKETS --hidden $HIDDEN --act screlu --out-buckets 8 --factorise \
  --epochs $EPOCHS --batch 16384 --lr 2e-3 --wdl 0.85 --pc-weight 0.5 --val-n ${VAL_N:-50000} \
  --out $OUT
