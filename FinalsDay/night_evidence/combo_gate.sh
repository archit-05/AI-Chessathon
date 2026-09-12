#!/bin/bash
# When a new net arrives: three gates, each its own candidate directory, exact V8.5 code.
#   A: net alone            cand_net_<tag>        (V8.5 + net)                     vs bini_astra_v5_noc2b
#   B: book given the net   cand_netbook_<tag>    (V8.5 + net + SF book + guards)  vs cand_net_<tag>
#   C: the combined package cand_netbook_<tag>                                     vs bini_astra_v5_noc2b
# usage: combo_gate.sh <net.safetensors> <book.json> <tag> [games=300] [workers=6]
set -u; cd ~/chess; V=~/chess/venv/bin/python; G=~/chess/gates; NET="$1"; BOOK="$2"; TAG="$3"; GAMES=${4:-300}; W=${5:-6}; export BINI_JOIN_S=300
mk() { rm -rf "$1"; cp -r bini_astra_v5_noc2b "$1"; rm -rf "$1/__pycache__"; mkdir -p "$1/tools"; cp tools_v85/arena_par.py tools_v85/curated.epd "$1/tools/"; }
mk cand_net_$TAG; cp "$NET" cand_net_$TAG/nnue.safetensors
mk cand_netbook_$TAG; cp "$NET" cand_netbook_$TAG/nnue.safetensors; cp "$BOOK" cand_netbook_$TAG/book.json; $V bookbuild/patch_guards.py cand_netbook_$TAG
for c in cand_net_$TAG cand_netbook_$TAG; do (cd $c && sha256sum agent.py bini_*.py nnue.safetensors book.json) > $G/${c}_manifest.txt; $V pkg_smoke.py $c smoke_$c 2>&1 | tail -3; done
run() { nohup $V $1/tools/arena_par.py --agent ~/chess/$1 --opponent ~/chess/$2 --games $GAMES --base-ms 120000 --inc-ms 500 --workers $W --openings $1/tools/curated.epd --pgn-out $G/$3.pgn --stats-out $G/$3.stats.jsonl > $G/$3.log 2>&1 < /dev/null & }
case "${6:-A}" in
  A) run cand_net_$TAG bini_astra_v5_noc2b combo_${TAG}_A ;;
  B) run cand_netbook_$TAG cand_net_$TAG combo_${TAG}_B ;;
  C) run cand_netbook_$TAG bini_astra_v5_noc2b combo_${TAG}_C ;;
esac
echo "started gate ${6:-A} for $TAG at $(date)"
