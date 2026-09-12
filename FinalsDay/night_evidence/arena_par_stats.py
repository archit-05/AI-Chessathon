"""Parallel arena on top of the starter harness (never edits harness/).

    python tools/arena_par.py --agent ../bini --opponent ../aichessathon-starter/baselines/minimax \
        --games 200 --base-ms 10000 --inc-ms 100 --workers 6 --openings tools/openings.epd

Alternates colours per opening, runs games in a process pool, prints W/D/L, score, Elo with a
95% interval, and every failure termination. Exits non-zero if any game ended by crash,
illegal, flag or init on the agent's side.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import chess

STARTER = Path(__file__).resolve().parents[2] / "aichessathon-starter"
sys.path.insert(0, str(STARTER))

from harness.referee import play_match  # noqa: E402
from harness.sandbox import local  # noqa: E402


def one_game(args: tuple[str, str, int, int, str, bool]) -> tuple[bool, str, str, str, str]:
    agent, opponent, base_ms, inc_ms, fen, agent_white = args
    white, black = (agent, opponent) if agent_white else (opponent, agent)
    w, b = local(Path(white)), local(Path(black))
    outcome = play_match(w, b, base_ms, inc_ms, start_fen=fen)
    ours = w if agent_white else b
    # name the players so tools/cpl.py can attribute moves
    wn, bn = (Path(white).name, Path(black).name)
    pgn = outcome.pgn.replace('[Result ', f'[White "{wn}"]\n[Black "{bn}"]\n[Result ', 1)
    return agent_white, outcome.result, outcome.termination, pgn, ours.stderr_tail, fen


def elo(score: float, n: int) -> tuple[float, float]:
    score = min(max(score, 1e-6), 1 - 1e-6)
    e = -400 * math.log10(1 / score - 1)
    # normal approximation of the interval on the score, mapped through the logistic
    se = math.sqrt(score * (1 - score) / n)
    lo = min(max(score - 1.96 * se, 1e-6), 1 - 1e-6)
    hi = min(max(score + 1.96 * se, 1e-6), 1 - 1e-6)
    return e, (-400 * math.log10(1 / hi - 1) - -400 * math.log10(1 / lo - 1)) / 2


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", required=True)
    ap.add_argument("--opponent", required=True)
    ap.add_argument("--games", type=int, default=100)
    ap.add_argument("--base-ms", type=int, default=10000)
    ap.add_argument("--inc-ms", type=int, default=100)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--openings", default=str(Path(__file__).with_name("openings.epd")))
    ap.add_argument("--pgn-out")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--stats-out", help="JSONL: one record per game with our stderr tail")
    a = ap.parse_args()

    fens = [chess.STARTING_FEN]
    p = Path(a.openings)
    if p.exists():
        fens = [line.split(";")[0].strip() for line in p.read_text().splitlines() if line.strip()]
    rng = random.Random(a.seed)
    jobs = []
    for g in range(a.games):
        fen = fens[(g // 2) % len(fens)] if len(fens) > 1 else fens[0]
        jobs.append((str(Path(a.agent).resolve()), str(Path(a.opponent).resolve()), a.base_ms, a.inc_ms, fen, g % 2 == 0))
    rng.shuffle(jobs)

    w = d = l = 0
    terms: dict[str, int] = {}
    failures = 0
    pgns = []
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        futs = [ex.submit(one_game, j) for j in jobs]
        done = 0
        for f in as_completed(futs):
            agent_white, result, term, pgn, err, fen = f.result()
            done += 1
            if a.stats_out:
                with open(a.stats_out, 'a') as sf:
                    sf.write(json.dumps(dict(i=done, agent_white=agent_white, fen=fen, result=result, term=term, stderr=err)) + '\n')
            terms[term] = terms.get(term, 0) + 1
            if "still compiling" in err:
                print("NOTE: agent ran on the fallback (compile exceeded the join timeout)", flush=True)
            if "engine error" in err or "ILLEGAL" in err:
                print("AGENT STDERR:\n" + err[-1500:], flush=True)
            if result in ("draw", "void"):
                d += 1
            elif (result == "white") == agent_white:
                w += 1
            else:
                l += 1
                if term in ("crash", "illegal", "flag", "init"):
                    failures += 1
                    print(f"AGENT FAILURE: {term}\n{pgn[:400]}\nstderr tail:\n{err[-1200:]}", flush=True)
            if result == "draw":
                print(f"DRAW ({term}) stderr tail:\n{err[-600:]}", flush=True)
            if term in ("crash", "illegal", "flag", "init") and ((result == "white") == agent_white):
                pass  # opponent failed
            pgns.append(pgn)
            n = w + d + l
            score = (w + d / 2) / n
            e, pm = elo(score, n)
            print(f"[{done}/{a.games}] +{w} ={d} -{l}  score {score:.1%}  elo {e:+.0f} ±{pm:.0f}  last: {result} by {term}", flush=True)
    if a.pgn_out:
        Path(a.pgn_out).write_text("\n\n".join(pgns) + "\n")
    print("terminations: " + ", ".join(f"{k} {v}" for k, v in sorted(terms.items())))
    if failures:
        raise SystemExit(f"agent failed {failures} game(s)")


if __name__ == "__main__":
    main()
