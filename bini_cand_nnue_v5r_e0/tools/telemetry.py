"""Summarise platform match logs (the .log files the dashboard offers next to each PGN).

    python tools/telemetry.py ../logs/*.log

Prints per game: result, our time use, slowest move, depth reached and nodes/s on the EPYC as
reported by our own stderr lines, and the init time. Use it after every rated round.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


def summarise(path: Path) -> None:
    text = path.read_text(errors="replace")
    get = lambda key: (re.search(rf"^\s*{key}\s+(.+)$", text, re.M) or [None, "?"])[1].strip()  # noqa: E731
    result = (re.search(r"RESULT\n\s+(.+)", text) or [None, "?"])[1].strip()
    ready = get("Ready in")
    left = get("Left at end")
    slowest = get("Slowest")
    depths = [int(d) for d in re.findall(r"bini-\S+ m\d+ d(\d+) ", text)]
    nodes = [(int(n), int(ms)) for n, ms in re.findall(r" (\d+)n (\d+)ms left", text)]
    nps = sum(n for n, _ in nodes) / max(1e-9, sum(ms for _, ms in nodes) / 1000.0) if nodes else 0.0
    print(f"{path.name}: {result} | init {ready} | left {left} | slowest {slowest} | depth avg {sum(depths) / len(depths) if depths else 0:.1f} min {min(depths) if depths else 0} | nps {nps / 1000:.0f}k")


def main() -> None:
    for arg in sys.argv[1:]:
        summarise(Path(arg))


if __name__ == "__main__":
    main()
