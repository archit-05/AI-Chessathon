#!/bin/bash
# C2 on the pod: after Lane C, continue bp48 for 48 more superbatches on the binpacks (same eval scale), then the same
# alignment (12 sb on the shuffle) and fc_b continuation, export, bound, sanity, mirror; screen via screen_one.
# usage: bash run_c2_lane.sh <gcp target>
set -u; GCP="$1"; cd ~/chess; S=~/chess/logs/c2_lane.status; export PATH=/usr/local/cuda/bin:$HOME/.cargo/bin:$PATH
log() { echo "$(date '+%F %T') $*" | tee -a $S; }
T=~/chess/bini_v7/tools/bullet_trainer/target/release/bini_bullet_trainer; CK=~/chess/data/ckpt; NETS=~/chess/data/nets; V=~/chess/venv/bin/python; X=~/chess/bini_v7/tools/bullet_export.py; BP=~/chess/data/binpacks
log "waiting for Lane C"
while ! grep -q "C-lane done\|FAILED\|stop C" ~/chess/logs/c_lane.status 2>/dev/null; do sleep 60; done
grep -q "C-lane done" ~/chess/logs/c_lane.status || { log "Lane C did not finish; C2 not run"; exit 0; }
ES=$(grep -o "eval scale for binpacks = 400/k = [0-9.]*" ~/chess/logs/c_lane.status | grep -o "[0-9.]*$" | tail -1); [ -n "$ES" ] || { log "no eval scale recorded"; exit 1; }
log "ARM bp96: resume bp48-48, 48 more sb on jan..jun at eval-scale $ES"
$T --binpack $BP/test80-2024-01-jan-2tb7p.min-v2.v6.binpack $BP/test80-2024-02-feb-2tb7p.min-v2.v6.binpack $BP/test80-2024-03-mar-2tb7p.min-v2.v6.binpack $BP/test80-2024-04-apr-2tb7p.min-v2.v6.binpack $BP/test80-2024-05-may-2tb7p.min-v2.v6.binpack $BP/test80-2024-06-jun-2tb7p.min-v2.v6.binpack \
   --resume $CK/bp48-48 --start-superbatch 49 --superbatches 96 --hidden 1024 --act screlu --wdl 0 --eval-scale $ES --lr 0.0005 --lr-schedule cosine --save-rate 96 --threads 6 --binpack-buffer-mb 4096 --min-ply 16 --max-score 3000 --device 0 --out $CK --net-id bp96 > ~/chess/logs/train_bp96.log 2>&1 && log "bp96 trained" || { log "bp96 FAILED"; exit 1; }
LAST=$(ls -d $CK/bp96-* | sort -t- -k2 -n | tail -1)
log "ARM bp96_d7: 12 sb on the shuffle from $LAST"
$T --data ~/chess/data/bullet_shuf/shuffled_0.bin ~/chess/data/bullet_shuf/shuffled_1.bin ~/chess/data/bullet_shuf/shuffled_2.bin ~/chess/data/bullet_shuf/shuffled_3.bin ~/chess/data/bullet_shuf/shuffled_4.bin ~/chess/data/bullet_shuf/shuffled_5.bin ~/chess/data/bullet_shuf/shuffled_6.bin ~/chess/data/bullet_shuf/shuffled_7.bin \
   --resume $LAST --start-superbatch 1 --superbatches 12 --lr 0.0005 --lr-schedule cosine --hidden 1024 --act screlu --wdl 0 --save-rate 12 --threads 6 --device 0 --out $CK --net-id bp96_d7 > ~/chess/logs/train_bp96_d7.log 2>&1 && log "bp96_d7 trained" || { log "bp96_d7 FAILED"; exit 1; }
log "ARM bp96_d7_ft: fc_b schedule on clean_d10"
$T --data ~/chess/data/ft/clean_d10_shuf.bin --resume $CK/bp96_d7-12 --start-superbatch 97 --superbatches 104 --lr 0.0005 --lr-schedule cosine --hidden 1024 --act screlu --wdl 0 --save-rate 104 --threads 6 --device 0 --out $CK --net-id bp96_d7_ft > ~/chess/logs/train_bp96_d7_ft.log 2>&1 && log "bp96_d7_ft trained" || { log "bp96_d7_ft FAILED"; exit 1; }
$V $X --checkpoint $CK/bp96_d7_ft-104 --hidden 1024 --act screlu --out $NETS/nnue_bp96_d7_ft.safetensors 2>&1 | tee -a $S
$V - <<PYEOF 2>&1 | tee -a $S
import sys, numpy as np; sys.path.insert(0, "$HOME/chess/bini_astra_v5_noc2b"); from bini_nnue import read_safetensors
t,_ = read_safetensors(__import__("pathlib").Path("$NETS/nnue_bp96_d7_ft.safetensors")); b = int(np.abs(t["b1"]).max()) + 32*int(np.abs(t["w1"]).max())
print("bp96_d7_ft ACC_BOUND", b, "int16 OK" if b < 32767 else "INT32 FALLBACK (slower)")
PYEOF
rsync -az -e "ssh -o StrictHostKeyChecking=no" $NETS/nnue_bp96*.safetensors ~/chess/logs/ $GCP:~/chess/data/stage/nets_night/ 2>/dev/null; rsync -az -e "ssh -o StrictHostKeyChecking=no" $CK/bp96_d7_ft-104 $GCP:~/chess/data/stage/ckpt_night/ 2>/dev/null
log "C2-lane done"
