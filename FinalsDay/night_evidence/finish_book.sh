#!/bin/bash
# After the main GCP shard: mop up the Mac residues (10-12) then the VM residues (6-9) at 4 plies, seeded with
# whatever those machines have finished (their jsonl files are synced here every 10 min), merge with the old book
# as fallback for uncovered roots, smoke the package, start the 120+0.5 gate.
set -u; cd ~/chess/bookbuild; V=~/chess/venv/bin/python; S=~/chess/gates/finish_book.status; SF=~/chess/Stockfish/src/stockfish
echo "$(date) waiting for main shard" > $S
while ! grep -q "^done" sfbook_gcp.log 2>/dev/null; do sleep 60; done
echo "$(date) main shard done: $(wc -l < sfbook_gcp.jsonl) entries" >> $S
touch sfbook_mac.jsonl sfbook_vm.jsonl
$V sf_book.py roots.epd sfbook_mac.jsonl --stockfish $SF --workers 6 --shard 10,11,12/13 --plies 4 --nodes 800000 > sfbook_gcp_mac.log 2>&1
echo "$(date) mac residues done: $(wc -l < sfbook_mac.jsonl) entries" >> $S
$V sf_book.py roots.epd sfbook_vm.jsonl --stockfish $SF --workers 6 --shard 6,7,8,9/13 --plies 4 --nodes 800000 > sfbook_gcp_vm.log 2>&1
echo "$(date) vm residues done: $(wc -l < sfbook_vm.jsonl) entries" >> $S
$V merge_book.py ~/chess/bookbuild/book_sf.json --roots roots.epd --base ~/chess/bini_astra_v5_noc2b/book.json sfbook_gcp.jsonl sfbook_mac.jsonl sfbook_vm.jsonl >> $S 2>&1
cd ~/chess && bash book_gate.sh ~/chess/bookbuild/book_sf.json 300 6 >> $S 2>&1
echo "$(date) finish_book done" >> $S
