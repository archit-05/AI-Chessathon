"""Merge book files from the analysis workers into one book and grade every entry with Stockfish
(V5 Plan s3.3): an entry whose move loses more than --max-loss centipawns against Stockfish's
choice at --nodes is dropped, so the book cannot be worse than the grader. Entries keep their
provenance (depth, score, root, ply). Report at the end; ships as data/book.json.

    python tools/book_merge.py ../data/book_v5/*.json --out ../data/book.json --stockfish stockfish
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import chess  # noqa: E402
from grade import SF  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("books", nargs="+")
    ap.add_argument("--out", required=True)
    ap.add_argument("--nodes", type=int, default=120_000)
    ap.add_argument("--max-loss", type=int, default=15)
    ap.add_argument("--stockfish", default="stockfish")
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--count", type=int, default=10**9)
    a = ap.parse_args()
    book: dict[str, dict] = {}
    for f in a.books:
        for k, v in json.loads(Path(f).read_text()).items():
            if k not in book or v.get("ms", 0) > book[k].get("ms", 0) or (v.get("ms", 0) == book[k].get("ms", 0) and v.get("depth", 0) > book[k].get("depth", 0)):
                book[k] = v
    keys = sorted(book)[a.start : a.start + a.count]
    sf = SF(a.stockfish)
    kept: dict[str, dict] = {}
    losses, dropped = [], 0
    for i, k in enumerate(keys):
        board_fen, side, castling = k.split(" ")[:3]
        fen = f"{board_fen} {side} {castling} - 0 1"
        b = chess.Board(fen)
        mv = book[k]["move"]
        if chess.Move.from_uci(mv) not in b.legal_moves:
            dropped += 1
            continue
        before, sf_best = sf.score(fen, a.nodes)
        if mv == sf_best:
            loss = 0
        else:
            b2 = b.copy(); b2.push_uci(mv)
            after_them, _ = sf.score(b2.fen(), a.nodes)
            loss = max(0, min(1000, before + after_them))
        losses.append(loss)
        if loss > a.max_loss:
            dropped += 1
            continue
        e = dict(book[k]); e["grade"] = int(loss)
        kept[k] = e
        if (i + 1) % 100 == 0:
            print(f"  {i + 1}/{len(keys)}: kept {len(kept)}, dropped {dropped}, mean loss {statistics.mean(losses):.1f} cp", flush=True)
    Path(a.out).write_text(json.dumps(kept, indent=0))
    print(f"BOOK MERGE: {len(keys)} entries graded, kept {len(kept)}, dropped {dropped} (> {a.max_loss} cp or illegal); mean loss of graded {statistics.mean(losses) if losses else 0:.1f} cp, worst kept {max((e['grade'] for e in kept.values()), default=0)} -> {a.out}")
    sf.cmd("quit")


if __name__ == "__main__":
    main()
