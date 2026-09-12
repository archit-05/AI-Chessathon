"""Standalone NNUE-on speed check for one build: five middlegame positions, fixed 4 s each.
usage: nps.py <build_dir>"""
import os, sys, time
from pathlib import Path
build = Path(sys.argv[1]).resolve(); sys.path.insert(0, str(build)); os.environ.setdefault('BINI_TT_BITS', '22')
import bini_engine as E, bini_search as S
eng = E.Engine(use_nnue=True); E.warm_up(eng)
FENS = ["r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4",
        "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
        "r2q1rk1/ppp2ppp/2n1bn2/2b1p3/3pP3/2P2N1P/PP1N1PP1/R2QR1K1 b - - 0 11",
        "6k1/4Qpp1/p3p2p/qrNb4/7P/1PR2PP1/4P1K1/8 w - - 9 39",
        "r1bq1rk1/pp3pbp/2nppnp1/2p5/4P2P/2NP2P1/PPP1NPB1/R1BQ1RK1 w - - 0 9"]
tot_n = 0; tot_t = 0.0
for f in FENS:
    eng.new_game(); eng.set_position(f, [])
    t0 = time.perf_counter(); mv, sc, d = eng.think(4000, 4000, log=False); dt = time.perf_counter() - t0
    n = int(eng.info[S.I_NODES]); tot_n += n; tot_t += dt
    print(f"{build.name} {f[:20]:22s} d{d:2d} {mv} {sc:5d}cp {n:9d}n {dt:5.2f}s {n/dt/1000:7.1f} knps", flush=True)
print(f"{build.name} TOTAL {tot_n/tot_t/1000:.1f} knps nnue={eng.use_nnue}", flush=True)
