#!/bin/bash
# On the x86 box: replace the four S1 generators with four elite-game labellers (Lichess Elite
# 2025-05, positions after ply 10 sampled at 25%, Stockfish 19 depth 10), output ~/chess/data/elite2.
cd ~/chess/bini_v5 || exit 1
for p in $(ps -eo pid,args | grep "[s]elfplay_sf.py --out" | grep dec2 | awk '{print $1}'); do kill -9 "$p" 2>/dev/null; done
sleep 2; for p in $(ps -eo pid,ppid,comm | awk '$2==1 && $3=="stockfish" {print $1}'); do kill -9 "$p" 2>/dev/null; done
cd ~/chess/data/elite && [ -f lichess_elite_2025-05.pgn ] || unzip -o -q lichess_elite_2025-05.zip
PGN=$(ls ~/chess/data/elite/*2025-05*.pgn | head -1)
mkdir -p ~/chess/data/elite2
cd ~/chess/bini_v5
PATH=$HOME/chess/Stockfish/src:$PATH nohup nice -n 5 ../venv/bin/python tools/label_positions.py "$PGN" ~/chess/data/elite2 --positions 3000000 --depth 10 --workers 4 > ~/chess/data/elite2.log 2>&1 < /dev/null &
sleep 30; tail -3 ~/chess/data/elite2.log
echo "$(date '+%F %T') x86: label $(pgrep -fc label_positions) eg3 $(ps -eo args | grep -c '[s]elfplay_sf.py --out .*eg3') book $(pgrep -fc make_book) stockfish $(pgrep -xc stockfish)"
