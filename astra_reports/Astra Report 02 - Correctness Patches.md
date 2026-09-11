# Astra Report 02 — Correctness Patches (C1, C2)

**Candidate:** `bini_astra_correctness/` (C1+C2) · isolation build `bini_astra_c2/` (C2 only)
**Baseline:** `bini_v8_ship/` — SHA-256 of the archive `47ace193…`, unchanged
**Written:** 10 September 2026, ~19:40 BST
**Status of this report:** C1 and C2 are **implemented, reproduced-before / passing-after, generalised-tested and cost-measured**. Timed regression games are Report 03. C3 and C4 are diagnosed below, not folded into the release.

Two files differ from the baseline, and only two: `bini_search.py` and `bini_board.py`. The network, the book, `agent.py`, `bini_engine.py`, `bini_eval.py`, `bini_nnue.py`, `bini_magics.py` and `bini_calib.py` are byte-identical. Diffs: `astra_reports/C1_C2_bini_search.diff` (167 added, 27 removed) and `C2_bini_board.diff` (13 lines).

---

## C2 — Repetition indexing and history boundaries

**Status:** reproduced → fixed → regression-tested.
**Source location:** `bini_search.py::is_repetition` (baseline line 281); `bini_board.py::make_null` (line 644). Baseline `bini_search.py` md5 `163cda13023d7d5aa89cc4b523c6b576`.
**Depends on:** nothing. **C1 depends on C2.**

**Minimal reproduction.** Pre-root `g1f3`; root after `g1f3 g8f6`; in search play `f3g1 f6g8`. At ply 2, halfmove 4, the position on the board *is* the initial position. Expected `True`; baseline returns **`False`**.

**Root cause (evidence, not hypothesis).** `ub[0]` and `hist[hist_n-1]` hold the same position — the root. The search-path loop tests the root at `steps=2`; the history loop then starts at `hist[hist_n-1]` and tests the root *again* at `steps=4`. Every genuine pre-root ancestor is therefore charged two plies more than its true distance, and the `steps <= half` guard truncates the walk two plies early. The baseline's own comment — "walk backwards over history entries with the same parity" — is correct; the index arithmetic that implements it is not, and it contains a dead first assignment to `j` that is immediately overwritten, which is the fingerprint of the edit that introduced the fault.

**Patch.** `is_repetition` rewritten on an explicit distance model: an ancestor with the same side to move sits at distance `d ∈ {2,4,6,…}`; distance `d` is `ub[ply-d]` while inside the tree and `hist[hist_n-1-(d-ply)]` once past the root. The root is visited exactly once and no counter advances twice. The walk stops when `d` exceeds the halfmove clock, and at the nearest synthetic null ancestor (`ui[i,4] == 0` marks a pass), because a position on the far side of a pass is not a repetition a real game could have reached.

`make_null` additionally no longer advances the halfmove clock. A pass is not a move: it must neither age the fifty-move counter (which could manufacture a draw score inside a null subtree) nor widen the repetition window across the pass. `unmake_null` restores the saved value either way, so the change is symmetric.

**Why this fixes the class, not the example.** The defect was an off-by-two in a distance counter, so it affected *every* ancestor reached through game history at *every* parity — the directive's example is simply the shallowest instance. The replacement computes distance directly from `ply` and `d` with no running counter to desynchronise.

**Negative tests, all passing.** No repetition across a pawn move; no repetition on a first occurrence; identical piece placement with spent castling rights is *not* a repetition (different key, correctly rejected); cycles wholly inside the tree, wholly inside game history, and straddling the root at both parities; an eight-ply double cycle with no pre-root history.

**Remaining approximation, named and measured.** The engine treats a **second** occurrence inside the search as a draw. The local referee uses `board.outcome(claim_draw=True)`, which I drove directly rather than assuming: over a repeated four-ply knight cycle from the start position, the engine's rule is satisfied from **ply 4** (the second occurrence), while the referee first reports `THREEFOLD_REPETITION` at **ply 7**, when a third occurrence becomes claimable through the next move.

So the engine's internal draw signal fires about three plies before the referee would actually award anything. That is the standard engine convention — a cycle in the tree is treated as drawn because the opponent can force the repetition — and it is **unchanged from the baseline**. C2 fixes *which positions are found*, not *what finding one means*. I am naming it as a heuristic rather than presenting it as exact adjudication, and I have deliberately not touched it: changing second-occurrence semantics is a playing-behaviour design question, not a rule repair, and the platform's own adjudication convention should be confirmed before anyone touches it.

---

## C1 — Centralised exact terminal semantics

**Status:** reproduced → fixed → regression-tested.
**Source locations:** `bini_search.py::qsearch` (baseline line 451, stand pat), `::search` (line 594, terminal block).
**Depends on:** C2.

### What was wrong

Three separate faults with one shared cause — the engine had no single place where the rules are decided before heuristics get a vote.

1. **Stalemate at the quiescence frontier.** `qsearch` stand-pats before it knows a legal move exists, and only tests `legal == 0` after generating *captures*. "No legal captures" is not "no legal moves". `k7/8/1QK5/8/8/8/8/8 b - - 0 1` → **−1719**. Four of five stalemate positions returned a non-draw score; a stalemate one capture deep returned **+1719** to the side delivering it.
2. **Fifty-move rule outranking checkmate.** `if st[S_HALF] >= 100 or is_repetition(...)` ran before any check or legality test. `7k/6Q1/5K2/8/8/8/8/8 b - - 100 1` → **−20** instead of a mate score.
3. **No dead-material recognition at all.** `K+B vs K` → **107**, `K+N vs K` → **111**, `K vs K` → **61**, same-colour bishops → **78**. `endgame_scale` divides such positions by 8; the R99 family.

### The patch

Three helpers, then two call sites.

* **`dead_material(bb)`** — exactly python-chess's `is_insufficient_material`, derived class by class from its source rather than copied from the rejected candidate. With no pawns, rooks or queens anywhere: no knights → drawn iff every bishop sits on one colour complex; otherwise drawn iff there is exactly one knight in total and no bishops. First line is a single OR over six bitboards, so the overwhelming majority of nodes reject in a few instructions.
* **`king_has_move(bb, st)`** — cheap and exact. Lifts the king off the occupancy so a slider behind it is not treated as blocked, then asks whether any adjacent non-own square is unattacked. If yes, the position cannot be stalemate and no move is generated at all. This keeps the expensive probe off the hot path.
* **`has_legal_move(...)`** — the exact probe. Generates into a dedicated scratch slice at `(MAX_PLY+4)*MOVES_PER_PLY`, past every ply the search can reach, and saves and restores this ply's `ub`/`ui` entry, which `make`/`unmake` use as working storage. It therefore disturbs no live move list, no undo slot and no accumulator — asserted by test `A.probe_leaves_no_trace`, which failed on my own first attempt and drove this design.

In `search`, dead material returns the terminal draw utility **before** the TT probe, before `corrected()` and before any pruning; checkmate now outranks the fifty-move rule, with only the mated case falling through so the existing `legal == 0` path scores it `-MATE + ply` with correct normalisation. In `qsearch` the same block runs before the TT cutoff and before stand pat — on recursive nodes, not only the first main-search-to-qsearch call. (`qsearch` is also entered directly from ProbCut, whose nodes never pass through `search`'s terminal block; ProbCut is off by default, so that path is structural rather than live — see below.)

**Correction history cannot touch a terminal.** Every terminal return above is a direct `info[I_CONTEMPT]` value; none passes through `corrected()`. This is the point the directive made with the +64 counterexample, and it is now structural rather than incidental.

**`endgame_scale` is deliberately untouched.** It is a heuristic scale, not a rule, and mixing the two is what produced the original confusion. Its docstring's claim about pawnless material remains a heuristic and I have not promoted it to a theorem.

**Repetition inside `qsearch`.** I did not add a repetition test there, and the reason is a proof rather than an omission. `I_QS_CHECKS` is **0** in the shipped configuration, so every move quiescence plays is a capture or a promotion, both of which reset the halfmove clock; a repetition needs two same-side plies at an unchanged clock and cannot occur. The fifty-move test *is* present because it becomes reachable the moment quiet checks are enabled (`BINI_QS_CHECKS=1`), and it costs one comparison.

The same reasoning bounds the ProbCut argument. ProbCut does enter `qsearch` without passing through `search`'s terminal block, but `I_PROBCUT` is **0** by default, so that path is dormant in the shipped build — it is a structural reason for putting the block there, not a live one. What earns C1's quiescence block its keep in the shipped configuration is **stalemate and dead material**, which are live on every quiescence node.

### Negative and counterexample tests, all passing

`kn6/1B6/1K6/8/8/8/8/8 b - - 0 1` — the legal bishop-versus-knight checkmate — is still scored `-29999`. `KNN-K`, `KBN-K`, opposite-colour bishops, `KB-KN`, `KN-KN` and material with pawns are **not** forced to zero. A genuine fifty-move draw stays a draw; a stalemate on the 100th halfmove stays a draw and does not become a mate. The rejected `(wm == 1 and bm == 1)` condition appears nowhere in the patch.

---

## C1b — Terminal semantics at the maximum-ply exits

**Status:** reproduced → fixed → regression-tested. **Depends on:** C2, then C1.
**Source locations:** `bini_search.py::qsearch` and `::search`, the `ply >= MAX_PLY - 1` guards.

Both entry points bail out with a raw evaluation once the ply counter reaches `MAX_PLY - 1`. In
`qsearch` that bail-out sat **above** C1's terminal block, so the deepest nodes were still deciding
dead material and stalemate by neural evaluation — C1 had fixed every quiescence node except the
ones at the bottom of the stack. In `search` the rule-draw block runs first, but the exit still
returned an evaluation for a position that might be **mate or stalemate**, because those are
decided by the `legal == 0` path further down which the exit skips.

**Patch.** The quiescence terminal block is moved above the max-ply exit, and both exits now
answer mate (and, in `search`, stalemate) before falling back to an evaluation. The cost is
confined to ply 127, where the search is over anyway.

**Evidence** (`astra_tests/test_v2.py`, ply forced to `MAX_PLY-1 = 127`, correction history
saturated): the baseline **fails** on dead K+B-vs-K, dead K-vs-K, stalemate and checkmate in both
entry points; the candidate passes all eight. The negative control — an ordinary middlegame
position at ply 127 — still returns an evaluation (−14) and is **not** turned into a draw.

## C2b — A real draw claim is not the same thing as a search heuristic

**Status:** implemented → tested against an independent oracle. **Depends on:** C2.

The baseline, and C2 with it, score **any** earlier occurrence as a draw — including a single
occurrence in the game before the root. That is a *second* occurrence. FIDE needs a third, and so
does the referee: driving `board.outcome(claim_draw=True)` over a repeated knight cycle, it first
reports `THREEFOLD_REPETITION` at **ply 7**, where the engine's rule was satisfied from **ply 4**.
Scoring a second occurrence as a draw is therefore an *invented* claim, not a conservative one.

**Patch.** `repetition_kind()` replaces the boolean and returns:

| kind | meaning | status |
|---|---|---|
| 1 | a cycle inside the **search tree** | a **named heuristic** — the side that wants the repetition can force it, which is why every strong engine scores it as drawn. Not a FIDE claim. |
| 2 | a genuine **third occurrence** counting pre-root game history | a real claim, matching what the referee adjudicates |
| 0 | anything less, including a bare second occurrence in history | **not a draw** |

Both 1 and 2 still return the draw utility, but they are different claims, they are tested
separately, and a bare second occurrence is no longer one of them.

**Evidence.** Every repetition case in `test_repro.py` is now scored against an **independent
python-chess oracle** that replays the whole line and counts occurrences, rather than against my
own arithmetic — which caught one case (`C.cycle_in_game_history`) that I had hand-computed
wrongly as a second occurrence when it is in fact a third. Ten cases, all agreeing with the
oracle on the candidate: in-tree cycles → 1, third occurrences → 2, second occurrences → 0,
pawn moves and changed castling rights → 0.

**What this changes in play, stated plainly.** The engine will no longer treat a position it has
seen once before in the game as drawn on sight. It can still find the draw — when a repetition is
actually forceable, the cycle appears inside its own tree and returns kind 1. What it can no
longer do is award itself a draw that the referee would not give. This is a behavioural change
beyond a pure bug fix, it is the change the brief asked for, and it is the one item in this
candidate whose game-level effect I most want the timed gate to check.

---

## Evidence

### Reproductions (`astra_tests/test_repro.py`)

| | baseline | C2 only | C1+C2 |
|---|---|---|---|
| failures | **7** | **6** | **0** |
| tests | 21 + 2 info | 21 + 2 info | 21 + 2 info |

Artefacts: `repro_v8_baseline.json`, `repro_c2_only.json`, `repro_c1c2_candidate.json`. C2 alone moves exactly one case, which is the isolation the directive asked for.

### Generalised suite (`astra_tests/test_suite.py`)

**Baseline 19/20 · candidate 20/20 — identical on macOS/arm64 and on the x86 deployment target.** The single baseline failure is `T1.terminal_beats_poisoned_tt`, on the three dead-material classes, with a deliberately poisoned exact depth-60 TT entry of +900 and saturated correction history for that very position.

Everything else passes on **both** builds, which is the point — the patches were required not to break anything:

* **Move generation is sound.** perft matches python-chess on ten positions (six with published constants, plus en-passant-pin, promotion and castling positions) and on **623** positions drawn from 30 seeded random games. The suite also cross-checks its own published constants against python-chess, after I briefly mis-reported a perft failure that was my test's fault, not the engine's.
* make/unmake restores bitboards, state and piece array over ~26,000 moves; the incrementally maintained Zobrist key equals a full recompute every time; a rejected illegal move leaves caller state intact; nested null make/unmake restores key, side, rights and clock at depths 1–5.
* **NNUE:** incremental accumulator *and* evaluation equal a full refresh over 26,492 moves spanning quiet (23,880), capture (2,497), promotion (56), castling (55) and en-passant (4), across output buckets 5–7. Largest accumulator magnitude observed **3,485** against an `int16` limit of 32,767 and a declared worst-case bound of 16,355. NNUE confirmed on, not a silent handcrafted downgrade. Colour-mirrored evaluations agree within 40 cp. A full search restores the board and the root accumulator.
* **TT and search:** 4,000 randomised pack/unpack round trips including mate normalisation; mate scores carry the right distance at plies 1, 2, 3, 5, 8; excluded-move search terminates and restores its slot; full and reduced-pruning searches agree within 15 cp on quiet positions (a consistency check, *not* a claim that selective search returns exact minimax); a search aborted mid-tree at node caps of 2,000 / 20,000 / 200,000 restores the board and root accumulator exactly; depth-preferred replacement holds and a key colliding to the same index is never read back as a hit; null windows placed 200 and 600 cp either side of the true score fail on the correct side.

### Wrapper and cold init (`astra_tests/test_wrapper.py`)

Run in a **cold process with the production `COMPILE_JOIN_S = 75`** — no `BINI_JOIN_S` override. **13/13 on both builds.**

| | baseline | candidate |
|---|---|---|
| import + compile | **26.9 s** | **24.1 s** (budget 90 s) |
| NNUE on | yes | yes |
| stdout at import / in play | clean | clean |
| 80-ply self-play, all moves legal | yes | yes |
| hard-budget breaches | 0 | 0 |
| forced move / no legal move / low clock (2000→40 ms) | correct | correct |
| engine exception + illegal candidate recovery | legal move, telemetry on stderr | same |
| threads alive between moves | none | none |

The 2.8 s init difference is run-to-run compile variance, not a patch effect. **`BINI_JOIN_S=300` is used only for contended-box gating and does not leak into this measurement.**

### Runtime cost (`astra_tests/bench.py`)

Fixed depth 10, best of 2, nine positions.

| position | baseline knps | candidate knps | Δ | nodes |
|---|---|---|---|---|
| opening | 344.1 | 339.3 | −1.4% | identical |
| kiwipete | 324.8 | 328.7 | +1.2% | identical |
| middlegame | 352.5 | 352.9 | +0.1% | identical |
| tactical | 345.8 | 341.1 | −1.4% | identical |
| rook endgame | 395.1 | 383.1 | −3.0% | identical |
| pawn endgame | 377.9 | 372.0 | −1.6% | identical |
| queenless | 351.1 | 345.8 | −1.5% | identical |
| **minor endgame** | 402.0 | 395.4 | −1.6% | **34,313 → 41,495** |
| **halfmove 80** | 421.4 | 412.9 | −2.0% | 28,931 → 28,923 |

**Mean −1.08% over the seven positions whose node count is identical** — that is the pure cost of the added terminal checks. Two positions changed tree shape, both expected: the minor endgame is the K+B-vs-K+N family where sub-lines now terminate at zero (its score moved +62 → −65, i.e. the engine stopped believing it was better in a drawn ending), and the halfmove-80 position moved by eight nodes.

**Confirmed by a second, drift-controlled experiment.** A first attempt at depth 11 appeared to show −40%, and then −9%. Both were measurement artefacts, and I am reporting them rather than quietly dropping them: the first had another test running on the same machine, and the second was machine drift. Re-run as A/B/A/B at depth 11, best of 4:

| run | build | knps | nodes |
|---|---|---|---|
| 1 | baseline | 361.9 | 977,117 |
| 2 | candidate | 329.2 | 991,322 |
| 3 | **baseline** | **328.8** | 977,117 |
| 4 | candidate | 353.3 | 991,322 |

The baseline itself measured 361.9 and then 328.8 knps on **bit-identical work** — a 9% swing from machine state alone, which is exactly why the ordering was interleaved. Comparing means: 341.3 vs 345.4 knps, **−1.2%**, agreeing with the depth-10 figure. Node counts are identical within each build across repeats, so the work being timed is deterministic and only the timing drifts.

**Best estimate: about −1%, with a precision of a few percent, not a fraction of one.** This machine cannot resolve better than that, and I am not going to quote three significant figures off a bench that swings 9% on its own. A 1% speed cost is roughly 1–2 Elo; no 400-game gate at an 82% draw rate can resolve that either way. It is the price of not returning −1719 for a stalemate.

**These are Mac/arm64 numbers at fixed depth with a cold table; the x86 deployment target is faster in absolute terms and its correctness is validated separately (Report 03).**

---

## C3 and C4 — diagnosed, deliberately **not** in this release

**C3 — null-move and identity.** The null half of C3 is addressed inside C2 (nulls no longer age the fifty-move clock; the repetition walk stops at a pass) and is covered by `S6.null_make_unmake`. Two items are **open and unfixed**:
* **EP hashing** accepts a potential pawn capture without testing whether it is legal under a pin, so two positions can share a Zobrist key while differing in legal options. My perft suite includes two EP-pin positions and both match python-chess exactly, so the *move generation* is right; the *hash* aliasing is a TT-sharing question I have not yet demonstrated a wrong result from.
* **Book keys omit EP entirely** (`board_fen() + side + castling_xfen()`). Legality-checking the chosen move — which `agent.py` does — prevents an illegal book move but not a strategically wrong one. Narrow (first 12 moves only) and unfixed.

**C4 — TT context correctness. Hypothesis tested and REFUTED.** My working hypothesis, stated earlier in this session and carried into the first draft of this report, was that round 100's `Rfa1` was invalid context reuse: a cold replay played `Qb2` where the game played `Rfa1`, so accumulated state looked like the carrier. **That is wrong, and I am withdrawing it.** Three measurements:

1. **Full wrapper replay.** Feeding the exact FEN and clock sequence of round 100 through `agent.get_move` — TT, correction history, killers, continuation history and pre-root game keys all accumulating exactly as in the game — the engine plays **`Qb2`, not `Rfa1`**. The blunder does not reproduce. The replay reached depth 19 in 3,361 ms where the game reached depth 18 in 1,742 ms; the machine differs, so the depth differs.
2. **Fixed-depth sweep at the position** (`2r3k1/6p1/1p1pr2p/1Pqb1p2/5P2/R1NP3P/3Q2PK/5R2 w - - 7 29`), cold table, deterministic:

| depth | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 | 19 | 20 | 21 | 22 | 23 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| best | Rfa1 | Rfa1 | Qb2 | Qb2 | Rfa1 | Rfa1 | Qb2 | Rfa1 | **Rfa1** | Qb2 | Qb2 | Rfa1 | Rfa1 | Qb2 |
| score | +11 | +22 | −78 | −20 | +54 | −20 | −30 | −20 | **+8** | −37 | −31 | −20 | −20 | −40 |

The engine oscillates between the two moves at **every** depth from 10 to 23 — 40 million nodes at depth 23 — and never scores them more than about 60 cp apart. There is no depth at which it sees a 523 cp difference. The in-game choice at depth 18 was not caused by stale context; the two moves are simply indistinguishable to this engine.

3. **Which side of the blind spot.** Searching the positions *after* each move to depth 18:

| | engine (depth 18) | Stockfish (depth 26) | error |
|---|---|---|---|
| after `Qb2` | **−3** | −36 | ~33 cp — accurate |
| after `Rfa1` | **−17** | **−559** | **~540 cp** |

So the evaluation is *right* about the good move and *wrong by five pawns* about the bad one, and 3.9 million nodes do not find the refutation.

**Diagnosis: round 100 is an evaluation and search blind spot, not a rule defect, not a transposition-table context defect, and not a time-management defect.** No patch in C1–C4 addresses it. It is a strength limit of the current network plus the depth this implementation reaches in the time available. I am recording it as such rather than attaching it to a repair that would not have prevented it.

The genuine C4 concerns from the directive — that a bad stored score can move pruning, aspiration windows and thinking time even when the root move is unchanged — remain **untested and open**. I built the diagnostic replay for them and it produced this negative result; I have not constructed the adversarial-history matrix that would actually settle them, and I will not claim the transposition table is context-safe on the strength of one refuted hypothesis.

## Round 99 — what C1 actually changes in a real game

Round 99 ended `1/2-1/2` by insufficient material. Our move 64, from `8/6n1/4K2B/8/8/7k/8/8 w - - 2 70` (K+B vs K+N), was `Bxg7`, taking the knight and reaching **K+B vs K — a dead draw** — and the in-game log scored that move **+80**.

| | baseline | candidate |
|---|---|---|
| score of `Bxg7`, depth 8 | **+67** | **−20** |
| depth 12 / 16 / 20 | −43 / −44 / −20 | −20 / −20 / −20 |
| move chosen | `Bxg7` | `Bxg7` |

**C1 makes the evaluation truthful and immediate** — the draw utility from depth 8, stable, instead of a wandering +67 — **but it does not change the move or the result.** Every alternative from that position is also a draw; K+B vs K+N is itself theoretically drawn and the engine cannot do better. I am stating this plainly because the temptation is to present R99 as "fixed". It is not fixed; the engine's *belief* is fixed. That matters for earlier decisions — a search that scores a liquidation at +80 will steer toward it — but it did not cost this game, and I have no evidence that it cost any game.

## R102 — the defect caught in a rated game, decomposed

Round 102 finished at 18:07 UTC on 10 September, after V8 went live. We were Black; the game was
drawn by **insufficient material**, the final position being bare kings. The engine's own log:

```
m117 d25 d2g2  +57cp    (122...Rxg2, trading into K+P vs K+P)
m118 d22 g5g4  +54cp    (123...g4, which after 124.fxg4+ Kxg4 leaves K vs K)
m119 d29 h5g4  -20cp    (124...Kxg4 - only now, with the board already bare, does it see a draw)
```

**Layer-by-layer attribution** (`astra_tests/decompose.py`, cold table, contempt-signed draw = ±20):

| position | raw NNUE | after `endgame_scale` | search d18 | search d22 | candidate | Stockfish d34 |
|---|---|---|---|---|---|---|
| m117, before Rxg2 | 12 | 12 | **+61** | **+59** | **−20** | **0.00** |
| m118, before g4 | 47 | 47 | **+59** | **+61** | **−20** | **0.00** |
| m119, before Kxg4 | 87 | 87 | +59 | +57 | −20 | 0.00 |
| **bare K vs K** | **−68** | **−9** | **−65** | **−64** | **−20** | draw |

The bottom row is the whole defect in one line. The network scores an empty board at **−68**;
`endgame_scale` divides it to −9 and *keeps the sign*; and the search, having no terminal rule to
appeal to, wanders back out to **−64**. The engine simply has no representation of "this position
is over". C1 returns the draw utility at every depth.

**Was a win thrown away?** No — and I checked rather than assumed. Stockfish at depth 34 on every
legal move at m116, m117 and m118 returns **0.00 for every reasonable move**: the position was
drawn throughout and **no winning alternative existed**.

**Was a draw thrown away?** Also no, and this is the more interesting half. At m117 the position
is genuinely sharp: **nine of seventeen legal moves lose by force** (the rook on d2 is attacked
along the rank), and only eight hold. Both builds choose `Rxg2` — one of the eight — at every
depth from 6 to 22. So the move selection was sound in a position where more than half the moves
lose.

| R102 m117, drawing move chosen at depth | 6 | 10 | 14 | 18 | 22 | losing choices |
|---|---|---|---|---|---|---|
| baseline | ✓ **−20** | ✓ −5 | ✓ −2 | ✓ **+61** | ✓ **+59** | 0 of 5 |
| candidate | ✓ −20 | ✓ −20 | ✓ −20 | ✓ +34 | ✓ −20 | 0 of 5 |

**So the honest verdict on R102 is: right moves, wrong numbers.** The false positives were real
and are eliminated, but they did not cost this game. What they cost is the engine's ability to
*plan*: a search that believes a liquidation is worth +60 will steer into one, and the R99
family is where that does cost something.

## R100, decomposed rather than assumed

The earlier entry in this report said R100 was "an evaluation and search blind spot". That was
directionally right but it was an assumption dressed as a conclusion. Decomposing it properly
gives a sharper and partly different answer.

**Method.** Search the position *after* the blunder (`2r3k1/6p1/1p1pr2p/1Pqb1p2/5P2/R1NP3P/3Q2PK/R7 b`)
at fixed depth with one heuristic layer switched off at a time. Truth, from Stockfish: **−559**
for White. Scores below are from White's side.

| configuration | d10 | d14 | d16 | nodes at d16 |
|---|---|---|---|---|
| default | −11 | −26 | −14 | 1,387,296 |
| **null-move pruning off** | **−129** | **−169** | **−115** | 1,884,783 |
| correction history off | −51 | −7 | +3 | 1,434,138 |
| continuation history off | +6 | +7 | −139 | 1,689,353 |
| SEE pruning off | +93 | −11 | +82 | 1,758,198 |
| quiescence checks on | −81 | +3 | −14 | 1,507,962 |
| all of the above | +23 | −132 | −113 | 2,290,160 |

**What this actually shows.**

1. **Null-move pruning is the single largest masker.** Disabling it alone moves the score from
   −14 to −115 at depth 16 and −169 at depth 14 — roughly 100 to 155 cp of the error, and no
   other single switch does that consistently. The refutation involves a quiet build-up the null
   move lets the search skip over.
2. **It is not the whole story, and this is the part that matters.** With *every* switchable
   layer off, the engine still reaches only **−113** against a true **−559**. Around 400 cp of
   the gap survives the removal of correction history, continuation history, SEE pruning and
   null-move pruning together. That residue is evaluation and depth, not a pruning bug.
3. **Two layers move it the wrong way.** Turning SEE pruning off gives **+82**, further from the
   truth than the default; continuation history off is erratic (+6, +7, −139). The layers
   interact, so "disable pruning to see better" is not a repair, and I am not proposing one.

**Honest limits of this experiment.** Switching a pruning layer off changes the shape of the
tree, so scores at equal nominal depth are not strictly comparable in centipawns; what is
comparable is the direction and rough size, and those are consistent across three depths.

**Conclusion.** R100's failure is *partly* null-move pruning hiding the refutation and *mostly*
a limit of the evaluation at the depth this implementation reaches. **No patch in this candidate
addresses either half**, and I am not proposing a null-move change on the strength of one
position — that is exactly the kind of evidence-free heuristic edit the brief rules out. It is
recorded as a specific, reproducible post-lock investigation with a named first suspect.

## The dead-material defect cuts both ways

This is the part I had wrong when I first framed R99 as "the engine throws away wins". `endgame_scale` divides a pawnless score by 8 but **keeps its sign**, so the baseline is wrong in *both* directions:

* **ahead** — a raw +640 in K+B vs K becomes +80. The engine still believes it is winning and will liquidate into a dead draw. That is R99.
* **behind** — a raw −640 becomes −80. The engine still believes it is losing and will **avoid a saving dead draw**, which is the "convert losses into draws" case the owner cares about.

Two constructed positions where the losing side can capture into dead material, searched on both builds:

| | baseline, depth 6 / 10 / 14 | candidate |
|---|---|---|
| `7k/8/8/8/3n4/8/1n6/K7 w` — Kxb2 reaches K vs K+N | **−21 / −79 / +45** | **−20 / −20 / −20** |
| `8/8/4k3/8/8/8/1b6/K7 w` — Kxb2 reaches K vs K | **−2 / +56 / −65** | **−20 / −20 / −20** |

Both builds find the capture *here*, because it is obviously best. The point is the **score**: the baseline's estimate of a dead ending is sign-flipping noise inside ±80, so it cannot plan toward or away from one; the candidate's is exact and stable from depth 6. That precision is spent several plies earlier, when the engine is deciding whether to steer into such an ending at all — which is where R99 was actually lost, not on move 64.

This composes correctly with the existing draw policy, which I checked rather than assumed: `draw_behind = 1` sets contempt to **0** once the previous root score is ≤ −100 and the move number is ≥ 20, so when the engine is losing a dead draw scores 0 rather than −20 and it will take it. C1 makes that policy actually reachable in dead endings, where before it was competing against a fictitious ±80.

## Interactions and residual uncertainty

* C1 edits the terminal block C2 leaves behind, so **C1 must be applied after C2**; both patch scripts assert a unique anchor and `py_compile` the result before writing. The combined candidate is the thing that was tested — no untested combination is being proposed.
* The terminal draw utility is contempt-signed (±20), unchanged from the baseline. C1 makes *more* positions reach that utility, so if contempt is mis-signed anywhere the patch increases exposure to it. Contempt was not touched and the sign convention matches the existing `legal == 0` path exactly.
* Dead-material recognition now fires before the TT probe on every non-root node. On a position at `ply >= MAX_PLY-1` the pre-existing `return evaluate(...)` guard still runs first; at ply 127 the search is over regardless, and I am recording it rather than special-casing it.
* Elo is not yet measured. **A positive result is not required to justify these repairs**, and equally I will not claim non-inferiority merely because an interval contains zero — Report 03 states a predeclared margin and tests it.

**Question for Astra:** C4's original hypothesis is refuted (above) and I have no reproduction of invalid transposition reuse. The remaining C4 work — an adversarial matrix over differing legal histories, halfmove counters near a claim boundary, and empty/warm/move-order-only/bounded tables — is real but unstarted. **My recommendation is to hold it post-lock**: a transposition-table change in the final hours is exactly what section 8 warns against, and I have no failing test to aim it at. If you want it attempted before the lock, say so and I will build the matrix rather than the fix.
