"""Diagnostic match: a few games between two engine directories through the harness, keeping the
PGN and both engines' per-move score lines, then Stockfish grades every move of the candidate so
we can see WHERE it loses (phase, drift vs blunder, own-score trajectory vs the truth).

    python tools/diag_match.py ../bini_v4o ../bini_v3b --games 4 --base-ms 10000 --inc-ms 100 --out ../data/diag_v4o
"""

from __future__ import annotations

import argparse
import io
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "aichessathon-starter"))
import chess  # noqa: E402
import chess.pgn  # noqa: E402

from harness.referee import play_match  # noqa: E402
from harness.sandbox import local  # noqa: E402


class SF:
    def __init__(self) -> None:
        self.p = subprocess.Popen(["stockfish"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
        self.cmd("uci"); self.wait("uciok"); self.cmd("setoption name Threads value 1"); self.cmd("setoption name Hash value 64"); self.cmd("isready"); self.wait("readyok")

    def cmd(self, s):
        self.p.stdin.write(s + "\n"); self.p.stdin.flush()

    def wait(self, t):
        while True:
            ln = self.p.stdout.readline()
            if ln.startswith(t):
                return ln

    def score(self, fen, nodes=150000):
        self.cmd(f"position fen {fen}"); self.cmd(f"go nodes {nodes}"); sc = 0
        while True:
            ln = self.p.stdout.readline()
            if ln.startswith("info") and " score " in ln and " pv " in ln:
                t = ln.split(); i = t.index("score"); sc = int(t[i + 2]) if t[i + 1] == "cp" else (10000 if int(t[i + 2]) > 0 else -10000)
            elif ln.startswith("bestmove"):
                return sc


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cand"); ap.add_argument("base")
    ap.add_argument("--games", type=int, default=4)
    ap.add_argument("--base-ms", type=int, default=10000); ap.add_argument("--inc-ms", type=int, default=100)
    ap.add_argument("--openings", default=str(Path(__file__).with_name("curated.epd")))
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    fens = [ln.split(";")[0].strip() for ln in Path(a.openings).read_text().splitlines() if ln.strip()]
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    sf = SF()
    for g in range(a.games):
        fen = fens[g // 2]
        cand_white = g % 2 == 0
        w, b = (a.cand, a.base) if cand_white else (a.base, a.cand)
        W, B = local(Path(w)), local(Path(b))
        oc = play_match(W, B, a.base_ms, a.inc_ms, start_fen=fen)
        cand_agent = W if cand_white else B
        (out / f"game{g}.pgn").write_text(oc.pgn)
        (out / f"game{g}.cand.log").write_text(cand_agent.stderr_tail)
        res = "cand " + ("WIN" if (oc.result == "white") == cand_white and oc.result != "draw" else ("DRAW" if oc.result == "draw" else "LOSS"))
        # grade the candidate's moves with Stockfish and show its own score next to the truth
        game = chess.pgn.read_game(io.StringIO(oc.pgn)); board = game.board()
        own = [int(m) for m in re.findall(r" m\d+ d\d+ \S+ (-?\d+)cp ", cand_agent.stderr_tail)]
        rows = []; k = 0
        before = sf.score(board.fen())
        for i, mv in enumerate(game.mainline_moves()):
            mover_cand = board.turn == (chess.WHITE if cand_white else chess.BLACK)
            board.push(mv)
            after = -sf.score(board.fen()) if not board.is_game_over() else (0 if not board.is_checkmate() else -10000)
            if mover_cand:
                loss = max(0, min(1000, before - after))
                rows.append((i // 2 + 1, mv.uci(), before, own[k] if k < len(own) else None, loss)); k += 1
            before = -after
        worst = sorted(rows, key=lambda r: -r[4])[:6]
        phases = {"1-15": [], "16-40": [], "41+": []}
        for r in rows:
            (phases["1-15"] if r[0] <= 15 else phases["16-40"] if r[0] <= 40 else phases["41+"]).append(r[4])
        ph = "  ".join(f"{k}: {sum(v)/len(v):.0f}cp/{len(v)}" for k, v in phases.items() if v)
        print(f"game {g} {res} as {'W' if cand_white else 'B'} {oc.termination} {len(rows)} own moves | loss by phase {ph}", flush=True)
        print("   worst (move, uci, SF before, own score, loss): " + "; ".join(f"{r[0]}.{r[1]} SF{r[2]:+d} own{'' if r[3] is None else r[3]:+} -{r[4]}" for r in worst), flush=True)
    sf.cmd("quit")


if __name__ == "__main__":
    main()
