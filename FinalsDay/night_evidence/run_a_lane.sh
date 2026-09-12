#!/bin/bash
# One-command A-lane on a rented CUDA box (root, Ubuntu, vastai/pytorch template).
#   1. provision (apt, rust, bullet trainer, stockfish, platform venv)   2. pull staged data from gcp-x86
#   3. A1 = exact fc_b replicate (control)   4. A2-lite = clean_d10 + 3 % depth-16 spice (+ leaf labels if present)
#   5. export each with ACC_BOUND check + sanity evals   6. 30k screen and 5+0.05 ladder vs fc_b on this box's cores
#   7. rsync nets + logs back to gcp-x86:~/chess/data/stage/nets_night/
# usage: bash run_a_lane.sh <gcp ssh target e.g. forge@8.228.62.35> [workers_for_gates=8]
set -u; GCP="$1"; W=${2:-8}; export DEBIAN_FRONTEND=noninteractive; mkdir -p ~/chess/{data/ckpt,data/nets,data/ft,gates,logs}; cd ~/chess; S=~/chess/logs/a_lane.status
log() { echo "$(date '+%F %T') $*" | tee -a $S; }
log "start on $(hostname) nproc=$(nproc) gpu=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1)"
apt-get update -qq >/dev/null 2>&1; apt-get install -y -qq build-essential git curl wget rsync zstd pkg-config >/dev/null 2>&1 && log "apt ok"
[ -x ~/.cargo/bin/cargo ] || { curl -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal >/dev/null 2>&1 && log "rust ok"; }; source ~/.cargo/env
rsync -az -e "ssh -o StrictHostKeyChecking=no" $GCP:~/chess/bini_v7/tools/ ~/chess/bini_v7/tools/ && rsync -az -e "ssh -o StrictHostKeyChecking=no" $GCP:~/chess/bini_astra_v5_noc2b/ ~/chess/bini_astra_v5_noc2b/ && rsync -az -e "ssh -o StrictHostKeyChecking=no" $GCP:~/chess/bini_v65/tools/ ~/chess/bini_v65/tools/ && rsync -az -e "ssh -o StrictHostKeyChecking=no" $GCP:~/chess/bini_v85_stable/ ~/chess/bini_v85_stable/ && rsync -az -e "ssh -o StrictHostKeyChecking=no" $GCP:~/chess/astra_tests/ ~/chess/astra_tests/ && log "code pulled"
[ -d ~/chess/bini_v7/tools/bullet_trainer/src ] || rsync -az -e "ssh -o StrictHostKeyChecking=no" $GCP:~/chess/bini_v7/tools/bullet_trainer/ ~/chess/bini_v7/tools/bullet_trainer/
( cd ~/chess/bini_v7/tools/bullet_trainer && cargo build --release --features cuda > ~/chess/logs/trainer_build.log 2>&1 && log "trainer built" || log "TRAINER BUILD FAILED (logs/trainer_build.log)" ) &
BUILD=$!
rsync -az -e "ssh -o StrictHostKeyChecking=no" $GCP:~/chess/data/stage/clean_d10_shuf.bin ~/chess/data/ft/ && rsync -az -e "ssh -o StrictHostKeyChecking=no" $GCP:~/chess/data/stage/leaf/site_spice_12_23.bin ~/chess/data/ft/ && rsync -az -e "ssh -o StrictHostKeyChecking=no" $GCP:~/chess/data/stage/ckpt/k96-96 ~/chess/data/ckpt/ && rsync -az -e "ssh -o StrictHostKeyChecking=no" $GCP:~/chess/data/stage/nets/nnue_k96.safetensors ~/chess/data/nets/ && cp ~/chess/bini_astra_v5_noc2b/nnue.safetensors ~/chess/data/nets/nnue_fcb.safetensors && log "data pulled"
rsync -az -e "ssh -o StrictHostKeyChecking=no" "$GCP:~/chess/data/stage/leaf/leaf_labels_mac_*.npz" ~/chess/data/ft/ 2>/dev/null && log "leaf labels pulled" || log "no leaf labels yet"
PY=$(command -v python3.12 || command -v python3.11 || command -v python3)
[ -x venv/bin/python ] || { $PY -m venv venv && venv/bin/pip install -q --upgrade pip && venv/bin/pip install -q "numba==0.67.0" "numpy==2.5.2" "chess==1.11.2" && log "venv ok"; }
[ -x Stockfish/src/stockfish ] || { git clone -q --depth 1 --branch sf_19 https://github.com/official-stockfish/Stockfish.git; ARCH=x86-64-avx2; grep -q avx512_vnni /proc/cpuinfo && ARCH=x86-64-vnni512; ( cd Stockfish/src && make -j$(nproc) profile-build ARCH=$ARCH > ~/chess/logs/sf_build.log 2>&1 ) && log "stockfish built"; }
V=~/chess/venv/bin/python
for f in ~/chess/data/ft/leaf_labels_mac_*.npz; do [ -f "$f" ] && $V bini_v7/tools/bulletformat.py convert "$f" "${f%.npz}.bin" >/dev/null 2>&1; done
SP=""; ls ~/chess/data/ft/leaf_labels_mac_*.bin >/dev/null 2>&1 && { cat ~/chess/data/ft/leaf_labels_mac_*.bin > ~/chess/data/ft/leaf_labels.bin; SP="--spice ~/chess/data/ft/leaf_labels.bin:2"; }
$V bini_v7/tools/mix_corpus.py ~/chess/data/ft/a2lite.bin --base ~/chess/data/ft/clean_d10_shuf.bin --spice ~/chess/data/ft/site_spice_12_23.bin:3 $SP 2>&1 | tee -a $S
wait $BUILD; T=~/chess/bini_v7/tools/bullet_trainer/target/release/bini_bullet_trainer; [ -x $T ] || { log "no trainer binary; stopping"; exit 1; }
CK=~/chess/data/ckpt; NETS=~/chess/data/nets; X=~/chess/bini_v7/tools/bullet_export.py
run_arm() { ID="$1"; DATA="$2"; SB="$3"; START="$4"; EXTRA="$5"
  log "ARM $ID: data=$DATA superbatches=$SB start=$START $EXTRA"
  $T --data $DATA --resume $CK/k96-96 --start-superbatch $START --superbatches $SB --lr 0.0005 --lr-schedule cosine --hidden 1024 --act screlu --wdl 0 --save-rate $SB --threads 8 --device 0 --out $CK --net-id $ID $EXTRA > ~/chess/logs/train_$ID.log 2>&1 && log "ARM $ID trained" || { log "ARM $ID FAILED"; return 1; }
  LAST=$(ls -d $CK/$ID-* | sort -t- -k2 -n | tail -1)
  $V $X --checkpoint $LAST --hidden 1024 --act screlu --out $NETS/nnue_$ID.safetensors 2>&1 | tee -a $S
  $V - <<PYEOF 2>&1 | tee -a $S
import sys, numpy as np; sys.path.insert(0, "$HOME/chess/bini_astra_v5_noc2b"); from bini_nnue import read_safetensors
t,_ = read_safetensors(__import__("pathlib").Path("$NETS/nnue_$ID.safetensors")); b = int(np.abs(t["b1"]).max()) + 32*int(np.abs(t["w1"]).max())
print("$ID ACC_BOUND", b, "int16 OK" if b < 32767 else "INT32 FALLBACK (slower)")
PYEOF
  BINI_NNUE=$NETS/nnue_$ID.safetensors BINI_DIR=$HOME/chess/bini_astra_v5_noc2b BINI_TT_BITS=16 $V - <<PYEOF 2>&1 | tee -a $S
import sys; sys.path.insert(0, "$HOME/chess/astra_tests"); from harness import Probe, N
p = Probe()
for f in ("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", "8/8/4k3/8/8/4K3/4P3/8 w - - 0 1", "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKB1R w KQkq - 0 1"):
    p.setup(f, [], budget=1); print("$ID sanity", f[:24], int(N.nnue_eval(p.e.bb, p.e.st, p.e.acc, p.e.w2, p.e.b2)), "cp (stm view; expect ~0, positive, negative)")
PYEOF
}
# A1: exact fc_b replicate (schedule from train_fc_b.log: start 97, end 104, cosine 0.0005 over 104)
run_arm fcb_re ~/chess/data/ft/clean_d10_shuf.bin 104 97 ""
# A2-lite: same schedule on clean_d10 + 3 % depth-16 spice (+ 2 % leaf labels if present)
run_arm a2lite ~/chess/data/ft/a2lite.bin 104 97 ""
# screens vs fc_b on this box's cores (fixed nodes = upper bound), then 5+0.05 ladder
E=~/chess/bini_astra_v5_noc2b; NG=~/chess/bini_v65/tools/node_gate.py; O=~/chess/bini_v65/tools/curated.epd
for ID in fcb_re a2lite; do [ -f $NETS/nnue_$ID.safetensors ] || continue
  $V $NG --engine $E --a "BINI_NNUE=$NETS/nnue_$ID.safetensors" --b "BINI_NNUE=$NETS/nnue_fcb.safetensors" --openings $O --games 576 --nodes 30000 --workers $W --tt-bits 22 --out ~/chess/gates/${ID}_30k > ~/chess/gates/${ID}_30k.stdout 2>&1
  log "SCREEN $ID vs fc_b: $(grep -E '^\S+ \[' ~/chess/gates/${ID}_30k.log | tail -1)"
done
for ID in fcb_re a2lite; do [ -f $NETS/nnue_$ID.safetensors ] || continue
  $V $NG --engine $E --a "BINI_NNUE=$NETS/nnue_$ID.safetensors" --b "BINI_NNUE=$NETS/nnue_fcb.safetensors" --openings $O --games 400 --tc 5+0.05 --workers $W --tt-bits 22 --out ~/chess/gates/${ID}_tc5 > ~/chess/gates/${ID}_tc5.stdout 2>&1
  log "TC5 $ID vs fc_b: $(grep -E '^\S+ \[' ~/chess/gates/${ID}_tc5.log | tail -1)"
done
ssh -o StrictHostKeyChecking=no $GCP 'mkdir -p ~/chess/data/stage/nets_night ~/chess/data/stage/ckpt_night'; rsync -az -e "ssh -o StrictHostKeyChecking=no" $NETS/nnue_fcb_re.safetensors $NETS/nnue_a2lite.safetensors ~/chess/logs/ ~/chess/gates/ $GCP:~/chess/data/stage/nets_night/ 2>/dev/null; rsync -az -e "ssh -o StrictHostKeyChecking=no" $CK/fcb_re-* $CK/a2lite-* $GCP:~/chess/data/stage/ckpt_night/ 2>/dev/null
log "A-lane done; nets and checkpoints mirrored to gcp-x86:~/chess/data/stage/{nets_night,ckpt_night}"
