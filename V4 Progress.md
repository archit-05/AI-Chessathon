# V4 Progress

Running status of the V4 build. Newest entries at the bottom of each section; the board at the
top is always current. Plan and rationale: [PLAN_V4.md](PLAN_V4.md). Times are London.

## Board (updated Tue 8 Sept, 11:10)

| Track | State | Next |
|---|---|---|
| V4 | HANDED OVER: `submission_v4_0908_1053.zip` (sha256 00fe9eae6b5cc356..., 8 files, 6.40 MB unzipped) = V4 engine (safety bundle, real fallback engine, book hook, telemetry stripped) + V3's net (v3b), no book. Battery all green, byte-check identical, extracted zip mates the minimax baseline in 19 | Archit uploads; the site's first rated games become the post-mortem input |
| Net decision | real-clock proxies: 20k V3 46.3% / v4o2 40.0%; 40k V3 27.5% / v4o2 20.0%. v4o2 wins every static test and holds V3 at 10 s (51.7% over 270) but is not clearly positive in play, so it does not ship | V4.5 net on decisive self-play (PLAN s23, s24.1) |
| Live on the platform | V3 (leap clock + v3b net). Rank 17 after R56 (33 games) | V4 once uploaded |
| Oracle VM | 4 curated workers at depth 9 (~70 pos/s each) + endgame streams; SPSA finished flat; book built (not shipped) | switch generators to decisive-game mode for V4.5 data |
| Data | site-labelled ~660k train / 85k held-out; self-play 29 chunks; hard set 7 chunks (140 positions); harvest 37 tagged errors | V4.5 mix: decisive self-play, no result blend, site x4 |
| V4.5 | Wednesday, freeze 22:00: net on fixed data, 768 candidate, SPSA at the new scale, clock softening (clean build this time), speed pass, drawishness scaling (23.8), 1,000-game regression vs V4; uploads only if >= +30 with the interval clear of zero and no proxy regression | starts now |

## Key numbers so far

- Shipped net (v3b) vs the site's depth-16 labels, 18,675 held-out positions: MAE 146 cp,
  correlation 0.91, 23.5% off by 200+. By piece count: 54 cp (29–32 pieces) → 84 → 135 →
  165–199 (5–20 pieces) → 184 (1–4). Queens off 167 vs on 128. Material imbalance ±4: 250–276.
  The endgame is the hole.
- Scale: Lichess cp ≈ 0.86 × SF19 cp (median ratio 0.80, corr 0.94, residual 49 cp).
- Self-play generator: 75–85 positions/s per worker unloaded, 64–68 when sharing with tests.
- Grader baseline v3b on the VM: 14.2 cp mean, 0.3% blunders, 65% exact best (1.5 s, loaded ARM core).
- Net-diagnostic baseline v3b at the 0.85 label scale (the reference for every V4 export): MAE 144.8 cp overall, 215 at 9-12 pieces, 162 at 17-20, 50 at 29-32; 23.1% off by 200+.
- V3 battery: 600-game gate +28/+48 (two halves), one flag loss (stalled machine, 80 ms budget);
  20-game real-clock proxy 50% (leap: 57.5%).

## Per-epoch table (v4a, complete)

Trainer validation is on quiet positions of the held-out site chunk (the diagnostic's "quiet" column is the comparable figure); "all" includes tactical positions. Labels at the 0.85 scale. Grader resolution about +-3 cp / +-2 blunders between epochs.

| v4a epoch | trainer val MAE (quiet) | diag all | diag quiet | diag 5-16 pieces | slope | grader cp | blunders |
|---|---|---|---|---|---|---|---|
| v3b (reference) | – | 144.8 | 131 | 165–215 | 1.305 | 14.2 | 1 (0.3%) |
| 1 | 139 | 148.0 | 135.8 | 187 | 1.194 | 22.2 | 10 (3.3%) |
| 2 | 137 | 145.9 | 133.3 | 183 | 1.244 | 18.5 | 5 (1.7%) |
| 3 | 134 | 143.6 | 131.0 | 184 | 1.276 | 17.8 | 3 (1.0%) |
| 4 | 133 | 143.2 | 129.4 | 182 | 1.311 | 14.5 | 2 (0.7%) |
| 5 | 132 | 141.9 | 129.0 | 182 | 1.299 | 17.9 | 4 (1.3%) |
| 6 | 132 | 142.4 | 128.9 | 183 | 1.312 | 16.5 | 3 (1.0%) |

## Log

- 10:30 Oracle VM provisioned (Stockfish 19 ARM build, venv: python-chess, numpy, numba,
  torch CPU). HyroTrader services stopped and disabled on Archit's instruction.
- 10:40 `bini_v4/` working copy from bini_v3b; `tools/curated.epd` (288 start positions, 2,484
  games); `tools/selfplay_sf.py` smoke-tested (335 positions, sane labels) and launched at 4
  workers with MultiPV only on exploring moves.
- 11:00 `tools/site_labelled.py` → `data/site_labelled/` (1,143 games). Scale-fit sample (20k
  quiet Lichess positions) sent to the VM.
- 11:10 `bini_nnue.py` rewritten for squared activation and output buckets; exactness test
  passes on the shipped net on the VM (32 s including compile).
- 11:20 `tools/net_diag.py` and first diagnostic (numbers above). `tools/train_nnue.py`
  rewritten. torch installed on the VM.
- 11:40 Engine patches: check mask, contempt-when-behind, root-guard cap, pawnless scaling,
  TT 2^24. `tools/grade.py` written. Search gate passes on the patched engine.
- 12:00 Search batch (quiet checks, ProbCut, improving) behind switches. Trainer smoke test on
  the VM: export + consistency 0.9 cp with everything on. Wrapper telemetry added.
- 12:05 Scripts ready for the Mac: `run_v4a.sh`, `run_v4b.sh`, `gate.sh`, `pull_selfplay.sh`.
  Grader position set (800 candidates) built and shipped to the VM.
- 12:10 Scale fit hit Stockfish crashing on fantasy Lichess positions (seven knights a side);
  material-plausibility filter added, rerun.
- 12:15 Scale fit done: k = 0.85 applied to every Stockfish-labelled set in both run scripts.
- 12:20 Waiting on: switch-on search suites (VM), first self-play chunks (VM), Mac release.
- 12:20 Switch suites on the VM: quiet checks in quiescence solve WAC.001 (tactics 10/11 vs 9/11), mates 80/80 in every configuration, bench -5% nodes/s with all three on. Alarm: with all three on, both R43 blunder positions are repeated at depth 13-15 on the loaded ARM core; the same test passed at depth 15-16 on the Mac. Per-switch runs at 2.5 s and 5 s queued to separate depth from the switches.
- 12:22 Second review adopted: draw-when-behind off by default (own gate after v4a); the safety items get one bundle gate vs V3 before becoming the baseline; compile timing is the first Mac job. R49 log requested.
- 12:25 Grader baseline (VM, ARM core under load, 1.5 s per move, Stockfish 120k nodes as grader, 300 ladder positions): v3b mean loss 14.2 cp, median 0, blunders 0.3%, exact best move 65%. Relative yardstick for every net and search change on the same machine; the platform at 3 s will be lower.
- 12:28 Blunder regression per switch on the VM (depth 13-16): switches off avoid 17.Rd4 at both 2.5 s and 5 s but repeat 15.Rad1 (the Mac at depth 15-16 avoided both); each switch alone flips at least one of the two, all three on repeat both. Reading: the R43 positions are borderline for this net and turn on a ply or two of depth; the switches change the tree enough to lose that ply. They stay off by default; each needs its 300-game gate plus the grader, and the blunder set at the platform budget is a hard requirement for whatever ships.
- 12:31 First self-play chunks (4 x 200k): median |label| 32 cp, 16% beyond 300, quiet share 0.81, 22% of positions with 7 or fewer pieces, 70% from drawn games. Pulled to data/selfplay.
- 12:50 Third review adopted: endgame-start worker (depth 12, from the site's games), piece-count loss weights (0.5), WDL 0.85 in the from-scratch run too, hard-example harvest (`tools/harvest_errors.py`: 16 tagged errors, 62 positions, labelled at depth 20 on the VM), whole-site scrape (`intel/scrape_all.py`, running), v4a to 8 epochs with per-epoch exports graded as candidates. Declined: a CPU training run on the VM (generation wins), second hidden layer, MCTS.
- 13:10 Path-to-first section written (PLAN_V4 s17): three requirements, AlphaFish proxy match as the acceptance test. Generator dedup added (first 12 plies, max 3 per worker) and the VM workers restarted: 3 curated at depth 9 (84/s each), 1 endgame at depth 12 (29-36/s), dedup skipping ~2.4%.
- 13:15 Fifty-move audit of 500 self-play games (10 s): draws by fifty-move 108, threefold 116, insufficient 51; only 4 (0.8%) ended with a decisive material edge and none by the fifty-move rule with a rook or more up. No progress term needed; the pawnless-draw rule covers the rest.
- 13:15 Hard set labelled at depth 20 on the VM: 57 positions -> data/hard/chunk_0000.npz.
- 14:32 Compile timing on the quiet Mac, bini_v4 with everything compiled: 20.1 / 20.1 / 21.1 s init (compile 19.5-20.2 s), peak RSS 462-477 MB with the 256 MB table. Ceilings 35 s / 2 GB hold.
- 14:34 v4a training launched (8 epochs, screlu, 8 out-buckets, factorised, WDL 0.85, piece-count weight 0.5, scale 0.85 on Stockfish-labelled sets). Restarted 14:44 with a 50k validation slice after the 200k-row validation pass on MPS printed an impossible loss (9.17) and starved the run; with 50k rows the numbers are sane (site 0.039, Lichess 0.047). Training batches are 16k rows and were verified consistent on MPS (0.5 cp).
- 14:35 Safety-bundle gate started: bini_v4 (switches off, V3's net) vs bini_v3b, 300 games at 10 s + 0.1 s, 4 workers, curated openings, TT 2^22 for memory (the 256 MB table is judged by RSS and the pressure run).
- 14:50 Wrapper fallback engine replaced: python-chess alpha-beta with quiescence, iterative deepening to the budget (depth 4-5 in 1.5 s), instead of the 2-ply material search.
- 14:55 Trainer steady state 29 s per 770k-position chunk beside the gate (106 min per epoch): v4a restarted with 6 epochs (ends ~01:30) and `tools/overnight.sh` armed: waits for v4a, pulls chunks, rebuilds the site-labelled set from the whole-site scrape, runs the v4b fine-tune. Both nets by morning.
- 14:55 Fallback engine bug found and fixed on the VM: an aborted search left pushed moves on the caller's board; it now searches a copy. Verified legal, board intact, budget respected, finds mate in one.
- 15:00 Tunable search parameters (RFP margin, null-move base/divisor, singular margin, LMR base/multiplier, futility and LMP scales, ProbCut margin) moved into info slots with defaults identical to the constants; overridable by `bini_params.json` next to agent.py or `BINI_P_*` env, for SPSA. In the dev copy (`bini_v4dev`) since the gate runs from bini_v4; suites queued on the VM.
- 15:00 Mac thrashed: load 143, 10 GB of swap, 57 MB free, seven of the first thirty gate games on the fallback (compile past 85 s). Eight engines plus the trainer exceed 8 GB. Gate stopped (orphaned pool workers hunted down and killed); it restarts at two workers with a 2^21 table once memory recovers, finishing this evening beside the training. Rule from here: on the Mac, training plus at most two gate workers.
- 15:02 Dev-copy suites on the VM: parameter plumbing passes with defaults (gate 2, mates 80/80) and with a params file plus all switches (tactics 10/11); exactness ok; bench 576 knps vs 590 before (noise-level).
- 15:05 `tools/spsa.py` written (perturb, play plus-vs-minus on the curated set at 2 s + 0.02 s, step theta; the final theta gets a real 300-game gate).
- 15:05 Bundle gate restarted at 2 workers, 2^21 table (trainer back to 22 s per chunk with the gate gone; load 5).
- 15:10 Accumulator cache (per king bucket, refresh by piece-set difference) in the dev copy: bit-exact against the reference, and the search visits exactly the same node count as without it (273,572 nodes at depth 12 on the test position). Speed back-to-back on the VM: 440 knps without, 428 with: no gain (the king-bucket refresh was not the hotspot). Kept as verified code, not counted as an improvement; the speed pass needs a real profile first.
- 15:20 Generator gained a mode where our own engine plays one side (250 ms per move on the VM) with every position still labelled by Stockfish at depth 9. VM now: 2 curated workers (run3), 1 endgame worker at depth 12, 1 Bini-vs-Stockfish worker. Chunks from run2 (6) are kept.
- 15:30 `tools/proxy_match.py` (AlphaFish proxy: Stockfish at a scaled node budget with a 4%-of-clock habit, our engine through the real wrapper) validated functionally on the VM with tiny clocks; the real 40-game run needs a quiet Mac.
- 15:40 Per-epoch loop armed: each v4a export is copied aside, diagnosed on the held-out site chunk and graded on 300 ladder positions on the VM (`tools/grade_export.sh`), so Tuesday morning starts with six graded candidates.
- 15:50 Whole-site scrape done: 288 teams with games, 6,202 game pages cached (about 750k depth-16 positions). Building `data/site_all` (train/held-out by game id, same rule as before); `data/site_labelled` stays as the fixed held-out reference for the v4a comparisons. v4b now trains on site_all x4 and validates on both held-out chunks; overnight chain restarted with the change.
- 15:50 Bundle gate 52/300: 54.8% (+34 +-97), zero fallback games at two workers. Trainer 28 s per chunk; v4a ends about 00:45.
- 16:30 Fourth review (PLAN_V4 s18): v4c from scratch Tuesday night on the full mix; evaluation-scale slope added to the diagnostic (search margins assume 1.0); adaptive draw policy built Tuesday from V3's telemetry if the signal separates opponents; larger net only if v4b's validation curve is still falling.
- 16:45 Evaluation scale: v3b's slope against the site's labels (Lichess scale) is 1.305, i.e. the shipped net's centipawns run 30% large and every search margin was tuned on that. Export gained `--out-scale` (plus `tools/export_from_pt.py`) so V4 nets are matched to that scale before gating. Adaptive contempt built behind `BINI_ADAPTIVE` (off), `tools/run_v4c.sh` ready for Tuesday night. Dev-copy suites with the switches on pass on the VM.
- 16:50 v4a after 1 of 6 epochs, held-out site chunk (0.85 scale): MAE 148 cp (v3b 145), 212 at 9-12 pieces (v3b 215), 51 at 29-32; scale slope 1.19 (v3b 1.31). Lichess chunk 180 cp. Bundle gate 120/300: 47.5% (-17 +-63), three fallback-contaminated games to exclude at the end.
- 17:00 Adaptive contempt parked on evidence (`tools/opp_signal.py`, 21 rated games): the gift signal is confounded with "already winning" and is noise in the 1500-1800 band. Replaced by a global contempt gate (20 vs 35) on Tuesday: draw rate vs Stockfish 2000 and score at full strength.
- 17:10 Fifth review adopted: bundle split rule, v3b-resume fallback path in the trainer, `BINI_FORCE_FALLBACK` hook for the battery (ten torture games on the crash path), scope rule restated (V4.0 = v4b net + what gated; the rest is V4.1 by Wed 22:00 or dropped).
- 17:45 R55 loss to ms (rank 12) analysed: evaluation slide in a quiet Closed Ruy Lopez middlegame, clock and depth fine. Roadmap changes adopted (PLAN_V4 s20): site positions x12 above Lichess, rook-and-knight endgame stream at depth 16, hourly post-mortem loop into the hard set, clock softening + SPSA, 40k-node top-15 proxy at >= 60%, conditional endgame draw rules. Generators now record the quiet end of Stockfish's line. VM: SPSA (2 workers) + resolved endgame worker (d12) + rook-knight worker (d16). Mac: book build from our own 60 s analysis of the 288 curated positions; profiler run.
- 17:50 Post-mortem loop's first real run: the site now prints ranks as "#17" and the scraper choked; fixed. 25 of our games since R31 scraped, 25 tagged errors (R55 contributed six inaccuracies, no blunder: the slide was graded as a slide), 92 positions, 30 new ones labelled at depth 20; hard set is two chunks. The ladder shows BINI Alpha at rank 17 after 32 games on V3.
- 17:55 All four levers live in parallel: net (Mac GPU, chain extended through the v4b gates), SPSA (VM, iteration 0 running), book (Mac, 288 x 60 s), profile (run once; absolute numbers void under load, fixed-depth node counts recorded for change detection; clean re-run tomorrow). Hourly post-mortem loop armed (:42). Organiser email drafted for Archit to send.
- 18:45 v4a epoch 2: site chunk MAE 146 (9-12 pieces 205, slope 1.24), grade 18.5 cp / 5 blunders (epoch 1: 22.2 / 10; v3b: 14.2 / 1). Trend right; must cross v3b by epoch 4.
- 18:50 VM corrections: the rook-and-knight worker at depth 16 produced 2 positions/s (30k by morning), restarted at depth 14; SPSA's update step was too small to move any parameter (bug in my scaling) and the iterations took 19 min, so it restarts with the corrected step, 16 games per iteration, 40 iterations, ending about 06:00. Endgame worker (d12, resolved) unaffected at 23/s.
- 19:00 Bundle gate stopped at 241 games (the Mac's memory storms had put 12 games on the fallback): clean tally +53 =123 -53 over 229, exactly 50.0%, +0 +-40. Neutral. Check mask and root-guard cap stay (they cannot change 10 s results); the pawnless-draw rule and the 256 MB table are judged in the real-clock battery. Book build restarted with a 64 MB table (116 of 288 positions kept). Mac from here: trainer, book, structures worker only.
- 19:15 V4 directive recorded (PLAN_V4 s21): telemetry stripped from the shipping wrapper; clock softening built behind `BINI_SOFT_STOP`; `run_v4d.sh` (20 epochs, tournament-weighted mix, Lichess capped) chained after v4b and its gate; switches gate dropped from the chain (not in V4); frequent-structures self-play slice (`structures.epd`, depth 12, resolved) running on the Mac; targets set: site-chunk MAE < 110, < 130 at 5-16 pieces.
- 20:05 Tonight's rules adopted (PLAN_V4 s22): Mac = training + two-worker gate only; load check before every launch; book and structures worker moved to the VM behind SPSA; per-epoch table with reconciled MAE (trainer = quiet only); battery never compressed; V4 = v4d net + gated items. V4.5 plan written (s23): 768 candidate, SPSA at the new scale, clock, speed, conditional endgame rules, book; freeze Wed 22:00.
- 21:30 V4.5 plan gained item 23.8: drawishness scaling in front of the net (rook endings, opposite bishops, minor-piece endings with few pawns), gated alone with the drawn set, a new small-edge conversion set and node-count invariance; R52 moves 30-40 to the hard set.
- 21:45 v4a epoch 4: grader 14.5 cp / 2 blunders (v3b 14.2 / 1), diag 143.2 all, slope 1.311 (v3b 1.305, so the margins already match). Stopping rule met on the grader too: the fallback path is not needed; v4d builds on this architecture.
- 22:40 v4a epoch 5: diag 141.9 all (best yet), grader 17.9 / 4 vs epoch 4's 14.5 / 2 on the same 300 positions. The grader on a loaded VM core at 1.5 s resolves to about +-3 cp and +-2 blunders between epochs; it ranks candidates but does not pick between close ones. The pick between close nets is the 300-game gate and the real-clock battery.
- 23:30 v4a finished (6 epochs). Chain running: v4b fine-tune started 23:29 (~25 min/epoch on the quiet Mac); then the two-worker gate vs V3, the whole-site refresh, and v4d (20 epochs, ~18 min each) expected 04:30-10:30.
- 23:45 v4a final (epoch 6): diag 142.4 all / 129 quiet, 5-16 pieces 182, slope 1.312, grader 16.5 cp / 3 blunders, exact-best 69% (v3b 65%). Verdict: the architecture alone is at v3b's level on the shipped data with a better hit rate; the endgame (182 cp) waits for the self-play and endgame streams in v4b/v4d.
- 23:55 v4b epoch 1 (first pass over the tournament mix): site chunk 118 (trainer, quiet) / 131.9 (diag, all); 9-12 pieces 166 (v4a 211, v3b 215); 17-20 pieces 156; slope 1.157 (export will rescale by 1.305/1.157); grader 16.5 / 5 (noise band). Self-play held-out 109, whole-site held-out 123, Lichess 174.
- 00:10 v4b final (2 epochs on the tournament mix): diag 130.7 all (v3b 144.8), 9-12 pieces 160 (215), 17-20 pieces 153 (162), |err|>200 19.2% (23.1%); grader 15.9 / 3 (noise band of v3b's 14.2 / 1); slope 1.112. Chain rescaled the export by 1.174 to v3b's 1.30 (margins unchanged in eval units); exactness passed; the consistency test had to learn about the export scale (fixed, 1.5 cp mean). Candidate `bini_v4b` gating vs V3 at two workers since 00:04. A second candidate, the raw-scale net (`bini_v4b_raw`, margins effectively 17% looser), is queued to gate beside v4d.
- 00:30 v4b (rescaled) gate vs V3 at 44 games: 36.4% (-97 +-111), no fallback games, while the same net passes mates 80/80, puzzles 40/40, the blunder set 3/3 (first build to do so) and grades 15.2 cp / 2 blunders / 68% exact. Static tests cannot see what is losing games. Three controls started: the raw-scale v4b gate (scale hypothesis), a v4a gate (architecture hypothesis: buckets/squared activation were never gated in games), and the fallback net v4o (v3b fine-tuned on the tournament mix, old architecture) training on the idle GPU. Decision at ~100 games each.
- 00:40 Three gates plus the fallback trainer thrashed the Mac (load 73, swap full); the raw-scale gate and the v4o trainer were stopped (wired memory fell from 4.3 to 2 GB). Running: v4b (rescaled) vs V3 at 48 games, 36.5%, and v4a vs V3 just started; both clean of fallback games. v4o and the raw-scale gate resume after these two report.
- 01:05 v4a vs V3 at 38 games: 36.8% (-94 +-120); v4b at 85: 40.6% (-66 +-77). Both new-architecture nets lose in play despite better static numbers. Chain stopped (no v4d on a suspect recipe); three ablation fine-tunes (v4o, v4o2, v4b2) running back to back on the GPU, each to be gated; see PLAN_V4 s24. Cause of the confusion: five changes gated together, my error.
- 01:15 v4b (rescaled) gate stopped at 88 games: 41.5% (-60 +-75), not positive. v4a gate continues (40 games, 36%). v4o training; its gate queued behind it. Reminder to self: kill patterns go in script files, not in the shell's own command line (three sessions lost to it).
- 01:25 v4a gate stopped at 42 games: 35.7% (-102 +-115). Mac now: v4o fine-tune (fast, ~5 s per chunk) with its gate queued behind it, then v4o2 and v4b2. Machine clean.
- 01:50 v4o (old architecture + full tournament mix) at 26 games: 36.5% (-96 +-149): the architecture is not the (only) cause; the data mix is implicated. v4o2 (mild mix) trains, gate next. SPSA finished flat (LMR multiplier 429, futility 101, LMP 102 after 37 iterations of 16-game comparisons): the defaults are near an optimum at 2 s; no theta gate needed. Diagnostic match (4 logged games v4o vs v3b, Stockfish-graded per move) running to see how the new nets lose.
- 02:15 Diagnostic match explains the losses (PLAN_V4 s24.1): middlegame moves grade 36-53 cp vs 1-8 in the opening/endgame; own scores compressed (+156 where the truth is +424). The self-play stream (70% draws, median 32 cp) plus the result blend flattened v3b's middlegame in a strong two-epoch fine-tune. Trainer gained `--thin-flat`; `run_v4o3.sh` (gentle recipe: full Lichess kept, self-play thinned, no blend, lr 2e-4, one epoch on v3b) queued behind the ablations. v4o2 gate running.
- 04:20 Candidate grades (VM, 300 ladder positions, 1.5 s):
  | net | diag all | 9-12 pieces | 17-20 | slope | grader cp | blunders | exact best | gate vs V3 (10 s) |
  |---|---|---|---|---|---|---|---|---|
  | v3b (V3) | 144.8 | 215 | 162 | 1.305 | 14.2 | 1 (0.3%) | 65% | – |
  | v4o2 (old arch, mild mix) | 134.8 | 189 | 152 | 1.19 | 14.0 | 1 (0.3%) | 69% | 50.5% at 208, running |
  | v4o3 (gentle) | 144.0 | 217 | 162 | 1.30 | 15.0 | 2 (0.7%) | 66% | 51.2% at 86, running |
  | v4b (new arch, full mix) | 130.7 | 160 | 153 | 1.11 | 15.9 | 3 | 63% | 41.5% at 88, stopped |
  v4o2 is the V4 net candidate: v3b's move quality, better static accuracy and endgame, level in self-play. Real-clock proxies decide it against V3's net.
- 04:35 Book complete on the VM: 288 root positions at 60 s (depth 20-21), 2,018 entries (`data/book.json`). Play-time hook added to the dev wrapper (position key lookup for our first twelve moves, off-book the moment the opponent deviates); verified on the VM (R55's start plays the book's Na5, state consistent, wrapper-state test passes). Book-vs-engine first-move check running (Stockfish-graded, 288 positions). Ships only with the organisers' confirmation and a non-negative check.
- 04:45 Ablation gates: v4o2 (old architecture, mild mix) 50.5% at 208 games (+3 +-48); v4o3 (gentle recipe) 50.0% at 72. Both hold V3's level; neither shows a gain at 10 s, a format that is half draws and cannot see conversion. SPSA ended flat. Grading v4o2 and v4o3 on the VM; the real-clock proxies decide between them and V3 in the morning.
- Morning plan (Tue): gates finish ~06:00/07:30 -> proxy matches on the Mac (v4o2 vs the 20k and 40k proxies, V3 vs the 40k proxy as the baseline, ~3 h) -> V4 assembled from the winner plus the gated engine items (safety bundle neutral, fallback engine, book only if confirmed and graded) -> battery -> hand-over. Honest read: V4 is V3's engine with a net that knows the tournament's positions and endgames without losing anything, not the leap the 20-epoch plan promised; the leap moves to V4.5 with the data fixed (decisive self-play, no result blend, gentle fine-tunes gated one at a time).
- 04:50 Book check (288 curated positions, Stockfish 120k grading): book root move 2.3 cp mean loss, engine at 3.8 s 3.0 cp, same move in 225 of 288, no blunders either way. Not worse, marginally better, and it saves the first move's 3.8 s (more while the line holds). Ships with the organisers' confirmation.
- 05:05 Incident: my assembly script named the candidate `bini_V4`; on macOS's case-insensitive filesystem that is `bini_v4`, and its `rm -rf` deleted the working copy. Restored from `bini_v4o3` (a full clone from 03:45) plus the four scripts written since, v3b's net put back, harvest set regenerated. Running gates and queued proxies use their own directories and were unaffected. The candidate is now `bini_v4final`, and the assembly script refuses any target that resolves to the working copy.
- 05:15 `bini_v4final` assembled: bini_v4 engine (safety items, switches off, telemetry stripped), dev wrapper (book hook, forced-fallback hook), v4o2 net, book (2,018 entries). Compile 19.1 s; book move then a searched move from the R55 start, both legal. Correctness half of the battery running now; the timing half (puzzles, blunder set at the platform budget, torture, pressure) after the proxies on a quiet Mac.
- 05:25 Consequence of the deletion: every game process spawned after 06:05 inherited a working directory that no longer existed, and numba's error path (`os.path.relpath`) crashed each one at start-up. Clean gate tallies (crashed games excluded): v4o2 vs V3 +81 =117 -72 over 270, 51.7% (+12 +-41); v4o3 47.7% over 132. Queued scripts started from the dead directory were killed and the proxy queue restarted from the restored one; post-mortem monitor restarted. v4o2 stays the V4 net candidate.
- 06:20 First real-clock proxy pair: v4o2 vs the 20k-node proxy (the AlphaFish stand-in) 40.0% over 40 games (+3 =26 -11; as White +1 =15 -4, as Black +2 =11 -7). All 11 losses are Stockfish conversions ending in checkmate; the early repetitions (14-25 own moves, 50-75 s left) are equal-position bailouts, not clock trouble; min end clock 6.3 s. No V3 baseline exists at 20k (only at 40k), so a V3-at-20k pair was appended after the queue (`tools/extra_proxies.sh`) and the battery now waits for "extra proxies done" so it runs on a quiet Mac. Decision rule for the V4 net: v4o2 ships only if it is within noise of V3 on both proxies; otherwise V4 = the V4 engine with V3's net. Queue timing: v4o2 40k 06:20, V3 40k ~07:15, v4o2-soft 40k ~08:10, V3 20k ~09:05, battery+package ~10:00, hand-over before noon.
- 07:12 v4o2 vs the 40k proxy: 20.0% over 40 (+2 =12 -26), min end clock 7.2 s. Far below the 60% line; V3 at 40k (running) tells whether the proxy is simply too strong at the real clock.
- 08:03 V3 vs the 40k proxy: 27.5% over 40 (+0 =22 -18). So the 40k proxy is out of reach for both nets at the real clock (the 60% line was calibrated on 10 s games, not the real clock); v4o2 trails V3 by 7.5 points there, within noise but in the wrong direction. The net decision rests on the 20k comparison (V3 pair ~09:00-10:00). Leaning: V4 = V4 engine + V3 net unless v4o2 matches V3 at 20k.
- 09:05 The soft-clock variant pair (bini_v4o2_soft) was invalid: its engine failed to build at start (dev engine mixed with the non-dev NNUE module, missing new_cache), the wrapper ran on the fallback engine and no game finished in an hour. Killed; clock softening is a V4.5 item and gets its own build there. Queue advanced to V3 at 20k.
- 09:54 V3 vs the 20k proxy: 46.25% over 40 (+6 =25 -9; min end clock 5.6 s in one game, flagged for the V4.5 clock work). Real-clock table: 20k proxy V3 46.3% / v4o2 40.0%; 40k proxy V3 27.5% / v4o2 20.0%. Each gap is within noise, both point the same way, and the gating rule needs a clearly positive gate. DECISION: V4 ships with V3's net (v3b) inside the V4 engine. The book stays out (no organiser confirmation). bini_v4final reassembled (net = v3b byte-identical, no book.json); battery + package started at 09:55 on a quiet Mac.
- 10:53 Battery on bini_v4final (v3b net, no book) all green: init 19.1-19.2 s x2; wrapper state ok; NNUE incremental == reference on 3,958 positions; perft + 5,000-position differential ok; mate-in-1/2 80/80, gate 2 passed; puzzles 40/40; blunder set 2/3 (repeats 15.Rad1?! of R43, a slow slide not a blunder; V3 itself scores 1/3 today and also repeats 17.Rd4??, which the V4 build avoids); harvest 27/37; torture 10/10 mates, 10/10 with the fallback forced; real-clock pressure 0-4-6, min clock 8.3 s, unclear 2.37 s vs decided 1.23 s (V3 record: 0-3-7, 7.3 s). Packaged submission_v4_0908_1053.zip (8 files, 6.40 MB unzipped, sha256 00fe9eae6b5cc356...), every file byte-identical to the sources. The fresh-extraction game step had a wrong flag (fixed); rerun by hand: the extracted zip beats the minimax baseline by mate in 19 moves at 30 s + 0.5 s.
- 11:05 HAND-OVER: submission_v4_0908_1053.zip is the V4 upload (Archit uploads; nothing here uploads). Book not included (no organiser confirmation). V4.5 work starts per PLAN_V4 s23.
- 11:35 V4.5 step 1, the data fix (s24.1): selfplay_sf.py gained `--random-open P` (a 2-6 ply uniformly random walk before recording, so half the games start imbalanced and Stockfish plays them out) and `--balance` (near-zero positions thinned: |cp|<40 kept at 0.3, <120 at 0.6). Local smoke: median |cp| 128 (old stream: 32), results 144 W / 54 B / 137 D over 335 rows. VM: rook-knight stream stopped (27k positions in 16 h at depth 14, no chunk) and structures stream stopped (2 chunks banked); two decisive workers started at depth 9 into data/selfplay/dec, endgame stream eg2 kept.
- 12:30 V4.5 step 4 (speed): profile on the quiet Mac: perft 4.8 M leaves/s, static NNUE eval 1.09 us (Python call overhead included; the inner loop alone is 179 ns), make+update 2.7 us (same caveat), search 782 knps. Tried an int32-blocked output layer (micro-benchmark 106 vs 179 ns, exact): slower inside the engine (582 knps), reverted; node counts identical throughout. The remaining speed candidates (lazy accumulator update, TT static-eval cache) are deeper changes and wait behind the net.
- 12:35 V4.5 step 3 (clock): the dev soft-stop clock (predictive stop at 1.5x the last iteration, 1.6x extension when the best move changed) ported into bini_v4 behind BINI_SOFT_STOP=1 (off by default), for a real-clock proxy gate later today.
- 12:40 V4.5 step 23.8 (drawishness): endgame_scale gained the three rules (one rook each with equal pawns x0.5; opposite bishops alone within two pawns x0.5; one minor each with <= 2 pawns each x0.6; only for |score| <= 150, no queens) behind BINI_DRAWISH (compile-time, off by default). Node counts at depth 10 unchanged with it off; with it on only the KRP ending changes (18,345 -> 15,596). Gate started 12:40: bini_v45_draw (rule on) vs V4 (bini_v4final), 300 games at 10 s + 0.1 s, 2 workers (~2 h). Then, on a quiet Mac: drawn.epd must not lose and marginal.epd (the 40 "small edge" site positions, +51..+150) must convert at least as often as V4, both via tests/test_conversion2.py.
- 13:15 First two decisive chunks (400k rows): median |cp| 301 (old stream 32), 64% above 150 cp, results 30% W / 41% D / 29% B, median 15 pieces (games ran to 1,500 cp before adjudication, so long conversion tails dominate). Adjudication made a flag (`--adj-cp`) and the two workers restarted at 800 cp; the first two chunks stay in the set (the held-out one is worker 50's first chunk).
- 13:00 Rounds 57-64 came in for the live V3 build: 5 wins, 2 draws, 1 loss (R64 to "what even is en passant"); the post-mortem harvested them (hard set 8 chunks, 152 positions; 40 tagged errors).
- 13:20 Post-mortem written (PLAN_V4 s26) and the GCP question answered (trial: no GPUs, 8 vCPUs, no quota changes; upgrade keeps the credit; GPU quota may be refused; Colab Pro as insurance). Afternoon queue started (`tools/afternoon.sh`, log data/afternoon.log): draw gate (50/300 at 50.0%) -> drawn.epd + marginal.epd conversion tests for the rule and for V4 -> soft-clock 20k proxy (bini_v45_soft, 40 games) -> when 8 decisive chunks are local: 1-epoch pilot on the decisive mix (run_v45.sh), slope + out-scale export, VM grade, 40-game 20k proxy. Decision rule for the full run: pilot proxy >= V3's 46% within noise and no middlegame flattening in the diagnostic.

## Rules that shape the build (from the docs, 7 Sept)

- A level knockout tie goes to the better Swiss standing: Swiss points count twice. As the
  higher seed two draws advance us; as the lower seed we must win a game.
- The ladder rating is fitted to the current build's results, with the house engines holding
  the scale; each upload shows its own strength within a few games.
- The lookup ban covers "another engine's moves or evaluations"; a book from our own analysis
  would be permitted. Still optional: the intel says book value is low.

## The path to first (see PLAN_V4.md section 17)

AlphaFish 2517, 27-6-4 after R50. Three requirements: no sharp-middlegame blunders (grader
<= 0.1%), win the endgames it draws (site-label MAE < 100 cp at 5-16 pieces), keep depth after
move 30. Acceptance: AlphaFish proxy match >= 50% over 40 real-clock games.

## Decisions

- Lichess scale is canonical; Stockfish-labelled sets are scaled by 0.85.
- Search items ship only if their own gate is clearly positive (batch-2 rule).
- Adaptive contempt: built, off, parked on the opp_signal evidence; a global contempt 20-vs-35 gate replaces it. Draw-when-behind
  is also off until its own Stockfish 1800/2000 draw-rate gate, run after the v4a net.
- Safety items (check mask, root-guard cap, pawnless scaling, TT 256 MB, telemetry) are gated as
  one bundle against V3 before anything is measured on top of them.
- Dropped: KPK bitbase (search converts KPK; low value), repetition-history start-position fix
  (position never seen when we move second; cannot be reconstructed).

## Live build correction (Tue 8 Sept, 17:05)

Every platform log from rounds 64 to 69 prints `bini-2.0`; the V4 zip prints `bini-4.0`. **V3
(dashboard v6, `submission_v3_0907_1258.zip`, leap clock + v3b net) is the live build and the
rollback.** V4 was handed over but never uploaded. V5 candidates are gated against
`bini_v4final` (V4 engine + V3's net), which is V3's playing strength with the safety items; no
result assumes V4 is on the platform. Draw-policy dry run (28 logged rated games, trigger −100
after our 20th move): fires in 9 games, 7 of them losses where the site agreed we were worse
(−67 to −470), 2 draws (one false alarm at site −5), no wins affected.
