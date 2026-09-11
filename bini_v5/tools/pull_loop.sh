#!/bin/bash
# Pull finished self-play chunks from the VM and the x86 box every 10 minutes (idempotent).
cd "$(dirname "$0")/.."
while true; do
  bash tools/pull_selfplay.sh 2>&1 | tail -1
  if ssh -o BatchMode=yes -o ConnectTimeout=8 gcp-x86 true 2>/dev/null; then
    rsync -az --include='*/' --include='chunk_*.npz' --include='*.log' --exclude='*' gcp-x86:chess/data/selfplay/ ../data/selfplay/ 2>/dev/null && echo "$(date '+%H:%M') x86 pulled: $(ls ../data/selfplay/dec2/chunk_w7*.npz 2>/dev/null | wc -l | tr -d ' ') chunks"
  fi
  sleep 600
done
