# V8 handover — Wednesday 9 September 2026, 23:00 London

**Live build: V7k**, uploaded 20:27 BST, md5 `246fe9fa97439a1abd832a2a6c9b18c8`, zip
`submission_v7k_0909_2040.zip` (7,109,016 bytes; 14 MB unzipped). **Rollback: V6.5**
(`submission_v6.5_0909_1603.zip`, md5 `6dd0c7181772e850f1a48cd8628a512f`).

Plan of record: `Project Prometheus.md` (section 13 is the dated experiment log). Strategy and the
ranked experiment list: `V8Plan.md`. This file is the state at hand-over.

---

## 0. Where we got to today

| Build | Change | Gain | Instrument |
|---|---|---|---|
| V6.0 (10:53) | net r1, 3x book | +72 | fixed nodes |
| V6.5 (16:03) | net s48 (48 superbatches), LMR_DIV 1.6, int16 accumulators | **+125 ±22** | 5 s, 576 games |
| **V7k (20:27)** | net k96 (1024-wide), correction history, continuation history | **+39 ±21** | 30 s, 400 games |

**About +164 over V6.0 in a day.** Ladder 2396 -> 2511 (rank 19 -> 17 of 432).

**V7k in the wild, 2 games:** R89 beat Challenger by checkmate (clean monotonic conversion
+146 -> +351 -> mate, punishing their blunder); **R90 drew Patzer 2.4, the ladder leader, as Black
at ACPL 2 / 99.5% accuracy, zero mistakes, zero blunders, depth 21-32.** V6.5 before it went three
draws, no losses, at ACPL 7, 8 and 3.

**The rating badly lags the strength.** A 2511 engine held a ~2750 engine to a flawless draw.

---

## 1. What is running right now (nothing needs restarting)

| Where | Job | Log |
|---|---|---|
| GPU 0+1 (both at ~98%) | **Hyperparameter sweep**, 6 variants of k96's recipe: lr 0.0005 / 0.0015, schedule linear / step, batch 8192 / 32768. Each gated vs k96 at 1152 games when trained. | `~/chess/logs/v8hp.log` |
| GPU box CPU | **Teacher-depth experiment**: FEN regeneration then depth-12 relabelling. Auto-scales 24 -> 64 workers when gates drain. | `~/chess/logs/v8.log`, `label_d12*.log` |
| — | V7k playing rated rounds hourly | site dashboard |

Nets land in `~/chess/data/nnue_*.safetensors`; gates in `~/chess/gates/`.

---

## 2. Tonight's results — four levers, correctly buried

All at 1728 games, fixed nodes, vs V7k's exact config, **re-scored against the correct baseline**:

| Experiment | Elo | Wins | Losses | Verdict |
|---|---|---|---|---|
| **Contempt 32** | **+6 ±10** | **+1.6pp** | **−0.2pp** | **live candidate** — the only change all night with wins up AND losses down |
| Contempt 45 | +6 ±11 | +2.4pp | +0.7pp | overshoots; 32 is the value |
| Anti-simplification 12 / 24 | −6 / **−49** | −1.4 / −4.9pp | +0.3 / **+9.0pp** | **dead** |
| Drawishness (Q+P, opp-bishops) | −0 / −4 / −2 | ~0 | ~0 | **dead** |
| **Book (never measured before)** | book 2.3 cp loss vs engine 3.0 cp, 0 blunders in 250 | | | **keep** |

**Contempt 32 is the one survivor and it is small.** It does not clear the +20 ship bar alone; it is
a candidate for the combination gate only.

---

## 3. Instrument work — the real deliverable of the evening

**Read this section before running any gate.**

**I0 — the clock bug.** `agent._budget` has four ABSOLUTE thresholds (4000 / 30000 / 10000 ms and
RESERVE_MS) tuned for the platform's 120 s base. `node_gate.py` copied them while scaling only the
increment. At `--tc 5+0.05` the engine dropped into the emergency branch after one move and played
**~20 ms a move for the rest of every game**. **Every "5 s" and "10 s" verdict this project ever
produced — including V6.5's headline — was a fixed-node verdict wearing a clock.**
Fixed: `CLOCK_SCALE = base_ms / 120000` scales all four. Verified **identical to `agent._budget` at
120+0.5 across 5,432 points**. Deployed to all boxes. The shipped `agent.py` is untouched.

**I1/I1b — the harness is clean.** A-vs-A, 400 games at 30+0.125: **49.9% (−1 ±15)**, decisive 54-55.
A-vs-A at fixed nodes, 1728 games: **exactly 50.0%, ±0, pentanomial [0, 0, 864, 0, 0]** — every pair
mirrored. **V7k's +39 needs no correction.**

**I2 — rate reporting.** `bini_v65/tools/gate_rates.py <gate.json> [baseline.json]` reports win /
loss / decisive rates and the two thesis rules. **Baseline must be the same instrument**: use
`gates/base_f30k.json` for fixed-node gates, `gates/i1b_aa30.json` for timed. I got this wrong for
several hours and it manufactured a phantom "+17 to +22pp decisive" on every experiment.

**The rule that keeps being learned the hard way: fixed-node gates are blind to anything touching
speed, and cross-instrument comparisons are meaningless.** It cost us the 1024 net three times, a
float32 rewrite, and a night of decisive-rate numbers.

---

## 4. What is closed, with numbers — do not reopen

| Lever | Evidence |
|---|---|
| Training data volume | 712M vs 490M at matched compute = **+2 ±22** |
| Epoch budget | 24 = +13, 48 = +44, 96 = +59, **144 = +57** — peaks at 96 |
| King buckets | 16 = +14 vs 8 = +15 at matched budget — neutral |
| **Net width** | 512 -> 1024 = **+23 timed**; 1024 -> 1536 = **−30**; 1024 -> 2048 = **−4 at fixed nodes** (which flatters wide nets). **1024 is the optimum.** |
| Eleven search constants | LMR_DIV was the only bad one. SEE_Q +4 ±11, LMR_BASE +2 ±14 on the shipped config |
| Three disabled features | ProbCut −8, qs_checks −10, improving −7 |
| Inference speed | Seven implementations measured in situ; the shipped scalar integer loop (702 ns) wins. No compiler on the image (`Info.md` line 40) |
| Calibration table | v3b-fitted table scores −31 on the current net; `V8Plan.md` §6 argues the refit is redundant with the net's 8 output buckets |

---

## 5. The two live bets

**A. Teacher depth — the only axis never varied.** Every net this project ever trained learned from
**Stockfish at depth 7**. We swept volume, epochs, width and buckets and never once asked whether a
better teacher on fewer positions beats a worse teacher on more. A network cannot exceed what it
imitates, and depth 7 is weakest exactly in the closed middlegames and endgames where our games are
decided — the "reads closed middlegames 100-250 cp too optimistically" diagnosis has now survived
four net generations unchanged.
Design: **the same positions relabelled at depth 12**, so teacher quality is the only variable, with
the endgame (`shard_007*`) and elite late-ply (`shard_009*`) streams included because that is where
depth pays. **Train two ways**: from-scratch at matched volume (the clean control) and a **fine-tune
of k96** (the likelier winner — needs far less data and directly corrects the teacher's systematic
error). Gate at fixed nodes vs k96, then 30+0.125.

**B. Hyperparameter sweep.** k96's entire recipe is `lr 0.001, cosine`, inherited from r1 four
generations ago and never questioned. Six variants training now. Small-effect knobs, but free.

---

## 6. The finding that decides the NEXT competition, not this one

**Batched native inference is 8-11x faster than numba.** Measured on the Mac with the preinstalled
torch 2.13: batch 1 = 3,305 ns/position (4x slower than our numba eval, so per-node is dead), batch
64 = **97 ns**, batch 256 = **68 ns**, against our 762 ns.

**Alpha-beta cannot use it** — the search needs each evaluation before choosing the next node.
**MCTS can**: it expands many leaves before needing any value. That is why a hobby transformer +
MCTS reaches a far higher level than its raw network. With batching we could afford an evaluator
**10x the size of k96**.

That is a policy head, a training pipeline, an MCTS and a full validation burden. **It does not fit
before Friday 11:00.** It is the right answer for next time and it is written down here so it is not
rediscovered from scratch.

---

## 7. Diagnosis: what actually loses us games (an earlier theory was wrong)

**Retracted:** "our losses are move-quality collapses (ACPL 31-92) — a reliability tail." That was
built on the site's ACPL, which is measured over ALL positions including hopeless ones. Losing a
game **produces** high ACPL; it is not caused by it. Every "worst move" in a lost game happened when
we were already **−650 to −4,000**.

**What the data actually says** (63 rated games with site evaluations):

| | Lost (14) | Not lost (49) |
|---|---|---|
| **Our max advantage all game** | **+39** (median +22) | +6195 (median +60) |
| Opponent's ACPL | 31.1 | 33.1 |

**We do not lose won positions. We lose games we were never winning** — and our opponents played no
better in them. That is also why all four "convert an advantage" levers measured zero: in the games
we lose, there is no advantage to convert.

Per-opening and per-colour splits (White 43.8% vs Black 56.2%; Ruy Lopez Closed 16.7%) are **not
significant** — n=16 and n=3. Do not act on them.

---

## 8. Thursday, in order

1. **Read** `logs/v8hp.log` (6 HP verdicts) and `logs/v8.log` (depth-12 progress).
2. **Train the depth-12 nets** as soon as enough shards exist: fine-tune k96 first, then the
   matched-volume from-scratch control. Gate at fixed nodes vs k96; anything ≥ +25 goes to 30+0.125.
3. **Clock experiments (T1/T2 in `V8Plan.md`)** — the largest untested lever, and only testable now
   that I0 is fixed. **Must be gated at 120+0.5 or at least 60+0.25. Never at 5 s or 10 s.**
4. **Combination gate**: everything that cleared, plus contempt 32, vs V7k as uploaded, at 30+0.125,
   576+ games. Ship rule **≥ +20 with the interval clear of zero**.
5. **Anchor**: candidate vs Stockfish at 20k nodes, real clock, foreign opponent. V6.5 scored 52.5%.
6. **Battery on the exact zip**, byte-check, cold fresh-extraction game, md5.
7. **Upload V8.0 Thursday ~20:00.** Friday 10:00 for V8.1 only if it clearly beats V8.0;
   **hard stop 10:30**; default is not to upload.

**If nothing clears +20, ship nothing. V7k is a good build** — it drew the ladder leader at 99.5%
accuracy — and a marginal change is worse than no change.

---

## 9. Traps

- `node_gate.py` line 482 sets `BINI_BOOK=0`. **Every gate ever run was book-free.** The book is only
  exercised through `agent.py` (proxy_match, real games).
- `assemble_v5.sh` hardcoded `BINI_CONT` to 0 until today; it is now the 7th positional argument.
  **`bash tools/assemble_v5.sh <dir> <net> <book> CORR SEEP CALIB CONT`** — V7k needs `1 1 0 1`.
- `tools/proxy_match.py --stockfish` is dead; `tests/uci_sf.py` hardcodes `Popen(["stockfish"])`, so
  the binary must be on PATH.
- The dev tree `bini_v65` defaults to CORR=1/CONT=1; the shipped zips bake them explicitly. **Always
  pass every switch explicitly in a gate** so nothing is inherited.
- Platform init is **35-38 s**, not the 22-26 s measured on the Mac. Still 42% of the 90 s budget.
- Never trust a hot-cache microbenchmark for engine work. One said float32 was 3.9x faster; it is
  17-29% **slower** in the engine.

---

## 10. Honest odds (from `V8Plan.md` §11, unchanged by tonight)

Top five in the final Swiss **0.40** (0.50 if the "International" teams are outside the UK Swiss,
0.32 if inside). *Comfortably* top five **0.22**. First at the London knockout **0.08**.

**The target is not the ladder.** `Info.md` line 78: the ladder only seeds a 13-round Swiss over the
builds locked at Friday 11:00. **The build frozen at 11:00 is the entire deliverable**; the ~20
remaining ladder rounds are free validation on real hardware.

**Worth settling by email:** AlphaFish (#3), Patzer 2.4 (#4) and AI Fellow (#11) are listed
"International". If the final Swiss requires a UK university student, the strongest engines on the
ladder may not be in our event. Inference, not fact — and worth 30-55 points of bar.
