#!/bin/bash
# gcp-x86: <src_build> -> <ship_build> with the init patch, build numba's cache by one import, harvest it into nbcache/, zip.
# usage: build_cache.sh <src_build_dir> <ship_build_dir> <zip_name>
set -u; cd ~/chess; V=~/chess/venv/bin/python; SRC="$1"; DST="$2"; ZIP="$3"
rm -rf "$DST"; cp -r "$SRC" "$DST"; rm -rf "$DST/__pycache__" "$DST/tools" "$DST/nbcache"
$V patch_cache.py "$DST"
rm -rf /tmp/bini_pkg /tmp/bini_cache
echo "--- first import (compiles and writes the cache) ---"
(cd "$DST" && env -u BINI_JOIN_S BINI_JOIN_S=120 $V -c "import time; t=time.perf_counter(); import agent; print(f'import {time.perf_counter()-t:.1f}s ready={agent._ready.is_set()} compile={agent._compile_seconds:.1f}s')" 2>&1 | grep -v "^bini-5.0 m")
echo "cache tree:"; find /tmp/bini_cache -type f | wc -l; du -sh /tmp/bini_cache | cut -f1
cp -r /tmp/bini_cache "$DST/nbcache"
echo "--- second import, fresh process, fresh /tmp (must be fast, ready=True) ---"
rm -rf /tmp/bini_pkg /tmp/bini_cache
(cd "$DST" && env -u BINI_JOIN_S $V -c "import time; t=time.perf_counter(); import agent; print(f'import {time.perf_counter()-t:.1f}s ready={agent._ready.is_set()} compile={agent._compile_seconds:.1f}s')" 2>&1 | grep -v "^bini-5.0 m")
(cd "$DST" && sha256sum agent.py bini_*.py nnue.safetensors book.json) > gates/${DST}_manifest.txt
$V build_packages.py "$DST:$ZIP" | grep -v "^    "
