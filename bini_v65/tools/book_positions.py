"""Book position list (V5 Plan s3.3): every position within PLIES plies of a curated root that
occurs at least MIN_N times across the scraped site games, with the moves the field played from
it. Output: EPD-like lines "fen ; n=<count> ; replies=<uci:count,...>" sorted by count, so the
book analysis (make_book.py --positions) can work through them most-common first.

    python tools/book_positions.py ../intel/raw/cache/games --plies 10 --min 3 --out tools/book_positions.txt
"""
from __future__ import annotations

import argparse
import io
import json
from collections import Counter, defaultdict
from pathlib import Path

import chess
import chess.pgn


def key(b: chess.Board) -> str:
    return f"{b.board_fen()} {'w' if b.turn else 'b'} {b.castling_xfen()} {chess.SQUARE_NAMES[b.ep_square] if b.ep_square is not None and b.has_legal_en_passant() else '-'}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("games_dir")
    ap.add_argument("--plies", type=int, default=10)
    ap.add_argument("--min", type=int, default=3)
    ap.add_argument("--out", default="tools/book_positions.txt")
    a = ap.parse_args()
    count: Counter = Counter()
    replies: dict[str, Counter] = defaultdict(Counter)
    fullfen: dict[str, str] = {}
    roots: Counter = Counter()
    n_games = 0
    for f in sorted(Path(a.games_dir).glob("*.json")):
        try:
            pgn = json.load(open(f)).get("pgn")
        except Exception:  # noqa: BLE001
            continue
        if not pgn:
            continue
        g = chess.pgn.read_game(io.StringIO(pgn))
        if g is None:
            continue
        b = g.board()
        n_games += 1
        roots[key(b)] += 1
        for i, m in enumerate(g.mainline_moves()):
            if i >= a.plies:
                break
            k = key(b)
            count[k] += 1
            replies[k][m.uci()] += 1
            fullfen.setdefault(k, b.fen())
            b.push(m)
    keep = [(n, k) for k, n in count.items() if n >= a.min]
    keep.sort(reverse=True)
    with open(a.out, "w") as fh:
        for n, k in keep:
            rep = ",".join(f"{m}:{c}" for m, c in replies[k].most_common(6))
            fh.write(f"{fullfen[k]} ; n={n} ; replies={rep}\n")
    print(f"{n_games} games, {len(roots)} distinct roots, {len(count)} positions within {a.plies} plies, {len(keep)} with >= {a.min} occurrences -> {a.out}")
    for lo, hi in ((3, 4), (5, 9), (10, 19), (20, 49), (50, 10**9)):
        print(f"  occurrences {lo}-{hi if hi < 10**9 else '+'}: {sum(1 for n, _ in keep if lo <= n <= hi)}")


if __name__ == "__main__":
    main()
