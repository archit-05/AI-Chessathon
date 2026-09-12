#!/bin/bash
# 04:50 push: assemble GrigoryMorning.md from the template + live status, copy small artefacts into the evidence dir,
# commit, pull --rebase, push (fallback branch if the rebase fails).  usage: morning_push.sh <SP> [dry]
SP="$1"; R="/Users/architbhardwaj/Desktop/AI Chessathon"; cd "$R" || exit 1
ST="$SP/out/push_status.txt"; : > "$ST"
g() { perl -e 'alarm 45; exec @ARGV' ssh -o BatchMode=yes gcp-x86 "$1" 2>/dev/null; }
{
  echo "Written $(date '+%F %H:%M %Z')."
  echo; echo "**Book gate (`gcp-x86:~/chess/gates/sfbook_real.log`)** — read as partial unless it says 300/300:"; echo '```'
  g 'grep -E "^\[" ~/chess/gates/sfbook_real.log | tail -1; grep -c "still compiling\|AGENT FAILURE\|engine error\|ILLEGAL" ~/chess/gates/sfbook_real.log; cat ~/chess/gates/finish_book.status | tail -4'
  echo '```'
  echo; echo "**Gate report so far**:"; echo '```'
  g '~/chess/venv/bin/python ~/chess/bookbuild/book_gate_report.py ~/chess/gates/sfbook_real.log ~/chess/gates/sfbook_real.stats.jsonl 2>&1 | head -60'
  echo '```'
  echo; echo "**Book audit / merge / manifest**:"; echo '```'
  g 'grep -E "entries|Stockfish|coverage" ~/chess/gates/finish_book.status | tail -3; cat ~/chess/gates/sfbook.summary 2>/dev/null | head -12; cat ~/chess/gates/sfbook_manifest.txt 2>/dev/null'
  echo '```'
  echo; echo "**Leaf corpus / labels / errors**:"; echo '```'
  echo "leaf_mac rows: $(wc -l < "$SP/out/leaf_mac.jsonl" 2>/dev/null)"; echo "leaf_vm rows: $(wc -l < "$SP/out/leaf_vm.jsonl" 2>/dev/null)"
  echo "labelled (mac pilot): $(wc -l < "$SP/out/leaf_labels_mac.labels.jsonl" 2>/dev/null)"; echo "errors_mac: $(wc -l < "$SP/out/errors_mac.jsonl" 2>/dev/null)  errors_vm: $(wc -l < "$SP/out/errors_vm.jsonl" 2>/dev/null)"
  cat "$SP/out/mac_chain.status" 2>/dev/null; g 'cat ~/chess/bookbuild/vm_chain.status 2>/dev/null; ls -la ~/chess/data/stage/leaf/ 2>/dev/null'
  echo '```'
  echo; echo "**A-lane on the RunPod A40 (`ssh root@63.141.33.33 -p 22018`, `~/chess/logs/a_lane.status`)**:"; echo '```'
  perl -e 'alarm 45; exec @ARGV' ssh -o BatchMode=yes runpod 'for f in a_lane b_lane a3_site c_lane c2_lane c3_lane align_variants width_ladder screen_queue; do echo "== $f"; cut -c1-200 ~/chess/logs/$f.status 2>/dev/null | tail -12; done; ls ~/chess/data/nets/ 2>/dev/null' 2>/dev/null; echo; echo "gcp morning chain:"; g 'cut -c1-200 ~/chess/gates/morning_chain.status 2>/dev/null'
  echo '```'
  echo; echo "**Mirrored nets on gcp-x86** (`~/chess/data/stage/nets_night/`):"; echo '```'; g 'ls -la ~/chess/data/stage/nets_night/ 2>/dev/null | awk "{print \$5, \$9}"; ls ~/chess/data/stage/leaf/ 2>/dev/null'; echo '```'
  echo; echo "**Must-win gate on the VM (V8.5 + book + contempt 40 vs V8.5 + book, 120+0.5, 100 games, `~/chess/gates/c40_vm.log`)**:"; echo '```'
  perl -e 'alarm 40; exec @ARGV' ssh -o BatchMode=yes priorcrypto-vm 'grep -E "^\[" ~/chess/gates/c40_vm.log | tail -1; grep -c "AGENT FAILURE\|engine error\|ILLEGAL\|still compiling" ~/chess/gates/c40_vm.log' 2>&1
  cat "$SP/out/wait_c40.log" 2>/dev/null | grep -A12 "final:" ; echo; echo "pod draw-shape screen (contempt 40 vs 20, same net, 30k, 576 games, upper bound for strength):"; perl -e 'alarm 40; exec @ARGV' ssh -o BatchMode=yes runpod 'grep SHAPE ~/chess/logs/screen_queue.status | tail -3; grep -E \"^\\\\S+ \\\\[\" ~/chess/gates/eg_30k.log 2>/dev/null | tail -1; grep -E "^\\S+ \\[" ~/chess/gates/c40_30k.log 2>/dev/null | tail -1' 2>&1; echo '```'
  echo; echo "**Endgame-honesty build at the real clock on the Mac (cand_sfbook_eg vs cand_sfbook, 120+0.5, 2 workers, `scratchpad/gates/eg_mac.log`)**:"; echo '```'; grep -E "^\\[" "$SP/gates/eg_mac.log" | tail -1; grep -c "AGENT FAILURE\\|engine error\\|ILLEGAL\\|still compiling" "$SP/gates/eg_mac.log"; echo '```'
  echo; echo "**Morning chain on gcp-x86 (`~/chess/gates/morning_chain.status`)**:"; echo '```'
  g 'cat ~/chess/gates/morning_chain.status | tail -8; for f in ~/chess/gates/combo_*_C.log ~/chess/gates/combo_*_A.log; do [ -f $f ] && echo "$(basename $f): $(grep -E "^\[" $f | tail -1)"; done'; echo '```'
} > "$SP/out/status_block.md" 2>&1
python3 - "$SP/GrigoryMorning.template.md" "$SP/out/status_block.md" "$R/GrigoryMorning.md" <<'PY'
import sys; t=open(sys.argv[1]).read(); s=open(sys.argv[2]).read(); import time
open(sys.argv[3],'w').write(t.replace('__NOW__', time.strftime('%H:%M %Z, %d %B %Y')).replace('__STATUS__', s)); print('GrigoryMorning.md written')
PY
# small artefacts into the evidence dir (never the leaf dumps)
mkdir -p FinalsDay/night_evidence/book
scp -q gcp-x86:~/chess/bookbuild/book_sf.json gcp-x86:~/chess/gates/sfbook_manifest.txt gcp-x86:~/chess/gates/sfbook.summary gcp-x86:~/chess/gates/finish_book.status gcp-x86:~/chess/gates/sfbook_real.log FinalsDay/night_evidence/book/ 2>/dev/null
scp -q gcp-x86:~/chess/data/stage/nets_night/a_lane.status FinalsDay/night_evidence/ 2>/dev/null; scp -q gcp-x86:~/chess/gates/sfbook_real.stats.jsonl gcp-x86:~/chess/gates/sfbook_real.pgn gcp-x86:~/chess/gates/preflight.status gcp-x86:~/chess/gates/pf_instrument.log FinalsDay/night_evidence/book/ 2>/dev/null
cp "$SP/out/leaf_mac_profile.json" "$SP/out/leaf_mac.log" "$SP/out/label_mac.log" "$SP/out/errors_mac.log" "$SP/out/mac_chain.status" FinalsDay/night_evidence/ 2>/dev/null
[ -f "$SP/out/errors_mac.jsonl" ] && cp "$SP/out/errors_mac.jsonl" FinalsDay/night_evidence/
cp "$SP/GrigoryMorning.template.md" "$SP/morning_push.sh" "$SP/mac_night_chain.sh" "$SP/vm_night_chain.sh" FinalsDay/night_evidence/ 2>/dev/null
find FinalsDay/night_evidence -size +45M -print -delete
[ "${2:-}" = "dry" ] && { echo "dry run: not committing"; exit 0; }
git add GrigoryMorning.md "FinalsDay/Finals Night Cause Table.md" FinalsDay/night_evidence "Overnight Plan.md" 2>>"$ST"
git commit -q -m "Finals night: Stockfish book candidate, gate, leaf corpus, error mining, preflight for the pretrain lane; GrigoryMorning.md handover

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" >>"$ST" 2>&1
if git pull -q --rebase --autostash origin main >>"$ST" 2>&1 && git push -q origin main >>"$ST" 2>&1; then echo "$(date) pushed to origin/main" >>"$ST"
else git rebase --abort 2>/dev/null; git checkout -q -b night/finals-evidence 2>/dev/null || git checkout -q night/finals-evidence; git push -q -u origin night/finals-evidence >>"$ST" 2>&1 && echo "$(date) pushed to origin/night/finals-evidence (main rebase failed)" >>"$ST"; git checkout -q main; fi
cat "$ST"
