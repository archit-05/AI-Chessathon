#!/bin/bash
# Assemble the V5 candidate from named parts into a NEW directory (never a working copy):
#   bash tools/assemble_v5.sh <target dir name> <net .safetensors> [book.json] [CORR=0|1] [SEEP=0|1] [CALIB=0|1]
# The target must not exist and must not resolve (case-insensitively) to any bini_* working copy.
set -euo pipefail
cd "$(dirname "$0")/.."
TARGET=${1:?target dir name}; NET=${2:?net file}; BOOK=${3:-}; CORR=${4:-0}; SEEP=${5:-1}; CALIB=${6:-0}
T="../$TARGET"
low=$(echo "$TARGET" | tr 'A-Z' 'a-z')
for keep in bini bini_v4 bini_v4final bini_v5 bini_v3b; do [ "$low" = "$keep" ] && { echo "refusing to touch working copy $keep"; exit 1; }; done
[ -e "$T" ] && { echo "refusing: $T exists (delete it yourself if that is what you want)"; exit 1; }
[ -f "$NET" ] || { echo "no such net: $NET"; exit 1; }
mkdir -p "$T"
for f in agent.py bini_board.py bini_calib.py bini_engine.py bini_eval.py bini_magics.py bini_nnue.py bini_search.py; do cp "$f" "$T/"; done
cp "$NET" "$T/nnue.safetensors"
[ -n "$BOOK" ] && cp "$BOOK" "$T/book.json"
mkdir -p "$T/tests" && cp -R tests/pos "$T/tests/" && cp tests/*.py "$T/tests/"
mkdir -p "$T/tools" && cp tools/arena_par.py tools/curated.epd tools/openings.epd tools/package.sh tools/proxy_match.py tools/grade.py "$T/tools/" 2>/dev/null || true
# bake the switch defaults into the engine so the zip needs no environment
sed -i '' -e "s/os.environ.get(\"BINI_CORR\", \"1\")/os.environ.get(\"BINI_CORR\", \"$CORR\")/" -e "s/os.environ.get(\"BINI_SEEP\", \"1\")/os.environ.get(\"BINI_SEEP\", \"$SEEP\")/" -e "s/os.environ.get(\"BINI_CONT\", \"1\")/os.environ.get(\"BINI_CONT\", \"0\")/" -e "s/os.environ.get(\"BINI_CALIB\", \"0\")/os.environ.get(\"BINI_CALIB\", \"$CALIB\")/" "$T/bini_engine.py"
grep -n "BINI_CORR\|BINI_SEEP\|BINI_CONT\|BINI_DRAW_BEHIND\|BINI_DRAW_CP" "$T/bini_engine.py" | cut -c1-110
echo "assembled $T: net $(md5 -q "$T/nnue.safetensors" 2>/dev/null || md5sum "$T/nnue.safetensors" | cut -c1-32) book $([ -f "$T/book.json" ] && echo yes || echo no)"
