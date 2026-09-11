"""Fit the scalar that maps Stockfish 19 (normalised) centipawns onto the Lichess evaluation
database's mostly classical-scale labels, so the two data sources can be mixed.

    python tools/scale_fit.py sample ../data/lichessq3/chunk_0036.npz fens.txt --n 20000
    python tools/scale_fit.py evaluate fens.txt evals.txt --stockfish /path --depth 9
    python tools/scale_fit.py fit evals.txt

`fit` prints the least-squares scalar k in lichess_cp ~ k * sf19_cp over |cp| <= 800 and the
median absolute ratio, which is what --scale SFDIR:k in the trainer expects.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import numpy as np

CHARS = ".PNBRQKpnbrqk"


def to_fen(row: np.ndarray, stm: int) -> str:
    ranks = []
    for r in range(7, -1, -1):
        s, empty = "", 0
        for f in range(8):
            c = int(row[r * 8 + f])
            if c == 0:
                empty += 1
            else:
                if empty:
                    s += str(empty); empty = 0
                s += CHARS[c]
        if empty:
            s += str(empty)
        ranks.append(s)
    return "/".join(ranks) + (" w" if stm == 0 else " b") + " - - 0 1"


def plausible(b) -> bool:
    """The Lichess database holds some fantasy positions (seven knights a side); Stockfish exits on
    them, so keep only material a real game can produce (at most one promotion's worth extra)."""
    import chess  # noqa: PLC0415

    limits = {chess.PAWN: 8, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 3, chess.QUEEN: 2}
    for colour in (chess.WHITE, chess.BLACK):
        for pt, lim in limits.items():
            if len(b.pieces(pt, colour)) > lim:
                return False
        if len(b.pieces(chess.KING, colour)) != 1:
            return False
    return True


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["sample", "evaluate", "fit"])
    ap.add_argument("src")
    ap.add_argument("dst", nargs="?")
    ap.add_argument("--n", type=int, default=20000)
    ap.add_argument("--stockfish", default="stockfish")
    ap.add_argument("--depth", type=int, default=9)
    a = ap.parse_args()
    if a.mode == "sample":
        z = np.load(a.src)
        keep = (np.abs(z["cp"].astype(int)) <= 800) & (z["quiet"] == 1)
        idx = np.random.default_rng(5).choice(np.flatnonzero(keep), a.n, replace=False)
        with open(a.dst, "w") as fh:
            for i in idx:
                fh.write(f"{to_fen(z['pieces'][i], int(z['stm'][i]))};{int(z['cp'][i])}\n")
        print(f"{a.n} positions -> {a.dst}")
    elif a.mode == "evaluate":
        import chess  # noqa: PLC0415

        p = subprocess.Popen([a.stockfish], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)

        def cmd(s: str) -> None:
            p.stdin.write(s + "\n"); p.stdin.flush()  # type: ignore[union-attr]

        cmd("uci")
        while not p.stdout.readline().startswith("uciok"):  # type: ignore[union-attr]
            pass
        cmd("setoption name Threads value 1"); cmd("setoption name Hash value 32")
        n = 0
        with open(a.src) as fh, open(a.dst, "w") as out:
            for ln in fh:
                fen, cp = ln.strip().split(";")
                b = chess.Board(fen)
                if not b.is_valid() or b.is_check() or b.is_game_over() or not plausible(b):
                    continue
                cmd(f"position fen {fen}"); cmd(f"go depth {a.depth}")
                score = None
                while True:
                    line = p.stdout.readline()  # type: ignore[union-attr]
                    if not line:
                        raise RuntimeError(f"stockfish exited on {fen}")
                    if line.startswith("info") and " score cp " in line:
                        t = line.split(); score = int(t[t.index("cp") + 1])
                    elif line.startswith("info") and " score mate " in line:
                        score = None
                    elif line.startswith("bestmove"):
                        break
                if score is None:
                    continue
                sf_white = score if b.turn else -score
                out.write(f"{cp} {sf_white}\n")
                n += 1
                if n % 2000 == 0:
                    print(n, flush=True)
        cmd("quit")
        print(f"{n} evaluated -> {a.dst}")
    else:
        d = np.loadtxt(a.src)
        li, sf = d[:, 0], d[:, 1]
        m = (np.abs(sf) <= 800) & (np.abs(li) <= 800)
        li, sf = li[m], sf[m]
        k = float(np.dot(li, sf) / np.dot(sf, sf))
        nz = np.abs(sf) >= 30
        print(f"n {len(li)}  least-squares k {k:.3f}  median |lichess/sf19| {np.median(np.abs(li[nz] / sf[nz])):.3f}  corr {np.corrcoef(li, sf)[0, 1]:.3f}")
        print(f"residual MAE with k: {np.mean(np.abs(li - k * sf)):.1f} cp   without: {np.mean(np.abs(li - sf)):.1f} cp")


if __name__ == "__main__":
    sys.setrecursionlimit(10000)
    main()
