# Astra Report 01 — Baseline and Reproductions

**Build under test:** BINI Alpha / Opus Carlsen, frozen V8 (platform "v10")
**Written:** 10 September 2026, ~19:15 BST · lock 11 September 11:00 London
**Status:** all four directed cases reproduced against the unmodified frozen engine; C1 and C2 implemented and passing. Nothing has been uploaded and `bini_v8_ship/` is untouched.

---

## 1. Baseline manifest

`submission_v8_0910_0313.zip` — **SHA-256 `47ace1930f8119473b49524e30652f0ae7c798e8cdad601bac07e6adebee8449`**, 7,104,654 bytes packed, **14,042,168 bytes unpacked, ten files**. This matches the digest in the directives exactly.

The archive and `bini_v8_ship/` are byte-identical file for file:

| file | md5 |
|---|---|
| `agent.py` | `5bff736371872bc5688fd59d0c1cc74c` |
| `bini_board.py` | `861d5989e13dc1938cbeeb7d6e045366` |
| `bini_calib.py` | `18210c5b3f8d7109151da461ee3b74f8` |
| `bini_engine.py` | `4f4de482c28eca01e47cff5d6380a2c2` |
| `bini_eval.py` | `d44763ba4ad0465a9257bfb32cd9c990` |
| `bini_magics.py` | `3c2ab7807a87e0f31fb4d889367870e2` |
| `bini_nnue.py` | `e06453c8a7a9a34b1e9405b309b071c2` |
| `bini_search.py` | `163cda13023d7d5aa89cc4b523c6b576` |
| `book.json` | `51c97f3f4e8ab4c1801543945d749906` |
| `nnue.safetensors` | `182c8fc8fb60b96fdb51f231cbe9c0e9` |

**Network, read from the loaded module, not from prose:** 768 → 1024 → 2 → 8 output buckets, SCReLU, `int16` accumulators, `ACC_BOUND = 16355` (worst case; the largest magnitude actually observed over ~26,500 probed positions was **3,485**, comfortably inside the `int16` limit of 32,767).

**Effective feature settings, read from `bini_engine.py` rather than from any narrative.** The directive was right to insist on this and I got two of them wrong on a first pass, so they are listed exactly:

| flag | default | |
|---|---|---|
| `I_USE_NNUE` | **1** | network in use |
| `I_CORR` (correction history) | **1** | on |
| `I_CONT` (continuation history) | **1** | on |
| `I_SEEP` (SEE pruning in main search) | **1** | on |
| `I_QS_CHECKS` (quiet checks in quiescence) | **0** | **off** |
| `I_IMPROVING` | **0** | **off** |
| `I_PROBCUT` | **0** | **off** — compiled in, not enabled |
| `I_CALIB` (`bini_calib` table) | **0** | **off** |

Contempt is **20 cp**, and `draw_behind = 1`: when the previous root score is ≤ `draw_cp` (−100) and the move number is ≥ `draw_move` (20), contempt is set to **0** for that move — so a draw scores 0 rather than −20 and the engine accepts a draw when it is losing. The terminal-draw utility the tests below observe is therefore ±20 in a level game and 0 when behind.

Two consequences matter for C1. Because `I_QS_CHECKS` is **off**, every move quiescence plays is a capture or promotion, both of which reset the halfmove clock — so a repetition cannot arise inside quiescence at all, and the fifty-move test I added there is unreachable in the shipped configuration (it is correct, and becomes live if quiet checks are ever enabled). Because `I_PROBCUT` is **off**, the ProbCut path that enters `qsearch` without passing through `search`'s terminal block is likewise dormant by default. C1's quiescence terminal block therefore earns its keep on the **stalemate** and **dead-material** cases, which are live on every node, not on the rule-draw cases.

**Environments used.** Correctness work: `/tmp/chess-external-review-venv/bin/python` — Python 3.13.2, numpy 2.5.3, numba 0.67.0, llvmlite 0.49.0, python-chess 1.11.2, macOS 26.0 arm64. A second environment exists at `aichessathon-starter/.venv` (Python 3.12.4, numpy 2.5.2, same numba/llvmlite/chess). **Neither is the x86 deployment image**; every number below is Mac/arm64 and x86 validation is tracked separately. Probes ran with `BINI_TT_BITS=16` (a deliberately small table, so TT pressure is if anything higher than in play).

**Isolation.** `bini_astra_correctness/` (C1+C2) and `bini_astra_c2/` (C2 only) were unpacked from the verified archive and confirmed byte-identical before patching. `bini_v8_ship/`, the incumbent zip and the existing `bini_v85_*` candidates were not modified.

---

## 2. Reproductions against the frozen engine

Suite: `astra_tests/test_repro.py`, driven through the real `search`/`qsearch`/`is_repetition` entry points via `astra_tests/harness.py`. Artefacts: `astra_reports/repro_v8_baseline.json`, `repro_c2_only.json`, `repro_c1c2_candidate.json`.

**Baseline result: 7 failures.** Candidate result: **0 failures.**

### A — Stalemate at the quiescence frontier · *reproduced*

`k7/8/1QK5/8/8/8/8/8 b - - 0 1` is stalemate. `qsearch` returns **−1719**.

Root cause, from source: `qsearch` stand-pats on `corrected(evaluate(...))` when not in check, and only ever tests `legal == 0` *after* generating captures — so "no legal captures" is silently treated as "no legal moves". The generalised case shows it is not a one-position curiosity: **four of five** stalemate positions returned a non-draw score (−297 to −1905), and a stalemate reached one capture deep inside `qsearch` returned **+1719** to the side that stalemated its opponent — i.e. the engine reads a stalemating capture as winning a queen.

### B — Checkmate at the fifty-move boundary · *reproduced*

`7k/6Q1/5K2/8/8/8/8/8 b - - 100 1` is checkmate. At non-root ply 1 the engine returns **−20**, the draw utility.

Root cause: in `search`, `if st[S_HALF] >= 100 or is_repetition(...)` precedes any legality or check test, so the fifty-move return pre-empts mate detection. Reproduced through the real parent transition as well: from `7k/8/5K2/8/8/8/6Q1/8 w - - 99 1` the parent scores the mating move **−20** instead of a mate score.

Both negative controls already passed on the baseline (a genuine fifty-move draw stays a draw; a stalemate on the 100th halfmove stays a draw, not a mate), so the defect is specifically the precedence, not the rule.

### C — Repetition at an even-ply history boundary · *reproduced*

Exactly as described: pre-root `g1f3`, root after `g1f3 g8f6`, in-tree `f3g1 f6g8`. At ply 2, halfmove 4, the current position *is* the initial position and `is_repetition` returns **False**.

Root cause confirmed at source: `ub[0]` and `hist[hist_n-1]` are the *same* position — the root. The search-path loop tests it at `steps=2`, then the history loop starts at `hist[hist_n-1]` and tests it again at `steps=4`. Every genuine pre-root ancestor is therefore charged two plies more than its true distance, and the `steps <= half` guard cuts the walk off two plies early. Six other repetition cases (in-tree cycles, pure-history cycles, odd parity, spent castling rights, irreversible-move and distinct-position negatives) **passed on the baseline** — which is why this never showed up as an obvious failure.

### D — The existing insufficient-material candidate is not an exact repair · *confirmed, and a separate baseline defect found*

`kn6/1B6/1K6/8/8/8/8/8 b - - 0 1` is a legal checkmate with bishop against knight (python-chess: valid, checkmate, **not** insufficient material). The directive is right that `bini_v85_insuf`'s `(wm == 1 and bm == 1)` condition is unsound. **That condition has not been used.** For the record, the frozen engine already scores this position `-29999`, so the mate itself is found; the objection is to the proposed fix, not to baseline behaviour here.

Two further facts confirmed:

* `corrected()` moves a static zero to **+64** with two saturated correction entries, so "the evaluation happens to be 0" is not a draw guarantee.
* Separately, **the baseline does not recognise dead material at all**: `K+B vs K` scored **107**, `K+N vs K` **111**, `K vs K` **61**, same-colour bishops **78**. `endgame_scale` divides such scores by 8 rather than returning a terminal draw, and the docstring's claim that pawnless material differences below a rook are "drawn" is a heuristic, not a theorem. This is the R99 family of positions.

---

## 3. Patch boundaries

Two patches, applied by auditable scripts that assert a unique anchor and `py_compile` the result (`astra_tests/patch_c1.py`, `patch_c2.py`).

**C2 — repetition indexing and null boundaries.** *Files:* `bini_search.py`, `bini_board.py`. *Depends on:* nothing.
`is_repetition` rewritten on an explicit distance model — distance `d` is `ub[ply-d]` inside the tree and `hist[hist_n-1-(d-ply)]` past the root, so the root is visited exactly once. It now takes `ui` and stops at the nearest synthetic null ancestor. `make_null` no longer advances the halfmove clock: a pass is not a move, so it must neither age the fifty-move counter inside null subtrees nor widen the repetition window across the pass.

**C1 — exact terminal semantics.** *Files:* `bini_search.py` only. *Depends on:* **C2** (it edits the terminal block C2 leaves behind).
Adds `dead_material()` (exactly python-chess's `is_insufficient_material`, derived class by class, not copied from the rejected candidate), `king_has_move()` (a cheap exact gate: if the king can legally step anywhere, the position is not stalemate) and `has_legal_move()` (the expensive exact probe, generating into a dedicated scratch slice past every live ply and saving/restoring this ply's undo entry, so it leaves no trace). In `search`, dead material returns the draw utility **before** the TT probe, correction history or any pruning; checkmate now outranks the fifty-move rule. In `qsearch` the same terminal block runs before the TT cutoff and before stand pat, on recursive nodes as well as the first call — `qsearch` is also entered directly from ProbCut, which never passed through `search`'s terminal block at all.

`bini_eval.endgame_scale` is **deliberately untouched**: it is a heuristic scale and is kept distinct from exact rule recognition, as directed.

---

## 4. Discrepancies from Astra's findings

1. **`arena_par.py` interval arithmetic.** Astra is right that Bernoulli variance is wrong at an 84% draw rate. My own earlier reports used ±34 at 400 games and that figure is too wide. I have *not* substituted ±13.6; the correct number depends on measured pair covariance, which I am computing from retained PGNs rather than asserting.
2. **Curated input size.** Confirmed: the local curated EPD holds **288** FENs, distinct from the 1,226-root book corpus. This is the same class of error I made when rebuilding the book, and it is now a coverage gate in code.
3. **Move generation is sound.** I initially recorded a perft failure on two positions. It was my test at fault — one FEN was not a legal position and my remembered counts were wrong. Against python-chess as oracle, perft matches on **ten** positions and on **623** positions drawn from 30 seeded random games. I am flagging this explicitly because a wrong constant reported as an engine bug is exactly the failure mode the directive warns about; the suite now cross-checks its own published constants.
4. **R100.** Independent Stockfish analysis at depth 26 says the played `Rfa1` lost **523 cp** (best `Qb2`, −36). A cold replay of that exact position plays `Qb2` at 1.7 s, 3.1 s, 6.8 s and 20 s (depths 14–23). So the blunder is **not** a time-allocation effect, and it is not explained by C1 or C2. It is a live, unexplained context-dependence reproduction and belongs to C4. It is recorded here rather than claimed as fixed.

---

## 5. Reproduction summary

| case | baseline | C2 only | C1+C2 |
|---|---|---|---|
| A. qsearch stalemate (single) | **FAIL** −1719 | FAIL | PASS −20 |
| A. stalemate set, poisoned corr (5) | **FAIL** 4/5 | FAIL | PASS 0/5 |
| A. stalemate at a recursive frontier | **FAIL** +1719 | FAIL | PASS +20 |
| A. probe leaves no trace | n/a | n/a | PASS |
| B. mate at halfmove 100, non-root | **FAIL** −20 | FAIL | PASS −29999 |
| B. mate through the parent transition | **FAIL** −20 | FAIL | PASS +29999 |
| B. negative: real fifty-move draw | PASS | PASS | PASS |
| B. negative: stalemate at halfmove 100 | PASS | PASS | PASS |
| C. even-ply history boundary | **FAIL** | **PASS** | PASS |
| C. six other repetition cases | PASS | PASS | PASS |
| D. dead material scores the draw utility | **FAIL** 6/6 | FAIL | PASS 0/6 |
| D. winnable material not zeroed | PASS | PASS | PASS |
| **totals** | **7 fail / 21** | **6 fail** | **0 fail / 21** |

Report 02 covers the diffs, the generalised suite, runtime cost and residual risk.
