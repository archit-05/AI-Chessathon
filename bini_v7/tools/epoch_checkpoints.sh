#!/bin/bash
# Checkpoint a training run by games after every epoch (V5 Plan 18:15 rule): when the log shows
# "epoch N done", snapshot the export, copy it to the x86 box, run checkpoint_gate.sh (40 games at
# 5 s vs V3's net). Kill the run if an epoch scores below the pass line.
#   bash tools/epoch_checkpoints.sh <run name, e.g. v5d> <pass percent> <epochs>
set -uo pipefail
cd "$(dirname "$0")/.."
RUN=$1; PASS=${2:-45}; EPOCHS=${3:-2}; GAMES=${4:-200}
say() { echo "$(date '+%F %T') $*"; }
for ((e=0; e<EPOCHS; e++)); do
  until [ "$(grep -c 'epoch .* done' ../data/train_$RUN.log)" -ge $((e+1)) ] && [ -f ../data/nnue_$RUN.safetensors ] || grep -qE "Traceback" ../data/train_$RUN.log; do sleep 30; done
  grep -q Traceback ../data/train_$RUN.log && { say "$RUN crashed"; exit 1; }
  sleep 20  # let the export finish writing
  NAME=nnue_${RUN}_e$e
  cp ../data/nnue_$RUN.pt ../data/$NAME.pt && cp ../data/nnue_$RUN.safetensors ../data/$NAME.safetensors
  for BOX in gcp-x86 gcp-x86b; do rsync -az ../data/$NAME.pt ../data/$NAME.safetensors $BOX:chess/data/ 2>/dev/null; done
  say "$RUN epoch $e exported: $(grep -E "epoch $e val" ../data/train_$RUN.log | sed -E 's/.*val ([a-z_0-9]+)\/.*MAE ([0-9]+)cp/\1 \2/' | tr '\n' ' ')"
  bash tools/checkpoint_gate.sh $NAME $GAMES > ../data/ckpt_$NAME.log 2>&1
  T=$(grep -E "^\[" ../data/gate_ckpt_$NAME.log | tail -1); PCT=$(echo "$T" | grep -o "score [0-9.]*" | awk '{print $2}')
  say "$RUN epoch $e checkpoint: $T"
  if [ -n "$PCT" ] && [ "$(echo "$PCT < $PASS" | bc)" = "1" ]; then say "$RUN epoch $e BELOW $PASS%: stopping the run"; pkill -f "tools/train_nnue.py"; exit 2; fi
done
say "$RUN CHECKPOINTS DONE"
