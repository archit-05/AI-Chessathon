#!/bin/bash
# Pull finished self-play chunks from the Oracle VM into ../data/selfplay (idempotent; the
# generator writes .tmp.npz first and renames, so only complete chunks match *.npz).
#   bash tools/pull_selfplay.sh            # once
#   watch -n 600 bash tools/pull_selfplay.sh   # every ten minutes
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p ../data/selfplay
rsync -az --include='*/' --include='chunk_*.npz' --include='*.log' --exclude='*' priorcrypto-vm:~/chess/data/selfplay/ ../data/selfplay/
n=$(find ../data/selfplay -name "chunk_*.npz" | wc -l | tr -d ' ')
echo "$(date '+%H:%M') selfplay chunks local: $n"
