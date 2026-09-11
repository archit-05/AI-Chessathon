#!/bin/bash
# Tuesday night chain (V5 Plan): run A exports -> local judge steps (slope, scale-matched export,
# exactness, blunder set) -> run B starts on the GPU -> run A fast gate on the x86 box (400 at 5 s)
# -> draw-policy gates on the x86 box -> run A 10 s gate on the VM (after the VM screens) ->
# real-clock proxy for run A on the x86 box. Every step logs to ../data/night_chain.log.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
say() { echo "$(date '+%F %T') $*"; }
until [ "$(grep -c 'epoch .* done' ../data/train_v5a.log)" -ge 6 ] && ! pgrep -f "tools/train_nnue.py" > /dev/null; do sleep 30; done
say "run A finished: $(grep -E 'epoch 5 val' ../data/train_v5a.log | tr '\n' ' ' | cut -c1-200)"
SKIP_VM=1 bash tools/judge_net.sh ../data/nnue_v5a.pt v5a 0 2>&1 | tail -6
say "starting run B on the GPU"
( cd ../bini_v4 && bash tools/pull_selfplay.sh | tail -1 && VAL_N=20000 EPOCHS=6 nohup bash tools/run_v5b.sh > ../data/train_v5b.log 2>&1 & )
sleep 60
say "run A fast gate on x86 (400 at 5 s vs V3's net)"
bash tools/x86_gate.sh bini_cand_v5a bini_v4final 400 v5a_vs_v4_5s 5000 50
say "draw-policy gates on x86"
bash tools/draw_gate.sh 2>&1 | tail -5
until grep -q "VM SCREENS DONE" ../data/vm_screens.log 2>/dev/null; do sleep 60; done
say "run A 10 s gate on the VM (300)"
bash tools/vm_gate.sh bini_cand_v5a bini_v4final 300 v5a_vs_v4_10s 10000 100
say "run A real-clock proxy on x86 (40 at 20k)"
bash tools/x86_proxy.sh bini_cand_v5a 40 20000 v5a_20k 2>&1 | tail -3
say "NIGHT CHAIN DONE"
