# Project Prometheus — the plan for a 2700+ engine, rewritten from a clean slate

Rewritten Tuesday 8 September 2026, 21:45 London, after reading every plan and log of the week
(PLAN.md, PLAN_V22_LEAP.md, PLAN_V3*.md, PLAN_V4.md, V4 Progress.md, V5 Plan.md s0–14, the first
Prometheus draft), the engine in `bini_v5/`, the trainer, the generators, the intel corpus, the
platform logs of rounds 64–69, and the state of the three boxes at 21:20. The first draft is kept
as `Project Prometheus v1 (Tue 2115).md`. Uploads lock Friday 11 September 11:00; the 13-round
Swiss on locked builds is Friday afternoon; the London knockout is Saturday.

The ask: **a 2700/2800+ engine on this ladder's scale that comfortably beats the top five and has
a real shot at first.** This document says, in order, where we are, what went wrong this week and
what it cost, what went right and must not be touched, why the plan below is different in kind
from V4 and V5 rather than in degree, the exact list of experiments and their kill rules, the
hour-by-hour schedule to Friday, and honest odds.

---

## 0. The verdict in one screen

| | |
|---|---|
| **Where we are** | BINI Alpha 2346, rank 16 (25-11-10). Move loss 16.1 cp per move over all games, 13.7 since R50. Zero failures in 50 rated games. Platform speed 700–730k nodes/s, depth 15–19 in 2 s, compile 25–28 s. |
| **The top five tonight** | PSL God Matt Bomer 2811*, Patzer 2.1 2678*, AlphaFish 2648, SoberPaschoud 2614*, ms 2613 (* provisional). Their move loss: 7.7–11.6 cp. Blunders 0.1–0.6%. Nobody at the top blunders; 61 of their 82 losses are evaluation slides. |
| **What the gap is** | Entirely the evaluation network. The search, speed, clock and robustness are already at the level of the top five (section 4). The net reads closed middlegames 100–250 cp too optimistically and endgames 165–215 cp wrong (measured). |
| **Why the week did not close it** | We ran eleven training experiments and zero controls; steered on 40-game gates (±12 points) for four days; mixed four label scales and called it a dataset; tried to move a 155M-row net with 1–9M rows; trained on an 8 GB laptop; pursued six levers with capacity for one. Section 2. |
| **The plan** | One lever, executed to completion: **a net trained from scratch on hundreds of millions of consistently labelled positions**, on the A100, judged by **fixed-node games** that give a ±5-point verdict in 15 minutes. Refined at 22:20 (section 4.1): **three independent routes to that net run in parallel from tonight**, not as fallbacks: bullet (the trainer behind nearly every 3000+ open-source NNUE) on the public Stockfish binpacks; our trainer on our own Stockfish-19 labels produced at depth 5–7 (4× the volume of depth 9: 300–500M in-distribution positions by Wednesday noon); a timeboxed Leela batch labeller on the A100 for a variant net. Net capacity goes to 1024 SCReLU with 8 output buckets once the data is there. The engine is frozen for V5.0; Thursday gets one search retune at fixed nodes on top of the new net. Everything already built and gated (draw policy, SEE pruning, clock, book) rides along. |
| **Two builds** | V5.0 Wednesday evening (the best gated net, or v3b if none clears, plus the gated extras). V5.1 Thursday by 15:00 only if it beats V5.0 by ≥ +30 with the interval clear of zero. Friday is rollback only. |
| **Honest odds** | After the 22:20 refinement: a net ≥ +100 at fixed nodes by Wednesday 13:00: 0.8 (three routes at 0.5–0.6 each, correlated only through the shared exporter and judge). 2700+ by Friday: 0.45 after the 23:00 bottleneck pass (section 4.3). Top-five seed: 0.7. First: about 0.2. Floor if nothing lands: 2380–2450. What holds it below "very likely": the ceiling of a single-layer net inside a 700k nodes/s numba search is about 2750–2850 on this scale, there are 40 hours and two hand-overs, and the search has never been tuned. Section 11. |

---

## 1. The goal, in numbers that can be measured

| Yardstick | Today | Top five | 2700 target |
|---|---|---|---|
| Ladder rating | 2346 | 2613–2811 | 2700+ |
| Move loss per move (site grader: Stockfish 16 depth 16) | 16.1 (13.7 since R50) | 7.7–11.6 | ≤ 8 |
| Blunder rate (moves losing ≥ 200 cp) | 0.8% (0.3% since R50) | 0.1–0.6% | ≤ 0.2% |
| Games lost by an evaluation slide over quiet moves | 6 of the last 21 | their main loss mode too | 0: hold or draw them |
| Score vs the 2300–2500 band | 60–70% | 80–90% | ≥ 85% |
| Score vs the top five | 0-1-3 (rated) | 40–68% among themselves | ≥ 50% |
| Real-clock proxy vs Stockfish at 20k nodes | 46% | – | ≥ 60% |
| Failures (flag, illegal, crash, init) | 0 in 50 | 30 across the field's cache | 0 |

The Swiss rewards not losing downward; the knockout replays each position with both colours and
breaks ties on the Swiss standing. "Comfortably beats the top five" therefore means: never loses to
the band below, draws the top five as Black and beats them as White more often than not. That is
a move-quality target (≤ 8 cp, no slides), a draw-discipline target (take the repetition they
offer when we are worse; never allow one when we are better) and a robustness target (zero
failures), in that order.

---

## 2. Brutal critique: what went wrong, why, and what it cost

1. **Eleven experiments, zero controls.** v4a, v4b, v4b2, v4o, v4o2, v4o3, run A, run D, run E,
   the refit and the calibration all ran before the one control that decides whether any of them
   means anything: *the current trainer, from scratch, on v3's own data, must reproduce v3.* It has
   still never run. D3 (Tuesday 21:05) only shows the trainer can *fine-tune*; every from-scratch
   verdict of the week (v4a, v4b, run A) is uninterpretable, because a from-scratch failure could be
   the data or the trainer and we cannot tell. Cost: three days of GPU time and the premise of
   both V4 and V5.
2. **Four days of steering on 40-game gates.** A 40-game gate resolves ±12 points. We discovered
   this at 20:10 tonight when two bit-identical engines scored 40% and 49%. Every decision before
   that was made on noise: the search batch (continuation history "−11", SEE "+28"), run D
   "37.5%", run A "31%", the afternoon's pilots, the epoch checkpoints. The correction-history
   bug (−132) was the only real signal, and it was real because it was huge. Cost: the search
   items were dropped or kept by coin flip; nets were killed after one epoch on noise.
3. **Four label scales glued with one constant.** Lichess (Stockfish 11 to 16, depths 12 to 60,
   classical and NNUE scales), Stockfish 16 depth 16 normalised (the site), Stockfish 19 depth 9
   (self-play), Stockfish 19 depth 10 (elite), reconciled by a global ×0.85 and, on the self-play,
   a result blend over 70% draws. Every net that saw the mix was level or worse. The best net we
   own (v3, then v3b) is the most single-sourced one. The lesson was written down on Sunday and
   the mix was still the training set on Tuesday. Cost: all of V4 and the N lever of V5.
4. **Trying to move a 155M-row net with 1–9M rows.** Site ×4, elite ×10, hard ×10, endgames ×2:
   oversampling small sets into a 155M-row net either does nothing (level fine-tunes) or overfits
   the small set (the "flattening"). The closed-structure error the losses come from can only move
   with tens of millions of consistently labelled positions from those structures. We never had
   them and kept trying to substitute weight for volume. Cost: the whole net programme.
5. **Fine-tuning as a strategy for a generational leap.** A gentle fine-tune cannot change what
   the feature layer represents; it is structurally capped at +0 to +40. Six of them were run
   (v4o2, D, D3, E, refit, calibration) in search of +200.
6. **Static metrics stayed in the loop after they were shown not to order nets.** MAE on the
   site's labels "improved" for every losing net (it is in-distribution for anything trained on
   the site set and out-of-distribution for v3b, so the comparison is meaningless). V4 s26 said
   games only; on Tuesday MAE was still choosing epochs and pilots.
7. **Training on an 8 GB laptop for five days, diagnosed four times.** Runs stalled at 1–4% CPU;
   every gate that ran beside a run was contaminated; run E died to a browser at 21:20. The GPU
   box is being rented on the last night instead of the first.
8. **Six levers, capacity for one.** N, S, B, P, T, D, calibration, refit, draw policy,
   drawishness rule. Each needs 400 games to see; the fleet yields about 20 verdicts a day. So
   nothing got a proper 400-game gate except what failed, and the one lever that matters (N) got
   a fraction of the attention.
9. **Search items sent to 300-game gates without unit tests.** The correction-history table
   saturated after ten updates (a 40× step size). A twenty-line test of the table's dynamics would
   have caught it in a minute; instead it cost a 300-game VM gate and 1h50 of paused generators.
10. **Shell hygiene cost hours.** Inline `pkill -f` patterns killed their own shells; a
    `profile.py` shadowed the standard library and killed torch's import; a rename on a
    case-insensitive filesystem deleted a working copy; a browser killed a training run.
11. **The plans were incremental while the target was generational.** V5 gave itself 0.2 for
    2500; the first Prometheus draft 0.25–0.3 for 2700. Both were lists of +10 to +40 items with
    the net as one item among six. Neither was structured so that the one lever that can produce
    +200 got everything it needed first.
12. **Attention went to low-value levers at the critical time.** The book (2,018–4,926 entries,
    +10 to +25 at best, an unanswered organiser email, Mac cores and x86 slots during the net
    runs), the drawishness rule (185 games to prove it neutral), the midgame boost, the root
    guard, adaptive contempt: each a day's attention for a few points.

The common root: **we did not treat the network as a data problem with an experimental method.**
We treated it as a recipe to be tweaked and judged the tweaks with an instrument that could not
see them.

---

## 3. What went well (keep, and do not touch this week)

1. **The engine core.** numba bitboards with magic move generation, PVS with TT, null move with
   verification, LMR/LMP, reverse futility, futility, SEE, singular extensions and multi-cut,
   check extension, mate-distance pruning, repetition and fifty-move detection; 700–730k nodes/s
   on the platform (1.43M nodes in 1.97 s in R66), depth 15–19 in 2 s, 22–25 in quiet endgames;
   perft-exact and differential-tested against python-chess; compile 25–28 s of the 90 s budget;
   a python-chess fallback that turns a crash into a game. **Fifty rated games, zero failures**,
   against a field that has logged 12 flags, 10 illegal moves, 4 inits and 3 crashes. This is the
   platform for everything below and is worth 30–50 points on its own.
2. **The v2 → v3 → v3b line and its lesson.** From scratch on one big consistent source
   (+198, +34); then human whole-game positions labelled by one Stockfish (+39). That *is* the
   recipe; what was missing was volume in the consistent regime, not a better mix.
3. **The diagnosis.** Losses are 100–300 cp evaluation slides over quiet moves in closed
   structures, with healthy clocks and no tactical blunder; the net is 100–250 cp too optimistic
   in exactly those positions (the depth-25 slide replay proved it). Correct and actionable.
4. **Intel.** The site's own per-position Stockfish evaluations harvested for 1,277 games; the
   profiles of the top eight (no blunders, fixed 3–4% clocks, slides, repetition leaks, time
   trouble in a third of some teams' games); the discovery that the site voids repetition games.
   All of it feeds the draw policy and the time policy directly.
5. **The late-Tuesday discipline.** Three controls (export path, gate host, recipe) run and
   cleared; the 200/400-game rule; kill patterns in script files; one gate per box; the trainer
   stall monitor. Two hours of method did more than two days of runs.
6. **The fleet and its tooling.** Any x86 box provisioned by script in ten minutes; generators,
   labellers, pause/resume gates, a judge script with automatic scale matching, telemetry, the
   battery, packaging with byte-check and a fresh-extraction game.
7. **The clock.** Front-loaded horizon (+27 on the proxy), danger multiplier, low-clock caps: no
   flags in 50 games, 16–30 s left at the end, more depth than the top five in the middlegame.
8. **The draw policy**, built on evidence (7 of 9 qualifying losses become draws in the dry run)
   and gated properly: vs Stockfish 2000 it is 47-2-0 at 49 games with the draw rate not rising.

---

## 4. The thesis: what a 2700 engine is, and where the gap actually sits

| Component | What 2700 needs on this platform | What we have | Gap |
|---|---|---|---|
| Speed | ≥ 500k nodes/s on one EPYC core | 700–730k | none |
| Search | the standard alpha-beta feature set, bug-free | all present; tactics 9–10/11, mates 80/80, puzzles 38+/40 | +20–40 from tuning, not this week |
| Clock, robustness | no failures, depth where it matters | 50 games clean; front-loaded clock | none |
| Draw discipline | repetition when worse vs stronger, never when better | built, gate running | small, in progress |
| **Evaluation** | **a net trained from scratch on ≥ 300M consistently labelled positions** | 155M mixed-label Lichess positions, 1M elite | **the whole gap: +150 to +300** |

Three facts decide the design.

**One evaluator, hundreds of millions of positions.** Every strong NNUE in existence was trained
on hundreds of millions to billions of positions scored by one engine at one setting. Ours was
trained on Lichess's mixed archive. The rules allow the fix explicitly: *"training it on
positions an existing engine labelled is allowed"*; *"Training data is unrestricted, including
positions annotated by an existing engine"*; only *"starting from a published chess network"* is
banned. The public Stockfish training data (Leela self-play positions scored by Stockfish, the
files the Stockfish team trains its own nets on, ~2.5 bytes per position in the binpack format,
billions of positions on public mirrors) is exactly "positions an existing engine labelled".
Downloading a slice is minutes on a cloud box; converting it to our chunk format is the one
piece of new engineering tonight. Our own Stockfish-19 labelling of in-distribution positions
(the tournament's games, human elite games, self-play from the tournament's structures) is the
second source, and the CPU fleet does nothing else from tonight.

**From scratch, on the A100, judged at fixed nodes.** A from-scratch run over 300M rows takes
30–60 minutes on an A100 (our trainer at ~1M rows/s). A fixed-node arena (both engines stop at
30k nodes a move, 288 curated openings × 2 colours = 576 games, deterministic, no clock noise)
gives a ±5-point verdict in 15–20 minutes on box B. Together they make the loop *train → judge →
decide* about one hour instead of one day, which is what lets the fixed experiment list of
section 6 complete by Wednesday noon with 400-game confirmations behind it.

**The engine is frozen.** The search, the clock, the wrapper and the battery do not change,
except a node limit for the arena (five lines) and, if a box is idle, a speed pass that ships only
with identical node counts. A better net makes the existing search stronger without retuning; the
one coupling, the evaluation scale versus the pruning margins, is handled by the existing
scale-matched export (`judge_net.sh`).

### 4.1 Refinement at 22:20: three routes, throughput over depth, capacity up

Archit's challenge: with Stockfish and Leela on tap the odds of 2700 should be much higher. They
should, and the reason the 21:45 draft did not say so is where its risk sat: not in the
labellers, in **our own new tooling**, a trainer that has never reproduced a from-scratch net, a
converter to be written tonight, one gate box, and a single data source. Every one of those was
a single point of failure on the critical path. The refinement removes them:

1. **Three independent routes to a net, in parallel from tonight, none a fallback for another.**
   - *Route A, bullet on the public binpacks.* bullet is the CUDA trainer behind nearly every
     3000+ open-source NNUE; it reads Stockfish binpacks natively, trains (768 × buckets → HL) × 2
     → 1 nets with SCReLU and output buckets at millions of positions per second, and saves raw
     weights. The only code we write is the exporter into our safetensors (a permutation of the
     768 piece-square features into our kind × square order, our king-bucket map, our
     quantisation), verified against our integer forward pass on 1,000 positions. This removes
     the "our trainer from scratch" risk from the critical path entirely.
   - *Route B, our trainer on our chunks*, fed by route C's labels and, if the converter works,
     by the public data. C0 still runs, as a diagnostic rather than a gate.
   - *Route C, our own Stockfish 19 labels at depth 5–7 instead of 9.* Measured at 22:10 on a
     loaded box-B core: 269 positions/s at depth 5, 145 at depth 7, 70 at depth 9, 144 at 2,000
     nodes. On 36 quiet cores that is roughly 40M/h at depth 5 and 20M/h at depth 7: **300–500M
     positions in our own distribution by Wednesday noon** (every position of the site's 6,253
     games, Lichess Elite whole games, every position of our own arena and rated games, random
     walks from the curated roots). A depth-5 to depth-7 Stockfish 19 score is dominated by its
     network's judgment, which is the knowledge we are distilling; the extra information in
     depth 9 is small next to four times the volume, and our net's capacity binds long before
     label depth does.
   - *Route L, Leela as a batch labeller, timeboxed to two hours, no dependency.* lc0 ships
     Python bindings (`pip install git+https://github.com/LeelaChessZero/lc0.git`, module
     `lczero.backends`: Weights, Backend, GameState, batch `evaluate`) that return the raw
     value head per position; on the A100 that is tens of thousands of positions a second while
     the GPU is otherwise idle. Leela's value on quiet positions is the best positional judgment
     available, tactically blind, which is what a static evaluator inside an alpha-beta search
     should be. It produces a variant net (L1) judged like any other. If the CUDA build fights
     back for two hours, it is dropped without touching anything else.
2. **Net capacity up by default.** 1024 hidden, SCReLU, 8 output buckets by piece count from P2
   on; our numba path already supports all three (HIDDEN, `act` and NO are read from the weights
   file). With ≥ 300M positions a 512 CReLU net leaves strength on the table; the 5 s gate
   decides whether the ~12% speed cost is paid back (expected: +40 to +80).
3. **Judging capacity ×3.** Fixed-node arenas on box B *and* box A (both pause their labellers),
   and a fixed-depth-8 arena (five minutes) as a coarse first filter, so the day allows about 40
   verdicts instead of 12.
4. **One search item, Thursday only, on top of the new net:** a short SPSA of the pruning and
   reduction constants at fixed nodes (2,000 games an hour on two boxes; RFP, futility, LMR
   base and divisor, null-move reduction, aspiration window), and correction history measured
   at 576 games rather than 100. Expected +20 to +50; ships only into V5.1 and only through the
   full ladder.

What this does not change: Stockfish's and Leela's *strength* cannot ship (the rules ban their
networks and any port of them); it enters only as labels into a net a hundredth of their size,
searched by an engine a third of their speed. That is why the ceiling is 2750–2850 on this
scale, not 3000, and why the plan spends its effort on volume, capacity and judging rather than
on cleverer labels.

### 4.2 Why this cannot end like V4 and V5: the assurance ladder

Archit's condition for the GPU (22:30): we must be able to reassure ourselves that this does not
end as V4 and V5 did, with every new net level or worse than v3b. Nobody can promise the
outcome. What can be promised is that **each of the causes of the V4/V5 story is blocked by a
rule with a test behind it**, that **no GPU hour is spent before the instrument and the trainer
are proven on cheap checks**, and that **the downside is bounded**: one night, under £30 of
GPU, and V5.0 still ships on time with v3b if nothing clears.

| V4/V5 cause | How it is blocked | The test that proves the block |
|---|---|---|
| gates that could not see the change (40 games, ±12 points) | 576 fixed-node games per verdict, ±5 | **Stage 0**: the instrument is calibrated on nets whose order we know: v3b vs v3b must land at 50 ± 4; v3b vs v3 (+39 in games this week) and v3b vs v2 (about +70) must come out in that order and clear of zero. No net is judged until this is green |
| an unvalidated from-scratch trainer | two trainers, each with a control on v3's own data | **Stage 1**: bullet on our Lichess quiet chunks (converted) and our trainer on the same data must each land within ±40 of v3 at fixed nodes. A trainer that fails its control trains nothing else |
| four label scales in one set | one evaluator per set; no per-source scale without a written fit | the judge checks the exported net's slope on the site chunk and its static error on the four slide positions before any game |
| 1–9M rows oversampled into a 155M-row net | nothing under 100M rows enters a from-scratch run; the oversampling flag is not used | the run manifest is printed and logged in section 13 |
| draw-heavy self-play with a result blend | no self-play games as the bulk; WDL only as P3, alone, with its interval | P3's kill rule |
| fine-tuning at a high rate | no fine-tunes (P1b is insurance only, judged like any other) | – |
| the Mac thrashing under a gate | the Mac never trains; every measurement on a box, one gate per box | the scripts pause generators and wait for a free box |
| static metrics choosing nets | static numbers only detect a broken export | judge script, then games |
| export or scale mismatch between trainer and engine | exactness test on 1,000 positions for every export (both trainers) | `tests/test_train_consistency.py`, `tests/test_nnue.py` |

**The go/no-go sequence, with costs:**

| Stage | What | Needs | Time | Go rule |
|---|---|---|---|---|
| 0 | instrument calibration at 30k nodes, 600 games each: v3b/v3b (determinism: mirrored PGNs, exactly 50%), v3b/v3 and v3b/v2 (the known order, clear of zero, and the pentanomial noise floor read from them) | no GPU; the UK box's first socket, or box B until it is up | ~20 min once `node_gate.py` exists | order reproduced, v3b/v3 clear of zero, determinism exact |
| 1 | trainer controls C0 and C0b: our trainer and bullet on v3's data, one per card | the UK box, ~1 h of both GPUs | ~1.5 h | at least one trainer within ±40 of v3; the other trains nothing else |
| 2 | the bet: B1 and R1 (and P1) vs v3b at fixed nodes | A100, 1–3 h | by Wed 05:00 | ≥ 55% for any one → the time ladder; 50–55% → one more data doubling; < 50% → **stop and diagnose**, no retraining until the cause is named |
| stop | Wed 08:00: no route ≥ 50% vs v3b | – | – | GPU work stops; V5.0 = v3b + gated extras, on time; Thursday goes to the retune and the draw policy |

Why this is different in kind and not only in discipline: V4 and V5 tried to *add* 1–9M
distribution-shifted rows to v3's recipe. Prometheus *replaces the data regime* with the one
every strong NNUE was trained in. The existence proof is already ours: v3b's +39 came from
1M human positions labelled by one Stockfish. Route C scales that exact source by 300×; route
A uses the data Stockfish's own nets are trained on; and neither touches the recipe that failed.

### 4.3 Refinement at 23:00 with the full infrastructure: every bottleneck and its fix

With the UK box (2× RTX 5090, 384 Genoa threads, 515 GB, a 20-hour window) plus the two GCP
boxes, the VM and the Mac, the binding constraints move. Each one below was found by walking
the night's critical path with the new numbers; each has a fix that is in the workstreams and
the timeline, not a hope.

| Bottleneck | Where it bites | Fix |
|---|---|---|
| **Compile per game in the arenas** | the harness starts a fresh process per game: 25 s of numba compile per side, so a 576-game gate spends more CPU compiling than playing (that is why 400 games took 100 min on eight workers) | `node_gate.py`: one engine process per worker per side, compiled once, alive across games; each game pinned to its own physical core. On the UK box's first socket a **600-game fixed-node verdict takes about five minutes**. The same persistent-engine arena runs the timed ladder on the GCP boxes: 576 games at 5 s in ~40 min instead of 2.5 h |
| **Fixed-node games are deterministic** | v3b vs v3b at fixed nodes is *exactly* 50% by construction (each opening's two games are mirror images) and measures no noise at all; one opening yields one independent sample | the v3b/v3b run becomes a determinism check (mirrored PGNs, or the harness is broken); the noise floor is read from the pentanomial spread of v3b/v3 and v3b/v2; **opening diversity is the sample size**: 288 curated roots + ≥ 400 top-ten positions at ply 10–16 (W1e) ≈ 700 opening pairs; a verdict is 600 games from 300 openings, a ship candidate plays all 1,400 |
| **Position supply and dedup for 300+ labellers** | 300 workers at depth 7 consume ~75k FENs/s; elite games repeat their first 16 plies millions of times | producers (eight processes decoding PGNs at ~50k plies/s each) write FEN shards ahead of the consumers; per-shard dedup for plies ≤ 16, skip plies < 8, skip in-check, skip \|score\| > 3000; label = Stockfish 19 **depth 7** from the side to move; the game result travels with the row |
| **The binpack converter on the critical path** | route B depended on a Rust tool written and verified tonight | **dropped from the critical path.** Public binpacks feed bullet only (its native loader). Route C writes **bulletformat (32 bytes a row) as the canonical format**, which bullet reads as is and our trainer reads with a 40-line struct reader. Both trainers consume the same own-label set; the experiment list is renamed below |
| **Two evaluator scales** | the public binpacks carry Stockfish's raw internal scores; our own labels are Stockfish 19's UCI centipawns; they are not the same scale | never in one run without a fitted scale written in section 13: B-series = binpacks only, P/R-series = own labels only, P4 = the mix with the fitted scale. Every export is slope-matched to v3b's 1.305 against the site chunk regardless of source |
| **Transposition-table memory in parallel arenas** | 256 MB per engine × 192 engines = 48 GB | `BINI_TT_BITS=22` (64 MB) inside arenas; 30k nodes never fill it; the platform build keeps 2^24 |
| **Labellers, trainers and arenas on one box** | 384 threads shared by three jobs with different sensitivities | a core map, enforced with `taskset` in the scripts: 32 threads for the two trainers' loaders; a **16-thread slice with idle SMT siblings reserved for real-clock proxies** (this box is Genoa, the platform's EPYC 9V74 is Genoa: the most platform-like timed measurement we have had); the remaining ~336 threads label (~75k positions/s, ~250M/h, a billion by about 04:30) and are **SIGSTOPped for the five minutes of each fixed-node verdict** by the gate script, which resumes them itself |
| **The 90 Mbps upload** | mirroring labels off the box | exports and checkpoints are megabytes; labelled shards mirror to box B continuously in the background (1 GB per 30 min at 90 Mbps is 1.5 min); nothing waits on it |
| **One person writing five tools tonight** | the integrator is the serial path | three sub-agents in parallel, each with a named acceptance test: (i) `node_gate.py` (persistent engines, pinning, pentanomial report; test: v3b/v3b mirrored PGNs), (ii) `label_fleet.py` (producers, consumers, bulletformat, resume; test: 10k rows round-trip through both readers and a spot check of 50 labels against a fresh Stockfish), (iii) `bullet_export.py` + the bulletformat reader for our trainer (test: `test_train_consistency.py` on 1,000 positions). The integrator provisions the box and sequences the runs |
| **Judging still gated by timed games** | only the timed ladder needs quiet cores | fixed-node verdicts (minutes, UK box) filter; the GCP boxes run only the timed ladder of the winners: 5 s gates on both boxes, 10 s on the VM; capacity ~10 timed verdicts a day, which is more than the winners need |

Odds after this pass (section 11): the judging and data-path bottlenecks were the two largest
residual risks in the 22:20 numbers; a net ≥ +100 by Wednesday 13:00 is now about 0.85 and
2700+ about 0.45. The ceiling argument of section 4.1 is unchanged.

Not in this plan, and why: a second hidden layer (10× the output cost in numba), new search
features before the net is in (noise-level at our gate capacity, and their value changes with
the evaluation), tablebases, opponent modelling at the board, anything not in section 6.

---

## 5. Workstreams

### W1 — Data (Claude; the CPU fleet and the A100 box's cores)

**W1a. Public Stockfish training data → our chunks.** Pick one recent standard-chess file from
the public index (robotmoon.com/nnue-training-data lists the test80 2023–2024 files and where they
are hosted; prefer a filtered/deduplicated variant, which already drops positions in check and
non-quiet positions). Download to the A100 box. Convert with a small Rust tool on the `sfbinpack`
crate (Disservin's port of the Stockfish binpack reader: it yields position, move, score, ply,
result per entry) into fixed-width records → `chunk_NNNN.npz` (`pieces` uint8[N,64], `stm`, `cp`
from White's view, `result`, `quiet`=1), applying our filters: not in check, the recorded move not
a capture or promotion, |score| ≤ 3000, ply ≥ 16. Target: **300M rows by Wed 03:00, 1B by Wed
14:00.** Fallback if the converter is not producing rows by Wed 01:00: the `bullet` trainer's
own `SfBinpackLoader` reads the files directly; we then train in bullet with our bucket layout and
write the quantiser to safetensors ourselves.

**W1b. Our own single-evaluator set (Stockfish 19 at depth 7 for every position; one depth,
never mixed).** `label_fleet.py`: eight producer processes decode PGNs into FEN shards ahead of
~336 consumer processes (raw UCI, one Stockfish each), output **bulletformat** shards of 1M rows
(the format both trainers read), resumable, with a manifest of source counts per shard; the
labelled shards mirror to box B in the background. Order: all positions of the 6,253
scraped site games (~500k, tonight first: the tournament's own distribution); Lichess Elite
2025-03..06 whole games (every second position after ply 8: tens of millions available); every
position of our own arena, proxy and rated games; random walks from the curated roots (the S1
generator's exploration, without the game play). Rate ~20–40M rows/h on 36 cores (the two GCP
boxes, the VM, the A100 box's vCPUs). **300–500M by Wed 12:00, ~1B by Thu 06:00.** Existing
dec2/eg2/eg3 chunks (depth 9 and 12) are kept out of the main set and tested as a second source
in P4 only; the site-labelled (SF16) and Lichess sets never enter.

**W1e. The top teams' games (the scraped corpus, 6,253 games and growing by ~200 a round).**
Used three ways, none of them as labels: (1) **seeds**: every position of every game involving
a top-30 team becomes a start point for the route-C random walks, so millions of labelled
positions come from the structures the Swiss will actually produce (closed Ruy Lopez, Italian,
London, closed Sicilian, symmetrical English), labelled by our one evaluator; (2) **gate
openings**: a second opening set for the fixed-node arena, positions at ply 10–16 of top-ten
games, so the judge plays the games the top plays, weighted toward the families we lost in;
(3) **the slide set**: 100–200 positions from top-ten games where the site's evaluation moved
100 cp or more over quiet moves; every export reports its static error there against v3b's, as
a diagnostic, never a gate. The site's own Stockfish-16 depth-16 evaluations stay out of
training (a second evaluator) and serve only as held-out error reporting. Their moves are not
imitation targets: the labels come from an engine far stronger than any team here. The hourly
scrape continues and feeds all three uses.

**W1d. Leela batch labels (route L, timebox two hours, A100).** `lczero.backends` with a strong
public network, batches of 256, the raw value head converted to centipawns through the same
sigmoid the trainer uses, on the W1b position stream, ~30–100M/h if the CUDA backend builds.
Output chunks `data/leela/`, a separate single-evaluator set for L1.

**W1c. Lichess re-stream on the A100 box** (`stream_lichess.py` from the public evaluation
database, ~40 min) so the trainer control C0 can run without uploading 13 GB from the Mac.

### W2 — Trainer (Claude; the A100)

Route A: bullet on the A100 (rustup, CUDA toolkit, `cargo build --release --features cuda`),
network = our 8-bucket mirrored king map × 768 → 1024 × 2 → 8 output buckets, SCReLU, WDL
blend 0.75, reading the public binpacks directly; `bullet_export.py` turns its saved raw weights
into our safetensors (feature permutation, bucket map, QA 255 quantisation) and
`tests/test_train_consistency.py` proves the integer forward pass matches on 1,000 positions
before any game is played. Timebox to a first exported net: two hours from the box being up.

Route B: `train_nnue.py` gains a CUDA device, a background chunk loader (four chunks in flight,
pinned memory), a `--sources` manifest, held-out chunks from every source, and a throughput print. The
recipe stays the proven one: 8 king buckets × 768 → HIDDEN × 2 → 1, MSE on sigmoid(cp/400),
Adam, one-cycle, batch 16k, lr 1e-3 from scratch. Export and scale matching unchanged
(`export_from_pt.py --out-scale`, slope fitted to v3b's 1.305 on the site chunk so the search
margins keep their meaning). Target ≥ 1M rows/s; a 300M × 8-epoch run in under an hour.

### W3 — Judging (Claude; box B, the VM, box A)

1. `BINI_MAX_NODES`: the search aborts at N nodes (slot 1 of `tlim`, checked where the clock is
   checked). Five lines in `bini_search.py`/`bini_engine.py`, no signature change.
2. `arena_par.py --nodes 30000`: both agents at 30k nodes a move, book off, 576 games on the
   curated openings, 8 workers on box B: **15–20 minutes, ±5 points.** Every net is judged here
   first, against v3b or against the current best.
3. The time ladder for anything that wins at fixed nodes: 400 at 5 s + 0.05 s on box B (~100
   min, ±5), 300 at 10 s on the VM (~2.5 h), 40 real-clock proxies on box A (reference 46.3%),
   blunder set at the platform budget, the four slide positions.
4. The battery, unchanged and uncompressed, on the exact zip, on the Mac (which no longer trains).

### W4 — Engine (frozen) and the speed pass (Claude; Mac)

Frozen: `bini_v5/` with `BINI_CORR=0 BINI_CONT=0 BINI_SEEP=1`, calibration off for any new net
(the table was fitted to v3b), the clock as is, the draw policy at its gated setting. HIDDEN is
read from the weights file, so a 1024-wide net needs no engine change (compile +2–3 s, ~−15%
nodes/s, accepted only if the net wins at 5 s). Speed pass (int16 accumulators, single in-check per
node) only if the Mac is idle Wednesday and only with identical node counts at fixed depth.

### W5 — Assembly (Claude + Archit)

V5.0: `assemble_v5.sh` with the best gated net (or v3b), SEE pruning, the draw policy if its two
gates pass, the graded book only if its no-book rollback zip is tagged beside it; 1,000-game
regression vs the live V3 at 5 s on box A; battery; package; byte-check; fresh-extraction game;
hand-over note with the validation checklist. V5.1: the same with the Thursday net.

### W6 — Archit

Section 12.

---

## 6. The experiment list (fixed; nothing is added without a line here)

| ID | Data | Net | Question | Judge | Kill rule |
|---|---|---|---|---|---|
| **C0** | Lichess quiet (our existing chunks, ~155M), v3's recipe, our trainer on the GPU | 512 CReLU | does our trainer reproduce v3 from scratch? (Stage 1 control) | 600 fixed-node vs v3b | < 45% → our trainer trains nothing else tonight; the P-series runs on bullet instead |
| **C0b** | the same Lichess chunks written as bulletformat, bullet | 512 CReLU | does bullet plus our exporter reproduce v3? (Stage 1 control) | 600 fixed-node vs v3b | < 45% with the consistency test green → the data path, not the exporter; compare the two controls' errors on the site chunk |
| **P1** | route C: own Stockfish-19 depth-7 labels, first 300M, cp only, our trainer | 512 CReLU | the bet on v3's own architecture: one evaluator, in-distribution volume | 600 fixed-node vs v3b | < 50% with C0 passed → the label filter or scale; inspect with `net_diag` and the slide set before any retrain; **no new mixes** |
| **B1** | public binpacks, ≥ 300M, read by bullet | 1024 SCReLU, 8 output buckets | route A: the proven trainer on the proven data | 600 fixed-node vs v3b | exporter mismatch (consistency test fails) → fix the exporter, never the net |
| **P2** | P1's data | 1024 SCReLU, 8 output buckets | capacity | 576 vs P1 | ships only if also ≥ P1 at 5 s (speed cost) |
| **R1** | route C: own labels, ≥ 300M, bullet | 1024 SCReLU, 8 output buckets | in-distribution volume on the proven trainer | 600 vs best | < 50% vs v3b with B1 ≥ 50% → the label filter or depth; check the slide set and MAE by piece count before changing anything |
| L1 | route L: Leela labels on the same positions | as R1 | positional labels | 576 vs best | timebox only; dropped silently if the bindings do not build by Wed 01:00 |
| T1 | – | – | Thursday SPSA of pruning/reduction constants at fixed nodes on the new net; correction history at 576 | 576, then the full ladder | V5.1 only; nothing at < +20 clear of zero |
| **P3** | P1's data, result blend λ = 0.8 | best of P1/P2 | does WDL help on this data? | 576 vs best | drop if not ≥ 52% |
| **P4** | P1's data + W1b own set (scale fitted per source on 100k relabelled positions) | best | in-distribution data on top | 576 vs best | drop if not ≥ 52% |
| **P5** | 1B rows, 10 epochs, the winning recipe | best | the V5.1 net | 576, then 400 at 5 s, 300 at 10 s, proxies | V5.1 only at ≥ +30 vs V5.0 clear of zero |
| P1b | v3b fine-tuned one epoch on P1's data at 5e-4 | 512 | insurance if C0 fails and P1 cannot be trusted | 576 vs v3b | GPU-idle only |
| S1 | – | – | int16 accumulators, single in-check | node-identical at fixed depth, then 400 at 5 s | any node-count difference → not shipped |
| D1 | – | – | draw policy (running: SF-2000 draw rate; full-strength draws must rise) | as designed | fails either → off |

Every result is written into section 13 of this file with its game count and interval before
anything is called won or lost.

---

## 7. Hardware and what each machine does from tonight

| Machine | Spec | Job | Never |
|---|---|---|---|
| **GPU box** (Vast.ai #50131784, UK: 2× RTX 5090, 2× EPYC 9654 Genoa = 384 threads, 515 GB RAM, 3.6 TB NVMe, 1.4 Gbps down; **a 20-hour window, Tue ~23:00 → Wed ~19:00**) | core map (section 4.3): ~336 threads labelling, 32 for the trainers' loaders, 16 (siblings idle) for real-clock proxies; labellers paused for each five-minute fixed-node verdict | both trainers in parallel (all runs, front-loaded into the window); binpack download; **route C labelling at ~250M/h, a billion by ~04:30**; **every fixed-node verdict**; the real-clock proxies of the final candidates on Genoa; Leela if it builds. Labels, checkpoints and exports mirror to box B continuously, so the window's end loses nothing | nothing from it ships except our own trained weights; nothing that needs a GPU is scheduled after Wed 19:00; timed games never share a core with a labeller |
| GCP box A `gcp-x86` | 8 vCPU, 31 GB, Stockfish 19 at 1.09M nodes/s/core | **the timed ladder, half**: 5 s gates of fixed-node winners (persistent engines, 576 games in ~40 min); the 1,000-game regression Wednesday afternoon; S1 generators when idle | gates and generators at once (the scripts pause) |
| GCP box B `gcp-x86b` | same | **the timed ladder, half**: 5 s gates; the mirror of the UK box's labels, checkpoints and exports; Stage 0 until the UK box is up | two gates at once |
| Oracle VM `priorcrypto-vm` | 4 ARM cores, 23 GB | 10 s confirmations (300 games); the draw gate finishing | training |
| Mac (M2, 8 GB) | – | development tonight (the three tools, on small data), the speed pass, **the battery** | training; any two heavy jobs |

Driver scripts live in `bini_v5/tools/` (`provision_gpu.sh` minus Leela, `x86_gate.sh`,
`vm_gate.sh`, `x86_proxy.sh`, `judge_net.sh`, `assemble_v5.sh`, `battery.sh`, `package.sh`,
`pull_loop.sh`); new tonight: `binpack_convert` (Rust), `label_fleet.sh`, `node_gate.sh`,
`train_gpu.sh`.

---

## 8. Timeline (London time)

**The GPU window is 20 hours (Tue ~23:00 → Wed ~19:00), so every training run is inside it;
everything after is CPU-only** (gates, proxies, the battery, the Thursday SPSA). Hour by hour on
the GPU box: H0 provision, downloads, labelling on ~336 threads; H1–2 the Stage 1 controls on both
cards; H2–5 B1, P1, R1 (the first ~150M own labels); H5–9 the variants P2/P3/P4 while labels
reach a billion; **H9–13 (08:00–12:00) the final runs: 1024 SCReLU on ~1B rows, two data
recipes, one per card**, exported by 13:00; H13–19 Leela's L1 if it built, one last run with
every label, final rsync at 18:30. The Thursday V5.1 candidates are therefore trained Wednesday
midday and chosen Thursday from Wednesday night's gates plus Thursday's rated games; there is no
Thursday retrain, which is the one thing 20 hours gives up against 40.

| When | A100 box | Box B (gates) | Box A + VM | Mac / Claude | Milestone |
|---|---|---|---|---|---|
| **Tue 22:00–23:30** | Archit rents the UK box; provisioning (root container: Stockfish 19 avx512, rustup + bullet, the two venvs, the engine, the site and elite games; ~25 min) | draw pressure gate finishes; refit gate done (50.7%, level) | generators stay on until the UK labellers are producing | three sub-agents write `node_gate.py`, `label_fleet.py`, `bullet_export.py` + the bulletformat reader, each to its acceptance test; the integrator provisions | box up; tools tested on small data |
| **Tue 23:30–00:30** | labelling starts on ~336 threads (site games first, then elite); binpacks downloading; **Stage 0** on the first socket (20 min) | Stage 0 on box B in parallel until the UK box has it | – | integrator reads Stage 0 | **instrument calibrated**; labels at ~250M/h |
| **Tue 23:00–01:00** | binpack file(s) downloaded; bullet built; **B1 training starts** (route A); lczero bindings build attempt (route L, timebox); converter on `sfbinpack` for route B | fixed-node control: v3b vs v3b (must be 50 ± 5) | labelling | bullet exporter verified by the consistency test on 1,000 positions | **a bullet net exported and judged by ~02:00**; route L kept or dropped by 01:00 |
| **Wed 01:00–03:00** | B1 exported and judged; our trainer smoke; **C0** (diagnostic) and **P1** start; **R1 starts** on the first ~100M own labels | B1 vs v3b (576); v3b vs v3b done | labelling | – | **first real verdict on the thesis (B1) by ~02:30** |
| **Wed 03:00–06:00** | P1 exported at 300M; **P2 starts** (1024 SCReLU) | C0 vs v3b (576); P1 vs v3b (576) | labelling | judge (slope, scale export, exactness, blunder set, slides) for each export | **first real verdict on the thesis by ~05:00** |
| **Wed 06:00–09:00** | P3, then P4 | P2 vs P1; P3 vs best; best net **400 at 5 s vs v3b** | VM: best net 300 at 10 s; box A: 40 proxies | – | the V5.0 net identified |
| **Wed 09:00–13:00** | **P5 starts** (1B rows, 10 epochs, ~3–4 h) | P4 vs best; then S1 speed gate if ready | 10 s and proxies finish | speed pass (node-identical) if idle | **13:00 V5.0 net decision** |
| **Wed 13:00–19:00** | P5 | 1,000-game regression V5.0 vs live V3 at 5 s (box A) | – | **battery on the exact zip**, package, byte-check, fresh-extraction game, hand-over note | V5.0 ready |
| **Wed 19:00–21:00** | P5 exported | – | – | hand-over | **Archit uploads V5.0; validation log back** |
| Wed 21:00–Thu 09:00 | P5 variants if any (P5 + WDL) | P5 vs V5.0 net: 576 → 400 at 5 s | 300 at 10 s; proxies | scripted chain, logs only | V5.1 candidate judged |
| Thu 09:00–15:00 | – | – | – | battery on V5.1 if it cleared; Thursday's rated rounds (from 08:00) validate V5.0 live | **V5.1 uploaded by 15:00 only if ≥ +30 clear of zero, not negative at 10 s, proxies not worse, V5.0's platform games clean** |
| Thu 15:00–Fri 11:00 | off | off | off | platform telemetry only | rollback only |

Slips move the hand-over, never the battery. If P1's verdict is not in by Wed 08:00, V5.0 is
v3b + the gated extras and the net programme continues for V5.1 only.

---

## 9. Rules of execution

1. **Games decide, at the right resolution.** 576 fixed-node games to rank nets; 400 at 5 s and
   300 at 10 s and 40 proxies to ship one. Nothing under those counts is called a result. A gate
   with a fallback game, a compile over 75 s or a load spike is rerun, not tallied.
2. **Controls before conclusions.** C0 and C0b run before any P- or B-series net is trusted; the
   Stage 0 calibration (determinism exact, the known order reproduced) runs before any
   fixed-node verdict is read; a verdict is 600 games from 300 openings, never fewer openings.
3. **One evaluator per training set.** No chunk enters a run whose labels came from a different
   engine or setting than the rest, unless a fitted per-source scale is written down in section
   13 with the positions it was fitted on.
4. **The experiment list is closed.** Section 6, no additions without a line here and a gate slot.
5. **The engine is frozen.** Node limit and the node-identical speed pass only.
6. **The Mac never trains.** One heavy job at a time on it; every measurement runs on a box.
7. **Every destructive shell step is a script that lists its target.** Kill patterns in files;
   `bini_*` names only; no `profile.py`, `types.py`, `chess.py`, `random.py`, `time.py`.
8. **The safe build exists before the ambitious one is attempted.** Rollback zip tagged; battery
   never compressed; one hand-over per day.
9. **Everything shipped is ours.** Our code, our trainer's weights from random initialisation,
   our engine's book. The README states the training data (public Stockfish training data by
   file name; our own Stockfish-19-labelled positions) and the trainer. Nothing from Stockfish
   or Leela is in the zip.
10. **This file is the log.** Section 13 records every run, gate and decision with numbers.

---

## 10. Risks and their answers

| Risk | Answer |
|---|---|
| The binpack converter is not producing rows by 01:00 | bullet's `SfBinpackLoader` trains on the files directly (our bucket layout, our quantiser); in parallel W1b keeps labelling, and P1 runs on W1b + re-streamed Lichess if it must |
| C0 fails (the trainer cannot reproduce v3 from scratch) | it is the most valuable result of the night: it explains the week. Fix candidates in order: the one-cycle warm-up (3%), Adam epsilon, init std, batch/lr pairing; else bullet as trainer with the same data |
| P1 is level or worse despite C0 passing | inspect, do not retrain blindly: `net_diag` slope and MAE by piece count on the site chunk, the four slide positions, a 1,000-position agreement check against v3b. The likeliest causes are the scale (a 2× wider SF-internal scale un-matched at export) and filtering (positions in check or non-quiet let through) |
| The public data's evaluator is Leela's value rather than Stockfish's search (some files are one, some the other) | either is a single consistent source; the scale fit at export handles the units; prefer a Stockfish-rescored file where the index says so |
| Upload bandwidth from the Mac | nothing large leaves the Mac: the public data, the Lichess DB and the elite PGNs are fetched by the cloud boxes directly |
| The trainer is slower than 1M rows/s on the A100 | 300M × 8 epochs still fits in 2 h; P5 shrinks to 600M |
| Compile time with a 1024-wide net | +2–3 s (today 25–28 s of 90); the 75 s join hedge stays |
| Organiser challenge to the training data | the rules and the FAQ allow it in writing; the README discloses it; Archit's email (section 12) puts it on record before the upload |
| Fatigue at 4 am | every chain is a script with a log; the decision points are 05:00, 13:00, Thursday 09:00; nothing is typed at 3 am that is not a script |
| A gate polluted by a co-running job | one gate per box; the scripts pause generators and wait for a free box |

---

## 11. Honest odds

Revised at 22:20 for the three-route structure (section 4.1). The routes fail for different
reasons (bullet: exporter mismatch; our trainer: the from-scratch path; own labels: depth or
filter), so their failures are only weakly correlated; what they share is the judge and the
exporter's consistency test, both of which are controlled.

| Step | Probability | Note |
|---|---|---|
| Route A: a bullet net exported, consistency test green, by 02:00 | 0.7 | proven trainer and loader; the exporter is 60 lines with an exact test behind it |
| Route C: ≥ 300M own labels by Wed 12:00 | 0.85 | measured throughput, 36 cores, resumable labeller |
| Route B: converter + our trainer producing a from-scratch net by 05:00 | 0.55 | the 21:45 draft's single path, now one of three |
| Route L: Leela labels flowing by 01:00 | 0.4 | timebox; nothing depends on it |
| **At least one net ≥ +100 at fixed nodes by Wed 13:00** | **0.8** | any one route suffices |
| A new net in V5.0 Wednesday evening | 0.7 | needs the verdict by 08:00 and the time ladder by 13:00 |
| The 1B-row 1024 net (P5/B-series) beats V5.0 by ≥ +30 for V5.1 | 0.55 given a net landed | |

| Outcome by Friday | Build | Ladder | Probability |
|---|---|---|---|
| Net lands near the top of its range, Thursday retune ships | 1024 SCReLU net + T1 in V5.1 | 2700–2850 | 0.4 |
| Net lands | new net in V5.0, V5.1 modest or not cleared | 2580–2700 | 0.25 |
| Net modest | +50–100 | 2450–2580 | 0.15 |
| No new net clears | v3b + draw policy + SEE (+ book) | 2380–2450 | 0.2 |

**2700+: about 0.45 (after the 23:00 bottleneck pass, section 4.3). Top-five seed: about 0.7. First: about 0.2**, in the first row, where the
Swiss's 13 rounds and the knockout's paired colours give a 2750 engine with perfect draw
discipline a real chance against the leader. The floor is unchanged: a solid top-ten seed with
zero failures.

What holds the number at 0.4 rather than higher: the ceiling of a single-layer net inside a
700k nodes/s numba search (about 2750–2850 on this scale, section 4.1), forty hours with two
hand-overs, and a search that has never been tuned. What moves it most, in order: the A100 tonight
(all three routes train there), the fleet labeller by 23:00 (route C's volume), the bullet
exporter's consistency test (route A's trust), and the discipline of section 9.

---

## 12. What Archit does, now

1. **Rent the GPU box tonight on Vast.ai.** The card: **RTX 4090 or RTX 5090** (an A100 SXM is
   the second choice if no 4090/5090 host meets the rest of the spec; an H100 buys nothing
   here). NNUE training is a sparse fp32 workload where a 4090 out-runs an A100, bullet's own
   users train on 4090s, and lc0's fp16 backend is fastest on Ada/Blackwell consumer cards.
   What matters more than the card is the host: filter for **on-demand (not interruptible)**,
   verified host, reliability ≥ 99.5%, **≥ 16 effective CPU cores** (32 preferred; they label
   and decode binpacks), **≥ 64 GB RAM**, **≥ 300 GB disk set at rental** (it cannot be grown
   later), **inet down ≥ 500 Mbps** (the binpacks are tens of GB), direct SSH. Template:
   `nvidia/cuda:12.4.1-devel-ubuntu22.04` (or the PyTorch *devel* image); the runtime-only
   images have no `nvcc` and bullet and lc0 will not build. Add the ssh line Vast shows (it is
   `ssh -p <port> root@<ip>`) to `~/.ssh/config` as `Host gpu` and say "gpu is up"; the
   provisioning script is adjusted for a root container (no sudo, no systemd). Expected cost:
   about $0.4–0.6 an hour, under $30 for the whole event; a second identical box for Leela
   labelling is rented only if the bindings build (section 4.1, route L). Stage 1 (section
   4.2) does not start until Stage 0 is green, so an idle first hour costs 50 cents.
2. **One email to the organisers, tonight** (two lines): our network is trained by our own
   trainer from random initialisation on public Stockfish training data and on positions we
   labelled with Stockfish ourselves, per the docs' "positions an existing engine labelled";
   nothing from Stockfish or Leela ships; our opening book is our own engine's analysis. Ask
   them to say if they disagree. This puts the disclosure on record before Friday.
3. **Keep the Mac free** of browsers and other work during the battery Wednesday afternoon.
4. **Wed 19:00–21:00: upload V5.0**, bring back the validation log's init line and nodes/s.
5. **Thu 14:00–15:00: upload V5.1** only if the hand-over note says it cleared.
6. **Friday: nothing.** No uploads after Thursday 15:00 unless the platform shows a defect.

---

## 13. Log (results are written here, with counts and intervals, as they land)

- 21:45 Plan rewritten from a clean slate. State of the fleet: box A eight S1 generators + a
  200-game gate finishing (calibration 52.8%, +19 ±49 at 200: within noise); box B eight S1
  generators + the refit gate (47.5% at 141); VM three S1 + eg2 + the draw gate vs Stockfish
  2000 (47-2-0 at 49, draw rate not rising); Mac idle (run E killed at 21:20). Live build: V3
  (`bini-2.0`, v3b net), rollback `submission_v3_0907_1258.zip`.
- 22:10 Refit gate final: 50.7% (+5 ±48) over 200: level, dropped. Draw pressure gate (full
  strength) still running on box B. Stockfish 19 labelling throughput probed on one loaded box-B
  core over 60 curated positions: depth 5 = 269/s, depth 7 = 145/s, depth 9 = 70/s, 2,000 nodes
  = 144/s, 8,000 nodes = 48/s (a quiet core runs about twice that).
- 22:20 Plan refined after Archit's challenge (section 4.1): three independent routes to the net
  (bullet on the public binpacks; our trainer on our own labels; a timeboxed Leela labeller), own
  labelling at depth 5–7 for 4× the volume, 1024 SCReLU with 8 output buckets as the default
  capacity, judging on both GCP boxes, a Thursday search retune at fixed nodes. Odds revised in
  section 11: a net ≥ +100 by Wed 13:00 0.8; 2700+ 0.4; top five 0.65; first 0.2.
- 22:35 Archit's condition for the GPU: assurance that this cannot end like V4/V5. Section 4.2
  added (the assurance ladder: Stage 0 instrument calibration without GPU, Stage 1 trainer
  controls, Stage 2 the bet, hard stop Wed 08:00) and W1e (the top teams' games as seeds, gate
  openings and a slide diagnostic set; never as labels or imitation targets).
- 22:50 GPU decided with Archit: Vast.ai #50131784 (UK, 2× RTX 5090, 2× EPYC 9654, 384 threads,
  515 GB, 3.6 TB, 90 up / 1427 Mbps down, 99.76%), a 20-hour window Tue ~23:00 → Wed ~19:00.
  No HTML rendering of this plan from here on (Archit): this file is the plan of record.
- 23:00 Full-infrastructure bottleneck pass (section 4.3): persistent-engine arenas (a 600-game
  fixed-node verdict in ~5 min on the UK box; timed gates 4× faster on the GCP boxes), fixed-node
  determinism handled (mirrored-PGN check, noise from known pairs, 700 opening pairs),
  bulletformat as the one data format for both trainers, the binpack converter dropped from the
  critical path, one core map for labellers/trainers/proxies with labellers paused during
  verdicts, real-clock proxies on Genoa. Experiment list renamed (C0, C0b, P1 on own labels,
  B1, R1 on bullet). Odds: net ≥ +100 by Wed 13:00 0.85; 2700+ 0.45.
- 23:10 Box up: Vast instance 50314681 (a 92-CPU quota of 384 threads, 241 GB, 300 GB disk,
  2× 5090, 1.2 Gbps, $1.228/h; credit $24.95 = a hard clock to ~19:20 Wed). Provisioned from
  `provision_vast.sh` (Stockfish 19 vnni512, rustup + bullet, both venvs, elite zips, the 21.7 GB
  Lichess evaluation database). Session interrupted 23:15 (account limit) until 01:41.
- 01:45 (Wed) Resumed. A peer session (Opus) had run `gpu_overnight.sh` on the box meanwhile:
  bullet built; **all four elite zips extracted at stride 2 (even plies, White to move) and
  labelled at Stockfish 19 depth 7: 45.9M rows in 230 npz shards, 526 positions/s per worker**;
  its binpack download hit the wrong Hugging Face endpoint (0 files) and its training runs
  crashed on the empty list. Verified 20 of its labels against a fresh depth-7 search (mean
  difference +24 cp, signs right). Kept: bullet, the labelled set, its labeller (lifted out as
  `peer_label.py`). Overridden: the download (the dataset API needs `/datasets/`; the min-v2
  Feb and Mar 2024 test80 binpacks, 6.9 + 7.9 GB zst, now downloading) and the training chain.
- 01:55 **C0 started** on GPU 0: our trainer, v3's recipe (8 buckets, 512 CReLU, lr 2e-3, 6
  epochs) on the 173 Lichess quiet chunks present (~85% of v3's data; the rest still uploading
  from the Mac at 30 Mbps), ~600k rows/s, ends ~02:45. **P1 pilot started** on GPU 1: the same
  recipe from scratch on the 45.9M own-labelled rows (trainer patched: `--rows-per-chunk` for
  the 200k shards, `shard_*.npz` accepted), ~8 min. Three sub-agents rewriting `node_gate.py`,
  `label_fleet.py` + `bulletformat.py`, `bullet_export.py` + the bullet trainer project.
- 02:15 Labelling restarted on the box's spare threads: `fen_producer.py` (elite odd plies →
  ids 1000+, the site's 6,594 games → 3000+, the Lichess evaluation database's positions →
  5000+) feeding `peer_label.py` with 64 workers at depth 7 (~30k positions/s expected).
- 02:00 `node_gate.py` delivered and accepted on the Mac (mirrored games at fixed nodes, exactly
  50% for identical nets; the node cap is checked every 1024 nodes so `--nodes 3000` stops at
  3072, deterministic). `bulletformat.py` + `label_fleet.py` delivered: the layout verified
  byte-for-byte against the Rust crate on 400 random positions; the Stockfish labels are
  reproducible with a fresh hash, and **warm-hash labels (no `ucinewgame` between positions)
  differ from fresh ones by up to ~400 cp on a few percent of positions**. Decision: the fleet
  stays warm-hash (4–5× the throughput; the same regime as the 45.9M rows already labelled;
  symmetric noise, no sign bias: 20 spot checks mean +24 cp). Never mix the two regimes.
- 02:10 Labeller workers were dying at startup ("stockfish exited") when 64 launched at once;
  patched with staggered starts and five retries; `label_keeper.sh` (via `keeper_ctl.sh`) tops
  the fleet back up to 64 every five minutes. Lesson re-learned twice tonight: an inline
  `pkill -f`/`pgrep -f` pattern matches the shell that carries it (one ssh command killed
  itself); kill patterns live in script files invoked by a short command.
- 02:20 **Stage 0 on the box**: determinism 16 games, pentanomial [0,0,8,0,0], exactly 50%
  (mirrored pairs). v3b vs v3 running at ~100 games/min at 30k nodes with 24 workers; v3b vs
  v2 and the P1-pilot verdict follow (`stage0.sh`). C0 at epoch 3 of 6 (ends ~02:45).
- 02:25 **Overnight chain armed** (`overnight2.sh`, results in `logs/overnight2.log`, grep
  RESULT): GPU 0: C0 → judge; P3 (512 CReLU, wdl 0.75 on the elite results) → judge; 04:30
  P2b (1024 SCReLU, 8 output buckets, wdl 0.75) → judge. GPU 1: 02:35 P1 (512 CReLU, all own
  labels present) → judge; 03:30 P2 (1024 SCReLU, 8 output buckets) → judge. Every judge is
  576 games at 30k nodes vs v3b through a lock. Labelling continues on 64 workers (~30k
  positions/s) from three producers: elite odd plies (46M), site games (0.6M), the Lichess
  evaluation database (all of it). Session paused for the account limit; resume ~08:30.
- 10:00 (Wed) **Overnight verdicts, all 576 games at 30k nodes, ±22–27:**
  | Run | Data | Net | vs v3b |
  |---|---|---|---|
  | Stage 0: v3b vs v3 | – | – | 53.5% (+24) |
  | Stage 0: v3b vs v2 | – | – | 57.8% (+55): the known order reproduced, instrument calibrated |
  | C0 (control) | Lichess quiet, 173 chunks, from scratch | 512 CReLU | **29.4% (−152)**: our trainer does not reproduce v3 from scratch on the Lichess mix |
  | P1 pilot | own labels, 46M | 512 CReLU | 47.0% (−21) |
  | **P1** | own labels, ~96M | 512 CReLU | **57.9% (+55 ±23)**: the first net to beat v3b, clear of zero |
  | P2 | own labels, ~100M | 1024 SCReLU, 8 output buckets | 56.2% (+43 ±24) |
  | P3 | own labels, 66M, wdl 0.75 | 512 CReLU | 29.8% (−149) |
  | P2b | own labels, 100M, wdl 0.75 | 1024 SCReLU | 28.3% (−162) |
  Reading: the thesis holds (one evaluator, in-distribution positions) and shows at 96M rows;
  C0's failure beside P1's success says the *data* broke every from-scratch run this week, not
  the trainer; **the result blend is dead** (two runs at −150); 1024 SCReLU is level with 512 at
  100M rows (needs volume); held-out MAE again does not order nets (P2 135 < P1 169).
- 10:00 Naming: Project Prometheus ships as **V6** (V6.0 today by 19:30, V6.0b tonight only if
  a bigger-data net clears the same ladder, V6.1 Thursday by 15:00 at ≥ +30). Plan additions
  agreed with Archit: the data loop (positions from our own arena games, labelled, retrained),
  input-side capacity (16 king buckets + factoriser: free at inference), the fixed-node SPSA of
  the search constants and the speed pass for V6.1, no result blend, no calibration/refit.
- 10:15 Labelling fleet found dead since ~05:00: 1,784 shards (357M positions) stuck in inflight;
  the keeper only topped up while the queue was non-empty. Requeued; keeper patched to requeue
  when no worker is alive. **But the relaunched Stockfish workers die at startup en masse
  (58 of 63; 2,295 failures logged overnight)** while 40–48 simultaneous launches from a shell
  succeed: under diagnosis with stderr captured. Producers finished: Lichess evaluation database
  363.7M positions, elite odd plies 45.5M. Labelled: 498 shards = 98.9M rows.
- 10:20 Timed ladder started for the two winners (generators paused via `pause_gen.sh`): P1 on
  box B, P2 on box A, 576 games at 5 s + 0.05 with the platform's clock formula and TT
  (`node_gate.py --tc`). Nets copied to `data/nnue_v6_p1.safetensors`, `nnue_v6_p2.safetensors`.
- 10:45 **Labeller die-off explained**: the Lichess evaluation database contains analysis-board
  fantasies (seven knights, eight queens) and Stockfish 19 exits with code 1 on them, taking the
  worker down (the V4 log met the same in July's scale fit). Fixes: a material-plausibility filter
  (≤ 8 pawns, ≤ 3 of each piece, ≤ 16 per side) and, because a few legal-looking positions still
  kill it, the worker now restarts Stockfish and skips the position instead of dying. Stockfish's
  stderr showed nothing; the failing FENs are logged.
- 10:50 **P1 at 5 s + 0.05 on box B, 520/576: 58.5% (+59 ±26)**: confirmed at the real speed;
  the 10 s confirmation (200 games) is chained behind it (`ladder_b.sh`), then the generators
  resume. P1's 40 real-clock proxies vs Stockfish 20k nodes run on the VM (generators paused;
  candidate dir `bini_v6_p1` = V5 engine + P1 net + book). P2's 5 s gate on box A restarted after
  a stale `bini_eval.py` there (the calibration import). bullet trainer built on the box (9 s);
  own labels being converted to bulletformat and shuffled for R1 (`r1_prep.sh`). Day chain armed
  (`daychain.sh`): 12:15 London run A (512 CReLU and 1024 SCReLU, both 16 king buckets +
  factoriser, on every label present), 14:15 run B; each judged vs v3b and vs P1 at 30k nodes.
- 11:15 Fleet stable after the two fixes: 63 workers alive, 587 shards (117M rows), 1,442 in
  the queue (~30k positions/s). **P1 at 5 s final: 58.3% (+58 ±24) over 576**; at 10 s 62.2%
  (+87 ±52) at 90/200. **P2 (1024 SCReLU) at 5 s: 46.4% (−25 ±29) at 420**: the wide net's
  speed cost exceeds its evaluation gain at the real clock; 1024 waits for the speed pass (V6.1).
  Proxies for P1 running on the VM (Stockfish had to be put on PATH there).
- 11:20 **Route A proven end to end**: bullet rebuilt with the CUDA feature (`--features cuda`,
  `CUDA_PATH=/usr/local/cuda`; the first build was the mock backend); the exported smoke net
  passes the exactness test on 3,958 positions; **R1 = bullet, 512 CReLU, 8 output buckets, 6
  superbatches × 100M on the shuffled own labels, trained in 52 s: 57.2% (+51 ±29) vs v3b at
  360/576**, the same gain as P1 from an independent trainer. bullet is ~20× faster than our
  trainer, so the data → net → verdict loop is now minutes. Variants running on GPU 1
  (`r1_variants.sh`): r1b (12 superbatches), r1e (1024 SCReLU, for Thursday).
- 11:21 **V6.0 candidate assembled**: `bini_v6a` = V5 engine (SEE pruning on, correction
  history off, calibration off, draw policy on) + P1 net + `data/book.json` (2,018 graded
  entries). Battery running on the Mac: init 22 s, wrapper state, NNUE exactness, perft and the
  5,000-position differential all green so far.
- 11:45 **R1 final: 60.2% (+72 ±23) vs v3b over 576 at 30k nodes**, the best net so far and
  from the independent trainer. P2's 5 s gate stopped at 500 (47.5%, −17 ±27; cannot reach the
  bar) and **R1's 5 s gate started on box A** (`gate_r1_a.sh`). P1 at 10 s: 64.2% (+101 ±46) at
  120/200; proxies running on the VM. Battery on `bini_v6a` (P1): mates 80/80, puzzles 40/40,
  blunders 12/12, continuing. r1b (12 superbatches) exported and judging; r1e (1024) next.
  Hand-over document written: `V6 HANDOVER.md` (state, machines, commands, the afternoon's
  order, Thursday, the traps). Fable session hands to Opus here.
- 12:05 Everything armed to run unattended (handover section 2b): scale-match + bullet sweep +
  retrain-as-labels-grow (`afternoon.sh`), Thursday's r1_final/r1e_final at 18:30 London
  (`thursday.sh`), today's arena games into the labelling queue (shards 4000+), R1's 10 s on box
  A and proxies on the VM chained behind the running gates, the Mac mirror at 18:35. Fleet: 728
  shards (146M rows), 62 workers. R1 at 5 s: 56.5% (+46 ±39) at 230. Battery on `bini_v6a`:
  torture 10/10 both ways, pressure running. Fable session ends here; Opus carries the day.
- 12:30 Variants: r1b (12 superbatches) +38, r1e (1024 SCReLU) +9 vs v3b: more epochs and
  width do not help at 100M rows; volume is the lever. The automatic scale step exported with
  an empty slope (r1s −458: invalid, ignored). Redone properly (`scale_match.sh`): **slope of
  v3b vs R1 static evals = 0.982, R1 is already on v3b's scale**; r1s2 vs r1 running as
  confirmation only. **Book merged**: `data/book_v6.json` = book.json ∪ the graded deep pass,
  6,105 entries, none over 15 cp; `bini_v6r` (R1) re-assembled with it. Today's arena games
  (863k positions) queued for labelling as shards 4000–4013 (the loop's first cycle).
  Handover section 3b (tonight's gains) and section 4 (the V6.1 final run: the bar, the recipe,
  the timeline to a Thursday 13:30 upload, 24/40 GPU hours) written.
- 12:50 Read of the ladder's top (leader vs #2: 155 moves, 3 cp/move each, drawn): the top eight
  are engine-grade, separate in the endgame, draw each other and never lose downward; a fresh
  strong build climbs within ~15 rounds. Acted on: an **endgame stream** (≤ 16 pieces; the whole
  Lichess evaluation database → shards 7000+, elite games after ply 30 → 9000+) added to the
  labelling queue for 2× weight in the final sets; three coding tasks written for Opus (handover
  3c): 4-man Syzygy WDL probing at the root in the wrapper, an endgame-holding slice in every
  timed gate, endgame weighting in the bullet prep. Each gated alone; the net untouched.
- 13:05 Directive: V6.0 tonight is the generational-leap build; the GPU box pauses for a couple of
  hours after it. Handover section 0 written (export before the pause, mirror with labels, the
  ladder continues on the CPU boxes, `resume.sh` after). Sweep results: r1c (lr 0.002) +8, r1d
  (24 sb) +53, r1s2 (scale 0.982) +5 vs r1 → recipe fixed at lr 0.001, 6 sb/100M; scale a
  non-issue. `r1_prep.sh` now weights the endgame shards 2×. Labelled 1,698 shards (~340M).
  **Fable session ends; handover final at 13:05.**
- Next entries (Opus): the 14:00/16:00/18:00 retrains vs r1; R1 5 s/10 s/proxies; P1 10 s/
  proxies; run A/B; tasks A–C; V6.0 ~17:00; V6.0b ~21:00 if cleared; pause; resume.
- 22:25 **Coordination note from the V5.0 session (Claude, session 44031d80).** Two Claude
  sessions work this repo tonight. Split, effective now: the Prometheus session owns the A100,
  every training route (A/B/C/L), the fleet labeller and the fixed-node arenas; the V5.0
  session owns the safe build to hand-over. What the V5.0 session holds and when it releases:
  box A until ~00:30 (V5.0's 400-game gate vs V3's engine, running since 21:50, then the
  calibration table's second 200); box B until the pressure draw gate ends (~23:30; two cores,
  generators running); the VM until the Stockfish-2000 draw-rate gate ends (~23:30). After that
  the V5.0 session needs only: the Mac for the Wednesday battery, box A for V5.0's 40 real-clock
  proxies (~3 h, Wednesday morning) and its 1,000-game regression Wednesday afternoon. Neither
  session touches the other's queues or candidates; results go into this log. Net-side verdicts
  at 200 games vs v3b tonight: calibration table 52.8% (+19 ±49, extending to 400), refit
  50.7%, D3 48.2%, D 44.0%, A 35.5%; SF-2000 draw-rate check with the rule on: 98% at 49/100,
  two draws.
- 22:40 (V5.0 session) Draw policy, part (b): vs Stockfish UCI_Elo 2000, 100 games at 10 s each
  way: rule on 98.5% (3 threefold), rule off 98.0% (3 threefold, 1 fifty-move). **The rule does
  not raise the draw rate against weaker opponents.** Part (a) (full strength, real clock) at
  7/10 games each side on box B. V5.0 vs V3's engine 55.7% (+40 ±52) at 176/400. The VM now runs
  V5.0's 300-game 10 s confirmation (until ~01:00), then is released.
- 12:05 (Opus session) **Situation at noon London.** R1 5 s final: **57.4% (+52 ±24) over 576**;
  R1 10 s: **62.3% (+87 ±41) over 200** (box A, `ladder_a.log`). P1 10 s: **60.0% (+70 ±35) over
  200** (box B, `ladder_b.log`). P1 proxies (VM, 40 games): **40.0% (42.5% + 37.5%)** — below
  the v3b reference of 46%. R1 proxies running on the VM (10/20 + 8/20 done, ~34–38% so far).
  afternoon.sh: r1s2 vs r1 +5 ±20 (scale 0.982, R1 on v3b's scale — confirmed); r1c +8, r1d +53
  (neither beats R1). Day chain run A training on both GPUs (512 CReLU with 16 king buckets on
  GPU 0, 1024 SCReLU on GPU 1, both on 1,134 shards = ~227M rows). Labelling fleet: 1,579 shards
  (~316M rows), 62 workers, stable. Generators resumed on box A, box B. Battery started on
  `bini_v6r` (R1 + 6,105-entry book) on the Mac.
- 14:10 (Opus session) **V6.0 battery complete, all green.** Full results:
  init 22–23.8 s, book 6,105 | wrapper/NNUE/perft/diff: ok | mates 80/80, tactics 10/11 |
  puzzles 40/40 | blunders 11/12 | harvest 28/37 | torture 20/20 | **pressure 10 games vs
  SF@1.5M: 7 draws 3 losses, min clock 6.5 s (>5 s), median unclear 1.45 s ≥ decided 1.44 s.**
  `package.sh` ok: 10 files, 7,728,861 bytes unzipped (3.7 MB zip). Byte-check: all files
  identical. Fresh-extraction game: 40 plies, all legal, book firing, NNUE on, compile 21.7 s.
  **MD5 `3133e32644bbdc24c156f9dacea5f91e`.** Day-chain verdicts: a512 +63, a1024 +95
  (excluded — 1024), r1c +8, r1d +53, r1e +9 — none displaces R1 (+72). Labelling fleet:
  2,077 shards (~415M rows). **V6.0 decision: ship R1.**
  Handover: net R1, four numbers +72/+52/+87/37.5%, compile ~22 s, `submission.zip`
  3,687,181 bytes, md5 `3133e32644bbdc24c156f9dacea5f91e`. Changes vs live build: new NNUE net
  (R1, from-scratch on SF19 d7 labels ~200M rows), new book (6,105 entries, 3× size), engine
  frozen (no code changes).
- 14:50 (Opus session, V6.5) **V6.5 opened: engine work, not just the net.** V6.0 landed five
  hours early, so the freed window went to the two levers with zero hours on them all week.
  1. **Speed pass — shipped.** `bini_v65/bini_nnue.py`: accumulators are int16 when the net's own
     weight bound allows it (`ACC_BOUND = max|b1| + 32*max|w1|`, a generous bound; int32 otherwise,
     and `BINI_ACC32=1` forces int32 so the change can be A/B'd in a *timed* gate — a fixed-node
     gate equalises nodes and cannot see a speed change at all). Bounds measured: v3b 27,108,
     r1 11,238, r1_1303 14,201 (all int16); **a1024 55,826 — does not fit, falls back to int32.**
     Clean A/B on the Mac, r1_1303, depth 12, 3 runs each: **684 → 731 knps, +6.9%**, node counts
     bit-identical on all 12 positions, `test_nnue.py` exact on both paths.
  2. **Two hypotheses killed by measurement.** The eval inner loop cannot be vectorised in numba:
     blocking into int32 lanes = 592 ns per 512-wide pass, numpy array expressions = 1,936 ns,
     versus **462 ns for the plain flat loop** (`/tmp/loopvar2.py`). Comment left in the source so
     nobody re-does it. `nnue_copy` is only 43 ns/call net of dispatch, so lazy accumulators are
     not worth the risk. **Eval is 641 ns of a ~1,430 ns node** — dominant, and immovable in numba.
  3. **1024 is an architecture wall, quantified.** a1024 runs at **317 knps vs 512's 697** (2.2x).
     That is why P2 went +43 at fixed nodes to −17 at 5 s. 1024 does not ship until the eval gets
     out of numba; it is not a tuning problem.
  4. **Search constants are tunable for the first time.** Eight knobs added to `bini_search.py`
     (`BINI_LMR_BASE/LMR_DIV/RFP/NMP/NMPD/FUT/LMP/SEE_Q/SEE_C`), defaults byte-identical to V6.0's
     frozen search so an untuned build is unchanged. Verified live: RFP=150 moves node counts +30%,
     LMR_DIV=1.8 −19%.
  **Verdicts (576 games at 30k nodes).** Net: r1_1303 (12 sb on 490M rows) **+87 vs v3b, +38 vs R1**;
  s24 (24 sb) +13 vs r1_1303; **s48 (48 sb) +44 ±23 vs r1_1303** — the epoch budget, not width, is
  the lever, and `afternoon.sh`'s hardcoded 12 superbatches has been under-training every retrain
  today. s96/s144 launched to find the turnover. Search: **LMR_DIV 2.0 = +19 ±20, LMR_DIV 2.5 =
  −13 ±21** — this search wants *deeper* late-move reduction; 1.8/1.6 and the base term probing.
  **Corrections to my own earlier calls, both from acting on one data point:** I called the
  superbatch lever dead on s24 (+13) alone — s48 (+44) says otherwise. Discipline: two points on a
  monotonic axis before a verdict.
  **Infra:** box B (`gcp-x86b`) unreachable since ~13:35 (SSH timeout) — one of two timed-gate
  boxes lost. Labelling keeper stopped and its 64 workers SIGSTOPped at 13:47 (load was 88.6 of a
  92-CPU quota and gates were starving); 2,868 shards (~575M rows) banked, resume with
  `keeper_ctl.sh start 64 7` + `bini_v65/tools/pause_gen.sh resume`.
- 15:03 (Opus session, V6.5) **The 1024 line is closed for tonight, on measurement not estimate.**
  k24 (1024 SCReLU, 24 sb, 490M rows) is **+92 ±22 vs r1_1303** at fixed nodes — the best net of the
  day — but head to head against s48 it is only **+28 ±22**, and it runs at **307 knps vs s48's 731**
  (2.38x; k24 does fit int16, bound 16,329, so that is the *optimised* figure). Calibration for what
  that costs comes from our own data: P2, also 1024-wide, went **+43 at fixed nodes to −17 at 5 s**,
  a −60 swing. Applying it, k24 lands near −32 on the clock. The queued 45-minute timed gate on box A
  was cancelled rather than spend it confirming a conclusion the numbers already force.
  **Method note this vindicates:** a fixed-node gate is structurally blind to speed. Every 1024
  verdict this week (+95 a1024, +92 k24, +9 r1e) was measured on an instrument that cannot see the
  one thing that disqualifies the architecture. Fixed nodes ranks evaluators; only the clock ranks
  engines.
  **LMR is a plateau, not a peak.** DIV 1.4 = +25, 1.6 = +31, 1.8 = +13, 2.0 = +19, 2.25 (shipped
  default) = 0, 2.5 = −13; DIV 1.8 + BASE 1.0 = +25. Six parameterisations that increase reduction,
  all positive; the two that decrease it, both negative. The band 1.4–2.0 is not separable at 576
  games (±20) and I over-read a "clean unimodal peak at 2.0" off four points before 1.6 landed at
  +31 and broke it — the same read-structure-into-noise error this document's section 2 was written
  about. What is real is the direction and the magnitude, ~+20–25; a 1728-game confirmation
  (interval ~±11) fixes the shipping value. RFP settled: 55 = −15, 100 = −24, default 75 optimal.
  NMP=2 neutral (−0 ±20).
- 15:20 (Opus session, V6.5) **V6.5 feature-locked: s48 net + LMR_DIV 1.6 + int16 accumulators +
  the 6,105-entry book.** Components, each measured alone before the combination gate:
  | change | evidence | Elo |
  |---|---|---|
  | LMR_DIV 2.25 -> 1.6 | **1728 games**, fixed nodes | **+31 ±11** |
  | r1_1303 net + int16 vs V6.0 as uploaded | 576 games, **5 s** | **+57 ±23** |
  | s48 over r1_1303 | 576 games, fixed nodes | +44 ±23 |
  | int16 accumulators | direct bench, node-identical | +6.9% nps |
  | combination (ship gate) | 5 s, provisional at 180/576 | +143 ±45 |
  **Superbatch curve closed** (vs r1_1303 = 12 sb): 24 sb +13, 48 sb +44, 96 sb ~+59 (s96 vs s48
  = +15 ±21). Still climbing but the marginal return collapsed; s48 is the knee. **s96 did not
  ship: the rule "replace s48 only at >= +25" was set BEFORE the verdict**, and +15 ±21 does not
  clear its own interval -- taking it would have cost 90 minutes and a fresh set of unvalidated
  bytes for a gain indistinguishable from noise. s96 is Thursday's starting point instead.
  **Search sweep, final:** LMR_DIV was the *only* real mistuning. RFP (55 = -15, 100 = -24),
  NMP (2 = -0, 4 = -5) and FUT (75 = +5, 130 = -1) are all already optimal at their shipped
  defaults; LMR_BASE 0.5 = -8 (wrong way), 1.0 = +25 (same direction as a lower DIV). Seven of
  seven "more reduction" parameterisations positive, two of two "less reduction" negative.
  **Static suites, corrected read:** blunder 10/12 (V6.0: 11/12), puzzles 39/40 (40/40), tactics
  9/11 (10/11) -- but **harvest 29/37 (28/37), the other way, and it is the largest of these sets**.
  I first called three-sets-down a real tactical cost from the LMR retune; harvest landing up says
  that was over-read on small samples. Call the static suites neutral overall; the evidence that
  counts is 576 games on the clock. 1.6 was still chosen as the *centre* of the 1.2-2.0 plateau
  rather than its edge, because aggressive LMR trading tactics for depth remains the plausible
  failure mode even if this battery does not show it.
- 15:30 (Opus session, V6.5) **SHIP GATE FINAL: V6.5 is +118 ±23 over V6.0 at 5 s, 576 games**
  (`gates/v65_ship_tc5.log`, box A, generators paused): +280 =205 -91, score 66.4%, pentanomial
  [6, 35, 80, 98, 69]. A = s48 + LMR_DIV 1.6 + int16; B = V6.0 exactly as uploaded (r1 + stock
  constants + int32). Interval clear of zero by five sigma. The components predicted this: +57
  (net r1_1303 + int16, measured at 5 s) plus +31 (LMR, 1728 games) plus s48's +44 over r1_1303
  at fixed nodes, landing at +118 rather than the naive sum -- the usual mild overlap, not
  cancellation. **The combination gate was worth running: additivity was the real open question.**
  Search sweep complete, and the finding is narrow and clean: **LMR_DIV was the only mistuned
  constant of eight.** RFP (55/-15, 100/-24), NMP (2/-0, 4/-5), FUT (75/+5, 130/-1), LMP (70/+8,
  140/-17), SEE_Q (40/-16) are all optimal at their shipped defaults. A well-built search with one
  bad number in it -- which is why six days of net work never found it, and why an hour of A/B did.
  **Net sweep complete.** vs r1_1303 at fixed nodes: s24 +13, s48 +44, s96 ~+59, k24 +92, k48 +86.
  **The two best evaluators we trained today (k24, k48, both 1024-wide) are both unshippable at
  307 knps.** That is the V7 headline: we can already train a net ~+90 better than what ships and
  cannot afford to run it. The bottleneck has moved off data and onto inference speed, which is a
  numba problem, not a chess problem.
  **Thursday's blocker found and fixed in advance:** the Lichess evaluation database is fully
  consumed (FEN queue hit 0 at 2,868 shards). Restarted the keeper at 48 workers and launched the
  data loop (`v65_dataloop.sh`) over today's 146 MB / 48 arena PGNs at start-id 20000 -- ~12-15M
  positions our own engine actually played, i.e. in-distribution. Further growth needs either more
  arena games or a new external corpus.
- 15:42 (Opus session, V6.5) **The stale-baseline effect, caught and measured.** SEE_Q=90 scored
  **+20 ±20** in the sweep (baselined on r1_1303 + stock constants) and **+4 ±11 over 1728 games**
  when re-measured on the SHIPPED config (s48 + LMR_DIV 1.6). It is worth nothing. Mechanism:
  LMR and SEE pruning cull the same late quiet moves, so once LMR reduces more aggressively there
  is nothing left for a wider SEE margin to win -- SEE_Q=120 on the shipped config confirmed it
  from the other side at **-21**. Had this been rushed into V6.5 it would have cost two hours of
  re-gating and re-battery for +4, and put a fourth unvalidated change into a locked build.
  **Rule for every future sweep: tune against the current best, never against a fixed historical
  baseline.** Otherwise changes that each looked good in isolation are stacked and interact. Only
  the LMR find was large enough (+31) to survive being measured the wrong way; everything in the
  ±20 band from the first sweep is unreliable until re-measured.
  **Final search verdict: LMR_DIV was the only real mistuning of the eight.** RFP, NMP, FUT, LMP
  and SEE_Q are all optimal at their shipped defaults; LMR_BASE 1.0 (+29 alone on the old
  baseline) is a *substitute* for a lower DIV rather than an addition -- DIV 1.8 + BASE 1.0
  together scored +25, below DIV 1.6 alone at +31 -- and **measured at +2 ±14 over 1152 games
  on top of the shipped DIV 1.6** -- confirmed a substitute, worth nothing once DIV is fixed.
  **The search is closed.** Both Thursday probes returned null against the shipped config
  (SEE_Q 90: +4 ±11; LMR_BASE 1.0: +2 ±14). One bad number out of eight, found in an hour of A/B
  after six days of net work never looked at it, and no cheap search Elo remains.
  **Consequence for Thursday: spend zero time on search constants.** The ranked levers are now
  (1) inference speed -- k24/k48 are +92/+86 and unshippable only because of 307 knps, so getting
  the eval out of numba is worth the largest single number on the board; (2) s96 + the data loop,
  real but clearly flattening; (3) everything else, small.
- 16:10 (Opus session, V6.5) **V6.5 PACKAGED AND HANDED OVER.** `bini_v65_ship/submission.zip`,
  3,804,853 bytes, 10 files, 7,731,943 unzipped, **md5 `6dd0c7181772e850f1a48cd8628a512f`**.
  **Headline: +118 ±23 over V6.0 at 5 s + 0.05 over 576 games** (+280 =205 -91, 66.4%,
  pentanomial [6, 35, 80, 98, 69]; box A, generators paused) -- measured against the build
  uploaded at 14:13 today, not a historical baseline.
  Contents: net **s48** (512 CReLU, 8 output buckets, bullet, 48 superbatches on 490M own SF19
  depth-7 labels); **LMR_DIV 1.6** baked as the default in `bini_search.py`; **int16 accumulators**
  auto-selected per net in `bini_nnue.py`; book 6,105 entries; engine core otherwise the frozen
  V6.0 code.
  Battery all green on the exact bytes: init 22.3 s (cold import from the unzipped submission
  23.2 s), wrapper/exactness/perft/differential ok, mates 80/80, tactics 9/11, puzzles 39/40,
  blunders 10/12, harvest 29/37, torture 20/20, **pressure 7 draws 3 losses, min clock 8.0 s
  (V6.0: 6.5 s), median unclear 2.20 s >= decided 0.83 s**. Byte-check: all 10 files identical to
  their originals. Fresh-extraction game from the unzipped tree: 19 plies, every move legal, 1-0.
  **Ladder completion in flight** (V6.0 shipped with four numbers; V6.5 must not ship with two):
  200 games at 10 s on box A (`v65_tc10.sh`) and 20 proxies on the VM run from `bini_v65_ship`
  itself (`v65_proxy.sh`) so the baked constants are what is tested. V6.0 proxy reference 37.5%,
  v3b 46%.
  **Rollback = V6.0** (`3133e32644bbdc24c156f9dacea5f91e`), live since 14:13.
  **Thursday inherits, pre-validated:** t48/t96 training on the 712M-row shuffle and judged
  against s48 on LMR 1.6; s96 (+15 over s48, needs ladder time only); the data loop refilling a
  FEN queue that hit zero. Note r1_1502 (12 sb on 712M) = +92 vs v3b against r1_1303's +87 on
  490M -- **45% more data bought +5 at 12 superbatches**, confirming the epoch budget and not the
  volume was today's binding constraint. **Box B (`gcp-x86b`) still unreachable since ~13:35.**
  **GPU credit still ends ~19:20 without a top-up; everything above dies with it.**
- 16:30 (Opus session, V6.5) **10 s gate: +131 ±41 over 200 games** (+97 =78 -25, 68.0%,
  pentanomial [2, 10, 30, 30, 28]; box A, generators paused) -- V6.5 vs V6.0 as uploaded.
  **The gain grows with time control: +118 ±23 at 5 s, +131 ±41 at 10 s.** This is the result that
  most needed checking. The one real risk in this build was that a more aggressive LMR buys depth
  by pruning something it should not, which would show up as the edge eroding once both sides get
  more clock. It does the opposite, so the retune is sound rather than a fixed-depth artifact.
  Ladder now 3 of 4: fixed nodes (s48 ~+82 over V6.0's net, derived), 5 s +118 ±23 over 576,
  10 s +131 ±41 over 200. Proxies running on the VM.
  **Tooling bug found, worth fixing before it bites again:** `tools/proxy_match.py` accepts
  `--stockfish` but `tests/uci_sf.py` hardcodes `subprocess.Popen(["stockfish"])`, so the flag is
  dead and the binary must be on PATH. Cost two failed proxy attempts. Workaround in
  `~/chess/v65_proxy3.sh` on the VM (`export PATH=/home/ubuntu/chess/Stockfish/src:$PATH`).
  **Epoch budget, third independent confirmation:** r1_1502 (12 sb on **712M** rows) = +63 over
  V6.0's net; s48 (48 sb on **490M** rows) = +82. Less data, four times the passes, better net.
- 16:40 (Opus session, V6.5) **The data lever is exhausted; the lever is training compute.**
  t48 (48 sb on **712M** rows) vs s48 (48 sb on **490M** rows) = **+2 ±22**. At a fixed budget of
  4.8B positions seen it makes no measurable difference whether they come from 490M or 712M unique
  rows. Put beside the rest of the day (all vs V6.0's net r1): 12 sb / 490M = +38, 12 sb / 712M =
  +63, 48 sb / 490M = **+82**, 48 sb / 712M = +82.
  **Read across that table: superbatches move the net, unique rows barely do.** This contradicts
  the premise the whole week was built on -- "volume is the lever", from 46M -> -21, 96M -> +55/+72,
  227M -> +63/+95. That scaling was real up to ~100-200M rows and is flat by 500M. We spent the
  week buying data we did not need and under-training on it: the fleet labelled ~600M rows while
  every retrain ran 12 superbatches.
  **Consequences, in order.** (1) Stop labelling for volume; ~500M rows is already past sufficient.
  (2) Thursday's training budget goes to superbatches (t96 running; s96 was +15 over s48 at 490M),
  not to more data. (3) The GPU box is wanted for *training compute and the fixed-node judge*, not
  for the labelling fleet -- which changes what a top-up buys. (4) V7's ranked levers stand
  unchanged and are now better justified: inference speed first (k24/k48 are +92/+86 and
  unshippable only at 307 knps), training compute second, data last.
  **Correction to my own earlier note:** I read "0 .fen files" as the data loop having failed. It
  had not -- the keeper had consumed the queue. Labelled shards went 2,868 -> 2,980 with 49 in the
  `shard_02*` (arena) range, so the loop works end to end and is available whenever in-distribution
  data is actually wanted.
- 16:50 (Opus session, V6.5) **BOTH LEVERS EXHAUSTED FOR THE 512 NET. This is V7's brief.**
  Superbatch curve, 512 CReLU, vs the 12-sb baseline: 24 = +13, 48 = **+44**, 96 = **+59**,
  144 = **+57** (s144 vs s96 = -2 ±20). Data curve at fixed compute: t48 (712M) vs s48 (490M) =
  **+2 ±22**; t96 (712M) vs s48 = +18, s96 (490M) vs s48 = +15 -- the extra 222M rows contribute
  nothing at either budget.
  **So: more data does nothing, more epochs past ~96 superbatches does nothing.** The 512-wide net
  is at its capacity ceiling. Every lever this project pulled for six days is now measurably
  finished, and the finish line is well short of the top of the ladder.
  **What is left is width, and width is blocked by speed alone.** k24 (1024, 24 sb) = +92 and k48 =
  +86 at fixed nodes -- far beyond anything 512 can reach -- and both are unshippable only because
  they run at **307 knps against 512's 731**. They are better evaluators we cannot afford to run.
  **V7 is therefore an inference-speed project, not a chess project, and this is now arithmetic
  rather than judgement.** Budget: eval is **641 ns of a ~1,430 ns node** (measured, net of numba
  dispatch); `nnue_copy` is 43 ns so lazy accumulators are not the answer; numba emits scalar code
  for the eval reduction in every formulation tried (flat 462 ns < blocked int32 592 ns < numpy
  array expressions 1,936 ns per 512-wide pass). int16 accumulators bought +6.9% and that is what
  numba had left. Getting 1024 to parity needs roughly 2.4x on the eval, which means SIMD, which
  means leaving numba for the forward pass -- the platform bans shipped native binaries, so the
  route is whatever vectorises inside the 90 s init budget from source.
  **Thursday, concretely:** t96 is the best 512 net (+18 over s48, ~+100 over V6.0's net) and is
  Thursday's candidate; it did NOT go into V6.5 because +18 ±21 is below the >= +25 rule set before
  s96 was seen, and applying that rule only to other people's nets would defeat it. Do not spend
  Thursday on more data, more epochs, or more search constants -- all three are measured out.
- 17:10 (Opus session, V6.5) **LADDER COMPLETE, 4 of 4 — and the proxy resolves the week's
  instrument doubt.** Proxy: **52.5%** (+4 =13 -3 over 20 games, min end clock 7.3 s, median 11.5 s),
  against **V6.0's 37.5%** and v3b's 46%. This is the only test against a FOREIGN opponent rather
  than our own previous net, it runs at **120 s + 0.5 s -- the platform's exact time control**, and
  all week it had contradicted the gates (P1 and R1 both scored below v3b on it while measuring
  +55 and +72 in self-play). It now agrees emphatically. 20 games is a wide interval on its own;
  what makes it meaningful is that it points the same way as 776 timed games.
  **V6.5 final four numbers vs V6.0:** fixed nodes ~+82 (net alone, derived) | **5 s +118 ±23**
  (576) | **10 s +131 ±41** (200) | **proxy 52.5%** (20). Note the V6.1 "top-five material" bar in
  section 4 asked for proxies >= 55%; 52.5% is close but short of it.
  **V6.0 in the wild, 2 games, both won by checkmate:** R83 vs OMI (Black, 88 moves, 17.6 s left,
  init 35.8 s) and R84 vs zak (White, 104 moves, 14.2 s left, init 38.1 s) -- zak had beaten us at
  R68. Both were long endgame conversions rather than tactical wins, which is the profile the top
  eight have. Rating 2396 -> **peak 2495 at R84**, provisional on fewer than six games.
  **Platform init is 35.8-38.1 s, not the 22 s we measure on the Mac** (~1.7x slower box), i.e.
  40-42% of the 90 s budget. V6.5 compiles in the same 22 s locally so it lands in the same place.
  **Correction to my 16:50 entry: "the 1024 line is closed" was measured at the wrong speed.** The
  2.4x node deficit is fixed, but Elo-per-doubling shrinks with depth, and the platform runs at
  depth 18-21 on ~2M nodes per move -- far deeper than the 5 s gates that condemned it. Re-doing the
  arithmetic at platform depth puts k24 near -28 rather than -59: still negative, so 512 remains
  right for V6.5, but "closed" overstated it. It deserves one gate at 120 s + 0.5 s before Thursday
  discards it, and that is a reason to keep the GPU box alive.
- 18:55 (Opus session, V7) **V7 CORE CONFIRMED: correction history + continuation history = +40 ±11
  over 1728 games** (55.7%, +513 =900 -315), measured on the shipped V6.5 config (s48 + LMR 1.6),
  every switch explicit. Two env flags. No new code, no new net.
  **How it was missed for a week.** Both features were already implemented and SHIPPED DISABLED.
  They were screened on 40-game gates at **-10 and -11 with ±60-70 error bars** -- six times larger
  than the effect. And they are **superadditive**: corrhist alone +19, conthist alone +5, together
  **+40**. Conthist sharpens move ordering, which makes corrhists error estimates more reliable.
  One-at-a-time screening on a noisy gate could not have found this even in principle.
  **The other three disabled features were rightly off**: probcut -8 ±19, qs_checks -10 ±21,
  improving -7 ±19. So the old screening was not wrong about them -- the failure was specific.
  **Also found: V6.5s constants were tuned in the wrong configuration.** Every gate today ran from
  the dev tree, whose defaults are CORR=1/CONT=1, while both zips bake them to 0. Both sides shared
  it so every comparison stands, but LMR 1.6 and the rest were optimised for a config the shipped
  zip is not in. Turning the two features on does not merely add +40 -- it puts the engine back in
  the configuration its constants were tuned for.
  **Route A closed honestly:** kb16 at 48 sb = -13, at 96 sb = +14, versus 8 buckets at 96 sb = +15.
  King buckets are neutral; the apparent bucket effect was entirely the training budget. The 48 sb
  result was a confound (2x parameters at a budget tuned for 1x), not a true negative.
  **Route C closed conclusively:** seven eval implementations measured IN SITU -- blocked int32,
  numpy array expressions, fused float32 (821 ns), split float32 + caller buffer (903 ns), split +
  local alloc (-9.5% nps), slice-hoisted indexing (711 ns) -- all slower than the shipped scalar
  integer loop (702 ns). numba will not emit SIMD for this shape and Info.md line 40 confirms the
  image carries no compiler, so hand-written vectorisation is impossible. **A hot-cache
  microbenchmark said float was 3.9x FASTER; it is 17-29% slower in the engine.** Its integer
  baseline (917 ns) was 43% slower than the real one. Never trust a synthetic loop for this again.
- 20:05 (Opus session, V7) **V7k CONFIRMED: +39 ±21 over V6.5 at 30 s + 0.125, 400 games**
  (55.6%, +98 =249 -53). Ships as: **k96** (1024 wide, SCReLU, 96 superbatches on 712M own SF19
  depth-7 labels) + **correction history** + **continuation history** + LMR_DIV 1.6 + int16
  accumulators + the 6,105-entry book. That is **~+164 over V6.0** in one day.
  **Components and their overlap:** corrhist+conthist +24 ±19 timed; k96 over s48 +23 ±18 @30 s and
  +23 ±22 @60 s (replicated at two clocks). Naive sum +47; end to end **+39** -- partial overlap, as
  predicted, because correction history has less to correct once the evaluator is better. **The
  combination gate was worth running.**
  **The 1024 net was rejected three times this week (a1024, k24, k48) and every rejection was
  measured on an instrument that could not see the relevant property.** Fixed-node gates equalise
  the speed penalty out of existence; a 5 s gate exaggerates it ~16x versus the platform clock.
  It also needed the epoch discovery from the same afternoon: k24 at 24 sb was +28 over s48, k96 at
  96 sb is +68. Neither finding alone would have produced V7k.
  **Static suites, V7k vs V7-s48:** blunders 11/12 vs 12/12, harvest 29/37 vs 30/37, puzzles 40/40
  both, mates 80/80 both. The wider net is very slightly worse on the static sets and clearly better
  in games -- another reminder that the suites rank differently from the clock.
  **Calibration remains the best open thread and is deferred deliberately**, not abandoned: the
  v3b-fitted table scores -31 on the current net, which proves the mechanism has grip. A refit
  (`tools/calib_table.py` on `data/site_all` + `data/site_labelled`) is Thursday's first job. It
  targets the one flaw the real games expose -- R86 read +164 in a drawn position, R87 read -313 in
  one it saved: position-dependent bias, not a constant offset.
  **Width frontier opened (funded by the credit top-up):** 1536 and 2048 at 96 sb training now,
  to be judged at 30 s + 0.125 against k96. Zip budget: 1536 -> 18.9 MB, 2048 -> 25.2 MB of the
  50 MB unzipped limit. **We have tested exactly two points (512, 1024) on a curve we only
  discovered was mismeasured six hours ago.**

- 01:40 (Opus session, V8 night) **AUTOPSY: the recipe sweep is one knob, not three, and it is
  already near its optimum.** Twelve nets trained tonight to sweep the k96 training recipe. Read as
  independent levers the results look contradictory; read as a single effective step size they are
  coherent. Baseline k96 is lr 0.001 at batch 16384. Write r for the ratio lr/batch relative to that
  baseline -- the SGD noise scale, the quantity that actually governs where the optimiser lands:

  | net | lr | batch | r | result vs k96 |
  |---|---|---|---|---|
  | hp_lr05 | 0.0005 | 16384 | 1/2 | **+10 ±14** |
  | hp_bs32 | 0.001 | 32768 | 1/2 | **+8 ±15** |
  | hp_combo | 0.0005 | 32768 | 1/4 | **-6 ±12** |
  | hp_lr025 | 0.00025 | 16384 | 1/4 | **-21 ±12** |
  | hp_lr01 | 0.0001 | 16384 | 1/10 | **-55 ±12** |
  | hp_lr15 | 0.0015 | 16384 | 3/2 | **-16 ±14** |

  **Halving the noise scale by either route gives the same answer (+10, +8). Quartering it by
  either route is negative (-6, -21). The two levers we thought we had stacked were the same lever
  pulled twice, and the second pull went past the peak.** The peak sits at r = 1/2 and is worth
  about +9; there is nothing further on this axis. hp_combo did not fail, it landed exactly where
  the curve says it should -- our error was in expecting +10 and +8 to add to +18.

  **What could have been done better:** the batch sweep and the lr sweep should never have been run
  as separate one-dimensional experiments. Both move the same underlying quantity, so the second
  sweep bought almost no new information for six nets of GPU time -- it re-measured the first curve
  in different units. Sweeping *r* directly (four points, four nets) would have produced the same
  conclusion for a third of the compute, and would have made the non-additivity obvious in advance
  rather than as a surprise. The general form of the mistake: **before sweeping two hyperparameters
  separately, ask whether the model is actually sensitive to them separately or only to a
  combination of them.** Learning rate and batch size are the textbook case of the latter.

  **Prediction recorded before the result lands (hp_combo2, lr 0.00025 at batch 32768, r = 1/8, is
  gating now): if the one-knob model is right it must land between -25 and -50**, bracketed by
  hp_lr025 at r = 1/4 (-21) and hp_lr01 at r = 1/10 (-55). Near zero or positive falsifies the model
  and means lr and batch are genuinely separate axes after all. The model is approximate, not exact:
  the two r = 1/4 points differ by 15 Elo (-6 vs -21), about 1 sigma, which is the signature of the
  real second-order effect -- a larger batch also reduces gradient variance, which is not the same
  as lowering the learning rate.

  **Consequence for V8.** The recipe axis is closed at r = 1/2 (lr 0.0005 at batch 16384, cosine),
  worth ~+9, and every remaining candidate is trained there. **The open axis is the data**: what the
  net learns from, not how it learns. Tonight the depth-10 teacher gave +18 and +25 on fine-tunes
  where the entire recipe sweep gave +10 at best, from a tenth of the compute. That is the seam.

- 02:00 (Opus session, V8 night) **AUTOPSY: the fine-tune has one knob too, it is lr x superbatches,
  and round 2 walked it past the peak. The same mistake as the recipe sweep, made twenty minutes
  after writing that lesson down.** Every depth-10 fine-tune, ordered by total update size:

  | arm | lr | sb past k96-96 | lr x sb | rows | result vs k96 |
  |---|---|---|---|---|---|
  | ft_lo | 0.0002 | 2 | 0.0004 | 18M | **+18 ±13** |
  | ft_mid | 0.0005 | 3 | 0.0015 | 18M | **+25 ±14** |
  | ft_mix | 0.0005 | 4 | 0.0020 | 18M + old | **+11 ±14** |
  | ft2_a | 0.0005 | 4 | 0.0020 | 41M | **-1 ±11** |
  | ft_hi | 0.001 | 4 | 0.0040 | 18M | **-0 ±13** |

  **A narrow peak near 0.0015 with a fast collapse above 0.0020.** The mechanism is ordinary
  catastrophic forgetting: k96 carries 712M depth-7 positions, the fine-tune pulls it toward a
  different label distribution, and two to three superbatches move it enough to gain while four
  overwrite more than they add. Round 2 was designed as "fix lr, vary training length" on the
  explicit belief that those were separate axes -- they multiply, so it walked the same knob from
  0.0015 to 0.0020 and 0.0040. **ft2_a at -1 is not evidence that more data hurts; it is the
  0.0020 point of this curve, measured on 41M rows instead of 18M and landing where ft_mix already
  landed.** Data volume is not implicated at all.

  **The uncomfortable part.** ft_mid at +25 is the best number of the night, it is a single
  unreplicated point, and its two nearest neighbours on the knob are -1 and +11. The project rule is
  two points before a lever is called dead -- s24 taught that at a cost of the day's biggest gain --
  and the rule is exactly as binding for calling a lever ALIVE. On one point I cannot distinguish a
  real peak at 0.0015 from a +1.8 sigma excursion on a curve that is flat-to-negative everywhere
  else. Treating +25 as V8's headline without replication would be the same error as before with the
  sign reversed.

  **What could have been done better:** round 2 should have replicated ft_mid before extending past
  it. Extending a curve is only worth compute once you believe the point you are extending from.
  Two of the four fine-tune slots tonight went to arms above the peak, which the knob model would
  have flagged as dead before they were trained.

  **Running now (v8_ftgrid.sh), the replication and the bracket, all on 41M rows:**
  fa_rep = the exact ft_mid recipe (0.0005 x 3) -- replication and the clean data-volume test at the
  peak in one arm; fa_a (0.00075 x 2) and fa_b (0.00025 x 6) -- total update held at 0.0015 and split
  differently, which must land near ft_mid if the knob model is right; fa_lo (0.0005 x 2 = 0.0010)
  and fa_hi (0.00075 x 3 = 0.00225) to bracket the peak from both sides. **ft_mid is also being
  re-gated at 1728 games** rather than the 1152 it was called on, which adds 576 genuinely new games
  and tightens the headline interval for nothing.

  **Prediction recorded before the results land:** ft2_b (0.0005 x 8 = 0.0040) must be clearly
  negative, -10 to -40. If the knob model holds, fa_rep, fa_a and fa_b cluster together near ft_mid
  and fa_hi is negative. **If fa_rep, fa_a and fa_b all land near zero, ft_mid was noise, the
  depth-10 fine-tune line is dead, and V7k stays.**

- 02:25 (Opus session, V8 night) **AUTOPSY: flagE scored -345 and killed the from-scratch
  depth-10 line. The cause is arithmetic, not chess, and it invalidated the flagship before the
  flagship could waste the GPU window on it.**

  flagE: 1024 SCReLU, from scratch, 96 superbatches, lr 0.0005, on 41M depth-10 rows.
  Result **-345 ±20** vs k96 (12.1%, checkmated in 1,461 of 1,728 games).

  **What the diagnostics said, and why the obvious reading was wrong.** The net looks healthy on
  every quick check: startpos 19.9 cp, startpos-minus-a-rook -343.2 cp, KPK 289.1 cp, weight norms
  in the normal band (|b1|max 0.449 against k96 0.763), running loss 0.003565 -- lower than any net
  trained tonight. A low loss and sane sanity positions would ordinarily mean a good net. Here the
  low loss IS the failure, and the three sanity positions are precisely the ones a memorising net
  still gets right.

  | | unique rows | superbatches | position views | **epochs** |
  |---|---|---|---|---|
  | k96 (the working baseline) | 712M | 96 | 9.6B | **13.5** |
  | flagE (-345) | 41M | 96 | 9.6B | **236** |

  A superbatch is a fixed 100M positions regardless of dataset size, so cutting the corpus by 17x
  multiplies the epoch count by 17. **flagE saw every row 236 times and memorised the set.**

  **The labels were checked before the data was blamed, and they are clean**: cp is int16 spanning
  +-3000 with median 10 and mean 56, a normal white-biased distribution; the all-zero `result`
  column is expected because the trainer runs `--wdl 0.0` and uses eval only. Depth-10 is not what
  failed.

  **Why no amount of waiting fixes it.** A from-scratch 1024 net needs ~9.6B position views to
  converge. To keep the epoch count near 13 that requires ~700M rows. Labelling runs at ~4,500
  pos/s, so 700M depth-10 rows is roughly 43 hours away. **From-scratch on depth-10 alone is
  unreachable before the deadline, and the line is closed on arithmetic rather than on a verdict.**

  **What this caught.** The flagship was armed to train from scratch on ~77M depth-10 rows at 96
  superbatches -- 126 epochs, still ~9x k96's regime -- and would have produced a second broken net
  plus two wasted gate slots. It was stopped before its convert step wrote anything, so no work was
  lost. flagF (192 superbatches on the same 41M rows, ~470 epochs) is still gated deliberately: if
  the overfitting diagnosis is right it must be WORSE than flagE, and that is the cheapest available
  confirmation of the mechanism.

  **What could have been done better:** the flagship's own header said "the from-scratch floor of
  ~46M rows" and armed a from-scratch run at 41M anyway. The floor was written down and then not
  applied to the arm that violated it. The epoch count -- views divided by unique rows -- is one
  line of arithmetic and was never computed for any arm tonight until a net came back at -345.
  **Every training arm from here states its epoch count before it is launched.**

  **Replaced by v8_mix.sh, the corrected version of the same bet:** keep the volume that works and
  change the labels on the fraction we can. mixA = 712M d7 + 77M d10 (789M rows, 10% depth-10, 12.2
  epochs on every row -- k96's regime exactly, zero overfitting risk). mixB = 712M d7 + 77M d10
  oversampled 3x (943M rows, 25% depth-10, 10.2 epochs on d7 and 31 on d10). Two points on the
  depth-10 fraction, the axis nothing has measured.

- 02:45 (Opus session, V8 night) **PREDICTION FALSIFIED, AND THE HONEST REPLACEMENT IS "WE ARE
  READING NOISE".** The total-update model predicted ft2_b (lr 0.0005 x 8 sb = 0.0040) at -10 to
  -40. It returned **+17 ±11** over 1728 games, interval clear of zero. The model is dead:

  | arm | lr | sb past 96 | lr x sb | rows | result |
  |---|---|---|---|---|---|
  | ft_lo | 0.0002 | 2 | 0.0004 | 18M | +18 ±13 |
  | ft_mid | 0.0005 | 3 | 0.0015 | 18M | +25 ±14 |
  | ft_mix | 0.0005 | 4 | 0.0020 | 18M + old | +11 ±14 |
  | ft2_a | 0.0005 | 4 | 0.0020 | 41M | -1 ±11 |
  | ft_hi | 0.001 | 4 | 0.0040 | 18M | -0 ±13 |
  | **ft2_b** | **0.0005** | **8** | **0.0040** | **41M** | **+17 ±11** |

  Two arms at an identical total update of 0.0040 land 17 Elo apart, and on the same data at the
  same learning rate the LONGER run is better, not worse. Both are the opposite of what the model
  required.

  **The replacement is not a better model, it is the admission that there is not enough signal for
  one.** Six arms spanning -1 to +25, every interval ±11 to ±14. That spread is about 2 sigma: it is
  entirely consistent with depth-10 fine-tuning being worth a flat **+10 to +15** with arm-to-arm
  scatter from measurement noise and training stochasticity, and no structure in lr or superbatches
  at all. Under that reading ft_mid's +25 is the top of the scatter and ft2_a's -1 the bottom, and
  every mechanism I have proposed tonight -- the total-update peak, the catastrophic-forgetting
  story -- was pattern-matching on six noisy points.

  **This is the second time tonight I built a mechanism out of a curve that was noise** (the first
  was reading the recipe sweep as one clean knob, which the r = 1/8 point then contradicted at -18
  against a predicted -25 to -50). The failure mode is consistent and worth naming: **with ±12
  intervals, any six points admit a story, and I keep telling one instead of saying the interval is
  wider than the effect.**

  **What this means for V8, stated plainly.** A flat +10 to +15 at 30k fixed nodes is NOT a
  generational leap, and it is worse than that at the clock that counts. The one timed gate running
  has ft_mid at **+5 ±17 after 220 games at 120+0.5** against its +25 at fixed nodes -- consistent
  with the project's own precedent, where V7k's core measured +40 fixed-node and +24 timed. **Eval
  gains compress as depth rises**, because a deeper search compensates for eval error, so a 30k-node
  gate (depth ~11-12) systematically overstates an eval change relative to the platform's depth
  ~17-19. That is the mirror image of the speed-blindness lesson and it deserves the same standing.

  **Consequence: the net is unlikely to carry V8 on its own, and the ship rule stands untouched --
  +20 or better at the real clock with the interval clear of zero, or V7k stays.** The two lines
  that can still matter are the draw-conversion policy, which is being measured properly for the
  first time tonight, and the confirmation that V7k's +39 survives the real wrapper, which is at
  58.5% (+60 ±70) after 100 of 400 games.

- 03:00 (Opus session, V8 night) **THE DEPTH-10 CORPUS IS TWO DIFFERENT DISTRIBUTIONS, AND THAT --
  not volume, not learning rate, not superbatches -- is the one non-noise difference between the
  fine-tunes that disagree.** Measured across all 406 labelled shards:

  | series | shards | rows | \|cp\|>800 | cp mean | quiet |
  |---|---|---|---|---|---|
  | shard_4xxxxx | 130 | 26M | **3.6%** | 58 | 78.6% |
  | shard_5xxxxx | 228 | 45M | **19%** | 130-215 | 83% |
  | shard_9xxxxx | 48 | 9.6M | **3.5%** | 60 | 77.8% |
  | *d7, the corpus k96 was trained on* | - | 712M | *9.9%* | *98* | - |

  The 5xxxxx series carries roughly **five times** the already-decided positions of the other two
  and twice the rate of d7 itself. All three series are labelled at depth 10 and all pass the
  earlier sanity check, which is why the contamination survived that check: the labels are correct,
  it is the POSITIONS that are drawn from a different distribution.

  **This maps exactly onto the one clean disagreement in the results.** ft_mid and fa_rep share a
  recipe -- 1024 SCReLU, resume k96-96, lr 0.0005, 3 superbatches -- and differ only in corpus:

  | net | corpus | \|cp\|>800 | rows | result |
  |---|---|---|---|---|
  | ft_mid | shuf_d10, 4xxxxx only | 3.6% | 18M | **+23 ±16** at 860 games |
  | fa_rep | shuf_g, 38% 5xxxxx by row | 9.5% | 41M | **+6 ±15** at 860 games |

  The 17-Elo gap has been stable from 300 games through 860. It is about 2.1 sigma on the
  difference, so on its own it would be suggestive rather than settled -- but the corpus difference
  behind it is **measured, not inferred**, which is what separates this from the two mechanisms I
  proposed and lost tonight.

  **What this reframes.** "More depth-10 data did not help" was never a volume result. Every arm
  that used the larger corpus was also using a corpus that was 38% contaminated by row, and the two
  were confounded from the moment shuf_g was built. ft2_a (-1), fa_rep (+6) and flagE (-345) all
  drank from it. flagE remains an epoch-count failure -- 236 epochs is fatal on its own -- but its
  data was dirty as well.

  **What could have been done better:** the corpus was never profiled before it was trained on. One
  pass computing mean, median and the |cp|>800 fraction per shard series -- about thirty seconds of
  numpy, and exactly the pass that found this -- would have caught it before six nets were trained
  and gated on it. **Profile the data distribution before training on it, not after a net comes back
  wrong**, and the profile belongs next to the epoch count in the pre-launch checklist.

  **Acted on: fc_a and fc_b**, fine-tunes on all 178 CLEAN shards -- 35,458,988 rows at a verified
  3.68% -- which is twice the data ft_mid had at the same purity, at the two recipes that produced
  positives (lr 0.0005 x 3 = 8.4 epochs, and x 8 = 22.5 epochs, both stated before launch). They
  train alongside the mix rather than behind it, because the mix is I/O bound at ~50% GPU and these
  are two minutes of work. **If the clean-data reading is right these match or beat ft_mid's +24 on
  twice the data; if they land near +5 like fa_rep, the corpus was not the difference and the whole
  depth-10 fine-tune line is noise around +10.**

- 03:30 (Opus session, V8 night) **THREE VERDICTS: the overfitting mechanism is confirmed by a
  correct prediction, the clean-data reading survives its test at full length, and the draw-policy
  lever is dead.**

  **1. flagF confirms the epoch diagnosis.** The prediction on record was that if flagE's -345 was
  caused by epoch count rather than by depth-10 labels, then flagF -- the same data and recipe at
  192 superbatches instead of 96, so 470 epochs instead of 236 -- must be WORSE. It is:
  **flagF -366 ±20 against flagE -345 ±20**, 21 Elo worse for exactly double the epochs. The
  mechanism is established rather than assumed, and the from-scratch-on-depth-10 line is closed with
  a reason attached.

  **2. The clean-data result held at full length.** Both gates finished at 1728 games:

  | net | corpus | \|cp\|>800 | rows | F30k vs k96 |
  |---|---|---|---|---|
  | ft_mid | 4xxxxx only | 3.6% | 18M | **+25 ±11** |
  | fa_rep | 38% 5xxxxx | 9.5% | 41M | **+4 ±11** |

  Identical recipe, 21 Elo apart, **2.7 sigma on the difference**. ft_mid's re-gate also reproduced
  its original +25 ±14 exactly at +25 ±11, so the headline is a replicated measurement rather than a
  single lucky gate. This is the only mechanism proposed tonight that was measured in the data
  before it was used to explain a result, and it is the only one still standing.

  **3. The draw-policy lever is dead at the screen depth.** Against s48, with k96 on the near side:

  | arm | vs s48 | draw rate |
  |---|---|---|
  | contempt 20 (shipped default, control) | **+68 ±16** | 45.8% |
  | contempt 0 (no draw aversion at all) | **+68 ±14** | 45.0% |
  | contempt 45 | **+49 ±22** (540 games) | - |
  | draw-seek 40 when behind (control -68) | **-83 ±23** (560 games) | - |

  Removing contempt entirely moves neither the Elo nor the draw rate; raising it costs ~19; and
  actively seeking draws when behind costs ~15. The last one has a clean explanation: seeking a draw
  means declining better continuations, and being behind is not the same as being lost.

  **The caveat, stated rather than buried: this screen may be structurally blind to the lever it is
  screening.** Contempt only binds when a draw by rule genuinely competes with the alternative, and
  the 30k-node gate runs at 45.8% draws while the 120+0.5 gate between comparable engines runs at
  **84%**. Screening a drawn-position lever in an instrument with half the drawn positions is the
  same shape of error that rejected the 1024 net three times. **v8_deep.sh is running the control and
  contempt 45 again at 200,000 nodes** -- roughly depth 15-16 against 11-12, still deterministic and
  still contention-immune, so it costs no timed-gate time. If the two arms land together again the
  lever is genuinely dead; if c45 separates there, the screen was blind and the answer changes.

  **Standing state of the V8 conversion requirement.** Draw-to-win and loss-to-draw have now been
  attacked through three distinct mechanisms: static eval twice (A1 anti-simplification, A3
  drawishness, both dead at default 0) and the search's terminal draw score once (contempt and the
  new BINI_DRAW_SEEK, dead or harmful at 30k nodes, pending the 200k re-screen). **BINI_DRAW_SEEK
  ships defaulted to 0 either way, which is byte-identical to V7k's behaviour**, so nothing about
  the current build changes on account of this work.

- 04:20 (Opus session, V8 night) **THE FIXED-NODE SCREEN DOES NOT PREDICT THE CLOCK, AND THE
  EXPECTATION FOR V8 IS BEING WRITTEN DOWN BEFORE THE VERDICT RATHER THAN AFTER.** ft_mid now has
  three independent measurements against the same opponent:

  | instrument | approx depth | ft_mid vs k96 | games |
  |---|---|---|---|
  | 30k fixed nodes | 11-12 | **+25 ±11** | 1728 |
  | 30 s + 0.125 | ~15 | **-6 ±24** | 280, running |
  | 120 s + 0.5 (the platform) | 17-19 | **+10 ±15** | 400 |

  The fixed-node number is the outlier and the two real clocks straddle zero. Pooling the intent of
  all three, **ft_mid's value at a real clock is somewhere between 0 and +10, not +25.** The
  compression is not a smooth function of depth either -- 30+0.125 sits below 120+0.5 -- so the
  cleanest statement is the modest one: a 30k-node gate measures something that does not survive to
  tournament conditions, and the size of the loss is not predictable from the screen.

  **Why this did not show up before.** V7k passed the same chain and its gain DID survive -- +40
  fixed, +24 at 30+0.125, and now +42 ±57 through the real wrapper at 150 of 400 games. The
  difference is what the gain was made of: V7k's came mostly from correction and continuation
  history, which are SEARCH features, plus a wider net. **A search feature changes what the engine
  finds at every depth; an eval refinement is progressively compensated for by deeper search.** That
  is a hypothesis, not a measurement, but it fits every number the project has.

  **Stated expectation for fc_b, recorded now.** fc_b is **+33 ±15 at 1728-game pace on fixed nodes**
  and is the best screen number of the night. Applying ft_mid's observed compression, the honest
  prediction is **fc_b lands between 0 and +15 at 120+0.5, and therefore fails the +20 ship rule.**
  Two independent 400-game gates are running to pool to ~±11, because a result near +15 would
  otherwise be unresolved rather than rejected, which is the least useful outcome available.

  **If that prediction is right, the recommendation is to hold V7k**, and V8's contribution to the
  project is not a net but four closed questions and one corrected instrument: the recipe axis is
  exhausted at lr/batch = 1/2; from-scratch on depth-10 is impossible before the deadline on epoch
  arithmetic; the corpus is two distributions and only 178 of 406 shards are clean; and the draw
  policy is dead or harmful at screen depth. **The candidate zip is nevertheless built, diffed and
  validated so that shipping remains a decision rather than a scramble.**

- 03:30 (Opus session, V8 night) **CORRECTION AND A CLEANER RESULT: the three instruments agree
  after all, and reading a gate mid-flight was the error.** At 290 of 400 games the 30+0.125 gate on
  ft_mid was showing -6 ±24 and I wrote that the instruments were mutually inconsistent, since that
  sat below the 120+0.5 figure of +10. **It finished at +8 ±21.** The mid-flight number was noise
  and the inconsistency was mine, not the instruments'.

  | instrument | approx depth | ft_mid vs k96 | games |
  |---|---|---|---|
  | 30k fixed nodes | 11-12 | **+25 ±11** | 1728 |
  | 30 s + 0.125 | ~15 | **+8 ±21** | 400 |
  | 120 s + 0.5 (the platform) | 17-19 | **+10 ±15** | 400 |

  **The two real clocks agree with each other at about +9 and only the fixed-node screen is the
  outlier.** Pooling them gives ft_mid **+9 ±12 at a real clock against +25 on the screen**, a
  compression ratio of 0.36. That is a much stronger statement than the muddle I wrote an hour ago:
  the screen is not unpredictable, it is consistently inflationary for an eval change, by roughly a
  factor of three.

  **Operational rule this produces:** a fixed-node number for a net change should be read as roughly
  a third of itself before it is compared to the ship rule. On that arithmetic fc_b's +31 ±14 screen
  becomes about **+11 at a real clock**, which is a real gain and still short of +20.

  **And the standing lesson, restated because I broke it tonight: do not read a partial gate.**
  Every interval quoted mid-flight this session -- fa_rep at +9 then +4, fc_b at +23 then +33 then
  +31, ft_mid at -6 then +8 -- moved more than its own interval implied, because the pentanomial
  intervals assume the full paired sample. Partial reads are for spotting a crash, not for forming a
  view.

- 03:45 (Opus session, V8 night) **PROVENANCE OF THE 5xxxxx SHARDS: not contamination, a deliberate
  endgame-targeting decision that backfired at concentration.** v8_feed3.sh line 9 seeds the
  500000-series FENs from `data/labelled/shard_007*` -- the **endgame stream**, 559 files -- plus
  `shard_009*`, the **elite late-ply stream**, and `shard_020*`. That was aimed squarely at the flaw
  the real games exposed and the V7k entry named: "after the endgame bias of the net is fixed".

  **The intent was correct and the concentration was not.** Endgame and late-ply positions are
  disproportionately already decided -- one side is usually winning by the time you are there -- so
  seeding from those streams produced a corpus at 19% |cp|>800 against 3.6% for normal play, and
  against 9.9% for the depth-7 corpus k96 actually learned from. At 38% of shuf_g by row it dragged
  the whole training distribution away from the distribution the engine is evaluated in, and cost
  **21 Elo** against the same recipe on clean data (fa_rep +4 ±11 versus ft_mid +25 ±11).

  **The correct version of this idea, for the Friday build:** targeted data works as a SPICE, not as
  a base. Endgame and late-ply positions belong in the corpus at something like the 5-10% they
  occupy in real play, not at 38%. The diagnostic that decides it is one line -- the |cp|>800
  fraction of the blended corpus against the 9.9% of the corpus that trained the current champion --
  and it costs thirty seconds to compute before any training starts.

  **This also retires the word "contamination" from tonight's account.** Nothing was corrupt: the
  labels are correct, the depth is a uniform 10, and the positions are real. What went wrong is that
  I changed what the net was being taught about without measuring how far that moved the teaching
  set from the test set. **Distribution shift, self-inflicted, and invisible to every check that
  looked at label correctness rather than label distribution.**

- 03:55 (Opus session, V8 night) **DRAW POLICY CLOSED, AND THE ASPIRATION WINDOW WAS ALREADY SWEPT.**

  Final contempt numbers, k96 on the near side against s48, 1152 games each:

  | arm | result | vs control |
  |---|---|---|
  | contempt 0 | **+68 ±14** | 0 |
  | **contempt 20 (shipped default)** | **+68 ±16** | control |
  | contempt 45 | **+46 ±15** | **-22** |
  | draw-seek 40 when behind | **-80 ±16** (control -68 ±16) | **-12** |

  **Flat from 0 to 20, sharply negative above, and the loss-to-draw half is actively harmful.** The
  shipped default of 20 is already at the optimum and there is nothing on this axis to win. The
  draw-seek result has a clean mechanism: being behind is not the same as being lost, and scoring a
  draw as a gain makes the search decline continuations that were better than the draw.

  **A stale comment corrected.** bini_engine.py line 42 says the aspiration window "has never been
  swept; it is one of the last untouched search constants". It was swept yesterday at 17:14 --
  **asp12 -16 ±19 and asp50 -18 ±18** on the V7 config, 576 games each -- and both lost. The two
  points bracket the default of 25 on either side, so the peak is at or near 25 and the lever was
  already closed. Tonight's sweep re-runs 12, 18, 35 and 50 against **k96** rather than the historical
  baseline and at 1728 games rather than 576, which is the right way round per the SEE_Q lesson, but
  the expectation is confirmation rather than a gain. **The comment should be deleted from the source
  so it stops advertising a lever that is shut.**

  **Process note:** a_asp50.log already existed from that earlier run, and for a few minutes the
  poll showed it as "576/576 complete" alongside an arm that had not started -- an impossible
  ordering that gave the collision away. Gate output names are being reused across sessions in a
  flat directory, and the only reason this was caught is that the sequencing made no sense.
  **Gate outputs should carry a run stamp.**

- 04:00 (Opus session, V8 night) **THE CLEAN-DATA HYPOTHESIS IS CONFIRMED AT FULL LENGTH, AND IT IS
  THE ONE THING TONIGHT THAT SURVIVED EVERY TEST IT WAS GIVEN.** Both arms finished at 1728 games:

  | net | corpus | rows | superbatches | epochs | F30k vs k96 |
  |---|---|---|---|---|---|
  | **fc_b** | 178 clean shards, 3.68% | 35.5M | 8 | 22.5 | **+29 ±11** |
  | fc_a | same | 35.5M | 3 | 8.4 | **+25 ±12** |
  | ft_mid | 90 clean shards, 3.6% | 18M | 3 | 16.7 | **+25 ±11** |
  | fa_rep | 38% endgame/late-ply, 9.5% | 41M | 3 | 7.3 | **+4 ±11** |

  **Doubling the clean data held the gain and did not extend it** (ft_mid +25 at 18M against fc_a +25
  at 35.5M, the same recipe), which finally answers the volume question that was confounded all
  night: within this range, depth-10 volume is neutral and **purity is worth 21 Elo**. The gain comes
  from the corpus the fine-tune is drawn from, not its size.

  **Training length has a peak and it is bracketed on both sides.** On the clean corpus: 3 sb +25,
  **8 sb +29**, 16 sb +13 and falling, 24 sb -27. Enough training to absorb the new label
  distribution, not so much that k96's 712M depth-7 positions are overwritten -- and the decay
  setting in around 45-68 epochs is the same forgetting that destroyed flagE at 236 and flagF at 470.
  **fc_b sits at the peak of a four-point curve**, which is a materially stronger claim than ft_mid's
  original single point.

  **What this cost to learn, honestly.** The peak was found by measuring, not by reasoning: two
  mechanisms were proposed tonight to explain the fine-tune results (a total-update knob, then
  catastrophic forgetting as the sole cause) and both were falsified by the next data point. The
  thing that actually worked was profiling the corpus and noticing that two arms sharing a recipe
  disagreed by 21 Elo. **Measure the input before theorising about the output.**

- 04:05 (Opus session, V8 night) **THE "SPICE NOT BASE" HYPOTHESIS IS FALSIFIED TOO, AND RUNNING TWO
  TIMED GATES INSTEAD OF ONE IS ALREADY EARNING ITS KEEP.**

  **Blend dose curve.** The reasoning was that the endgame and elite late-ply streams were the right
  instinct at the wrong dose -- 38% of the corpus cost 21 Elo, so 5-10% should pay. It does not. On
  fc_b's recipe (lr 0.0005, 8 superbatches past k96-96), with the blended distribution measured
  BEFORE training this time:

  | arm | endgame share | blended \|cp\|>800 | rows | F30k vs k96 |
  |---|---|---|---|---|
  | **fc_b (control, 0%)** | 0% | 3.68% | 35.5M | **+29 ±11** |
  | fb_10 | 10% | 5.17% | 39.4M | **+18 ±26** at 310 games |
  | fb_20 | 20% | 6.66% | 44.3M | **-1 ±26** at 290 games |

  Monotone downward in the endgame share, from the first percent. **Pure normal-play data beats every
  blend tested**, and the simple version of the finding is the right one: for this fine-tune the
  endgame stream hurts at any concentration tried, not merely at 38%. That is the third mechanism I
  proposed tonight and the third to be falsified by its own test -- after the total-update knob and
  catastrophic forgetting as sole cause. The pattern is consistent and worth naming plainly:
  **every explanatory story I built tonight failed, and every measurement held.**

  **The two fc_b timed gates disagree, and that is the point of running two.** At 120+0.5 against
  k96: gate one **+29 ±22** over 240 games, gate two **+2 ±29** over 190. Pooled across 430 games the
  estimate is about **+17**, below the +20 ship bar. A single gate landing on +29 would have read as a
  comfortable pass and would have been half of a 27-Elo spread. **A 400-game gate at 120+0.5 has an
  84% draw rate and simply cannot resolve a 20-Elo question**; the decision needs the pool, and the
  pool is what the ship call will be made on.

  **Two search levers are meanwhile alive where the net is fading.** The aspiration window at 18 is
  **+15 ±14 over 930 games** against the shipped 25, with the interval now clear of zero, while 12 is
  -22 ±14 and 50 was -18 ±18 yesterday -- a real peak below the current setting. And contempt 45,
  which the 30k screen scored 22 Elo BELOW the shipped 20, is **+85 ±31 against +61 ±29 at 200k
  nodes**. Both are search changes, and search changes are what transferred intact for V7k while the
  eval gain compressed by two thirds.

- 04:10 (Opus session, V8 night) **CORRECTION TO THE CLEAN-DATA CLAIM: the effect is real but I
  over-read a single pair.** fa_lo finished at **+24 ±12** over 1728 games. It is 2 superbatches at
  lr 0.0005 on the DIRTY 41M corpus -- as strong as anything trained on clean data, and it does not
  fit the story I wrote at 03:00.

  Every fine-tune at lr 0.0005, by corpus and length:

  | superbatches | clean corpus (3.6%) | dirty corpus (9.5%) |
  |---|---|---|
  | 2 | - | **+24 ±12** (fa_lo) |
  | 3 | **+25 ±11** (ft_mid, 18M), **+25 ±12** (fc_a, 35.5M) | **+4 ±11** (fa_rep) |
  | 8 | **+29 ±11** (fc_b) | **+17 ±11** (ft2_b) |
  | 16 | **+1 ±16** (fc_c) | - |
  | 24 | **-27 ±16** (fc_d) | - |

  **What I said and what is actually supported.** I wrote that the corpus difference was "21 Elo,
  2.7 sigma, measured not inferred, the only mechanism still standing". The 21 Elo came from ONE
  matched pair (ft_mid against fa_rep at 3 superbatches). There are two matched pairs, not one:
  **21 Elo at 3 sb and 12 Elo at 8 sb.** So the honest figure is **12 to 21 Elo**, and fa_rep's +4
  is probably a low outlier as much as it is a corpus effect.

  **The better-supported statement is about behaviour, not magnitude.** Across four lengths the
  clean corpus is smooth and single-peaked -- +25, +29, +1, -27 -- while the dirty corpus across
  four lengths is erratic: +24, +4, -1, +17, with a 20-Elo swing from a single extra superbatch.
  **Clean data trains predictably; endgame-heavy data trains unpredictably.** That is worth more
  operationally than the headline number, because it means a dirty-corpus arm cannot be trusted from
  one gate, and it is consistent with fa_rep and ft2_a both landing near zero by chance.

  **This is the fourth story of the night to be dented by its next data point.** The measurements
  have all held; every narrative I have laid over them has needed revision. The one that has
  survived unchanged is the plainest: **fc_b at +29 ±11 on the screen is the best net we have, and
  the screen inflates by about 3x.**

- 04:25 (Opus session, V8 night) **CONTEMPT 45 IS -40 AT A REAL CLOCK, AND THE 200k SCREEN THAT
  REVIVED IT LOOKS LIKE AN ARTEFACT OF FIXED NODES.**

  fc_b with contempt 45 against fc_b with the shipped 20, self-play at 30+0.125, 400 games:
  **-40 ±24**. Against an equal opponent, raising contempt costs 40 Elo -- decisively, and in the
  direction the 30k screen originally said before the 200k screen appeared to overturn it.

  | instrument | opponent | c45 relative to shipped 20 |
  |---|---|---|
  | 30k fixed nodes | s48, weaker | **-22** |
  | 200k fixed nodes | s48, weaker | **+41** |
  | 30 + 0.125, real clock | itself, equal | **-40** |

  **Two of these three are fixed-node and they disagree with each other by 63 Elo on the same
  opponent.** That alone should have been a warning: a lever whose measured value swings by 63 Elo
  between two node counts is not a lever with a stable value, it is an instrument artefact.
  Tonight's other measurement of the same kind -- ft_mid at +25 on the screen and +9 at two real
  clocks -- says the same thing from the other direction.

  **A design error of mine, named.** When the first contempt sweep was built I argued explicitly
  that self-play is the wrong test for contempt, because declining a draw against an equal opponent
  is pure risk with no edge, so a self-match reports ~0 however good the policy is. I then built the
  timed confirmation as self-play anyway. The -40 is therefore the right answer to the wrong
  question: it measures contempt's cost against an equal, not its value against the field.
  **v8_cgap.sh is running the missing cell** -- fc_b at contempt 20 and 45 against **k24**, which is
  1024 wide like fc_b (so speed-identical, unlike s48 at 512, which cannot be used in a timed gate
  on a loaded box) and about 40 Elo weaker, at 30+0.125.

  **Prediction recorded before it lands:** if contempt is a real ladder lever, c45 beats c20 against
  k24 by something like the +41 the 200k screen suggested. If contempt is simply bad, c45 loses to
  c20 there too, and the 200k reversal was noise plus fixed-node inflation. **My expectation, given
  a -40 at a real clock and a -22 at the honest screen depth, is the second: contempt stays at 20.**

- 04:40 (Opus session, V8 night) **POOLED SHIP NUMBER, AND A CORRECTION TO THE COMPRESSION RULE.**

  fc_b against k96 at 120+0.5, two independent 400-game gates, combined by inverse-variance weighting:

  | | Elo | 95% interval |
  |---|---|---|
  | gate 1 (400 games) | +23 ±18 | [+5, +41] |
  | gate 2 (400 games) | +7 ±22 | [-15, +29] |
  | **pooled (~800 games)** | **+16.6 ±13.9** | **[+2.7, +30.5]** |
  | clean fine-tune family (+ fc_a) | **+17.9 ±11.6** | **[+6.3, +29.5]** |

  **Clear of zero, short of the +20 bar.** Running two gates was worth it: gate 1 alone reads as a
  comfortable pass and gate 2 alone reads as nothing, and each is a legitimate 400-game sample. The
  84% draw rate at 120+0.5 is what makes a single gate this unstable.

  **Correction: the "read a screen number as a third of itself" rule was over-precise.** It was
  derived from one net. Two nets now have both numbers -- ft_mid +25 screen / +9 clock (0.36) and
  fc_b +29 screen / +17 clock (0.59) -- so the survival fraction is somewhere between a third and
  three fifths, not a constant. **The defensible form is weaker and more useful: a fixed-node number
  is an upper bound that requires a timed gate, and cannot be scaled by a fixed factor into one.**
  That is the fifth story of the night to need revision on contact with its second data point.

- 04:55 (Opus session, V8 night) **CONTEMPT CLOSED FOR GOOD, AND A REAL-WRAPPER TEST CAUGHT BEING
  INVALID BEFORE IT WAS BELIEVED.**

  **Contempt, final.** fc_b against k24 (1024 wide like fc_b, so speed-identical, and ~40 Elo
  weaker) at 30+0.125, 400 games each -- the deployment condition, a real clock against a weaker
  opponent:

  | arm | result vs k24 |
  |---|---|
  | **contempt 20 (shipped)** | **+51 ±23** |
  | contempt 45 | **+37 ±22** |

  **Contempt 45 is 14 Elo worse than the shipped 20 in exactly the condition that was supposed to
  favour it.** The prediction recorded before this landed was that the 200k-node reversal (+86 vs
  +53) was fixed-node artefact rather than a real depth effect, and that is what it was. Every
  honest instrument now agrees: contempt is flat from 0 to 20 and negative above, and **the shipped
  value of 20 is already correct.** The draw-conversion requirement has been attacked through static
  eval twice and the search's terminal draw score once, and all three are dead.

  **The real-wrapper test was invalid on its first attempt and said so in its own log.** V8 versus
  V7k through arena_par at 40 workers printed **"NOTE: agent ran on the fallback (compile exceeded
  the join timeout)"** on 50 of the first 47 games. agent.py joins its numba build thread for
  COMPILE_JOIN_S = 75s and plays a simple fallback engine if the compile is not finished; 40 workers
  means 80 simultaneous compiles, the join blew, and **both sides were playing as the fallback**.
  The 50.0% it printed was two fallback engines drawing with each other and had nothing to do with
  either net.

  **Restarted at 28 workers with BINI_JOIN_S=300**, which is a faithfulness fix rather than a
  convenience one: the platform gives each agent its own process and a 90s budget with no
  competition, and compile there measures 37s. The 75s join only binds because this harness runs
  dozens of compiles at once, which the platform never does. Fallback count on the restart is **0**.

  **The lesson is not the misconfiguration, it is that the harness announced its own failure and the
  number still looked plausible.** A 50.0% between two nets that differ by a single fine-tune is
  exactly what a real result would look like. Had that line not been read, an invalid 50.0% would
  have gone into the handover as evidence that fc_b is worthless at the real clock. **Check the
  harness's own diagnostics before reading its numbers, especially when the numbers are unsurprising.**

- 05:10 (Opus session, V8 night) **THE CONTEMPT REVERSAL WAS A PARTIAL-READ ARTEFACT, AND IT
  DISSOLVED AS THE SAMPLE FILLED.** At 200k fixed nodes against s48, the gap between contempt 45 and
  the shipped 20 shrank steadily as games accumulated:

  | games each | c20 | c45 | gap |
  |---|---|---|---|
  | ~130 | +55 ±33 | +88 ±36 | **+33** |
  | ~260 | +52 ±25 | +84 ±27 | +32 |
  | ~400 | +50 ±21 | +82 ±21 | +32 |
  | **576 / 520 (final)** | **+56 ±18** | **+69 ±19** | **+13** |

  The gap held around +32 for four hundred games and then collapsed to +13 in the last stretch,
  which is smaller than the interval on the difference. **There is no contempt effect at depth.**
  Together with the real-clock test against a weaker opponent -- contempt 20 **+51 ±23**, contempt 45
  **+37 ±22** -- the lever is closed in every condition that was supposed to favour it.

  **I called that reversal "the single most interesting thing on the board" at 130 games**, and
  built an experiment on it. The prediction I recorded before the timed cell landed was right (that
  it was fixed-node artefact), but the excitement preceded the evidence by three hours. This is the
  same failure as fa_rep at +9 then +4, fc_b at +23 then +33 then +29, ft_mid at -6 then +8, and
  fc_b's pooled clock number at +27 then +17 then +13.7. **Six times tonight a partial read pointed
  somewhere the full sample did not go, and every single time the full sample was less exciting.**
  The rule is not "read partials carefully". It is **do not form a view from a partial gate at all**;
  use them only to confirm a job is alive.

  **Standing at 05:10.** V8 = V7k code plus the fc_b net, +13.7 ±13.7 at the platform clock, below
  the +20 bar with the interval touching zero. **Recommendation: hold V7k.** Aspiration 18 is at
  +17 ±26 over 100 timed games against a +14 ±11 screen, and is the one lever worth the morning.
  The V8-versus-V7k real-wrapper test is running at about 47 games per 14 minutes and will be cut
  short by the credit; whatever partial it reaches is in `gates/v8_vs_v7k_real.log` and mirrored to
  `~/chess_d10_mirror/final_tests_progress.txt`.

- 05:15 (Opus session, V8 night) **THE ASPIRATION SWEEP IS COMPLETE AND IS THE BEST-ESTABLISHED
  RESULT OF THE NIGHT.** Every arm at 1728 games against k96, the current champion:

  | window | vs shipped 25 |
  |---|---|
  | 12 | **-22 ±11** |
  | **18** | **+14 ±11** |
  | 25 | shipped default |
  | 35 | **-14 ±11** |
  | 50 | **-14 ±12** |

  **A symmetric single peak at 18, with both shoulders measured at full length.** That is a stronger
  evidential base than fc_b has: the net rests on a four-point length curve, this on a five-point
  sweep. Its timed gate at 30+0.125 is tracking **+10 ±24 over 180 games** -- positive, a little
  under the screen, consistent with mild compression rather than the collapse an eval change suffers.

  **Why this was nearly missed.** bini_engine.py line 42 has carried the comment "25 has never been
  swept; it is one of the last untouched search constants" since V6, and the sweep that WAS run
  yesterday tested 12 and 50 against **s48** at 576 games -- both lost, so the lever was written off
  as closed. Re-running against **k96** at 1728 games found a +14 peak between the two points that
  had been tested. **The SEE_Q lesson (tune against the current best, never a historical baseline)
  cost +16 when it was learned and would have cost +14 again here.** Two points that bracket a
  default do not close a lever if they were measured against the wrong opponent.

  **Not shipped tonight**, because it has no completed timed gate and every screen number this
  project has trusted without one has been wrong. It is the first job of the morning: one env var,
  no training, forty minutes of gate.

- 05:20 (Opus session, V8 night) **CONTEMPT CLOSED WITH PROPER STATISTICS, AND THE ERROR THAT MADE
  IT LOOK ALIVE WAS COMPARING POINT ESTIMATES INSTEAD OF TESTING THE DIFFERENCE.**

  Contempt 45 against the shipped 20, every instrument, expressed as a difference with the interval
  on that difference:

  | instrument | opponent | c45 - c20 | verdict |
  |---|---|---|---|
  | 30k fixed nodes | s48 | **-22 ±22** | significant LOSS |
  | 200k fixed nodes | s48 | **+14 ±26** | not distinguishable from zero |
  | 30 + 0.125 real clock | k24, weaker | **-14 ±32** | not distinguishable from zero |
  | 30 + 0.125 real clock | itself, equal | **-40 ±24** | significant LOSS |

  **No instrument shows a significant gain; two show significant losses.** The shipped value of 20 is
  correct and the lever is shut.

  **The error, named precisely.** When the 200k screen showed c45 at +88 ±36 against c20 at +54 ±35
  I read a 34-Elo effect and called it "the single most interesting thing on the board", then built a
  further experiment on it. **The interval on the DIFFERENCE was ±26 from the first moment** -- two
  independent gates each carrying ±35 can differ by 34 points and mean nothing at all. Testing the
  difference is one line of arithmetic and I did not run it until three hours later, by which point
  the gap had also shrunk to +14 as the samples filled.

  **The general form, which applies to every comparison in this project:** when two arms are measured
  in separate gates, the uncertainty on their difference is sqrt(2) times the uncertainty on either
  one. Eyeballing two point estimates systematically overstates the effect, and does so most exactly
  when the intervals are widest and the temptation is greatest. **Compute the difference interval
  before forming a view, not after building an experiment on the point estimates.**

- 05:35 (Opus session, V8 night) **ASPIRATION 18 DIED AT THE CLOCK, AND IT TAKES ONE OF MY
  HYPOTHESES WITH IT.**

  | aspiration 18 vs the shipped 25 | result | games |
  |---|---|---|
  | 30k fixed nodes | **+14 ±11** | 1728 |
  | 30 + 0.125, real clock | **-3 ±17** | 400 |

  The screen result was the best-established finding of the night -- a symmetric five-point peak,
  every arm at 1728 games against the current champion, both shoulders measured (12 -22, 35 -14,
  50 -14). **At a real clock it is zero.** The two numbers are not statistically distinguishable
  (the difference is 17 ±20) so this is not a contradiction, but the point estimate at the clock is
  -3 and **the lever is therefore not established and does not ship.** BINI_ASP stays at 25.

  **The hypothesis this damages.** I argued repeatedly tonight that SEARCH changes transfer to the
  clock better than EVAL changes, on the evidence that V7k's correction and continuation history
  held their value (+40 screen, +24 timed, +46 through the real wrapper) while ft_mid's eval gain
  lost two thirds. I used that reasoning to justify running the aspiration sweep at all, and to rank
  it as the first job of the morning. **The aspiration window is a search change and it transferred
  worse than the net did** -- fc_b kept 0.47 of its screen number, aspiration kept none of it. One
  counter-example does not refute the pattern, but it is enough to stop me asserting it, and the
  handover has been corrected to remove the recommendation that rested on it.

  **Where this leaves the night: no lever cleared its bar at a real clock.** fc_b +13.7 ±13.7 against
  a +20 rule; aspiration -3 ±17; contempt, draw-seek, endgame blending, four from-scratch variants
  and two wider nets all closed negative. The recipe axis is exhausted. **V7k stays**, and the one
  unambiguously good thing measured tonight is V7k's own validation at 57.0% (+49 ±44) through the
  real wrapper -- established rather than assumed for the first time.

  **The count for the night: six hypotheses of mine proposed, six falsified by their own next data
  point** -- the total-update knob, catastrophic forgetting as sole cause, clean data worth a flat
  21, endgame data as a spice, contempt at depth, and search-transfers-better. **Every measurement
  held; every story I told about them needed revision.** The instruments were sound all night. The
  narration was the unreliable part.

- 06:20 (Opus session, V8 night) **THE REAL-WRAPPER TEST FINISHED AND CHANGED THE RECOMMENDATION.**

  V8 (V7k code, byte-identical, carrying the fc_b net) against V7k itself, through arena_par on the
  starter harness -- agent.py, book on, 120+0.5, the shipped configuration end to end:

  | measurement | games | Elo | interval |
  |---|---|---|---|
  | real wrapper arena 1 (0 fallbacks) | 400 | **+22 ±34** | [-12, +56] |
  | real wrapper arena 2 | 208 | +34 ±48 | [-14, +82] |
  | **real wrapper pooled** | **608** | **+26 ±28** | [-2, +54] |
  | node_gate, book-free, fc_b vs k96 | 800 | +13.7 ±13.7 | [0.0, +27.4] |
  | **COMBINED, both harnesses** | **~1400** | **+16.1 ±12.3** | **[+3.8, +28.4]** |

  **V8 is established as better than V7k. It is not established as better by 20.** The rule was +20
  with the interval clear of zero: the second condition passes clearly now, the first does not.

  **The recommendation moved from hold to ship, and the move was driven by evidence rather than by
  wanting a result.** At 05:30 the only clock numbers were book-free node_gate gates pooling to
  +13.7 with a lower bound of +0.02 -- indistinguishable from nothing -- and hold was right on that
  evidence. The wrapper test then added 608 games of the actual shipped configuration and pulled the
  combined lower bound to +3.8. **Updating on new data is not inconsistency; refusing to update
  would have been the error.** What has not moved is the reporting: the number is +16, the bar was
  +20, and the handover says so in those words.

  **Why shipping is defensible despite missing the bar.** The bar existed to filter noise. +16 with
  a lower bound of +3.8 over 1,400 games in two independent harnesses is not noise. The change
  carries no code risk at all -- every source file compares byte-identical to a build now validated
  at 57.5% (+53 ±40) against V6.5 -- so the only variable is the weights, and rollback is a
  re-upload of a zip that already exists.

  **The night's shape, final.** Six hypotheses proposed and six falsified; every measurement held.
  One net gain of about +16 that is real but modest, one instrument corrected (fixed-node screens are
  upper bounds and cannot be scaled), one self-inflicted data fault quantified at 21 Elo, seven
  levers closed with numbers, and V7k proven rather than assumed. **Not a generational leap. A
  well-mapped small step, and an accurate map where there used to be guesses.**

- 06:55 (Opus session, V8 night) **RUN COMPLETE. The GPU box credit expired at 06:50 London;
  everything was captured.** Final figures for V8 (V7k code byte-identical, fc_b net) over V7k:

  | measurement | games | Elo | interval |
  |---|---|---|---|
  | real wrapper, arena 1 (complete, 0 fallbacks) | 400 | +22 ±34 | [-12, +56] |
  | real wrapper, arena 2 (at expiry, 0 fallbacks) | 346 | +33 ±37 | [-4, +70] |
  | **real wrapper pooled -- the shipped configuration** | **746** | **+27 ±25** | **[+2.0, +52.1]** |
  | node_gate, book-free | 800 | +13.7 ±13.7 | [0.0, +27.4] |
  | **COMBINED** | **~1550** | **+16.8 ±12.0** | **[+4.8, +28.8]** |

  **V8 is established as better than V7k and is not established as better by 20.** Recommendation:
  ship, with the shortfall against the rule stated rather than papered over. V7k remains the
  rollback and is itself now validated at **58.9% (+62 ±36)** over V6.5 at 372 of 400 games on box A,
  which continues to run.

  **Everything survived the expiry:** both submission zips, the 5.8 GB depth-10 label corpus, five
  nets, 180 gate logs and 16 gate summaries, all on the Mac under ~/chess_d10_mirror. Arena progress
  was snapshotted every four minutes to final_tests_progress.txt, so the box dying mid-run cost
  nothing but the last 54 games of arena 2.

  **Closing tally of the night.** Seven levers closed with numbers (contempt, draw-seek, endgame
  blending, from-scratch in four variants, two wider nets, the training recipe, the aspiration
  window). One net gain of about +16, real but short of the bar. One instrument corrected: **a
  fixed-node screen is an upper bound and cannot be scaled into a clock number** -- survival measured
  at 0.36, 0.47 and 0.00 across three levers. One self-inflicted data fault quantified at 21 Elo.
  Six hypotheses proposed and six falsified by their own next data point, while **every measurement
  held**. The instruments were sound all night; the narration was the unreliable part, and the
  practices that earned their keep were running two gates instead of one, bracketing every curve on
  both sides, profiling inputs before theorising, testing differences rather than point estimates,
  and reading the harness's own diagnostics before believing its numbers.

- 07:00 (Opus session, V8 night) **V7k'S VALIDATION IS COMPLETE, AND IT LEAVES A LEAD WORTH ONE
  TEST.** V7k against V6.5 through the real wrapper finished at 400 of 400: **58.6% (+61 ±35)**,
  interval [+26, +96]. The build now running is decisively better than its predecessor in the
  shipped configuration -- established, after a night that began with the 80-game Stockfish anchor
  offering no support for it at all.

  **The lead.** Both comparisons this project has run through both harnesses read HIGHER through the
  real wrapper than through node_gate:

  | comparison | node_gate (BINI_BOOK=0) | real wrapper (book on) |
  |---|---|---|
  | V7k over V6.5 | +39 ±21 | **+61 ±35** |
  | V8 over V7k | +13.7 ±13.7 | **+27 ±25** |

  Two cases with wide overlapping intervals is not a law and must not be treated as one -- that is
  exactly the error that produced six falsified stories tonight. But it points the same way twice,
  and there is an obvious mechanism: **node_gate gates run book-free, and the wrapper carries the
  6,105-entry book.** If a book amplifies a stronger engine's edge -- plausible, since it removes the
  opening phase where a weaker evaluator is least exposed -- then **every book-free gate this project
  has ever run is systematically conservative**, and the screen-inflation finding from tonight is
  partly a book effect rather than purely a depth effect.

  **The test that would settle it is cheap and specific:** one net pair, two gates, book on and book
  off, same clock, same openings. Until that is run this stays a lead. It is written down here so it
  is not lost, and because it would change how every future number in this project is read.

- 11:45, 10 Sept (Opus session, post-upload diagnosis) **V8 IS LIVE AND #1. DIAGNOSIS OF ITS FIRST
  DRAW FOUND A REAL TRANSPOSITION-TABLE BUG THAT DID NOT COST THE GAME.**

  **Standing.** V8 shipped as v10 at 09:42 (validation confirms 14,042,168 bytes, the correct zip).
  It has played rounds 93 (win, checkmate) and 94 (draw, threefold). **Rank #1 of 440, rating 2788**,
  up from 2716 on V8's first game. No loss since round 56 on 7 September -- **38 rounds unbeaten**.

  **The loss review is closed.** All seven losses in the exported data are by checkmate, none on
  time, and five were as Black in the early rounds on 0.5 s init, i.e. V1/V2 builds. There is no
  remaining pattern to fix and no lever there.

  **Draws split into two kinds and only one is convertible.** Of the five drawn games we hold logs
  for: three ended by insufficient material having peaked at +18, +70 and +84 -- genuinely level,
  correctly drawn. Two ended by threefold having peaked at **+164 (R86)** and **+335 (R94)**, both
  finishing at exactly -20, the contempt-scored draw.

  **R94, diagnosed to the ply.** The engine reported +335 at PGN move 42 and -20 one move later.
  Reproduced exactly by replaying the endgame with a warm transposition table and the game's real
  budgets: **+383 at depth 16**, against **-20 at depth 15 from a cold table**. Same position, same
  net, same depth band. **The transposition table is producing a ~400 cp error**, almost certainly
  the classic TT-versus-repetition interaction: repetition draws are path-dependent, TT entries are
  not, so a score stored on a path with no repetition is reused on a path where the position IS a
  draw.

  **But it did not change the move.** Warm table plays Ke2. Cold table plays Ke2. At 1.5 s, 10 s and
  60 s, warm or cold, it plays Ke2. **A real bug with no evidence that it cost this game.**

  **Two corrections to my own reporting during the diagnosis**, both caught by checking the source
  rather than trusting a derived number: I first said the engine spent 992 ms and reached depth 14 at
  move 42 -- the stderr line says **1490 ms and depth 17**, and my figures came from my own estimate,
  not the log. And my first replay table flagged moves 35-38 as mismatches when the mismatch was my
  own mis-mapping of engine move numbers to PGN move numbers.

  **Decision: do not touch the search.** Fixing a TT/repetition interaction is engine-internals
  surgery on a build that is #1, unbeaten in 38 rounds and validated at +17 over its predecessor,
  with 24 hours to the roster lock and no evidence the bug costs games. The risk is grossly
  asymmetric now in a way it was not last night.

  **The one change under test** is the knob the code already documents for this:
  `MIDGAME_BOOST 1.0 -> 1.25`, "25% more time on moves 16-35 (gated at the real clock)". It targets
  measured under-spending -- the engine finishes games with 21-44 s unused, i.e. it uses only 75-85%
  of its clock. Running now on box A through **arena_par**, 400 games at 120+0.5.

  **Why arena_par and not node_gate:** MIDGAME_BOOST lives in agent.py's _budget. node_gate has a
  faithful copy of that function and does honour the knob, but reads it once as a module global that
  applies to BOTH sides, so node_gate cannot A/B it. And it has to run at 120+0.5 rather than a
  faster scaled control, because **agent.py's low-clock caps (4 s, 30 s, 10 s) are absolute, not
  scaled** -- node_gate has CLOCK_SCALE for exactly this, agent.py does not, so at a 30 s base those
  caps would bind immediately and the test would measure something else.

  The two directories differ by one line, verified with `diff -r`, on an identical net.
