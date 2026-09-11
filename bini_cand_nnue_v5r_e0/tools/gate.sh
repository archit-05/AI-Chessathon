#!/bin/bash
# Arena gate on the tournament's own opening positions.
#   bash tools/gate.sh <candidate_dir> <baseline_dir> <games> <base_ms> <inc_ms> <workers> <tag>
# e.g. bash tools/gate.sh ../bini_v4 ../bini_v3b 300 10000 100 6 v4a_vs_v3
# Log and PGN land in ../bini/tests/arena/<tag>.{log,pgn} like every earlier gate.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=../aichessathon-starter/.venv/bin/python
cand=$1; base=$2; games=${3:-300}; bms=${4:-10000}; ims=${5:-100}; workers=${6:-6}; tag=${7:-gate}
mkdir -p ../bini/tests/arena
echo "$(date '+%F %T') gate $tag: $cand vs $base, $games games at ${bms}+${ims} ms, $workers workers, curated openings" | tee ../bini/tests/arena/$tag.log
BINI_JOIN_S=85 $PY tools/arena_par.py --agent "$cand" --opponent "$base" --games "$games" --base-ms "$bms" --inc-ms "$ims" --workers "$workers" --openings tools/curated.epd --pgn-out ../bini/tests/arena/$tag.pgn 2>&1 | tee -a ../bini/tests/arena/$tag.log | grep -E "^\[|terminations|FAILURE|NOTE" | tail -3
