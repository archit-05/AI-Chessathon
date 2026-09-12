#!/bin/bash
# priorcrypto-vm: when the endgame gate ends, join the bp336 evidence: ship_bp336 vs V8.5, 120+0.5, seed 7 (different openings from gcp)
set -u; cd ~/chess; V=~/chess/aichessathon-starter/.venv/bin/python; G=~/chess/gates; S=$G/vm_chain.status; export BINI_JOIN_S=300
log() { echo "$(date '+%F %T') $*" | tee -a $S; }
while ps -eo args | grep -q "[a]rena_par.py --agent"; do sleep 60; done
log "eg gate finished: $(grep -E '^\[' $G/eg_vm.log | tail -1 | cut -c1-70)"; $V book_gate_report.py $G/eg_vm.log $G/eg_vm.stats.jsonl > $G/eg_vm_report.json 2>&1 && log "eg report written"
mkdir -p ship_bp336/tools; cp cand_sfbook_c40/tools/arena_par.py cand_sfbook_c40/tools/curated.epd ship_bp336/tools/
log "starting direct package comparison: ship_bp336 vs ship_v85, 100 games, 4 workers, seed 7"
$V ship_bp336/tools/arena_par.py --agent ~/chess/ship_bp336 --opponent ~/chess/ship_v85 --games 100 --base-ms 120000 --inc-ms 500 --workers 4 --seed 7 --openings ship_bp336/tools/curated.epd --pgn-out $G/bp336_vs_v85pkg_vm.pgn --stats-out $G/bp336_vs_v85pkg_vm.stats.jsonl > $G/bp336_vs_v85pkg_vm.log 2>&1 < /dev/null
log "bp336 vm done: $(grep -E '^\[' $G/bp336_vs_v85pkg_vm.log | tail -1 | cut -c1-70)"
