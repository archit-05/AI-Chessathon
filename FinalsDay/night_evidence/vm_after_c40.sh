#!/bin/bash
# priorcrypto-vm: after the contempt-40 gate ends, write its report here, then run the endgame-fix gate (eg vs book candidate), then its report.
set -u; cd ~/chess; V=~/chess/aichessathon-starter/.venv/bin/python; G=~/chess/gates; S=$G/vm_chain.status; export BINI_JOIN_S=300
log() { echo "$(date '+%F %T') $*" | tee -a $S; }
log "waiting for the c40 gate (100 games)"
while ! grep -q "^\[100/100\]" $G/c40_vm.log 2>/dev/null && ps -eo args | grep -q "[a]rena_par.py --agent /home/ubuntu/chess/cand_sfbook_c40"; do sleep 120; done
sleep 10; log "c40 gate: $(grep -E '^\[' $G/c40_vm.log | tail -1)"
$V book_gate_report.py $G/c40_vm.log $G/c40_vm.stats.jsonl > $G/c40_vm_report.json 2>&1 && log "c40 report written ($G/c40_vm_report.json)"
L=$(grep -E "^\[" $G/c40_vm.log | tail -1); W=$(echo "$L" | sed -nE 's/.*\+([0-9]+) =.*/\1/p'); D=$(echo "$L" | sed -nE 's/.*=([0-9]+) -.*/\1/p'); Lo=$(echo "$L" | sed -nE 's/.*-([0-9]+)  score.*/\1/p'); python3 match_odds.py "$W" "$D" "$Lo" | tee -a $S
mkdir -p cand_sfbook_eg/tools; cp cand_sfbook_c40/tools/arena_par.py cand_sfbook_c40/tools/curated.epd cand_sfbook_eg/tools/
log "starting eg gate: cand_sfbook_eg vs cand_sfbook, 100 games, 4 workers"
$V cand_sfbook_eg/tools/arena_par.py --agent ~/chess/cand_sfbook_eg --opponent ~/chess/cand_sfbook --games 100 --base-ms 120000 --inc-ms 500 --workers 4 --openings cand_sfbook_eg/tools/curated.epd --pgn-out $G/eg_vm.pgn --stats-out $G/eg_vm.stats.jsonl > $G/eg_vm.log 2>&1 < /dev/null
log "eg gate: $(grep -E '^\[' $G/eg_vm.log | tail -1)"
$V book_gate_report.py $G/eg_vm.log $G/eg_vm.stats.jsonl > $G/eg_vm_report.json 2>&1 && log "eg report written ($G/eg_vm_report.json)"
log "vm chain done"
