#!/bin/bash
# pod: after the fixed-node screens are done, use the CPU for two real-clock checks we have not run anywhere else:
#  1) the full package vs Stockfish at UCI_Elo 2400 (a non-clone opponent: absolute level + decisive rate), 60 games
#  2) a short-clock stress test of the full package vs the book candidate at 30 s + 0.3 s, 40 games (zero timeouts required)
set -u; cd ~/chess; V=~/chess/venv/bin/python; G=~/chess/gates; S=~/chess/logs/pod_queue.status; export BINI_JOIN_S=300
log() { echo "$(date '+%F %T') $*" | tee -a $S; }
log "waiting for the screens (bp240, bp336) to finish"
while ps -eo args | grep -q "[n]ode_gate.py --engine" || ! grep -q "SCREEN bp336_d7_ft\|SKIP bp336_d7_ft" ~/chess/logs/screen_queue.status; do sleep 120; done
C=cand_sfbook_c40eg; mkdir -p $C/tools; cp arena_tools/arena_par.py arena_tools/curated.epd $C/tools/
log "gate 1: $C vs Stockfish UCI_Elo 2400, 120+0.5, 60 games, 4 workers"
SF_ELO=2400 $V $C/tools/arena_par.py --agent ~/chess/$C --opponent ~/chess/sf_agent --games 60 --base-ms 120000 --inc-ms 500 --workers 4 --openings $C/tools/curated.epd --pgn-out $G/sf2400.pgn --stats-out $G/sf2400.stats.jsonl > $G/sf2400.log 2>&1 < /dev/null
log "gate 1 done: $(grep -E '^\[' $G/sf2400.log | tail -1)"; $V book_gate_report.py $G/sf2400.log $G/sf2400.stats.jsonl > $G/sf2400_report.json 2>&1
log "gate 2: $C vs cand_sfbook at 30+0.3, 40 games (timeouts/failures check)"
$V $C/tools/arena_par.py --agent ~/chess/$C --opponent ~/chess/cand_sfbook --games 40 --base-ms 30000 --inc-ms 300 --workers 4 --openings $C/tools/curated.epd --pgn-out $G/short30.pgn --stats-out $G/short30.stats.jsonl > $G/short30.log 2>&1 < /dev/null
log "gate 2 done: $(grep -E '^\[' $G/short30.log | tail -1); failures=$(grep -c 'AGENT FAILURE\|engine error\|ILLEGAL\|still compiling\|timeout\|forfeit' $G/short30.log)"; grep -E '^terminations' $G/short30.log | tail -1 | tee -a $S
log "pod queue done"
