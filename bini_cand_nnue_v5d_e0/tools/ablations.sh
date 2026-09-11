#!/bin/bash
# Three one-hour fine-tunes, back to back on the GPU, to attribute the v4a/v4b game losses:
#   v4o  = v3b (old architecture) + the full tournament mix (wdl 0.85, pc-weight, site x12)
#   v4o2 = v3b (old architecture) + the mild mix (no wdl, no pc-weight, site x4)
#   v4b2 = v4a (new architecture) + the mild mix
set -u
cd "$(dirname "$0")/.."
for run in run_v4o run_v4o2 run_v4b2; do
  echo "$(date '+%F %T') $run start"
  bash tools/$run.sh > ../data/train_${run#run_}.log 2>&1
  echo "$(date '+%F %T') $run done: $(grep -E 'epoch 1 val site_labelled' ../data/train_${run#run_}.log | tail -1)"
done
echo "$(date '+%F %T') ablations done"
