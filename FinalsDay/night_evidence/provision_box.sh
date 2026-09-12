#!/bin/bash
# Lean provisioning for a rented x86 CPU box (run as root or a sudo user, Ubuntu): tools, Stockfish 19 (avx2 or vnni512 by CPU),
# the platform-stack venv (numba 0.67 / numpy 2.5.2 / python-chess 1.11.2), directories. No big downloads, no Rust.
set -u; export DEBIAN_FRONTEND=noninteractive; mkdir -p ~/chess/gates ~/chess/logs ~/chess/data ~/chess/bookbuild; cd ~/chess
echo "== $(date '+%F %T') start on $(hostname) nproc=$(nproc) ram=$(free -g | awk '/Mem/{print $2}')G"
(apt-get update -qq && apt-get install -y -qq build-essential git curl wget zstd htop rsync python3-venv python3-pip) > logs/apt.log 2>&1 && echo "apt ok" || echo "apt FAILED (see logs/apt.log)"
ARCH=x86-64-avx2; grep -q avx512_vnni /proc/cpuinfo && ARCH=x86-64-vnni512
if [ ! -x Stockfish/src/stockfish ]; then
  git clone -q --depth 1 --branch sf_19 https://github.com/official-stockfish/Stockfish.git
  ( cd Stockfish/src && make -j$(nproc) profile-build ARCH=$ARCH > ../../logs/sf_build.log 2>&1 && echo "SF_BUILD_DONE ($ARCH)" || echo "SF_BUILD_FAILED" )
fi
ln -sf ~/chess/Stockfish/src/stockfish /usr/local/bin/stockfish 2>/dev/null || true
echo "bench 16 1 12 default depth" | timeout 120 ~/chess/Stockfish/src/stockfish 2>&1 | grep -E "Nodes/second"
PY=$(command -v python3.12 || command -v python3.11 || command -v python3)
if [ ! -x venv/bin/python ]; then $PY -m venv venv && venv/bin/pip install -q --upgrade pip && venv/bin/pip install -q "numba==0.67.0" "numpy==2.5.2" "chess==1.11.2" && echo "platform venv ok ($($PY --version))"; fi
venv/bin/python -c "import numba,numpy,chess;print('venv numba',numba.__version__,'numpy',numpy.__version__,'chess',chess.__version__)"
[ -e aichessathon-starter/.venv ] || ln -s ~/chess/venv ~/chess/aichessathon-starter/.venv 2>/dev/null
echo "== $(date '+%F %T') provision done"
