#!/bin/bash
# gcp-x86: must-win confirmation gate. cand_sfbook_c40 (book + contempt 40) vs cand_sfbook (book), 120+0.5, stats sidecar.
# usage: c40_gate.sh [games=200] [workers=6] [tag=c40_gcp]   (run only when no other arena is on the box)
set -u; cd ~/chess; V=~/chess/venv/bin/python; G=~/chess/gates; N=${1:-200}; W=${2:-6}; TAG=${3:-c40_gcp}; export BINI_JOIN_S=300
ps -eo args | grep -q "[a]rena_par.py" && { echo "another arena is running; refusing to start"; exit 1; }
[ -d cand_sfbook_c40 ] || { rm -rf cand_sfbook_c40; cp -r cand_sfbook cand_sfbook_c40; rm -rf cand_sfbook_c40/__pycache__; sed -i 's/os.environ.get("BINI_CONTEMPT", "20")/os.environ.get("BINI_CONTEMPT", "40")/' cand_sfbook_c40/bini_engine.py; }
grep -q 'BINI_CONTEMPT", "40"' cand_sfbook_c40/bini_engine.py || { echo "contempt patch missing"; exit 1; }
mkdir -p cand_sfbook_c40/tools; cp cand_sfbook/tools/arena_par.py cand_sfbook/tools/curated.epd cand_sfbook_c40/tools/
(cd cand_sfbook_c40 && sha256sum agent.py bini_*.py nnue.safetensors book.json) > $G/cand_sfbook_c40_manifest.txt
$V pkg_smoke.py cand_sfbook_c40 smoke_cand_sfbook_c40 2>&1 | tail -3
setsid nohup $V cand_sfbook_c40/tools/arena_par.py --agent ~/chess/cand_sfbook_c40 --opponent ~/chess/cand_sfbook --games $N --base-ms 120000 --inc-ms 500 --workers $W --openings cand_sfbook_c40/tools/curated.epd --pgn-out $G/$TAG.pgn --stats-out $G/$TAG.stats.jsonl > $G/$TAG.log 2>&1 < /dev/null &
echo "started $TAG: $N games, $W workers; read with: $V bookbuild/book_gate_report.py $G/$TAG.log $G/$TAG.stats.jsonl"
