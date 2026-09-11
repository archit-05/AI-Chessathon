#!/bin/bash
# After provisioning gcp-x86b: copy the V5 tools, the diagnostic chunk, the sparring agent, put
# stockfish on PATH, and start eight S1 generators (ids 90-97). Run FROM THE MAC.
set -uo pipefail
cd "$(dirname "$0")/.."
rsync -a --exclude __pycache__ --exclude tests/arena ./ gcp-x86b:chess/bini_v5/
rsync -a ../sparring/ gcp-x86b:chess/sparring/
rsync -az ../data/site_labelled/chunk_0001.npz gcp-x86b:chess/data/site_labelled/
rsync -az ../data/nnue_v3b.pt gcp-x86b:chess/data/ 2>/dev/null || true
ssh -o BatchMode=yes gcp-x86b 'bash -s' <<'REMOTE'
[ -x /usr/local/bin/stockfish ] || sudo ln -s $HOME/chess/Stockfish/src/stockfish /usr/local/bin/stockfish
[ -e ~/chess/aichessathon-starter/.venv ] || ln -s ~/chess/venv ~/chess/aichessathon-starter/.venv
cp ~/chess/bini_v5/tools/selfplay_sf.py ~/chess/bini_v4/tools/selfplay_sf.py
sed -e 's/70 + w/90 + w/' -e 's/101 + w/301 + w/' -e 's/worker_7\*/worker_9*/' ~/chess/bini_v5/tools/x86_start_s1.sh > ~/chess/bini_v5/tools/x86b_start_s1.sh
bash ~/chess/bini_v5/tools/x86b_start_s1.sh | tail -2
REMOTE
echo "$(date '+%F %T') box B set up"
