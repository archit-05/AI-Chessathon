# Astra Final Report — Candidate Decision

**Candidate:** `bini_astra_v2/` — frozen V8 + C2 + C1 + C1b + C2b
**Archive:** `submission_astra_v2.zip`
· SHA-256 **`2c14b91fbb131dcd74f9d3fca488aacd8e3288e9a8e568017e30c834a9ac20db`**
· 7,106,973 bytes packed · **14,049,339 bytes unzipped** · 10 files
**Earlier candidates retained:** `submission_astra_c1c2.zip` (C1+C2, SHA-256 `ef41bc8d…`) and
`submission_astra_c2only.zip` (C2 alone, SHA-256 `92a8098b…`)
**Incumbent / rollback:** `submission_v8_0910_0313.zip`, SHA-256 `47ace1930f8119473b49524e30652f0ae7c798e8cdad601bac07e6adebee8449`, untouched
**Lock:** 11 September 2026, 11:00 Europe/London

> **VERDICT: pending the timed gate — filled in below.**

**Nothing has been uploaded.** No upload will happen without the owner's explicit instruction.

---

## 1. What is in the candidate, and what is not

**Included — two files, four correctness repairs:**

* **C2** (`bini_search.py`, `bini_board.py`) — repetition detection rewritten on an explicit distance model; the root is no longer counted twice; the walk stops at a synthetic null ancestor; `make_null` no longer advances the fifty-move clock.
* **C1** (`bini_search.py`) — exact terminal semantics: dead material, stalemate and the fifty-move rule are decided **before** the transposition table, correction history, pruning or stand pat can supply a number; checkmate now outranks the fifty-move rule.
* **C1b** (`bini_search.py`) — the same guarantees at the **maximum-ply exits** of both entry points, which previously bailed out with a raw evaluation; mate and stalemate are answered there too.
* **C2b** (`bini_search.py`) — a **real threefold claim** is separated from the **in-tree search heuristic**, and a bare second occurrence in game history is no longer scored as a draw, because neither FIDE nor the referee grants one.

**Excluded, deliberately:**

| not shipped | why |
|---|---|
| any network change | out of scope by directive; the net is byte-identical |
| any book change | a full rebuild measured **−16.5 ±13.9 Elo**; the pipeline is unsound but a rebuild made play *worse* |
| book-key en-passant fix | invalidates all 6,105 entries — a rebuild by another name |
| a wrapper guard skipping the book when en passant is available | a playing-behaviour change with no supporting evidence |
| `stable`, `mtg24`, `mtg30`, `insuf` time/eval candidates | all null at 400 games with corrected intervals |
| any C4 transposition-table change | its original hypothesis is refuted and no failing test points at one |
| `endgame_scale` | a heuristic scale, kept distinct from exact rule recognition, as directed |

## 2. Guarantees established — stated as tested invariants, not as "perfect"

These are things the suite **demonstrates**, on macOS/arm64 **and** on the x86 deployment target (AMD EPYC 9J14, Python 3.12.3, numba 0.67.0):

1. **Terminal positions are decided by the rules, not by a stored or corrected number.** Dead material, stalemate and the fifty-move rule are evaluated before the TT probe, before `corrected()` and before any pruning, in `search` **and** in `qsearch` — including `qsearch` nodes entered from ProbCut, which never pass through `search`'s terminal block. Verified against a deliberately poisoned exact depth-60 TT entry of +900 and saturated correction history.
2. **Dead material matches python-chess exactly** on K-K, KB-K, KN-K (either orientation) and bishops-only positions on a single colour complex, and **excludes** KNN-K, KBN-K, opposite-colour bishops, KB-KN, KN-KN and anything with pawns. The legal bishop-versus-knight checkmate `kn6/1B6/1K6/8/8/8/8/8 b` is still scored as mate.
3. **Checkmate outranks the fifty-move rule**, and a genuine fifty-move draw and a stalemate on the hundredth halfmove both still return the draw utility.
4. **Repetition detection is one-directional at the index level.** Over **576,852** enumerated `(ply, halfmove, history length, match distance)` configurations, the C2 index finds real repetitions the baseline missed in 1.5% of cases and **invents one in zero cases**.
4b. **Draw claims and search heuristics are distinct.** `repetition_kind` returns 1 for an in-tree cycle (a named heuristic), 2 for a genuine third occurrence (a real claim) and 0 otherwise. Every repetition case is checked against an **independent python-chess occurrence count**, and the engine's verdict now agrees with the referee about which line is actually a draw.
4c. **Terminals hold at the deepest nodes.** At ply 127 the baseline decides dead material, stalemate and checkmate by evaluation in both entry points; the candidate decides them by rule, while an ordinary position there still returns an evaluation.
5. **The legality probe leaves no trace** — board, move lists, undo stack and accumulator are exactly as found. This is asserted by a test that failed on my first implementation.
6. **Move generation is sound**: perft matches python-chess on ten positions including en-passant pins, promotions and castling, and on 623 positions from seeded random games.
7. **State and NNUE invariants hold**: make/unmake restores every array over ~26,000 moves; the incremental Zobrist key equals a full recompute every time; the incremental accumulator and evaluation equal a full refresh over 26,492 moves across quiet, capture, promotion, castling and en-passant classes; the largest accumulator magnitude observed is 3,485 against an `int16` limit of 32,767; a search aborted mid-tree at three node caps restores the board and root accumulator. **All eight output buckets are covered**, including **206 captures that cross a bucket boundary**, every one consistent.
8. **The wrapper is sound under failure**: a missing network degrades to the handcrafted evaluation with `nnue=off`; a truncated network fails fast with an explicit `BUILD FAILED`; an engine exception and an illegal candidate each recover to a legal move with telemetry. **All five scenarios keep stdout clean and return legal moves.**
9. **Cold initialisation is 24.1 s of the 90 s budget** at the production `COMPILE_JOIN_S = 75`, with no `BINI_JOIN_S` override.
10. **The archive is the artefact that was tested** — all ten members hash identically to the build the timed gate played on the box.

## 3. What remains imperfect — the honest list

* **The engine is not strong enough to see some five-pawn tactics.** Round 100's `Rfa1` lost 523 cp by Stockfish's depth-26 reckoning; our engine cannot separate it from the best move at *any* depth from 10 to 23, and evaluates the position after it at −17 where the truth is −559. No patch here addresses that. It is the single largest known gap and it is a strength ceiling, not a defect.
* **C4 is unresolved.** A bad stored score can still move pruning, aspiration windows and thinking time even when the root move is unchanged. I refuted my own hypothesis about it and did **not** build the adversarial-history matrix that would settle it. No failing test currently points at it.
* **The second-occurrence rule is a search heuristic, not the FIDE claim rule.** Unchanged from the baseline, but C2 makes it fire in cases it previously missed.
* **The book key omits en passant** and genuinely aliases; demonstrated, unfixed by choice. The legality check bounds the damage to a suboptimal move, never an illegal one.
* **85.3% of book entries carry metadata copied from their root** — `depth` and `score` are their parent's. Provenance only; the book still measured better than any rebuild.
* **The EP hash over-distinguishes**, splitting one position across two table entries when a pinned en-passant capture is impossible. Wasteful, not wrong: no key aliasing was found across 3,562 positions.
* **`endgame_scale` remains a heuristic** whose docstring asserts more than it can prove. Left alone on purpose.
* **At ply 127 the pre-existing `MAX_PLY` guard returns a raw evaluation before the terminal block.** The search is over at that depth regardless.
* **The speed cost is real** — about 1%, measured, with a precision of a few percent on hardware that drifts 9% on identical work.
* **A 400-game gate cannot resolve better than roughly ±14 Elo** at an 82% draw rate. Two gates pooled reach roughly ±10. Nothing here can demonstrate a 1–2 Elo effect either way, and I will not claim one.

## 4. Timed regression

**PENDING — filled in from the completed gate.**

## 5. Recommendation

**PENDING.**

## 6. Rollback

`bini_v8_ship/` and `submission_v8_0910_0313.zip` are untouched and verified this session (SHA-256 `47ace193…`, 14,042,168 bytes, ten files). Rolling back is uploading that archive; nothing else needs undoing, and no candidate directory has ever overwritten it.
