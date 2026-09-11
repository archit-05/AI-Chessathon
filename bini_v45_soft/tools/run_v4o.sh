#!/bin/bash
# v4o: fine-tune the SHIPPED v3b net (old architecture: clipped ReLU, one output) on the same tournament mix; the fallback candidate. Original header: v4b: fine-tune v4a on the curated self-play stream (Stockfish 19 depth 9, results kept) plus the
# site-labelled set, with the quiet Lichess data kept in the mix so nothing is forgotten.
# Run from bini_v4/ on the Mac:  RESUME=../data/nnue_v4a.pt bash tools/run_v4b.sh
set -euo pipefail
cd "$(dirname "$0")/.."
PY=../aichessathon-starter/.venv/bin/python
RESUME=${RESUME:-../data/nnue_v3b.pt}
SCALE_SF19=${SCALE_SF19:-0.85}   # tools/scale_fit.py: lichess_cp ~ 0.86 * sf19_cp (median 0.80), SF16 site labels share the scale
EPOCHS=${EPOCHS:-2}
LR=${LR:-5e-4}
WDL=${WDL:-0.85}
HIDDEN=${HIDDEN:-512}
OUT=${OUT:-../data/nnue_v4o.safetensors}
# a held-out self-play chunk: the first chunk of worker 0 never trains
VAL_SP=$(ls ../data/selfplay/chunk_w0_*.npz | head -1)
exec $PY tools/train_nnue.py \
  --data ../data/selfplay ../data/site_all ../data/elite_labelled ../data/hard ../data/lichessq3 \
  --quiet-only \
  --oversample ../data/selfplay:2 --oversample ../data/site_all:12 --oversample ../data/hard:20 \
  --scale ../data/selfplay:$SCALE_SF19 --scale ../data/elite_labelled:$SCALE_SF19 --scale ../data/site_all:$SCALE_SF19 --scale ../data/site_labelled:$SCALE_SF19 --scale ../data/hard:$SCALE_SF19 \
  --val ../data/site_labelled/chunk_0001.npz --val ../data/site_all/chunk_0001.npz --val "$VAL_SP" --val ../data/lichessq3/chunk_0036.npz \
  --buckets 8 --hidden $HIDDEN --act crelu --out-buckets 1 \
  --resume "$RESUME" --epochs $EPOCHS --batch 16384 --lr $LR --wdl $WDL --pc-weight 0.5 --val-n ${VAL_N:-50000} \
  --out $OUT
