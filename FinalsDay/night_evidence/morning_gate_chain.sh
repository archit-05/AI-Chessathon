#!/bin/bash
# GCP: when the book gate finishes, run the real-clock (120+0.5) wrapper gates for the best screened net:
#   C: net + SF book + guards vs V8.5 as shipped (the shipping check), then A: net alone vs V8.5.
# Best net = highest 30k screen among the pod's SCREEN lines (mirrored to stage/nets_night); requires >= +12.
set -u; cd ~/chess; V=~/chess/venv/bin/python; G=~/chess/gates; S=$G/morning_chain.status; NN=~/chess/data/stage/nets_night
log() { echo "$(date '+%F %T') $*" | tee -a $S; }
# Pre-declared read point: 200 games (or 300 if it got there). The box is 4 physical cores, so 300 would run past 10:00.
# Read point: 300 games, or 08:00 BST (07:00 UTC on this box) whichever comes first (Archit: no rush; the pace is ~64 games/h).
log "waiting for the book gate: 300 games or 07:00 UTC"; while ! grep -q "^\[300/300\]" $G/sfbook_real.log 2>/dev/null && [ "$(date -u +%H%M)" -lt 0700 ]; do sleep 120; done
log "book gate at read point: $(grep -E '^\[' $G/sfbook_real.log | tail -1)"
ps -eo pid,args | grep "[a]rena_par.py --agent /home/forge/chess/cand_sfbook" | awk '{print $1}' | xargs -r kill; sleep 5; ps -eo pid,args | grep "[h]arness.runner" | awk '{print $1}' | xargs -r kill; sleep 3
log "book gate stopped after $(grep -E '^\[' $G/sfbook_real.log | tail -1 | cut -d] -f1 | tr -d '[') games (pre-declared read: 300 games or 07:00 UTC)"
$V bookbuild/book_gate_report.py $G/sfbook_real.log $G/sfbook_real.stats.jsonl > $G/sfbook_report.json 2>&1; log "book report written ($G/sfbook_report.json)"
BEST=""; BESTE=-999
for f in $NN/screen_queue.status $NN/a_lane.status; do [ -f $f ] || continue
  while read -r line; do id=$(echo "$line" | sed -nE 's/.*SCREEN ([a-z0-9_]+) vs fc_b.*/\1/p'); e=$(echo "$line" | sed -nE 's/.*elo ([+-]?[0-9]+).*/\1/p'); [ -n "$id" ] && [ -n "$e" ] && [ "$e" -gt "$BESTE" ] && { BESTE=$e; BEST=$id; }; done < <(grep "SCREEN" $f)
done
log "best screened net: ${BEST:-none} (+$BESTE)"
if [ -z "$BEST" ] || [ "$BESTE" -lt 12 ] || [ ! -f $NN/nnue_$BEST.safetensors ]; then log "no net clears +12 on the screen (or file missing): no net gate; V8.5 (+book if it passed) stands"; exit 0; fi
bash combo_gate.sh $NN/nnue_$BEST.safetensors bookbuild/book_sf.json $BEST 150 6 C >> $S 2>&1
while ! grep -q "^\[150/150\]" $G/combo_${BEST}_C.log 2>/dev/null; do sleep 120; done
log "combo C ($BEST + book vs V8.5): $(grep -E '^\[' $G/combo_${BEST}_C.log | tail -1)"; $V bookbuild/book_gate_report.py $G/combo_${BEST}_C.log $G/combo_${BEST}_C.stats.jsonl > $G/combo_${BEST}_C_report.json 2>&1
bash combo_gate.sh $NN/nnue_$BEST.safetensors bookbuild/book_sf.json $BEST 150 6 A >> $S 2>&1
while ! grep -q "^\[150/150\]" $G/combo_${BEST}_A.log 2>/dev/null; do sleep 120; done
log "combo A ($BEST vs V8.5): $(grep -E '^\[' $G/combo_${BEST}_A.log | tail -1)"; log "morning chain done"
