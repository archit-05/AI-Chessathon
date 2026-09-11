#!/bin/bash
# V5 run B (V5 Plan s3.1): run A + the result blend (lambda 0.75) on the self-play streams only.
# clipped ReLU, one output), on the corrected mix: all quiet Lichess, decisive self-play from
# site-game starts (dec2) + the V4.5 decisive stream (dec), the resolved endgame stream (eg2),
# site-labelled x4, elite whole-game x2, hard x10. cp targets only (WDL 1.0); run B adds the blend.
# Pilot (1 epoch, Lichess capped):   EPOCHS=1 LICHESS_CAP=12 OUT=../data/nnue_v5p.safetensors bash tools/run_v5a.sh
# Full run:                          bash tools/run_v5a.sh
set -euo pipefail
cd "$(dirname "$0")/.."
PY=../aichessathon-starter/.venv/bin/python
SCALE=${SCALE:-0.85}
EPOCHS=${EPOCHS:-6}
LR=${LR:-1e-3}
WDL=${WDL:-1.0}
HIDDEN=${HIDDEN:-512}
ACT=${ACT:-crelu}
OUTB=${OUTB:-1}
OUT=${OUT:-../data/nnue_v5b.safetensors}
LICHESS_CAP=${LICHESS_CAP:-100000}
EXTRA=${EXTRA:---wdl-dir ../data/selfplay/dec2:0.75 --wdl-dir ../data/selfplay/dec:0.75 --wdl-dir ../data/selfplay/eg2:0.75 --wdl-dir ../data/selfplay/eg3:0.75}
VAL_DEC2=$(ls ../data/selfplay/dec2/chunk_w60_*.npz 2>/dev/null | head -1 || true)
VAL_DEC=$(ls ../data/selfplay/dec/chunk_w50_*.npz | head -1)
VALS="--val ../data/site_labelled/chunk_0001.npz --val ../data/site_all/chunk_0001.npz --val $VAL_DEC --val ../data/lichessq3/chunk_0036.npz"
[ -n "$VAL_DEC2" ] && VALS="$VALS --val $VAL_DEC2"
exec $PY tools/train_nnue.py \
  --data ../data/lichessq ../data/lichessq2 ../data/lichessq3 ../data/selfplay/dec2 ../data/selfplay/dec ../data/selfplay/eg2 ../data/selfplay/eg3 ../data/site_all ../data/elite_labelled ../data/hard \
  --quiet-only \
  --max-chunks ../data/lichessq:$LICHESS_CAP --max-chunks ../data/lichessq2:$LICHESS_CAP --max-chunks ../data/lichessq3:$LICHESS_CAP \
  --oversample ../data/site_all:4 --oversample ../data/elite_labelled:2 --oversample ../data/selfplay/dec2:2 --oversample ../data/selfplay/dec:2 --oversample ../data/selfplay/eg2:2 --oversample ../data/selfplay/eg3:2 --oversample ../data/hard:10 \
  --scale ../data/selfplay:$SCALE --scale ../data/elite_labelled:$SCALE --scale ../data/site_all:$SCALE --scale ../data/site_labelled:$SCALE --scale ../data/hard:$SCALE \
  $VALS \
  --buckets 8 --hidden $HIDDEN --act $ACT --out-buckets $OUTB \
  --epochs $EPOCHS --batch 16384 --lr $LR --wdl $WDL --pc-weight 0.0 --val-n ${VAL_N:-50000} $EXTRA \
  --out $OUT
