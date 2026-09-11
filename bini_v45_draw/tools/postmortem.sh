#!/bin/bash
# Hourly post-mortem loop: scrape our new rated games, harvest every site-tagged error and its
# neighbourhood, label the new positions at depth 20 on the VM, pull them into data/hard.
#   bash tools/postmortem.sh        (run at :42 past the hour; games finish by ~:35)
set -uo pipefail
cd "$(dirname "$0")/.."
PY=../aichessathon-starter/.venv/bin/python
( cd ../intel && nice -n 15 $PY scrape.py "BINI Alpha" > ../data/postmortem_scrape.log 2>&1 )
nice -n 15 $PY tools/harvest_errors.py --epd tests/pos/harvest.epd --fens ../data/hard_fens.txt > ../data/postmortem_harvest.log 2>&1
tail -1 ../data/postmortem_harvest.log
# hand-picked positions (e.g. R52 moves 30-40) live in hard_fens_extra.txt and are merged every run
[ -f ../data/hard_fens_extra.txt ] && cat ../data/hard_fens_extra.txt >> ../data/hard_fens.txt && sort -u ../data/hard_fens.txt -o ../data/hard_fens.txt
new=$(comm -23 <(sort ../data/hard_fens.txt) <(sort ../data/hard_fens_labelled.txt 2>/dev/null) )
if [ -z "$new" ]; then echo "$(date '+%H:%M') no new hard positions"; exit 0; fi
echo "$new" > ../data/hard_fens_new.txt
n=$(wc -l < ../data/hard_fens_new.txt | tr -d ' ')
stamp=$(date '+%m%d_%H%M')
rsync -az ../data/hard_fens_new.txt priorcrypto-vm:~/chess/data/hard_fens_$stamp.txt
ssh -o BatchMode=yes priorcrypto-vm "cd ~/chess && nice -n 5 ./venv/bin/python bini_v4/tools/label_fens.py data/hard_fens_$stamp.txt data/hard/chunk_$stamp.npz --depth 20 --stockfish ~/chess/Stockfish/src/stockfish > hard_label_$stamp.log 2>&1; tail -1 hard_label_$stamp.log" < /dev/null
rsync -az priorcrypto-vm:~/chess/data/hard/ ../data/hard/
cat ../data/hard_fens_new.txt >> ../data/hard_fens_labelled.txt
echo "$(date '+%H:%M') post-mortem: $n new positions labelled; hard set now $(ls ../data/hard/chunk_*.npz | wc -l | tr -d ' ') chunks"
