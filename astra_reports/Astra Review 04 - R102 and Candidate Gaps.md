# Astra Review 04 — R102 and candidate review

Independent review of the downloaded R102 game and Claude Reports 01–03, source diffs, tests and arena. Written 10 September 2026. This is a **review and implementation follow-up**, not a claim that Astra reran Claude's engine tests or independently confirmed remote gate results.

## Decision

The C1/C2 work is meaningful progress, but **the current candidate is not yet established to meet the terminal-consistency claims in its reports**. Keep its completed test evidence; close the specific gaps below, then repackage and validate the new exact build. Do not discard the work or restart unrelated tuning.

R102 was played by the unchanged active V8. Its draw does not test the candidate. The downloaded PGN names Gijs Smit; the local `intel/raw/targets.json` and leaderboard map that team to **Patzer 2.4**, matching the owner’s description. The earlier R97 victory was also Black against that team, but from a different start FEN. They are not a controlled win-to-draw regression comparison.

## 1. What R102 actually shows

Files: `/Users/architbhardwaj/Downloads/aichessathon-round-102-gijs-smit.log` and `aichessathon-round-102-gijs-smit-vs-opus-carlsen.pgn`.

* Sicilian Dragon, Black starts at fullmove 6. **Log decision m1 = PGN 6...**, so add five when mapping Black's log counter to the PGN fullmove. Do not confuse m117 with PGN move 117.
* Initialization: **37.2 seconds** within a 90-second allowance.
* Five book decisions, taking the clock to about **122.5 seconds**. First fresh search: PGN **11...Bd7**, −39 cp. Subsequent fresh scores reach −98 cp at PGN 29...Rb2. These are Black-relative engine estimates, not independent proof of objective disadvantage or book error.
* Logged local decisions m1–32: fresh scores range **−98 to −32**, median reported depth 20. At m33–60, retained scores range **−49 to −20**, median depth 22. At m61–116, retained scores range **−20 to +28**, median depth 20.
* Late clock allocation is stable: 119 decisions complete with **9.6 seconds remaining**. Near the end it spends about the increment per move. This game does not support a claim that its late search collapsed for lack of time.
* The raw log explicitly contains **`[845 bytes dropped]`**. Do not claim a complete per-move evaluation trajectory. The PGN gives the complete played line, while a segment of search telemetry is unavailable.
* A persistent −20 often represents the configured draw utility, not exactly a 20-centipawn material disadvantage. Avoid treating small utility oscillations as objective changes in winning chances.

The result is consistent with reaching and maintaining a draw after an initially less comfortable position. It does **not** establish that Black had no winning alternative anywhere; that requires independent analysis. It also does not demonstrate a thrown-away large advantage from the recorded evaluations.

### The actionable endgame inconsistency

At PGN **122...Rxg2**, log m117, V8 reports **+57 cp** at depth 25. At **123...g4**, m118, it reports **+54 cp** at depth 22. The game then plays 124.fxg4+ Kxg4 and reaches bare kings, with the final log returning −20.

The positions before those moves are:

* Before 122...Rxg2: `8/8/8/6pk/8/5P2/3r2R1/5K2 b - - 88 122`.
* Before 123...g4: `8/8/8/6pk/8/5P2/6K1/8 b - - 0 123`.
* Before 124...Kxg4: `8/8/8/7k/6P1/8/6K1/8 b - - 0 124`.

**Task R102-A:** replay these positions with actual history on V8 and the corrected candidate. Show root move, terminal continuation, score and completed depth. Confirm whether the +54/+57 becomes the consistent draw utility. This tests whether C1 reaches real ancestors of a dead ending, not only isolated KB–K positions.

**Task R102-B:** independently assess the rook exchange and alternatives, using a suitable exact endgame oracle for supported positions or deeper independent searches. If all continuations draw, call this false numerical optimism, not a lost win. The final bare-king result alone cannot prove the earlier exchange was wrong.

**Task R102-C:** independently grade the first book exit and selected transitions around PGN 11–29, 38–41, 65–78. Compare the best alternative to the played move under matched analysis conditions. Do not conclude “book caused the draw” from the first negative in-house score.

R101's win and initialization are available in the owner’s dashboard excerpt, but I did not find a matching R101 download in the inspected Downloads files. Do not present it as an independently analyzed game. If already available elsewhere, include its exact source.

## 2. What Claude has done well

* Kept the incumbent untouched and isolated C2 from C1+C2.
* Reproduced the original defects and retained machine-readable evidence.
* Replaced the unsound one-minor-each rule with a conservative material predicate.
* Added a dedicated legal-probe scratch area and addressed its initially discovered state-restoration problem.
* Added board, accumulator, TT and abort regression tests instead of testing only the original FENs.
* Reported independent Mac and x86 runs rather than treating them as interchangeable.
* Kept net, book and time-management changes outside the correctness patch.
* Acknowledged that R100’s tactical failure remains outside the fixes.

These are substantial positives. However, passing the tests written so far does not establish that the test matrix is complete.

## 3. Required C1 corrections / adversarial tests

### C1-R1 — Main-search stalemate remains exposed to TT and pruning

In the current `bini_astra_correctness/bini_search.py::search`, dead material and some draw counters are checked early, but **stalemate is not checked before TT cutoffs or reverse-futility/null pruning**. The eventual `legal == 0` check is too late for an early return. The new stalemate helper is used in quiescence, not to protect all main-search paths.

Test the original stalemate FEN at non-root depth 1 and greater:

`k7/8/1QK5/8/8/8/8/8 b - - 0 1`

Use full and null windows, an empty table, and a deliberately wrong exact TT entry. Also select a narrow window low enough that reverse-futility would otherwise return the static evaluation. Demonstrate the rule result before any heuristic exit. Fix the general path, while measuring the cost of any legal-move probing.

### C1-R2 — Recognized mate still falls through to TT instead of returning mate

At halfmove 100, both search functions recognize `in_check && !has_legal_move` but deliberately fall through rather than immediately returning `-MATE + ply`. A TT score can still be accepted on the way to the eventual no-legal-moves block; main-search cutoff depends on the window, while quiescence accepts an exact entry even in a full window.

Extend the mate-boundary test with poisoned TT and narrow/full windows in both entry points. Return the established mate result directly once mate is known. Check ordinary mate below halfmove 100 as well; do not claim universal terminal-before-TT semantics while ordinary mates remain untested.

### C1-R3 — Quiescence repetition omission is justified by an invalid proof

Report 02 says only captures/promotions and at most one quiet-check ply occur, making repetition impossible. **The code generates all evasions whenever `in_chk` is true, independent of `qdepth`. Quiet evasions can give a countercheck, allowing further quiet evasions.** A legal quiet checking continuation can also revisit a position in pre-existing game history; it need not build a whole cycle after the quiescence root.

Withdraw the impossibility claim. Construct a legal countercheck/evasion history test, and a case where the qsearch continuation repeats a pre-root game position. Test supported feature settings separately: default quiet checks are off in the frozen driver, but enabled tests or future feature configurations must not invalidate semantic claims. A capture cannot restore pre-capture material; use valid histories when designing the tests.

Decide how quiescence accesses repetition history and null boundaries, then implement or explicitly document the remaining approximation. Do not add an untested signature change and call the package final.

### C1-R4 — Maximum-ply exits bypass the claimed terminal guarantee

Quiescence returns `evaluate()` at `MAX_PLY-1` before its new terminal block. Main search also has a maximum-ply evaluation fallback before its final legality/mate checks. Add boundary tests with legal array indices and exact terminal positions. Preserve a recursion limit, but report and repair terminal precedence at the limit rather than silently treating a finished game as static evaluation.

### C2-R1 — Limit the monotonicity claim

Report 03's “C2 cannot invent a draw” is stronger than its evidence. An enumeration of transcribed index algorithms over configurations is useful, but is not a proof about full engine behavior, null boundaries and the retained second-occurrence heuristic. Correct indexing can trigger that heuristic more often without creating a legally claimable draw.

State precisely what the enumeration tested and supplement it with real legal histories. Preserve the valid conclusion—one indexing class was repaired—without promoting it into proof of exact draw adjudication.

## 4. The repaired arena still needs repairs

I inspected `astra_tests/arena_astra.py` and `analyse_gate.py`; these are source findings, not a claim that the running remote gate is contaminated.

1. **Full logs are not retained:** `one_game` stores only the final 2,500 characters for each arm. Scanning may occur on full in-memory stderr, but the report's promise of retained complete evidence is false. Write full logs as artifacts.
2. **Fallback is not directly counted:** the summary labels `still_compiling` counts as fallback. `BINI_FORCE_FALLBACK=1` can coexist with a successful `nnue=on` startup, yet the current scanner does not detect that mode. Add explicit per-move mode accounting or equivalent verified coverage; include forced-fallback injection as an arena test.
3. **Singles are included:** `pentanomial()` mixes incomplete pairs into the estimate. If one contaminated game is rejected, its partner survives and can affect the result. Reject the gate for release assessment or use complete valid pairs under a predeclared treatment; never silently call a mixed estimate a complete-pair gate.
4. **Pooling is by run/pair, not start position:** `analyse_gate.py` groups by `(run,pair_id)`. Two 200-opening lanes drawn from a 288-opening pool necessarily overlap by at least 112 openings. A changed offset does not establish independent fresh starts. Report overlap and cluster repeated start FENs appropriately when pooling.
5. **The claimed legacy confidence bounds are not established:** draw-aware independent-game intervals are not guaranteed upper bounds on paired uncertainty. Positive covariance can widen, negative covariance can narrow it. Without pair information, “book is significantly worse” is assumption-dependent. The negative point estimate supports caution, but do not present its significance as settled.
6. **Partial results are printed:** the arena starts emitting estimates after two pairs and every ten completed games. That is not “no partial reading possible.” Preserve predeclared stopping decisions; do not claim the software prevented peeking.
7. **Flag attribution is incomplete:** output reports total flags, whereas acceptance calls for comparing candidate versus baseline flag rates. Attribute the flagged side; distinguish infrastructure conditions from genuine time-management failures under a declared rule.
8. `BAD_STDERR` includes `book ignored`, but the tuple is unused by classification. Ensure the claimed diagnostic policy is actually implemented and tested.

Do not cancel or overwrite the running gate merely because its source instrument is imperfect. Preserve all attainable artifacts, finish under its declared conditions if appropriate, and describe exactly what conclusions remain available. Any code changes create a new candidate requiring new validation.

## 5. R100 is not yet a diagnosed neural-network failure

The new sweeps are valuable: Rfa1 appears even with a cold TT, so stale context is **not necessary** to produce it. That weakens the context-only hypothesis. It does not prove context played no role in the original game, and it does not isolate the network from selective pruning or draw handling.

A **searched score at depth 18 is not a raw neural evaluation**. Before declaring a network blind spot:

* Retain the independent judge's exact refutation PV and search conditions, and verify the claimed −559 score at greater effort.
* Force the critical opposing reply in BINI and inspect the continuation where its assessment diverges.
* Compare raw NNUE, corrected evaluation, qsearch and full search at the key nodes.
* Disable individual relevant pruning features only as targeted diagnostics, not a release sweep.
* Trace draw returns along the bad line—many sweep scores land exactly on contempt's −20 utility, which is a clue worth testing, not proof of the cause.

Correct the table/report discrepancies: `r100_depth_sweep.json` lists **f1a1 at depth 19**, while Report 02 lists Qb2. `r100_after_sweep.json` gives the Qb2 child a White-relative **+6** at depth 18, while the prose says −3. Small transcription errors do not invalidate the entire experiment but must not drive causal conclusions.

## 6. Reporting accuracy and remaining coverage

* Frozen `bini_engine.py` defaults **QS_CHECKS=0, IMPROVING=0, CALIB=0**. Report 01 says QS_CHECKS=1 and IMPROVING=1. Report source defaults separately from runtime environment overrides and prove which values each test used.
* The range of NNUE buckets tested is **5–7**, not all eight. Add small-material cases for buckets 0–4, precisely where current endgame concerns concentrate. This is missing coverage, not evidence of a known arithmetic defect.
* The code accepting pseudo-legal pinned EP generally distinguishes positions that have the **same** legal options; the report describes that as merging positions with different options. Correct that direction. The book's omission of legal EP is a separate merging/aliasing problem.
* Replace manually guessed report times with recorded timestamps. Some report “written/predeclared” times are ahead of their observed local file timestamps and the current snapshot. Establish sequencing from command logs; do not infer misconduct or claim predeclaration from prose alone.

## Next report requested

Produce **Astra Report 04 — Review Corrections and R102 Replay** with:

1. C1-R1 through R4: failing-before/passing-after or a concrete reason a suspected path is unreachable, supported by tests.
2. R102 replay and independent verdict on whether a win was available at liquidation.
3. Repaired arena evidence, manifest overlap and corrected statistical language.
4. Corrected runtime manifest and R100 tables.
5. New candidate hash if code changes; current gate status described only from completed evidence, with no unvalidated readiness claim.

A bounded C4 diagnostic remains worthwhile; a speculative TT redesign remains out of scope. Correctness comes first, and precise claims are part of that correctness.
