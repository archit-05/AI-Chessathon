#!/bin/bash
# Assemble the V4 candidate directory ../bini_v4final (a name that cannot collide with bini_v4 on
# a case-insensitive filesystem; the earlier "bini_V4" did, and deleted the working copy).
#   engine  = bini_v4 (safety items, switches off, telemetry stripped)
#   wrapper = bini_v4dev/agent.py (book hook + forced-fallback test hook)
#   net     = $1 (default the v4o2 net); book = data/book.json when $2 = book
set -euo pipefail
cd "$(dirname "$0")/.."
net=${1:-../data/nnue_v4o2.safetensors}; withbook=${2:-book}
target=../bini_v4final
[ "$(cd .. && pwd -P)/bini_v4final" != "$(pwd -P)" ] || { echo "refusing: target is the working copy"; exit 1; }
rm -rf "$target"
rsync -a --exclude __pycache__ --exclude tests/arena ./ "$target"/
cp ../bini_v4dev/agent.py "$target"/agent.py
cp "$net" "$target"/nnue.safetensors
if [ "$withbook" = "book" ]; then cp ../data/book.json "$target"/book.json; else rm -f "$target"/book.json; fi
cd "$target" && ../aichessathon-starter/.venv/bin/python -c "import ast,os; [ast.parse(open(f).read()) for f in ['agent.py','bini_engine.py','bini_search.py','bini_nnue.py','bini_board.py','bini_eval.py']]; print('assembled bini_v4final:', '$net', 'book' if os.path.exists('book.json') else 'no book')"
