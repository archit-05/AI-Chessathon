#!/bin/bash
# Create ../bini_hce: the same engine without the network file (hand-crafted eval), used as the
# arena opponent when gating a new network.
set -euo pipefail
cd "$(dirname "$0")/.."
rm -rf ../bini_hce && mkdir -p ../bini_hce
cp agent.py bini_*.py ../bini_hce/
echo "../bini_hce ready (no nnue.safetensors => HCE)"
