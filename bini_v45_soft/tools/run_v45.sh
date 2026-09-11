#!/bin/bash
# V4.5 net (PLAN_V4 s23.1 / s24.1): v3b fine-tuned on the fixed mix. The balanced self-play stream
# (70% draws, median |cp| 32) is OUT; in its place the decisive stream (random opening walk +
# score-balanced sampling, data/selfplay/dec) and the resolved endgame stream (eg2). No result
# blend (WDL 1.0), no piece-count weight, site x4, hard x10, quiet Lichess kept so nothing is
# forgotten. OneCycle LR (built into the trainer) decays over the run.
# Run from bini_v4/ on the Mac:  bash tools/run_v45.sh
set -euo pipefail
cd "$(dirname "$0")/.."
PY=../aichessathon-starter/.venv/bin/python
RESUME=${RESUME:-../data/nnue_v3b.pt}
SCALE_SF19=${SCALE_SF19:-0.85}
EPOCHS=${EPOCHS:-8}
LR=${LR:-5e-4}
OUT=${OUT:-../data/nnue_v45.safetensors}
VAL_DEC=$(ls ../data/selfplay/dec/chunk_w50_*.npz | head -1)   # first decisive chunk of worker 50 is held out
exec $PY tools/train_nnue.py \
  --data ../data/selfplay/dec ../data/selfplay/eg2 ../data/site_all ../data/elite_labelled ../data/hard ../data/lichessq3 \
  --quiet-only \
  --oversample ../data/site_all:4 --oversample ../data/hard:10 --oversample ../data/selfplay/dec:2 \
  --scale ../data/selfplay/dec:$SCALE_SF19 --scale ../data/selfplay/eg2:$SCALE_SF19 --scale ../data/elite_labelled:$SCALE_SF19 --scale ../data/site_all:$SCALE_SF19 --scale ../data/site_labelled:$SCALE_SF19 --scale ../data/hard:$SCALE_SF19 \
  --val ../data/site_labelled/chunk_0001.npz --val ../data/site_all/chunk_0001.npz --val "$VAL_DEC" --val ../data/lichessq3/chunk_0036.npz \
  --buckets 8 --hidden ${HIDDEN:-512} --act crelu --out-buckets 1 \
  --resume "$RESUME" --epochs $EPOCHS --batch 16384 --lr $LR --wdl 1.0 --pc-weight 0.0 --val-n ${VAL_N:-50000} \
  --out $OUT
