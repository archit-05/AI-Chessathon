# Astra Report 03 — Integration and Regression

**Candidate:** `bini_astra_correctness/` = frozen V8 + C2 + C1
**Archive:** `submission_astra_c1c2.zip` — SHA-256 `ef41bc8d1f3bb7e587b0ffa888afa4a3333d2c7d936a1bdde5490c2b1f902617`, 7,106,550 B packed, **14,048,000 B unzipped, 10 files**
**Written:** 10 September 2026 · **nothing has been uploaded**

---

## 1. Combined manifest — the tested build *is* the packaged build

The archive was built from `bini_astra_correctness/` and every one of its ten members was hashed against both the frozen baseline archive and the copy of the build the gate is playing on the x86 box. All three agree:

| file | md5 | vs frozen V8 |
|---|---|---|
| `agent.py` | `5bff736371872bc5688fd59d0c1cc74c` | same |
| `bini_board.py` | `39304f6ae518e221a8df45d27f195e8e` | **changed (C2)** |
| `bini_calib.py` | `18210c5b3f8d7109151da461ee3b74f8` | same |
| `bini_engine.py` | `4f4de482c28eca01e47cff5d6380a2c2` | same |
| `bini_eval.py` | `d44763ba4ad0465a9257bfb32cd9c990` | same |
| `bini_magics.py` | `3c2ab7807a87e0f31fb4d889367870e2` | same |
| `bini_nnue.py` | `e06453c8a7a9a34b1e9405b309b071c2` | same |
| `bini_search.py` | `9e409ed2ec715cd0ffd141e1ceb2372d` | **changed (C1+C2)** |
| `book.json` | `51c97f3f4e8ab4c1801543945d749906` | same |
| `nnue.safetensors` | `182c8fc8fb60b96fdb51f231cbe9c0e9` | same |

Two files changed. The network and the book are byte-identical to the incumbent, so nothing in this candidate depends on the net or book work that measured null or negative.

## 2. x86 deployment validation, kept separate from Mac

All correctness work above was done on macOS 26 / arm64, Python 3.13.2. The deployment target is x86. Both suites were re-run on the box — **AMD EPYC 9J14, Linux 5.15, Python 3.12.3, numpy 2.5.2, numba 0.67.0, llvmlite 0.49.0, python-chess 1.11.2** — and reproduce the Mac results exactly:

| | Mac baseline | Mac candidate | **x86 baseline** | **x86 candidate** |
|---|---|---|---|---|
| directed reproductions | 7 fail / 21 | **0 fail** | 7 fail / 21 | **0 fail** |
| generalised suite (20 tests) | 19 / 20 | **20 / 20** | 19 / 20 | **20 / 20** |
| C3 position identity | 2 pass, 1 fail (book key), 1 info | same | same | same |

The single generalised-suite failure on both architectures is `T1.terminal_beats_poisoned_tt`, on the baseline, on the dead-material classes. The suite covers perft against python-chess (10 positions plus 623 from seeded random games), make/unmake and Zobrist invariants over ~26,000 moves, illegal-move state integrity, nested null make/unmake, NNUE incremental-versus-refresh over 26,492 moves across every move class and buckets 5–7, accumulator range, colour-mirror symmetry, search state restoration, terminal recognition under a poisoned table, mate normalisation, 4,000 TT round trips, excluded-move search, reduced-feature agreement, **mid-tree abort state restoration**, **depth-preferred TT replacement with a colliding key**, and **aspiration null windows failing on the correct side**. The last three were added after the first pass and pass on both builds — they are regression cover, not patch evidence.

## 3. Reliability under injected failure (directive §5)

Run in cold processes at the production join, with the candidate build:

| scenario | result |
|---|---|
| network file **missing** | builds, prints `nnue=off`, plays through the handcrafted evaluation, **4/4 legal moves**, stdout clean |
| network file **truncated** (400 KB of 12 MB) | fails fast in 0.5 s with `BUILD FAILED: ValueError('cannot reshape array of size 199680 into shape (6144,1024)')` on stderr, engine absent, fallback returns **4/4 legal moves** |
| engine raises on every attribute | `engine error: RuntimeError('injected engine failure')` on stderr, legal move returned, stdout clean |
| engine returns an illegal candidate (`a1a8`) | `ILLEGAL candidate a1a8` on stderr, legal move returned, stdout clean |
| forced fallback (`BINI_FORCE_FALLBACK=1`) | legal moves throughout |

Every degradation is explicit on stderr and none of them writes to stdout. This matters beyond reliability: the repaired arena **rejects** any game where either arm printed `nnue=off`, `still compiling`, `engine error` or `ILLEGAL candidate`, so these are exactly the signals it keys on.

## 3b. Instrument repair: repeated openings are now clustered

Astra's point that pair/cluster covariance must be *measured* rather than asserted had a second
half I had not implemented: an **opening** can appear in more than one pair. A manifest offset
overlaps, or a manifest repeats a line, and two pairs drawn from the same opening are not
independent observations.

`arena_astra.pentanomial()` now reports a standard error clustered **by opening** as well as by
pair, and quotes the wider of the two. Validated against Monte Carlo before use, 300 replications
each:

| design | empirical SD of the estimate | SE by pair | SE by opening |
|---|---|---|---|
| 200 unique openings, 1 pair each | 0.01798 | 0.01828 | 0.01828 |
| **50 openings, 4 pairs each** | **0.03248** | **0.01812** *(understates 1.8×)* | **0.03102** |

With unique openings the two coincide, so nothing is lost. With repeats the by-pair figure
**understates the true spread by 1.8×** and the opening-clustered figure is right. The gate
artefacts now carry `openings`, `repeated_openings`, `se_by_pair` and `se_by_opening` so the
reader can see which regime a given run was in.

The arena also now checkpoints every ten games to `<out>.partial.json` and accepts `--resume`,
after a host failure cost 260 completed games (§5).

## 4. How much do these defects actually get to fire?

Terminations across **2,800 completed gate games** (the five V8.5 lanes plus the two weak-opponent lanes):

| termination | games | share |
|---|---|---|
| **threefold repetition** | 1,390 | **49.6%** |
| checkmate | 580 | 20.7% |
| **fifty-move rule** | 435 | **15.5%** |
| **insufficient material** | 382 | **13.6%** |
| stalemate | 12 | 0.43% |
| ply cap | 1 | 0.04% |

Half of all games end by repetition; one in six reaches the fifty-move boundary; one in seven ends in dead material. These are the three predicates C1 and C2 touch. That is exposure at the *end* of games — positions inside the search hit all three far more often.

**How much does C2 change?** Both index algorithms were transcribed exactly and run over every plausible `(ply, halfmove clock, history length, true match distance)` configuration — **576,852** of them:

* they agree on **98.5%**;
* the baseline **misses a real repetition the fix finds** in 1.5% overall — **2.8%** of configurations whose match lies in pre-root game history, **0%** of matches inside the search tree;
* the baseline claims a repetition the fix does not in **zero** configurations.

That last line is the safety argument. **C2 cannot invent a draw.** It is strictly one-directional: the engine sees more real repetitions than before, never fewer and never spurious ones. Combined with the 49.6% exposure, this is the most consequential of the two patches even though it is the smaller diff.

## 5. Timed regression games

Two gates, both candidate versus the frozen baseline through the real wrapper at **120 s + 0.5 s**, on the x86 box, 32 workers, `BINI_JOIN_S=300` (a contended-box relaxation recorded in each artefact and kept out of the cold-init measurement in §3).

* **Primary** — `curated.epd` offset 0, 200 unique openings played from both colours, manifest md5 `c3ec09087ed34140fdee3b71de114a74`, seed 20260910.
* **Confirmation** — offset 88, seed 88088, chained to start automatically when the primary finishes. Openings 88–287: **88 of the 200 are ones the primary never used**, the other 112 are replayed with fresh scheduling and fresh game outcomes. The manifest has only 288 entries, so a fully disjoint 400-game confirmation is not available; the overlap is stated rather than glossed.

Predeclared acceptance criteria were written into `Astra Status.md` **before any result was read**, and the arena deliberately prints no Elo until enough colour-reversed pairs complete, so no partial reading was possible.

### The primary gate was lost to a host failure

At **260 of 400 games** the Vast.ai box became unreachable — ICMP silent, `ssh` refused on both the direct and the proxy route. It was not a network blip: the instance stopped. There is no `vastai` CLI or API key on the workstation, so it can only be restarted from the Vast console, which is the owner's action.

**The 260 games are gone.** My arena wrote its results file only after the last game, so nothing but the progress lines survived, and those live on the box. That is a defect in my instrument, not bad luck, and I have fixed it: `arena_astra.py` now writes `<out>.partial.json` every ten games and accepts `--resume` to continue from it. Had that been there from the start, this would have cost twenty minutes rather than the whole sample.

**I am not quoting the interrupted gate.** It was a partial gate, and reading partials is the specific error I have made repeatedly on this project. The last progress line is recorded here as an artefact of the interruption, not as a result: `[260/400] valid 260, 0 rejected`. Nothing should be inferred from it.

### Fallback while the host is down: a fixed-node screen

Run on the workstation, which cannot host a 120+0.5 gate (8 cores / 8 GB: 400 games would take over thirteen hours). `astra_tests/node_gate_ab.py` — the persistent-engine runner, extended with `--engine-a` / `--engine-b` so it can compare two *code* builds rather than one build under two environments.

**What this screen is worth, stated before its result:** fixed nodes per move make it deterministic and contention-immune, and they remove the patch's ~1% speed cost from the comparison, so it measures the *quality* effect alone. Against that, it runs **with the book off** and at **100,000 nodes per move** against the platform's roughly 1.4 million — several plies shallower. My own recorded methodology note is that fixed-node screens overstate evaluation gains by two to three times. **It is a screen for gross regression. It is not a substitute for the timed gate and will not be presented as one.**

**FIXED-NODE SCREEN PENDING**

### Still required

A completed 400-game gate at 120 s + 0.5 s through the real wrapper, plus its confirmation run on the varied manifest, both of which need the box back.

## 6. Unresolved risks

* **The gate can only rule out a regression larger than roughly 20 Elo** at 400 games with an ~82% draw rate. A second gate on a varied manifest is chained behind the first; pooled, that reaches roughly ±10. Anything smaller than that is beyond what the remaining time can measure, and I will say so rather than call it non-inferior.
* **C4 is open.** Its original hypothesis is refuted (Report 02); the adversarial-history matrix that would actually settle transposition-table context safety has not been built. No failing test currently points at it.
* **The book key aliases on en passant** (demonstrated). Unfixed by choice — see `Astra Note - Book Pipeline Audit.md`.
* **The engine's second-occurrence rule is a search heuristic, not the FIDE claim rule.** Unchanged from the baseline, but C2 makes it fire in cases it previously missed, which is a behavioural change even though it is a correctness fix.
* **A ~1% speed cost is real** and was measured, not assumed. At an 82% draw rate no 400-game gate can resolve 1–2 Elo either way.
