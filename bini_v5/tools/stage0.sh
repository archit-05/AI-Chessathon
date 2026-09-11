#!/bin/bash
# Stage 0 (instrument calibration) + the first own-label verdict, all at 30k nodes, 24 workers. Runs on the GPU box.
cd ~/chess/bini_v5; P=~/chess/venv/bin/python; D=~/chess/data; G=~/chess/gates; O=tools/curated.epd
run() { name=$1; a=$2; b=$3; n=$4; echo "== $(date "+%T") $name"; $P tools/node_gate.py --engine . --a "BINI_NNUE=$a" --b "BINI_NNUE=$b" --openings $O --games $n --nodes 30000 --workers 24 --tt-bits 22 --out $G/$name > $G/$name.stdout 2>&1; tail -n 2 $G/$name.log; }
run s0_determinism $D/nnue_v3b.safetensors $D/nnue_v3b.safetensors 16
echo "mirror yes/no: $(grep -c "mirror=YES" $G/s0_determinism.log) / $(grep -c "mirror=NO" $G/s0_determinism.log)"
run s0_v3b_vs_v3 $D/nnue_v3b.safetensors $D/nnue_v3.safetensors 576
run s0_v3b_vs_v2 $D/nnue_v3b.safetensors $D/nnue_v2.safetensors 576
run p1pilot_vs_v3b $D/nnue_p1pilot.safetensors $D/nnue_v3b.safetensors 576
echo "== $(date "+%T") stage0 done"
