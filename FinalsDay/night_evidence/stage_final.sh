#!/bin/bash
# gcp-x86: build the full finals package for a given net = V8.5 code + that net + Stockfish book + guards + contempt 40 +
# endgame fix; manifest; exact-package smoke; upload-ready zip.   usage: stage_final.sh <net_id|v85> <tag>
#   net_id must exist as ~/chess/data/stage/nets_night/nnue_<net_id>.safetensors (e.g. bp144_d7_ft, bp240_d7_ft, bp336_d7_ft)
set -u; cd ~/chess; V=~/chess/venv/bin/python; ID="$1"; TAG="$2"; D=cand_final_$TAG
rm -rf $D; cp -r bini_astra_v5_noc2b $D; rm -rf $D/__pycache__ $D/tools
if [ "$ID" != "v85" ]; then [ -f data/stage/nets_night/nnue_$ID.safetensors ] || { echo "no net nnue_$ID"; exit 1; }; cp data/stage/nets_night/nnue_$ID.safetensors $D/nnue.safetensors; fi
cp bookbuild/book_sf.json $D/book.json; $V bookbuild/patch_guards.py $D | tail -1
sed -i 's/os.environ.get("BINI_CONTEMPT", "20")/os.environ.get("BINI_CONTEMPT", "40")/' $D/bini_engine.py
$V patch_endgame.py $D
grep -q 'BINI_CONTEMPT", "40"' $D/bini_engine.py && grep -q "EG_DRAW" $D/bini_search.py && grep -q "_has_ep_capture" $D/agent.py || { echo "patch check failed"; exit 1; }
(cd $D && sha256sum agent.py bini_*.py nnue.safetensors book.json) > gates/${D}_manifest.txt
$V pkg_smoke.py $D smoke_$D 2>&1 | tail -3
$V build_packages.py $D:submission_V9_${TAG}_book_c40eg.zip | grep -v "^    "
echo "built $D -> packages/submission_V9_${TAG}_book_c40eg.zip; gate: bash pair_gate.sh $D bini_astra_v5_noc2b final_${TAG}_vs_v85 120 6"
