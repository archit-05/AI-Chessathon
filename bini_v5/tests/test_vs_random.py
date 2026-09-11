"""In-process games: agent.get_move (the real wrapper) against a random mover, python-chess as
referee with claim_draw. Verifies that a winning engine never lets a game end by repetition,
fifty-move rule or ply cap, and never returns an illegal move."""

from __future__ import annotations

import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import chess  # noqa: E402

import agent  # noqa: E402


def main() -> None:
    assert agent._ready.is_set(), "engine did not compile in time"
    rng = random.Random(5)
    games = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    ms = int(sys.argv[2]) if len(sys.argv) > 2 else 20000
    results = {}
    for g in range(games):
        board = chess.Board()
        we_are_white = g % 2 == 0
        agent._state.board = None  # new game
        clock = float(ms)
        while not board.is_game_over(claim_draw=True) and board.ply() < 600:
            if board.turn == chess.WHITE and we_are_white or board.turn == chess.BLACK and not we_are_white:
                t0 = time.perf_counter()
                uci = agent.get_move(board.fen(), int(clock))
                clock -= (time.perf_counter() - t0) * 1000.0
                clock += 500
                mv = chess.Move.from_uci(uci)
                assert mv in board.legal_moves, (uci, board.fen())
                board.push(mv)
            else:
                board.push(rng.choice(list(board.legal_moves)))
        out = board.outcome(claim_draw=True)
        term = out.termination.name if out else "ply_cap"
        won = out is not None and out.winner == (chess.WHITE if we_are_white else chess.BLACK)
        results[term] = results.get(term, 0) + 1
        print(f"game {g + 1}: {'WIN' if won else 'NOT WON'} by {term} in {board.fullmove_number} moves, clock left {clock / 1000:.1f}s", flush=True)
        if not won:
            print(board.fen())
            print(" ".join(m.uci() for m in board.move_stack))
    print(results)


if __name__ == "__main__":
    main()
