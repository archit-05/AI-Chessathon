"""Root search score at fixed nodes for a build. usage: search_probe.py <build_dir> <nodes> <fen>..."""
import sys, os, time
sys.path.insert(0, sys.argv[1]); os.chdir(sys.argv[1])
import bini_engine; e = bini_engine.Engine(use_nnue=True, tt_bits=20); nodes = int(sys.argv[2])
for fen in sys.argv[3:]:
    e.new_game(); e.set_position(fen, []); st = e.static_eval()
    mv, sc, d = e.think(60000.0, 60000.0, log=False, max_nodes=nodes)
    print(f"static {st:5d}  search {sc:5d} d{d:<2d} {mv}   {fen}", flush=True)
