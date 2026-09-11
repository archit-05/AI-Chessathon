"""SPSA tuning of the search parameters that bini_params.json can override.

    python tools/spsa.py --engine ../bini_v4 --iters 60 --games 32 --base-ms 2000 --inc-ms 20 --workers 6

Each iteration perturbs every parameter by +-c_k * delta (delta in {-1, +1}), builds two candidate
directories (symlinks to the engine's files plus their own bini_params.json), plays them against
each other on the curated openings, and steps theta along the estimated gradient. The running
theta is written to spsa_theta.json after every iteration; the final one is the candidate for a
proper 300-game gate against the unmodified engine, never shipped on the SPSA score alone.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import re
import subprocess
import sys
import time
from pathlib import Path

# name: (default, min, max, initial step c)
PARAMS = {
    "rfp": (75, 40, 140, 12),
    "nmp_base": (3, 2, 4, 1),
    "nmp_div": (4, 3, 6, 1),
    "sing_mult": (2, 1, 4, 1),
    "lmr_base": (75, 30, 120, 12),
    "lmr_mult": (444, 250, 700, 60),
    "fut_scale": (100, 60, 160, 15),
    "lmp_scale": (100, 60, 160, 15),
}


def make_candidate(engine: Path, root: Path, name: str, params: dict[str, int]) -> Path:
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    for f in engine.iterdir():
        if f.suffix == ".py" or f.name == "nnue.safetensors":
            link = d / f.name
            if not link.exists():
                link.symlink_to(f.resolve())
    (d / "bini_params.json").write_text(json.dumps(params))
    return d


def play(a: argparse.Namespace, cand: Path, base: Path, openings: Path) -> float:
    """Score of cand against base in [0, 1]."""
    cmd = [sys.executable, str(Path(a.engine).resolve() / "tools" / "arena_par.py"), "--agent", str(cand), "--opponent", str(base), "--games", str(a.games), "--base-ms", str(a.base_ms), "--inc-ms", str(a.inc_ms), "--workers", str(a.workers), "--openings", str(openings), "--seed", str(random.randint(1, 10**6))]
    out = subprocess.run(cmd, capture_output=True, text=True, env={**__import__("os").environ, "BINI_TT_BITS": "20", "BINI_JOIN_S": "85"}).stdout
    m = re.findall(r"\+(\d+) =(\d+) -(\d+)\s+score ([\d.]+)%", out)
    if not m:
        raise RuntimeError("arena produced no score:\n" + out[-2000:])
    w, d, l, _ = m[-1]
    n = int(w) + int(d) + int(l)
    return (int(w) + int(d) / 2) / n


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", required=True)
    ap.add_argument("--iters", type=int, default=60)
    ap.add_argument("--games", type=int, default=32)
    ap.add_argument("--base-ms", type=int, default=2000)
    ap.add_argument("--inc-ms", type=int, default=20)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--a", type=float, default=0.6, help="step size relative to the parameter's c")
    ap.add_argument("--out", default="spsa_theta.json")
    ap.add_argument("--resume")
    ap.add_argument("--work", default="../spsa_work")
    a = ap.parse_args()
    engine = Path(a.engine).resolve()
    openings = engine / "tools" / "curated.epd"
    work = Path(a.work).resolve()
    theta = {k: float(v[0]) for k, v in PARAMS.items()}
    if a.resume:
        theta.update(json.load(open(a.resume)))
    rng = random.Random(7)
    t0 = time.perf_counter()
    for k in range(a.iters):
        ck = {n: PARAMS[n][3] / (k + 1) ** 0.101 for n in PARAMS}
        ak = {n: a.a * PARAMS[n][3] / (k + 1) ** 0.602 for n in PARAMS}
        delta = {n: rng.choice((-1, 1)) for n in PARAMS}
        plus = {n: int(round(min(PARAMS[n][2], max(PARAMS[n][1], theta[n] + ck[n] * delta[n])))) for n in PARAMS}
        minus = {n: int(round(min(PARAMS[n][2], max(PARAMS[n][1], theta[n] - ck[n] * delta[n])))) for n in PARAMS}
        cp = make_candidate(engine, work, f"plus_{k}", plus)
        cm = make_candidate(engine, work, f"minus_{k}", minus)
        score = play(a, cp, cm, openings)
        g = score - 0.5  # positive: plus is better
        # step proportional to the perturbation size: a full-score edge (g = 0.5) moves each
        # parameter by a * c_k in the winning direction, decaying with the iteration count
        for n in PARAMS:
            theta[n] = min(PARAMS[n][2], max(PARAMS[n][1], theta[n] + 2.0 * g * delta[n] * ak[n] / (a.a * PARAMS[n][3]) * (a.a * ck[n])))
        Path(a.out).write_text(json.dumps({n: int(round(v)) for n, v in theta.items()}, indent=1))
        print(f"iter {k + 1}/{a.iters} plus-vs-minus {score:.3f}  theta {json.dumps({n: int(round(v)) for n, v in theta.items()})}  {time.perf_counter() - t0:.0f}s", flush=True)
    print("done:", Path(a.out).read_text())


if __name__ == "__main__":
    sys.setrecursionlimit(10000)
    main()
