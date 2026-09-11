"""Compile-time and speed check. Usage: python tests/bench.py [ms_per_position]"""
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
t0 = time.perf_counter()
import bini_engine as E
import bini_search as S
imp = time.perf_counter() - t0
eng = E.Engine(use_nnue=False)
t0 = time.perf_counter()
E.warm_up(eng)
print(f"import {imp:.2f}s  compile+warmup {time.perf_counter()-t0:.2f}s")
ms = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
fens = [
    "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
    "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4",
    "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
    "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1",
    "r2q1rk1/ppp2ppp/2n1bn2/2b1p3/3pP3/2P2N1P/PP1N1PP1/R2QR1K1 b - - 0 11",
]
total_nodes = 0; total_t = 0.0
for fen in fens:
    eng.new_game(); eng.set_position(fen, [])
    t0 = time.perf_counter()
    mv, sc, d = eng.think(ms, ms * 1.5, log=False)
    dt = time.perf_counter() - t0
    n = int(eng.info[S.I_NODES]); total_nodes += n; total_t += dt
    print(f"{fen[:30]:30s} {mv:6s} {sc:6d}cp d{d:2d}/{int(eng.info[S.I_SELDEPTH]):2d} {n:9d}n {dt*1000:6.0f}ms {n/dt/1000:6.0f} knps")
print(f"overall {total_nodes/total_t/1000:.0f} knps")
