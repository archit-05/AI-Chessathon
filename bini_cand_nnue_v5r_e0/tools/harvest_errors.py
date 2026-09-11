"""Harvest our own errors from the site's game pages: every position where the site tagged our
move as inaccuracy, mistake, miss or blunder becomes (a) a regression row (FEN ; avoid <played>)
in tests/pos/harvest.epd and (b) a FEN for deep labelling (hard-example mining for the fine-tune).

    python tools/harvest_errors.py --games ../intel/raw/cache/games --team "Opus Carlsen" \
        --epd tests/pos/harvest.epd --fens ../data/hard_fens.txt [--since-round 31]

Also writes the position *before* each error and the two positions after it (the punishment and
the recovery), since those are where our evaluation was wrong, not only the move itself.
"""

from __future__ import annotations

import argparse
import io
import json
from pathlib import Path

import chess
import chess.pgn

BAD = {"inaccuracy", "mistake", "miss", "blunder"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", default=str(Path(__file__).resolve().parents[2] / "intel" / "raw" / "cache" / "games"))
    ap.add_argument("--team", default="Opus Carlsen")
    ap.add_argument("--epd", default=str(Path(__file__).resolve().parents[1] / "tests" / "pos" / "harvest.epd"))
    ap.add_argument("--fens", default=str(Path(__file__).resolve().parents[2] / "data" / "hard_fens.txt"))
    ap.add_argument("--since-round", type=int, default=31, help="v2 era onwards (v1 games teach nothing)")
    a = ap.parse_args()
    rows: list[str] = []
    fens: set[str] = set()
    games = 0
    for f in sorted(Path(a.games).glob("*.json")):
        try:
            d = json.load(open(f))
        except Exception:  # noqa: BLE001
            continue
        pgn = d.get("pgn")
        if not pgn or a.team not in pgn:
            continue
        game = chess.pgn.read_game(io.StringIO(pgn))
        if game is None:
            continue
        rnd = int(game.headers.get("Round", "0") or 0)
        if rnd < a.since_round:
            continue
        we = chess.WHITE if game.headers.get("White") == a.team else chess.BLACK
        verdicts = d.get("site_verdicts") or []
        board = game.board()
        moves = list(game.mainline_moves())
        games += 1
        for i, mv in enumerate(moves):
            if board.turn == we and i < len(verdicts) and verdicts[i][1] in BAD:
                san = board.san(mv)
                rows.append(f"{board.fen()} ; avoid {mv.uci()} ; R{rnd} {verdicts[i][1]} {san}")
                fens.add(board.fen())
                # the neighbourhood: one position before, and the two after
                b2 = board.copy()
                for k in range(2):
                    if i + k < len(moves):
                        b2.push(moves[i + k])
                        if not b2.is_game_over():
                            fens.add(b2.fen())
                if i >= 1:
                    b0 = game.board()
                    for m in moves[: i - 1]:
                        b0.push(m)
                    fens.add(b0.fen())
            board.push(mv)
    Path(a.epd).write_text("\n".join(rows) + ("\n" if rows else ""))
    Path(a.fens).write_text("\n".join(sorted(fens)) + ("\n" if fens else ""))
    print(f"{games} of our games since R{a.since_round}: {len(rows)} tagged errors -> {a.epd}; {len(fens)} positions -> {a.fens}")


if __name__ == "__main__":
    main()
