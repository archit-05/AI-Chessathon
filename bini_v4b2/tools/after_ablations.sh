#!/bin/bash
cd "$(dirname "$0")/.."
until grep -q "ablations done" ../data/ablations.log 2>/dev/null; do sleep 60; done
echo "$(date '+%F %T') v4o3 start"; bash tools/run_v4o3.sh > ../data/train_v4o3.log 2>&1; echo "$(date '+%F %T') v4o3 done: $(grep 'epoch 0 val site_labelled' ../data/train_v4o3.log | tail -1)"
