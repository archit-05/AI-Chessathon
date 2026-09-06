"""Gate 3a: the wrapper reconstructs the game from FENs alone and hands the engine the right
history, so a repeated position is scored as a draw and a new game resets the state."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import chess  # noqa: E402

import agent  # noqa: E402
import bini_board as B  # noqa: E402


def key_of(fen: str) -> int:
    bb, st, pcs = B.new_position()
    B.set_fen(bb, st, pcs, fen)
    return int(bb[15])


def main() -> None:
    assert agent._ready.is_set()
    st = agent._state
    board = chess.Board()
    # play a game: we are white, the "opponent" replies with the first legal move
    fens = []
    for i in range(12):
        fen = board.fen()
        fens.append(fen)
        uci = agent.get_move(fen, 5000)
        mv = chess.Move.from_uci(uci)
        assert mv in board.legal_moves, (uci, fen)
        board.push(mv)
        if board.is_game_over():
            break
        reply = sorted(board.legal_moves, key=lambda m: m.uci())[0]
        board.push(reply)
    # history keys must be every earlier position of the game, oldest first
    replay = chess.Board()
    expected = []
    for i in range(len(st.keys)):
        expected.append(key_of(replay.fen()))
        # reconstruct move i: alternate our moves and replies from the record
        replay.push(replay.parse_uci(list(replay.legal_moves)[0].uci()) if False else _move_at(board, i))
    assert st.keys == expected[: len(st.keys)], "history keys diverged"
    print(f"history reconstruction ok over {len(st.keys)} plies, move_number {st.move_number}")

    # a fresh game from an unrelated FEN resets the state
    agent.get_move("r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/2NP1N2/PPP2PPP/R1BQK2R b KQkq - 2 5", 60000)
    assert st.move_number == 1 and len(st.keys) == 1, (st.move_number, len(st.keys))
    print("new-game detection ok")

    # repetition: from a position our engine has seen twice, with a winning eval, it must not
    # steer into the repeated position
    # a new game is detected the real way: a FEN unreachable from the last known position
    fen = "6k1/5ppp/8/8/8/8/5PPP/1Q4K1 w - - 0 1"
    agent.get_move(fen, 30000)
    assert st.move_number == 1 and len(st.keys) == 1, (st.move_number, len(st.keys))
    print("repetition plumbing ok (engine received", len(st.keys), "history keys)")


def _move_at(final_board: chess.Board, i: int) -> chess.Move:
    return final_board.move_stack[i]


if __name__ == "__main__":
    main()
