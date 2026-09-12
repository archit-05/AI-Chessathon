#!/bin/bash
# Push everything a gate/labelling box needs from this Mac.  usage: push_to_box.sh <ssh-alias>
set -u; B="$1"; R="/Users/architbhardwaj/Desktop/AI Chessathon"; SP="$(dirname "$0")"
ssh "$B" 'mkdir -p ~/chess/tools_v85 ~/chess/bookbuild ~/chess/bini_v65 ~/chess/bini_v7'
rsync -az --exclude __pycache__ --exclude submission.zip "$R/bini_astra_v5_noc2b/" "$B:~/chess/bini_astra_v5_noc2b/"
rsync -az --exclude __pycache__ "$R/bini_v65/tools/" "$B:~/chess/bini_v65/tools/"
rsync -az --exclude __pycache__ --exclude bullet_trainer "$R/bini_v7/tools/" "$B:~/chess/bini_v7/tools/"
rsync -az --exclude __pycache__ --exclude .venv "$R/aichessathon-starter/" "$B:~/chess/aichessathon-starter/"
rsync -az --exclude __pycache__ "$R/astra_tests/" "$B:~/chess/astra_tests/"
rsync -az --exclude __pycache__ "$SP/bini_diag_leaf/" "$B:~/chess/bini_diag_leaf/"
rsync -az "$R/bini_v85_stable/tools/curated.epd" "$SP/arena_par.py" "$SP/microbench.py" "$SP/depth_bench.py" "$SP/nps.py" "$SP/pkg_smoke.py" "$B:~/chess/tools_v85/"
rsync -az "$SP/sf_book.py" "$SP/merge_book.py" "$SP/book_audit.py" "$SP/book_gate_report.py" "$SP/patch_guards.py" "$SP/leaf_dump.py" "$SP/leaf_profile.py" "$SP/label_leaf.py" "$SP/mine_errors.py" "$SP/roots.epd" "$B:~/chess/bookbuild/"
rsync -az "$SP/provision_box.sh" "$B:~/chess/"
for f in pkg_smoke.py net_gate.sh book_gate.sh combo_gate.sh; do scp -q "gcp-x86:~/chess/$f" "/tmp/_$f" && scp -q "/tmp/_$f" "$B:~/chess/$f"; done
ssh "$B" 'cp ~/chess/tools_v85/pkg_smoke.py ~/chess/pkg_smoke.py 2>/dev/null; chmod +x ~/chess/*.sh; ls ~/chess'
echo "pushed to $B"
