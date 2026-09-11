"""Tactics gate: Stockfish-verified unique winning moves must be found at the real move budget.

    python tests/test_tactics.py tests/pos/puzzles.epd --ms 2000 --min-rate 0.9
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import bini_engine as E  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("epd")
    ap.add_argument("--ms", type=int, default=2000)
    ap.add_argument("--min-rate", type=float, default=0.9)
    a = ap.parse_args()
    eng = E.Engine(use_nnue=True)
    E.warm_up(eng)
    rows = [ln for ln in Path(a.epd).read_text().splitlines() if ln.strip()]
    solved = 0
    for ln in rows:
        parts = [p.strip() for p in ln.split(";")]
        fen, bm = parts[0], parts[1].split()[1]
        eng.new_game(); eng.set_position(fen, [])
        mv, sc, d = eng.think(a.ms, a.ms * 1.5, log=False)
        ok = mv == bm
        solved += ok
        if not ok:
            print(f"MISS  {fen}  expected {bm} got {mv} ({sc}cp d{d})")
    rate = solved / len(rows)
    print(f"tactics: {solved}/{len(rows)} = {rate:.0%}")
    assert rate >= a.min_rate, "tactics gate failed"


if __name__ == "__main__":
    main()
