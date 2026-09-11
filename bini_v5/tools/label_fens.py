"""Label a list of FENs with Stockfish at a fixed depth into one training chunk (same format as
the other generators, result = 0 unknown). For the hard-example set: a few thousand positions
at depth 20 on one VM core.

    python tools/label_fens.py fens.txt out_dir/chunk_0000.npz --depth 20 --stockfish path
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

import chess
import numpy as np

CODES = {"P": 1, "N": 2, "B": 3, "R": 4, "Q": 5, "K": 6, "p": 7, "n": 8, "b": 9, "r": 10, "q": 11, "k": 12}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("fens")
    ap.add_argument("out")
    ap.add_argument("--depth", type=int, default=20)
    ap.add_argument("--stockfish", default="stockfish")
    a = ap.parse_args()
    fens = [ln.strip() for ln in Path(a.fens).read_text().splitlines() if ln.strip()]
    p = subprocess.Popen([a.stockfish], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)

    def cmd(s: str) -> None:
        p.stdin.write(s + "\n"); p.stdin.flush()  # type: ignore[union-attr]

    cmd("uci")
    while not p.stdout.readline().startswith("uciok"):  # type: ignore[union-attr]
        pass
    cmd("setoption name Threads value 1"); cmd("setoption name Hash value 128")
    P, S, C, Q = [], [], [], []
    t0 = time.perf_counter()
    for k, fen in enumerate(fens):
        b = chess.Board(fen)
        if not b.is_valid() or b.is_check() or b.is_game_over():
            continue
        cmd(f"position fen {fen}"); cmd(f"go depth {a.depth}")
        cp, best = None, None
        while True:
            line = p.stdout.readline()  # type: ignore[union-attr]
            if not line:
                raise RuntimeError("stockfish exited")
            if line.startswith("info") and " score " in line and " pv " in line:
                t = line.split(); i = t.index("score")
                cp = int(t[i + 2]) if t[i + 1] == "cp" else (3000 if int(t[i + 2]) > 0 else -3000)
                best = t[t.index("pv") + 1]
            elif line.startswith("bestmove"):
                break
        if cp is None:
            continue
        row = np.zeros(64, dtype=np.uint8)
        for sq, pc in b.piece_map().items():
            row[sq] = CODES[pc.symbol()]
        mv = chess.Move.from_uci(best) if best else None
        q = 0 if (mv and (b.is_capture(mv) or mv.promotion is not None)) else 1
        P.append(row); S.append(0 if b.turn else 1); C.append(max(-3000, min(3000, cp if b.turn else -cp))); Q.append(q)
        if (k + 1) % 200 == 0:
            print(f"{k + 1}/{len(fens)} {time.perf_counter() - t0:.0f}s", flush=True)
    cmd("quit")
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    np.savez(a.out, pieces=np.array(P, dtype=np.uint8), stm=np.array(S, dtype=np.uint8), cp=np.array(C, dtype=np.int16), depth=np.full(len(C), a.depth, dtype=np.uint8), quiet=np.array(Q, dtype=np.uint8), result=np.zeros(len(C), dtype=np.int8))
    print(f"{len(C)} positions labelled at depth {a.depth} -> {a.out} in {time.perf_counter() - t0:.0f}s")


if __name__ == "__main__":
    sys.setrecursionlimit(10000)
    main()
