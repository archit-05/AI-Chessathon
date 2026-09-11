# Project Prometheus — a 2700+ engine for the AI Chessathon final

Written Tuesday 8 September 2026, 21:15 London. Uploads lock Friday 11 September 11:00; the
13-round Swiss on locked builds is Friday afternoon; the London knockout is Saturday. This is the
plan for the last 62 hours: the goal, the hardware, every lesson the week has taught, the six
levers that add up to the goal, the schedule, and the rules that keep it executable.

---

## 1. The goal, stated so it can be measured

**A locked build that plays at 2700 or better on the tournament's own ladder**, which today means:

| Yardstick | Today (V3 live, rank 18–21, 2304–2332) | 2700 |
|---|---|---|
| vs the 2300–2500 band | 60–70% | 90% |
| vs the leader (AlphaFish 2688, CPL 7.8, one blunder in 38 games) | 0–1–3 | 55–60% |
| move loss per move (site's Stockfish-16 depth-16 grader) | 12.8 cp (middlegame 13.7, endgame 13.5) | 8–9 cp, endgame under 10 |
| games lost to slow evaluation slides at moves 20–35 | 6 of the last 21 games | none: hold or draw them |
| real-clock proxy vs Stockfish at 20k nodes (≈ the leader's quality) | 46% | 60%+ |
| failures (flag, illegal, crash, init) | 0 in 42 rated games | 0 |

Two builds, not one: **V5.0**, the safe strong build, uploaded Wednesday evening so Thursday's
rated games validate it; **V5.1**, the Prometheus build, uploaded Thursday by 15:00 only if it
beats V5.0 by ≥ +30 over 400 games with the interval clear of zero and no real-clock regression.
Friday is rollback only.

---

## 2. Hardware and what each machine does

| Machine | Spec | Role | Never |
|---|---|---|---|
| Mac (M2, 8 GB RAM, MPS) | trains at ~200k rows/s when nothing else runs; 4.5 GB free at best | code, the book, the trainer until the GPU box exists, then the speed pass tests | two CPU-heavy jobs at once (it thrashes: swap sits at 7.7 GB) |
| Oracle VM `priorcrypto-vm` | 4 ARM cores, 23 GB, Stockfish 19 at 440k nps/core | self-play generation (site-start decisive stream, endgame stream), 10 s confirmations (300 games ≈ 2.5 h, generators paused) | training |
| GCP box A `gcp-x86` | 8× Sapphire Rapids, 31 GB, Stockfish 19 at 1.09M nps/core, our engine at 725 knps | elite-game labelling (Stockfish depth 10, 3M positions), endgame generation, book analysis, gates when B is busy | – |
| GCP box B `gcp-x86b` | same as A (Debian 13) | **the gate machine**: 200 games at 5 s in ~50 min, 400 in ~100 min, real-clock proxies; self-play when idle | two gates at once (the scripts wait for a free box) |
| **NVIDIA A100 instance (to rent tonight)** | 1× A100, ≥ 16 vCPUs, 200 GB disk, Ubuntu | **Leela as a batch labeller (10–20M positions/h, one evaluator for every position) and the trainer (150M rows in ~10 min per pass)**; the vCPUs run Stockfish labelling as the fallback | shipping anything from it: only our own trained weights leave the box |

Driver scripts (all in `bini_v5/tools/`): `provision_x86.sh` (any Ubuntu/Debian x86 box in ~10
min), `x86_gate.sh`, `x86_proxy.sh`, `vm_gate.sh`, `checkpoint_gate.sh`, `epoch_checkpoints.sh`,
`judge_net.sh`, `draw_gate.sh`, `vm_draw_gate.sh`, `x86_pressure_gate.sh`, `assemble_v5.sh`,
`book_merge.sh`, `pull_loop.sh`. Every machine's kill patterns live in script files.

---

## 3. Lessons learned (the whole week, in the order they cost us)

**On measurement**
1. **A 40-game gate is worth ±12 points.** Two bit-identical engines scored 40% and 49% in two
   40-game samples tonight. Every "verdict" this week on fewer than 200 games was noise,
   including the afternoon's search screens. 200 games (±7) is the minimum to steer; 400 (±5)
   to ship; real-clock proxies before any hand-over.
2. **Static metrics do not order nets by strength.** Every retrained net this week (v4a, v4b,
   v4o, V5 run A, run D) graded better on the site's labels and was level or worse in games.
   Games are the only instrument.
3. **Control experiments before conclusions.** The export path, the gate host and the trainer
   were each suspected tonight and each cleared by a control (re-export vs original: identical
   weights; v3b vs v3b: 48.8%; v3b's recipe rerun: 48.2%). Without the controls we would have
   rewritten a sound trainer.

**On the network**
4. **Mixed label sources hurt.** Lichess (many Stockfish versions and depths), Stockfish 16
   depth 16 (site), Stockfish 19 depth 9–10 (self-play, elite) have different scales and
   horizons; a global 0.85 fit does not reconcile them. The only net that gained (v3b, +39)
   was the most single-sourced. The Prometheus net uses **one evaluator for every position**.
5. **Draw-heavy self-play flattens the evaluation** (V4: 70% draws, median label 32 cp); the
   fix is decisive games from random walks or from real middlegame positions, and no result
   blend on data that is not consistent self-play.
6. **Fine-tuning a good net on a small shifted set at a high rate destroys what it knew**;
   gentle fine-tunes are level at best. From scratch on consistent data is the way to a gain.
7. **The net's failure mode is systematic**: 100–250 cp too optimistic in closed middlegames
   (R55, R56, R64, R65, R67, R68 all slides), 3× the error at 5–20 pieces, wrong by 200 cp on
   minor-piece-vs-pawn endings. The calibration table measures it (128 non-zero cells).

**On search and time**
8. Search features at our level are worth +10 to +30 each and cannot be seen at 100 games;
   a bugged one (correction history v1, saturating tables) costs −130 and *can* be seen.
9. The front-loaded clock (leap build) was worth +27 points on the proxy: time matters; the
   book now buys 15–25 s per game, and the moves-16-to-35 window is where to spend it.
10. **Draw discipline is worth more than move quality on this ladder.** PSL (11.1 cp, 11
    blunders) is rated above Capablanca (10.2 cp); multi millionare (18.4 cp) is 2568 on 15
    repetition draws. Our 0-1-3 against 2450+ is the rating gap; the draw-when-worse policy
    would have turned 7 of our 9 qualifying losses into draws.

**On operations**
11. The 8 GB Mac stalls the trainer at 1–4% CPU the moment a second job runs; MPS pins 2 GB
    wired. Trainer alone, everything else elsewhere.
12. Inline `pkill -f` patterns kill the shell that issued them; a rename of a working copy on
    a case-insensitive filesystem deleted it; a script named `profile.py` shadowed the standard
    library and killed torch's import. Kill patterns in files, guards on every destructive
    step, `bini_*` names only.
13. Nothing that is not through its own gate and the full battery ships; the rollback zip is
    always the previous gated build (today: V3, `submission_v3_0907_1258.zip`; V4 was never
    uploaded).

---

## 4. The six levers and what they add up to

| Lever | Mechanism | Gain (ladder points) | State at 21:15 |
|---|---|---|---|
| **Evaluation (Prometheus net)** | Leela on the A100 labels 150–250M positions (elite human games, the tournament's own games, our self-play from tournament structures, a Lichess slice) with one scale and one horizon; from-scratch runs of the proven 512-wide net, the piece-count-output variant and a 1024-wide net; each fully annealed and judged by 200 then 400 games | +80 to +150 | needs the GPU box |
| **Draw discipline** | repetition/fifty-move draw scored 0 (not −20) once we are worse than −100 after our 20th move | +60 to +100 vs this field | built; gating tonight vs Stockfish 2000 (draw rate must not rise) and full strength (draws must rise) |
| **Speed** | 16-bit accumulators, staged move generation, table improvements; every change proven node-count identical at fixed depth | +40 to +60 (one ply) | Wednesday, on the Mac once training moves to the GPU |
| **Search features** | SEE pruning (54% at 100), continuation history, re-tested at 400 games on the gate box | +20 to +40 | built behind switches |
| **Book and clock** | 4,926 graded book entries (mean loss 1.7 cp, none over 15); midgame time boost on moves 16–35 | +20 to +30 | book done; boost built, needs a real-clock gate |
| **Calibration / refit (if the net does not land)** | v3b's measured bias table by piece count × material; last-layer refit on the tournament's positions | +10 to +40 | calibration 52.7% at 132/200, refit 48.5% at 65/200 |

Sum if everything lands: +250 to +410 over today's 2320, i.e. **2570 to 2730**; median about
2620–2650. The 2700 line needs the net at the top of its range and the 1024 variant to earn its
speed cost. Probability of 2700+ with the GPU: 25–30%; of 2550+: 70%; the floor (V5.0) is
2420–2470 whatever happens.

---

## 5. Phases and timeline

| When | GPU box | GCP A / B | VM | Mac | Milestone |
|---|---|---|---|---|---|
| Tue 21:15–01:00 | provision (CUDA torch, Leela + strong net, our tools), upload elite games + site positions (30–60 min), start 8–16 labellers | A: elite labelling, endgame gen, book deep pass; B: refit gate → pressure draw gate | run D final → SF-2000 draw gate | run E (v3b + 4× whole-game) → 200 games | **V5.0 candidate assembled** (v3b or the best of E/calib/refit, + draw policy + book + SEE) |
| Wed 01:00–08:00 | labelling to 100M+; first from-scratch 512 run at ~50M (04:00), judged by 05:30; second run at 100M | 200-game checkpoints of every GPU candidate | generation | V5.0 battery (pressure 10, torture, suites) | V5.0 battery green by 08:00 |
| Wed 08:00–13:00 | 150M+ runs: 512 final, piece-count outputs, 1024-wide | 400-game confirmations of anything ≥ 53%; real-clock proxies | 300 at 10 s for the survivor | speed pass (node-count-exact), search features at 400 on B | net decision 13:00 |
| Wed 13:00–19:00 | last run with all labels | 1000-game regression V5.0 vs V3 engine; proxies for the final zip | – | assembly, package, byte-check, fresh-extraction game | **V5.0 hand-over Wed evening; Archit uploads** |
| Wed 19:00–Thu 08:00 | final Prometheus candidate(s) | 400 games + proxies | 10 s confirmation | – | V5.1 candidate |
| Thu 08:00–15:00 | – | regression V5.1 vs V5.0 (1000), proxies | – | battery | **V5.1 uploaded by 15:00 only if ≥ +30 clear of zero** |
| Fri before 11:00 | – | – | – | – | rollback only |

---

## 6. Rules of execution (how "no mistakes" is enforced)

1. Games decide. 200 to steer, 400 to ship, real-clock proxies before any hand-over. Anything
   called "dropped" or "failed" on fewer games is reopened when a box is free.
2. One change per gate. One gate per box (the scripts wait). Generators are paused only by the
   gate that needs the box and resumed by the same script.
3. Every training run is fully annealed before it is judged; no mid-schedule checkpoints.
4. Every speed change ships only with identical node counts at fixed depth and the exactness
   suite green.
5. The safe build always exists before the ambitious one is attempted; the rollback zip is
   tagged; the battery is never compressed.
6. The Mac runs one heavy job. Destructive shell steps live in scripts that list their targets.
7. Everything shipped is our own code and our own trained weights; the labeller (Leela or
   Stockfish) never enters the zip; the book is our engine's analysis with its builder and log in
   the repo; the calibration table is a tuned evaluation term.

---

## 7. Where everything stands (21:15)

- Live: V3 (bini-2.0). Rollback: `submission_v3_0907_1258.zip`.
- Net candidates at 200 games vs v3b: run A e4 35.5% (closed), D3 48.2% (trainer cleared),
  run D e0 44.1% at 194 (level-to-negative), calibration 52.7% at 132, refit 48.5% at 65,
  run E training (export ~21:40).
- Search: SEE pruning +28 ±69 at 100 (to 400), continuation history −11 ±61 at 129 (to 400),
  correction history dropped (−131 buggy, −10 fixed).
- Draw policy: dry run 7 of 9 qualifying losses become draws; gates queued (VM: SF 2000 on/off;
  B: full-strength pressure on/off).
- Book: pass 1 graded (4,926 entries); deep pass running on A.
- Data: 47 decisive site-start chunks (9.4M rows) + 9 endgame chunks; elite labels 1.1M of 3M
  (paused while A plays); the A100's Leela labels replace all of this as the training set once
  they exist.
- Intel: hourly loop live; the field's top eight lose by slides and by draw discipline, not by
  blunders (V5 Plan s14).

---

## 8. Risks and their answers

| Risk | Answer |
|---|---|
| Leela will not build or run on the rented box | the box's vCPUs run Stockfish depth 10 at ~1/5 of the rate; the plan degrades to 30–50M labels, still single-source |
| The consistent-label hypothesis is wrong and the Prometheus net is level too | V5.0 ships (2420–2470); the calibration table and refit are the remaining net levers; the speed pass and search features still add +60–100 |
| Upload bandwidth (elite games ~1 GB, positions ~13 GB) | elite PGNs first (the labeller needs only those to start), Lichess slice last |
| Judging capacity (about 20 verdicts before Wednesday noon) | the candidate list is fixed at four; nothing is added until one clears |
| A gate polluted by a co-running job | one gate per box, enforced in the scripts; contaminated gates are rerun, not tallied |
| Compile time with a 1024-wide net | +2–3 s (V5 is 34 s on the platform's scale); the 90 s budget holds |
| Fatigue-driven mistakes overnight | every chain is a script with logs; nothing is typed at 3 am that is not a script |

---

## 9. What Archit does

1. Rent the A100 instance (Lambda or RunPod: one A100, ≥ 16 vCPUs, 200 GB disk, Ubuntu, the
   same ssh key) and send the IP. Everything else on it is scripted.
2. Upload V5.0 Wednesday evening when handed over; bring back its validation log.
3. Keep the Mac free of other applications while it trains or runs the battery.
4. Thursday 15:00: upload V5.1 if, and only if, the hand-over note says it cleared.
