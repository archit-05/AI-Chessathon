#!/bin/bash
# Turn a fresh RunPod A40 pod into a real-clock gate worker: pull the two candidate dirs from gcp-x86, platform venv,
# harness, then run arena_par (120+0.5, 4 workers) on an opening slice so several pods cover disjoint blocks.
# usage: bash gate_worker.sh <gcp target> <agent_dir_name> <opponent_dir_name> <slice_start_fen> <games> <tag>
set -u; GCP="$1"; A="$2"; B="$3"; START="$4"; GAMES="$5"; TAG="$6"; export DEBIAN_FRONTEND=noninteractive
mkdir -p ~/chess/gates ~/chess/logs ~/chess/tools_v85; cd ~/chess; S=~/chess/logs/gate_$TAG.status
log() { echo "$(date '+%F %T') $*" | tee -a $S; }
apt-get update -qq >/dev/null 2>&1; apt-get install -y -qq rsync python3-venv >/dev/null 2>&1
for d in $A $B aichessathon-starter astra_tests tools_v85; do mkdir -p ~/chess/$d; rsync -az --exclude __pycache__ --exclude .venv -e "ssh -o StrictHostKeyChecking=no" $GCP:~/chess/$d/ ~/chess/$d/ || { log "pull $d failed"; exit 1; }; done
PY=$(command -v python3.12 || command -v python3.11 || command -v python3)
[ -x venv/bin/python ] || { $PY -m venv venv && venv/bin/pip install -q --upgrade pip && venv/bin/pip install -q "numba==0.67.0" "numpy==2.5.2" "chess==1.11.2"; }
[ -e aichessathon-starter/.venv ] || ln -s ~/chess/venv ~/chess/aichessathon-starter/.venv
mkdir -p $A/tools; cp tools_v85/arena_par.py $A/tools/; sed -n "$((START+1)),$((START+GAMES/2))p" tools_v85/curated.epd > $A/tools/slice_$TAG.epd
log "gate $TAG: $A vs $B, openings $((START+1))..$((START+GAMES/2)), $GAMES games, 4 workers"
export BINI_JOIN_S=300
venv/bin/python $A/tools/arena_par.py --agent ~/chess/$A --opponent ~/chess/$B --games $GAMES --base-ms 120000 --inc-ms 500 --workers 4 --openings $A/tools/slice_$TAG.epd --pgn-out ~/chess/gates/$TAG.pgn --stats-out ~/chess/gates/$TAG.stats.jsonl > ~/chess/gates/$TAG.log 2>&1
log "gate $TAG done: $(grep -E '^\[' ~/chess/gates/$TAG.log | tail -1)"
rsync -az -e "ssh -o StrictHostKeyChecking=no" ~/chess/gates/ $GCP:~/chess/data/stage/gates_pods/ 2>/dev/null
