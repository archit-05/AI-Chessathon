# V5 — the plan (Tuesday 8 September 2026, 13:00 London)

Written after reading PLAN.md, PLAN_V22_LEAP.md, PLAN_V3*.md, PLAN_V4.md (sections 0–27),
V4 Progress.md, the engine in bini_v4final/, the trainer and generators, the intel corpus and its
notes, our 42 rated games with the site's own Stockfish-16 evaluations, the top teams' games, and
the live leaderboard and game pages Archit linked at 12:48. No code was changed. Uploads lock
Friday 11:00; freeze for V5 is Wednesday 22:00 with a Thursday fallback.

The directive is a build that lands comfortably in the 2500–2700 band. Section 1 says what that
band is today, section 10 says honestly what this plan can and cannot promise. Everything in
between is how we get the most Elo out of the 33 hours to the freeze.

---

## 0. The read in one screen

| Fact | Value | Source |
|---|---|---|
| Ladder now (Tue 12:48) | AlphaFish 2662; places 4–7 at 2519–2532 (multi millionare, Capablanca, SoberPaschoud, AI Fellow); places 8–15 at 2390–2405; **BINI Alpha 2306, rank 19** (23-7-9) | live leaderboard |
| The band the directive names | places 1–7 today; it will drift up 50–100 by Friday as builds improve (multi millionare rose +700 in a day with one upload) | leaderboard history |
| Our form on the front-loaded clock (R46–R65, 20 games) | 12-4-4, 70%, against average opposition ~2150: a 2300 performance | scrape |
| How the four losses happened | R55 (ms), R56 (Edward), R64 (stockfih), R65 (Poincare): **no tactical blunder in any of them**; evaluation slides of 100–300 cp over 6–10 quiet moves in closed structures (two Closed Ruy Lopez, an Italian, a London), then a lost endgame; clocks were healthy (22–27 s at move 40) | site evaluations, platform logs |
| What the engine already does well | depth 15–19 at 1–4 s (700–850k nodes/s on the EPYC), perft-exact, zero failures in 42 rated games, conversion 14/15, never repeats while ahead, calm-position ACPL 3–12 | logs, intel |
| What the net does badly | MAE 145 cp against the site's labels; 165–215 cp at 5–20 pieces; 250 cp when material is ±4; output scale 1.3× the site's; the R55/R56/R64/R65 structures scored 0 to +50 where Stockfish read −100 | net_diag, game evals |
| Why V4 did not deliver | every retrained net won every static test and lost or tied in games (PLAN_V4 s24, s26): the fine-tune data was 70% draws with a median label of 32 cp, five changes went into one gate, gates were underpowered (±40–75 Elo) and run on a thrashing 8 GB Mac | PLAN_V4 s24–26 |
| Machines | Mac M2, 8 cores, **8 GB RAM**, MPS; Oracle VM 4 ARM cores, 23 GB, Stockfish 19 at 440k nodes/s per core; GCP trial **not yet provisioned** (no gcloud on this Mac) | measured |
| Data on hand | Lichess quiet 155M; site-labelled 750k (depth-16, the tournament's own distribution); elite whole-game 1.05M; decisive self-play ~1.2M and growing at ~0.5M/h (2 VM workers); endgame stream ~1.4M; hard set 152 positions | data/ |

---

## 1. What the evidence says, from first principles

### 1.1 The rating arithmetic

Glicko on this ladder is mostly about **not dropping points to the band below you**. AlphaFish is
2662 because it is 11-0 against ranks 11–50 and 66% against 2300+. We are 2306 because we are
70% against a 2150 average. To sit at 2550 we need roughly 80% against 2300-average opposition;
AlphaFish's level needs 85–88%. In Swiss terms: 13 rounds, top seeds meet from round 4–5, a
podium is ~10.5–11/13, and every half point leaked to a 2100–2300 team is a full round lost.

So the work has one objective: **stop losing to the 2100–2400 band without a tactical blunder**.
That failure mode is entirely evaluation. Depth 17 with an evaluation that reads a −100 structure
as level produces a confident, wrong plan; more depth does not fix it quickly.

### 1.2 What the top plays like (all 40+ games each, site evaluations)

- **Uniform accuracy, not brilliance.** AlphaFish CPL 8.4, blunders 0.0%; the next tier 10–12 cp.
  Games average 150 plies; half of AlphaFish's moves come after move 40 and it grades 7 cp there.
- **Flat clocks.** A fixed 3–4% of the remaining clock per move (3–4 s early, 1–1.5 s by move 40,
  28–40 s unused). Nobody spends more after a swing. Our front-loaded horizon already beats this
  in the middlegame and is a wash later.
- **Their leaks are narrow and known** (intel C1): AlphaFish plays instantly with a mate score and
  has repeated with a mate on the board; AI Fellow repeats while ahead (4 times); test_bot, AI
  Fellow, Astral, Fuzzydafool go under 5 s in a third of their games. AlphaFish also lost R50 by
  **init failure**: platform variance is real; our 31 s compile is a real asset.
- **multi millionare** (new build, +700 in a day, now 4th): draws AlphaFish, Capablanca, Sobriety,
  AI Fellows, checkers at ACPL 6 and beats the rest. That is the profile the Swiss rewards and the
  one to copy: never lose downward, hold upward.
- **The openings are a closed set.** 300 curated roots in 6,202 scraped games; the 40 most common
  cover a quarter of games; the families are Sicilian, Caro-Kann, French, Reti, English, Ruy
  Lopez, Petroff. Our four losses came from exactly the closed families. The same roots recur
  hundreds of times: what the field plays from each of them is **known data**.

### 1.3 What V4 taught (kept as rules, PLAN_V4 s26)

1. A static metric may only pick a net if it orders v2.1 < v2.2 < v3b; otherwise games decide.
2. Pilot before scale: one epoch, scale-matched export, 40 real-clock proxy games.
3. One change per gate. Machines by job. Effect-size budget: 300+ games at 10 s and 80 real-clock
   proxy games per shipped change, on machines that are not thrashing.
4. Every destructive shell step goes through a script that lists its target first.

One thing V4 did not record that matters for V5: the V4 trainer runs at ~33k rows/s (202 chunks
in 4,632 s) where the v3 trainer ran at ~98k rows/s (272 chunks in 2,134 s) on the same Mac. A
from-scratch run over 170M rows is 85 min an epoch today and 30 min with the v3 path. Fixing that
is the first engineering task, because it decides whether two full runs fit before the freeze.

---

## 2. Where Elo can come from in 33 hours (ranked, with honest odds)

| Lever | What it is | Expected gain if it lands | P(lands by Wed 22:00) | Cost |
|---|---|---|---|---|
| **N. Net from scratch on the corrected mix** | 8×768→512×2 (the shipped inference path), Lichess + decisive self-play + endgames + site ×4, cp targets, WDL only on self-play; two runs, gated by games | +30 to +120 (+100 needs the self-play volume) | 0.5 for ≥ +30; 0.25 for ≥ +100 | Mac GPU 2 × 5 h; generators on VM + GCP |
| **S. Search batch** | correction history, continuation + capture history, history-driven LMR and pruning, SEE pruning in the main search, TT static eval, improving on | +40 to +90 | 0.6 | Claude 5 h; one 600-game gate on GCP/VM |
| **B. Opening book from our own analysis, along the lines the field actually plays** | 300 roots × the continuations seen ≥ 3 times in the 6,202 site games, analysed 45 s each by our engine; graded, pruned; wrapper hook exists | +10 to +25 (fewer opening errors, 15–25 s of clock reinvested) | 0.8 | VM/GCP 6–8 core-hours; rules: permitted as shipped data (docs), confirm by email |
| **P. Speed pass** | int16 accumulators, TT eval reuse, no double in-check; node counts identical | +10 to +25 (at +15% nps) | 0.5 | Claude 3 h, Wednesday only if N/S are done |
| T. Clock | keep V3's horizon; nothing new unless the book changes the profile | 0 | – | – |
| D. Draw/contempt | keep 20; draw-when-behind stays off; drawishness rule ships only if its running gate is positive | 0 to +10 | – | already running |

Sum if everything lands: +100 to +260, i.e. 2400–2560 on today's ladder. The 2500–2700 band is
reachable **only if N lands near the top of its range**; S + B + P alone put us around 2400–2450,
top ten, not top five. Section 10 says this again with the decision rules.

Not on the list, and why: 1024 hidden (data-limited, −20% speed), a second hidden layer (10× the
output cost in numba), 16 king buckets (data-limited), Syzygy (4-men fits in the zip but is worth a
few Elo; our search already converts), MCTS/policy nets (research), opponent-specific behaviour
(we see a FEN and a clock), anything untested by Wednesday night.

---

## 3. The V5 system

V5 = the V4 engine (hardened, telemetry-free, real fallback) + N + S + B (+ P if measured), each
gated alone against V4, assembled Wednesday afternoon, battery Wednesday night.

### 3.1 N — the evaluation network

**Architecture (run A and B): unchanged from the shipped net.** 8 king buckets × 768 features →
512 × 2 → 1, clipped ReLU, int16, the exact inference path that has played 42 rated games. The
SCReLU + 8-output-bucket variant is run C (Thursday candidate), gated alone.

**Data mix per epoch** (rows after the quiet filter; oversampling shown as ×k):

| Source | Rows | Weight | Targets | Why |
|---|---|---|---|---|
| Lichess quiet (lichessq, q2, q3) | 155M | ×1 (all of it) | cp | the representation; capping it to 28M in V4 was a mistake |
| Decisive self-play, site-game starts (stream S1, section 4) | whatever exists at run start (target 15M by Wed 03:00, 40M+ by Wed 22:00) | ×2 | cp blended with the result, λ = 0.75 | teaches that winning positions are won and material counts; the V4 stream (balanced roots, 70% draws) is **excluded** |
| Endgame stream (eg2, resolved) | ~1.5M | ×2 | cp + result λ = 0.75 | the 165–215 cp hole at 5–20 pieces |
| Site-labelled (site_all) | 750k | ×4 | cp | the tournament's distribution; ×12 flattened, ×4 held V3's level (v4o2) |
| Elite whole-game (SF19 depth 10) | 1.05M | ×2 | cp | the v3b gain came from here |
| Own-distribution set (S3) | ~300k | ×5 | cp | positions our search actually reaches, labelled at depth 12 |
| Hard set + harvest | 152 | ×10 | cp | our own tagged errors |

Scale: Lichess is canonical; every Stockfish-16/19 set ×0.85 (tools/scale_fit.py). Export rescales
the output so the slope against the site's labels equals v3b's 1.305 (the search margins were
tuned on that scale); `net_diag.py` reports the slope, `export_from_pt.py --out-scale` applies it.

**Runs**

| Run | When (Mac GPU) | Recipe | Purpose |
|---|---|---|---|
| **A** | Tue ~21:00 → Wed ~03:00 (6 epochs, one-cycle, lr 1e-3, batch 16k) | mix above, cp-only everywhere (λ = 1.0) | the safe baseline: from scratch on the broader mix; if it merely matches v3b the pipeline is sane and B carries the bet |
| **B** | Wed ~03:30 → ~10:00 | A + λ = 0.75 on the self-play streams + the self-play banked by 03:00 | the decisiveness bet, gated alone against A and V4 |
| **C** | Wed 22:00 → Thu 06:00 | best of A/B + SCReLU + 8 output buckets + factoriser, all data through Wed 22:00, 8 epochs | Thursday candidate (V5.1), only if it clears +30 |

**Pilot rule before every run:** 1 epoch on the first 20 chunks, export, `net_diag` slope and MAE,
40 games at 5 s vs V4 on the VM (25 min). A pilot that loses badly (< 40%) stops the run; the
recipe is corrected before the GPU is spent.

**Judging a net (games only, static numbers for sanity):** 400 games at 5 s + 0.05 s vs V4 on the
x86 box (8 workers, ~90 min; ±25 Elo), then 300 at 10 s on the VM (2.5 h; ±40), then 40
real-clock proxy games vs Stockfish at 20k nodes on the x86 box (V3/V4 reference 46.3%). Ship
if ≥ +30 at 5 s with the draw-aware interval clear of zero, not negative at 10 s, proxy ≥ 40%
(within noise of 46%) and the blunder set at the platform budget passes.

**Calibration (30 min, Tue afternoon, not a blocker):** run `net_diag` and the WDL validation
loss on a held-out S1 chunk for v2.1, v2.2/v3 and v3b. If either metric orders them correctly it
may rank epochs within a run; it never picks between recipes.

### 3.2 S — the search batch

Each item is standard in mature alpha-beta engines and absent or switched off in ours. They are
implemented in one working copy with the existing test suite (perft, node-count regression at
fixed depth where the change must not alter the tree, mates 80/80, puzzles, blunder set).

1. **Correction history.** A table `corr[side][pawn_key & 16383]` (int32, ×256) updated at the
   end of every completed non-root node that is not in check and whose bound agrees with the
   direction (exact; lower with score > static; upper with score < static):
   `corr += clamp((score − static) × depth, −limit, +limit)` with exponential decay. The static
   evaluation used by RFP, futility, null-move and the improving flag becomes
   `static + corr/256`. This is a runtime patch for exactly our failure: the search learns, within
   the game, that the net is 80 cp too optimistic about this pawn structure. Needs a pawn-only
   Zobrist key maintained in make/unmake (about 20 lines in bini_board.py). Also a second table
   keyed by non-pawn material.
2. **Continuation history** (1-ply and 2-ply, `[piece][to]` indexed by the previous move's
   piece/to) added to quiet-move ordering scores and to the LMR formula
   (`r −= (hist + cont1 + cont2) / 8192`), plus **history pruning** at depth ≤ 3 for quiets with
   strongly negative combined history. Batch 2 measured +5 ±56 over 150 games: underpowered, not
   negative.
3. **Capture history** `[piece][to][captured]` for capture ordering after the SEE split and for
   reducing late losing captures.
4. **SEE pruning in the main search** (non-PV, not in check, depth ≤ 8): skip captures with
   SEE < −20·depth² and quiets with SEE < −60·depth.
5. **TT stores the static eval**; on a hit the eval call is skipped and a TT score whose bound
   agrees replaces the static for pruning decisions (Stockfish's "ttValue as better static").
   Age-aware replacement stays; two-slot buckets only if compile time allows.
6. **Improving flag on** (built, `BINI_IMPROVING`), gated inside the batch.
7. Quiet checks in quiescence and ProbCut stay **off** (they flipped the R43 positions on the VM).

Gate: the batch vs V4, 600 games at 5 s + 0.05 s on the x86 box (~2 h at 8 workers), then 300 at
10 s on the VM, then 40 real-clock proxies. Ship at ≥ +25 at 5 s with the interval clear of zero,
not negative at 10 s, proxy not worse. If the batch fails: split into (1, 4, 5, 6) and (2, 3) and
gate each once; drop what is not clearly positive. Compile ceiling: 40 s local quiet (today 20 s;
each item adds 1–3 s).

### 3.3 B — the opening book

The book hook, the builder and the grader exist (tools/make_book.py, book_check.py, the wrapper
lookup for our first twelve moves). What changes is coverage and provenance:

- **Positions:** the 300 curated roots plus every position within 10 plies of a root that occurs
  ≥ 3 times in the 6,202 scraped site games (the field's actual replies), estimated 2,500–4,000.
- **Analysis:** our own engine, 45 s per position (depth 20–22), TT 64 MB, on the VM's spare cores
  and the x86 box Wednesday morning (~40 core-hours; 2,000 positions is the floor, ranked by
  frequency). Entries store move, depth, score.
- **Pruning:** every entry graded by Stockfish at 120k nodes (the site's grader level); entries
  losing > 15 cp against the grader's best are dropped (this also makes the book robust to the net
  change: a V4-net book move that the grader accepts is fine under the V5 net).
- **Runtime:** in book only while the position matches exactly (board, side, castling); the moment
  the opponent leaves the tree we search. Book moves cost ~5 ms; the saved 15–25 s of clock is
  reinvested automatically by the budget formula.
- **Rules:** the docs say "Opening books and endgame tablebases are permitted as shipped data" and
  the lookup ban is about "another engine's moves or evaluations". This book is our engine's own
  output; the builder, its log and the grader report ship in the repo and are described in
  README.md. Archit sends the drafted organiser email today; unless they object by Wednesday
  20:00 the book ships, and a no-book zip is the standing rollback.

### 3.4 T, D, P — clock, draws, speed

- **Clock:** V3's horizon `mtg = max(18, 34 − 0.4n)`, danger multiplier, root guard, low-clock caps
  stay. Rated games on this policy end with 10–25 s and the pressure set's minimum is 8.3 s. With
  the book the first 4–6 moves cost nothing and the middlegame gets 3–4 s a move instead of 2–3.
- **Draws:** contempt 20; draw-when-behind off; the drawishness rule (bini_v45_draw, 49.2% at
  118/300 against V4 right now) ships only if the full 300 is positive **and** the marginal set
  converts at least as often as V4; otherwise it is dropped for good.
- **Speed (Wednesday, only if N and S are through their gates):** int16 accumulators (export
  checks the saturation bound), TT static-eval reuse (part of S), single in-check per node.
  Accept only with bit-exact evaluation and identical node counts at fixed depth; ≥ +12% nodes/s
  or it does not ship.

### 3.5 Robustness (unchanged battery, uncompressed)

Wrapper state, NNUE exactness on 3,958 positions, perft + 5,000-position differential, mates
80/80, puzzles ≥ 38/40, blunder set at the platform budget, harvest set, torture 10 + 10 with the
fallback forced, real-clock pressure 10 (min clock ≥ 5 s), both proxies, compile ≤ 40 s local
quiet (platform 31 s today; the join hedge at 75 s stays), zip byte-check, fresh-extraction game.

---

## 4. Data generation (the thing V4 got wrong at source)

### 4.1 Streams

| Stream | Start positions | Play | Labels | Rate | Where |
|---|---|---|---|---|---|
| **S1 decisive, site-game starts** (main) | a random ply 8–40 of a random scraped site game (6,202 games, the tournament's structures, already imbalanced by then), then one random legal ply with p = 0.5 | Stockfish 19 depth 9 both sides, MultiPV-3 exploration p = 0.1 for six plies, adjudicate at ±800 for six plies, result kept | depth-9 score, quiet-resolved, near-zero thinning keep 0.5 below 40 cp, dedup on the first 12 plies | ~70 pos/s per ARM core, ~150 per x86 core | VM 3 workers now; x86 box 8 workers from tonight |
| S2 endgame (eg2) | site games after ply 40, ≤ 16 pieces | depth 12, resolved | as above | 25/s | VM 1 worker |
| S3 own distribution | every position from our ~2,500 local arena/proxy games and 42 rated games | – | SF19 depth 12 | 40/s | VM, Tue afternoon, once (~300k) |
| Book analysis | section 3.3 | our engine 45 s | – | – | VM spare cores, x86 box Wed morning |

The V4 balanced stream (curated roots, best moves, 70% draws) is retired. Its chunks stay on disk
and out of every mix.

### 4.2 Volumes

| Time | VM only (1M/h) | VM + x86 box from Tue 22:00 (1M + 4M per hour) |
|---|---|---|
| Wed 03:00 (run B starts) | ~10M | ~25M |
| Wed 10:00 | ~17M | ~50M |
| Wed 22:00 (run C starts) | ~29M | ~95M |

Without the x86 box, run B trains on ~10M decisive rows and the from-scratch gain rests mostly
on the mix and the endgame data; with it, B sees 25M and C sees 95M, which is the volume at which
nets of this size stop being data-limited. **Provisioning the x86 box is Archit's first action**
(section 9).

### 4.3 Machine split (no machine runs two jobs)

| Machine | Job | Never |
|---|---|---|
| Mac (8 GB) | training only; the trainer restored to ≥ 90k rows/s | gates, generators, proxies, browsers during a run |
| Oracle VM (4 ARM cores) | generators S1–S3; pilots (40 games); the 300-game 10 s gates (generators paused) | training |
| x86 box (8 vCPU, e2/c3-standard-8, Ubuntu, Stockfish built from source, the starter venv) | S1 generation Tue 22:00 → Wed 08:00; from Wed 08:00 the 5 s gates, real-clock proxies (x86 at ~2.6 GHz is closer to the platform than the M2), book analysis | – |

---

## 5. Measurement that can see a 30-Elo change

- **Fast gate:** 5 s + 0.05 s, curated openings, colours alternated, 8 workers on x86: 600 games
  in ~2 h, ±22 Elo. Every net and the search batch go through this first.
- **Confirm gate:** 10 s + 0.1 s on the VM, 300 games, 4 workers (generators paused), ~2.5 h.
- **Real clock:** 40 proxy games vs Stockfish at 20k nodes with the 4% clock habit
  (tools/proxy_match.py) on the x86 box, 2 workers, ~3 h; reference 46.3% (V3/V4).
- **Regression at the end:** 1,000 games V5 vs V4 at 5 s on x86 (3.5 h) while the battery runs on
  the Mac; V5 must not be negative.
- **Static sanity only:** `net_diag` (MAE by piece count, slope, |err| > 200 share) and the grader
  on 300 ladder positions; they rank epochs inside a run and catch a broken export, nothing else.
- **Contamination rules:** any gate with a fallback game, a compile over 75 s or a load spike is
  discarded and rerun, not "excluded and tallied".

---

## 6. Schedule (London time; the Mac's GPU is the critical path)

| When | Mac | VM | x86 box | Claude |
|---|---|---|---|---|
| Tue 13:00–15:00 | drawishness gate finishes (2 workers); nothing else | S1 restarted in site-start mode (3 workers) + eg2; S3 labelling queued | Archit provisions (section 9) | trainer throughput fixed (numpy feature path or precomputed indices; target ≥ 90k rows/s); S1 generator changes (`--site-starts`); calibration of the static metrics |
| Tue 15:00–21:00 | **pilot for run A** (1 epoch, 20 chunks) → export → 40-game pilot on VM → **run A starts (~21:00)** | pilot games; then generators | provision → Stockfish build → S1 at 8 workers | search batch S written and unit-tested (correction history first); book position list built from the 6,202 games |
| Tue 21:00–Wed 03:00 | run A (6 epochs) | generators; book analysis on 1 spare core | S1 generation | S batch gate 600 games at 5 s **on x86 only if generation can spare it, otherwise on the VM at 4 workers overnight** (generators paused 23:00–03:00) |
| Wed 03:00–03:30 | export A (scale-matched), diag | – | – | pilot for run B (20 chunks) |
| Wed 03:30–10:00 | **run B** | 10 s confirm gate for A (300 games) | 08:00: switch to gates: A vs V4 600 at 5 s; then S batch 10 s confirm if not yet done | – |
| Wed 10:00–14:00 | export B, diag | B 10 s gate | B vs V4 and B vs A at 5 s (600 each); proxies for the winning net (40) and for S (40); book analysis on the remaining cores | assembly of candidate V5 = V4 engine + S (if gated) + best net + book |
| Wed 14:00–19:00 | book grading (Stockfish 120k) and pruning | idle for the pressure set | 1,000-game regression V5 vs V4 at 5 s | P speed pass only if everything above is green by 14:00 |
| Wed 19:00–22:00 | **battery on the exact zip** (section 3.5), package, byte-check, fresh-extraction game | – | proxies for the final zip if not done | hand-over note; rollback zip (V4, and V5 without book) tagged |
| **Wed 22:00** | **freeze; Archit uploads V5 tonight or Thu 08:00** | run C data through 22:00 collected | – | – |
| Wed 22:00–Thu 06:00 | **run C** (SCReLU + output buckets, all data) | generators to 06:00 | S1 to 06:00 | – |
| Thu 06:00–14:00 | export C | C 10 s gate | C vs V5 600 at 5 s; proxies 40 | – |
| Thu 14:00–18:00 | battery on V5.1 if C clears +30 with the interval clear of zero and no proxy regression | – | – | **final upload by Thu 18:00**; otherwise V5 stands |
| Fri before 11:00 | rollback only, on platform telemetry | – | – | – |

Slips move the hand-over, never the battery. If run A is not exported by Wed 05:00, run B is
skipped and A is the only net candidate; if neither net beats V4 clearly by Wed 16:00, V5 ships
with V3's net plus S and B.

---

## 7. Risks and what neutralises them

| Risk | Effect | Mitigation |
|---|---|---|
| x86 box not provisioned by Tue 22:00 | self-play volume 1/4; gates slower | plan runs on VM volumes (section 4.2); gates at 4 workers overnight; the net bet rests on the mix and endgames rather than volume |
| Trainer stays at 33k rows/s | one run instead of two before the freeze | fix is first; fallback caps Lichess to the newest 100M rows for run A only |
| Net flattens again (compressed scores, middlegame loss up) | a net that wins static tests and loses games | pilot with 40 games before the run; the diagnostic match (tools/diag_match.py, Stockfish-graded per phase) on every candidate; site ×4 not ×12; V4 balanced stream excluded; λ only on self-play |
| Search batch is neutral or negative | no S gain | split rule; correction history alone is the item most likely to carry; nothing ships un-gated |
| Compile creeps past 40 s | init risk | compile_profile after every jitted change; drop the two-slot TT first, then capture history |
| Mac thrash (8 GB) | polluted gates, stalled training | Mac runs the trainer and nothing else; every other job has another machine; load check before any launch |
| Book challenged | disqualification risk | our own engine's output only, builder + log + grader report in the repo, README section, organiser email; no-book zip as rollback |
| Rescale/scale bug in a new net | margins wrong, weird play | slope check in `net_diag` before any gate; the blunder set at the platform budget in every gate |
| Working-copy deletion, shell self-kills | hours lost | every destructive step through a script that lists its target; kill patterns live in files |

---

## 8. What we are not doing, and why

- A bigger net or a second layer: data-limited and speed-limited; the shipped inference path is
  proven and the compile budget is precious.
- Fine-tuning v3b on a small distribution-shifted set at a high learning rate: that is what
  flattened V4's nets.
- SPSA on search constants: needs tens of thousands of games; the Monday run was flat.
- Syzygy tablebases: 4-men fit but the search already converts; a KPK bitbase is an idle-hours item.
- Adaptive contempt/opponent modelling: parked on evidence (PLAN_V4 s18).
- Anything that is not through its gate and the battery by Wednesday 22:00, except run C for the
  Thursday V5.1 slot.

---

## 9. Actions for Archit, now

1. **Provision the x86 box** (30 min): GCP → Compute Engine → e2-standard-8 (8 vCPU, 32 GB) or
   c3-standard-8, Ubuntu 22.04, 100 GB disk, region europe-west2; add your ssh key; put the alias
   in ~/.ssh/config as `gcp-x86` and tell Claude. Claude runs the provisioning script (Stockfish
   from source, the starter venv, the tools) from ~/chess/provision.log's recipe.
2. **Confirm V4 is live** and bring back the first two validation-log lines (init seconds,
   nodes/s) and the first rated log.
3. **Send the organiser email** about the book (drafted Monday). Ship-unless-objected by Wed 20:00.
4. **Keep the Mac free**: close browsers and IDE processes that page; no other work on it while a
   run is going. The 8 GB is the reason V4's gates were unreadable.
5. Be reachable Wed 21:00–23:00 for the upload, and Thu 14:00–18:00 for V5.1.

---

## 10. Honest expectation against the directive

| Outcome | Build | Ladder today | Probability |
|---|---|---|---|
| Everything lands | V4 + N (≥ +80) + S + B + P | 2500–2560 | 0.2 |
| Net modest, search and book land | V4 + N (+30) + S + B | 2420–2480 | 0.35 |
| Net fails, search and book land | V4 + S + B | 2380–2440 | 0.25 |
| Only the book lands | V4 + B | 2320–2360 | 0.15 |
| Nothing gates | V4 | 2300 | 0.05 |

The directive asks for 2500–2700 comfortably. This plan gives roughly a one-in-five chance of
the lower edge of that band by Wednesday night and a better chance by Thursday if run C lands,
and it raises the floor to a solid top-ten seed in every branch. The band's ceiling (AlphaFish
at 2662 with 0.0% blunders over 2,500 moves) is not reachable by any single 33-hour step from a
net that misreads closed structures by 100 cp; it is reachable by the loop in this plan run for
two more cycles, which the Thursday slot gives us one of.

What would change the odds most, in order: the x86 box tonight (volume for N), the trainer
throughput fix (two runs instead of one), and the discipline of section 5 (gates that can see
what we are shipping). None of the three is chess; all three are why V4 fell short.

---

## 11. Definition of done for V5

- Net: beats V4 by ≥ +30 at 5 s (interval clear of zero), not negative at 10 s, proxy ≥ 40%,
  blunder set passes at the platform budget, diagnostic match shows no middlegame flattening
  (middlegame loss per move within 5 cp of V4's).
- Search batch: ≥ +25 at 5 s, not negative at 10 s, proxy not worse, compile ≤ 40 s local.
- Book: ≥ 2,000 graded entries, none losing > 15 cp against the grader, wrapper-state test passes,
  organisers informed.
- Assembly: 1,000-game regression vs V4 not negative; battery all green; zip byte-identical to
  sources; fresh-extraction game clean; rollback zips tagged (V4; V5 without book).
- Upload Wednesday night or Thursday 08:00; V5.1 Thursday by 18:00 only on ≥ +30 clear.

---

## 12. Solidified for a Wednesday-evening hand-over (Tue 8 Sept, 14:00)

Decisions taken with Archit at 13:30: hand-over Wednesday evening (not Thursday); machines are
GCP + Oracle VM + Mac only (no Colab); the whole Mac is Claude's; V4.5 is paused and its useful
data is reused; the aim is a system that lands comfortably in the top five with a real chance
at first.

### 12.1 What was done at 13:30–14:00 (setup only, no engine code)

- **Mac.** The V4.5 afternoon queue and the drawishness gate were stopped. Final tally of the
  drawishness rule vs V4: +35 =116 −34 over 185 games, 50.3% (+2 ±50): **neutral, dropped for
  good.** Nothing heavy runs on the Mac now (load 3.5 from the IDE and dashboard only).
- **Oracle VM.** All 6,218 scraped site games copied over (it had 1,158). The two V4.5
  decisive workers (curated roots + random walk, `data/selfplay/dec`, ~0.7M rows) were stopped;
  their chunks are kept and go into the V5 mix. Three **S1 workers** now run in the V5 recipe
  (`~/chess/vm_start_s1.sh`: starts at random plies 8–40 of the site's games, 2–6 ply random walk
  with p = 0.5, Stockfish 19 depth 9, quiet-resolved, adjudicated at ±800, score-balanced,
  output `data/selfplay/dec2`, worker ids 60–62) at 60–85 positions/s each, plus the depth-12
  endgame worker (eg2, 8 chunks so far). Expected: ~0.8M S1 rows per hour from the VM alone.
- **x86 box.** `bini_v4/tools/provision_x86.sh <alias>` provisions any Ubuntu x86 box in ~10
  minutes from the Mac (Stockfish 19 built from the sf_19 tag with AVX2, the platform's package
  versions in two venvs, the engine, tools, site games, site-labelled and hard sets; ends with a
  compile-and-move smoke test), and `tools/x86_start_s1.sh` starts eight S1 workers (ids 70–77).
  `tools/pull_selfplay.sh` will pull from both machines.

**GCP steps for Archit (15 minutes):** console → Compute Engine → Create instance → name
`bini-x86`, region europe-west2, machine type **c3-standard-8** (or e2-standard-8 if c3 is not
allowed on the trial), boot disk Ubuntu 22.04 LTS, 100 GB balanced disk; under Security add your
public ssh key (`cat ~/.ssh/id_ed25519.pub` on this Mac); create; note the external IP; add to
`~/.ssh/config`:

```
Host gcp-x86
  HostName <external ip>
  User <the username in your key's comment>
  IdentityFile ~/.ssh/id_ed25519
```

then tell Claude "gcp-x86 is up". The trial's default quota allows 8 vCPUs in one region, which
is exactly this box. Cost about £0.35 an hour; stop it Friday.

### 12.2 V4.5 work that carries into V5

| From V4.5 | Reused as |
|---|---|
| decisive stream `dec` (random walks from curated roots, ~0.7M rows) | part of the self-play set in every V5 run |
| endgame stream `eg2` (depth 12, resolved, ~1.5M rows) | S2 in every run |
| `--random-open`, `--balance`, `--adj-cp`, `--resolve` in the generator | the S1 recipe (no new generator code was needed) |
| `--thin-flat`, `--max-chunks`, `--scale`, `--out-scale`, per-source validation in the trainer | used as is |
| `net_diag.py` slope report, `diag_match.py` per-phase grading, `grade_export.sh` | the sanity checks on every export |
| the soft-clock build (`BINI_SOFT_STOP`) | **not** carried: its proxy pair never ran cleanly and the clock is not where points are lost |
| drawishness rule (`BINI_DRAWISH`) | dropped (neutral at 185 games) |
| the book hook in the wrapper and `make_book.py`, `book_check.py` | the base of B |

### 12.3 Schedule to the Wednesday-evening hand-over

The Thursday run C is removed from the critical path: it becomes a V5.1 only if the platform's
Thursday games show a defect or if C is clearly better by Thursday noon; otherwise V5 stands.

| When | Mac | VM | x86 box (from when Archit says it is up) | Claude |
|---|---|---|---|---|
| Tue 14:00–16:30 | trainer throughput fix and verification on one chunk; depth-25 replay of the four slides (10 min) | S1 + eg2 | provision → 8 S1 workers | trainer fix; slide replay; S3 labelling script queued on the VM |
| Tue 16:30–19:00 | **pilot A** (1 epoch, 20 chunks) → export → diag | 40-game pilot vs V4 (generators paused 20 min) | S1 | correction history + pawn key (S item 1) written and unit-tested |
| Tue 19:00 | **run A starts** (6 epochs, ends ~01:00 at ≥ 90k rows/s) | S1 + eg2 | S1 | S items 2–5 written; book position list from the 6,218 games |
| Tue 22:00–Wed 01:00 | run A | generators paused; **S-batch gate 300 games at 10 s** (4 workers) | S1 | – |
| Wed 01:00–01:30 | export A (scale-matched), diag, blunder set | generators resume | S1 | pilot B |
| Wed 01:30–08:00 | **run B** (A + λ 0.75 on self-play + all S1 rows banked by 01:00) | S1 + eg2 | S1 until 08:00 | – |
| Wed 08:00–11:00 | run B | A 10 s gate (300) | **A vs V4 600 at 5 s; S batch 600 at 5 s** | S-batch split gates if needed |
| Wed 11:00–14:00 | export B; book analysis (2 cores) | B 10 s gate | B vs V4 and B vs A at 5 s; then 40 real-clock proxies for the best net and for S | assemble candidate V5 |
| Wed 14:00–17:00 | book grading (Stockfish 120k) | – | 1,000-game regression V5 vs V4 at 5 s | speed pass only if all green by 14:00 |
| Wed 17:00–20:30 | **battery on the exact zip** (section 3.5), package, byte-check, fresh-extraction game | – | proxies for the final zip | hand-over note, rollback zips |
| **Wed 20:30–21:30** | **hand-over; Archit uploads** | – | – | – |
| Wed 22:00–Thu 08:00 | run C (SCReLU + output buckets, all data) on the idle GPU | S1 | S1 | – |
| Thu | Thursday's rated rounds are the acceptance test of V5; C gated only if V5 shows a defect or C is ≥ +30 clear by noon | – | – | rollback-only after 18:00 |

If the x86 box is not up by Tue 20:00: the S-batch 5 s gates move to the VM (4 workers,
overnight), the real-clock proxies run on the Mac beside training at 2 workers (the one
combination that worked in V4), and run B trains on VM volume (~8M S1 rows).

### 12.4 What "comfortably top five, a real chance at first" needs, stated as numbers

- Top five today is 2519+; first is 2662. Our 2306 needs +215 for the band and +360 for first.
- Section 2's levers sum to +100 to +260 if everything lands. So: top five is the realistic
  target of this hand-over **if the net lands** (N ≥ +60) and S and B ship; first place needs a
  second cycle of the same loop (Thursday's run C at best, more likely beyond this event), or
  AlphaFish to lose a knockout game, which its R48–R50 form (two losses and an init failure in
  three rounds) says is possible.
- The Swiss and knockout reward consistency over peak strength: a V5 that never loses to the
  2100–2400 band and draws the top five is a semi-finalist. That is the shape being built.

### 12.5 Hourly reverse-engineering of the top ten (Archit's question, 14:05)

The intel pipeline already does most of this: `intel/refresh.sh --auto` re-scrapes every team's
games with the site's Stockfish-16 evaluations, re-renders the dossiers and STRATEGY.txt every
three hours, and `intel/snapshot.py` takes an hourly ladder snapshot. Two changes are worth
making, and both feed the build rather than the reading:

1. **Hourly game scrape into the cache** (not the full report): every new rated game of the top
   thirty lands in `intel/raw/cache/games` within the hour. That cache is now a training input
   (S1 start positions, the site-labelled set, the book's line tree), so every hour adds a few
   hundred depth-16-labelled positions in the tournament's own distribution and new lines for
   the book. Cheap: scrape only, no analysis.
2. **The strategy report stays three-hourly**, with one added table: the top ten's results by
   opening family and by game length, refreshed as the field re-uploads. It tells us which
   families to weight in the gate openings, nothing more; per-opponent behaviour cannot be used
   at the board (we see a FEN and a clock), so an hourly report would be read, not acted on.

## 13. Execution log (Tue 8 Sept, from 13:30)

- 13:30 Mac cleared (V4.5 queue and draw gate stopped; drawishness rule neutral at 185 games,
  dropped). VM: all 6,218 site games copied; three S1 workers (dec2, ids 60–62, 60–85 pos/s each)
  + the eg2 endgame worker.
- 13:41 **x86 box up** (Archit created it: 8 vCPU Sapphire Rapids, 31 GB, `gcp-x86`, user forge).
  Provisioned by `tools/provision_x86.sh` in 8 minutes: Stockfish 19 (avx512) at 1.09M nodes/s
  per core, both venvs, engine, tools, site games; smoke test compiled in 22.6 s and played a
  move. Eight S1 workers (ids 70–77) at ~100 pos/s each: **~2.9M rows/h** from the box, ~0.8M/h
  from the VM. `tools/pull_loop.sh` pulls both every 10 minutes.
- 13:45 Trainer benchmark on the quiet Mac: ~200k rows/s (the 33k/s of V4 was load, not the
  code). A 170M-row epoch is ~15 min. No trainer fix needed. Found and fixed a shadowing bug on
  the way: `tools/profile.py` shadowed the standard library's `profile` when a tool ran from
  `tools/`, and torch's import died; renamed to `profile_engine.py` (the footgun list strikes
  again).
- 13:50 **Slide replay** (the four losses' slide positions, our engine at 3/20/60 s):
  the net's static evaluation is off by 100–250 cp in every one (R64 ply 21: static −281,
  truth −74; R55 ply 40: static +150, truth +28; R56 ply 47/63: +51/+68, truth −43/−17). Depth
  pulls the *score* toward the truth and sometimes the move (R65's Bxh3?? is replaced by Re8 at
  20 s; R64's f3?? by Rc1 even at 3 s with a fresh table), but R55/R64's positional choices stand
  at 60 s. Verdict: the evaluation is the lever; correction history is the right runtime patch;
  the book's clock savings buy the depth that fixed two of the four.
- 13:55 `bini_v5/` working copy created from bini_v4final. **Correction history implemented**
  (pawn-structure and material-configuration tables hashed from the bitboards, no board-module
  change, stored at the tail of the `scores` array so no jitted signature changed; corrected
  static used in quiescence stand-pat, RFP, futility, null-move and the improving flag; update at
  node end when the bound agrees and the best move is quiet). Suites running.
- 14:00 Pilot A training (1 epoch, Lichess capped at 36 chunks, full small sets), ~10 min.
- 14:05 Background intel agent launched (scrape + render, hourly loop, no engines) per Archit.
- 14:00 Pilot A done (1 epoch, 55M rows, 874 s = ~150k rows/s beside other jobs): site chunk
  MAE 166 after one partial epoch (v3b 145 after six full ones). Pipeline sane; export fine.
  Judge running (slope, scale-matched export, exactness, blunder set, 40 games at 5 s on the VM).
- 14:05 **Run A started** (6 epochs, 328 chunks/epoch: all 202 Lichess + elite ×2 + eg2 ×2 +
  site ×4 + dec ×2 + hard ×10; dec2 had no finished chunk yet). ETA ~16:45 at ~27 min/epoch.
  The trainer is 3–4× faster than V4's runs, so **the GPU is not the bottleneck; self-play
  volume is**. Revised: run B ~17:00 (with ~10M dec2 rows), run C ~20:00 (~22M), run D overnight
  (~50M); each judged by games as it lands, the best one at Wed 14:00 ships.
- 14:05 Book analysis: 1,275 positions (≥ 5 occurrences within 10 plies of a root, from 6,253
  games), two workers on the Mac at 30 s each (V4 net), ~5 h. Grading follows on the x86 box.
- 14:10 Correction-history speed check moved to the x86 box with the generators paused: Mac
  benches under the training load were noise (V5 452 vs V4 291 knps side by side, the reverse
  of the sequential run). The 8/11 tactics result is under the same suspicion; rerun on x86.
- 14:20 **x86 quiet-box results.** Correction history alone: 743 vs 725 knps (V4), tactics 9/11
  = V4; the Mac's "40% slowdown" was load. Full batch (correction + continuation history with
  history pruning and history-driven LMR + SEE pruning in the main search, all behind switches
  BINI_CORR/BINI_CONT/BINI_SEEP): 696 knps (−4%), **tactics 10/11 (V4 9/11: WAC.001 now
  solved)**, mates 80/80, blunder set 2/3 (= V4). Puzzles running. Gate: 300 games at 10 s on
  the VM queued behind the pilot.
- 14:25 **The Mac's 8 GB bit again.** Run A stalled at 1–4% CPU: the trainer's MPS buffers pin
  ~2.3 GB wired, VS Code's helpers hold ~2.3 GB, Spotlight is indexing the data folder, swap was
  7.7 GB of 9.2 GB. Book workers moved to the x86 box (two of its eight generator slots); the
  judge's Mac-side tests finished; trainer now frees the MPS cache every chunk and validates on
  20k rows per set. Run A restarted 14:27. Rule restated in bold: the Mac runs the trainer and
  nothing else; every test, gate and analysis runs on the VM or the x86 box.
- 14:30 Pilot net (1 epoch, a third of Lichess): sane values (queen up +1052, picks the site's
  best b4 in the R55 slide position) but 0/12 at 5 s vs V4: a one-epoch net is that weak.
  Pipeline proven; games stopped to give the VM to the search gate. The x86 CPU trainer benchmark:
  5.4k rows/s (30× slower than the Mac's GPU): **the Mac is the only trainer**; it needs the other
  apps closed (asked Archit).
- 14:32 **S-batch gate started on the VM** (bini_v5 all switches on vs V4, 300 games at 10 s,
  generators paused). Run A at 10 s/chunk (~55 min/epoch, ETA ~19:45).
- 14:35 Intel brief (`intel/V5_INTEL_20260908_1409.txt`, hourly loop live, podium parser fixed):
  ladder 13:00 AlphaFish 2688, PSL God Matt Bomer 2621 (new #2), multi millionare 2539; top-5 bar
  2521; us 2332 (#18). Our build since R50: CPL 13.7, blunders 0.3%, 21 s left; AlphaFish 7.8.
  **All four losses are slides and our evaluation fell under −100 by ply 23–31**: the damage is
  done in the opening/early middlegame, 5–10 plies after the book's current reach. Consequence:
  a deeper book (lines to 16 plies from the root where the field repeats them) is queued behind
  the first pass. Field-wide the top teams lose the same way (slides, not blunders); the ones
  with clock trouble are multi millionare, AI Fellow, ms.
- 14:50 Compile on the x86 box (quiet): V5 24.8 s, V4 22.5 s (platform V4: 31 s) → V5 ~34 s of
  the 90 s budget. Book pass 1 at ~22 s/position, ETA ~18:10; pass 2 (1,554 positions seen 3–4
  times) queued behind it at 20 s. `tools/book_merge.py` merges and grades (drop > 15 cp).
  Generators: ~1.4M S1 rows in flight (x86 945k, VM 477k); first chunks land ~15:00.
- 15:00 Tooling ready for the evening: `tools/x86_gate.sh` (8-worker 5 s gates on the x86 box,
  generators and book paused), `tools/x86_proxy.sh` (real-clock proxies there), `tools/vm_gate.sh`
  (10 s on the VM), `tools/judge_net.sh` (net → scale-matched candidate → games), trainer
  `--wdl-dir` (result blend per source; site results are bot results and stay out),
  `tools/run_v5b.sh` (run A + λ 0.75 on self-play only). Run A: 8 s/chunk, ETA ~18:50. S gate:
  8/300 at 15:00. Evening order: S gate result ~17:30 → run A judge on x86 (400 at 5 s) and VM
  (300 at 10 s) → run B starts the moment run A exports → proxies overnight.
- 16:25 **S-batch gate final: 39.5% (−74 ±40) over 300 at 10 s. Negative.** First single-item
  screen (x86, 150 at 5 s): correction history alone **31.9% (−132 ±61)**: it is the culprit.
  Cause found by inspection: the update step was ~40× Stockfish's (bonus = error × depth × 8 in
  1/64 cp units, cap 3072), so a table entry saturated to ±48 cp after a handful of noisy
  updates and the applied correction swung by up to ±96 cp. Rescaled (bonus = error × depth / 4,
  cap 2048, applied /64: at most ±64 cp in total, 0.6% per update for a 10 cp error at depth 5)
  and queued for a 150-game re-screen behind the continuation-history and SEE screens. If it is
  not clearly positive on the re-screen it is dropped; the other two items ship only if their
  screens are positive and a combined 300-game gate confirms.
- 16:25 VM generators resumed after the gate (they had been paused for 1h50: the VM gate's real
  cost). Live build (V4): R66 W vs test_bot (2334), R67 L vs FuzzyBot (2349, slide from +103 to
  −173 in the middlegame), R68 L vs cory (2343, 163-ply slide, 10 s left at the end). Rank 18.
- 17:05 Archit's two changes: draw trigger raised to −100 (our net reads level as −40 to −150);
  dry run over the 28 logged rated games with site evaluations: fires in 9 games, 7 losses where
  Stockfish agreed we were worse, 2 draws, no wins touched. Live build recorded as V3 (bini-2.0)
  in V4 Progress.md; V4 was never uploaded; candidates are gated against V3's net as before.
  Draw-policy gates tonight on the x86 box: vs full-strength Stockfish (draws must rise) and vs
  Stockfish at UCI_Elo 1800–2000 (draw rate must not rise).
- 17:20 **Re-plan of the x86 box (no second box available).** Screens moved off it: continuation
  history final 48.4% (−11 ±61) at 129 games → **dropped**; SEE pruning and the rescaled
  correction history screen on the VM (100 games at 5 s each). The x86 box now runs 4 S1 + 2
  endgame (eg3: site games from ply 40, depth 12, resolved) + 2 book workers, and pauses only for
  run A's 400-game gate. The draw-policy gates no longer pause the generators (5 cores). Night
  chain armed (`tools/night_chain.sh`): run A exports → local judge (slope, scale-matched export,
  exactness, blunder set incl. today's positions) → **run B starts on the GPU** → run A 400 at 5 s
  on x86 → draw-policy gates on x86 → run A 300 at 10 s on the VM → run A real-clock proxy (40 at
  20k) on x86. A trainer stall monitor watches the Mac. Two self-inflicted incidents avoided
  from here on: kill patterns live in script files (an inline `pkill -f runner.py` killed its
  own ssh shell), and the V5 tools folder now carries the current generator.

## 14. Reverse-engineering the top eight (Tue 8 Sept, 18:30, from the site's evaluations)

| Team (rating) | What they do right | What they do wrong | Our response |
|---|---|---|---|
| AlphaFish 2688 | one blunder in 38 games; endgame 7.4 cp/move (best in the field); 82-move games; 16/38 draws; fixed 4% clock, 27 s left | plays instantly on a mate score and has repeated with a mate on the board (R32); a fixed clock share cannot spend more on a critical move; lost to an init failure (R50); slides vs test_bot/Capablanca | draw policy (take the repetition it offers when we are worse); danger multiplier keeps our depth on the swings it cannot afford; endgame stream + piece-count outputs (run C) for the after-move-40 phase where it is best |
| PSL God Matt Bomer 2621 | 71% vs sub-2100, 69% vs 2500+; rating built on not losing upward (6 of 8 losses are slides) | 11 blunders in 38 games (0.7%), CPL 11.1: the worst move quality in the top three | our depth punishes blunders; play the game out when better (contempt stays 20 when ahead) |
| Capablanca 2588 | best opening play (7.6 cp), 17/37 draws, 88% vs sub-2100, no build resets | 10 of 11 losses are slides vs 2400+; 45% in the 2300–2499 band | book neutralises its opening edge; same slide fix as ours |
| multi millionare 2568 | 15 repetition draws, no loss to a strong opponent; 79% in 2300–2499 | CPL 18.4 (worst in the top ten), middlegame 16.1, 13 s left at the end, 9 of 14 losses tagged with clock trouble, 5 blunders | never accept its repetitions when we are better; long games and complications are lethal to it; our depth finds its 0.9% blunders |
| ms 2564 | 100% in 2300–2499; solid | all 14 losses are slides; 15 s left | the slide fix; keep games long |
| cory 2512 | 168-ply games, patient | CPL 14.2, 10 slides, 12% in Caro-Kann | nothing special: it is beatable by quality |
| SoberPaschoud 2511 | opening 6.5 cp (best), 87% vs sub-2100 | **endgame 12.0 cp/move**, 40% vs 2500+, 11 slides, one flag | long games into endgames; our endgame data targets exactly its weak phase |
| AI Fellow 2498 | CPL 9.2, Ruy Lopez 93% | **10 s left at the end**, 5 of 9 losses with clock trouble, repeats while ahead (4 times) | keep games long; when worse, steer for repetition: it accepts |

Cross-cutting facts that decide what to build:
1. **Nobody at the top blunders; everyone loses by slides.** 61 of the top eight's 82 losses are slides. The slide fix (the network) is therefore the whole field's weakness, not only ours, and the team that fixes it first pulls away.
2. **Ratings are made by draw discipline, not by move quality.** PSL (11.1 cp, 11 blunders) is rated above Capablanca (10.2); multi millionare (18.4) sits at 2568 on 15 repetition draws. Our 12.8 cp per move is inside the top group; our 0-1-3 against 2450+ is the rating gap. The draw policy is worth more than any search item.
3. **Every top engine spends a fixed share of the clock and thins after move 40**; three of the top eight end games under 15 s. Long, complicated games favour whoever keeps depth late: with the book saving the opening clock and our danger multiplier, that is us.
4. **The failures that end games outright** (30 in the cache: 12 flags, 10 illegal, 4 init, 3 crashes) never happen to us: 42 rated games clean. That is a standing 30–50 point edge over the field's average and must not be traded for anything.

Added to V5 from this (each gated): the draw policy at −100 after move 20 (done, gates tonight); the book (in progress); the endgame stream and run C's piece-count outputs (running/queued). Considered and parked: opponent-clock-aware "grind mode" (their remaining clock is observable from wall time between our calls; worth building for Thursday only if the Wednesday battery is clean early), adaptive contempt (noise, PLAN_V4 s18), tablebases (wrong phase).
- 18:05 Rescaled correction history: 48.5% (−10 ±69) over 100 at 5 s → **dropped**. Search batch
  for V5 is SEE pruning only (54.0%, +28 ±69), decided by the combined 300-game gate of the
  assembled candidate. The V5 engine ships with BINI_CORR=0, BINI_CONT=0, BINI_SEEP=1 baked in.
- 18:25 **Run A checkpoint (epoch 4, 40 games at 5 s vs V3's net): 31.2% (+6 =13 −21). Failed
  the 40% line. Run A stopped; run B not started.** Its epoch table (site / self-play / Lichess
  MAE): 150/208/190, 144/203/183, 137/200/178, 136/204/174, 132/192/175: better than v3b on
  every static number, worse by ~140 Elo in play. That is the third from-scratch or full-mix net
  to do this (v4a, v4b, run A). Pivot, evidence-based: the only nets that gained games this week
  came from the v3 line (quiet Lichess) fine-tuned on Stockfish-labelled human whole-game
  positions (v3b, +39). **Run D** = v3b resumed at 5e-4 for 2 epochs on all quiet Lichess +
  elite whole-game ×10 + the resolved endgame streams ×2 + the hard set ×10; no site set, no
  self-play, no result blend. Checkpointed by 40 games after every epoch (pass 45%; the run is
  killed below it). The x86 box now labels 3M more elite positions (2025-05, depth 10) for run E
  (the same recipe with three times the whole-game data), overnight. The from-scratch line
  returns only with the wider evaluation scale in the loss and an epoch-one game check, after D/E.
- 18:40 Smoke tests passed: `x86_gate.sh` (the 40-game checkpoint itself), `x86_proxy.sh`
  (8 real-clock games, 25–37%, min clock 8.6 s), `judge_net.sh` VM path (8 games). Elite
  labeller running: 3,000,027 positions sampled from Lichess Elite 2025-05, four workers at
  depth 10. Run D at 7 s/chunk, epoch 0 ends ~19:05, first game checkpoint ~19:30.
- 19:25 **Run D epoch-0 checkpoint: 37.5% (+6 =18 −16) over 40 at 5 s vs v3b; killed by the
  rule.** Its static numbers were again better (site 135, elite 123, endgame 1–4 pieces 136 vs
  v3b's 184). A gentle fine-tune of v3b should sit near 50%; −89 says something systematic. The
  one factor every losing net shares and v3b lacks: the rewritten V4 trainer plus the 0.85 label
  scaling on Stockfish-labelled sets. **Run D3** (19:35): v3b's exact recipe (resume v3b, Lichess
  + elite ×10, labels unscaled) with the current trainer, one fully annealed pass at 3e-4, then
  the 40-game checkpoint. Holds 50% → trainer sound, the added data/scaling is the culprit and
  D2 (D3 + endgame streams, unscaled) follows. Fails → the trainer is the culprit and the v3b-era
  trainer (bini_v3b/tools) takes over for the night's runs. Second GCP box (`gcp-x86b`, Debian
  13, same CPU) provisioned 19:13; it hosts the gates and eight S1 generators; box A labels elite
  games (600k of 3M at 19:30) and runs the endgame and book workers.
- 19:55 Controls (Archit): (a) v3b.pt re-exported through the current export path vs the original
  file, (b) v3b vs itself, 40 games each on box B. The first attempt at (a) silently played v3b vs
  v3b: `export_from_pt.py` loaded the old checkpoint's `out.*` keys strictly and failed; fixed
  (keys mapped as the trainer does), rerun. Numerically the re-export equals the original file in
  every weight (w1, b1, w2, b2 max diff 0; only w2's header shape differs), so the export path is
  cleared; the games now test the gate host. D3 (v3b's recipe, current trainer) at 11 s/chunk,
  verdict ~20:40.
- 20:10 **Controls decided the measurement question.** (b) v3b vs v3b on box B: 48.8% over 40.
  (a) v3b re-exported through the current path vs the original file: 39.7% over 39, although the
  two files are bit-identical in every static evaluation and every fixed-depth search (600
  positions). Two identical engines, 40 games, nine points apart: a 40-game gate resolves ±12
  points, so run D's 37.5% and run A's 31% were weak evidence, and the day's 100–150-game
  screens were near noise. Rules from here: every checkpoint is 200 games (±7 points), a ship
  candidate needs 400+, and nothing is called "dropped" or "failed" on fewer. Run D's epoch-0
  net gets 200 games on the VM now; D3 gets 200 on box B when it exports (~20:35).
- 20:20 Control (a) final: 40.0% (+7 =18 −15) over 40 for a bit-identical engine. Run A's
  epoch-4 net now also gets 200 games (box A, labellers paused ~50 min) so the from-scratch line
  is judged at the same resolution as the others before run B is ruled in or out.
- 20:50 **Two evaluation levers that do not retrain the whole net**, both gated at 200 games:
  (1) *Calibration table*: v3b's median residual against the site's depth-16 labels by piece
  count × material imbalance (300k positions, slope 1.083, 128 non-zero cells, e.g. −212/+226 cp
  at 4 pieces with a two-pawn imbalance: the net over-values a minor piece against a pawn in
  trivial endings). Baked as constants in `bini_calib.py`, applied in `evaluate()` behind
  `BINI_CALIB`; candidate `bini_cand_calib` (v3b net, calibration only) queued on box A behind
  run A's 200. (2) *Last-layer refit*: v3b's feature layer frozen, only the 1,024 output
  weights refitted on the site's own labelled positions + elite whole-game chunks
  (`tools/refit_output.py`, GPU, minutes); judged with 200 games on box B after D3.
  200-game runs in flight: D3 (box B), run A e4 (box A: 34.9% at 96), run D e0 (VM: 42.9% at 56).
- 21:00 200-game verdicts so far: **run A e4 (from scratch, full mix): 35.5% (−104 ±51)**, the
  from-scratch line is genuinely behind and is closed for tonight. D3 (v3b's recipe, current
  trainer) 47.4% at 133 and run D e0 (v3b + endgames) 46.1% at 114: fine-tunes of v3b are level
  within noise, so the trainer is sound and the 40-game verdicts of the afternoon were noise.
  Reading: whole-net retraining does not beat v3b tonight; the remaining net levers are the
  last-layer refit (paper 123 cp), the calibration table, and run E (v3b + 4× whole-game data,
  started 21:00 on the current trainer, one annealed pass, 200-game checkpoint).
- 21:05 **D3 final: 48.2% (−12 ±48) over 200.** v3b's recipe rerun on the current trainer is
  level with v3b: the trainer is sound, the export path is sound (control a), the host is sound
  (control b). What has failed is the data added to the recipe (site set, self-play, result
  blends), not the tooling. Refit-net gate now running on box B; calibration on box A; run E
  trains.
- 21:20 Run D final 44.0% (−42 ±49): dropped. Calibration 50.7% at 142, refit 49.4% at 79.
  **Run E stalled on the Mac at chunk 141/250** (3.7% CPU, 91 MB free, a browser and system
  helpers holding memory): killed; it reruns on the GPU box the moment it exists. The Mac is no
  longer a trainer in this plan (Prometheus s2).
- 21:35 **V5.0 candidate assembled** (`bini_v50`): V5 engine with v3b's net, the draw policy
  (−100 after move 20), the graded book (4,926 entries; the smoke test played the book move
  instantly at move 1), SEE pruning on, correction/continuation history and the calibration
  table off, midgame boost off. Its 400-game gate vs V3's engine is queued on box A behind the
  calibration gate (calibration 50.3% at 151, refit 49.4% at 88: both level so far). GPU-box
  tooling written: `provision_gpu.sh` (CUDA torch, Leela built with the CUDA backend, Stockfish
  fallback), `leela_net.sh`, `label_leela.py` (K lc0 processes, `go nodes 1`, WDL → cp, our chunk
  format). Waiting on the instance.
- 21:50 Calibration table final: **52.8% (+63 =85 −52, +19 ±49) over 200**: the first net-side
  candidate above 50; extended to 400 behind V5.0's gate. Draw policy vs Stockfish 2000 (rule
  on): 98% at 49/100 with two draws, i.e. the rule does not create draws against weaker
  opponents (rule-off half follows). V5.0's 400-game gate vs V3's engine started on box A.
- 22:00 Last-layer refit final: 50.7% (+5 ±48) over 200: level, not shipped. Net-side scoreboard
  at 200 games vs v3b: calibration 52.8% (to 400), refit 50.7%, D3 48.2%, D 44.0%, A 35.5%.
  Pressure draw gate (full-strength Stockfish, rule on/off) starting on box B; V5.0's 400 on A.
- 22:00 VS Code crashed and took the session's watchers with it; every real job survived
  (all launched with nohup): V5.0's 400-game gate on box A (54.8% at 168, +33 ±53), the
  full-strength pressure draw gate on box B (6 of 10 games each side), the labellers, book and
  endgame workers, the generators on B and the VM, the pull loop and the hourly intel loop.
  **Draw-rate gate vs Stockfish 2000 final: rule on 98.5% (+97 =3 −0), rule off 98.0%
  (+96 =4 −0): the rule does not raise the draw rate against weaker opponents. PASS.**
  Watchers re-armed; the calibration extension still queues behind V5.0's gate.
- 22:20 **Pressure draw gate (full-strength Stockfish, 1.5M nodes, real clock, 10 games each):
  rule on 0-5-5 (min clock 8.8 s), rule off 0-4-6 (8.6 s).** Draws up by one, the right
  direction, within the noise of ten games; together with the dry run (7 of 9 qualifying losses
  would have been draws) and the no-cost check vs Stockfish 2000 (98.5% vs 98.0%), the draw
  policy stays in V5.0. Its net effect is also inside V5.0's 400-game gate (54.8% at 168).
- 22:46 **V5.0 vs V3's engine, 400 games at 5 s: 61.4% (+166 =159 −75), +80 ±35.** The first
  clear, significant gain of the week: v3b's net unchanged, with the draw policy (losses 75 vs
  wins 166), the graded book (fires from the curated roots) and SEE pruning. Confirmation ladder
  started: 300 at 10 s on the VM now, 40 real-clock proxies vs Stockfish 20k on box A after the
  calibration extension (~01:00–04:00; reference 46.3%), battery on the Mac Wednesday.
