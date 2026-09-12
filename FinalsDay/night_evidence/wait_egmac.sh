#!/bin/bash
SP="/private/tmp/claude-501/-Users-architbhardwaj-Desktop-AI-Chessathon/edc9c181-8258-4c54-8a6f-0a83813055f3/scratchpad"; E="/Users/architbhardwaj/Desktop/AI Chessathon/FinalsDay/night_evidence"
while :; do
  L=$(grep -E "^\[" "$SP/gates/eg_mac.log" | tail -1); echo "$(date '+%H:%M') $L" | cut -c1-140
  echo "$L" | grep -q "^\[60/60\]" && break
  ps -eo args | grep -q "[a]rena_par.py --agent $SP/cands/cand_sfbook_eg" || { echo "arena process gone"; break; }
  sleep 600
done
cp "$SP/gates/eg_mac.log" "$SP/gates/eg_mac.stats.jsonl" "$SP/gates/eg_mac.pgn" "$E/" 2>/dev/null
python3 "$E/book_gate_report.py" "$E/eg_mac.log" "$E/eg_mac.stats.jsonl" > "$E/eg_mac_report.json" 2>&1; head -30 "$E/eg_mac_report.json"
echo "failures: $(grep -c 'AGENT FAILURE\|engine error\|ILLEGAL\|still compiling' "$SP/gates/eg_mac.log")"; echo "EG MAC DONE $(date)"
