#!/bin/bash
# gcp-x86: real-clock (120+0.5) gate of one build directory against another, with manifest, package smoke and stats sidecar.
# usage: pair_gate.sh <cand_dir> <opp_dir> <tag> [games=150] [workers=6]     (refuses to start while another arena runs)
# examples: pair_gate.sh cand_sfbook_eg cand_sfbook eg_vs_book 150        # endgame honesty alone
#           pair_gate.sh cand_sfbook_c40eg bini_astra_v5_noc2b final_vs_v85 150   # the full package vs the Swiss build
set -u; cd ~/chess; V=~/chess/venv/bin/python; G=~/chess/gates; C="$1"; O="$2"; TAG="$3"; N=${4:-150}; W=${5:-6}; export BINI_JOIN_S=300
ps -eo args | grep -q "[a]rena_par.py" && { echo "another arena is running; refusing to start"; exit 1; }
[ -d "$C" ] && [ -d "$O" ] || { echo "missing build dir"; exit 1; }
mkdir -p "$C/tools"; cp cand_sfbook/tools/arena_par.py cand_sfbook/tools/curated.epd "$C/tools/"
(cd "$C" && sha256sum agent.py bini_*.py nnue.safetensors book.json 2>/dev/null) > $G/${TAG}_cand_manifest.txt
$V pkg_smoke.py "$C" smoke_${TAG} 2>&1 | tail -3
setsid nohup $V "$C/tools/arena_par.py" --agent ~/chess/"$C" --opponent ~/chess/"$O" --games $N --base-ms 120000 --inc-ms 500 --workers $W --openings "$C/tools/curated.epd" --pgn-out $G/$TAG.pgn --stats-out $G/$TAG.stats.jsonl > $G/$TAG.log 2>&1 < /dev/null &
echo "started $TAG ($C vs $O): $N games, $W workers; progress: grep -E '^\[' $G/$TAG.log | tail -1; report: $V bookbuild/book_gate_report.py $G/$TAG.log $G/$TAG.stats.jsonl"
