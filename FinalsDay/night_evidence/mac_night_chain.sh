#!/bin/bash
# Mac, after the leaf dump: profile -> sync dumps to GCP stage -> label a stratified 100k pilot at depth 12 (3 workers)
# while mining decision errors from 150 self-play games at depth 12 (3 workers). Logs in $SP/out.
SP="$1"; R="/Users/architbhardwaj/Desktop/AI Chessathon"; PY="$R/aichessathon-starter/.venv/bin/python"; S="$SP/out/mac_chain.status"
echo "$(date) waiting for leaf dump" > "$S"
while ! grep -q "^done" "$SP/out/leaf_mac.log" 2>/dev/null; do sleep 60; done
echo "$(date) leaf dump done: $(wc -l < "$SP/out/leaf_mac.jsonl") rows" >> "$S"
"$PY" "$SP/leaf_profile.py" "$SP/out/leaf_mac.jsonl" --corpus-npz ~/chess_d10_mirror/labelled_d10/shard_400000.npz > "$SP/out/leaf_mac_profile.json" 2>&1
echo "$(date) profile written" >> "$S"
ssh gcp-x86 'mkdir -p ~/chess/data/stage/leaf' && rsync -az "$SP/out/leaf_mac.jsonl" "$SP/out/leaf_mac_profile.json" gcp-x86:~/chess/data/stage/leaf/ && echo "$(date) leaf_mac synced to gcp stage" >> "$S"
( "$PY" "$SP/mine_errors.py" "$SP/out/errors_mac.jsonl" "$R/astra_reports/gate_mirror/out/gateA.pgn" --stockfish /opt/homebrew/bin/stockfish --workers 3 --depth 12 --loss 100 --player both --limit 150 > "$SP/out/errors_mac.log" 2>&1; echo "$(date) miner done: $(wc -l < "$SP/out/errors_mac.jsonl") errors" >> "$S" ) &
"$PY" "$SP/label_leaf.py" "$SP/out/leaf_mac.jsonl" "$SP/out/leaf_labels_mac" --stockfish /opt/homebrew/bin/stockfish --workers 3 --depth 12 --stratify --limit 100000 --batch 100 > "$SP/out/label_mac.log" 2>&1
echo "$(date) labelling done: $(wc -l < "$SP/out/leaf_labels_mac.labels.jsonl" 2>/dev/null) labelled" >> "$S"
wait
rsync -az "$SP/out/leaf_labels_mac"* "$SP/out/errors_mac.jsonl" gcp-x86:~/chess/data/stage/leaf/ 2>/dev/null
scp -q priorcrypto-vm:chess/bookbuild/leaf_vm.jsonl "$SP/out/leaf_vm.jsonl" 2>/dev/null && rsync -az "$SP/out/leaf_vm.jsonl" gcp-x86:~/chess/data/stage/leaf/ 2>/dev/null
scp -q priorcrypto-vm:chess/bookbuild/errors_vm.jsonl "$SP/out/errors_vm.jsonl" 2>/dev/null && rsync -az "$SP/out/errors_vm.jsonl" gcp-x86:~/chess/data/stage/leaf/ 2>/dev/null
rsync -az "$SP/out/site_spice_12_23.npz" "$SP/out/site_spice_12_23.jsonl" gcp-x86:~/chess/data/stage/leaf/ 2>/dev/null && echo "$(date) site spice synced" >> "$S"
echo "$(date) mac chain done" >> "$S"
