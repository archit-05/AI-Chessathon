"""Static evaluation (side to move) of a build on given FENs. usage: eval_probe.py <build_dir> <fen>..."""
import sys, os, time
sys.path.insert(0, sys.argv[1]); os.chdir(sys.argv[1])
t0 = time.perf_counter(); import bini_engine; e = bini_engine.Engine(use_nnue=True, tt_bits=16); print(f"compiled {time.perf_counter()-t0:.0f}s", flush=True)
for fen in sys.argv[2:]:
    e.set_position(fen, []); print(f"{e.static_eval():6d}  {fen}", flush=True)
