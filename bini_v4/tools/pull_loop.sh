#!/bin/bash
# Pull finished self-play chunks from the VM and both x86 boxes every 10 minutes (idempotent).
cd "$(dirname "$0")/.."
while true; do
  bash tools/pull_selfplay.sh 2>&1 | tail -1
  for BOX in gcp-x86 gcp-x86b; do
    if ssh -o BatchMode=yes -o ConnectTimeout=8 $BOX true 2>/dev/null; then
      rsync -az --include="*/" --include="chunk_*.npz" --include="*.log" --exclude="*" $BOX:chess/data/selfplay/ ../data/selfplay/ 2>/dev/null && echo "$(date '+%H:%M') $BOX pulled"
      rsync -az --include="chunk_*.npz" --exclude="*" $BOX:chess/data/elite2/ ../data/elite2/ 2>/dev/null
    fi
  done
  sleep 600
done
