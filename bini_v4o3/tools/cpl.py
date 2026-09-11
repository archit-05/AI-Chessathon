"""Average centipawn loss per player with Stockfish (local analysis only).

    python tools/cpl.py games.pgn [--nodes 200000] [--player NAME]

For every move: eval before (mover's view) minus eval after, clipped to [0, 1000]; positions with
|eval| > 800 before the move are skipped (decided games teach nothing about strength).
"""

from __future__ import annotations

import argparse
import statistics
from collections import defaultdict

import chess
import chess.engine
import chess.pgn


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("pgn")
    ap.add_argument("--nodes", type=int, default=200_000)
    ap.add_argument("--player")
    a = ap.parse_args()
    eng = chess.engine.SimpleEngine.popen_uci("stockfish")
    eng.configure({"Threads": 1, "Hash": 128})
    losses: dict[str, list[int]] = defaultdict(list)
    blunders: dict[str, int] = defaultdict(int)
    games = 0
    with open(a.pgn) as fh:
        while True:
            game = chess.pgn.read_game(fh)
            if game is None:
                break
            games += 1
            board = game.board()
            names = {chess.WHITE: game.headers.get("White", "?"), chess.BLACK: game.headers.get("Black", "?")}
            info = eng.analyse(board, chess.engine.Limit(nodes=a.nodes))
            before = info["score"].pov(board.turn).score(mate_score=2000)
            for mv in game.mainline_moves():
                mover = board.turn
                name = names[mover]
                board.push(mv)
                if board.is_game_over():
                    break
                info = eng.analyse(board, chess.engine.Limit(nodes=a.nodes))
                after_mover = -info["score"].pov(board.turn).score(mate_score=2000)
                if before is not None and abs(before) <= 800 and (a.player is None or a.player.lower() in name.lower()):
                    loss = max(0, min(1000, before - after_mover))
                    losses[name].append(loss)
                    if loss >= 200:
                        blunders[name] += 1
                before = -after_mover if after_mover is not None else None
                before = info["score"].pov(board.turn).score(mate_score=2000)
    eng.quit()
    print(f"{games} games analysed at {a.nodes} nodes/position")
    rows = sorted(losses.items(), key=lambda kv: statistics.mean(kv[1]))
    for name, ls in rows:
        if len(ls) >= 40:
            print(f"{name:28s} moves {len(ls):5d}  mean cpl {statistics.mean(ls):6.1f}  median {statistics.median(ls):4.0f}  blunders(>=200) {blunders[name]:3d} ({100 * blunders[name] / len(ls):.1f}%)")


if __name__ == "__main__":
    main()
