"""Calibrate the 'top-team proxy': the Stockfish node budget whose move quality, measured by the
site grader (120k nodes), matches the strongest teams (CPL ~10-12 by our scraped estimates).

    python tools/proxy_calib.py pgn [pgn ...] --budgets 20000 40000 80000 --positions 120
"""
from __future__ import annotations

import argparse
import random
import statistics
import subprocess

import chess
import chess.pgn


class SF:
    def __init__(self) -> None:
        self.p = subprocess.Popen(["stockfish"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
        self.cmd("uci"); self.wait("uciok")
        self.cmd("setoption name Threads value 1"); self.cmd("setoption name Hash value 64")
        self.cmd("isready"); self.wait("readyok")

    def cmd(self, s: str) -> None:
        self.p.stdin.write(s + "\n"); self.p.stdin.flush()

    def wait(self, token: str) -> str:
        while True:
            line = self.p.stdout.readline()
            if not line:
                raise RuntimeError("stockfish exited")
            if line.startswith(token):
                return line.strip()

    def go(self, fen: str, nodes: int) -> tuple[str, int]:
        self.cmd("ucinewgame"); self.cmd(f"position fen {fen}"); self.cmd(f"go nodes {nodes}")
        score = 0
        while True:
            line = self.p.stdout.readline()
            if line.startswith("info") and " score " in line and " pv " in line:
                t = line.split()
                i = t.index("score")
                score = int(t[i + 2]) if t[i + 1] == "cp" else (20000 if int(t[i + 2]) > 0 else -20000)
            elif line.startswith("bestmove"):
                return line.split()[1], score


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("pgn", nargs="+")
    ap.add_argument("--budgets", type=int, nargs="+", default=[20000, 40000, 80000])
    ap.add_argument("--positions", type=int, default=120)
    ap.add_argument("--grader", type=int, default=120000)
    a = ap.parse_args()
    rng = random.Random(7)
    fens: list[str] = []
    for path in a.pgn:
        with open(path) as fh:
            while True:
                g = chess.pgn.read_game(fh)
                if g is None:
                    break
                b = g.board()
                for i, mv in enumerate(g.mainline_moves()):
                    b.push(mv)
                    if 16 <= i <= 70 and rng.random() < 0.08:
                        fens.append(b.fen())
    rng.shuffle(fens)
    fens = fens[: a.positions * 2]
    sf = SF()
    losses: dict[int, list[int]] = {n: [] for n in a.budgets}
    used = 0
    for fen in fens:
        if used >= a.positions:
            break
        best_mv, before = sf.go(fen, a.grader)
        if abs(before) > 300:
            continue
        used += 1
        b = chess.Board(fen)
        for n in a.budgets:
            mv, _ = sf.go(fen, n)
            if mv == best_mv:
                losses[n].append(0)
                continue
            b2 = b.copy(); b2.push_uci(mv)
            if b2.is_game_over():
                continue
            _, after = sf.go(b2.fen(), a.grader)
            loss = max(0, min(1000, before + after))
            losses[n].append(loss)
    sf.p.kill()
    print(f"{used} positions, grader {a.grader} nodes")
    for n in a.budgets:
        ls = losses[n]
        print(f"budget {n:7d}: mean cpl {statistics.mean(ls):5.1f}  median {statistics.median(ls):3.0f}  blunders>=200 {sum(l >= 200 for l in ls)}/{len(ls)}")


if __name__ == "__main__":
    main()
