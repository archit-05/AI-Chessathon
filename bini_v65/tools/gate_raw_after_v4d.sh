#!/bin/bash
# second candidate: the raw-scale v4b net (slope 1.11) vs V3, two workers, once v4d has started
cd "$(dirname "$0")/.."
PY=../aichessathon-starter/.venv/bin/python
until grep -q "starting v4d" ../data/overnight.log 2>/dev/null; do sleep 120; done
while true; do l=$(uptime | sed 's/.*load averages*: *//' | cut -d' ' -f1 | tr -d ','); ok=$($PY -c "print(1 if float('$l') <= 10 else 0)"); [ "$ok" = "1" ] && break; sleep 120; done
echo "$(date '+%F %T') gate v4b_raw vs V3 (two workers)"
BINI_TT_BITS=22 bash tools/gate.sh ../bini_v4b_raw ../bini_v3b 300 10000 100 2 v4b_raw_vs_v3
echo "$(date '+%F %T') raw gate done"
