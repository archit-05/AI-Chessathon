#!/bin/bash
# wait for the morning chain's book report, copy it into the evidence dir, then report what the chain does next
R="/Users/architbhardwaj/Desktop/AI Chessathon"; E="$R/FinalsDay/night_evidence"
while :; do
  perl -e 'alarm 40; exec @ARGV' ssh -o BatchMode=yes gcp-x86 'test -s ~/chess/gates/sfbook_report.json' 2>/dev/null && break
  echo "$(date '+%H:%M') $(perl -e 'alarm 40; exec @ARGV' ssh -o BatchMode=yes gcp-x86 'grep -E "^\[" ~/chess/gates/sfbook_real.log | tail -1' 2>/dev/null | cut -c1-120)"
  sleep 300
done
rsync -az gcp-x86:~/chess/gates/sfbook_report.json gcp-x86:~/chess/gates/sfbook_real.log gcp-x86:~/chess/gates/sfbook_real.stats.jsonl gcp-x86:~/chess/gates/sfbook_real.pgn gcp-x86:~/chess/gates/morning_chain.status "$E/" 2>/dev/null
echo "=== book report ==="; cat "$E/sfbook_report.json" | head -60; echo "=== chain ==="; cat "$E/morning_chain.status"
echo "BOOK REPORT DONE $(date)"
