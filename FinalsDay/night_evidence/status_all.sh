#!/bin/bash
# One command, every result. Run from any machine holding the ssh keys (aliases gcp-x86, priorcrypto-vm, runpod).
r() { python3 - "$@" <<'PY'
import json, sys
for p in sys.argv[1:]:
    try: r = json.load(open(p)); print(f"    {p.rsplit('/',1)[-1]:38s} {r['of']:4d} games  +{r['W']} ={r['D']} -{r['L']}  pair Elo {r['pair_elo']:+.1f} [{r['pair_elo_95'][0]:+.1f}, {r['pair_elo_95'][1]:+.1f}]  failures {sum(r['failures'].values())}")
    except Exception as e: print(f"    {p}: {e}")
PY
}
S() { perl -e 'alarm 45; exec @ARGV' ssh -o BatchMode=yes "$1" "$2" 2>/dev/null; }
echo "=== $(date '+%F %H:%M %Z') ==="
echo "--- gcp-x86 (combo / final package gates) ---"
S gcp-x86 'cd ~/chess/gates; for f in sfbook_real combo_bp144_d7_ft_C final_c40eg_vs_v85 final_bp144_vs_v85; do [ -f $f.log ] && echo "  $f: $(grep -E "^\[" $f.log | tail -1 | cut -c1-70)"; done; tail -2 after_chain.status 2>/dev/null | sed "s/^/  chain: /"; ls ~/chess/packages/*.zip 2>/dev/null | sed "s|.*/|  package: |"'
echo "  reports:"; S gcp-x86 'cd ~/chess/gates; for f in sfbook_report combo_bp144_d7_ft_C_report final_c40eg_vs_v85_report final_bp144_vs_v85_report; do [ -s $f.json ] && cat $f.json | tr -d "\n" && echo; done' | while read -r line; do echo "$line" > /tmp/_r.json; r /tmp/_r.json; done
echo "--- priorcrypto-vm (contempt 40, endgame fix) ---"
S priorcrypto-vm 'cd ~/chess/gates; for f in c40_vm eg_vm; do [ -f $f.log ] && echo "  $f: $(grep -E "^\[" $f.log | tail -1 | cut -c1-70)"; done; tail -2 vm_chain.status | sed "s/^/  chain: /"'
echo "  reports:"; S priorcrypto-vm 'cd ~/chess/gates; for f in c40_vm_report eg_vm_report; do [ -s $f.json ] && cat $f.json | tr -d "\n" && echo; done' | while read -r line; do echo "$line" > /tmp/_r.json; r /tmp/_r.json; done
echo "--- pod (screens, Stockfish-2400 gate, short-clock stress, lanes) ---"
S runpod 'cd ~/chess; grep -E "SCREEN|SHAPE" logs/screen_queue.status | sed -E "s/^[0-9-]+ //" | cut -c1-120 | sed "s/^/  /"; for f in sf2400 short30; do [ -f gates/$f.log ] && echo "  $f: $(grep -E "^\[" gates/$f.log | tail -1 | cut -c1-70)"; done; tail -1 logs/pod_queue.status 2>/dev/null | sed "s/^/  queue: /"; tail -1 logs/c5_lane.status | cut -c1-80 | sed "s/^/  C5: /"'
