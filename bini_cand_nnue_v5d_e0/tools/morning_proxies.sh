#!/bin/bash
# (re-created after the working-copy loss; the original instance is still running from its open
# file handle) real-clock proxy matches: v4o2 vs 20k, v4o2 vs 40k, V3 vs 40k; 2 x 20 games each.
cd "$(dirname "$0")/.."
PY=../aichessathon-starter/.venv/bin/python
until grep -q terminations ../bini/tests/arena/v4o2_vs_v3.log 2>/dev/null && grep -q terminations ../bini/tests/arena/v4o3_vs_v3.log 2>/dev/null; do sleep 120; done
run_pair() { d=$1; n=$2; t=$3; echo "$(date '+%F %T') proxy $t"; ( cd $d && BINI_TT_BITS=24 $PY tools/proxy_match.py --games 20 --nodes $n --start 0 --stockfish /opt/homebrew/bin/stockfish > ../data/proxy_${t}_a.log 2>&1 ) & ( cd $d && BINI_TT_BITS=24 $PY tools/proxy_match.py --games 20 --nodes $n --start 20 --stockfish /opt/homebrew/bin/stockfish > ../data/proxy_${t}_b.log 2>&1 ) & wait; echo "$(date '+%F %T') $t: $(grep 'PROXY MATCH' ../data/proxy_${t}_a.log | cut -c1-60) | $(grep 'PROXY MATCH' ../data/proxy_${t}_b.log | cut -c1-60)"; }
run_pair ../bini_v4o2 20000 v4o2_20k; run_pair ../bini_v4o2 40000 v4o2_40k; run_pair ../bini_v3b 40000 v3_40k
echo "$(date '+%F %T') morning proxies done"
