# V4 — the plan (Monday 7 Sept 2026, 10:00)

Written after reading everything in the folder: the engine (bini_*), the training and labelling
tools, PLAN.md and its three follow-ups, all 24 platform logs, the intel corpus (top-20 dossiers,
Strategy 6, notes), the arena logs and the training logs. No code was changed. Uploads close
Friday 11:00; the Swiss on locked builds is Friday afternoon; the London knockout is Saturday.

## 0. Three things to know before anything else

1. **The leap build went live at 09:17 (upload v5, sha 9a2227…).** Rounds 46 and 47 were still
   v2.2 (no `rg` counter, 1.3 s first move). R48 vs TMS is the first leap game and shows the
   expected profile: `rg` on every line, 2.3 s first move (predictive stop at depth 14), 3–5.5 s
   on moves 10–16, 69 s left at move 20, mate found at move 31, 56 s left in a 34-move game;
   init 30.9 s, 580k nodes/s on a slower worker. Rating 2013, rank 33 of 355 after R48.
   V3 (v3b net) follows when its extension gate and battery finish, about 13:15.
2. **The gate extension is running** (bini_v3b vs bini, 115/300, 57.4%, +52 ±65 at 09:34;
   the first 300 gave +28 with the draw-aware interval clear of zero). The machine is saturated
   by it (load 8.9 on 8 cores); nothing heavy should start until the battery is through.
3. **The ladder is only a seed.** What matters is the build locked at 11:00 Friday. V4's job is
   to be that build, with a full battery behind it by Thursday afternoon.

## 1. Where the engine actually stands (evidence, not impressions)

| Component | State | Evidence |
|---|---|---|
| Board, move generation | perfect | perft exact, 20k-position differential, 0 illegal moves in 24 rated games |
| Speed | 700–850k nodes/s on the EPYC, depth 14–20 at 1–4 s, compile 25–29 s of 90 | every platform log |
| Search | PVS, TT, null-move+verification, LMR/LMP, RFP, futility, SEE, singular+multi-cut, IIR, qsearch TT, check extension | batch 1 measured +63; batch 2 (capture/continuation history) +5, excluded |
| Evaluation | NNUE 8 king buckets x 768 -> 512 x 2 -> 1, int16, one linear output; v3b = v3 fine-tuned on 1M whole-game positions | v2 +198 over HCE; v3 +34 over v2.1; v3b +28 over leap; both R43 blunders now avoided |
| Clock | front-loaded horizon 34 - 0.4n, danger multiplier, root guard | real-clock proxy: 30.0% -> 57.5% vs the same Stockfish; min clock 6.7 s in 10 pressure games |
| Robustness | zero failures, platform and local | 24 rated games, ~1,700 local games |
| Ladder | 1869, rank 54, 11-3-5; site ACPL on recent games 3–12 | dashboard, intel |

The single most important measurement of the weekend is the proxy result: **the same net and
search scored 27 points more against the same opponent just by spending the clock where the top
teams spend it.** That says our play is strongly depth-limited, which in turn says the evaluation
still has holes that depth papers over. It also says the top five, who play 1.3–1.5 s a move by
move 40, can be out-searched on the moves that decide games.

What is still wrong, in order of points lost:

1. **Sharp middlegames.** R36, R40, R43: the net over-values its own activity, the search prunes
   quiet refutations, and the root commits to a move Stockfish refutes at depth 20. v3b fixes the
   two R43 positions, but by fine-tuning on 1M positions from human games labelled at depth 10;
   the class of error is still under-represented in the data.
2. **The opening phase.** Our own moves 1–15 are our weakest phase (intel: 27 cp vs 4 cp after
   move 40). The curated positions drop us into theory at move 6–9 and we search them cold.
3. **Nothing else measurable.** Conversion (11/12 won positions mated), repetition discipline
   (never repeated while ahead), and the clock are sound.

## 2. What separates us from first place

AlphaFish: CPL 8.1 cp, one blunder in 2,370 moves, 13-6-0 against the top ten, no book, a flat
4% of the clock per move, converts 25/27. Anchoa 10.4, SoberElwood 10.1, test_bot 11.5,
Capablanca 11.3, all with blunder rates under 0.5%. Our v2-era games grade at 3–12 cp when calm
and 25–44 when the position turns sharp. In other words we are already at their level in
ordinary positions and a class below in the positions that decide games between equals.

An honest rating model, built from what we can measure:

| Build | Real-clock proxy (vs SF 10k nodes, CPL ~11) | Self-play delta | Where it likely lands |
|---|---|---|---|
| v2.2 (live now) | 30% | – | 2000–2150 once it meets the top 30 |
| v2.2 leap (zip ready) | 57.5% | +2 ±48 at 30 s (the cadence hides the clock) | 2150–2300 |
| V3 = leap + v3b | not yet measured (battery today) | +28 ±27 over leap | 2200–2350 |
| V4 as below | target ≥ 65% | target +80 to +150 over V3 | 2350–2550, top five; first if the sharp-position class closes |

"Comfortably top five" is a realistic V4 outcome. "First" needs AlphaFish's consistency
(blunder rate 0.0%) plus our time edge; the plan below is aimed at exactly those two numbers.

## 3. V4 in one paragraph

V4 is an evaluation rebuilt on the right data, with two cheap architectural upgrades, plus a
gated batch of search improvements, plus a measurement pipeline that grades every change on the
tournament's own opening positions. The data is the leap: today the net learns from human
positions that people asked Lichess to analyse; V4's net learns from engine games played from the
284 curated start positions we have scraped, labelled by Stockfish 19 at depth 9, and from the
131,092 positions the site itself has already evaluated at depth 16. That is the distribution
the Swiss will be played in, labelled by a far stronger evaluator than anything on the ladder.

## 4. Pillar A — Evaluation v4

### A1. Data (the leap)

| Set | Source | Size | Status |
|---|---|---|---|
| Quiet Lichess | lichess_db_eval, depth >= 12, quiet-filtered | ~155M | have (data/lichessq*) |
| Elite whole-game | Lichess Elite games, SF19 depth 10 | 1.05M | have (data/elite_labelled) |
| **Site-labelled** | every cached game page, Stockfish 16 depth 16, ladder distribution | 131,092 positions in 1,056 games (all 338 teams scrapable: est. 600k–800k) | scrape cache has it; needs a 40-line converter |
| **Curated self-play** | Stockfish 19 vs itself at depth 9 from the 284 curated FENs and their Elite continuations, with exploration (random ply among the top-3 with p=0.1, random opening ply 0–4), each position's search score is its label | 20–30M by Tue night, 40–60M by Wed night | to build (tools/selfplay_sf.py) |
| Own-game positions | 1,660 arena games + 24 rated games, labelled SF19 depth 12 | ~150k | cheap, Monday |

Measured throughput on this machine: Stockfish 19 at depth 9 does 36 positions/s per process
*under today's load of 9*; a quiet machine with 6 workers should give 250–400 positions/s,
i.e. 1–1.4M per hour. Labelling and generation are the same process (the depth-9 search that
picks the move also yields the score), so nothing is labelled twice.

Two details that matter:
- **Scale fit.** Stockfish 19 reports normalised centipawns (100 = 50% win chance); the Lichess
  labels are mostly older, classical-scale. Before mixing, evaluate 20k Lichess positions with
  SF19 at depth 9 and fit one scalar (expect 1.2–1.5) so the sets agree; otherwise the mix adds
  label noise the net cannot resolve.
- **Held-out validation per source.** Keep one site-labelled chunk and one self-play chunk out
  of training; report MAE on each after every epoch. The site chunk is the tournament metric.

### A2. Architecture (cheap, known wins for small nets)

1. **Squared clipped ReLU** on the accumulator (v² / 255 instead of v): one extra multiply per
   hidden unit, no speed cost worth measuring, typically +15–40 Elo on nets this size.
2. **Output buckets by piece count** (8 buckets): w2 becomes [8, 1024], selected at evaluation
   time by popcount; zero cost, +10–30 Elo. The endgame and middlegame stop sharing one output.
3. **Factorised training**: train an un-bucketed 768-feature set alongside the 8 king-bucketed
   ones and fold it into the bucketed weights at export. Better generalisation per bucket with
   our data size; no inference change.
4. Optional, gated: **768 or 1024 hidden** (accumulator updates dominate NNUE cost; expect
   -10–20% nodes/s, so it must win its gate) and **16 king buckets** (12.6 MB file, still small).
   Not a second hidden layer: 1024 x 16 multiply-adds per node in numba would halve the speed.

Export stays int16 in the same safetensors format; test_nnue.py (incremental == reference) and
test_train_consistency.py are extended for the new activation and buckets. The trainer's
per-batch feature construction in numpy is the epoch bottleneck (77k positions/s in the v3b
run, ~45 min per 200M-position epoch); precomputing feature indices per chunk once, or building
them in torch on MPS, is a one-hour job that pays for itself on the first from-scratch run.

### A3. Training runs

| Run | Data | When | Purpose |
|---|---|---|---|
| **v4a** from scratch, new architecture, 512 hidden | quiet Lichess + elite + site-labelled x10 | Mon night (6–7 h) | isolates the architecture gain; fallback net if the self-play set disappoints |
| **v4b** fine-tune of v4a | + curated self-play (first 20–30M) x2, 2 epochs at lr 5e-4 | Tue midday (2–3 h) | the V4.0 net |
| **v4c** fine-tune or retrain | + self-play to 40–60M, own-game positions | Wed (4–6 h) | the V4.1 net if it gates |
| stretch | 1024 hidden and/or 16 buckets | Wed, only if v4b gated and the machine is free | ship only if it beats v4b at the real clock |

## 5. Pillar B — Search v4 (each item gated alone, then together)

Ranked by expected Elo per hour; items whose gate is not clearly positive are dropped:

1. **Quiet checks in quiescence** at the first quiescence ply (and correct evasions): the
   engine currently sees only captures at the frontier; this is where the R43-class
   "refutation is a quiet move" lives. Expect +10–25.
2. **ProbCut** at depth >= 5 (a shallow capture search beating beta + 200 cuts). +10–20.
3. **"Improving"** flag (static eval better than two plies ago) gating RFP, futility and LMP
   margins, and adding a ply of LMR when not improving. +10–20.
4. **LMR for captures and by history**: reduce late captures with negative SEE; continuous
   history-based reduction instead of a single step. +5–15.
5. **SEE pruning of losing captures** at depth <= 6 in the main search (currently only ordered
   last). +5–10.
6. **TT with static eval and two-slot buckets**, age-aware replacement. +5–10 at the real
   clock, where the TT fills.
7. **History indexed by piece-to** with depth-scaled bonus and malus caps (the batch-2
   continuation history can be retried on top of this; it measured +5 alone).

Gating cadence: 300 games at 5 s + 0.05 s, 6 workers, on the **284 curated FENs** instead of
the 68 hand openings (colours alternated per position) — about 45 minutes each, so all seven fit
in Tuesday and Wednesday around the training runs. The combined batch is then re-gated at
10 s + 0.1 s (300 games) and at the real clock by the proxy set. Nodes/s is recorded on every
gate; anything that costs more than 10% speed needs a correspondingly larger gate result.

## 6. Pillar C — Measurement (so V4 is judged the way the Swiss will judge it)

1. **Curated gate set.** `tools/curated.epd`: the 284 start positions from the scraped corpus,
   weighted by how often the site has used them. Every arena gate and the proxy set draw from it.
2. **Fast move-quality grader.** `tools/grade.py`: 400 middlegame positions sampled from the
   site's games, our engine moves at the real budget, Stockfish 19 at 120k nodes grades before
   and after (proxy_calib already does the grading half). Fifteen minutes, one number (mean loss,
   blunder rate) with far less variance than 300 games. Run it on every net and every search
   batch; the site's own grader is what the intel compares us on.
3. **The existing battery, unchanged**: perft/differential, NNUE exactness, trainer consistency,
   wrapper state, tactics 40, mate suites, blunder regression (now 3 positions, grows with every
   rated-game error), torture 30, real-clock pressure 10 (min clock >= 5 s), proxy 20, zip
   byte-check, fresh-extraction game.
4. **Compile budget**: V4 adds jitted code (buckets, SCReLU, ProbCut, qsearch checks). Keep
   compile under 35 s locally on a quiet machine (platform 25–29 s today; 90 s budget).

## 7. Small items that ride along (cheap, low risk, each still gated)

- **Clock horizon tuned on the leap's first rated games**: target 10–25 s left at the end; the
  10 s low-clock caps stay. Add a modest "critical position" bonus when the score is within
  ±60 and the best move changed in the last two iterations.
- **Draw scoring when behind**: score a repetition at 0 instead of -20 when the root score is
  below -150 (draws welcomed when worse, as the intel recommends against AI Fellow, AlphaFish's
  mate-score behaviour, and everyone below the top ten who repeats while ahead). Self-play cannot
  measure this; it is validated on the drawn/losing position sets against Stockfish's defence.
- **Opening book from Lichess Elite games (polyglot, <= 5 MB)**: only if `grade.py` shows the
  first eight own moves still lag after v4b. The intel's read (book is low value) stands until
  the number says otherwise; a book built from our own engine's analysis is not shipped (the
  rules treat a shipped table of engine moves as an engine).

## 8. Not doing, and why

- Conversion package (mop-up, fifty-move scaling): measured neutral twice; conversion is not
  where points are lost.
- A second NNUE hidden layer, MCTS, policy nets, batched torch inference: speed cost or build
  time out of proportion for a four-day window.
- Syzygy tables: 3–4 men is a few Elo at best and eats zip budget the net may need.
- Opponent-specific behaviour: the agent sees only a FEN and a clock.
- Any change untested by Wednesday night.

## 9. Schedule and CPU budget (8 cores: 4P + 4E, MPS for training)

| When | Engine work | Machine |
|---|---|---|
| Mon 10:00–13:15 | upload leap; write selfplay_sf.py, site-labelled converter, scale fit, curated.epd, grade.py, trainer changes (SCReLU, buckets, factoriser, fast features) — unit-tested against the current net | v3b gate extension + battery own the CPU |
| Mon 13:15 | V3 hand-over (leap + v3b) if the battery is green | |
| Mon 13:30–Tue 09:00 | curated self-play generation, 6 workers (target 20–30M); site-labelled set built; v4a from-scratch run overnight on MPS | generation 6 cores, trainer 1–2 cores + GPU |
| Tue 09:00–12:00 | v4a gate vs V3 (300 games, 6 workers, curated set) + grade.py; generation paused | gates |
| Tue 12:00–15:00 | v4b fine-tune (2 epochs) | trainer; generation resumes at 4 workers |
| Tue 15:00–19:00 | v4b gate + grade.py + proxy 20 at the real clock; search items 1–3 gated in the gaps | gates |
| Tue 19:00–22:00 | **V4.0 battery and hand-over** (leap clock + v4b net + any search item that gated) | quiet machine for the pressure games |
| Wed | search items 4–7 gated; v4c on 40–60M; stretch net if free; **V4.1 assembled and gated** | shared |
| Wed 22:00 | **feature freeze** | |
| Thu | 1,000-game regression vs V3 at 10 s + 0.1 s on the curated set, full battery, grade.py, package, byte-check, fresh extraction; **final upload Thursday afternoon** (earlier upload is a Swiss tie-break) | quiet machine |
| Fri before 11:00 | rollback only, on platform telemetry | |

## 10. Definition of done for V4

- v4 net: site-chunk validation MAE below v3b's (117 cp on the whole-game chunk), and
  `grade.py` mean loss below V3's by a clear margin; both R43 positions and every new
  blunder-regression position avoided at the real budget.
- Self-play: V4 beats V3 by >= +50 over 300 games at 10 s + 0.1 s on the curated set with the
  draw-aware interval clear of zero; proxy set >= 65% (leap: 57.5%).
- Battery all green: 0 failures, min clock >= 5 s, tactics >= 38/40, torture 30/30, compile
  <= 35 s quiet, zip byte-identical to sources, fresh-extraction game clean.
- Real-clock centipawn loss vs Stockfish 2400 <= 9 (v3: 11.7, v2.1: 13.3).

## 11. Risks

| Risk | Mitigation |
|---|---|
| self-play generation slower than measured (E-cores, contention with gates) | generation starts the moment the battery ends; the v4a run does not depend on it; v4b trains on whatever exists at Tue 12:00 |
| new activation/buckets break exactness between trainer and engine | tests extended first, run on the v3b weights re-exported through the new path before any training |
| label-scale mismatch between SF19 and Lichess | scale fit before mixing; site-chunk MAE reported per epoch |
| gates polluted by load (compile > 75 s, fallback games) | arena_par already flags fallback games; pressure/proxy runs only on a quiet machine; BINI_JOIN_S raised for local gates |
| search batch neutral like batch 2 | each item alone, dropped unless clearly positive; the net does not wait for the search |
| compile creeps past 40 s | compile_profile.py after every jitted change; the HCE evaluator is skipped when the net is loaded (already planned) |
| something unforeseen on the platform | the shipped build is always the previous gated one; rollback zip and tag ready |

## 12. Today, in order

1. Archit: upload `submission_v2.2leap_0907_0435.zip` (R46/R47 prove v2.2 is still live).
2. Let the v3b extension and battery finish; V3 hand-over ~13:15.
3. Meanwhile (no CPU needed): build the data tools and the trainer changes; unit-test the new
   forward pass against re-exported v3b weights; build `curated.epd` and `grade.py`.
4. 13:30: start curated self-play generation and the site-labelled build; scale fit.
5. Evening: v4a from-scratch run overnight; search item 1 implemented and unit-tested for a
   Tuesday gate.

## 13. Open questions for Archit

- Confirm the leap upload and bring back its first two logs (first move 3.5–4 s, `rg` on the
  line, end clock 10–25 s are the expected signatures).
- Is the site's rule for the Swiss still FIDE draws (repetition counts)? The contempt settings
  assume it.
- Any organiser reply on package additions? Nothing in V4 needs one.

## 14. First-principles review (Mon 7 Sept, 11:00)

Objective restated: points in the 13-round Swiss and the two-game knockout matches, not ladder
rating. Two jobs of equal weight: never leak half points downward (3 level draws in our last 19
games against weaker opponents), and hold or beat the top five.

Runtime observables the plan ignored, both free from the API we have:
- Opponent think time = wall time between our return and the next call; summed, their clock.
- Opponent error = change in our root score across their move, averaged over the game: a live
  strength estimate (AlphaFish reads near zero, a 1600 bot reads 40+ within ten moves).
Together they enable dynamic contempt (up against weak or short-of-time opponents, near zero
against strong ones, draw-seeking when worse against a strong one). Gate on the Stockfish Elo
ladder (draw rate and score at UCI_Elo 1800/2000, no loss at full strength); self-play cannot
measure it.

Not considered before:
- The ladder is endgame-heavy (half of AlphaFish's own moves are after move 40; top-five games
  average 150 plies). Self-play played to the end fixes the training distribution; output
  buckets by piece count give the net separate endgame outputs; blend WDL from game results
  (lambda ~0.85) in the self-play set.
- The NNUE path has no pawnless-draw knowledge (the HCE did). 11% of self-play games end by
  insufficient material. Add material-based draw scaling in front of the net and a KPK bitbase
  built at init.
- Diagnose before training: run the net over the 131k site-labelled positions and bin the error
  by piece count, king bucket, material balance, quiet vs tactical. Decides 8 vs 16 buckets and
  512 vs 768 hidden.
- Profile the search before adding to it: EBF, quiescence node share, TT hit rate from one
  bench run.
- The time edge vs AlphaFish only exists after move 30 (4.4/2.2 s at moves 1/30 vs our 3.8/2.35).
  Test a more aggressive horizon (5 s into moves 8-30) on 60 proxy games, not 20.
- Repetition history when we move second omits the curated start position the referee counts.
- "Earlier final submission" is a Swiss tie-break: weigh a marginal V4.1 against its timestamp.

Refinements: diagnostics step Monday afternoon; data mix 70% SF self-play with exploration +
30% positions from our own games vs Stockfish, results kept for WDL; runtime layer (opponent
model, dynamic contempt, pawnless scaling, KPK); TT 512 MB tested at the real clock only.
Search batch stays but behind these: individual search tweaks at our level are worth +5 to +15
each; the net and the runtime layer are where the points are.

## 15. Execution log and the loop (Mon 7 Sept, from 10:30)

**The loop we are building** (each turn of it makes the next one better):
1. Stockfish plays itself from the 288 curated start positions on the Oracle VM (4 ARM cores,
   ~300 positions/s, ~1.1M/h, ~25M/day), every position labelled at depth 9, results kept.
2. The trainer fine-tunes the net on that stream plus the site-labelled set (Stockfish 16
   depth 16, 109k train / 18.7k held-out, the tournament's own distribution).
3. The net is judged in fifteen minutes by `tools/grade.py` (Stockfish-graded move loss on 400
   real ladder positions) and by `tools/net_diag.py` (error by piece count, material, king
   bucket, quiet/tactical on the held-out site chunk), then by a 300-game gate on the curated set.
4. Every rated game the new build plays goes back in: its positions are labelled and joined to
   the next fine-tune, its errors go into the blunder regression set, its clock curve tunes the
   time policy. The stronger the build, the harder the opponents it is paired with, the sharper
   the data it brings back.

**Done 10:30–12:00:**
- Oracle VM provisioned (`~/chess`: Stockfish 19 ARM build, venv with python-chess, numba, torch
  CPU). The four HyroTrader services are stopped and disabled (Archit's instruction) so all four
  cores generate.
- `bini_v4/` working copy (from bini_v3b). `tools/curated.epd`: 288 curated start positions
  weighted by how often the site has used them (2,484 games).
- `tools/selfplay_sf.py` running on the VM: 4 workers, depth 9, MultiPV 3 only on exploring
  moves, adjudication at +-1500 for 6 plies, result recorded. 75-85 positions/s per worker.
- `tools/site_labelled.py` -> `data/site_labelled/` (1,143 games, 109,170 train + 18,675 held-out).
- `tools/scale_fit.py`: 20k quiet Lichess positions being re-evaluated by SF19 depth 9 on the VM
  to fit the SF19 -> Lichess label scale before the sets are mixed.
- `bini_nnue.py`: squared clipped ReLU and output buckets by piece count, read from the weights
  file's metadata; v2/v3 files load unchanged. Verified bit-exact against the reference on the
  shipped net (3,958 positions) on the VM.
- `tools/train_nnue.py` rewritten: features built in torch on the device (no per-batch numpy),
  --act screlu, --out-buckets, --factorise (folded at export), --wdl blend from game results,
  --scale DIR:k per source, explicit --val chunks with per-source validation every epoch.
- `tools/net_diag.py` and the first diagnostic of v3b on the held-out site chunk: MAE 146 cp,
  correlation 0.91, 23.5% of positions off by 200+. By piece count: 54 cp at 29-32 pieces, 84 at
  25-28, 135 at 21-24, 165-199 from 5 to 20 pieces, 184 at 1-4. Material imbalances of 4 points:
  MAE 250-276. Queens off: 167 vs 128 with queens on. Tactical positions 212 vs quiet 131. The
  endgame is the hole; output buckets and self-play played to the end are aimed at it.
- Engine: time-check mask 1023 when the hard budget is under 200 ms; draw scored 0 (not -20)
  when our previous score was below -150; root guard only within +-150 and at most two extra
  iterations per move; pawnless-draw scaling in front of the net (no pawns and less than a
  rook's worth of extra material -> score/8); TT 2^24 entries (256 MB). Under test on the VM.
- `tools/grade.py` written (samples 400 ladder middlegame positions once, grades with Stockfish
  at 120k nodes, prints mean loss, blunder rate, worst ten).
- Dropped: the "start position missing from repetition history when we move second" item; we
  never see that position (the first FEN we receive is after the opponent's move), so it cannot
  be reconstructed. The referee counts it; the case needs the exact start position to recur,
  which is vanishingly rare.

**Next (Mac still busy with the V3 battery):** trainer and engine suites on the VM; scale fit;
first self-play chunks (~200k per worker) around 11:30; grade baseline of v3b when a core is
free; v4a from-scratch run on the Mac the moment it is released.

**11:00–12:15 (Mac still on the V3 battery; times corrected to London):**
- Trainer smoke test on the VM (CPU): new architecture trains, exports, and the engine's integer
  forward pass agrees with the float model to 0.9 cp mean / 3.2 cp max with squared activation,
  8 output buckets and the factoriser all on. NNUE exactness and the search gate pass on the
  patched engine with the shipped net.
- Search batch behind switches (default off, `BINI_QS_CHECKS`, `BINI_PROBCUT`, `BINI_IMPROVING`):
  quiet checks at the first quiescence ply (direct checks by destination mask, SEE >= 0),
  ProbCut at depth >= 5 (beta + 180, SEE-filtered captures, qsearch then depth-4 verify),
  improving flag from the per-ply static eval (RFP margin, LMP threshold, +1 LMR when not
  improving). Switch-on suites running on the VM.
- Wrapper telemetry (no behaviour change): every log line now carries `ot` (opponent think
  time in ms, from the wall clock between our replies), `sd` (change in our root score across
  their move) and `og` (running average of their gifts). This is the data the adaptive draw
  policy would be built on; it costs nothing to collect from every rated game from now on.
- V3 battery observations: the 600-game v3b extension had one flag (the stalled-machine case
  the 1023-node check mask now covers); v3b's 20-game proxy was 50% against the leap's 57.5%,
  within +-16 points of noise but not the confirmation hoped for. V3 ships on the 300+300-game
  gate; the real-clock evidence for v3b is thin, and the grader will settle it.
- Scale fit found fantasy positions in the Lichess database (seven knights a side) that crash
  Stockfish; filtered by material plausibility. Fit in progress.
- Scripts ready for the Mac: `tools/run_v4a.sh` (from scratch, 4 epochs), `tools/run_v4b.sh`
  (fine-tune on self-play + site-labelled, WDL 0.85), `tools/gate.sh` (arena on the curated
  set), `tools/pull_selfplay.sh` (fetch chunks from the VM).
- 12:15 scale fit (18,437 quiet Lichess positions re-evaluated by SF19 at depth 9): Lichess cp
  ~ 0.86 x SF19 cp by least squares, median ratio 0.80, correlation 0.94, residual 49 cp. The
  Lichess scale is canonical (155M positions); every Stockfish-16/19-labelled set (self-play,
  Elite whole-game, site-labelled) trains with --scale 0.85.

## 16. Review amendments (Mon 7 Sept, 12:40)

Adopted from the second review:
1. **Draw-when-behind is off by default** (`BINI_DRAW_BEHIND`), gated like the adaptive layer:
   Stockfish at UCI_Elo 1800 and 2000, draw rate and score, after the v4a net. Note for the
   record: the rule moves the draw score by 20 cp only after a reading under -150, so it is
   nearly inert; the R49 steering risk is the net's endgame bias, not this rule.
2. **Safety bundle gate.** Check mask 1023, root-guard cap, pawnless-draw scaling, TT 2^24 and
   the telemetry go through one 300-game gate at 10 s + 0.1 s against V3 on the curated set
   before they become the baseline; not clearly neutral-or-better -> split and gate singly. The
   TT size is judged by RSS and the real-clock pressure run, since 10 s cannot show it.
3. **Compile time first.** The first thing run on the Mac when it is free: compile profile and
   three init timings of bini_v4, ceiling 35 s local, before any training starts.
4. R49 log requested for the blunder-regression and net-diagnostic sets.

Order on the Mac, revised: compile timing -> v4a training (GPU) with the safety-bundle gate
running beside it (6 workers) -> v4a gate and grader -> switch gates -> v4b.

## 17. The path to first (Mon 7 Sept, 13:10)

AlphaFish: 2517 after R50, 27-6-4. Beatable, and what beats it is three things, in order:
1. **Never lose the sharp middlegame** (its edge: one blunder in 2,370 moves). Net on the
   tournament's positions + hard-example set + depth where it matters. Number: grader blunders
   <= 0.1% on ladder positions (v3b: 0.3%).
2. **Win the endgames it draws** (it liquidates against the top five; its depth thins to 0.8 s
   after move 40; our net's error there is 3x its middlegame error). Endgame worker at depth
   12, output buckets, piece-count loss weight, fifty-move audit. Number: site-label MAE under
   100 cp at 5-16 pieces (v3b: 165-199).
3. **Keep depth when it cannot** (flat 4% clock vs our reserve): softer early stop + best-move-
   change extension, verified at the real clock.

Acceptance test for V4 (new): **AlphaFish proxy match**, 40 games at the real clock from the
curated positions on a quiet Mac: Stockfish held to ~20k nodes (grader loss near 8 cp, its
level), with its clock habit emulated (nodes scaled with 4% of a simulated remaining clock, so
its search thins after move 30 as AlphaFish's does). V4 is first-capable at >= 50%. Alongside:
grader blunders <= 0.1%, near-100% against the 2000-2300 band with draw rate under 5%.

Engineering added (ranked):
1. Self-play dedup: a worker records a position in the first twelve plies at most three times
   (the 288 openings otherwise repeat a few thousand positions hundreds of times).
2. SPSA over the never-tuned search constants (LMR, null-move R, RFP/futility margins, LMP,
   singular margin, aspiration) on fast games, Tuesday night on the Mac. Plumbing now:
   parameters read from an optional bini_params.json next to agent.py.
3. Accumulator cache per king bucket (refresh by piece-set difference instead of 64 squares)
   for the speed pass; exactness test guards it.
4. Fifty-move audit of existing self-play PGNs; a progress term only if wins are being drawn.
5. 768-hidden / 16-bucket candidate once 20M self-play positions exist (Wednesday).
6. One VM worker generating from Bini-vs-Stockfish games (our own distribution), 20% of stream.
7. Real fallback engine in the wrapper (python-chess alpha-beta, depth 4, time-bounded).
8. Adaptive draw policy gated Wednesday on today's telemetry.
9. First-move book from own analysis: only with idle Mac hours (there will be none).
Not doing: second hidden layer, MCTS, tablebases, anything untested by Wednesday night.

## 18. Fourth review (Mon 7 Sept, 16:30)

1. **v4c from scratch, Tuesday night**: Lichess + all self-play streams (30M+) + site_all + hard set,
   4 epochs; the grader chooses between v4b and v4c on Wednesday morning. Nets that see the
   target distribution from epoch zero beat fine-tunes; the GPU is idle overnight anyway.
2. **Evaluation scale check**: net_diag now reports the slope of prediction against label; every
   search margin is in centipawns, so a slope away from 1.0 is corrected at export before SPSA.
3. **Adaptive draw policy from V3's telemetry** (opponent think time, score drift): built Tuesday
   if the signal separates weak from strong within ten moves; gated on the Stockfish Elo ladder.
   The Swiss-specific lever: half points leaked to weaker opponents cost as much as losses to
   the top five.
4. **768-hidden / 16-bucket candidate only if v4b's validation curve is still falling** at the end
   of its epochs (data-limited); otherwise not.
- 16:45 Scale finding: v3b's outputs run 1.305x the site's labels on the Lichess scale (slope of
  prediction vs label, |label| <= 800). Every search margin was tuned on that inflated scale.
  Mechanism added: `--out-scale` at export (and tools/export_from_pt.py) so each V4 net is
  brought onto the scale the margins expect (ratio of slopes to v3b) before gating; SPSA then
  moves the margins deliberately. Adaptive contempt implemented behind `BINI_ADAPTIVE`
  (contempt = base + 2 x opponent gift average, capped at 60), wrapper passes the average;
  `tools/run_v4c.sh` written for Tuesday night.
- 17:00 Adaptive contempt, decided against on evidence (`tools/opp_signal.py` over 21 rated games):
  the opponent-gift average separates only the weakest bots (38-147 at move 10 for 1200-1450
  opponents) from the strong (2-16 for 1850-2013); in the 1500-1800 band it is 4-31, and it
  inflates once we are winning, i.e. exactly when contempt no longer matters. In the case that
  costs Swiss points (level position, weaker opponent) the signal is small for everyone. The
  code stays behind `BINI_ADAPTIVE` (off). Replacement for the Swiss: a global contempt gate,
  20 vs 35, Tuesday: draw rate vs Stockfish UCI_Elo 2000 (100 games, 10 s) and score vs full
  strength (proxy set); ship 35 only if draws fall and the full-strength score does not.
- 17:10 Fifth review adopted: bundle gate split rule (check mask and root-guard cap stay, the
  rest gate singly if the bundle is not neutral-or-better, contaminated games excluded);
  fallback path for the net made real (the trainer resumes v3b's old-format checkpoint, output
  layer mapped and replicated across buckets); `BINI_FORCE_FALLBACK` test hook so the battery
  plays ten torture games on the fallback engine; scope rule restated: V4.0 = v4b net + what
  gated; SPSA, contempt 35, clock softening are V4.1 by Wed 22:00 or dropped.

## 19. Everything ships in V4 tomorrow (realigned Mon 7 Sept, 17:30)

Rule unchanged: nothing ungated ships. Change: every item gets its gate before Tuesday's
hand-over, so the machines are planned to the hour.

| When | Where | What |
|---|---|---|
| Mon 17:45–22:00 | VM (2 workers; curated generation paused, endgame + Bini streams continue) | search switches: all three on vs off, 300 games at 10 s, curated openings |
| Mon 22:00–01:00 | VM | contempt 35 vs 20: draw rate and score vs the Stockfish sparring agent at UCI_Elo 2000, 100 games |
| Mon 22:30 | Mac | bundle gate ends; split rule applied |
| Tue 00:45 | Mac | v4a done; v4b fine-tune starts (chain) |
| Tue ~03:00 | Mac (chain) | v4b: diagnostic + slope, scale-matched export, candidate dir, 300-game gate vs V3 at 6 workers |
| Tue ~05:00 | Mac (chain) | SPSA on the v4b candidate, 6 workers, 2 s + 0.02 s, 60 iterations |
| Tue 08:00–11:00 | Mac | grade every export; SPSA theta gate (300 games); switch split gates if the VM gate was mixed |
| Tue 11:00–14:00 | Mac | clock softening: 60-game real-clock proxy; contempt result folded in |
| Tue 14:00–18:00 | Mac | V4 assembly; battery: tactics, mates, wrapper/NNUE suites, blunder set at platform budget, torture 30 + 10 on the forced fallback, real-clock pressure 10, AlphaFish proxy match 40 |
| Tue 18:00–20:00 | Mac | package, byte-check, fresh-extraction game, hand-over |
| Tue night | Mac | v4c from scratch on the full mix; if it beats v4b on Wednesday's grader and gate, it uploads Wednesday as V4.1 |

Fallbacks: if v4b does not beat V3, the v3b-resume fine-tune on the new data is the net; if
that fails too, V4 ships with the v3b net and every other gated item.

## 20. R55 (loss to ms, rank 12) and the roadmap changes (Mon 7 Sept, 17:45)

R55 as Black in a Closed Ruy Lopez: level to move 22, then a slow slide (-15 at move 22, -54 at
25, -152 at 28, -300 by 38) over quiet manoeuvring moves; the clock was fully used (11.8 s
left) at depth 15-18. An evaluation loss in exactly the structure the site's games produce.

Adopted:
1. Site positions carry the largest weight: v4b and v4c train on site_all x12 (about 8M of a
   ~45M-position epoch) with Lichess capped to lichessq3 (28M); each site position is seen
   ~24 times over the run, and the held-out site chunk's train/val gap guards against overfit.
2. Rook-and-knight endings from the site's games after move 40, labelled at depth 16, resolved
   to the quiet end of the line (`--material RN --resolve`), as a fourth VM stream.
3. Post-mortem loop: every hour our new rated games are scraped, tagged errors and their
   neighbourhoods harvested, labelled at depth 20 on the VM and joined to data/hard (x20).
4. Depth in quiet middlegames: clock softening (proxy-tested) and SPSA (running on the VM
   tonight, 2 workers, 2 s games, 70 iterations); the tuned theta gets a 300-game gate at 10 s.
5. Second proxy at 40k nodes (top-15 proxy, about 4-5 cp): acceptance >= 60% over 40 real-clock
   games, alongside the AlphaFish proxy.
6. Endgame draw-holding rules (opposite bishops, R vs R+P with the king in front, wrong
   bishop) only if the endgame error is still above 120 cp after v4b.
Also running: quiet-resolved labelling in every generator from now on; the book from our own
60 s analysis of the 288 curated positions (Mac, `tools/make_book.py`), shipped only with the
organisers' confirmation and a grader gain on the first eight own moves; the profile before any
speed work.

## 21. The V4 directive (Mon 7 Sept, 19:10) and how it is met

Failure mode (R55 vs ms 2250, R56 vs Edward 2127): no blunders, 18-20 cp loss per move
against their 5-10, ten small inaccuracies in closed structures, twenty moves of shuffling at a
flat evaluation, a clean squeeze into a lost endgame. V4 removes it by evaluation, depth and
structure-specific data; nothing from Leela, the transformer or any published network is in the zip.

| Directive | Mechanism | State |
|---|---|---|
| Site positions weighted above Lichess | site_all x12 (~8M/epoch) vs Lichess capped to 9 chunks (~7M) in the final run | in run_v4d.sh |
| Named self-play slice: Ruy Lopez Closed and every structure drawn > 10 times, depth 12, to the end | `tools/structures.epd` (the 288 filtered by frequency), worker on the Mac, resolved | running |
| Rook-and-knight endings from the site's games after move 40, depth 16 | VM worker at depth 14 (depth 16 gave 2 positions/s); `--material RN --resolve` | running |
| Resolve every self-play position to the quiet end of the line | `--resolve` in every generator | done |
| Results blended at 0.85 in every run | `--wdl 0.85` in v4a, v4b, v4c, v4d | done |
| Harvest R55, R56, every rated round | hourly post-mortem loop (`tools/postmortem.sh`, :42) | running |
| 20 epochs, decaying schedule, site scale export | `tools/run_v4d.sh` (one-cycle over 20 epochs on the tournament mix, ~25 min/epoch), chained after v4b tonight; scale matched at export (ratio of slopes) | chained |
| 768 hidden once 512 converged | `HIDDEN=768 bash tools/run_v4d.sh` after v4d, judged at the real clock; if it lands Wednesday it is V4.1 | scheduled |
| Targets | held-out site chunk MAE < 110 overall, < 130 at 5-16 pieces (v3b: 145 / 165-215) | to report per candidate |
| Spend the unused 40% of the soft budget | `BINI_SOFT_STOP`: stop at 1.5x the last iteration, factor 1.6 on a best-move change; proxy + pressure sets at the real clock | built, gate Tuesday |
| SPSA tonight, gate once at 10 s | VM, 2 workers, 16 games x 40 iterations, corrected step | running |
| Profile before speed work, target 1M nps, perft exact | profile.py (node counts recorded); clean run on a quiet core Tuesday | scheduled |
| Book from our own 60 s analysis, ship only with confirmation + grader gain | `tools/make_book.py` running on the Mac; organiser email drafted | running |
| Top-15 proxy: Stockfish 40k nodes, 40 real-clock games, >= 60% | `tools/proxy_match.py --nodes 40000` | Tuesday battery |
| Not in V4 | adaptive contempt (off), accumulator cache (dev copy only), telemetry (stripped), extra search switches (off; no gate scheduled) | done |
| Freeze Wed 22:00; battery on the exact zip incl. forced-fallback torture and a fresh-extraction game | battery list in s19 + `BINI_FORCE_FALLBACK` | Tuesday |

## 22. Tonight's rules (Mon 7 Sept, 20:00) and V4 / V4.5 split

Rules for the chain, adopted:
1. The Mac runs training plus a two-worker gate and nothing else. The v4b gate is two workers;
   every gate or training launch in the chain waits until the one-minute load average is 10 or
   below (`wait_load` in overnight.sh). Book build and the structures worker moved to the VM,
   queued behind SPSA; the book's 184 Mac-side positions were made under load 40-80 and are
   redone on a quiet core. The book ships only if the grader shows the first eight own moves
   improve, and only with the organisers' confirmation.
2. One table per run in the progress file: trainer validation MAE (quiet positions only, which
   is why it reads lower), diagnostic MAE on all positions and on quiet positions, 5-16 pieces,
   scale slope, grader loss and blunders (`tools/epoch_table.py`). Stopping rule: v4a crosses
   v3b (145 all / 14.2 cp grade) by epoch four, or the v3b-resume fine-tune is the base for v4d.
3. Timeline: Tuesday 20:00 is the best case; the battery is never compressed. A slipping stage
   moves the hand-over, not the battery; V4.5 absorbs what does not make it.
4. V4 (Tuesday) = the v4d net exported at the site's scale, plus whatever gated alone against
   V3 at 10 s and again in the real-clock battery (pressure 10, both proxy matches, torture 30 +
   10 with the fallback forced, blunder set at the platform budget, fresh-extraction game).

## 23. V4.5 (Wednesday): the leap over V4

What V4.5 is: the same architecture with the things that need Tuesday's results to be built
right, each gated alone against V4 at 10 s and in the real-clock battery, freeze Wed 22:00.

1. **Net v4.5**: the 768-hidden candidate on the tournament mix (starts on the GPU the moment
   v4d's gates are done Tuesday afternoon, ~11 h), judged against v4d by grader, 300 games and
   both proxies at the real clock. Ships only if it wins at the real clock, where its 10-15%
   speed cost is paid. Plus a second 20-epoch 512 run seeded from v4d with Tuesday's fresh data
   (the post-mortem chunks from V4's own rated games, the structures and rook-and-knight slices
   at full size, the whole-site set refreshed Wednesday morning) as the fallback candidate.
2. **Search parameters at the new scale**: SPSA re-run Tuesday night on the v4d net (the
   Monday run tunes at v3b's scale), 40 iterations, gated once at 10 s against V4.
3. **Clock**: the softer early stop and the best-move-change extension, validated on the proxy
   and pressure sets at the real clock; kept only if the 40k proxy score does not fall.
4. **Speed**: the profile on a quiet core; one change at a time (accumulator update, static-eval
   caching in the TT, move-ordering cost), each with perft exact and identical fixed-depth node
   counts; target one million nodes a second on the Mac.
5. **Endgame draw-holding rules** only if v4d's error at 5-16 pieces is still above 120 cp.
6. **Book** if confirmed and measured.
7. Battery identical to V4's plus a 1,000-game regression against V4; earlier upload wins the
   Swiss tie-break, so V4.5 uploads Wednesday evening only if it beats V4 clearly (>= +30 with the
   interval clear of zero and no proxy regression); otherwise V4 stays.

### 23.8 Drawishness scaling in front of the net (V4.5, gated alone)

When the material is a known drawish ending and the raw score is within +-150, scale the score
toward zero inside `evaluate` (so the search sees it at the leaves, which is what makes the engine
keep tension when ahead): pure rook endings with equal pawns x0.5, opposite-coloured bishops
with pawns x0.5, one minor piece each with two or fewer pawns each x0.6, the existing pawnless
rule unchanged. Tests before the 10 s gate against V3:
1. the drawn set must not lose a single game against Stockfish's defence;
2. a new "small edge" set: 40 middlegame positions from the site's games with the site's
   evaluation at +50 to +150 for us, played to the end against Stockfish at 20k nodes at the
   real clock; must not score worse than V3 and should convert more;
3. fixed-depth node counts on the profile positions unchanged wherever the rule does not trigger.
Ship only if the 10 s gate is not negative and the small-edge set improves. Also: R52's
positions from moves 30 to 40 go into the hard set at depth 20.

## 24. Night finding (Tue 8 Sept, 01:05): the V4 nets lose games despite winning every static test

v4b (rescaled) vs V3: 40.6% at 85 games (-66 +-77). v4a vs V3: 36.8% at 38 games (-94 +-120).
Both nets pass mates 80/80, puzzles 40/40, the blunder set 3/3, and grade at v3b's level; the
diagnostic shows them more accurate than v3b on the site's positions. The games disagree, so the
static measures miss what the search sees. The two nets share five changes that were never gated
alone: squared activation + output buckets + factoriser, site-set oversampling (x10-x12), the
result blend (0.85), the piece-count loss weight, and the 0.85 label scale. That is the
one-change-per-gate rule broken by me on Monday afternoon, inferring the architecture from the
grader instead of a gate.

Recovery (running): the chain is stopped before v4d spends the GPU on the suspect recipe. Three
one-hour ablation fine-tunes run back to back and gate as the current gates free up:
  v4o  = v3b (old architecture) + full tournament mix   -> isolates the architecture
  v4o2 = v3b (old architecture) + mild mix (no result blend, no piece weight, site x4) -> isolates the mix
  v4b2 = v4a (new architecture) + mild mix              -> the cross-check
The recipe that holds V3's level in a 300-game gate becomes the long run this morning; if none
does by 08:00, V4 ships with V3's net plus the gated engine items, and the net work continues
for V4.5 with the discipline restored. The hand-over time moves; the battery does not.

### 24.1 Diagnosis (02:15): the mix flattens the middlegame evaluation

Four logged games v4o vs v3b, Stockfish-graded per move (all draws): opening and endgame moves
at 1-8 cp of loss, middlegame moves at 36-53 cp (v3b's usual 8-15). The candidate's own scores
are compressed: +156 where Stockfish reads +424, +176 vs +378, -157 vs -25. A net that reads a
won position as a small edge does not press; one that reads level as lost drifts. Mechanism: the
self-play stream is 70% drawn games with a median label of 32 cp, the result blend pulls decisive
labels toward a draw, and a two-epoch fine-tune at 5e-4 overwrites v3b's Lichess-learned
middlegame with "everything is level". v4a (far less of that data) degraded less. The static
tests missed it because the held-out site chunk is the same distribution as the training mix.

Fixes, in the recipes now queued: keep the full quiet Lichess set in the mix; thin self-play's
flat positions (`--thin-flat selfplay:0.3:25`); no result blend; site x4; low learning rate and
one epoch on the v3b base (run_v4o3.sh). The v4o2 gate (mild mix) is the first test; v4o3 the
second. For the generators: self-play from level curated positions needs decisive games or
score-balanced sampling to be worth its weight; a fix for V4.5.

## 25. Tuesday decision (Tue 8 Sept, 09:55): V4 = the V4 engine with V3's net

Real-clock proxy table (40 games each, our engine through the real wrapper at 120 s + 0.5 s,
Stockfish at a fixed node budget with a 4%-of-clock habit):

| net | 20k proxy | 40k proxy |
|---|---|---|
| V3 (v3b) | 46.3% (+6 =25 -9) | 27.5% (+0 =22 -18) |
| v4o2 | 40.0% (+3 =26 -11) | 20.0% (+2 =12 -26) |

- v4o2 won every static test (site-chunk MAE 134.8 vs 145, endgame 189 vs 215, grader 14.0 cp / 1
  blunder) and held V3 at 10 s (51.7% over 270), but trails V3 by 6-7 points on both real-clock
  proxies. Each gap is inside noise; the direction is the same twice; the rule is "clearly positive
  or it does not ship". V3's net stays.
- The 40k proxy is out of reach for both nets at the real clock, so the 60% line in section 17 was
  calibrated on 10 s games and is replaced by the 20k proxy at >= 50% (V3 sits at 46%).
- Book: built (2,018 entries, 2.3 cp mean loss vs 3.0 cp for the engine at 3.8 s) but not shipped:
  no organiser confirmation. It sits in data/book.json and the wrapper loads it if the file is
  present, so it can be added to a later upload in one step.
- The soft-clock variant's build was broken (mixed engine modules); clock softening moves to V4.5
  with its own clean build and gate.

What V4 therefore is: V3's playing strength plus the hardening that was gated neutral or better:
check-mask fix, root-guard cap, pawnless-draw scaling, 256 MB TT, telemetry stripped, a real
fallback engine (python-chess alpha-beta on a board copy) instead of a random mover, and the book
hook. The leap (net on decisive self-play, 768 candidate, SPSA at the new scale, clock softening,
speed pass, drawishness scaling) is V4.5, Wednesday, freeze 22:00, per section 23.

## 26. Post-mortem of the V4 run and the rules for the next run (Tue 8 Sept, 13:10)

Why V4 is a hardened V3 and not the system section 0 promised:

1. The metric that chose candidates does not predict strength. Site-chunk MAE, the grader and the
   endgame error all improved on every retrained net; every one of them lost or tied in games. A
   draw-heavy label distribution (70% draws, median |cp| 32) rewards a net that shrinks its
   magnitudes; MAE falls while the search loses the decisiveness that wins. Nothing in the plan
   checked, before the compute was spent, that the metric orders the nets we already know the
   Elo of (v2.1, v2.2, v3b). It does not.
2. The data fix was the whole lever and it was wrong at source. Stockfish self-play from balanced
   curated positions with near-best moves is a draw generator. Random-walk openings and
   score-balanced sampling (built today) were needed on Sunday.
3. No pilot. Every data change went straight to a 6-20 epoch run and a 300-game gate; the
   flattening surfaced at 01:00 Tuesday instead of Monday afternoon. A one-epoch fine-tune plus
   40 real-clock proxy games (2 hours) answers the direction question.
4. The measurement budget was too small for the effect size: 10 s gates resolve +-40 Elo, 40-game
   proxies +-15 points; the differences we were choosing between were 10-20 Elo.
5. One 8 GB machine did training, gates and proxies; it thrashed, and the "training + one 2-worker
   gate" rule made the gates the bottleneck. The VM ran generators only, although the engine runs
   there.
6. Process losses of roughly eight hours: the working-copy deletion (case-insensitive rm), the
   shell-pattern self-kills, a broken soft-clock build, misnamed flags. Each is a missing check.
7. SPSA and the speed pass were the wrong tools at this scale: SPSA needs tens of thousands of
   games; the profile shows a per-node cost spread across TT, ordering, update and eval with no
   single hot loop.

Rules for the next run (V4.5 and beyond):

- Calibrate first: any metric used to pick a net must order v2.1 < v2.2 < v3b correctly; otherwise
  only games count.
- Pilot before scale: one epoch, scale-matched export, 40 proxy games at the real clock; the full
  run starts only if the pilot is at V3's level or better.
- Machines by job: 10 s gates on the VM (4 workers); the Mac trains and plays the real-clock
  proxies; never more than one job per machine at a time.
- Effect-size budget: 300 games at 10 s AND 80 real-clock proxy games per shipped change.
- Every destructive shell step goes through a script that lists its target before acting.

## 27. V5: a net from scratch on our own three machines (proposed Tue 8 Sept, 14:30)

Premise: the shipped net's failures are systematic (material deficits read 3-5x too small,
drift in heavy-piece middlegames, endgame error 3x the average), and a fine-tune cannot move a
net that far. A from-scratch run on the corrected data is the one lever left that can be large,
and it needs no GPU if the trainer streams chunks at >= 50k rows/s on the Mac.

Data (all local or streaming): Lichess deep-labelled quiet 155M; site-labelled 750k (x4);
decisive self-play (target 5-8M by Wed night); resolved endgames 2M+; hard set + harvest (x10);
a "our distribution" stream where the V4 engine plays one side against Stockfish.
Candidates: 512 from scratch (same speed as today) and 1024 from scratch (about -20% nps),
judged only by real-clock proxy games and 300-game gates; static metrics used only after they
are shown to order v2.1 < v2.2 < v3b correctly (calibration first, PLAN s26).
Search track in parallel on the cloud VM: correction history, continuation history, ProbCut and
improving switches, KPK bitbase, clock softening, each gated alone at 300 games.
Schedule: Tue night the decisive-mix pilot decides which run gets the Mac overnight (fine-tune
for V4.5 if the pilot is positive, else 512 from scratch); Wed V4.5 as in s23; Wed night 1024
from scratch; Thu gates, proxies, battery; Fri 09:00 upload only if V5 beats V4.5 by >= +30
with the interval clear of zero and no proxy regression.
Honest ceiling: +150 to +200 over V4 if everything lands, i.e. the 2200-2300 band and a top-5
seed. First place needs AlphaFish (2500+) to lose a knockout game to someone; the Swiss
tie-break and a blunder-free, endgame-solid engine are what put us in position to benefit.
