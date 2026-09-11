# Astra Directives

**Execution brief for Claude — AI Chessathon / BINI Alpha / Opus Carlsen**

Issued 10 September 2026. Roster lock supplied by the owner: **11 September 2026, 11:00 Europe/London**. Recalculate time remaining when you start; do not assume the original brief's “19 hours” is still accurate.

## 1. Your role and the actual objective

You are the implementation and testing agent. Astra is the independent reviewer and coordinator. **Write the exact code, run the tests, retain the evidence, and report back for review.** This document is the work order; the owner will relay your report to Astra for the next directions.

The owner's clarification is decisive:

> “The main concern here isn't ELO gain — it's to have a perfect chess engine without any flaws or inconsistencies … the engine isn't performing to its best caliber.”

Therefore:

1. Prioritize **chess-rule correctness, coherent state, consistent evaluation semantics, and faithful testing**.
2. A reproduced correctness defect deserves a repair even if a short match measures zero Elo gain.
3. Elo and timed games are regression instruments. They are not the definition of correctness.
4. Do not promise perfect optimal chess or claim that a finite test suite proves the absence of all bugs. Translate “perfect” into explicit, tested invariants and an honest list of remaining limitations.
5. Preserve the incumbent package until the replacement is validated. Implement changes in an isolated candidate. **This brief authorizes implementation, local/available development testing and preparation of a reviewable package; it does not authorize a platform upload or replacement of the live build.**

Do not merely offer a plan or wait for permission on routine reversible implementation choices. Execute the authorized work. Do not retrain the network, change contempt, sweep search parameters, rebuild the whole book, or perform broad optimization as a substitute for fixing correctness.

## 2. Establish the exact baseline

Workspace: `/Users/architbhardwaj/Desktop/AI Chessathon`.

Frozen baseline:

* Source: `bini_v8_ship/`.
* Archive: `submission_v8_0910_0313.zip`.
* SHA-256: `47ace1930f8119473b49524e30652f0ae7c798e8cdad601bac07e6adebee8449`.
* Unpacked size: 14,042,168 bytes, ten archive files.
* Active dashboard version: v10, uploaded 10 September at 09:42; digest prefix matches this archive.

Astra compared the archive files with this source directory and found them identical. Recheck hashes before you change anything; other work may be in progress. The workspace already has many unrelated modified and untracked files. Do not reset, clean, overwrite, kill or incorporate those changes indiscriminately.

Create a clearly named isolated candidate such as `bini_astra_correctness/` from the verified archive or verified source. If using Git, obey applicable repository instructions and use a `codex/` branch unless directed otherwise. Do not alter `bini_v8_ship`, the incumbent zip, or an existing candidate another process may be testing.

Read applicable `AGENTS.md` before working in its scope. The starter has `aichessathon-starter/AGENTS.md`; do not edit the official harness merely to make a failing test pass. Put additional audit/test tooling outside the official harness where possible.

Existing review evidence:

* `external_review_20260910/ENGINEERING_REVIEW.md` — detailed independent audit. **This directives file takes precedence where it updates priorities or workflow.**
* `external_review_20260910/probe_correctness.py` and `correctness_results.json` — successful direct probes of the unmodified frozen engine.
* `external_review_20260910/log_inventory.json` — downloaded rounds 87–100.
* `external_review_20260910/stockfish_triage.json` and `grade_games.log` — completed independent triage saved before the analysis was stopped for this handoff. Inspect actual coverage; do not imply all requested rounds were completed. These are finite-node estimates, not exact outcomes.
* `external_review_20260910/paired_gate_stats.py` — starting point for completed-PGN statistical reanalysis, not a substitute for testing the harness or retaining both engines' full logs.

The original probes used `/tmp/chess-external-review-venv/bin/python`, with Python 3.13 and installed dependencies; an existing project environment also exists at `aichessathon-starter/.venv/bin/python`. Neither is evidence of deployment-version equivalence. Record actual Python, numpy, numba, LLVM, python-chess, OS and CPU for every environment used. Keep x86 deployment validation separate from Mac results.

Emit a baseline manifest with every relevant file hash, net architecture/dtype, and effective feature settings. Source defaults show `draw_behind=1` and ProbCut off; these differ from parts of the narrative. Reconcile source, runtime and previously tested variants rather than trusting prose descriptions.

## 3. First checkpoint: reproduce before repairing

Produce `Astra Report 01 - Baseline and Reproductions.md`. Do not wait for this checkpoint to be relayed before starting the clearly specified isolated fixes below.

Reproduce these exact cases against V8, then run the corresponding generalized tests against your candidate. Tests should call the real search paths, not only a duplicate predicate in a test file.

### A. Stalemate at the quiescence frontier

FEN: `k7/8/1QK5/8/8/8/8/8 b - - 0 1`.

Python-chess says stalemate. V8's direct `qsearch` returns **−1719 cp**. Location: `bini_search.py::qsearch`, around line 451 in the frozen source.

Cause established from source: stand pat and capture-only search can return an evaluation without establishing that a legal move exists. Main search's later legal-move check does not cover all quiescence frontiers.

### B. Checkmate at the fifty-move boundary

FEN: `7k/6Q1/5K2/8/8/8/8/8 b - - 100 1`.

At non-root search ply 1, python-chess says checkmate. V8 returns **−20** (draw utility), instead of the negative mate score with correct ply normalization. Location: `bini_search.py::search`, around line 595.

Cause: the halfmove draw return precedes checkmate detection. Test the real parent-move transition as well as the direct non-root unit case.

### C. Missed repetition at an even-ply history boundary

Start from the initial position. Store the initial position and the position after `g1f3` as pre-root history. Root position is after `g1f3 g8f6`. In search, play `f3g1 f6g8`.

At search ply 2 and halfmove clock 4, the current position equals the initial position. V8's `is_repetition` returns **False**, despite its own documented policy of recognizing any previous occurrence.

Cause: the search-path loop checks the root, then the history loop checks the root again, advancing the distance counter twice and skipping the valid boundary occurrence.

This example is a **second occurrence**, not a legal threefold claim. Keep those concepts distinct: first fix the indexing error; separately define legal claimability versus the engine's search-cycle heuristic.

### D. The existing insufficient-material candidate is not an exact repair

Inspect `bini_v85_insuf/bini_eval.py`. It treats one minor on each side as categorically drawn and returns zero from static evaluation.

Counterexample FEN: `kn6/1B6/1K6/8/8/8/8/8 b - - 0 1`.

This is a **valid checkmate with bishop versus knight**, confirmed by python-chess. It disproves the categorical material claim. It does not mean the current eval-only candidate necessarily fails to detect that mate in every main-search call.

The candidate is also insufficient as a zero guarantee: `corrected()` can add **+64 cp to static zero**, reproduced with two saturated correction entries. TT returns can bypass evaluation as well.

**Do not copy this candidate's `(wm == 1 and bm == 1)` condition into a terminal recognizer.**

## 4. Implementation work packages

Keep patches small and reviewable. Give each one a unique ID. Record dependencies so the final combined candidate is not confused with independently tested parts.

### C1 — Centralize exact terminal semantics

Implement a consistent terminal policy shared by main search and quiescence. Do not equate a draw with a neural evaluation that happens to equal zero.

Required behavior:

* Checkmate takes precedence when applicable; return normalized mate scores.
* Stalemate returns the configured terminal draw utility.
* Exact dead-material recognition happens before TT score cutoffs, correction history and pruning can supply a nonterminal value.
* Quiescence's recursive nodes receive the necessary rule/history treatment; protection only at the first main-search-to-qsearch call is insufficient.
* A terminal score is not modified by correction history.
* The same terminal draw has consistent utility through every path. Preserve the established contempt policy unless a separately reviewed design requires changing it; chess truth and root-relative utility are distinct.

Conservative material cases to support, matching the referee's python-chess semantics:

* K–K.
* KB–K and KN–K, either orientation.
* Bishops-only positions in which **all bishops are on the same square-colour complex**, including promotions, with no pawns, knights, rooks or queens.

Negative cases must include KNN–K, KBN–K, opposite-colour bishops, KB–KN, KN–KN, and winnable material with pawns. Some individual positions in these classes may be drawn, but material counts alone do not certify that.

Keep `endgame_scale`'s heuristic scaling distinct from exact terminal recognition. Its existing claim about pawnless material is not a theorem. Do not change every pawnless evaluation as part of the exact-rule patch.

Stalemate handling must be correct before a stand-pat cutoff, not merely after finding no captures. “No legal captures” does not mean “no legal moves.” Design a fast legal-existence check in native/JIT code. Measure its cost, but do not knowingly preserve incorrect terminal semantics to obtain a favorable benchmark. Ensure legal-existence probes restore all state and do not clobber the current move list or accumulator.

Before implementing claim-related behavior, inspect the referee: the local one uses `board.outcome(claim_draw=True)`. That can recognize claims available through an intended next move. Literal platform adjudication and ordinary optional FIDE claims are not automatically interchangeable. Write tests for the actual platform convention, confirm the deployed rules if available, and document the policy you implement.

### C2 — Repair repetition indexing and history boundaries

Use an explicit distance model: same-side ancestor distances 2, 4, 6… mapped to undo history or pre-root game history, never counting the root twice. Stop correctly at irreversible and synthetic-null boundaries.

Test:

* Both search-ply parities, including 1, 2, 3, 4 and deeper cases.
* Matches exactly at the halfmove boundary and just beyond it.
* Empty, short, and dynamically extended histories.
* Root exclusion and first/second/third occurrence semantics.
* Cycles fully in the tree, fully in actual game history, and straddling the root.
* Pawn moves, captures, castling-right changes and en-passant rights.
* Histories reconstructed through `GameState.update` and `record_reply`, including forced moves and book moves.

Do not silently turn all second occurrences in game history into literal threefold draws. If a search-cycle approximation is retained, name it and test it separately from exact adjudication. Report what remains heuristic.

### C3 — Null-move and position-identity audit

These are source-level risks requiring concrete tests, not yet demonstrated explanations of losses.

`make_null` increments the halfmove clock and adds a synthetic ancestor. Introduce or verify sufficient null-boundary bookkeeping so a synthetic pass cannot manufacture a real-game repetition or fifty-move claim. Test null verification, nested search, aborts and exact undo restoration.

EP hashing currently accepts a potential pawn capture without checking whether it is legal under a pin. Test FENs with pinned EP and compare legal-position identity with python-chess. Book keys omit EP entirely; two positions can share a book key while offering different legal options. Legal checking of the chosen move alone does not solve this strategic aliasing.

Fix narrowly when a failing test demonstrates the defect. Keep book-format migration separate from search history/hash migration and test compatibility deliberately; do not strand existing entries silently.

### C4 — TT context correctness: diagnose, then make a bounded repair

Do not dismiss this because one root move was unchanged. A bad score can alter pruning, aspiration windows, and thinking time even with the same final move.

Do not assume every warm/cold score difference is a bug either. Match history, depth/nodes, correction arrays, move histories, draw policy and completed-iteration status. Warm and cold tests at different achieved depths do not isolate the cause.

Build a diagnostic matrix:

* Same board, differing legal game histories.
* Same board, halfmove counters near a claim boundary.
* Same board and history, fixed versus changed draw utility.
* Empty TT, warm TT, TT move-order-only, and normal TT bounds.
* Main search versus quiescence; full window versus null window.

Record bound type, stored/search depth, mate normalization, PV, root move, completed score and any change to allocated time. Show a concrete invalid reuse before selecting a fix.

Terminal-before-TT checks are necessary but do not solve every ancestor-bound history dependence. Clearing once per root is not a complete within-tree solution. Propagating a “draw seen” flag is not automatically a proof that all stored bounds are context independent. Evaluate the actual proposed solution against adversarial histories; document residual approximation rather than claiming a general graph-history solution without proof.

Use a slow, conservative reference mode for tests if needed. Do not make a sweeping TT redesign part of C1/C2. If C4 cannot be validated before lock, report it separately with exact reproductions and a post-lock repair plan.

## 5. Generalized regression suite

The four original positions are necessary but not sufficient. Add meaningful tests that exercise behavior, including negative cases and state corruption. Reuse sound existing tests rather than duplicating them.

### Board and state

* Differential legal move sets/perft against python-chess on curated tactical positions and seeded random legal games.
* Bitboards, piece array, side, castling/EP rights, reversible counter and Zobrist key match after make/unmake.
* Illegal make attempts leave the required caller state intact.
* Promotion/underpromotion, castling through check, EP exposing check, captures of rooks affecting rights, checks and double checks.
* Null make/unmake and abort at different recursion depths restore the root exactly.

### NNUE

* Incremental accumulators equal full refresh elementwise after every supported move class; test both perspectives and every output-bucket transition reached by captures/promotions.
* Side-to-move score orientation and accumulator restoration are correct.
* Verify range safety and integer arithmetic. The frozen net is 1024 wide with eight output buckets, int16 accumulators, and the observed bound is 16,355. Recompute rather than relying on this number if weights change.
* Confirm no missing/failed weights silently downgrade a nominal NNUE test to handcrafted evaluation.

### Search and TT

* Terminal recognition under empty and poisoned TT/correction history.
* Mate normalization across different plies; TT packing/unpacking and collision/replacement behavior.
* Exact/lower/upper-bound handling, aspiration fail-high/fail-low, excluded-move searches and aborted iterations.
* Compare tractable searches with an unpruned reference configuration. Do not claim aggressive selective search generally produces mathematically exact minimax values.
* Use state-preserving deterministic tests for correctness; use controlled timed tests for speed and wrapper behavior. They answer different questions.

### Wrapper and reliability

* Actual `get_move` with FEN history, book moves, forced moves, low budgets and repeated calls.
* Default 90-second production initialization, cold process/cache conditions, declared dependency versions.
* Simulated build failure, weights failure, illegal candidate and engine exceptions: legal recovery when time permits, with explicit mode/error telemetry.
* Protocol stdout remains clean. Log diagnostics to stderr.
* Verify returned move legality, clock overhead, and no background work contrary to suspension assumptions.

Report counts, seeds, commands and all failures. “Tests pass” without scope and evidence is not an acceptable report.

## 6. Repair the test instrument before trusting game results

This is infrastructure work in parallel with the engine corrections, if available resources permit. Do not rewrite the official competition referee's rules.

Confirmed local `arena_par.py` problems:

1. `void` counts as a draw.
2. Opponent crashes/init failures can count as wins without invalidating the gate.
3. Only the candidate's stderr is checked; the opponent can silently degrade.
4. Searching for the word “fallback” does not prove zero fallback moves or NNUE-on. A “still compiling” warning also does not prove that any fallback move was actually played.
5. `--seed` changes scheduling order but not opening selection. A 400-game gate always uses the first 200 FENs from its input.
6. The inspected curated input has 288 FENs, distinct from the larger 1,226-position book corpus. Verify remote files and manifests.
7. Elo intervals use Bernoulli variance despite draws. At 84% draws and approximately 50% score, the illustrative independent-game interval is about ±13.6 Elo at 400 games, not ±34.2. Actual pair/cluster covariance must be measured; do not replace one misleading number with another.
8. The local stable/weak launch scripts omit `--pgn-out`, which prevents proper pair-level reanalysis unless other records retain the games.

Required changes:

* Save complete logs and engine-mode/NNUE status for **both** arms.
* Reject contaminated games/gates; never silently award them normal chess scores or selectively discard unfavorable outcomes.
* Save unique game/pair/opening IDs, full PGNs, actual start FENs, build/net/book hashes and test configuration.
* Preselect a reproducible representative opening manifest, with both colours. Vary the manifest, not just scheduling, for fresh confirmation.
* Analyze W/D/L score variance by complete colour pair or opening cluster. Repeated pairs from the same start remain clustered. Retain same-opponent matched differences for two-arm comparisons.
* Keep production cold-init validation separate from relaxed local testing. `BINI_JOIN_S=300` does not override the official 90-second init budget and must not leak into release expectations.
* Audit both cores and memory bandwidth before concurrent lanes; 384 logical threads does not prove that 384 concurrent games are uncontended.

Do not reinterpret unfinished gates. Complete samples first. Do not relabel a null result as either proof of perfection or proof of a fundamental ceiling.

## 7. Book and game-quality work: second priority

Correct the source of claims before changing playing behavior.

The old book being built by a different net is **provenance**, not proof that it is inferior. New-net disagreement is not a blunder rate. More coverage is not automatically better play.

The inspected historical builder reads a PV from mutable TT entries and copies the root's score/depth onto every child entry. It can replace a mismatched first PV move while retaining the suffix, stopping only when a move becomes illegal. Audit the actual rebuild script for these behaviors. Legal moves are not a certificate of a completed principal variation.

Specify and test:

* Legal move for the exact keyed position, including EP state.
* Honest score perspective and depth provenance for each entry.
* No claim that a PV child received an independent 60-second search unless it did.
* Completed-search PV extraction or independent child reanalysis when needed.
* No stale entries retained silently through a resumed/reused output file.
* Explicit treatment of repeated/transposed positions and conflicting analyses.

Do not ship a wholesale rebuild to correct metadata. Repair the pipeline, then independently judge meaningful old/new disagreements. A small, independently verified entry deletion/replacement can become a separate candidate. Gate any playing changes separately.

For game explanations, identify the **first independently supported mistake and the available better continuation**, not the last large eval collapse. A smooth self-evaluation trajectory does not prove that there was no blunder.

Important facts from the downloaded logs:

* R99 and R100 used zero book moves.
* R99's final Bxg7 occurs after White has already lost its last pawn; the preceding material is bishop versus knight. This alone does not establish a sacrificed win. Investigate earlier decisions and actual alternatives.
* No fallback/illegal/engine-error markers were found in the inspected R87–R100 logs, but that is bounded evidence, not a lifetime reliability guarantee.
* R98's late shallow search can be a consequence of an already poor position. Time reserve changes require testing the entire earlier/later allocation tradeoff.

Use independent deeper analysis or exact small-endgame oracles when available to distinguish objective evaluation error, search/pruning miss and an unavoidable result. The frozen engine's own +150 cannot certify a win when evaluation is the suspected defect.

## 8. Deadline order and release boundaries

Execute in this order, adapting clock times to actual remaining time:

1. Baseline manifest and failing reproductions.
2. C1 terminal correctness and C2 repetition indexing, separate patches/tests.
3. Generalized state/NNUE/search regression checks and harness integrity repairs.
4. C3/C4 bounded reproductions and repairs where justified; do not hide unfinished work inside the C1/C2 release.
5. Exact combined candidate wrapper tests, cold-init and controlled timed regression games.
6. Final report and reviewable archive, while preserving rollback.

Aim to have the release candidate fixed early enough for several hours of final-package validation. Reserve the last two hours before lock for review, platform validation if separately authorized, and rollback. Do not make unvalidated final-hour changes.

For **correctness fixes**, acceptance means:

* Failing-before/passing-after reproducer.
* General invariant suite, including counterexamples, passes.
* No new state/NNUE/protocol/legality failures.
* Behavior is consistent across full search, quiescence, TT and wrapper paths.
* Runtime/initialization cost is measured and material regressions are understood.
* Final combined package is the exact one validated.

A positive Elo result is **not required** to repair a proven rule violation. Conversely, a positive result cannot excuse a remaining rule violation. Timed regressions still matter because an implementation that exhausts the clock or falls back is not a sound repair.

For **heuristic or strategic changes**, such as new book choices or time allocation, correctness tests alone do not establish improvement. Keep them separate and retain the incumbent behavior unless independent quality evidence and representative timed tests justify a change.

Do not claim non-inferiority merely because a confidence interval contains zero. If reporting a margin, predeclare and actually test it. Never infer that identical-width networks have identical speed without measuring dtype, architecture and throughput.

The dashboard text says “2 of 10 uploads in the last 24 hours,” which appears to mean two used, unlike the older brief's “two remaining.” Verify the actual remaining allowance before any separately authorized submission. Do not spend uploads as experiments.

## 9. Required reports back to Astra

Write reports in the workspace root or a clearly named `astra_reports/` directory. Keep a current `Astra Status.md` linking all reports and artifacts. Do not edit this directives file to erase uncompleted requirements or change acceptance criteria after seeing results. Put proposed scope changes in the report.

Report at these natural checkpoints:

* **Report 01 — Baseline and Reproductions:** baseline hashes, environment, reproduced cases, discrepancies from Astra's findings, and exact intended patch boundaries.
* **Report 02 — Correctness Patches:** diffs, failing-before/passing-after evidence, generalized tests, runtime impact, residual issues. C1/C2 can proceed under this brief; propose any large C4 redesign for review before folding it into the release candidate.
* **Report 03 — Integration and Regression:** combined manifest, wrapper/cold-init results, completed game results with proper diagnostics and pair-level statistics, unresolved risks.
* **Final Report — Candidate Decision:** exact archive/hash, included/excluded changes, guarantees established, limitations, and your evidence-based readiness recommendation. Clearly label **READY FOR REVIEW**, **NOT READY**, or **BLOCKED**, not “perfect.”

Use this structure for each defect:

```text
ID and title:
Status: reproduced / fixed / regression-tested / deferred / not reproduced
Original source location and baseline hash:
Minimal reproduction and expected behavior:
Observed baseline behavior:
Root cause (separate evidence from hypothesis):
Patch files and explanation:
Why this fixes the class, not just the example:
Negative/counterexample tests:
Commands, environment, seeds, counts and result artifact paths:
Observed candidate behavior:
Performance/clock/init effect:
Interaction with other patches:
Remaining uncertainty or approximation:
Decision or question for Astra, if one is actually needed:
```

For every game gate report:

```text
Candidate and opponent source/net/book hashes:
Exact command, environment overrides, host and worker/core allocation:
Opening manifest hash, unique openings, colour-pair IDs:
Requested games / completed games / valid games:
Both arms: NNUE-on, fallback moves, init failures, crashes, illegal moves, flags:
W/D/L, mean score, loss rate, paired/cluster uncertainty:
Affected-position exposure and intervention counts:
Full PGN and both-side diagnostic artifact paths:
Whether the result is final and whether selection/retesting affected interpretation:
```

Do not send reports externally or submit the agent through the website. The owner will provide the reports to Astra, who will review the evidence and guide the next iteration.

## 10. Explicit non-goals for this pass

* No net retraining, corpus changes, width changes or new architecture.
* No contempt or aspiration tuning campaign.
* No attempt to “fix draws” by making the engine irrationally reject them.
* No large time-management rewrite based on depth numbers alone.
* No speculative SIMD/GPU/ONNX rewrite. Profile later on the actual x86 target if speed work is needed.
* No conflation of Stockfish's greater strength with proof that Python/numba is the sole cause of every loss.
* No blanket declaration that TT/history is solved because one test passes or one root move is unchanged.
* No shipping an unvalidated combination of individually tested patches.

**Success for this assignment is a reviewable engine with demonstrated corrections to specific flaws, consistent rule/state semantics, a trustworthy regression instrument, and a precise account of what remains imperfect.**

## Follow-up review — after Reports 01–03 and round 102

Read `astra_reports/Astra Review 04 - R102 and Candidate Gaps.md` before declaring the C1/C2 candidate ready. It contains the next concrete work order: close remaining main-search/TT terminal paths, correct the quiescence-repetition argument, test maximum-ply precedence, replay R102's final liquidation, and repair remaining arena/reporting gaps. Preserve existing test evidence and the running gate's artifacts. Implement and test the bounded corrections, then return **Astra Report 04 — Review Corrections and R102 Replay**. No upload is authorized by this follow-up.

## Execution refinement — terminal audit and v4

Astra reviewed the supplied execution transcript introducing C1c/v4. The sequence—host smoke test and correctness audit, followed by gates of frozen builds—is approved as the working approach. Apply these refinements before calling the audit complete:

1. **Make failures stop automation.** The transcript shows a Python assertion followed by `exited with code 0`, because output was piped through `tail`; a completed suite also reported FAIL while exiting zero. Make the test process return nonzero on any FAIL or unexpected SKIP, and preserve its status with `set -o pipefail` or an equivalent checked invocation. Keep full output in a file; tail only for display. Assert required test categories and nonzero case counts before packaging/gating. A successful shell command is currently not evidence of a successful audit.
2. **Assert exact terminal semantics.** For a mated side to move require `-MATE + ply`, not either sign of any mate-range score. For a terminal draw require the configured root-relative draw utility, not `abs(score) <= 25`. Test contempt zero and the shipped nonzero value, both root colours, both side-to-move relationships and odd/even ply. Test parent negation separately. Restore/refresh the accumulator at the selected ply; changing `S_PLY` alone after root setup leaves the wrong accumulator active.
3. **Cover windows and cutoffs explicitly.** Full-window tests do not exercise the main-search non-PV TT return. Include narrow windows that trigger exact/lower/upper TT bounds and reverse-futility on terminal positions, empty/poisoned TT, both correction signs, rule50 boundaries and maximum ply. C1c's `(not in_chk) or has_legal_move(...)` protects mate cutoffs but explicitly still accepts non-check stalemate TT cutoffs in main search. Closing the reported mate failure is not the same as closing all terminal paths. Prefer directly returning mate when a legality probe has established it; if preserving fall-through, demonstrate that every remaining early exit is safe.
4. **Keep quiescence history on the list.** C1c does not address quiet evasions/counterchecks or matches with pre-root history. Complete the bounded repetition tests requested in Review 04. Preserve the distinction between an exact rule claim and an in-tree cycle heuristic; do not describe either as universal proof of the other.
5. **Validate the test corpus instead of weakening its oracle.** Require valid legal positions and correct oracle classifications, and retain a manifest of rejected curated FENs with reasons. Ensure mandatory categories remain represented after rejection. Non-dead material does not imply a nonzero searched score; checking the recognizer is the correct negative test, supplemented by deliberately chosen known continuations for integration. Random full games are a supplement, not efficient coverage of rare material classes. Call this a systematic terminal audit, not exhaustive proof over every possible state.
6. **Keep the repetition A/B genuinely isolated.** Once C1c or another shared correctness repair is added, put that same repair in BOTH comparison builds. Compare final-common-code plus C2b against final-common-code without C2b; v4 versus the existing v3 would differ in C1c as well and could not isolate repetition policy. Verify all file hashes/diffs and use unique immutable build directories. Never update a build in place while a game lane imports it.
7. **Freeze then validate the exact artifacts.** Run corrected deterministic tests and production cold-init/wrapper checks on the new x86 host for both final comparison hashes. Then run complete paired 120+0.5 gates with books enabled, manifest/overlap accounting, full two-arm logs and explicit mode diagnostics. Smoke games of v2 establish infrastructure health, not v4 strength or correctness. Archive members must match the actual tested directories; earlier startup/speed/x86 measurements remain attached to their earlier hashes until repeated.
8. **Make recovery independent of host survival.** Save each completed game's record/log references durably, update summaries atomically, and periodically copy checkpoints off the game host. A local checkpoint cannot survive losing the whole host/disk. Resume only with matching build, harness, environment and opening manifests, stable unique game IDs and no duplicate scoring. Do not selectively replay unfavorable valid games. Freeze the sample/stopping rule before reading results; retain complete pairs for the release estimate.

No broad new tuning or training is requested. Finish these concrete audit gaps, run the minimal two-build repetition comparison and final-package regression, and report precisely which invariants and hashes passed. No platform upload is authorized by this refinement.
