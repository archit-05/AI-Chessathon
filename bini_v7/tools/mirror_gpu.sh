#!/bin/bash
# Pull the GPU box's nets, gates, logs and the shuffled bulletformat set to the Mac (data/gpu_mirror) before the credit ends.
# Usage: bash bini_v5/tools/mirror_gpu.sh [also-labels]   (also-labels pulls data/labelled too: ~40 GB)
cd "$(dirname "$0")/../.."; mkdir -p data/gpu_mirror
rsync -az --include='nnue_*.safetensors' --exclude='*' gpu:~/chess/data/ data/gpu_mirror/nets/
rsync -az gpu:~/chess/gates/ data/gpu_mirror/gates/
rsync -az gpu:~/chess/logs/ data/gpu_mirror/logs/
rsync -az gpu:~/chess/data/bullet_shuf/ data/gpu_mirror/bullet_shuf/
rsync -az gpu:~/chess/data/ckpt/ data/gpu_mirror/ckpt/
[ "${1:-}" = "also-labels" ] && rsync -az gpu:~/chess/data/labelled/ data/gpu_mirror/labelled/
echo "$(date '+%F %T') mirror done: $(du -sh data/gpu_mirror | cut -f1)"
