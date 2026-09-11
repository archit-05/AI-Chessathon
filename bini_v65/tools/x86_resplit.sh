#!/bin/bash
# On the x86 box: 4 S1 workers (ids 70-73) + 2 endgame workers (ids 80-81: site games from ply 40-90,
# depth 12, resolved, results kept) + the book workers. Run after the screens finish.
cd ~/chess/bini_v5 || exit 1
for p in $(ps -eo pid,args | grep "[s]elfplay_sf.py --out" | grep -E "worker-offset 7[4-7] " | awk '{print $1}'); do kill -9 "$p" 2>/dev/null; done
sleep 2; for p in $(ps -eo pid,ppid,comm | awk '$2==1 && $3=="stockfish" {print $1}'); do kill -9 "$p" 2>/dev/null; done
mkdir -p ~/chess/data/selfplay/eg3
for w in 0 1; do
  nohup ../venv/bin/python tools/selfplay_sf.py --out "$HOME/chess/data/selfplay/eg3" --workers 1 --worker-offset $((80 + w)) --seed $((211 + w)) --depth 12 --positions 20000000 --stockfish "$HOME/chess/Stockfish/src/stockfish" --from-games "$HOME/chess/data/site_games" --ply-min 40 --ply-max 90 --resolve --adj-cp 800 > ../data/selfplay/eg3_$w.log 2>&1 < /dev/null &
done
sleep 20
echo "$(date '+%F %T') x86: S1 $(ps -eo args | grep -c '[s]elfplay_sf.py --out .*dec2') procs, eg3 $(ps -eo args | grep -c '[s]elfplay_sf.py --out .*eg3') procs, book $(pgrep -fc make_book)"
