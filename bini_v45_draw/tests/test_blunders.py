"""Blunder regression: positions from rated games where a shipped build played a losing move.
The engine must not repeat the recorded move at the real move budget.

    python tests/test_blunders.py [ms]
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import bini_engine as E  # noqa: E402


def main() -> None:
    ms = int(sys.argv[1]) if len(sys.argv) > 1 else 2500
    eng = E.Engine(use_nnue=True)
    E.warm_up(eng)
    rows = [ln for ln in (Path(__file__).parent / "pos" / "blunders.epd").read_text().splitlines() if ln.strip()]
    failures = 0
    for ln in rows:
        parts = [p.strip() for p in ln.split(";")]
        fen, avoid = parts[0], parts[1].split()[1]
        eng.new_game(); eng.set_position(fen, [])
        mv, sc, d = eng.think(ms, ms * 2, log=False)
        bad = mv == avoid
        failures += bad
        print(f"{'REPEATED' if bad else 'ok      '} {fen[:40]:40s} played {mv} {sc:+5d} d{d}  (avoid {avoid})  {parts[2] if len(parts) > 2 else ''}")
    print(f"blunder regression: {len(rows) - failures}/{len(rows)} avoided")
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
