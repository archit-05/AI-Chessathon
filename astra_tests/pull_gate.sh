#!/bin/bash
# Mirror gate artefacts off the host every 2 minutes, so a host failure costs at most one
# checkpoint interval rather than the whole sample (which is what happened on 10 September).
# Pulls: .partial.json (completed games so far), .json (final), .pgn, and the run log.
DEST="/Users/architbhardwaj/Desktop/AI Chessathon/astra_reports/gate_mirror"
mkdir -p "$DEST"
for i in $(seq 1 "${2:-200}"); do
  rsync -az --quiet \
     box2:/root/astra/out/ "$DEST/out/" 2>/dev/null
  rsync -az --quiet \
     box2:/root/astra/logs/ "$DEST/logs/" 2>/dev/null
  # a resume manifest: what was pulled, when, and the exact command that would continue it
  ls -la "$DEST/out/" > "$DEST/MANIFEST.txt" 2>/dev/null
  {
    echo "# mirrored $(date -u +%FT%TZ) from box2:/root/astra"
    for f in "$DEST"/out/*.partial.json; do
      [ -e "$f" ] || continue
      n=$(python3 -c "import json,sys;d=json.load(open(sys.argv[1]));print(d.get('completed','?'),d.get('requested','?'))" "$f" 2>/dev/null)
      echo "$(basename "$f"): $n games"
    done
  } >> "$DEST/MANIFEST.txt"
  if [ -f "$DEST/out/${1:-gate_v5}.json" ]; then echo "FINAL PRESENT: ${1:-gate_v5}.json"; fi
  sleep 120
done
