#!/bin/bash
# On box B: stop the invalid control (a) arena, re-export v3b.pt properly, rerun control (a).
cd ~/chess || exit 1
for p in $(ps -eo pid,args | grep "[a]rena_par.py --agent ../bini_ctrl_reexport" | awk '{print $1}'); do kill "$p"; done
sleep 2
for p in $(ps -eo pid,args | grep "[h]arness/runner.py" | grep "bini_ctrl_reexport" | awk '{print $1}'); do kill -9 "$p"; done
cd ~/chess/bini_v5 && ~/chess/venv/bin/python tools/export_from_pt.py ~/chess/data/nnue_v3b.pt ~/chess/data/nnue_v3b_reexport.safetensors --buckets 8 --hidden 512 --act crelu --out-buckets 1 --out-scale 1.0 2>&1 | tail -1
cp ~/chess/data/nnue_v3b_reexport.safetensors ~/chess/bini_ctrl_reexport/nnue.safetensors
md5sum ~/chess/bini_ctrl_reexport/nnue.safetensors ~/chess/bini_v4final/nnue.safetensors | cut -c1-34
cd ~/chess/bini_v4final && BINI_TT_BITS=22 nice -n 5 ../aichessathon-starter/.venv/bin/python tools/arena_par.py --agent ../bini_ctrl_reexport --opponent ../bini_v4final --games 40 --workers 4 --base-ms 5000 --inc-ms 50 --openings tools/curated.epd > ../gates/ctrl_reexport2.log 2>&1
echo "control a (re-export vs v3b, fixed): $(grep -E '^\[' ../gates/ctrl_reexport2.log | tail -1)"
echo "CONTROL A DONE"
