#!/bin/bash
# On the x86 box: when the first book pass (two make_book workers) has finished, run the second
# pass over tools/book_positions_deep.txt (positions seen 3-4 times, and the few deeper ones) at
# 20 s per position, two workers, into ~/chess/data/book_v5/deep_<w>.json.
cd ~/chess/bini_v5 || exit 1
while pgrep -f "make_book.py --epd tools/book_positions_5.txt" > /dev/null; do sleep 120; done
N=$(wc -l < tools/book_positions_deep.txt | tr -d ' '); H=$(( (N+1)/2 ))
for w in 0 1; do
  nohup nice -n 5 ../aichessathon-starter/.venv/bin/python tools/make_book.py --epd tools/book_positions_deep.txt --ms 20000 --plies 6 --start $((w*H)) --count $H --out ~/chess/data/book_v5/deep_$w.json > ~/chess/data/book_v5/deep_worker_$w.log 2>&1 < /dev/null &
done
echo "$(date '+%F %T') deep book pass started: $N positions"
