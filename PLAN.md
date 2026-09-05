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
