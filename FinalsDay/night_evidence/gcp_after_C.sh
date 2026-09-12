#!/bin/bash
# gcp-x86: once combo C (bp144_d7_ft + book vs V8.5) has its report, stop the chain's combo A (attribution only) and run the
# shipping-relevant gates instead: (1) the full package on the current net, cand_sfbook_c40eg vs V8.5; (2) if combo C is
# positive, the full package on the new net (bp144_d7_ft + book + contempt 40 + endgame fix) vs V8.5. 120 games each.
set -u; cd ~/chess; V=~/chess/venv/bin/python; G=~/chess/gates; S=$G/after_chain.status
log() { echo "$(date '+%F %T') $*" | tee -a $S; }
log "waiting for combo C report"; while [ ! -s $G/combo_bp144_d7_ft_C_report.json ]; do sleep 120; done
CE=$($V -c "import json; print(json.load(open('$G/combo_bp144_d7_ft_C_report.json'))['pair_elo'])" 2>/dev/null || echo 0)
log "combo C pair_elo = $CE; stopping the chain and combo A"
ps -eo pid,args | grep "[m]orning_gate_chain" | awk '{print $1}' | xargs -r kill; sleep 2
ps -eo pid,args | grep "[a]rena_par.py --agent /home/forge/chess/cand_net_bp144_d7_ft" | awk '{print $1}' | xargs -r kill; sleep 5
ps -eo pid,args | grep "[h]arness.runner" | awk '{print $1}' | xargs -r kill; sleep 5
log "gate 1: cand_sfbook_c40eg vs V8.5 (120 games)"; bash pair_gate.sh cand_sfbook_c40eg bini_astra_v5_noc2b final_c40eg_vs_v85 120 6 2>&1 | tee -a $S
while ! grep -q "^\[120/120\]" $G/final_c40eg_vs_v85.log 2>/dev/null; do sleep 120; done
$V bookbuild/book_gate_report.py $G/final_c40eg_vs_v85.log $G/final_c40eg_vs_v85.stats.jsonl > $G/final_c40eg_vs_v85_report.json 2>&1; log "gate 1 done: $(grep -E '^\[' $G/final_c40eg_vs_v85.log | tail -1)"
if $V -c "import sys; sys.exit(0 if float('$CE') > 0 else 1)"; then
  rm -rf cand_final_bp144; cp -r cand_netbook_bp144_d7_ft cand_final_bp144; rm -rf cand_final_bp144/__pycache__
  sed -i 's/os.environ.get("BINI_CONTEMPT", "20")/os.environ.get("BINI_CONTEMPT", "40")/' cand_final_bp144/bini_engine.py
  $V patch_endgame.py cand_final_bp144 2>&1 | tee -a $S
  grep -q 'BINI_CONTEMPT", "40"' cand_final_bp144/bini_engine.py && grep -q "EG_DRAW" cand_final_bp144/bini_search.py || { log "cand_final_bp144 patch failed"; exit 1; }
  $V build_packages.py cand_final_bp144:submission_V9_bp144_book_c40eg.zip | grep -v "^    " | tee -a $S
  log "gate 2: cand_final_bp144 (bp144_d7_ft + book + c40 + eg) vs V8.5 (120 games)"; bash pair_gate.sh cand_final_bp144 bini_astra_v5_noc2b final_bp144_vs_v85 120 6 2>&1 | tee -a $S
  while ! grep -q "^\[120/120\]" $G/final_bp144_vs_v85.log 2>/dev/null; do sleep 120; done
  $V bookbuild/book_gate_report.py $G/final_bp144_vs_v85.log $G/final_bp144_vs_v85.stats.jsonl > $G/final_bp144_vs_v85_report.json 2>&1; log "gate 2 done: $(grep -E '^\[' $G/final_bp144_vs_v85.log | tail -1)"
else
  log "combo C not positive: no gate on the new net; V8.5-net packages only"
fi
log "after-chain done"
