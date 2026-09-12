#!/bin/bash
# VM, after its leaf dump: mine decision errors from 80 self-play games (gateB) at depth 12 with 4 workers.
cd ~/chess/bookbuild; PY=~/chess/aichessathon-starter/.venv/bin/python; S=~/chess/bookbuild/vm_chain.status
echo "$(date) waiting for leaf dump" > $S
while ! grep -q "^done" leaf_vm.log 2>/dev/null; do sleep 60; done
echo "$(date) leaf dump done: $(wc -l < leaf_vm.jsonl) rows" >> $S
$PY mine_errors.py errors_vm.jsonl gateB.pgn --stockfish ~/chess/Stockfish/src/stockfish --workers 4 --depth 12 --loss 100 --player both --limit 80 > errors_vm.log 2>&1
echo "$(date) miner done: $(wc -l < errors_vm.jsonl) errors" >> $S
