#!/bin/bash
E="/Users/architbhardwaj/Desktop/AI Chessathon/FinalsDay/night_evidence"
while :; do
  S=$(perl -e 'alarm 40; exec @ARGV' ssh -o BatchMode=yes gcp-x86 'grep -E "^\[" ~/chess/gates/combo_bp144_d7_ft_C.log 2>/dev/null | tail -1; test -s ~/chess/gates/combo_bp144_d7_ft_C_report.json && echo REPORT_READY' 2>/dev/null | tr "\n" " ")
  echo "$(date '+%H:%M') $S" | cut -c1-160
  echo "$S" | grep -q "REPORT_READY" && break
  sleep 600
done
rsync -az gcp-x86:~/chess/gates/combo_bp144_d7_ft_C_report.json gcp-x86:~/chess/gates/combo_bp144_d7_ft_C.log gcp-x86:~/chess/gates/combo_bp144_d7_ft_C.stats.jsonl gcp-x86:~/chess/gates/morning_chain.status "$E/" 2>/dev/null
python3 -c "
import json; r=json.load(open('$E/combo_bp144_d7_ft_C_report.json')); print('COMBO C bp144_d7_ft + book vs V8.5:', r['of'], 'games W/D/L', r['W'], r['D'], r['L'], 'pair_elo', r['pair_elo'], r['pair_elo_95'], 'pent', r['pentanomial'], 'failures', r['failures'])"
echo "COMBO C DONE $(date)"
