#!/bin/bash
# (re-created) softer clock on the v4o2 net vs the 40k proxy after the morning proxies.
cd "$(dirname "$0")/.."
PY=../aichessathon-starter/.venv/bin/python
until grep -q "morning proxies done" ../data/morning_proxies.log 2>/dev/null; do sleep 120; done
( cd ../bini_v4o2_soft && BINI_TT_BITS=24 $PY tools/proxy_match.py --games 20 --nodes 40000 --start 0 --stockfish /opt/homebrew/bin/stockfish > ../data/proxy_v4o2soft_40k_a.log 2>&1 ) & ( cd ../bini_v4o2_soft && BINI_TT_BITS=24 $PY tools/proxy_match.py --games 20 --nodes 40000 --start 20 --stockfish /opt/homebrew/bin/stockfish > ../data/proxy_v4o2soft_40k_b.log 2>&1 ) & wait
echo "$(date '+%F %T') v4o2_soft_40k: $(grep 'PROXY MATCH' ../data/proxy_v4o2soft_40k_a.log | cut -c1-60) | $(grep 'PROXY MATCH' ../data/proxy_v4o2soft_40k_b.log | cut -c1-60)"
