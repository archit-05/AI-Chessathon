#!/bin/bash
# Copy the newly labelled elite chunks (data/elite2/chunk_NNNN.npz) into data/elite_labelled as
# chunk_1NNN.npz so both trainers see one elite set (idempotent).
cd "$(dirname "$0")/../../data" || exit 1
n=0
for f in elite2/chunk_*.npz; do
  [ -f "$f" ] || continue
  b=$(basename "$f" .npz); num=${b#chunk_}; dst="elite_labelled/chunk_1${num}.npz"
  [ -f "$dst" ] || { cp "$f" "$dst"; n=$((n+1)); }
done
echo "$(date '+%H:%M') elite_labelled now $(ls elite_labelled/chunk_*.npz | wc -l | tr -d ' ') chunks (+$n)"
