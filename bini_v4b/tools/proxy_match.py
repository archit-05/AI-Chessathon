"""AlphaFish proxy match: the acceptance test for V4.

Our engine, through the real wrapper (agent.get_move, real clock 120 s + 0.5 s), against
Stockfish held to AlphaFish's level and clock habit:
  * strength: a node budget whose grader loss is near AlphaFish's 8 cp (about 20k nodes),
  * clock habit: it spends 4% of a simulated remaining clock per move, so its node budget is
    scaled by (0.04 * clock_left) / 1.7 s and thins after move 30 exactly as AlphaFish's does.
Games alternate colours from the curated start positions. Prints the score, per-game results
and our clock curve. First-capable means >= 50% over 40 games.

    python tools/proxy_match.py --games 40 --nodes 20000 --stockfish stockfish
"""

from __future__ import annotations

import argparse
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))

import chess  # noqa: E402

import agent  # noqa: E402
from uci_sf import UCI  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--epd", default=str(Path(__file__).with_name("curated.epd")))
    ap.add_argument("--games", type=int, default=40)
    ap.add_argument("--nodes", type=int, default=20000, help="Stockfish nodes at its mean move time")
    ap.add_argument("--share", type=float, default=0.04, help="share of its remaining clock per move")
    ap.add_argument("--mean-s", type=float, default=1.7, help="its mean seconds per move (AlphaFish: 1.7)")
    ap.add_argument("--base-ms", type=int, default=120_000)
    ap.add_argument("--inc-ms", type=int, default=500)
    ap.add_argument("--stockfish", default="stockfish")
    ap.add_argument("--start", type=int, default=0, help="index of the first curated position")
    a = ap.parse_args()
    agent._ready.wait()
    fens = [ln.split(";")[0].strip() for ln in Path(a.epd).read_text().splitlines() if ln.strip()]
    sf = UCI()
    w = d = l = 0
    end_clocks: list[float] = []
    t_all = time.perf_counter()
    for g in range(a.games):
        fen = fens[(a.start + g // 2) % len(fens)]
        board = chess.Board(fen)
        we = chess.WHITE if g % 2 == 0 else chess.BLACK
        agent._state.board = None
        clock = float(a.base_ms)
        sf_clock = float(a.base_ms)
        own = 0
        t0 = time.perf_counter()
        while not board.is_game_over(claim_draw=True) and board.ply() < 600:
            if board.turn == we:
                t1 = time.perf_counter()
                uci = agent.get_move(board.fen(), int(clock))
                clock -= (time.perf_counter() - t1) * 1000.0
                clock += a.inc_ms
                own += 1
                mv = chess.Move.from_uci(uci)
                assert mv in board.legal_moves, (uci, board.fen())
                board.push(mv)
                if clock <= 0:
                    print("FLAG: we ran out of time", flush=True)
                    break
            else:
                spend = a.share * sf_clock / 1000.0  # its seconds for this move
                nodes = max(2000, int(a.nodes * spend / a.mean_s))
                board.push(chess.Move.from_uci(sf.bestmove(board.fen(), nodes=nodes)))
                sf_clock = sf_clock - spend * 1000.0 + a.inc_ms
        out = board.outcome(claim_draw=True)
        if out is None or out.winner is None:
            res = "draw"; d += 1
        elif out.winner == we:
            res = "WIN "; w += 1
        else:
            res = "loss"; l += 1
        end_clocks.append(clock / 1000.0)
        n = w + d + l
        print(f"game {g + 1:2d} {res} as {'W' if we else 'B'} {out.termination.name if out else 'ply_cap':22s} {own:3d} own moves, clock end {clock / 1000:5.1f}s (sf {sf_clock / 1000:5.1f}s)  score {(w + d / 2) / n:.1%}  {time.perf_counter() - t0:4.0f}s", flush=True)
    sf.quit()
    n = w + d + l
    print(f"\nPROXY MATCH +{w} ={d} -{l}  score {(w + d / 2) / n:.1%}  min end clock {min(end_clocks):.1f}s median {statistics.median(end_clocks):.1f}s  {time.perf_counter() - t_all:.0f}s total")


if __name__ == "__main__":
    main()
