#!/bin/bash
# On the x86 box: when book pass 1 has finished, merge its two files and grade every entry with
# Stockfish at 120k nodes (drop > 15 cp). Output ~/chess/data/book_v5/book_pass1.json.
cd ~/chess/bini_v5 || exit 1
while pgrep -f "make_book.py --epd tools/book_positions_5.txt" > /dev/null; do sleep 120; done
nice -n 5 ../aichessathon-starter/.venv/bin/python tools/book_merge.py ~/chess/data/book_v5/book_0.json ~/chess/data/book_v5/book_1.json --out ~/chess/data/book_v5/book_pass1.json --stockfish ~/chess/Stockfish/src/stockfish --nodes 120000 --max-loss 15 > ~/chess/data/book_v5/merge_pass1.log 2>&1
echo "$(date '+%F %T') $(tail -1 ~/chess/data/book_v5/merge_pass1.log)"
