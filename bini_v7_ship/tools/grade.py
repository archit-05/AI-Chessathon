"""Fast move-quality grader: our engine moves at a fixed budget from real ladder positions and
Stockfish grades each move the way the site does (loss = eval before - eval after, side to move's
view, positions inside +-800 only, clipped to 1000).

    python tools/grade.py --games ../intel/raw/cache/games --n 400 --ms 2000 --stockfish stockfish
    python tools/grade.py --epd positions.epd ...          # a fixed set for before/after comparisons

Prints mean loss, median, blunder rate (>= 200) and the ten worst positions. Fifteen minutes for
400 positions; far less variance than a 300-game gate for evaluation and search changes. The
first run writes the sampled positions to --save so later runs compare on the same set.
"""

from __future__ import annotations

import argparse
import io
import json
import random
import statistics
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import chess  # noqa: E402
import chess.pgn  # noqa: E402

import bini_engine as E  # noqa: E402


class SF:
    def __init__(self, path: str) -> None:
        self.p = subprocess.Popen([path], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
        self.cmd("uci"); self.wait("uciok")
        self.cmd("setoption name Threads value 1"); self.cmd("setoption name Hash value 64")
        self.cmd("isready"); self.wait("readyok")

    def cmd(self, s: str) -> None:
        self.p.stdin.write(s + "\n"); self.p.stdin.flush()  # type: ignore[union-attr]

    def wait(self, token: str) -> str:
        while True:
            line = self.p.stdout.readline()  # type: ignore[union-attr]
            if not line:
                raise RuntimeError("stockfish exited")
            if line.startswith(token):
                return line.strip()

    def score(self, fen: str, nodes: int) -> tuple[int, str]:
        """(cp from the side to move's view, best move)."""
        self.cmd(f"position fen {fen}"); self.cmd(f"go nodes {nodes}")
        sc = 0
        while True:
            line = self.p.stdout.readline()  # type: ignore[union-attr]
            if line.startswith("info") and " score " in line and " pv " in line:
                t = line.split(); i = t.index("score")
                sc = int(t[i + 2]) if t[i + 1] == "cp" else (10000 - abs(int(t[i + 2]))) * (1 if int(t[i + 2]) > 0 else -1)
            elif line.startswith("bestmove"):
                return sc, line.split()[1]


def sample_positions(games_dir: Path, n: int, seed: int) -> list[str]:
    rng = random.Random(seed)
    fens: list[str] = []
    files = sorted(games_dir.glob("*.json"))
    rng.shuffle(files)
    for f in files:
        try:
            d = json.load(open(f))
        except Exception:  # noqa: BLE001
            continue
        pgn = d.get("pgn")
        if not pgn:
            continue
        game = chess.pgn.read_game(io.StringIO(pgn))
        if game is None:
            continue
        b = game.board()
        moves = list(game.mainline_moves())
        for i, mv in enumerate(moves):
            b.push(mv)
            if 12 <= i <= 80 and not b.is_game_over() and not b.is_check() and len(b.piece_map()) >= 8 and rng.random() < 0.06:
                fens.append(b.fen())
        if len(fens) >= n * 2:
            break
    rng.shuffle(fens)
    return fens[: n * 2]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", default=str(Path(__file__).resolve().parents[2] / "intel" / "raw" / "cache" / "games"))
    ap.add_argument("--epd")
    ap.add_argument("--save", default=str(Path(__file__).resolve().parents[1] / "tests" / "pos" / "grade.epd"))
    ap.add_argument("--n", type=int, default=400)
    ap.add_argument("--ms", type=int, default=2000)
    ap.add_argument("--nodes", type=int, default=120_000, help="Stockfish grading budget per position")
    ap.add_argument("--stockfish", default="stockfish")
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--tag", default="")
    a = ap.parse_args()
    src = Path(a.epd) if a.epd else Path(a.save)
    if src.exists():
        fens = [ln.split(";")[0].strip() for ln in src.read_text().splitlines() if ln.strip()]
        print(f"{len(fens)} positions from {src}")
    else:
        fens = sample_positions(Path(a.games), a.n, a.seed)
        Path(a.save).write_text("\n".join(fens) + "\n")
        print(f"{len(fens)} candidate positions sampled -> {a.save}")
    sf = SF(a.stockfish)
    eng = E.Engine(use_nnue=True)
    E.warm_up(eng)
    losses: list[tuple[int, str, str, str]] = []
    t0 = time.perf_counter()
    for fen in fens:
        if len(losses) >= a.n:
            break
        before, sf_best = sf.score(fen, a.nodes)
        if abs(before) > 800:
            continue
        eng.new_game(); eng.set_position(fen, [])
        mv, sc, d = eng.think(a.ms, a.ms * 2, log=False)
        if mv == sf_best:
            losses.append((0, fen, mv, sf_best))
            continue
        b = chess.Board(fen); b.push_uci(mv)
        if b.is_game_over():
            after = 0 if not b.is_checkmate() else -10000
        else:
            after_them, _ = sf.score(b.fen(), a.nodes)
            after = -after_them
        loss = max(0, min(1000, before - after))
        losses.append((loss, fen, mv, sf_best))
        if len(losses) % 50 == 0:
            ls = [x[0] for x in losses]
            print(f"  {len(losses)} graded: mean {statistics.mean(ls):.1f} median {statistics.median(ls):.0f} blunders {sum(x >= 200 for x in ls)}  {time.perf_counter() - t0:.0f}s", flush=True)
    ls = [x[0] for x in losses]
    print(f"\nGRADE {a.tag} n {len(ls)} ms {a.ms}: mean loss {statistics.mean(ls):.1f} cp, median {statistics.median(ls):.0f}, blunders (>=200) {sum(x >= 200 for x in ls)} = {100 * sum(x >= 200 for x in ls) / len(ls):.1f}%, exact best {100 * sum(x == 0 for x in ls) / len(ls):.0f}%")
    print("worst:")
    for loss, fen, mv, best in sorted(losses, reverse=True)[:10]:
        print(f"  {loss:4d}  played {mv}  best {best}  {fen}")
    sf.cmd("quit")


if __name__ == "__main__":
    main()
