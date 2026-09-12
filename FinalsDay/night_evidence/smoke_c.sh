#!/bin/bash
# pod 3: real-clock smoke of the chosen contempt variant vs V14 (contempt 60), both bp336, harness init budget 30 s.
# usage: smoke_c.sh <cand_zip> <opp_zip> <games> <tag>   (waits for any fixed-node screen to finish first)
set -u; cd ~/chess; V=~/chess/venv/bin/python; CZ="$1"; OZ="$2"; N="$3"; TAG="$4"
while ps -eo args | grep -q "[n]ode_gate.py"; do sleep 20; done
for Z in "$CZ" "$OZ"; do D=${Z%.zip}; rm -rf "$D"; mkdir -p "$D" && (cd "$D" && $V -c "import zipfile; zipfile.ZipFile('/root/chess/$Z').extractall('.')"); mkdir -p "$D/tools"; cp arena_tools/arena_par.py arena_tools/curated.epd "$D/tools/"; done
C=${CZ%.zip}; O=${OZ%.zip}; echo "$(date '+%F %T') smoke $TAG: $C vs $O, $N games, 8 workers" | tee -a logs/smoke.status
env -u BINI_JOIN_S $V "$C/tools/arena_par.py" --agent ~/chess/"$C" --opponent ~/chess/"$O" --games "$N" --base-ms 120000 --inc-ms 500 --workers 8 --seed 23 --openings "$C/tools/curated.epd" --pgn-out gates/$TAG.pgn --stats-out gates/$TAG.stats.jsonl > gates/$TAG.log 2>&1 < /dev/null
echo "$(date '+%F %T') smoke $TAG done: $(grep -E '^\[' gates/$TAG.log | tail -1); failures=$(grep -c 'AGENT FAILURE\|engine error\|ILLEGAL\|BUILD FAILED' gates/$TAG.log); init-losses=$(grep -c 'by init' gates/$TAG.log)" | tee -a logs/smoke.status
grep -E '^terminations' gates/$TAG.log | tail -1 | tee -a logs/smoke.status
