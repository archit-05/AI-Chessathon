#!/bin/bash
# Provision the rented GPU box (Ubuntu, one NVIDIA GPU, >= 16 vCPUs): CUDA torch for the trainer,
# Leela (lc0) with a strong network as the batch labeller, Stockfish as the fallback labeller,
# our tools. Run FROM THE MAC:   bash tools/provision_gpu.sh <ssh-alias>
set -uo pipefail
HOST=${1:?ssh alias}
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
echo "== $(date '+%F %T') provisioning GPU box $HOST"
ssh -o BatchMode=yes "$HOST" 'bash -s' <<'REMOTE'
set -u
export DEBIAN_FRONTEND=noninteractive
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader || echo "NO GPU VISIBLE"
sudo apt-get update -qq
sudo apt-get install -y -qq build-essential git python3 python3-venv python3-pip rsync unzip bc meson ninja-build libopenblas-dev zlib1g-dev > /dev/null
mkdir -p ~/chess/data/selfplay ~/chess/gates ~/chess/data/leela
cd ~/chess
# --- Stockfish (fallback labeller)
if [ ! -x Stockfish/src/stockfish ]; then
  git clone --depth 1 --branch sf_19 https://github.com/official-stockfish/Stockfish.git
  ( cd Stockfish/src && make -j"$(nproc)" profile-build ARCH=x86-64-avx2 > ../../sf_build.log 2>&1 && echo SF_BUILD_DONE )
fi
# --- python: the platform stack + CUDA torch
if [ ! -x venv/bin/python ]; then
  python3 -m venv venv && venv/bin/pip install -q --upgrade pip
  venv/bin/pip install -q "numba==0.67.0" "numpy==2.5.3" "chess==1.11.2"
  venv/bin/pip install -q torch --index-url https://download.pytorch.org/whl/cu124 || venv/bin/pip install -q torch
fi
venv/bin/python -c "import torch;print('torch',torch.__version__,'cuda',torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else '')"
# --- Leela (lc0) with the CUDA backend
if [ ! -x lc0/build/release/lc0 ]; then
  git clone --depth 1 --recurse-submodules https://github.com/LeelaChessZero/lc0.git
  ( cd lc0 && CC=gcc CXX=g++ ./build.sh release -Dcudnn=false -Dplain_cuda=true > ../lc0_build.log 2>&1 && echo LC0_BUILD_DONE || echo "LC0_BUILD_FAILED (see ~/chess/lc0_build.log)" )
fi
ls -la lc0/build/release/lc0 2>/dev/null
nproc; free -g | head -2; df -h ~ | tail -1
REMOTE
echo "== code"
rsync -a --exclude __pycache__ --exclude 'tests/arena' "$REPO/bini_v5/" "$HOST:~/chess/bini_v5/"
rsync -a --exclude __pycache__ --exclude 'tests/arena' --exclude submission.zip "$REPO/bini_v4final/" "$HOST:~/chess/bini_v4final/"
rsync -a --exclude .venv --exclude __pycache__ "$REPO/aichessathon-starter/" "$HOST:~/chess/aichessathon-starter/"
ssh -o BatchMode=yes "$HOST" '[ -e ~/chess/aichessathon-starter/.venv ] || ln -s ~/chess/venv ~/chess/aichessathon-starter/.venv; [ -x /usr/local/bin/stockfish ] || sudo ln -s $HOME/chess/Stockfish/src/stockfish /usr/local/bin/stockfish; echo linked'
rsync -az "$REPO/data/site_labelled/" "$HOST:~/chess/data/site_labelled/"
rsync -az "$REPO/data/nnue_v3b.pt" "$REPO/data/nnue_v3b.safetensors" "$HOST:~/chess/data/"
echo "== $(date '+%F %T') $HOST provisioned. Next: fetch a Leela network (tools/leela_net.sh), upload elite PGNs (rsync data/elite/*.pgn), start tools/label_leela.py"
