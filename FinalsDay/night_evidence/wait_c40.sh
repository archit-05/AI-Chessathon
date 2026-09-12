#!/bin/bash
# wait for the VM contempt-40 gate (100 games) then fetch log+stats, write the pair-level report and the match odds
SP="/private/tmp/claude-501/-Users-architbhardwaj-Desktop-AI-Chessathon/edc9c181-8258-4c54-8a6f-0a83813055f3/scratchpad"
R="/Users/architbhardwaj/Desktop/AI Chessathon"; E="$R/FinalsDay/night_evidence"
while :; do
  L=$(perl -e 'alarm 40; exec @ARGV' ssh -o BatchMode=yes priorcrypto-vm 'grep -E "^\[" ~/chess/gates/c40_vm.log | tail -1' 2>/dev/null)
  echo "$(date '+%H:%M') $L" | cut -c1-140
  echo "$L" | grep -q "^\[100/100\]" && break
  [ "$(date +%H%M)" -ge 1000 ] && { echo "cap reached at 10:00, reading what exists"; break; }
  sleep 300
done
rsync -az priorcrypto-vm:chess/gates/c40_vm.log priorcrypto-vm:chess/gates/c40_vm.stats.jsonl priorcrypto-vm:chess/gates/c40_vm.pgn "$E/" 2>/dev/null
python3 "$E/book_gate_report.py" "$E/c40_vm.log" "$E/c40_vm.stats.jsonl" > "$E/c40_vm_report.json" 2>&1; cat "$E/c40_vm_report.json" | head -40
L=$(grep -E "^\[" "$E/c40_vm.log" | tail -1); W=$(echo "$L" | sed -nE 's/.*\+([0-9]+) =.*/\1/p'); D=$(echo "$L" | sed -nE 's/.*=([0-9]+) -.*/\1/p'); Lo=$(echo "$L" | sed -nE 's/.*-([0-9]+)  score.*/\1/p')
echo "final: $L"; python3 "$SP/match_odds.py" "$W" "$D" "$Lo"
echo "C40 GATE DONE $(date)"
