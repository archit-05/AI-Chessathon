"""Where does a node's time go? Measures, on one core:
  perft rate               move generation + make/unmake only
  static evaluation rate   NNUE forward pass from a refreshed accumulator (no updates)
  make+update rate         make/unmake with the incremental accumulator update
  search rate              the real search (NNUE), plus the share of nodes that are quiescence
  node counts              fixed-depth searches on five positions (for change-detection)

    python tools/profile.py [--ms 2000]
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402

import bini_board as B  # noqa: E402
import bini_engine as E  # noqa: E402
import bini_nnue as N  # noqa: E402
import bini_search as S  # noqa: E402

FENS = [
    "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
    "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4",
    "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
    "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1",
    "r2q1rk1/ppp2ppp/2n1bn2/2b1p3/3pP3/2P2N1P/PP1N1PP1/R2QR1K1 b - - 0 11",
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ms", type=int, default=2000)
    a = ap.parse_args()
    eng = E.Engine(use_nnue=True)
    E.warm_up(eng)
    # perft
    eng.set_position(FENS[2], [])
    t0 = time.perf_counter()
    n = B.perft(eng.bb, eng.st, eng.pcs, eng.mv, eng.ub, eng.ui, 4)
    dt = time.perf_counter() - t0
    print(f"perft(4) kiwipete: {n:,} leaves in {dt:.2f}s = {n / dt / 1e6:.2f} M leaves/s (movegen + make/unmake)")
    # static eval rate
    eng.set_position(FENS[1], [])
    t0 = time.perf_counter()
    k = 200_000
    for _ in range(k):
        S.evaluate(eng.bb, eng.st, eng.pcs, eng.acc, eng.info, eng.w2, eng.b2)
    dt = time.perf_counter() - t0
    print(f"static eval: {k / dt / 1e6:.2f} M/s ({dt / k * 1e9:.0f} ns each)")
    # make + incremental update rate over the legal moves
    eng.set_position(FENS[2], [])
    nm = B.gen_moves(eng.bb, eng.st, eng.pcs, eng.mv, 0, False)
    moves = [int(eng.mv[i]) for i in range(nm)]
    t0 = time.perf_counter()
    reps = 20_000
    cnt = 0
    for _ in range(reps):
        for m in moves:
            if B.make(eng.bb, eng.st, eng.pcs, m, eng.ub, eng.ui):
                N.nnue_after_make(eng.bb, eng.st, eng.pcs, eng.acc, eng.ui, m, eng.w1, eng.b1)
                B.unmake(eng.bb, eng.st, eng.pcs, eng.ub, eng.ui)
                cnt += 1
    dt = time.perf_counter() - t0
    print(f"make + nnue update + unmake: {cnt / dt / 1e6:.2f} M/s ({dt / cnt * 1e9:.0f} ns each; python call overhead included)")
    # search rate and quiescence share
    tot_n = tot_q = 0
    tot_t = 0.0
    for fen in FENS:
        eng.new_game(); eng.set_position(fen, [])
        t0 = time.perf_counter()
        eng.think(a.ms, a.ms * 1.5, log=False)
        dt = time.perf_counter() - t0
        tot_n += int(eng.info[S.I_NODES]); tot_t += dt
    print(f"search (NNUE): {tot_n / tot_t / 1000:.0f} knps over {tot_t:.1f}s")
    # fixed-depth node counts for change detection
    print("node counts at fixed depth 10 (must not change for a pure speed change):")
    for fen in FENS:
        eng.new_game(); eng.set_position(fen, [])
        eng.think(10**6, 10**6, max_depth=10, log=False)
        print(f"  {int(eng.info[S.I_NODES]):>9}  {fen[:40]}")


if __name__ == "__main__":
    main()
