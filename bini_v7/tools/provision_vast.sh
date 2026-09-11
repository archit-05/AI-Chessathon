#!/bin/bash
# Provision the Vast.ai GPU box (root container, Ubuntu 24.04, CUDA 12.8 devel, /venv/main has torch):
# Stockfish 19 (vnni512), rustup + bullet source, the platform venv (numba 0.67 / numpy 2.5.2 /
# python-chess 1.11.2), and the public data downloads in the background. Idempotent. Runs ON the box:
#   nohup bash ~/chess/provision_vast.sh > ~/chess/logs/provision.log 2>&1 &
set -u
export DEBIAN_FRONTEND=noninteractive
mkdir -p ~/chess/data/elite ~/chess/data/lichess ~/chess/data/binpacks ~/chess/data/own ~/chess/gates ~/chess/logs
cd ~/chess
echo "== $(date '+%F %T') start"
apt-get update -qq > /dev/null 2>&1
apt-get install -y -qq build-essential git curl wget unzip zstd libzstd-dev pkg-config meson ninja-build htop > /dev/null 2>&1 && echo "apt ok"
# --- public data first (the network is the fast path; the Mac is 30 Mbps)
( cd data/elite && for m in 2025-03 2025-04 2025-05 2025-06; do [ -f lichess_elite_$m.zip ] || wget -q https://database.nikonoel.fr/lichess_elite_$m.zip; done; ls -la; echo ELITE_DONE ) > logs/elite_dl.log 2>&1 &
( cd data/lichess && [ -f lichess_db_eval.jsonl.zst ] || wget -q https://database.lichess.org/lichess_db_eval.jsonl.zst; ls -la; echo EVAL_DONE ) > logs/eval_dl.log 2>&1 &
# --- Stockfish 19
if [ ! -x Stockfish/src/stockfish ]; then
  git clone -q --depth 1 --branch sf_19 https://github.com/official-stockfish/Stockfish.git
  ( cd Stockfish/src && make -j24 profile-build ARCH=x86-64-vnni512 > ../../logs/sf_build.log 2>&1 && echo "SF_BUILD_DONE" || echo "SF_BUILD_FAILED" )
fi
ln -sf ~/chess/Stockfish/src/stockfish /usr/local/bin/stockfish
echo "bench:"; (echo "bench 16 1 12 default depth" | timeout 60 stockfish 2>&1 | grep -E "Nodes/second|Total time") 
# --- rust + bullet source
if [ ! -x ~/.cargo/bin/cargo ]; then curl -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal > logs/rustup.log 2>&1 && echo "rust ok"; fi
source ~/.cargo/env
[ -d bullet ] || git clone -q --depth 1 https://github.com/jw1912/bullet.git && echo "bullet src ok"
# --- python: the platform stack in ~/chess/venv (numba engine, gates, labellers); torch in /venv/main
if [ ! -x venv/bin/python ]; then
  python3 -m venv venv && venv/bin/pip install -q --upgrade pip
  venv/bin/pip install -q "numba==0.67.0" "numpy==2.5.2" "chess==1.11.2" zstandard && echo "platform venv ok"
fi
/venv/main/bin/pip install -q "chess==1.11.2" zstandard numba > logs/venv_main_pip.log 2>&1 && echo "torch venv extras ok"
/venv/main/bin/python -c "import torch,numba,chess;print('torch',torch.__version__,'cuda',torch.cuda.is_available(),torch.cuda.device_count(),'numba',numba.__version__)"
venv/bin/python -c "import numba,numpy,chess;print('platform venv numba',numba.__version__,'numpy',numpy.__version__,'chess',chess.__version__)"
[ -e aichessathon-starter/.venv ] || ln -s ~/chess/venv ~/chess/aichessathon-starter/.venv 2>/dev/null
echo "== $(date '+%F %T') provision done (downloads continue: logs/elite_dl.log, logs/eval_dl.log)"
