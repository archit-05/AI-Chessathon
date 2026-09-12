#!/bin/bash
# After the Lane C screens (bp_d7_ft, bp96_d7_ft, bp144_d7_ft) have run or been skipped, run the 5+0.05 ladder (400 games)
# vs fc_b for the best 30k screen among all arms; mirror. Deadline 08:30 UTC.
set -u; cd ~/chess; S=~/chess/logs/screen_queue.status; V=~/chess/venv/bin/python; E=~/chess/bini_astra_v5_noc2b; NG=~/chess/bini_v65/tools/node_gate.py; O=~/chess/bini_v65/tools/curated.epd; NETS=~/chess/data/nets
log() { echo "$(date '+%F %T') $*" | tee -a $S; }
done_or_skipped() { [ -f ~/chess/gates/${1}_30k.log ] && grep -q "\[576/576\]" ~/chess/gates/${1}_30k.log || grep -q "SKIP $1 " $S 2>/dev/null; }
while ! { done_or_skipped bp_d7_ft && done_or_skipped bp96_d7_ft && done_or_skipped bp144_d7_ft; } && [ "$(date -u +%H%M)" -lt 0830 ]; do sleep 120; done
while ps -eo args | grep -q "[n]ode_gate.py --engine"; do sleep 30; done
BEST=""; BESTE=-999
for f in ~/chess/gates/*_30k.log; do ID=$(basename $f _30k); grep -q "\[576/576\]" $f || continue; e=$(grep -E '^\S+ \[' $f | tail -1 | sed -E 's/.*elo ([+-]?[0-9]+).*/\1/'); [ -n "$e" ] && [ "$e" -gt "$BESTE" ] && { BESTE=$e; BEST=$ID; }; done
log "ladder: best complete screen is ${BEST:-none} (+$BESTE)"
[ -n "$BEST" ] && [ "$BEST" != fcb_re ] && [ ! -f ~/chess/gates/${BEST}_tc5.log ] && {
  $V $NG --engine $E --a "BINI_NNUE=$NETS/nnue_$BEST.safetensors" --b "BINI_NNUE=$NETS/nnue_fcb.safetensors" --openings $O --games 400 --tc 5+0.05 --workers 4 --tt-bits 22 --out ~/chess/gates/${BEST}_tc5 > ~/chess/gates/${BEST}_tc5.stdout 2>&1
  log "TC5 $BEST vs fc_b: $(grep -E '^\S+ \[' ~/chess/gates/${BEST}_tc5.log | tail -1)"; }
rsync -az -e "ssh -o StrictHostKeyChecking=no" ~/chess/gates/ ~/chess/logs/ forge@8.228.62.35:~/chess/data/stage/nets_night/ 2>/dev/null; log "ladder step done"
