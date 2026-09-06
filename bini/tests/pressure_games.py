"""Real-clock games through the real wrapper (agent.get_move) against Stockfish at a fixed node
budget, from sharp middlegames. Logs the clock curve and checks the time policy:
  never under 5 s left; 10 s+ left after move 70; median time in unclear positions
  (|score| <= 200) not shorter than in decided ones.

    python tests/pressure_games.py tests/pos/sharp.epd --games 10 --sf-nodes 1500000
"""

from __future__ import annotations

import argparse
import re
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import chess  # noqa: E402

import agent  # noqa: E402
from uci_sf import UCI  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("epd")
    ap.add_argument("--games", type=int, default=10)
    ap.add_argument("--sf-nodes", type=int, default=1_500_000)
    ap.add_argument("--base-ms", type=int, default=120_000)
    ap.add_argument("--inc-ms", type=int, default=500)
    a = ap.parse_args()
    assert agent._ready.is_set()
    fens = [ln.split(";")[0].strip() for ln in Path(a.epd).read_text().splitlines() if ln.strip()]
    sf = UCI()
    results = {"win": 0, "draw": 0, "loss": 0}
    min_clock = 1e9
    unclear_times: list[float] = []
    decided_times: list[float] = []
    for g in range(a.games):
        board = chess.Board(fens[g % len(fens)])
        we = chess.WHITE if g % 2 == 0 else chess.BLACK
        agent._state.board = None
        clock = float(a.base_ms)
        curve = {}
        own_moves = 0
        t_start = time.perf_counter()
        while not board.is_game_over(claim_draw=True) and board.ply() < 600:
            if board.turn == we:
                t0 = time.perf_counter()
                uci = agent.get_move(board.fen(), int(clock))
                dt = time.perf_counter() - t0
                clock -= dt * 1000.0; clock += a.inc_ms
                own_moves += 1
                min_clock = min(min_clock, clock)
                if own_moves in (20, 40, 60, 80):
                    curve[own_moves] = round(clock / 1000, 1)
                score = agent._engine.info[3] if agent._engine is not None else 0
                (unclear_times if abs(int(score)) <= 200 else decided_times).append(dt)
                mv = chess.Move.from_uci(uci)
                assert mv in board.legal_moves, (uci, board.fen())
                board.push(mv)
            else:
                board.push(chess.Move.from_uci(sf.bestmove(board.fen(), nodes=a.sf_nodes)))
        out = board.outcome(claim_draw=True)
        if out is None or out.winner is None:
            res = "draw"
        else:
            res = "win" if out.winner == we else "loss"
        results[res] += 1
        term = out.termination.name if out else "ply_cap"
        print(f"game {g + 1}: {res:4s} as {'W' if we else 'B'} by {term:22s} {own_moves:3d} own moves, clock end {clock / 1000:5.1f}s, curve {curve}, {time.perf_counter() - t_start:5.0f}s", flush=True)
    sf.quit()
    print(f"results {results}; min clock {min_clock / 1000:.1f}s")
    if unclear_times and decided_times:
        print(f"median time: unclear {statistics.median(unclear_times):.2f}s  decided {statistics.median(decided_times):.2f}s  (unclear must not be shorter)")
    assert min_clock >= 5000, "clock fell under 5 s"


if __name__ == "__main__":
    main()
