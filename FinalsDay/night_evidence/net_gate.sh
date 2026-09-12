#!/bin/bash
# Turnkey validation of a NEW NET inside the exact V8.5 engine code.
# usage: net_gate.sh <new.safetensors> <tag> [screen_games=576] [tc5_games=576] [real_games=0]
set -u; cd ~/chess; V=~/chess/venv/bin/python; G=~/chess/gates; NET="$1"; TAG="$2"; SG=${3:-576}; TG=${4:-576}; RG=${5:-0}
bash bini_v65/tools/pause_gen.sh pause >/dev/null
rm -rf cand_$TAG; cp -r bini_astra_v5_noc2b cand_$TAG; rm -rf cand_$TAG/__pycache__; cp "$NET" cand_$TAG/nnue.safetensors
mkdir -p cand_$TAG/tools; cp tools_v85/arena_par.py tools_v85/curated.epd cand_$TAG/tools/
echo "== $(date) net=$(sha256sum "$NET" | cut -c1-16) bytes=$(stat -c %s "$NET") tag=$TAG" | tee $G/$TAG.summary
echo "-- package smoke (production init, nnue on, legal move, RSS)" | tee -a $G/$TAG.summary
~/chess/venv/bin/python pkg_smoke.py cand_$TAG $TAG 2>&1 | tee -a $G/$TAG.summary
A="BINI_NNUE=$HOME/chess/cand_$TAG/nnue.safetensors"; B="BINI_NNUE=$HOME/chess/bini_astra_v5_noc2b/nnue.safetensors"
$V bini_v65/tools/node_gate.py --engine ~/chess/bini_astra_v5_noc2b --a "$A" --b "$B" --openings bini_v65/tools/curated.epd --games $SG --nodes 30000 --workers 4 --tt-bits 22 --out $G/${TAG}_30k > $G/${TAG}_30k.stdout 2>&1
echo "30k screen (upper bound): $(grep -E "^\S+ \[" $G/${TAG}_30k.log | tail -1)" | tee -a $G/$TAG.summary
$V bini_v65/tools/node_gate.py --engine ~/chess/bini_astra_v5_noc2b --a "$A" --b "$B" --openings bini_v65/tools/curated.epd --games $TG --tc 5+0.05 --workers 4 --tt-bits 22 --out $G/${TAG}_tc5 > $G/${TAG}_tc5.stdout 2>&1
echo "5+0.05 timed: $(grep -E "^\S+ \[" $G/${TAG}_tc5.log | tail -1)" | tee -a $G/$TAG.summary
if [ "$RG" -gt 0 ]; then export BINI_JOIN_S=300
  $V cand_$TAG/tools/arena_par.py --agent ~/chess/cand_$TAG --opponent ~/chess/bini_astra_v5_noc2b --games $RG --base-ms 120000 --inc-ms 500 --workers 6 --openings cand_$TAG/tools/curated.epd --pgn-out $G/${TAG}_real.pgn > $G/${TAG}_real.log 2>&1
  echo "120+0.5 real wrapper: $(grep -E "^\[" $G/${TAG}_real.log | tail -1) fallback_lines=$(grep -c fallback $G/${TAG}_real.log)" | tee -a $G/$TAG.summary
fi
echo "== $(date) done" | tee -a $G/$TAG.summary
