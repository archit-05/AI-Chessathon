#!/bin/bash
# Alignment variants from the bp144 checkpoint (idle GPU): A = fc_b schedule directly on clean_d10 (no shuffle pass);
# B = 12 sb on the shuffle at lr 0.0001 (gentle), then the fc_b schedule. Export + bound; mirror; screens via screen_one.
set -u; GCP="$1"; cd ~/chess; S=~/chess/logs/align_variants.status; export PATH=/usr/local/cuda/bin:$HOME/.cargo/bin:$PATH
log() { echo "$(date '+%F %T') $*" | tee -a $S; }
T=~/chess/bini_v7/tools/bullet_trainer/target/release/bini_bullet_trainer; CK=~/chess/data/ckpt; NETS=~/chess/data/nets; V=~/chess/venv/bin/python; X=~/chess/bini_v7/tools/bullet_export.py
SRC=$(ls -d $CK/bp144-* | sort -t- -k2 -n | tail -1); log "source checkpoint $SRC"
exp() { $V $X --checkpoint $1 --hidden 1024 --act screlu --out $NETS/nnue_$2.safetensors 2>&1 | tee -a $S; $V - <<PYEOF 2>&1 | tee -a $S
import sys, numpy as np; sys.path.insert(0, "$HOME/chess/bini_astra_v5_noc2b"); from bini_nnue import read_safetensors
t,_ = read_safetensors(__import__("pathlib").Path("$NETS/nnue_$2.safetensors")); b = int(np.abs(t["b1"]).max()) + 32*int(np.abs(t["w1"]).max())
print("$2 ACC_BOUND", b, "int16 OK" if b < 32767 else "INT32 FALLBACK")
PYEOF
}
log "ARM bp144_ftd: fc_b schedule directly from bp144"
$T --data ~/chess/data/ft/clean_d10_shuf.bin --resume $SRC --start-superbatch 97 --superbatches 104 --lr 0.0005 --lr-schedule cosine --hidden 1024 --act screlu --wdl 0 --save-rate 104 --threads 6 --device 0 --out $CK --net-id bp144_ftd > ~/chess/logs/train_bp144_ftd.log 2>&1 && log "bp144_ftd trained" && exp $CK/bp144_ftd-104 bp144_ftd || log "bp144_ftd FAILED"
log "ARM bp144_soft: 12 sb on the shuffle at lr 0.0001 from bp144, then fc_b schedule"
$T --data ~/chess/data/bullet_shuf/shuffled_0.bin ~/chess/data/bullet_shuf/shuffled_1.bin ~/chess/data/bullet_shuf/shuffled_2.bin ~/chess/data/bullet_shuf/shuffled_3.bin ~/chess/data/bullet_shuf/shuffled_4.bin ~/chess/data/bullet_shuf/shuffled_5.bin ~/chess/data/bullet_shuf/shuffled_6.bin ~/chess/data/bullet_shuf/shuffled_7.bin \
   --resume $SRC --start-superbatch 1 --superbatches 12 --lr 0.0001 --lr-schedule cosine --hidden 1024 --act screlu --wdl 0 --save-rate 12 --threads 6 --device 0 --out $CK --net-id bp144_s7 > ~/chess/logs/train_bp144_s7.log 2>&1 && log "bp144_s7 trained" || { log "bp144_s7 FAILED"; exit 1; }
$T --data ~/chess/data/ft/clean_d10_shuf.bin --resume $CK/bp144_s7-12 --start-superbatch 97 --superbatches 104 --lr 0.0005 --lr-schedule cosine --hidden 1024 --act screlu --wdl 0 --save-rate 104 --threads 6 --device 0 --out $CK --net-id bp144_soft > ~/chess/logs/train_bp144_soft.log 2>&1 && log "bp144_soft trained" && exp $CK/bp144_soft-104 bp144_soft || log "bp144_soft FAILED"
rsync -az -e "ssh -o StrictHostKeyChecking=no" $NETS/nnue_bp144_ftd.safetensors $NETS/nnue_bp144_soft.safetensors ~/chess/logs/ $GCP:~/chess/data/stage/nets_night/ 2>/dev/null; log "align variants done"
