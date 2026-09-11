"""NNUE speed bench: fixed-depth search on a position set, reports knps and node counts.
Node counts must be IDENTICAL across speed-pass variants (same search, same eval) -- that is the
correctness oracle for an optimisation that must not change behaviour. Usage:
    BINI_NNUE=<net> python tests/bench_nnue.py [depth]"""
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bini_engine as E, bini_search as S, bini_nnue as N
t0 = time.perf_counter(); eng = E.Engine(use_nnue=True); E.warm_up(eng)
comp = time.perf_counter() - t0
depth = int(sys.argv[1]) if len(sys.argv) > 1 else 12
fens = [l.split(";")[0].strip() for l in open(Path(__file__).parent / "pos" / "sharp.epd") if l.strip()][:12]
tot_n = 0; tot_t = 0.0; sig = []
for fen in fens:
    eng.new_game(); eng.set_position(fen, [])
    t0 = time.perf_counter()
    mv, sc, d = eng.think(60000, 60000, log=False, max_depth=depth)
    dt = time.perf_counter() - t0
    n = int(eng.info[S.I_NODES]); tot_n += n; tot_t += dt; sig.append((mv, sc, n))
print(f"acc dtype {N.new_accumulators().dtype}  hidden {N.HIDDEN}  compile+warmup {comp:.1f}s")
print(f"depth {depth}: {tot_n} nodes in {tot_t:.2f}s = {tot_n/tot_t/1000:.0f} knps")
print("SIG " + " ".join(f"{m}:{s}:{n}" for m, s, n in sig))
