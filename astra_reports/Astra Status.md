# Astra Status

**Team:** Opus Carlsen · **Bot:** BINI Alpha · **Lock:** 11 September 2026, 11:00 Europe/London
**Last updated:** 10 September 2026, ~20:40 BST

Nothing has been uploaded. `bini_v8_ship/` and `submission_v8_0910_0313.zip` are untouched and remain the rollback.

## Reports

| report | covers | state |
|---|---|---|
| [Astra Report 01 — Baseline and Reproductions](Astra%20Report%2001%20-%20Baseline%20and%20Reproductions.md) | baseline manifest, environments, the four directed reproductions, patch boundaries | complete |
| [Astra Report 02 — Correctness Patches](Astra%20Report%2002%20-%20Correctness%20Patches.md) | C1 and C2 diffs, failing-before/passing-after, generalised suite, wrapper, runtime cost | complete |
| Astra Report 03 — Integration and Regression | combined manifest, timed games, pair-level statistics | **BLOCKED — host down at 260/400; fixed-node fallback running** |
| Astra Final Report — Candidate Decision | archive hash, guarantees, limitations, readiness recommendation | pending Report 03 |

## Builds

| directory | contents | archive |
|---|---|---|
| `bini_v8_ship/` | **frozen baseline, untouched** | `submission_v8_0910_0313.zip` · SHA-256 `47ace193…` · 14,042,168 B |
| `bini_astra_c2/` | V8 + C2 only (isolation) | `submission_astra_c2only.zip` · SHA-256 `92a8098b…` |
| `bini_astra_correctness/` | V8 + C2 + C1 | `submission_astra_c1c2.zip` · SHA-256 `ef41bc8d…` · 14,048,000 B |
| **`bini_astra_v2/`** | **V8 + C2 + C1 + C1b + C2b — the current candidate** | **`submission_astra_v2.zip` · SHA-256 `2c14b91fbb131dcd74f9d3fca488aacd8e3288e9a8e568017e30c834a9ac20db` · 7,106,973 B packed · 14,049,339 B unzipped · 10 files** |

Every candidate changes exactly **two** files from the frozen baseline — `bini_search.py` and
`bini_board.py`. The network, the book, `agent.py`, `bini_engine.py`, `bini_eval.py`,
`bini_nnue.py`, `bini_magics.py` and `bini_calib.py` are byte-identical in all of them.

**Patch stack, in dependency order:**

| id | what | files |
|---|---|---|
| C2 | repetition distance model; null move no longer ages the fifty-move clock | `bini_search.py`, `bini_board.py` |
| C1 | exact terminals before TT, correction and pruning, in search and quiescence | `bini_search.py` |
| C1b | terminals at the maximum-ply exits of both entry points | `bini_search.py` |
| C2b | a real threefold claim separated from the in-tree search heuristic | `bini_search.py` |

## Test assets

| path | what it is |
|---|---|
| `astra_tests/harness.py` | loads one build, drives the real search entry points |
| `astra_tests/test_repro.py` | the four directed cases, generalised |
| `astra_tests/test_suite.py` | perft, state, NNUE, search/TT regression |
| `astra_tests/test_wrapper.py` | `agent.get_move` in a cold process at the production join |
| `astra_tests/bench.py` | fixed-depth runtime cost |
| `astra_tests/arena_astra.py` | **repaired** two-arm arena (see below) |
| `astra_tests/replay_r100.py` | C4 diagnostic replay of round 100 |
| `astra_tests/patch_c1.py`, `patch_c2.py` | the patches, as anchor-asserting scripts |
| `astra_tests/package_astra.sh` | builds and validates an archive against the baseline manifest |

## Results so far

| measurement | baseline | candidate |
|---|---|---|
| directed reproductions (oracle-driven) | **7 fail** / 22 | **0 fail** / 22 |
| the same, re-run on **x86** (C1+C2 build) | **7 fail** | **0 fail** |
| C1b / C2b / eight-bucket tests | **2 fail** / 12 | **0 fail** / 12 |
| generalised suite (20 tests) | 19 / 20 | **20 / 20** |
| wrapper, cold process | 13 / 13 | **13 / 13** |
| injected failure recovery (5 scenarios) | — | **legal move + explicit telemetry in all 5** |
| cold init (budget 90 s) | 26.9 s | 24.1 s |
| speed, drift-controlled A/B/A/B | — | **about −1%** (±a few %, see Report 02) |
| timed games vs baseline | — | **blocked: host failed at 260/400** |

## Predeclared acceptance criteria for the correctness gate

**Written 10 September ~20:35 BST, before any result from the running gate was read.** The gate prints no Elo until enough colour-reversed pairs complete, so no partial reading was possible either.

The candidate is a **correctness** change, so a positive Elo is not required and will not be claimed if absent. What must hold:

1. **Non-inferiority margin: −20 Elo.** Accept if the lower bound of the 95% pentanomial interval is above −20. I am stating the margin's honesty up front: at 400 games with an ~82% draw rate the expected half-width is about ±14, and the measured speed cost of the patch is about −1 to −2 Elo, so **400 games can only rule out a regression larger than roughly 20 Elo**. A −10 margin is not testable at this sample size and I will not pretend otherwise. A second gate on a varied manifest, pooled, tightens this to roughly ±10.
2. **Zero contaminated games attributable to the candidate** — no crash, illegal move, init failure, `nnue=off` or fallback on the candidate arm.
3. **Flag rate not worse than the baseline arm.** A correctness patch that costs 1% speed must not start losing on time.
4. **Both arms NNUE-on in every scored game.**

Failing 2, 3 or 4 blocks the candidate regardless of the Elo. Failing only 1 means the evidence is insufficient, not that the patch is bad — and the response is more games, not a re-labelled conclusion.

## Instrument repairs (directive §6)

`astra_tests/arena_astra.py` replaces `tools/arena_par.py` for gating. Confirmed and fixed: `void` no longer scores as a draw; contaminated games are rejected rather than scored; **both** arms' stderr, engine mode and NNUE status are captured and checked; `still compiling` / `engine error` / `ILLEGAL candidate` / `nnue=off` contaminate a game; openings are a preselected manifest played from both colours with `--manifest-offset` to vary the manifest itself; intervals are **pentanomial over colour-reversed pairs**, not Bernoulli; every game keeps its ids, start FEN, full PGN and both stderr tails. Smoke-tested on the x86 box: 6/6 valid, 0 rejected, 0 fallbacks, 0 nnue-off.

## Closed with numbers (heuristic lane, all final at 400 games)

Astra was right that the ±34 these gates reported is wrong: it uses Bernoulli variance at an 81–83% draw rate. Recomputed with the draw-aware variance from the observed W/D/L, and **not** substituted with a guessed number — the pair ids were never retained by the old arena, so the pentanomial tightening cannot be applied and these are *upper bounds* on the true interval:

| candidate | W–D–L | draw % | score | Elo | as reported | **corrected** | verdict |
|---|---|---|---|---|---|---|---|
| `stable` (no quiet-position time discount) | 42–326–32 | 81.5% | 51.2% | **+8.7** | ±34 | **±14.6** | null |
| `mtg30` (endgame reserve, floor 30) | 37–325–38 | 81.2% | 49.9% | −0.9 | ±34 | ±14.8 | null |
| `insuf` (the rejected categorical fix) | 34–328–38 | 82.0% | 49.5% | −3.5 | ±34 | ±14.5 | null |
| `mtg24` (endgame reserve, floor 24) | 33–325–42 | 81.2% | 48.9% | −7.8 | ±34 | ±14.7 | null |
| **`book` (rebuilt with the current net)** | 24–333–43 | 83.2% | 47.6% | **−16.5** | ±34 | **±13.9** | **significantly worse** |
| `insufVweak` (vs a 40-Elo-weaker same-width opponent) | 86–292–22 | 73.0% | 58.0% | +56.1 | ±35 | ±17.3 | — |
| `v8Vweak` (baseline vs the same opponent) | 77–291–32 | 72.8% | 55.6% | +39.3 | ±34 | ±17.6 | — |
| **difference** `insufVweak − v8Vweak` | | | | **+16.8** | — | **±24.7** | null |

Two things change with the right arithmetic. The four null results are now null *tightly* — `stable`, the one I had been treating as the surviving candidate, is +8.7 with an upper bound of +23, which is not a case for shipping. And **the rebuilt book is not null at all: it is significantly worse than the shipped book**, which retrospectively validates not shipping it and is exactly the signal the too-wide interval was hiding.

Caveat I am not glossing over: these W/D/L counts came from the **old** arena, which scored `void` as a draw and did not reject contaminated games. The interval is now correct; the inputs may not be. The correctness gate uses the repaired instrument end to end.

The estimator itself was validated against Monte Carlo before use: reported SE / empirical SD = 0.95–1.02 across independent and correlated pair regimes.

## Fallback candidate

If the combined gate cannot support C1, `bini_astra_c2/` is a narrower option that is already built and validated: **wrapper 13/13, cold init 21.7 s**, reproductions 6 fail (fixing exactly the repetition boundary case), and the exhaustive enumeration shows it can only find *more* real repetitions and never invent one. It is not the recommendation; it exists so that a decision under time pressure has a validated middle option rather than an improvised one.

## Open

* **C3** — EP hashing ignores pin legality; book keys omit EP entirely. Diagnosed, unfixed, no demonstrated wrong result.
* **C4** — see Report 02. The round-100 blunder does **not** reproduce as a context effect; the finding is different from the original hypothesis and is written up there.
