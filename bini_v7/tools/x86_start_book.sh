#!/bin/bash
# On the x86 box: replace two S1 generator workers (ids 76, 77) with two book-analysis workers over
# tools/book_positions_5.txt (30 s per position, V4 net, 6-ply lines). Output ~/chess/data/book_v5.
cd ~/chess/bini_v5 || exit 1
for p in $(ps -eo pid,args | grep "[s]elfplay_sf.py" | grep -E "worker-offset 7[67]" | awk '{print $1}'); do kill "$p" 2>/dev/null; done
sleep 2
mkdir -p ~/chess/data/book_v5
N=$(wc -l < tools/book_positions_5.txt | tr -d ' '); H=$(( (N+1)/2 ))
for w in 0 1; do
  nohup nice -n 5 ../aichessathon-starter/.venv/bin/python tools/make_book.py --epd tools/book_positions_5.txt --ms 30000 --plies 6 --start $((w*H)) --count $H --out ~/chess/data/book_v5/book_$w.json > ~/chess/data/book_v5/worker_$w.log 2>&1 < /dev/null &
done
sleep 5
echo "book workers: $(pgrep -f make_book.py | wc -l), S1 workers: $(ps -eo args | grep -c '[s]elfplay_sf.py --out'), positions $N"
