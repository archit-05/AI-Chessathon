"""Does the opponent's play, as seen from our side of the board, reveal its strength early?

For every platform game log with its PGN: the opponent's think time per move comes from the PGN
clocks, the "gift" per opponent move is the rise in our root score across their move (our own
log's score line), and the running average `og` (EMA 0.8/0.2, gifts only) is what the adaptive
draw policy would see. Prints, per game, the opponent's rating, its mean think time and the
`og` value after 5, 10 and 20 of our moves, then the correlation with rating.

    python tools/opp_signal.py ../logs/aichessathon-round-*.log
"""

from __future__ import annotations

import io
import re
import sys
from pathlib import Path

import chess.pgn
import numpy as np


def parse_log(path: Path) -> dict | None:
    text = path.read_text(errors="replace")
    scores = [int(m) for m in re.findall(r"bini-\S+ m\d+ d\d+ \S+ (-?\d+)cp ", text)]
    if len(scores) < 6:
        return None
    opp = (re.search(r"Opponent\s+(.+)", text) or [None, "?"])[1].strip()
    colour = (re.search(r"Colour\s+(\w+)", text) or [None, "?"])[1].strip()
    rnd = (re.search(r"Rated (\d+)", text) or [None, "0"])[1]
    return {"scores": scores, "opp": opp, "colour": colour, "round": int(rnd)}


def opp_times(pgn_path: Path, we_white: bool) -> list[float]:
    if not pgn_path.exists():
        return []
    game = chess.pgn.read_game(io.StringIO(pgn_path.read_text(errors="replace")))
    if game is None:
        return []
    clocks = []
    node = game
    turn = game.board().turn
    while node.variations:
        node = node.variations[0]
        m = re.search(r"\[%clk (\d+):(\d+):([\d.]+)\]", node.comment or "")
        clocks.append((turn, float(m.group(1)) * 3600 + float(m.group(2)) * 60 + float(m.group(3)) if m else None))
        turn = not turn
    them = not we_white
    prev = None
    times = []
    for t, c in clocks:
        if t == them and c is not None:
            if prev is not None:
                times.append(max(0.0, prev - c + 0.5))
            prev = c
    return times


def main() -> None:
    rows = []
    for arg in sys.argv[1:]:
        p = Path(arg)
        d = parse_log(p)
        if not d:
            continue
        s = d["scores"]
        gifts = [max(0, s[i + 1] - s[i]) for i in range(len(s) - 1) if abs(s[i]) < 20000 and abs(s[i + 1]) < 20000]
        og, traj = 0.0, []
        for g in gifts:
            og = 0.8 * og + 0.2 * g
            traj.append(og)
        times = opp_times(p.with_suffix(".pgn"), d["colour"] == "White")
        rows.append((d["round"], d["opp"], np.mean(times) if times else float("nan"), traj[4] if len(traj) > 4 else float("nan"), traj[9] if len(traj) > 9 else float("nan"), traj[19] if len(traj) > 19 else float("nan"), np.mean(gifts) if gifts else 0.0))
    rows.sort()
    print(f"{'round':>5} {'opponent':<22} {'opp s/mv':>8} {'og@5':>6} {'og@10':>6} {'og@20':>6} {'mean gift':>9}")
    for r in rows:
        print(f"R{r[0]:<4} {r[1][:22]:<22} {r[2]:8.2f} {r[3]:6.0f} {r[4]:6.0f} {r[5]:6.0f} {r[6]:9.1f}")


if __name__ == "__main__":
    main()
