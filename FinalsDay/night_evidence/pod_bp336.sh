#!/bin/bash
# pod: when the ship_v85 smoke ends, join the bp336 evidence: ship_bp336 vs V8.5, 120+0.5, seed 11 (different openings)
set -u; cd ~/chess; V=~/chess/venv/bin/python; G=~/chess/gates; S=~/chess/logs/pod_queue.status
log() { echo "$(date '+%F %T') $*" | tee -a $S; }
while ps -eo args | grep -q "[a]rena_par.py --agent /root/chess/ship_v85"; do sleep 60; done
log "ship_v85 smoke finished: $(grep -E '^\[' $G/ship_v85_smoke.log | tail -1 | cut -c1-70); failures=$(grep -c 'AGENT FAILURE\|engine error\|ILLEGAL\|BUILD FAILED' $G/ship_v85_smoke.log); still-compiling lines (expected, one per game)=$(grep -c 'still compiling' $G/ship_v85_smoke.log)"
grep -E '^terminations' $G/ship_v85_smoke.log | tail -1 | tee -a $S
mkdir -p ship_bp336/tools; cp arena_tools/arena_par.py arena_tools/curated.epd ship_bp336/tools/
log "starting bp336 evidence: ship_bp336 vs bini_astra_v5_noc2b, 100 games, 4 workers, seed 11"
env -u BINI_JOIN_S $V ship_bp336/tools/arena_par.py --agent ~/chess/ship_bp336 --opponent ~/chess/bini_astra_v5_noc2b --games 100 --base-ms 120000 --inc-ms 500 --workers 4 --seed 11 --openings ship_bp336/tools/curated.epd --pgn-out $G/bp336_pod.pgn --stats-out $G/bp336_pod.stats.jsonl > $G/bp336_pod.log 2>&1 < /dev/null
log "bp336 pod done: $(grep -E '^\[' $G/bp336_pod.log | tail -1 | cut -c1-70)"
