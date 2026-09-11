"""Is the book better than the engine's own first move? For every curated start position, grade
the book's root move and the engine's move at the in-game budget with Stockfish (120k nodes
before and after), and report the mean loss of each. The book ships only if it is not worse.

    python tools/book_check.py --book ../data/book.json --ms 3800 --stockfish stockfish
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import chess  # noqa: E402

import bini_engine as E  # noqa: E402
from grade import SF  # noqa: E402


def key(board: chess.Board) -> str:
    return f"{board.board_fen()} {'w' if board.turn else 'b'} {board.castling_xfen()}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", default=str(Path(__file__).resolve().parents[2] / "data" / "book.json"))
    ap.add_argument("--epd", default=str(Path(__file__).with_name("curated.epd")))
    ap.add_argument("--ms", type=int, default=3800)
    ap.add_argument("--nodes", type=int, default=120_000)
    ap.add_argument("--stockfish", default="stockfish")
    ap.add_argument("--n", type=int, default=1000)
    a = ap.parse_args()
    book = json.loads(Path(a.book).read_text())
    fens = [ln.split(";")[0].strip() for ln in Path(a.epd).read_text().splitlines() if ln.strip()][: a.n]
    sf = SF(a.stockfish)
    eng = E.Engine(use_nnue=True)
    E.warm_up(eng)
    lb, le, same = [], [], 0
    for i, fen in enumerate(fens):
        b = chess.Board(fen)
        entry = book.get(key(b))
        if not entry:
            continue
        before, sf_best = sf.score(fen, a.nodes)
        eng.new_game(); eng.set_position(fen, [])
        em, _, _ = eng.think(a.ms, a.ms * 1.5, log=False)
        bm = entry["move"]
        same += bm == em
        for mv, acc in ((bm, lb), (em, le)):
            if mv == sf_best:
                acc.append(0); continue
            b2 = b.copy(); b2.push_uci(mv)
            after_them, _ = sf.score(b2.fen(), a.nodes)
            acc.append(max(0, min(1000, before + after_them)))
        if (i + 1) % 40 == 0:
            print(f"  {i + 1}: book {statistics.mean(lb):.1f} cp, engine {statistics.mean(le):.1f} cp, same move {same}/{len(lb)}", flush=True)
    print(f"\nBOOK CHECK n {len(lb)}: book mean loss {statistics.mean(lb):.1f} cp (blunders {sum(x >= 200 for x in lb)}), engine at {a.ms} ms {statistics.mean(le):.1f} cp (blunders {sum(x >= 200 for x in le)}), same move {same}/{len(lb)}")
    sf.cmd("quit")


if __name__ == "__main__":
    main()
