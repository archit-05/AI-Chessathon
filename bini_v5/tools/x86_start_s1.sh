#!/bin/bash
# On the x86 box: 8 S1 workers (decisive games from random plies 8-40 of the site's games),
# same flags as the VM's vm_start_s1.sh; worker ids 70-77 so chunk names never collide.
cd ~/chess/bini_v4 || exit 1
for p in $(ps -eo pid,args | grep "[s]elfplay_sf.py" | grep -v x86_start | awk '{print $1}'); do kill "$p" 2>/dev/null; done
sleep 3
mkdir -p ~/chess/data/selfplay/dec2
for w in 0 1 2 3 4 5 6 7; do
  nohup ../venv/bin/python tools/selfplay_sf.py --out "$HOME/chess/data/selfplay/dec2" --workers 1 --worker-offset $((70 + w)) --seed $((101 + w)) --depth 9 --positions 20000000 --stockfish "$HOME/chess/Stockfish/src/stockfish" --from-games "$HOME/chess/data/site_games" --ply-min 8 --ply-max 40 --random-open 0.5 --balance --resolve --adj-cp 800 > ../data/selfplay/dec2/gen_$w.log 2>&1 < /dev/null &
done
sleep 60
tail -n 1 ../data/selfplay/dec2/worker_7*.log 2>/dev/null
echo "generators: $(ps -eo args | grep -c '[s]elfplay_sf.py --out')  load: $(uptime | sed 's/.*load/load/')"
