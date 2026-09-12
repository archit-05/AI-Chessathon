#!/bin/bash
# Assemble the SF-book candidate (exact V8.5 + merged book + wrapper guards/instrumentation), audit, smoke, freeze (manifest), gate at 120+0.5 vs V8.5 as shipped.
# usage: book_gate.sh <merged_book.json> [games=300] [workers=6]
set -u; cd ~/chess; V=~/chess/venv/bin/python; G=~/chess/gates; BOOK="$1"; GAMES=${2:-300}; W=${3:-6}
rm -rf cand_sfbook; cp -r bini_astra_v5_noc2b cand_sfbook; rm -rf cand_sfbook/__pycache__; cp "$BOOK" cand_sfbook/book.json
$V bookbuild/patch_guards.py cand_sfbook
mkdir -p cand_sfbook/tools; cp tools_v85/arena_par.py tools_v85/curated.epd cand_sfbook/tools/
echo "== $(date) candidate = V8.5 + book $(sha256sum "$BOOK" | cut -c1-16) + wrapper guards" | tee $G/sfbook.summary
$V bookbuild/book_audit.py cand_sfbook/book.json bookbuild/roots.epd | tee -a $G/sfbook.summary
( cd cand_sfbook && sha256sum agent.py bini_*.py nnue.safetensors book.json ) | tee $G/sfbook_manifest.txt
$V pkg_smoke.py cand_sfbook sfbook 2>&1 | tee -a $G/sfbook.summary
sha256sum $G/sfbook.zip | tee -a $G/sfbook_manifest.txt
export BINI_JOIN_S=300; rm -f $G/sfbook_real.log $G/sfbook_real.pgn $G/sfbook_real.stats.jsonl
nohup $V cand_sfbook/tools/arena_par.py --agent ~/chess/cand_sfbook --opponent ~/chess/bini_astra_v5_noc2b --games $GAMES --base-ms 120000 --inc-ms 500 --workers $W --openings cand_sfbook/tools/curated.epd --pgn-out $G/sfbook_real.pgn --stats-out $G/sfbook_real.stats.jsonl > $G/sfbook_real.log 2>&1 < /dev/null &
echo "gate started $(date) games=$GAMES workers=$W" | tee -a $G/sfbook.summary
