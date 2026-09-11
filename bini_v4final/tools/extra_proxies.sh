#!/bin/bash
# After the morning proxies: V3's net against the 20k proxy (the missing baseline), then the marker
# the battery waits for.
cd "/Users/architbhardwaj/Desktop/AI Chessathon/bini_v4" || exit 1
PY=../aichessathon-starter/.venv/bin/python
until grep -q "morning proxies done" ../data/morning_proxies.log 2>/dev/null; do sleep 120; done
echo "$(date '+%F %T') proxy v3_20k"
( cd ../bini_v3b && BINI_TT_BITS=24 $PY tools/proxy_match.py --games 20 --nodes 20000 --start 0 --stockfish /opt/homebrew/bin/stockfish > ../data/proxy_v3_20k_a.log 2>&1 ) &
( cd ../bini_v3b && BINI_TT_BITS=24 $PY tools/proxy_match.py --games 20 --nodes 20000 --start 20 --stockfish /opt/homebrew/bin/stockfish > ../data/proxy_v3_20k_b.log 2>&1 ) &
wait
echo "$(date '+%F %T') v3_20k: $(grep 'PROXY MATCH' ../data/proxy_v3_20k_a.log | cut -c1-60) | $(grep 'PROXY MATCH' ../data/proxy_v3_20k_b.log | cut -c1-60)"
echo "$(date '+%F %T') extra proxies done"
