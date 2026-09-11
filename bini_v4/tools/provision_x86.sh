#!/bin/bash
# Provision an x86 Ubuntu 22.04/24.04 box (GCP e2-standard-8 / c3-standard-8) as the V5 generator
# and gate machine, mirroring the Oracle VM's ~/chess layout. Run FROM THE MAC:
#     bash bini_v4/tools/provision_x86.sh <ssh-alias>
# Idempotent: re-running skips finished steps. Takes ~10 min (Stockfish build ~3 min on 8 cores).
set -euo pipefail
HOST=${1:?ssh alias of the x86 box}
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
echo "== $(date '+%F %T') provisioning $HOST from $REPO"
ssh -o BatchMode=yes "$HOST" 'bash -s' <<'REMOTE'
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
sudo apt-get update -qq
sudo apt-get install -y -qq build-essential git python3 python3-venv python3-pip rsync htop > /dev/null
mkdir -p ~/chess/data/selfplay ~/chess/gates
cd ~/chess
if [ ! -x Stockfish/src/stockfish ]; then
  git clone --depth 1 --branch sf_19 https://github.com/official-stockfish/Stockfish.git
  ( cd Stockfish/src && make -j"$(nproc)" profile-build ARCH=x86-64-avx512 > ../../sf_build.log 2>&1 && echo BUILD_DONE )
fi
if [ ! -x venv/bin/python ]; then
  python3 -m venv venv
  venv/bin/pip install -q --upgrade pip
  # the platform stack (docs): numba 0.67, numpy 2.5.x, python-chess 1.11.2; torch CPU for net_diag/export
  venv/bin/pip install -q "numba==0.67.0" "numpy==2.5.3" "chess==1.11.2"
  venv/bin/pip install -q torch --index-url https://download.pytorch.org/whl/cpu
fi
echo "sf: $(Stockfish/src/stockfish bench 2>&1 | grep 'Nodes/second')"
venv/bin/python -c "import numba,numpy,chess,torch;print('venv ok',numba.__version__,numpy.__version__,chess.__version__,torch.__version__)"
nproc; free -g | head -2; df -h ~ | tail -1
REMOTE
echo "== code and data"
rsync -a --exclude __pycache__ --exclude 'tests/arena' "$REPO/bini_v4/" "$HOST:~/chess/bini_v4/"
rsync -a --exclude __pycache__ --exclude 'tests/arena' --exclude submission.zip "$REPO/bini_v4final/" "$HOST:~/chess/bini_v4final/"
rsync -a --exclude .venv --exclude __pycache__ "$REPO/aichessathon-starter/" "$HOST:~/chess/aichessathon-starter/"
rsync -a "$REPO/intel/raw/cache/games/" "$HOST:~/chess/data/site_games/"
rsync -a "$REPO/data/site_labelled/" "$HOST:~/chess/data/site_labelled/"
rsync -a "$REPO/data/hard/" "$HOST:~/chess/data/hard/"
# the starter venv on the box: bini_v4/../aichessathon-starter/.venv/bin/python is what the tools expect
ssh -o BatchMode=yes "$HOST" 'cd ~/chess/aichessathon-starter && [ -x .venv/bin/python ] || (python3 -m venv .venv && .venv/bin/pip install -q "numba==0.67.0" "numpy==2.5.3" "chess==1.11.2"); echo "starter venv: $(.venv/bin/python -c "import numba;print(numba.__version__)")"'
echo "== smoke: engine compiles and plays one move"
ssh -o BatchMode=yes "$HOST" 'cd ~/chess/bini_v4final && timeout 180 ../aichessathon-starter/.venv/bin/python -c "
import time; t=time.time(); import agent; print(\"init\", round(time.time()-t,1), \"s\"); print(agent.get_move(\"r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3\", 120000))"'
echo "== $(date '+%F %T') $HOST ready. Start S1 generation with: ssh $HOST bash ~/chess/bini_v4/tools/x86_start_s1.sh"
