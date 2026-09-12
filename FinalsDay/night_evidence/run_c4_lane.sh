#!/bin/bash
# C4: after C3, continue bp144 to 240 superbatches (five passes; screen trend -13/+5/+12 at 48/96/144), re-align, re-fine-tune, export, mirror. usage: run_c4_lane.sh <gcp target>
set -u; GCP="$1"; cd ~/chess; S=~/chess/logs/c4_lane.status; export PATH=/usr/local/cuda/bin:$HOME/.cargo/bin:$PATH
log() { echo "$(date '+%F %T') $*" | tee -a $S; }
T=~/chess/bini_v7/tools/bullet_trainer/target/release/bini_bullet_trainer; CK=~/chess/data/ckpt; NETS=~/chess/data/nets; V=~/chess/venv/bin/python; X=~/chess/bini_v7/tools/bullet_export.py; BP=~/chess/data/binpacks
ES=$(grep -o "eval scale for binpacks = 400/k = [0-9.]*" ~/chess/logs/c_lane.status | grep -o "[0-9.]*$" | tail -1)
LAST=$(ls -d $CK/bp144-* | sort -t- -k2 -n | tail -1); log "ARM bp240: resume $LAST, 96 more sb at eval-scale $ES"
$T --binpack $BP/test80-2024-01-jan-2tb7p.min-v2.v6.binpack $BP/test80-2024-02-feb-2tb7p.min-v2.v6.binpack $BP/test80-2024-03-mar-2tb7p.min-v2.v6.binpack $BP/test80-2024-04-apr-2tb7p.min-v2.v6.binpack $BP/test80-2024-05-may-2tb7p.min-v2.v6.binpack $BP/test80-2024-06-jun-2tb7p.min-v2.v6.binpack \
   --resume $LAST --start-superbatch 145 --superbatches 240 --hidden 1024 --act screlu --wdl 0 --eval-scale $ES --lr 0.0005 --lr-schedule cosine --save-rate 016 --threads 6 --binpack-buffer-mb 4096 --min-ply 16 --max-score 3000 --device 0 --out $CK --net-id bp240 > ~/chess/logs/train_bp240.log 2>&1 && log "bp240 trained" || { log "bp240 FAILED"; exit 1; }
L2=$(ls -d $CK/bp240-* | sort -t- -k2 -n | tail -1)
$T --data ~/chess/data/bullet_shuf/shuffled_0.bin ~/chess/data/bullet_shuf/shuffled_1.bin ~/chess/data/bullet_shuf/shuffled_2.bin ~/chess/data/bullet_shuf/shuffled_3.bin ~/chess/data/bullet_shuf/shuffled_4.bin ~/chess/data/bullet_shuf/shuffled_5.bin ~/chess/data/bullet_shuf/shuffled_6.bin ~/chess/data/bullet_shuf/shuffled_7.bin \
   --resume $L2 --start-superbatch 1 --superbatches 12 --lr 0.0005 --lr-schedule cosine --hidden 1024 --act screlu --wdl 0 --save-rate 12 --threads 6 --device 0 --out $CK --net-id bp240_d7 > ~/chess/logs/train_bp240_d7.log 2>&1 && log "bp240_d7 trained" || { log "bp240_d7 FAILED"; exit 1; }
$T --data ~/chess/data/ft/clean_d10_shuf.bin --resume $CK/bp240_d7-12 --start-superbatch 97 --superbatches 104 --lr 0.0005 --lr-schedule cosine --hidden 1024 --act screlu --wdl 0 --save-rate 104 --threads 6 --device 0 --out $CK --net-id bp240_d7_ft > ~/chess/logs/train_bp240_d7_ft.log 2>&1 && log "bp240_d7_ft trained" || { log "bp240_d7_ft FAILED"; exit 1; }
$V $X --checkpoint $CK/bp240_d7_ft-104 --hidden 1024 --act screlu --out $NETS/nnue_bp240_d7_ft.safetensors 2>&1 | tee -a $S
$V - <<PYEOF 2>&1 | tee -a $S
import sys, numpy as np; sys.path.insert(0, "$HOME/chess/bini_astra_v5_noc2b"); from bini_nnue import read_safetensors
t,_ = read_safetensors(__import__("pathlib").Path("$NETS/nnue_bp240_d7_ft.safetensors")); b = int(np.abs(t["b1"]).max()) + 32*int(np.abs(t["w1"]).max())
print("bp240_d7_ft ACC_BOUND", b, "int16 OK" if b < 32767 else "INT32 FALLBACK (slower)")
PYEOF
rsync -az -e "ssh -o StrictHostKeyChecking=no" $NETS/nnue_bp240*.safetensors ~/chess/logs/ $GCP:~/chess/data/stage/nets_night/ 2>/dev/null; rsync -az -e "ssh -o StrictHostKeyChecking=no" $CK/bp240_d7_ft-104 $GCP:~/chess/data/stage/ckpt_night/ 2>/dev/null; log "C4-lane done"
