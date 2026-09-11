#!/bin/bash
# On the VM: restart the two decisive-mode generators with the current flags. Lives in a file so
# the kill pattern is never part of an interactive shell's own command line.
cd ~/chess/bini_v4 || exit 1
for p in $(ps -eo pid,args | grep "[s]elfplay_sf.py" | grep "selfplay/dec" | grep -v vm_restart | awk '{print $1}'); do kill "$p" 2>/dev/null; done
sleep 3
for w in 0 1; do
  nohup ../venv/bin/python tools/selfplay_sf.py --out /home/ubuntu/chess/data/selfplay/dec --workers 1 --worker-offset $((50 + w)) --seed $((17 + w)) --depth 9 --positions 20000000 --stockfish /home/ubuntu/chess/Stockfish/src/stockfish --random-open 0.5 --balance --adj-cp 800 > ../data/selfplay/dec/gen2_$w.log 2>&1 < /dev/null &
done
sleep 45
tail -n 1 ../data/selfplay/dec/worker_50.log ../data/selfplay/dec/worker_51.log
echo "generators: $(ps -eo args | grep -c '[s]elfplay_sf.py')  load: $(uptime | sed 's/.*load/load/')"
