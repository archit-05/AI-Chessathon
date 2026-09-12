#!/bin/bash
# Screen every new net vs fc_b at 30k nodes (576 games) in priority order as they appear, one at a time after the
# A-lane's own screens; then a 5+0.05 ladder (400 games) for the best screen. Runs on the pod's cores (4 workers).
set -u; cd ~/chess; S=~/chess/logs/screen_queue.status; V=~/chess/venv/bin/python; E=~/chess/bini_astra_v5_noc2b; NG=~/chess/bini_v65/tools/node_gate.py; O=~/chess/bini_v65/tools/curated.epd; NETS=~/chess/data/nets
log() { echo "$(date '+%F %T') $*" | tee -a $S; }
busy() { ps -eo args | grep -q "[n]ode_gate.py --engine"; }
while ! grep -q "A-lane done\|no trainer binary" ~/chess/logs/a_lane.status 2>/dev/null; do sleep 60; done
for ID in k96b_ft a3site k96b; do
  while [ ! -f $NETS/nnue_$ID.safetensors ]; do sleep 60; [ -f ~/chess/logs/b_lane.status ] && grep -q "FAILED" ~/chess/logs/b_lane.status && [ "$ID" != a3site ] && break; done
  [ -f $NETS/nnue_$ID.safetensors ] || { log "SKIP $ID (not produced)"; continue; }
  while busy; do sleep 30; done
  $V $NG --engine $E --a "BINI_NNUE=$NETS/nnue_$ID.safetensors" --b "BINI_NNUE=$NETS/nnue_fcb.safetensors" --openings $O --games 576 --nodes 30000 --workers 4 --tt-bits 22 --out ~/chess/gates/${ID}_30k > ~/chess/gates/${ID}_30k.stdout 2>&1
  log "SCREEN $ID vs fc_b: $(grep -E '^\S+ \[' ~/chess/gates/${ID}_30k.log | tail -1)"
done
# best screen among all arms -> 5+0.05 ladder
BEST=""; BESTE=-999
for f in ~/chess/gates/*_30k.log; do ID=$(basename $f _30k); e=$(grep -E '^\S+ \[' $f | tail -1 | sed -E 's/.*elo ([+-]?[0-9]+).*/\1/'); [ -n "$e" ] && [ "$e" -gt "$BESTE" ] && { BESTE=$e; BEST=$ID; }; done
log "best screen: $BEST ($BESTE)"
if [ -n "$BEST" ] && [ ! -f ~/chess/gates/${BEST}_tc5.log ]; then
  $V $NG --engine $E --a "BINI_NNUE=$NETS/nnue_$BEST.safetensors" --b "BINI_NNUE=$NETS/nnue_fcb.safetensors" --openings $O --games 400 --tc 5+0.05 --workers 4 --tt-bits 22 --out ~/chess/gates/${BEST}_tc5 > ~/chess/gates/${BEST}_tc5.stdout 2>&1
  log "TC5 $BEST vs fc_b: $(grep -E '^\S+ \[' ~/chess/gates/${BEST}_tc5.log | tail -1)"
fi
rsync -az -e "ssh -o StrictHostKeyChecking=no" ~/chess/gates/ ~/chess/logs/ forge@8.228.62.35:~/chess/data/stage/nets_night/ 2>/dev/null; log "screen queue done"
