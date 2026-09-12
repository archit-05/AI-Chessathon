#!/bin/bash
# Lane C on the pod: public Stockfish binpacks (test80-2024 jan..jun) -> pilot to measure the score scale k ->
# from-scratch bp48 (48 sb, --eval-scale 400*k) -> bp_d7 (align on our 712M shuffle, 12 sb) -> bp_d7_ft (exact fc_b
# schedule on clean_d10) -> export + bound + sanity -> mirror.  usage: bash run_c_lane.sh <gcp target>
set -u; GCP="$1"; cd ~/chess; S=~/chess/logs/c_lane.status; export PATH=/usr/local/cuda/bin:$HOME/.cargo/bin:$PATH CUDA_PATH=/usr/local/cuda CUDA_HOME=/usr/local/cuda
log() { echo "$(date '+%F %T') $*" | tee -a $S; }
T=~/chess/bini_v7/tools/bullet_trainer/target/release/bini_bullet_trainer; CK=~/chess/data/ckpt; NETS=~/chess/data/nets; V=~/chess/venv/bin/python; X=~/chess/bini_v7/tools/bullet_export.py; BP=~/chess/data/binpacks; E=~/chess/bini_astra_v5_noc2b
log "waiting for the six binpack downloads"
while [ $(ls $BP/*.done 2>/dev/null | wc -l) -lt 6 ]; do sleep 30; done
log "downloads done: $(du -sh $BP | cut -f1); decompressing"
for f in $BP/*.binpack.zst; do [ -f "${f%.zst}" ] || zstd -d -q -T2 --rm "$f" & done; wait; log "decompressed: $(ls $BP/*.binpack | wc -l) files, $(du -sh $BP | cut -f1)"
# rebuild the trainer with --eval-scale (source already patched) once the GPU jobs before us are done
while ! grep -q "A3-site done\|FAILED" ~/chess/logs/a3_site.status 2>/dev/null; do sleep 30; done
( cd ~/chess/bini_v7/tools/bullet_trainer && cargo build --release --features cuda > ~/chess/logs/trainer_build_c.log 2>&1 ) && log "trainer rebuilt with --eval-scale" || { log "REBUILD FAILED"; exit 1; }
$T --help 2>&1 | grep -q "eval-scale" || { log "no --eval-scale in binary"; exit 1; }
# pilot: 6 sb on jan at scale 400, measure the pred/label slope of the pilot net and of fc_b on a depth-10 chunk
log "PILOT cpilot: 6 sb on jan (loader speed + score scale)"
$T --binpack $BP/test80-2024-01-jan-2tb7p.min-v2.v6.binpack --hidden 1024 --act screlu --wdl 0 --lr 0.0005 --lr-schedule cosine --superbatches 6 --save-rate 6 --threads 6 --binpack-buffer-mb 2048 --min-ply 16 --max-score 10000 --device 0 --out $CK --net-id cpilot > ~/chess/logs/train_cpilot.log 2>&1 && log "cpilot trained ($(grep -ao "[0-9]* pos/sec" ~/chess/logs/train_cpilot.log | tail -1))" || { log "cpilot FAILED"; exit 1; }
$V $X --checkpoint $CK/cpilot-6 --hidden 1024 --act screlu --out $NETS/nnue_cpilot.safetensors > /dev/null 2>&1
slope() { BINI_NNUE=$1 $V $E/tools/net_diag.py ~/chess/data/ft/slope_ref.npz --n 20000 2>&1 | grep -io "slope[^,;]*" | head -1; }
SP_PILOT=$(slope $NETS/nnue_cpilot.safetensors); SP_FCB=$(slope $NETS/nnue_fcb.safetensors); log "slope pilot: '$SP_PILOT'  slope fc_b: '$SP_FCB'"
KP=$(echo "$SP_PILOT" | grep -o "[0-9.]*" | head -1); KF=$(echo "$SP_FCB" | grep -o "[0-9.]*" | head -1)
K=$(python3 -c "kp=float('$KP' or 0); kf=float('$KF' or 1); k=kp/kf if kp>0 and kf>0 else 0; print(round(k,3))"); log "k = pilot/fc_b slope ratio = $K"
python3 -c "k=float('$K'); import sys; sys.exit(0 if 0.15 <= k <= 8 else 1)" || { log "k out of [0.15, 8]: stop C (wrong reading of the labels)"; exit 1; }
ES=$(python3 -c "print(round(400.0/float('$K'),1))"); log "eval scale for binpacks = 400/k = $ES (raw output stays cp/400)"
log "ARM bp48: jan..jun, 48 sb, --eval-scale $ES, --max-score 3000"
$T --binpack $BP/test80-2024-01-jan-2tb7p.min-v2.v6.binpack $BP/test80-2024-02-feb-2tb7p.min-v2.v6.binpack $BP/test80-2024-03-mar-2tb7p.min-v2.v6.binpack $BP/test80-2024-04-apr-2tb7p.min-v2.v6.binpack $BP/test80-2024-05-may-2tb7p.min-v2.v6.binpack $BP/test80-2024-06-jun-2tb7p.min-v2.v6.binpack \
   --hidden 1024 --act screlu --wdl 0 --eval-scale $ES --lr 0.0005 --lr-schedule cosine --superbatches 48 --save-rate 48 --threads 6 --binpack-buffer-mb 4096 --min-ply 16 --max-score 3000 --device 0 --out $CK --net-id bp48 > ~/chess/logs/train_bp48.log 2>&1 && log "bp48 trained ($(grep -ao "[0-9]* pos/sec" ~/chess/logs/train_bp48.log | tail -1))" || { log "bp48 FAILED"; exit 1; }
$V $X --checkpoint $CK/bp48-48 --hidden 1024 --act screlu --out $NETS/nnue_bp48.safetensors 2>&1 | tee -a $S
log "ARM bp_d7: resume bp48, 12 sb on the 712M shuffle (scale 400)"
$T --data ~/chess/data/bullet_shuf/shuffled_0.bin ~/chess/data/bullet_shuf/shuffled_1.bin ~/chess/data/bullet_shuf/shuffled_2.bin ~/chess/data/bullet_shuf/shuffled_3.bin ~/chess/data/bullet_shuf/shuffled_4.bin ~/chess/data/bullet_shuf/shuffled_5.bin ~/chess/data/bullet_shuf/shuffled_6.bin ~/chess/data/bullet_shuf/shuffled_7.bin \
   --resume $CK/bp48-48 --start-superbatch 1 --superbatches 12 --lr 0.0005 --lr-schedule cosine --hidden 1024 --act screlu --wdl 0 --save-rate 12 --threads 6 --device 0 --out $CK --net-id bp_d7 > ~/chess/logs/train_bp_d7.log 2>&1 && log "bp_d7 trained" || { log "bp_d7 FAILED"; exit 1; }
$V $X --checkpoint $CK/bp_d7-12 --hidden 1024 --act screlu --out $NETS/nnue_bp_d7.safetensors 2>&1 | tee -a $S
log "ARM bp_d7_ft: fc_b schedule on clean_d10 from bp_d7"
$T --data ~/chess/data/ft/clean_d10_shuf.bin --resume $CK/bp_d7-12 --start-superbatch 97 --superbatches 104 --lr 0.0005 --lr-schedule cosine --hidden 1024 --act screlu --wdl 0 --save-rate 104 --threads 6 --device 0 --out $CK --net-id bp_d7_ft > ~/chess/logs/train_bp_d7_ft.log 2>&1 && log "bp_d7_ft trained" || { log "bp_d7_ft FAILED"; exit 1; }
$V $X --checkpoint $CK/bp_d7_ft-104 --hidden 1024 --act screlu --out $NETS/nnue_bp_d7_ft.safetensors 2>&1 | tee -a $S
for ID in bp48 bp_d7 bp_d7_ft; do $V - <<PYEOF 2>&1 | tee -a $S
import sys, numpy as np; sys.path.insert(0, "$HOME/chess/bini_astra_v5_noc2b"); from bini_nnue import read_safetensors
t,_ = read_safetensors(__import__("pathlib").Path("$NETS/nnue_$ID.safetensors")); b = int(np.abs(t["b1"]).max()) + 32*int(np.abs(t["w1"]).max())
print("$ID ACC_BOUND", b, "int16 OK" if b < 32767 else "INT32 FALLBACK (slower)", "|w2|max", int(np.abs(t["w2"]).max()))
PYEOF
done
BINI_NNUE=$NETS/nnue_bp_d7_ft.safetensors BINI_DIR=$HOME/chess/bini_astra_v5_noc2b BINI_TT_BITS=16 $V - <<PYEOF 2>&1 | tee -a $S
import sys; sys.path.insert(0, "$HOME/chess/astra_tests"); from harness import Probe, N
p = Probe()
for f in ("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", "8/8/4k3/8/8/4K3/4P3/8 w - - 0 1", "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKB1R w KQkq - 0 1"):
    p.setup(f, [], budget=1); print("bp_d7_ft sanity", f[:24], int(N.nnue_eval(p.e.bb, p.e.st, p.e.acc, p.e.w2, p.e.b2)), "cp")
PYEOF
ssh -o StrictHostKeyChecking=no $GCP 'mkdir -p ~/chess/data/stage/nets_night ~/chess/data/stage/ckpt_night'; rsync -az -e "ssh -o StrictHostKeyChecking=no" $NETS/nnue_bp*.safetensors ~/chess/logs/ $GCP:~/chess/data/stage/nets_night/ 2>/dev/null; rsync -az -e "ssh -o StrictHostKeyChecking=no" $CK/bp48-48 $CK/bp_d7-12 $CK/bp_d7_ft-104 $GCP:~/chess/data/stage/ckpt_night/ 2>/dev/null
log "C-lane done"
