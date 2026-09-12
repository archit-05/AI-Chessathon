#!/bin/bash
# C5: after C4, continue bp240 to 336 superbatches (seven passes) while the GPU is otherwise idle; keep only if the bp240 screen holds the trend, re-align, re-fine-tune, export, mirror. usage: run_c5_lane.sh <gcp target>
set -u; GCP="$1"; cd ~/chess; S=~/chess/logs/c5_lane.status; export PATH=/usr/local/cuda/bin:$HOME/.cargo/bin:$PATH
log() { echo "$(date '+%F %T') $*" | tee -a $S; }
T=~/chess/bini_v7/tools/bullet_trainer/target/release/bini_bullet_trainer; CK=~/chess/data/ckpt; NETS=~/chess/data/nets; V=~/chess/venv/bin/python; X=~/chess/bini_v7/tools/bullet_export.py; BP=~/chess/data/binpacks
log "waiting for C4"; while ! grep -q "C4-lane done\|FAILED" ~/chess/logs/c4_lane.status 2>/dev/null; do sleep 60; done; grep -q "C4-lane done" ~/chess/logs/c4_lane.status || { log "C4 did not finish; C5 not run"; exit 0; }
ES=$(grep -o "eval scale for binpacks = 400/k = [0-9.]*" ~/chess/logs/c_lane.status | grep -o "[0-9.]*$" | tail -1)
LAST=$(ls -d $CK/bp240-* | sort -t- -k2 -n | tail -1); log "ARM bp336: resume $LAST, 96 more sb at eval-scale $ES"
$T --binpack $BP/test80-2024-01-jan-2tb7p.min-v2.v6.binpack $BP/test80-2024-02-feb-2tb7p.min-v2.v6.binpack $BP/test80-2024-03-mar-2tb7p.min-v2.v6.binpack $BP/test80-2024-04-apr-2tb7p.min-v2.v6.binpack $BP/test80-2024-05-may-2tb7p.min-v2.v6.binpack $BP/test80-2024-06-jun-2tb7p.min-v2.v6.binpack \
   --resume $LAST --start-superbatch 241 --superbatches 336 --hidden 1024 --act screlu --wdl 0 --eval-scale $ES --lr 0.0005 --lr-schedule cosine --save-rate 016 --threads 6 --binpack-buffer-mb 4096 --min-ply 16 --max-score 3000 --device 0 --out $CK --net-id bp336 > ~/chess/logs/train_bp336.log 2>&1 && log "bp336 trained" || { log "bp336 FAILED"; exit 1; }
L2=$(ls -d $CK/bp336-* | sort -t- -k2 -n | tail -1)
$T --data ~/chess/data/bullet_shuf/shuffled_0.bin ~/chess/data/bullet_shuf/shuffled_1.bin ~/chess/data/bullet_shuf/shuffled_2.bin ~/chess/data/bullet_shuf/shuffled_3.bin ~/chess/data/bullet_shuf/shuffled_4.bin ~/chess/data/bullet_shuf/shuffled_5.bin ~/chess/data/bullet_shuf/shuffled_6.bin ~/chess/data/bullet_shuf/shuffled_7.bin \
   --resume $L2 --start-superbatch 1 --superbatches 12 --lr 0.0005 --lr-schedule cosine --hidden 1024 --act screlu --wdl 0 --save-rate 12 --threads 6 --device 0 --out $CK --net-id bp336_d7 > ~/chess/logs/train_bp336_d7.log 2>&1 && log "bp336_d7 trained" || { log "bp336_d7 FAILED"; exit 1; }
$T --data ~/chess/data/ft/clean_d10_shuf.bin --resume $CK/bp336_d7-12 --start-superbatch 97 --superbatches 104 --lr 0.0005 --lr-schedule cosine --hidden 1024 --act screlu --wdl 0 --save-rate 104 --threads 6 --device 0 --out $CK --net-id bp336_d7_ft > ~/chess/logs/train_bp336_d7_ft.log 2>&1 && log "bp336_d7_ft trained" || { log "bp336_d7_ft FAILED"; exit 1; }
$V $X --checkpoint $CK/bp336_d7_ft-104 --hidden 1024 --act screlu --out $NETS/nnue_bp336_d7_ft.safetensors 2>&1 | tee -a $S
$V - <<PYEOF 2>&1 | tee -a $S
import sys, numpy as np; sys.path.insert(0, "$HOME/chess/bini_astra_v5_noc2b"); from bini_nnue import read_safetensors
t,_ = read_safetensors(__import__("pathlib").Path("$NETS/nnue_bp336_d7_ft.safetensors")); b = int(np.abs(t["b1"]).max()) + 32*int(np.abs(t["w1"]).max())
print("bp336_d7_ft ACC_BOUND", b, "int16 OK" if b < 32767 else "INT32 FALLBACK (slower)")
PYEOF
rsync -az -e "ssh -o StrictHostKeyChecking=no" $NETS/nnue_bp336*.safetensors ~/chess/logs/ $GCP:~/chess/data/stage/nets_night/ 2>/dev/null; rsync -az -e "ssh -o StrictHostKeyChecking=no" $CK/bp336_d7_ft-104 $GCP:~/chess/data/stage/ckpt_night/ 2>/dev/null; log "C5-lane done"
