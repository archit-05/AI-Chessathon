# Bini v2 — Plan to rank first at AI Chessathon

Written 5 Sept 2026 (Saturday evening). Uploads close Friday 11 Sept 11:00. Final Swiss on
locked builds Friday afternoon; London knockout Saturday 12 Sept.

## 0. Operating model (agreed 5 Sept, 21:10)

- **One builder.** Claude writes every line of the engine, tests and tooling; Archit uploads and
  brings back the platform logs. Grigory is not writing code. The two-track split in section 8
  therefore runs sequentially: engine core -> hand-crafted evaluation -> wrapper and tests -> NNUE.
- **One upload strategy.** We do not iterate on the ladder. The first upload is the finished
  system, verified locally under the real harness. Only if the ladder result is clearly below
  target do we tweak; if it performs, nothing changes before the Friday 11:00 lock.
- **Build order and gates** (each gate must pass before the next step starts):
  1. `bini_board.py`: bitboards, magics, make/unmake, Zobrist. Gate: perft exact on the standard
     suite + 200k-position differential test against python-chess.
  2. `bini_search.py` + `bini_eval.py` (tapered HCE): iterative deepening, PVS, TT, ordering,
     null-move, LMR, futility, qsearch with SEE, repetition, time abort. Gate: WAC >= 85% at 1 s,
     torture arena vs random with zero failures, compile time < 35 s locally.
  3. `agent.py` wrapper: FEN-only history reconstruction, time manager, legality check, fallback.
     Gate: 200 fast harness games with zero crash/illegal/flag; beats v1-style baseline > 95%.
  4. NNUE: data -> training -> quantisation -> numba inference -> verification -> arena gate
     (>= +100 Elo vs HCE at 10 s + 0.1 s), otherwise ship HCE.
  5. Final: dress rehearsal at 0.65x time, RSS check, `make zip`, hand over.

## 1. Where we stand, in one screen

| Fact | Value | Source |
|---|---|---|
| Our rating / rank | 1250, 233rd of 291 | dashboard |
| Our record | 0W 3D 2L | dashboard |
| Our speed | ~44k nodes/s on the EPYC, depth 5–6, fixed depth | round logs (406,349n in 9,260ms) |
| Our eval | material + tiny PST (scores step by 10cp; Kf1 losing castling scored +100) | round 25 log |
| Clock use | left 17–43 s unused at game end; slowest moves 9–10 s | games csv |
| Top of ladder | 2179 (AlphaFish), 2151, 2145; top-10 cut ~2017 | leaderboard |
| Calibration | house bots: Loki 3.0 = CCRL 2428, Zagreus 5.0 = CCRL 2168, Rustic Alpha 3 = 1792 | leaderboard |
| Platform | 1 core AMD EPYC 9V74 2.6 GHz, 2 GB, Python 3.12, numba 0.67, no network | docs |
| Local probe | numba compiles 4 non-trivial functions in 1.0 s; 572k pseudo-positions/s with slow (loop) sliding attacks | scratchpad/numba_probe.py |
| Local probe | python-chess raw perft = 189k nodes/s on M2 with **no** eval, so the v1 route is capped ~50k nps | probe |

Read (revised 5 Sept, 23:30, after Archit's leaderboard analysis): the ladder is deflated
and non-linearly so. House bots sit far below their CCRL ratings on it (Loki 3.0: 1729 ladder vs
2428 CCRL; Zagreus 5.0: 1677 vs 2168; Rustic Alpha 3: 1603 vs 1792), and the leaders sit 400–500
ladder points *above* Loki. Whatever the exact mapping, the top five are a tier of their own
(2107–2216), all handle every opening type, none flag or crash, and they draw 20–30% of their
mutual games. They are much stronger than "PST engines"; AlphaFish in particular looks like an
experienced engine author's own engine. Consequences: the hand-crafted evaluation gets us into
the top 20–30, not the top 5; the NNUE's quality is the deciding factor; repetition handling and
time management are table stakes; and the target is depth 14+ in middlegames with a strong net,
not depth 10 with tables. The engine as built (1.1M nodes/s, depth 16–17 from the opening) has
the search side of that; the network is what the rest of the schedule is spent on.

## 2. What the five games tell us about v1 (and about the field)

Evidence from the logs, each with a fix:

1. **Fixed depth, no time management.** Every move is d5 or d6; moves cost 2–10 s; we finished
   games with 17–43 s unused. Fix: time-based iterative deepening with soft/hard limits (section 6).
2. **Horizon and grabbing.** Round 27: d5 said +100, d6 said Bxb2 = −220, and the engine played it
   anyway, then lost the bishop. Round 24: Nxe5 scored −100 at d6 and was played. Fix: depth 10+
   with quiescence and SEE, and aspiration windows that re-search on a fail-low instead of
   accepting the fallen score.
3. **No king safety, no development sense.** Round 25 opened 6.Kf1 (losing castling) scored +100,
   then 7.Qd2, 8.Ng5, 9.Nf3 shuffling. Round 24 shuffled Re1–Re3 four times. Fix: real evaluation
   (tapered PST at minimum, NNUE as the target), king safety, history heuristic to break shuffles.
4. **Repetition handling is absent on both sides of the board.** Rounds 25 and 28: we were behind
   by 3–6 pawns and *the opponents* let us repeat. Round 26: we were +400 and slid into a
   perpetual. Fix: track every position asked about, count repetitions in search, score draws with
   contempt. This is also the single cheapest exploit against the field: many opponents will take
   a repetition while winning.
5. **Init is 0.5 s and 89.5 s of free budget is unused.** Fix: spend it on numba compilation.

## 3. The decision: what we build

**A numba-compiled bitboard alpha-beta engine, with a self-trained NNUE-style evaluation, and a
hand-crafted tapered evaluation kept as a switchable fallback.** Pure Python + python-chess cannot
get above ~50k nps on this box and tops out around 1500–1700 here. Neural MCTS on one CPU core
without a GPU-trained policy net is a research project, not a six-day build. The winning shape
the organisers themselves describe ("a search that calls a small evaluation") is exactly this.

Why the NNUE part is worth it: at equal speed a well-trained 768→256 net beats PeSTO-style PST
by 200–400 Elo, and the top teams' ceiling (~2180) is almost certainly PST engines. The NNUE is
the part of the plan that turns "probably first" into "clearly first". It is also cleanly legal:
the rules explicitly allow training on positions an existing engine labelled, and the Lichess
evaluation database (394M Stockfish-labelled positions, CC0) exists for exactly this. The HCE
fallback means the engine is competitive on day 2 even if the network is late.

Hard constraints the design has to respect:

- Everything jitted is compiled at import, inside the 90 s budget, every game. Target ≤ 30 s
  locally and verify the "ready in" line of every validation log (EPYC is slower than the M2).
- No native binaries: numba JIT only, no `cache=True` reliance, no pycc, no Cython.
- One core: no threads in search. `torch` is not imported at runtime at all (saves ~1 s and
  ~300 MB); weights load through numpy.
- Never name a module `chess.py`, `types.py`, `random.py`, `time.py`, `json.py`. Ours are
  `bini_*.py`.
- Total zip ≤ 50 MB unzipped; RSS ≤ ~1 GB (TT capped at 256 MB).

## 4. Architecture

```
submission/
├── agent.py            thin: parse FEN, game-state tracking, time budget, call engine,
│                       legality check with python-chess, fallback, logging
├── bini_board.py       numba: bitboards, magic/hyperbola sliding attacks, make/unmake, zobrist
├── bini_search.py      numba: iterative deepening, PVS, TT, pruning, qsearch, move ordering
├── bini_eval.py        numba: tapered HCE (fallback) + NNUE inference with incremental accumulators
├── bini_time.py        python: soft/hard limits, nps calibration
├── bini_fallback.py    pure python-chess 4-ply search used only if the jitted engine fails
├── nnue.safetensors    our trained weights (int16), ~1–3 MB; parsed with 15 lines of numpy
└── book.bin            optional polyglot book we build ourselves (≤ 10 MB)
```

### 4.1 Board (numba)
- 12 piece bitboards as `uint64` in one `np.ndarray`, plus occupancy, side, castling, ep, halfmove,
  zobrist key. **Strict dtype discipline**: numba promotes mixed `uint64`/`int64` arithmetic to
  `float64` silently. All bitboard math in `np.uint64`, all indices in `int64`, never mixed.
- Sliding attacks: magic bitboards (tables built in numpy at import, ~5 ms) or hyperbola
  quintessence (no tables, fewer bytes of code to compile). Start with hyperbola; switch to magics
  if profiling says so.
- Pseudo-legal generation into a preallocated per-ply move stack `moves[ply, 256]`; legality by
  king-attack check after make. Make/unmake with an undo stack, incremental zobrist and incremental
  NNUE accumulators.
- Correctness gate: perft on the 6 standard positions (startpos d5 = 4,865,609; Kiwipete d4 =
  4,085,603; …) **and** a differential test: 200k random positions from python-chess random walks,
  legal move sets must match exactly. This test is the reason we will not lose a game to an
  illegal move.

### 4.2 Search (numba) — in order of Elo per hour of work
1. Negamax + alpha-beta, iterative deepening, quiescence (captures + promotions, then checks at
   qs depth 0), mate-distance pruning.
2. Transposition table: `uint64` keys, 16-byte entries in numpy arrays (key, move, score, depth,
   bound, age), 2^24 entries = 256 MB max, kept across moves within a game. TT move first.
3. Move ordering: TT move → captures by MVV-LVA with SEE to demote losing captures → killers (2)
   → counter-move → history heuristic (quiet moves, butterfly boards, aging).
4. PVS, aspiration windows (±25cp, widen on fail).
5. Null-move pruning (R = 3 + depth/6, not in pawn-only endgames, verification at high depth).
6. Late move reductions (log formula, reduce less for killers/history-hot moves, never for
   captures/checks at low depth), late move pruning at depth ≤ 3.
7. Reverse futility (static eval − margin ≥ beta), futility pruning at frontier nodes, delta
   pruning in qsearch, SEE pruning of losing captures in qsearch.
8. Check extension (+1), singular/recapture extensions only if time permits.
9. Repetition detection inside search against the game history (hashes since the last irreversible
   move, passed in as an array) and the current path; 50-move rule from the FEN halfmove clock.
   Draw score = −contempt for us (start at 20cp; tune), 0 in dead-drawn material.
10. Time control inside the jitted loop: check a node budget every 4096 nodes and, via
    `numba.objmode`, the wall clock every ~16k nodes; abort cleanly, return the last completed
    iteration's PV move.

Numba engineering rules: one self-recursive `search` function with qsearch folded in as the
`depth <= 0` branch (mutual recursion needs explicit signatures and compiles slower); all state in
a handful of preallocated arrays passed as arguments (numba treats module-level arrays as frozen
constants); `boundscheck=False`; no Python objects, tuples of mixed types, or lists inside jitted
code; one explicit signature per function so nothing compiles twice; total jitted code kept under
~2,000 lines so compile stays ≈ 20–30 s. Measure compile time on every commit.

Expected speed: 600k–1.2M nps with HCE on the M2, roughly 0.7× of that on the EPYC. At ~2 s a
move that is depth 9–12 in the middlegame, 15+ in endgames.

### 4.3 Evaluation
**Stage 1 — tapered HCE (day 1–2, stays as fallback).** Material + midgame/endgame piece-square
tables interpolated by phase, bishop pair, rook on open/semi-open file, passed pawns (by rank),
doubled/isolated pawns, king pawn shield and open files near the king, simple mobility, mop-up
(drive the lone king to the edge) so KR/KQ endgames convert, insufficient-material scale to 0.
Table values: start from PeSTO (public constants) and replace them on day 3 with our own
Texel-tuned tables fitted on the Lichess data, so every number in the zip is ours and the story
at the final is clean.

**Stage 2 — NNUE (day 3–5, the target).**
- Features (v2, decided 5 Sept 23:30): king-relative. Per perspective the own king square picks
  one of 8 king buckets and a horizontal mirror, then each piece is (bucket, kind, square'):
  8×768 = 6,144 inputs → 512 hidden per perspective, int16, ~6.3 MB. v1 (plain 768→256) is the
  same code with 1 bucket and is kept as the baseline to beat.
- Inference in numba: incremental accumulator updates in make/unmake (add/remove 1–3 rows of 256),
  clipped ReLU, one 512-length int32 dot product. Cost ≈ 1 µs a node, so nps drops maybe 20–30%
  versus HCE and the eval is worth hundreds of Elo more than that.
- Training (PyTorch on the M2, MPS): stream `lichess_db_eval.jsonl.zst` (CC0) with the
  `zstandard` package locally, keep positions with depth ≥ 12, take 50–100M, encode to compact
  numpy (piece list + side + cp). Target = sigmoid(cp/400) clipped at ±1500cp; MSE loss; Adam,
  batch 16k, 5–10 epochs (a few hours). Quantise: input weights ×64 → int16, output ×64/127 → int16
  with an int32 accumulator; verify the numba forward pass against the torch model on 10k positions
  (max error < 2cp) before any game is played with it.
- Supplement (optional, days 4–5): 5–10M positions from our own engine's self-play games labelled
  by our own depth-8 search, which improves quiet-position calibration and is unambiguously ours.
- Export as `.safetensors` written by a 20-line script (the format is a JSON header + raw bytes)
  and read back with a 15-line numpy parser, so no `torch` at runtime and the file type is one the
  rules list by name.

### 4.4 Game-state tracking in agent.py
- We receive only a FEN. Keep the last position we returned a move from and the move we played;
  on the next call, find the opponent's move by matching legal moves from that position to the new
  FEN, so we have a full move list, a full hash history for repetition, and can detect a new game
  (FEN not reachable → reset). Python-chess does this in < 1 ms.
- Persist the TT, killers and history across moves; age the TT each move.
- Every returned move is validated against `chess.Board(fen).legal_moves`. Any exception anywhere,
  or a missing move, falls through to `bini_fallback` (python-chess, 4 ply, 0.5 s), then to the
  first legal move. Losing a game to a crash is not allowed to be possible.
- One compact log line per move to stderr (depth, score, nodes, ms, clock) — under 8 KB a game so
  the dashboard log keeps all of it.
- Import-time sequence: build tables → compile (warm every jitted function with the real argument
  types) → run a 300 ms benchmark search to measure nps on this machine → load weights → verify
  the net on 3 positions → print `ready compile=XXs nps=YYY`. A hedge for compile time: run the
  warm-up in a thread and `join(timeout=75)`; if it has not finished, import returns anyway and
  `get_move` uses the fallback engine until the flag flips. That hedge turns a would-be init loss
  into a couple of weak moves.

## 5. Opening book and endgames
- Curated start positions are mainstream lines at move 5–8 (Four Knights, Two Knights, Petroff,
  Scotch, Symmetrical English, Closed Ruy, French Advance, Caro-Kann, Nimzo, Grünfeld, KID, London
  seen so far). A polyglot book we build from the Lichess Elite games (2400+ ratings, ≥ 5
  occurrences, weighted by result) up to ply 24 will hit these. Value: 3–8 free moves of clock and
  no early eval-blind moves. Priority: day 4, ≤ 10 MB, `chess.polyglot` is in the base image.
  Skip if the arena shows no gain.
- Syzygy 3–4 men (~30 MB) is legal but too much of the 50 MB for too little Elo; a depth-15+
  search with mop-up eval converts those endgames anyway. Optional: a KPK bitbase generated at
  import in numba (<1 s).

## 6. Time management
Base 120 s + 0.5 s. Real games here last 30–60 of our moves. Per move:

```
mtg   = max(16, 42 - 0.5 * our_move_number)        # moves to go, shrinks as the game goes on
soft  = time_left / mtg + 0.6 * inc                 # start new iteration only if elapsed < soft
hard  = min(4 * soft, 0.35 * time_left)             # abort the iteration in progress
hard  = min(hard, time_left - 1500 ms)              # never eat the safety reserve
if time_left < 4000 ms: soft = 0.4 * inc, hard = 0.8 * inc
```
Extend soft ×1.6 when the best move changed at the last iteration or the score fell > 30cp;
shrink ×0.7 when the TT move was confirmed unchanged for three iterations. Disable the garbage
collector during search. Node budgets are derived from the nps measured at import, so a slower
EPYC just searches fewer nodes, never flags. Our v1 data says every move already costs ~1 ms of
Python and pipe overhead; the 1.5 s reserve covers a 1000× surprise.

## 7. Testing, in the order it protects us
1. **Perft + differential legality test** (section 4.1) on every movegen change. Non-negotiable.
2. **Torture arena**: 300 games vs `baselines/random` at 3 s + 0.05 s from 100 random start
   positions. Exercises promotions, underpromotions, en passant, castling edge cases, stalemate,
   50-move, insufficient material. Zero crashes, zero illegal moves, zero flags.
3. **Tactical suite**: WAC 300 (Win At Chess) at 1 s per position; target ≥ 90% solved. Mate-in-N
   sanity set for mate scoring and mate-distance pruning.
4. **Strength arena** (`tools/arena_par.py`, ours): wraps `harness.referee.play_match` in a
   process pool (M2 has 8 cores; the engine is single-threaded, so 6 games run at once), a fixed
   set of 100 "curated-like" openings at move 5–8 harvested from Lichess Elite games, colours
   alternated, 10 s + 0.1 s. Every candidate plays ≥ 400 games against the previous accepted build
   and is accepted only above +20 Elo with the error bar clear of zero (or a proper SPRT). Keep
   every accepted build as an opponent. Spot-check at the real 120 s + 0.5 s once a day.
5. **Platform dress rehearsal**: run the arena with a 0.65× time factor to approximate the EPYC,
   check RSS < 1 GB, check import time < 35 s locally.
6. **Live telemetry**: after every hourly rated round, download the log and PGN; a script pulls
   compile time, nps on the EPYC, time per move, termination. The first upload's validation log
   gives us the true EPYC compile time and nps within minutes.

## 8. Schedule and split (two people, six days)

Track A = engine core (movegen, search, numba performance). Track B = evaluation, data, NNUE
training, testing infrastructure and telemetry. Swap for reviews. Suggested: Grigory takes A,
Archit takes B, or the reverse — decide tonight.

| When | Track A | Track B | Gate / upload |
|---|---|---|---|
| Sat 5 (tonight) | repo skeleton, board representation, dtype conventions written down | arena_par.py, openings.epd, log-telemetry script; start the Lichess eval download | plan agreed, roles fixed |
| Sun 6 | movegen + make/unmake + zobrist, perft-exact by evening; alpha-beta + qsearch + TT + ordering | tapered HCE in numba; time manager; agent.py wrapper with legality check and fallback | **v2 upload Sun night**: expect 1800–2000 on the ladder |
| Mon 7 | PVS, aspiration, null-move, LMR, futility, killers/history, check ext, repetition | data pipeline: 100M positions encoded; training script; first 768→256 net trained overnight | v3 upload; torture arena clean |
| Tue 8 | SEE, LMP, TT aging, search tuning against arena | NNUE inference in numba, incremental accumulators, torch-vs-numba verification; Texel-tune PST for the fallback | v4 = NNUE build if it beats HCE by ≥ 100 Elo at 10 s + 0.1 s |
| Wed 9 | time-management tuning, endgame mop-up, ply-cap awareness, compile-time budget review | second net (more data, king buckets if cheap), polyglot book, 1000-game regression | v5 candidate final |
| Thu 10 | freeze features; only bug fixes; full test ladder at real TC | telemetry review of every ladder game; opponent-specific checks (repetition, time) | **final upload Thu evening** (earlier submission is the last tie-break) |
| Fri 11 before 11:00 | rollback only if telemetry shows a defect | | uploads close 11:00; Swiss in the afternoon |

Each ladder round (hourly, 08:00–22:00) is free telemetry against real opponents; upload every
accepted build, never an untested one. Ten uploads a day is plenty.

## 9. Risks and what neutralises them

| Risk | Effect | Mitigation |
|---|---|---|
| numba compile > 90 s on the EPYC | lose every game at init | keep jitted code compact, explicit signatures, measure on every commit, read "ready in" on every validation log, threaded warm-up with 75 s join as a hedge |
| uint64/int64 promotion bug or movegen bug | illegal move = loss | dtype rules, perft, 200k-position differential test, python-chess legality check on every returned move, fallback engine |
| Flag | loss | hard deadline inside search, node budget from measured nps, 1.5 s reserve, gc disabled, torture arena |
| OOM | loss | TT ≤ 256 MB, no torch import at runtime, RSS check in the dress rehearsal |
| NNUE late or weak | fall back to HCE | HCE is a switch, not a rewrite; gate every net by arena |
| Rule challenge at the final | disqualification | only our source; training scripts, data provenance and quantisation script kept in the repo; Texel-tuned tables replace borrowed constants; no shipped eval lookup tables; readable code |
| Platform slower than the M2 | shallower search | time-based iteration, nps calibration at import, 0.65× dress rehearsal |
| Module shadowing / zip layout | crash at import | `bini_*` names, `agent.py` at the zip root, `make zip` + validation log |
| Wasting uploads | none | one upload per accepted build only |

## 10. Field exploits (cheap, deliberate)
- Correct repetition handling: take draws when losing (rounds 25 and 28 were gifts), refuse them
  when winning, and a small contempt so an equal middlegame is played on rather than shuffled.
- Depth: the field is depth 3–6; a depth-10+ engine wins material by tactics without any special
  effort. Keep the position complicated when ahead on the clock (no explicit code; the eval does it).
- Endgame conversion: the mop-up term plus depth turns the half points the field gives away into
  full points.
- Knockout ties are 2-game pairs with colours swapped, so a reliable win-as-White engine and a
  draw-proof Black repertoire matter; the book and contempt tuning target that on Wed/Thu.

## 11. Side note: Daily Five
A human puzzle event, 6–10 Sept, one attempt a day, five positions, 20 minutes, no engines or
lookups. The daily top 3 eligible UK students earn a Finals Day wildcard seat. Independent of the
agent; worth 20 minutes a day from any UK-student team member who enjoys puzzles.

## 12. Tonight's actions
1. Agree the plan and the A/B split; make the repo private and push the starter.
2. `make setup` is done here (uv installed, exact platform stack verified: Python 3.12.4, numba
   0.67.0, numpy 2.5.2, python-chess 1.11.2, torch 2.13.0, onnxruntime 1.29.0).
3. Track A: write `bini_board.py` with the dtype conventions at the top of the file, and the
   perft test harness.
4. Track B: start the Lichess eval database download (`lichess_db_eval.jsonl.zst`), write
   `tools/arena_par.py` and `tools/telemetry.py`, harvest `openings.epd`.
5. Do not upload anything new until v2 passes perft, the torture arena and beats v1 in the arena.

## 13. Build log

- **Sat 5 Sept, 21:00–22:00.** Board module written and gated: perft exact on the six standard
  positions (16.5M leaves, 7.6M leaves/s); 25,000 random positions matched python-chess on every
  legal move with every move made/unmade and state compared. Evaluation, search, NNUE inference,
  engine driver and agent wrapper written. Search compiles in ~23 s on the M2 and runs at
  ~1.1M nodes/s (hand-crafted eval), depth 16–17 in two seconds from the opening. Mate-in-1
  40/40, mate-in-2 39/40 (the miss is a slower forced mate), tactics 9/11 (WAC.002 is the known
  null-move zugzwang case; a verification search was added). First harness game vs greedy: clean
  win by mate, protocol and clock fine. Lichess evaluation stream running (60M positions);
  training script validated end to end on a 300k sample (MPS, loss falling).
- **Sat 5 Sept, 22:00–23:00.** Git repository created and pushed (github.com/archit-05/AI-Chessathon).
  Torture arena exposed two real defects, both fixed: the emergency clock budget assumed the
  0.5 s increment (now spends a fraction of the remaining clock whatever the increment), and
  repetition detection ran after the quiescence dispatch (now first). Under heavy local CPU
  contention (training + arena) the compile exceeded the 75 s join and the fallback engine played
  as designed; local arenas now run with 3 workers while training runs. NNUE incremental
  accumulators verified exactly against a reference on ~4,000 positions; NNUE forward pass is
  170 ns vs 372 ns for the hand-crafted eval. 59.4M Lichess positions streamed; NNUE v1 training
  running (6 epochs, ~40 min each on the M2).
- **Sat 5 Sept, 23:00–00:00.** Leaderboard calibration re-read (section 1). NNUE v2 architecture
  implemented: king-bucketed features, shape read from the weights file at import, output scale
  chosen at export and shipped in the file; search/engine rewired; trainer generalised (multiple
  data directories, --buckets, --hidden). Stockfish 19 installed locally as a fixed-strength
  sparring partner (sparring/sf, never shipped). Second data stream (100M more positions) running.

## 14. Decisions from the strategy review (Sat 5 Sept, 23:50)

1. **Measure before anything else.** Calibration ladder vs Stockfish at fixed UCI_Elo (1800, 2000,
   2200, 2400, 2600; 100 games each, 10 s + 0.1 s) as soon as the CPU is free; build Loki 3.0 and
   Zagreus locally if they compile, since Loki's ladder rating (1729) maps our score directly onto
   the ladder. Every gate from now on is games against a fixed-strength reference, 300+ games for
   a decision between two nets.
2. **Training data quality.** Re-stream with a quiet-position flag (drop positions where
   Stockfish's best move is a capture or promotion, or the side to move is in check), 160M+
   positions, ~10 epochs of the king-bucket 512 net. The one-cycle schedule already anneals.
3. **Two uploads, not one.** Sunday: the hand-crafted build, to read compile time and nodes/s on
   the EPYC ("Ready in" line). Thursday afternoon: the final. Friday morning rollback-only.
4. **Book on Monday**, singular extensions and eval-dependent time saving when the calibration
   numbers say where the Elo is. Fixed contempt tuned in the arena; no opponent modelling.
- **Sat 5 Sept, 23:25 — first calibration.** Hand-crafted build vs Stockfish 19 at UCI_Elo 2000:
  8/8 wins. At UCI_Elo 2400 (10 s + 0.1 s, 32 games, stream paused): +18 =9 −5, 70%, ≈ +150 Elo,
  no failures. Local finding: under heavy CPU load the compile can exceed the hedge and the
  fallback then starves on the GIL behind the compiling thread, so the hedge protects against an
  *init* loss only; compile time itself must stay well inside the budget (measured quiet ~15–25 s,
  to be confirmed by the first validation log). `submission_hce_*.zip` packaged for that upload.
- **Sat 5 Sept, 23:35 — platform numbers (validation log of the hand-crafted upload).** Compile
  30.5 s and 32.6 s in the two smoke games (58 s headroom), ~850k nodes/s on the EPYC, depth 15–22
  in 2–5 s, both colours clean, no fallback. Compile risk closed; the 512-hidden net adds a few
  seconds at most. Overnight: quiet-filtered data (170M lines), NNUE v2 training (8 epochs),
  v1-vs-HCE gate running as the pipeline check, v2 gate at dawn.
- **Sun 6 Sept, 00:45 — overnight run launched.** Data: 166M Lichess positions (38 + 128 chunks)
  with the quiet flag, ~128M quiet used. NNUE v2 (8 king buckets, 512 hidden) training 8 epochs,
  ~50 min/epoch, expected done ~07:30. Concurrently: v1-vs-HCE gate rerun (100 games) and the
  centipawn-loss analysis of the top five's public games (tools/scrape_games.py, tools/cpl.py).
  Partial v1 gate before the restart: +15 =3 −11 (+48 ±134) — the plain net is only marginally
  better than the hand-crafted eval, hence the v2 changes.
- **Sun 6 Sept, 01:50 — the yardstick.** Mean centipawn loss vs Stockfish (120k nodes/position)
  on public platform games: AlphaFish 6.3 (0.1% blunders, 1,339 moves); Mate in One 18.8; Patzer
  19.8; Anchoa 27.7 (their moves against AlphaFish). Our hand-crafted build at the real clock
  (12 games vs SF UCI_Elo 2400, 12–0, machine heavily loaded): 17.3 mean, median 3, 1.3% blunders.
  Read: the hand-crafted build is a top-5 engine; AlphaFish is a tier above; v2 must roughly halve
  our centipawn loss. v1 net gate final: 51 games, 48% (−14 ±98) → no gain over HCE. v2 epoch 0
  validation loss 0.0136 already beats v1's final 0.0157.
- **Sun 6 Sept, 03:15 — early gate.** NNUE v2 snapshot after 3 of 8 epochs vs the hand-crafted
  build, 60 games at 10 s + 0.1 s: +42 =7 −11, 75.8%, ≈ +199 ±109 Elo, no failures. Evaluations
  well scaled (queen +1046, rook −476). Trainer/engine consistency 1.8 cp mean. Training continues
  (epoch 3, ~30 min/epoch); final gate, real-clock centipawn loss, torture and packaging at ~05:45.
- **Sun 6 Sept, 05:10 — v2 trained and packaged.** 8 epochs, ~128M quiet Lichess positions,
  validation loss 0.0116 (v1: 0.0157). Consistency 2.1 cp, incremental updates exact, compile with
  the net 25 s under load, 8/8 in-process wins vs random. `submission_v2_0906_0507.zip` (6.4 MB
  unzipped) built; 200-game gate vs the hand-crafted build running, torture and real-clock check
  follow before hand-over.
- **Sun 6 Sept, 06:08 — final gate.** v2 (epoch 8) vs hand-crafted build, 200 games at
  10 s + 0.1 s: +143 =17 −40, 75.8%, ≈ +198 ±57 Elo, 0 failures (183 checkmates, 7 fifty-move,
  4 insufficient material, 6 threefold). Torture suite and real-clock check running.
- **Sun 6 Sept, 06:35 — v2 handed over.** `submission_v2_0906_0507.zip`. Real clock vs SF 2400:
  12–0, all mates; our centipawn loss 11.3 mean / median 0 / 0.3% blunders (hand-crafted: 17.3 /
  1.3%; AlphaFish 6.3 / 0.1%; Mate in One 18.8). Torture 60/60. Next: Stockfish-labelled whole-game
  positions (Lichess Elite) for a second training iteration; singular extensions, capture history,
  qsearch TT probe; real-clock time-management tune; book on Monday. Each gated by games.

## 15. Plan to first (Sun 6 Sept, 07:10)

Evidence: site move grades — AlphaFish 90.3% best/excellent, 0.7% errors, flat 1.7 s/move (max
4.4 s), 9/11 vs top-12, its only loss a 102-ply middlegame; places 2–6 at 85–90% / 0.9–1.6%; our v2
centipawn loss 11.3 vs AlphaFish 6.3 and peers 18–28. v2 is likely second strongest today.

Levers, by Elo per day:
1. Evaluation v3: ~320M quiet Lichess positions + Stockfish-labelled whole-game positions, 6–8
   epochs; then a fine-tune on positions from our own search trees labelled at depth 12. Gate:
   300 games vs v2 + real-clock centipawn loss (target < 8).
2. Search: batch 1 (singular/multi-cut, IIR, qsearch TT) under gate; batch 2 capture history,
   continuation history, history-driven LMR, staged move generation (+10–20% nps).
3. Conversion: mop-up on top of the net, halfmove-clock-aware progress bonus when winning, KPK
   bitbase at import, a won-endgame conversion suite at the real clock; contempt re-tuned.
4. Time: finish with 10–15 s (field: 20–40 s), spend on swings, save when decided; tuned from
   ladder logs. AlphaFish's flat allocation is the structural edge in sharp middlegames.
5. Book from Elite games, Monday, only if the arena says so.
Not doing: opponent-specific behaviour or untestable sharpness terms.

Schedule: Sun batch-1 gate → v2.1, stream 150M more, start v3 tonight; Mon v3 gate, batch 2,
conversion + endgame suite, book; Tue own-search fine-tune, SF 2600/2800 ladder; Wed freeze,
1,000-game regression, package; Thu final upload (afternoon); Fri rollback only.
- **Sun 6 Sept, 08:17 — batch 1 gated.** Singular extensions + multi-cut, IIR (non-PV),
  quiescence TT, decided-position time saving: +80 =76 −44 vs v2 over 200 games, 59.0%,
  ≈ +63 ±49, 0 failures. Packaged as `submission_v2.1_*.zip`. Self-play draws: 31 fifty-move,
  32 threefold — the conversion package (mop-up on the net, fifty-move scaling, position-aware
  contempt; endgame suite 11/11 vs Stockfish's defence) is now gating against this build.
- **Sun 6 Sept, 08:45 — first rated game of v2.** Round 31 vs minimax three: win by checkmate in
  22 moves; init 25.0 s, 689k nodes/s, depth 16–17 in the opening, 6.9 s on the critical move,
  mate seen from move 13, 95 s left. Rating 1269 → 1353. v3 training running (202 chunks,
  ~60 min/epoch, 6 epochs). Conversion package gate vs batch 1 trending negative at 40 games
  (41%, −61 ±114); split variants prepared (endgame terms only / contempt only).
- **Sun 6 Sept, 10:20 — round 32.** Win vs Terminal by checkmate in 25 moves; init 29.3 s, 588k
  nodes/s (R31: 689k), depth 14–22, forced mate from move 22, 76 s left. v2.1 ready for upload
  after the 10:00 game. Conversion gate rerunning on 2 workers (the first run was polluted by
  memory starvation: 33 fallback games, 7 flags).
- **Sun 6 Sept, 10:15 — v2.1 battery (in progress).** Init ×10 under local load: 32–36 s
  typical, mean 40.0 s, outliers 49.8 s and 68.7 s on load spikes (26–35); platform reference for
  v2 was 29.2/29.6 s on a dedicated core. Torture rerun (2 workers, small tables): 26/26 clean,
  0 fallback games. Position sets (sharp/winning/marginal/puzzles/drawn) building; tactics gate,
  real-clock pressure games vs Stockfish and strong-defence conversion sets chained behind them.
  Next-build item: skip compiling the hand-crafted evaluator when the net is loaded.
- **Sun 6 Sept, 10:25 — v2.1 battery, part 1.** Torture (60 games vs random, 6 s + 0.3 s,
  small tables, machine quiet): 60/60 by checkmate, 0 fallback, 0 failures. Tactics gate (40
  Stockfish-verified unique winning moves, 2 s each): 39/40 = 98%. Real-clock pressure games vs
  Stockfish and the strong-defence conversion sets running.
- **Sun 6 Sept, 11:15 — pressure test caught a time-management defect.** Ten real-clock games
  from sharp middlegames vs full-strength Stockfish (1.5M nodes/move): clock 120 s → ~27 s after
  20 own moves → ~6 s after 40, minimum 3.8 s (below the 5 s floor); results 0-2-8 (expected vs
  that opponent). Cause: an iteration could start until the soft limit and then run to the hard
  limit (3x soft), so unstable moves spent 2-3x the budget. Fix: start an iteration only if
  elapsed + 2x the last iteration fits the budget; hard cap 2.2x soft and 20% of the clock;
  horizon max(22, 50 − 0.5·n) for 60–100-move games; low-clock guard under 10 s. Budget curve now
  2.7 s at move 1 → 1.6 s at move 40 (40 s left) → 0.75 s at 10 s left. Pressure games and
  torture rerunning on the fix; hand-over slips ~45 min.
- **Sun 6 Sept, 11:20 — site rule change (ladder).** Games ending by threefold repetition or the
  fifty-move rule are now voided retroactively on the ladder (insufficient material still counts);
  everyone re-rated (AlphaFish 2478, Capablanca 2429, Anchoa 2360, SoberElwood 2338). The Swiss
  rules still say FIDE draws. Decision: no ladder-only policy; contempt is set for the Swiss regime
  (refuse repetition when ahead, welcome it when behind). Bini: 3-0 since the v2 upload (R31–R33),
  1487, rank 188; site grades 43 best / 18 excellent / 4 good / 0 errors over three games.
- **Sun 6 Sept, 12:15.** Ladder: 4-0 since the v2 upload (R34 win vs ASD, 36 moves, 25 best /
  9 excellent / 0 errors), 1533, rank 163. AlphaFish uploaded again (+98 → 2576). The threefold
  voiding looks like a one-off re-rating pass, not a standing rule (a fresh R34 threefold stands).
  v2.1 battery: pressure games on the fixed time manager show 60–90 s left after 20 moves and
  33–62 s after 40 against full-strength Stockfish (min clock ≥ 24 s at game end). Conversion
  baseline of the shipped search vs Stockfish 400k nodes from +200..+500 positions: +11 =6 −3
  (55%); this is the number the conversion build must beat. Regression, torture alone, and
  packaging chained.
- **Sun 6 Sept, 12:50 — v2.1 battery, part 2.** Pressure games (10, real clock, sharp
  middlegames vs full-strength Stockfish 1.5M nodes/move) on the fixed time manager: min clock
  9.7 s in a 133-move game; clock 60–90 s after 20 own moves, 33–62 s after 40, 22–37 s after 60;
  unclear positions 1.85 s median vs decided 1.41 s; 0-3-7 (expected vs that opponent). Regression:
  perft exact, 6,000-position differential ok, NNUE exact, wrapper state ok, search gate passed.
  Conversion baseline vs Stockfish 400k: winning +11 =6 −3, marginal +0 =4 −6, drawn no losses.
  Torture (alone) running, then packaging.
- **Sun 6 Sept, 13:05 — v2.1 handed over.** `submission_v2.1_0906_1255.zip` (sha256
  e0072c9f…c537e348), files byte-identical to the tested sources. Battery: 200-game gate +63 ±49
  over v2; torture 60/60 + 30/30 (0 fallback, 0 failures); tactics 39/40; real-clock pressure
  min clock 9.7 s; regression (perft, 6,000-position differential, NNUE exactness, wrapper state,
  search gate) all green; fresh-extraction harness game vs Stockfish 2400 clean (compile 20 s
  quiet). Contents vs v2: search batch 1 (singular extensions + multi-cut, IIR at non-PV nodes,
  quiescence TT), decided-position time saving, predictive iteration start with a 50-move budget
  horizon, per-move counters in the log line. Next: conversion package gate (bini_conv), v3 net.
- **Sun 6 Sept, 13:15.** Ladder 5-0 on v2 (R35 as Black, 52 moves, 36/14/1/0/0/0/0; clock 73 s
  at move 20, 38 s at move 40, 32 s at the end — the pre-fix policy), 1580, rank 142. AlphaFish
  2642 after beating Capablanca (R34) and Anchoa (R35). Conversion package gate vs v2.1 running
  (150 games, 2 workers); v3 epoch 3 of 6.
- **Sun 6 Sept, 14:15.** Ladder 6-0 on v2 (R36 as Black vs berserker, 48 moves), 1638, rank
  115. Repetition draws count again from R35 (the voiding was a one-off pass). Conversion package
  self-play gate at 94 games: 48.9% (−7 ±71), neutral; Stockfish conversion sets on the
  conversion build in progress (baseline +11 =6 −3). v3 epoch 5 of 6, validation 0.0103.
- **Sun 6 Sept, 15:00 — conversion package does not gate.** Self-play vs v2.1, 150 games:
  50.7% (+5 ±56). Stockfish conversion sets: winning +8 =9 −3 (baseline +11 =6 −3), marginal
  0-5-5 (baseline 0-4-6). Mop-up, fifty-move scaling and position-aware contempt stay in the
  working copy, unshipped; the compile trim (skip HCE when the net is loaded, −7%) carries forward
  into the next build. Next gate: search batch 2 (capture + continuation history, history-driven
  reductions) on the v2.1 base, 150 games. v3 finishes ~16:15, then a 300-game gate vs v2.1.
- **Sun 6 Sept, 15:15 — R37 confirms the time defect.** v2 (still on the platform) drew R37 as
  White vs ChEKmate (1652) by threefold after 66 moves with the clock at 63/31/12 s at moves
  20/40/60 and 6 s at the end; level material, one site-tagged inaccuracy. This is the failure
  the v2.1 pressure test found and fixed (predictive iteration start, 2.2x hard cap, 50-move
  horizon). Ladder 6-1-4 on v2, 1638, rank 121; bot renamed "BINI Sahur".
- **Sun 6 Sept, 16:20 — v3 trained.** 6 epochs (1 + 5 resumed) over ~155M quiet positions
  (all 205M lines of the evaluation database, quiet-filtered); final validation 0.01017, MAE
  153 cp (v2: 0.01161 / 175 cp on its own chunk). Consistency 2.1 cp, incremental exact,
  evaluations well scaled (queen +962, rook −488, KQvK +1689). Gate vs v2.1: 300 games at
  10 s + 0.1 s, 3 workers, running alone. Batch 2 (capture/continuation history) gates after it.
- **Sun 6 Sept, 16:25.** Ladder 7-1 since the v2 upload (R38 win at 1.1 s/move with 97 s left,
  consistent with v2.1's clock policy now on the platform), 1717, rank 87. v3 gate vs v2.1 at
  61 games: +24 =24 −13, 59.0% (+63 ±91), 0 fallback.
- **Sun 6 Sept, 17:45.** Ladder 8-1 since v2 upload, 1779, rank 70. v3 gate at 242 games:
  +83 =103 −56, 55.6% (+39 ±44). v3 real-clock centipawn loss measured *under the gate's load*:
  16.1 mean / 1.4% blunders over 12 games — not comparable with v2's 11.3 (quiet machine); a
  quiet, sequential comparison of v2.1 and v3 vs Stockfish 2400 is chained after the gate, then
  the batch-2 gate.
- **Sun 6 Sept, 18:06 — v3 gate final.** v3 net (same v2.1 code) vs v2.1, 300 games at
  10 s + 0.1 s: +103 =123 −74, 54.8%, ≈ +34 ±40, 0 fallback. Passes the "measures positive" rule
  but short of the target; decision on shipping waits for the quiet real-clock centipawn
  comparison (v2.1 then v3, 12 games each vs Stockfish 2400). Tonight: batch-2 gate, then
  whole-game labelling for a v3b fine-tune.
- **Sun 6 Sept, 18:15 — evening pipeline chained.** (1) Quiet real-clock centipawn comparison
  v2.1 vs v3 (12 games each vs Stockfish 2400) → (2) batch-2 gate vs v2.1 (150 games, 3 workers)
  → (3) Stockfish depth-10 labelling of 2.5M whole-game Elite positions (4 workers) → (4) v3b
  fine-tune: resume v3, 2 epochs at lr 5e-4 with the whole-game set oversampled ×10. Trainer gained
  `--oversample DIR:K`. Ship decision for v3 after (1); v3b gate in the morning.
- **Sun 6 Sept, 18:30 — R40, first v2-era loss, analysed.** Black vs Parable (1799) from a
  Grünfeld start already −24 for Black; Stockfish move-by-move: our errors 17...f5 (−160),
  20...cxb4 (−73), 21...b5 (−106), 26...b4 (−85), 31...Bh6 (−171), collapse from move 38. Every
  one played with 75+ s on the clock after ~1 s of thought (9 s used in the first 17 own moves):
  the stable-move discount fires in slow squeezes. Time policy v2.2 (bini_tm): stable discount
  0.75 instead of 0.6, a danger multiplier ×1.5 when the score fell ≥25 cp since our previous
  move, a floor of half the budget before the predictive stop, cap ×2.0. Pressure test running.
  Evaluation side of the same game is v3/v3b's job.
