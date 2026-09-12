#!/bin/bash
# Green-before-GPU checks from the pretrain plan that need no GPU, on the quiet x86 box, then the clean d10 corpus, then relaunch the CHK gate.
set -u; cd ~/chess; V=~/chess/venv/bin/python; G=~/chess/gates; S=$G/preflight.status; E=~/chess/bini_astra_v5_noc2b; NETS=~/chess/data/stage/nets
FCB=$E/nnue.safetensors; K96=$NETS/nnue_k96.safetensors
echo "$(date) start" > $S
echo "-- determinism: same net both sides, 16 games @30k" >> $S
$V bini_v65/tools/node_gate.py --engine $E --a "BINI_NNUE=$FCB" --b "BINI_NNUE=$FCB" --openings bini_v65/tools/curated.epd --games 16 --nodes 30000 --workers 4 --tt-bits 22 --out $G/pf_determinism > $G/pf_determinism.stdout 2>&1
grep -E "^\S+ \[" $G/pf_determinism.log | tail -1 >> $S
echo "-- export parity 1024 screlu" >> $S
(cd bini_v85_stable && $V tests/test_bullet_export.py --hidden 1024 --act screlu --n 1000 2>&1 | tail -3) >> $S
echo "-- k96 re-export vs stored net" >> $S
$V bini_v7/tools/bullet_export.py --checkpoint ~/chess/data/stage/ckpt/k96-96 --hidden 1024 --act screlu --out /tmp/k96_re.safetensors >> $S 2>&1
$V - >> $S 2>&1 <<PYEOF
import sys, numpy as np; sys.path.insert(0, "$E"); from bini_nnue import read_safetensors
a,_ = read_safetensors(__import__("pathlib").Path("/tmp/k96_re.safetensors")); b,_ = read_safetensors(__import__("pathlib").Path("$K96"))
print("k96 re-export tensors identical:", all(np.array_equal(a[k], b[k]) for k in ("w1","b1","w2","b2")), {k: a[k].shape for k in a})
PYEOF
echo "-- instrument: fc_b vs k96 @30k, 576 games (plan expects about +29 +-22)" >> $S
$V bini_v65/tools/node_gate.py --engine $E --a "BINI_NNUE=$FCB" --b "BINI_NNUE=$K96" --openings bini_v65/tools/curated.epd --games 576 --nodes 30000 --workers 4 --tt-bits 22 --out $G/pf_instrument > $G/pf_instrument.stdout 2>&1
grep -E "^\S+ \[" $G/pf_instrument.log | tail -1 >> $S
echo "-- clean d10 corpus" >> $S
$V tools_v85/build_clean_d10.py ~/chess/data/stage/d10 ~/chess/data/stage/clean_d10_shuf.bin >> $S 2>&1
$V bini_v7/tools/bulletformat.py info ~/chess/data/stage/clean_d10_shuf.bin >> $S 2>&1
echo "$(date) preflight done; relaunching CHK real gate" >> $S
rm -f $G/chk_real.log $G/chk_real.pgn; bash chk_real.sh 400 6 >> $S 2>&1
echo "$(date) chain done" >> $S
