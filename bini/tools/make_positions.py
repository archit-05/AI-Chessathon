"""Build test position sets from real games, labelled by a local Stockfish (raw UCI):

  sharp.epd     middlegames, 20+ pieces, |eval| <= 50cp       (time-pressure and gate games)
  winning.epd   side to move +200..+500                        (conversion vs strong defence)
  marginal.epd  side to move +50..+150                         (the half-point cases)
  puzzles.epd   a unique winning move: best - second >= 250cp and best >= +100 (tactics gate)
  drawn.epd     hand-picked theoretical draws                  (must not be "won" for 50 moves)

    python tools/make_positions.py <pgn files...> --out tests/pos --nodes 400000
"""

from __future__ import annotations

import argparse
import random
import subprocess
from pathlib import Path

import chess
import chess.pgn


class UCI:
    def __init__(self) -> None:
        self.p = subprocess.Popen(["stockfish"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
        self.cmd("uci"); self.wait("uciok")
        self.cmd("setoption name Threads value 1"); self.cmd("setoption name Hash value 16"); self.cmd("setoption name MultiPV value 2")
        self.cmd("isready"); self.wait("readyok")

    def cmd(self, s: str) -> None:
        self.p.stdin.write(s + "\n"); self.p.stdin.flush()  # type: ignore[union-attr]

    def wait(self, token: str) -> str:
        while True:
            line = self.p.stdout.readline()  # type: ignore[union-attr]
            if not line:
                raise RuntimeError("stockfish exited")
            if line.startswith(token):
                return line

    def eval2(self, fen: str, nodes: int) -> tuple[int | None, int | None, str | None]:
        """(best cp, second cp, best move) from the side to move's view; mates mapped to +-3000."""
        self.cmd(f"position fen {fen}"); self.cmd(f"go nodes {nodes}")
        best = second = None; bm = None
        while True:
            line = self.p.stdout.readline()  # type: ignore[union-attr]
            if line.startswith("bestmove"):
                bm = line.split()[1]; break
            if line.startswith("info") and " multipv " in line and " score " in line and " pv " in line:
                t = line.split()
                pv_i = int(t[t.index("multipv") + 1])
                si = t.index("score")
                cp = int(t[si + 2]) if t[si + 1] == "cp" else (3000 if int(t[si + 2]) > 0 else -3000)
                if pv_i == 1:
                    best = cp
                elif pv_i == 2:
                    second = cp
        return best, second, bm


DRAWN = [
    ("KR v KR", "8/8/4k3/8/8/4K3/8/r6R w - - 0 1"),
    ("opposite bishops", "8/5k2/8/2b5/8/2B5/5K2/8 w - - 0 1"),
    ("KRP v KR Philidor", "4k3/8/8/4P3/8/8/r7/4K2R b - - 0 1"),
    ("wrong bishop h-pawn", "7k/8/6KP/8/8/8/8/5B2 w - - 0 1"),
    ("KP v K opposition", "8/8/8/4k3/4P3/4K3/8/8 b - - 0 1"),
    ("KQ v KQ", "8/8/3k4/8/8/3K4/8/q6Q w - - 0 1"),
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("pgns", nargs="+")
    ap.add_argument("--out", default="tests/pos")
    ap.add_argument("--nodes", type=int, default=400_000)
    ap.add_argument("--per-set", type=int, default=40)
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(3)
    cands: list[tuple[str, int]] = []
    for pg in a.pgns:
        with open(pg, errors="replace") as fh:
            while True:
                g = chess.pgn.read_game(fh)
                if g is None:
                    break
                b = g.board()
                for ply, mv in enumerate(g.mainline_moves()):
                    b.push(mv)
                    if 20 <= ply <= 70 and not b.is_game_over() and not b.is_check() and rng.random() < 0.15:
                        cands.append((b.fen(), len(b.piece_map())))
    rng.shuffle(cands)
    sf = UCI()
    sets: dict[str, list[str]] = {"sharp": [], "winning": [], "marginal": [], "puzzles": []}
    for fen, npieces in cands:
        if all(len(v) >= a.per_set for v in sets.values()):
            break
        best, second, bm = sf.eval2(fen, a.nodes)
        if best is None or second is None or bm is None:
            continue
        if abs(best) <= 50 and npieces >= 20 and len(sets["sharp"]) < a.per_set:
            sets["sharp"].append(f"{fen} ; sharp eval {best}")
        elif 200 <= best <= 500 and len(sets["winning"]) < a.per_set:
            sets["winning"].append(f"{fen} ; winning eval {best}")
        elif 50 <= best <= 150 and len(sets["marginal"]) < a.per_set:
            sets["marginal"].append(f"{fen} ; marginal eval {best}")
        if best >= 100 and best - second >= 250 and len(sets["puzzles"]) < a.per_set:
            sets["puzzles"].append(f"{fen} ; bm {bm} ; best {best} second {second}")
    for name, rows in sets.items():
        (out / f"{name}.epd").write_text("\n".join(rows) + "\n")
        print(f"{name}: {len(rows)}")
    (out / "drawn.epd").write_text("\n".join(f"{fen} ; {name}" for name, fen in DRAWN) + "\n")
    print("drawn:", len(DRAWN))


if __name__ == "__main__":
    main()
