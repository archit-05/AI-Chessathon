"""Opening book from our own engine's analysis of the curated start positions.

For every position in tools/curated.epd the engine searches for --ms milliseconds and the
principal variation (up to --plies plies) is read back from its transposition table. Every
position along that line, with the move the line continues with, becomes a book entry keyed by
the board, side to move and castling rights. At play time the wrapper plays the book move when
the position matches, whichever colour we are; the first deviation by the opponent leaves the
book. The book is our own engine's output, shipped as data (book.json), and this script plus the
log it writes are the record of how it was made.

    python tools/make_book.py --ms 60000 --plies 8 --out ../data/book.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import chess  # noqa: E402

import bini_engine as E  # noqa: E402


def key(board: chess.Board) -> str:
    return f"{board.board_fen()} {'w' if board.turn else 'b'} {board.castling_xfen()}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--epd", default=str(Path(__file__).with_name("curated.epd")))
    ap.add_argument("--ms", type=int, default=60000)
    ap.add_argument("--plies", type=int, default=8)
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[2] / "data" / "book.json"))
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--count", type=int, default=100000)
    a = ap.parse_args()
    fens = [ln.split(";")[0].strip() for ln in Path(a.epd).read_text().splitlines() if ln.strip()]
    fens = fens[a.start : a.start + a.count]
    out = Path(a.out)
    book: dict[str, dict] = json.loads(out.read_text()) if out.exists() else {}
    eng = E.Engine(use_nnue=True)
    E.warm_up(eng)
    log = open(out.with_suffix(".log"), "a")
    t0 = time.perf_counter()
    for i, fen in enumerate(fens):
        board = chess.Board(fen)
        if key(board) in book and book[key(board)].get("ms", 0) >= a.ms:
            continue
        eng.new_game()
        eng.set_position(fen, [])
        mv, score, depth = eng.think(a.ms, a.ms * 1.2, log=False)
        line = eng.pv_line(a.plies)
        if not line or line[0] != mv:
            line = [mv] + line[1:] if line else [mv]
        b = board.copy()
        added = 0
        for ply, uci in enumerate(line):
            m = chess.Move.from_uci(uci)
            if m not in b.legal_moves:
                break
            k = key(b)
            if k not in book or ply == 0:
                book[k] = {"move": uci, "ms": a.ms if ply == 0 else 0, "depth": int(depth), "score": int(score), "root": fen, "ply": ply}
                added += 1
            b.push(m)
        print(f"{i + a.start + 1:3d} d{depth} {score:+5d} {' '.join(line)}  (+{added} entries, {time.perf_counter() - t0:.0f}s)", file=log, flush=True)
        out.write_text(json.dumps(book, indent=0))
    print(f"book: {len(book)} entries -> {out}")


if __name__ == "__main__":
    main()
