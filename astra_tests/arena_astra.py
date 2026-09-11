"""Repaired two-arm arena.

Fixes every defect Astra listed in the old tools/arena_par.py:
  * `void` is no longer scored as a draw; contaminated games are rejected, not silently scored;
  * BOTH arms' stderr, engine mode and NNUE status are captured and checked, not just ours;
  * "still compiling" / "engine error" / "ILLEGAL candidate" / nnue=off contaminate a game;
  * openings are a preselected manifest played from BOTH colours, and --manifest-offset varies
    the manifest itself rather than only the scheduling order;
  * intervals are pentanomial over colour-reversed pairs, so repeated starts stay clustered
    instead of being treated as independent Bernoulli trials;
  * every game keeps its ids, start FEN, full PGN and both stderr tails.

Nothing here edits the official harness; the referee is imported unchanged.
"""
from __future__ import annotations

import argparse, hashlib, json, math, os, random, statistics, sys, time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import chess

STARTER = Path(__file__).resolve().parents[1] / "aichessathon-starter"
sys.path.insert(0, str(STARTER))
from harness.referee import play_match          # noqa: E402
from harness.sandbox import local               # noqa: E402

CONTAMINATING_TERMS = frozenset({"crash", "illegal", "init", "both_failed"})
BAD_STDERR = ("still compiling", "engine error", "ILLEGAL candidate", "book ignored")


def build_hashes(d: Path) -> dict:
    out = {}
    for f in sorted(Path(d).iterdir()):
        if f.suffix in (".py", ".json", ".safetensors"):
            out[f.name] = hashlib.md5(f.read_bytes()).hexdigest()
    return out


def scan(err: str) -> dict:
    """What the arm actually did, from its own stderr."""
    return dict(
        nnue_on="nnue=on" in err,
        ready="ready:" in err,
        still_compiling="still compiling" in err,
        engine_error="engine error" in err,
        illegal_candidate="ILLEGAL candidate" in err,
        book_moves=err.count(" book "),
        searched_moves=sum(1 for ln in err.splitlines() if " d" in ln and "cp " in ln),
    )


def one_game(job):
    gid, pair_id, opening_id, fen, a_dir, b_dir, base_ms, inc_ms, a_white = job
    white, black = (a_dir, b_dir) if a_white else (b_dir, a_dir)
    w, b = local(Path(white)), local(Path(black))
    t0 = time.time()
    outcome = play_match(w, b, base_ms, inc_ms, start_fen=fen)
    wall = time.time() - t0
    a_err, b_err = (w.stderr_tail, b.stderr_tail) if a_white else (b.stderr_tail, w.stderr_tail)
    wn, bn = Path(white).name, Path(black).name
    pgn = outcome.pgn.replace("[Result ", f'[White "{wn}"]\n[Black "{bn}"]\n[GameId "{gid}"]\n'
                              f'[PairId "{pair_id}"]\n[OpeningId "{opening_id}"]\n[Result ', 1)
    return dict(game_id=gid, pair_id=pair_id, opening_id=opening_id, start_fen=fen,
                a_white=a_white, result=outcome.result, termination=outcome.termination,
                pgn=pgn, wall_s=round(wall, 1),
                a=scan(a_err), b=scan(b_err),
                a_stderr=a_err[-2500:], b_stderr=b_err[-2500:])


def classify(g):
    """(valid, reason). A game only scores if both arms ran the real engine cleanly."""
    if g["result"] == "void":
        return False, "void"
    if g["termination"] in CONTAMINATING_TERMS:
        return False, f"termination:{g['termination']}"
    for arm in ("a", "b"):
        s = g[arm]
        if not s["nnue_on"]:
            return False, f"{arm}:nnue_off"
        if s["still_compiling"]:
            return False, f"{arm}:still_compiling"
        if s["engine_error"]:
            return False, f"{arm}:engine_error"
        if s["illegal_candidate"]:
            return False, f"{arm}:illegal_candidate"
    return True, ""


def a_score(g):
    if g["result"] == "draw":
        return 0.5
    return 1.0 if (g["result"] == "white") == g["a_white"] else 0.0


def elo_of(score):
    score = min(max(score, 1e-9), 1 - 1e-9)
    return -400 * math.log10(1 / score - 1)


def pentanomial(games):
    """Score and interval, clustered correctly.

    A colour-reversed pair is the unit of pairing, but an OPENING may appear in more than one
    pair (a manifest offset can overlap, or a manifest can repeat a line).  Two pairs from the
    same opening are not independent, so the headline standard error is clustered by opening,
    not by pair.  Both are reported; when every opening is unique they coincide.
    """
    by_pair, pair_open = {}, {}
    for g in games:
        by_pair.setdefault(g["pair_id"], []).append(g)
        pair_open[g["pair_id"]] = g.get("opening_id", g["pair_id"])
    pair_scores, pair_of_opening = [], {}
    singles = []
    for pid, v in by_pair.items():
        if len(v) == 2:
            sc = sum(a_score(x) for x in v)
            pair_scores.append(sc)
            pair_of_opening.setdefault(pair_open[pid], []).append(sc)
        else:
            singles.extend(a_score(x) for x in v)
    n_pairs = len(pair_scores)
    if n_pairs < 2:
        return None
    mu_pair = statistics.fmean(pair_scores)
    var_pair = statistics.variance(pair_scores)
    se_pair = math.sqrt(var_pair / n_pairs)

    # cluster by opening: the cluster value is the MEAN pair score for that opening, weighted
    # by how many pairs it contributed
    clusters = [statistics.fmean(v) for v in pair_of_opening.values()]
    n_clu = len(clusters)
    if n_clu >= 2:
        se_clu = math.sqrt(statistics.variance(clusters) / n_clu)
    else:
        se_clu = se_pair
    repeated = sum(1 for v in pair_of_opening.values() if len(v) > 1)

    score = mu_pair / 2.0
    se = max(se_pair, se_clu) / 2.0      # never quote the tighter of the two
    if singles:
        n1 = len(singles)
        v1 = statistics.pvariance(singles) if n1 > 1 else 0.25
        tot = n_pairs * 2 + n1
        score = (mu_pair * n_pairs + sum(singles)) / tot
        se = math.sqrt((max(var_pair, statistics.variance(clusters) * n_clu / max(1, n_pairs)
                            if n_clu >= 2 else var_pair) * n_pairs + v1 * n1) / tot ** 2)
    lo, hi = max(1e-9, score - 1.96 * se), min(1 - 1e-9, score + 1.96 * se)
    counts = {k: pair_scores.count(k) for k in (0.0, 0.5, 1.0, 1.5, 2.0)}
    return dict(score=score, se=se, elo=elo_of(score),
                elo_lo=elo_of(lo), elo_hi=elo_of(hi),
                elo_pm=(elo_of(hi) - elo_of(lo)) / 2,
                pairs=n_pairs, unpaired=len(singles), pentanomial=counts,
                openings=n_clu, repeated_openings=repeated,
                se_by_pair=se_pair / 2.0, se_by_opening=se_clu / 2.0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", required=True, help="candidate build directory")
    ap.add_argument("--b", required=True, help="reference build directory")
    ap.add_argument("--games", type=int, default=400)
    ap.add_argument("--base-ms", type=int, default=120000)
    ap.add_argument("--inc-ms", type=int, default=500)
    ap.add_argument("--workers", type=int, default=28)
    ap.add_argument("--openings", required=True)
    ap.add_argument("--manifest-offset", type=int, default=0,
                    help="first opening to use; varies the manifest, not just the order")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", required=True, help="prefix for .json / .pgn artefacts")
    ap.add_argument("--resume", action="store_true",
                    help="continue from <out>.partial.json instead of replaying finished games")
    a = ap.parse_args()

    fens = [ln.split(";")[0].strip() for ln in Path(a.openings).read_text().splitlines() if ln.strip()]
    n_pairs = a.games // 2
    if n_pairs > len(fens):
        raise SystemExit(f"manifest has {len(fens)} openings, {n_pairs} pairs requested")
    chosen = [fens[(a.manifest_offset + i) % len(fens)] for i in range(n_pairs)]
    manifest_hash = hashlib.md5("\n".join(chosen).encode()).hexdigest()

    A, Bd = str(Path(a.a).resolve()), str(Path(a.b).resolve())
    jobs = []
    for i, fen in enumerate(chosen):
        jobs.append((2 * i, i, (a.manifest_offset + i) % len(fens), fen, A, Bd, a.base_ms, a.inc_ms, True))
        jobs.append((2 * i + 1, i, (a.manifest_offset + i) % len(fens), fen, A, Bd, a.base_ms, a.inc_ms, False))
    random.Random(a.seed).shuffle(jobs)

    config = dict(a=A, b=Bd, games=a.games, base_ms=a.base_ms, inc_ms=a.inc_ms,
                  workers=a.workers, seed=a.seed, openings=str(Path(a.openings).resolve()),
                  manifest_offset=a.manifest_offset, unique_openings=len(set(chosen)),
                  manifest_md5=manifest_hash, host=os.uname().nodename,
                  cpus=os.cpu_count(), started=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                  a_hashes=build_hashes(Path(A)), b_hashes=build_hashes(Path(Bd)),
                  env={k: v for k, v in os.environ.items() if k.startswith("BINI_")})
    print(json.dumps({k: v for k, v in config.items() if k not in ("a_hashes", "b_hashes")}), flush=True)

    games, done = [], 0
    resume = Path(a.out + ".partial.json")
    if a.resume and resume.exists():
        prev = json.loads(resume.read_text())
        games = prev["games"]
        done = len(games)
        seen = {g["game_id"] for g in games}
        jobs = [j for j in jobs if j[0] not in seen]
        print(f"resuming: {done} games already recorded, {len(jobs)} still to play", flush=True)
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        for f in as_completed([ex.submit(one_game, j) for j in jobs]):
            g = f.result()
            ok, why = classify(g)
            g["valid"], g["reject_reason"] = ok, why
            games.append(g)
            done += 1
            if done % 10 == 0 or not ok:
                # checkpoint every ten games: a host that disappears mid-gate must not cost
                # the whole sample, which is exactly what happened on 10 September
                Path(a.out + ".partial.json").write_text(json.dumps(
                    dict(config=config, completed=done, requested=a.games, games=games), indent=1))
                valid = [x for x in games if x["valid"]]
                st = pentanomial(valid)
                tag = "" if ok else f"  REJECTED({why})"
                if st:
                    print(f"[{done}/{a.games}] valid {len(valid)}  score {st['score']:.1%}  "
                          f"elo {st['elo']:+.0f} ±{st['elo_pm']:.0f}  pairs {st['pairs']}{tag}", flush=True)
                else:
                    print(f"[{done}/{a.games}] valid {len(valid)}{tag}", flush=True)

    valid = [g for g in games if g["valid"]]
    st = pentanomial(valid)
    w = sum(1 for g in valid if a_score(g) == 1)
    d = sum(1 for g in valid if a_score(g) == 0.5)
    l = sum(1 for g in valid if a_score(g) == 0)
    terms, rejects = {}, {}
    for g in games:
        terms[g["termination"]] = terms.get(g["termination"], 0) + 1
        if not g["valid"]:
            rejects[g["reject_reason"]] = rejects.get(g["reject_reason"], 0) + 1
    summary = dict(config=config, requested=a.games, completed=len(games), valid=len(valid),
                   rejected=len(games) - len(valid), reject_reasons=rejects,
                   W=w, D=d, L=l, terminations=terms, stats=st,
                   flags=terms.get("flag", 0),
                   a_fallback=sum(1 for g in games if g["a"]["still_compiling"]),
                   b_fallback=sum(1 for g in games if g["b"]["still_compiling"]),
                   a_nnue_off=sum(1 for g in games if not g["a"]["nnue_on"]),
                   b_nnue_off=sum(1 for g in games if not g["b"]["nnue_on"]),
                   finished=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    Path(a.out + ".json").write_text(json.dumps(dict(summary=summary, games=games), indent=1))
    Path(a.out + ".pgn").write_text("\n\n".join(g["pgn"] for g in games) + "\n")
    print("\n=== FINAL ===")
    print(json.dumps(summary, indent=1, default=str))


if __name__ == "__main__":
    main()
