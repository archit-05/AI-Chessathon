# Independent engineering review — BINI Alpha / Opus Carlsen

Review date: 10 September 2026. Decision deadline supplied by the team: 11 September, 11:00 London. At 18:12 London approximately 17 hours 48 minutes remained, rather than the brief's original 19 hours.

## Decision

**Make correctness and consistency the primary objective. Repair proven rule violations and state inconsistencies in an isolated candidate, verify them against explicit invariants, then use timed play as a regression check. Keep the existing validated package as the fallback until the corrected package is validated. Do not replace the book merely because the net changed.**

The owner clarified during this review that Elo gain is not the main objective. That changes the priority: a provable rule violation warrants repair even if it is rare and the measured Elo gain is zero. It does not make an untested repair correct, or turn a heuristic disagreement into a bug. “Perfect” must be decomposed into testable guarantees; perfect optimal chess play cannot be promised by a finite audit or a finite-depth engine.

The supplied narrative confuses three different propositions: a component is logically imperfect; a component changes a move; and changing that move improves the competition result. The first does not establish the third. Conversely, one unchanged root move does not establish that a bug is harmless.

I inspected the frozen engine, candidate insufficient-material change, wrapper, local arena/referee, book builder, and downloaded logs for rounds 87–100. The shipped zip's SHA-256 begins `47ace1930f81`, matching the dashboard's active version. All ten archive files match their local `bini_v8_ship` counterparts, and its unpacked size is 14,042,168 bytes. I did not modify the live engine or submit a build. This is a bounded audit, not proof that every defect has been found. Remote final gate records and the rebuilt book were not available among the local files inspected; I do not claim to have verified their final outcomes.

## 1. Confirmed findings and their practical meaning

### 1.1 The proposed insufficient-material repair is both too broad and too weak

Location: `bini_v85_insuf/bini_eval.py`, added test in `endgame_scale`.

The condition `(wm == 1 and bm == 1)` includes bishop versus knight, knight versus knight, and bishops on opposite-coloured squares. Those material classes are not automatically dead positions. The legal position

`kn6/1B6/1K6/8/8/8/8/8 b - - 0 1`

is **checkmate with bishop versus knight**. Python-chess confirms that it is valid, checkmate, and not insufficient material. This does not mean the current eval-only candidate necessarily returns a draw at that checkmate—main search can still detect mate. It proves that its claimed categorical classification is false and must not be promoted into a terminal rule.

Conversely, returning zero from static evaluation does not establish a draw. The next `corrected()` call can add up to 64 cp; a direct probe returns +64 from a zero static score with saturated positive correction entries. Search can also accept an earlier TT score. Exact draw knowledge belongs in a terminal check before TT bounds, static evaluation, and pruning, with one consistent draw utility. If contempt remains enabled, distinguish chess truth (draw) from search utility (the established draw score); do not let identical drawn outcomes acquire inconsistent scores through different code paths.

Implement the conservative material predicate used by the actual referee: bare kings; one bishop or knight against a bare king; bishops-only positions where every bishop occupies the same colour complex, with no pawns/knights/rooks/queens. Include promoted same-colour bishops. Do not classify KNN–K, KB–KN, KN–KN, or opposite-colour bishop endings as terminal draws. Test the predicate against the installed python-chess version over an enumerated/random legal-position corpus.

The existing pawnless `score // 8` remains a heuristic, not a theorem. Its comment also calls KR–KB drawn, although that material class contains wins. Separate exact recognition from this heuristic and gate any changes to the latter independently.

### 1.2 A repetition-history indexing defect reproduces without TT involvement

Location: `bini_v8_ship/bini_search.py:281`, `is_repetition`.

Reproducer: retain the initial position and the position after Nf3 as game history; set the search root after Nf3 Nf6; search Ng1 Ng8. The current position equals the initial one, four reversible plies earlier. At search ply 2 and halfmove clock 4, `is_repetition()` returns **False**, despite its documented any-prior-occurrence policy.

Cause: the search-path scan checks the root at even ply, then the history scan starts at the root again. The distance counter advances twice for the same position, and the valid history-boundary match is skipped. This is a concrete bookkeeping bug, distinct from the broader graph-history/TT problem.

Fix using one explicit distance convention. Scan same-side ancestors at distances 2, 4, 6… without duplicating the root; map each distance to either an undo-stack key or pre-root history. Test both parities, the exact halfmove boundary, irreversible moves, root exclusion, short history, and reset/new-game behavior.

Important distinction: this reproducer is a second occurrence, not a FIDE threefold claim. It demonstrates failure to implement the engine's own cycle-detection policy. Separately specify search-cycle heuristics versus actual pre-root claimability, matching the platform referee's `claim_draw=True` behavior. Do not replace one ambiguous policy with another.

### 1.3 Quiescence can value a stalemate as a large material loss

Location: `bini_v8_ship/bini_search.py:451`, `qsearch`.

For `k7/8/1QK5/8/8/8/8/8 b - - 0 1`, python-chess reports stalemate. A direct call to V8 quiescence returns **−1719 cp**. It uses stand pat and capture-only generation without establishing the availability of a legal move. Full search's later legal-move check does not protect every frontier/qsearch position.

Quiescence also has no repetition/halfmove/material draw checks of its own. The first call through `search` gets some protection; recursive qsearch calls do not. Checks/evasions allow quiet moves inside quiescence, so it is not sufficient to argue that every qsearch ply resets the reversible-move counter.

Fix terminal semantics across both search entry points. For stalemate, absence of legal captures is not absence of legal moves. A correct approach must establish legal-move existence before accepting a result at a genuinely stalemated node; benchmark that overhead and design a fast legal-existence helper. A single broad unconditional python-chess call inside JIT search is not an acceptable implementation.

### 1.4 Fifty-move checking precedes checkmate

Location: `bini_v8_ship/bini_search.py:595`.

At non-root ply 1, `7k/6Q1/5K2/8/8/8/8/8 b - - 100 1` is checkmate. V8 returns its draw utility **−20**, rather than −29999. The current `halfmove >= 100` return occurs before checking mate. Match the referee's terminal precedence. This edge case is a confirmed correctness defect, not an established explanation for R98/R100.

### 1.5 The arena can hide invalid games and exaggerates uncertainty

Location: `bini_v8_ship/tools/arena_par.py`; the copy under `bini_v65/tools` is identical, and the local launch scripts invoke that copy.

* `elo()` uses `sqrt(p*(1-p)/n)`, treating every score as a binary win/loss. Draw scores are 0.5 and have a different variance. Near 50% score with 84% draws, the independent-game approximation gives roughly **±13.6 Elo** at 400 games, not ±34.2. This is illustrative, not a replacement interval for an unseen gate: use colour-paired/opening-cluster outcomes, because pair covariance and repeated openings matter.
* `--seed` shuffles the already-created jobs. It does not sample different openings. A 400-game gate uses the first 200 input FENs, regardless of seed. The inspected `bini_v65/tools/curated.epd` has 288 FENs, while `/tmp/book_roots.epd` is the larger preparation corpus. Audit which file actually ran on the remote host. More games on the same deterministic pairs do not buy the same information as new openings.
* `void` is counted as a draw. An opponent initialization failure can count as a win and is ignored by the candidate failure exit condition.
* Only our side's stderr is returned and inspected. The opponent can silently run fallback or non-NNUE evaluation. `BUILD FAILED` and NNUE-off are not comprehensively validated. A grep count of “fallback” is not a reliable gate-integrity certificate.
* A “still compiling” message proves a delayed build, not necessarily that a fallback move was played: the wrapper may wait for compilation or play book moves first. Explicit per-move engine-mode counters are required.
* `BINI_JOIN_S=300` is a stress-test accommodation, not a platform-compatible shipping setting. The local referee still defines a 90-second init budget. It does not make 300-second initialization legal. Final package validation must use the production default and a 90-second watchdog.
* Local sandbox processes are not actually suspended between moves. This is mostly immaterial when the engine is idle and ready, but matters for unfinished compilation. Separate realistic cold-init tests from strength lanes with healthy initialization.

Immediate repair: save full stderr and startup metadata for both sides; emit unique opening/pair/run IDs and build/net/book hashes; reject infrastructure-contaminated gates, never score voids; save PGNs; select a fixed, randomized/stratified opening manifest before dispatch; analyze complete opening pairs. The provided `paired_gate_stats.py` computes a cluster-based interval from completed, named-player PGNs and refuses unbalanced/incomplete/failed gates. It still needs independent full-log validation and representative opening sampling.

## 2. Reassessing diagnoses A–D

**A — wrong draw values: confirmed. Missed win in R99: not established by the cited evidence.** R99's final Bxg7 comes after White has already lost its last pawn: the preceding position is KB–KN. Correctly recognizing the final dead position cannot by itself recover a win lost or never present earlier. The critical question is where White last had a genuinely better, maintainable alternative, judged independently. A persistent +150 from the same miscalibrated engine is not evidence that a win existed. Sixty insufficient-material terminations measure endpoint frequency, not sixty missed conversion opportunities.

**B — old book: provenance confirmed; performance defect unproven.** Disagreement with a new net is not a blunder rate. Net improvements are aggregate, not a guarantee of better opening choice in every position. Deeper old analysis can beat shallower new analysis, and both can prefer different approximately equal moves. Coverage adds exposure as well as clock savings. Rebuilding changes move choice, branch exposure, coverage, and potentially search depth; those effects are confounded in a wholesale comparison.

The inspected builder (`bini_v7/tools/make_book.py`) reads PV moves back from mutable TT entries, then assigns the root's depth and score to every entry. Child entries are not independently searched at the advertised depth; their score is not necessarily from their side-to-move perspective. It may also replace a mismatched first PV move while retaining the old suffix, stopping only on illegality. Thus a legal suffix is not a certified final PV. Inspect the actual rebuild implementation for these same issues before trusting “60-second, eight-ply preparation.” If the +22→−46 trajectory was taken from book log metadata, it must be regraded; if independently searched, retain that evidence with its search conditions.

`_book_key()` also omits en-passant availability. Legality validation rejects an illegal stored move, but cannot detect a legal move that is strategically wrong when an en-passant option exists. Include normalized legal EP state in future keys. Rule/history-sensitive positions should not enter a position-only book indiscriminately.

**C — clock decay is real, but the proposed remedy is a resource tradeoff.** More endgame time costs earlier time. The formula is a rolling allocation, not a promise that exactly 18 moves remain. Increment, actual stopping factors, and hard caps make “spends exactly 1/18” incomplete. The counter is our moves since the supplied start FEN, not the PGN fullmove number; it reaches the floor on the 40th local decision, later on the chess scoresheet. Comparing depth numbers across phases is not a controlled quality comparison: extensions, reductions, branching and TT reuse differ. The completed reserve gates give no positive reason to ship. They do not prove universal zero effect or establish a ceiling.

**D — investigate, but do not deploy a broad TT rewrite now.** Warm/cold searches at different achieved depths do not isolate repetition as the unique cause. TT bounds, move ordering, correction history, rule50 context and changing contempt must be separated. The source omits rule50/history from the TT key, and draw utility can change between moves when `draw_behind` fires. Reusing such bounds is a real risk. Wrong scores also influence aspiration, pruning and time allocation even when one recorded root move is unchanged.

Use a fixed-node or fixed-depth diagnostic factorial: same position AND history, same correction/history arrays, same draw policy; vary only TT warm/cold or move-order-only TT; record bounds, complete root scores, PV, node count and allocation decisions. Compare with a repetition bookkeeping fix separately. Clearing the TT is a diagnostic, not a proven strength improvement or complete cure for within-search history dependence. Never claim that testing twenty positions “settles” absence of a bug.

Additional source-level risks to cover in the regression matrix: null moves currently increment the halfmove clock and enter the history chain without an explicit null boundary; EP hashing checks a potential pawn capture rather than fully legal EP, which matters for pinned pawns. These need dedicated reproductions before being attributed to game results.

## 3. Why the plausible repairs return zero

There is no evidence of a fundamental ceiling. There are several more immediate explanations:

1. The supposed causal chain may be false: low clocks often occur after a position is already lost; net disagreement can be harmless; positive engine evaluations can describe drawn endings.
2. The intervention can be incomplete, as with zeroing evaluation before correction rather than recognizing a terminal draw.
3. A fix can trade one source of strength for another: reserve time removes earlier nodes; new book coverage suppresses fresh search; draw recognition can remove chances against fallible opponents while improving objective evaluation.
4. Self-play is a useful safety test but samples few opponent errors and few intended conversion decisions. It is not structurally incapable of seeing a draw fix; the affected decision rate must be measured. Weaker-opponent tests and targeted continuation suites address different questions.
5. The uncertainty calculation and opening population need repair before claims about insufficient power are credible. For game score X in {0, 0.5, 1}, estimate variance from those scores, not a Bernoulli surrogate. For paired starts, use pair means or cluster sums. For two arms against a common opponent, compare matched opening/colour differences directly, preserving covariance.

Do not read the unfinished book/insuf/stable gates as final evidence. Do not interpret “not statistically significant” as “no effect.” Conversely, do not accept “within ±34” as a non-inferiority result. A claim that regression is at most 5 Elo needs a lower confidence bound above −5, not a point estimate near zero.

The same-width weaker net is a sensible control, but width alone does not prove speed identity: accumulator dtype, input king buckets, refresh frequency and search tree shape also matter. Log architecture, dtype and observed throughput for both nets. A fixed-node improvement is an empirical screening signal, not a universal 2–3× conversion law or a mathematical upper bound on timed strength.

## 4. What to do with the rebuilt book

**Retain the old book until a completed, clean direct comparison justifies replacement.** The current −17 at 340/400 is neither a final loss estimate nor proof of noise. Corrected intervals could make a completed negative result more concerning than the printed interval suggests.

After completion, attribute results by opening pair and by actual exposure: unchanged entry; changed covered entry; newly covered root; deeper PV continuation. Save old/new move, actual originating search depth/time, legal EP state, and book-exit board. Have an independent Stockfish judge search both candidate root moves under equal limits and repeat important disagreements deeper. Root-restricted equal-node evaluations are triage, not game-theoretic proof or substitutes for timed matches.

If only a small set of entries shows stable, material harm, make one selective candidate: remove those entries to invoke V8 search, or replace only entries supported by deeper independent judgment and current-engine reanalysis. Avoid mixing a complete rebuild, increased coverage and deeper preparation. Validate on fresh held-out openings, including transpositions into the affected lines. Retain the old book when time is insufficient. Book-off and root-only variants are diagnostics, not automatic recommendations.

No direct Elo claim follows from 100% versus 93.3% coverage. The target metric is match score at the competition clock, with opening loss risk and available clock recorded.

## 5. Engineering schedule to the lock

Times are London time and assume work begins around 18:15 on 10 September. Existing authorized lanes may continue; do not oversubscribe their CPUs. Reserve dedicated capacity for each strength test and monitor real throughput.

| Window | Deliverable | Acceptance / stop condition |
|---|---|---|
| 18:15–19:15 | Immutable V8 manifest; complete gate records; repaired pair selection and diagnostics; reanalysis of completed gates | Both arms NNUE-on; zero invalid/fallback games; archive hashes, command, worker/core allocation and opening manifest. Do not infer finals from partial logs. |
| 18:15–20:15 | Minimal correctness candidate in a separate directory; terminal tests and repetition boundary repair; independent R94/98/99/100 triage | Exact tests pass, no board/accumulator corruption; no unrelated pruning/net/time changes. If correctness work expands, reduce scope or defer. |
| 20:15–23:15 | Timed V8 versus correctness candidate on representative paired starts, and matched common-weaker-opponent conversion lane | All gates predeclared and complete. Save both arms' full logs, per-pair results, intervention counts and starting manifests. If no mechanism benefit or clear regression, stop this candidate. |
| 23:15–02:15 | One fresh-opening confirmation of the strongest eligible candidate; selective-book lane only if independent audit supports a small change | Do not pick the best of many noisy retests. Fresh representative starts must confirm; targeted positions alone cannot authorize shipping. |
| 02:15–06:30 | Final exact-package timed gate and cold-start/reliability checks; combination gate only if combining separately justified changes | Fix the final zip before testing. Any subsequent code/net/book change invalidates this gate. Use production initialization settings, not the 300-second override. |
| 06:30–08:30 | Decision, package verification, and upload if justified | Retain V8 if criteria below fail. Complete platform validation with time for rollback. |
| 08:30–11:00 | Contingency buffer and freeze | No new search experiments or untested late fixes. Verify which exact version is active at lock. |

Suggested use of available capacity: one isolated timed head-to-head lane, one matched weaker-opponent lane, one independent analysis/reproduction lane. These are ordinary test processes, not permission to saturate all 384 logical threads. Physical cores, memory bandwidth, compile concurrency and per-game NPS decide safe capacity. Launch scripts must save PGNs (`--pgn-out` was absent from the inspected stable/weak scripts), and preserve complete metadata rather than aggregate grep output.

### Ship rule

For a correctness repair, the primary acceptance conditions are a failing-before/passing-after reproducer, the corresponding general invariant suite, and consistent behavior across all relevant search entry points. **Do not require a positive Elo estimate to repair a proven rule violation.** Timed gates measure implementation costs and unexpected regressions; they do not decide whether stalemate is a draw. Predeclare a tolerated performance cost and investigate any substantial regression before release. If formal non-inferiority is claimed (for example at −5 Elo), its confidence bound must actually meet that margin; an inconclusive gate does not establish it. Strategic changes such as wholesale book replacement still require independent quality evidence and representative timed validation.

Require zero new legality/crash/init/fallback failures, exact reproduction tests passing, no material throughput/clock regression, representative opening exposure, and no untested combination. Report W/D/L and loss rate with uncertainty alongside total score. Maximizing Swiss score is not equivalent to minimizing losses at any cost; a policy that converts wins into draws can have fewer losses and be worse.

The dashboard says **2 of 10 uploads in the last 24 hours**, which reads as two used, not two remaining. The older brief appears inconsistent. Verify the actual counter before making release plans; one candidate and a rollback should be budgeted regardless. The displayed 34+24+15 record totals 73, while the chart covers 77 rounds and the game list includes an in-play round. Use completed game records for denominators rather than assuming all display counts refer to the same population. At the supplied R100 snapshot the rating is 2826, not 2892.

## 6. Cheap depth and hypotheses to revisit

Do not restart training, widen the net, alter contempt, or resweep aspiration before lock. “Closed for this deadline” is justified; “proved universally worthless” is not. Note the inspected live code defaults `draw_behind=1`, despite the brief saying a draw-seeking experiment cost strength; and ProbCut defaults off, despite being listed among the engine features. Emit a startup feature manifest and reconcile the measured variant with the shipped one before reasoning about either.

For speed, first measure where time goes on the **deployment x86 CPU**, not only the Mac: accumulator update, SCReLU output, move generation/SEE, sorting and TT memory. The frozen net really is 1024 wide, eight output buckets, int16 accumulators; the measured safety bound is 16,355. Preserve numerical equivalence.

A low-risk experiment is a smaller TT through the existing environment hook (`BINI_TT_BITS`), balancing cache behavior against hit rate and memory. Another is a demonstrably identical hot-loop implementation if target-machine assembly and benchmarks show a win. Numba has LLVM and assembly inspection; “no external compiler” does not mean “no code-generation options,” but the project's failed loop experiments are good reason not to guess. Do not force vectorization, fastmath, narrow overflow-prone reductions, or GPU/ONNX calls into a single-position CPU search on deadline.

Lazy accumulator updates can avoid work before terminal/TT cutoffs and may be a worthwhile future project; they require careful refresh/invalidation, promotion/castling/EP tests, and are not a free last-minute patch. Node reductions from better ordering/pruning also buy effective depth, but selective depth alone is not a strength metric. A 10–20% speedup generally buys a fraction of a ply, depending on measured effective branching factor—not three free plies.

## 7. Evidence and reproducibility

Files in this directory:

* `probe_correctness.py` and `correctness_results.json`: direct calls into unmodified frozen engine code, plus python-chess oracles. No timing or Elo claim is made from these local probes.
* `log_inventory.json`: downloaded rounds 87–100; no fallback/error/illegal markers found in those inspected logs. R99 and R100 have zero book moves.
* `grade_games.py`, `stockfish_triage.json`, `grade_games.log`: independent Stockfish triage with fixed nodes; consult the generated outputs and subsequent notes for completed coverage. These are search estimates, not tablebase certificates.
* `paired_gate_stats.py`: completed-PGN cluster analysis. The remote final gate PGNs are still needed to recompute the team's actual intervals.

Primary references supporting the rules and engineering distinctions:

* [FIDE Laws of Chess](https://handbook.fide.com/chapter/e012023): dead position requires impossibility of mate by any legal sequence; terminal precedence matters.
* [python-chess core API](https://python-chess.readthedocs.io/en/stable/core.html): material recognition and draw/outcome behavior. The installed competition referee is the operational authority for this project.
* [Stockfish search source](https://github.com/official-stockfish/Stockfish/blob/master/src/search.cpp): example of explicit rule50-aware TT safeguards; not a patch to transplant blindly.
* [Numba documentation](https://numba.readthedocs.io/en/stable/reference/jit-compilation.html): inspection of generated code for a target-specific optimization investigation.

The useful interpretation of the owner's directive is: preserve wins when a sound winning continuation exists, secure a draw when winning chances are gone, and minimize avoidable errors. It cannot be implemented by assigning every apparent advantage a winning truth value or by forbidding draws. The intended deliverable is a demonstrably more correct engine; if the corrected package cannot be validated before lock, retain the known package for the competition and continue the repairs separately.

## 8. Correctness-first engineering specification

This is the main worklist after the owner's clarification. “Confirmed” below means the defect was reproduced or directly established from the inspected code; the other items are required audit coverage, not claims of additional discovered failures.

| Priority | Invariant | Engineering work and acceptance test |
|---|---|---|
| P0 — confirmed | A terminal draw cannot become a positive/negative learned evaluation | Implement one conservative dead-material predicate and one draw utility; call before TT/eval/pruning in main search and quiescence. Compare material classification to python-chess. Run with empty and deliberately contaminated TT/correction tables. |
| P0 — confirmed | Stalemate is a draw at every frontier | Add efficient legal-move-existence handling. Test stalemate reached after a capture, after a quiet move, at qsearch entry, and recursively after check evasions. Test full and null windows and warm/cold TT. |
| P0 — confirmed | Checkmate takes precedence over draw counters | Test mate at halfmove 99, 100 and 150 and mate-in-one that crosses a boundary. Match the actual referee's order, not only a generic interpretation of FIDE rules. |
| P0 — confirmed | Repetition distance counts each ancestor once | Replace the even-ply duplicate-root scan; test all short reversible cycles across odd/even root boundaries and last-irreversible boundaries, including long histories. Separate actual claimability from heuristic search-cycle cutoffs. |
| P0 — confirmed in candidate | A material heuristic is never labelled an exact rule | Remove the one-minor-each categorical claim. Include the KB–KN mate counterexample and opposite-colour bishop positions in negative tests. |
| P1 — source risks | TT reuse cannot bypass context-sensitive terminal outcomes | Instrument draw provenance, rule50, policy and bound type. Check terminals before TT. Test same board under different reversible counters and histories; changing draw policy must invalidate or segregate dependent entries. A local early check alone does not solve all ancestor-bound contamination. |
| P1 — source risks | Null moves cannot manufacture real-game repetitions/claims | Track a null boundary/plies-since-null or otherwise isolate synthetic history. Test positions near rule50 and reversible cycles around a null subtree. Verify restoration after null verification and abort. |
| P1 — source risks | Position identity matches legal move rights | Include legal EP availability in book identity; normalize pinned/non-capturable EP consistently in engine history keys. Test castling-right changes and transpositions with identical piece placement. |
| P1 — audit | Make/unmake is an exact inverse | Differential legal-move sets and perft against python-chess; exact bb/st/pcs/key restoration after every legal, illegal, EP, promotion, underpromotion and castling attempt; randomized games and nested undo. |
| P1 — audit | Incremental NNUE equals a full refresh | Compare both accumulators elementwise after every move and undo, and compare output scores for both sides and all material bucket boundaries. Exercise king bucket/mirror changes for architectures that have them. Verify arithmetic range over legal positions and all enabled net formats. |
| P1 — audit | Search bounds carry their advertised meaning | TT pack/unpack round trips, positive/negative mate-distance normalization at different plies, exact/lower/upper-bound semantics, excluded-move searches, collision/replacement cases, aspiration fail-high/fail-low and aborted iterations. Check a small unpruned reference on tractable positions; selective heuristics are not generally minimax proofs. |
| P1 — audit | Timeouts cannot corrupt subsequent decisions | Force aborts at different nodes and recursion depths; compare restored state to the original; legal move fallback with sub-100ms budgets, forced moves, import failure, unavailable weights and low-clock overhead. Record fallback events explicitly. |
| P1 — confirmed measurement gaps | Every gate measures the intended two builds | Reject void/init/error/fallback/NNUE-off on either side; persist exact manifests, pair IDs, PGNs and mode counters. Verify production init separately. |
| P2 — confirmed metadata issue | Every book entry has honest provenance | Independently validate each entry's move, score perspective, search depth and completed-search origin. A root PV child cannot inherit root-depth certification. Test key collisions and avoid silently retaining stale entries on a resumed rebuild. |
| P2 — quality investigation | Claimed advantages correspond to defensible continuations | Independently reanalyze first deterioration points and alternatives. Use exact small-endgame oracles where available. Split objective evaluation errors from pruning misses and opponent-resource oversights; design targeted suites from those cases. |

For each repair, require four artifacts: the failing original case; a minimal isolated patch; a generalized regression suite that includes counterexamples; and the measured performance/behavior effect. Do not combine all search changes into one opaque “correctness” patch. Terminal handling and repetition bookkeeping can be developed separately and tested together only after each passes. Fixing a rule violation may change prior accepted behavior; that is expected, but its computational cost still needs measurement.

The platform's `board.outcome(claim_draw=True)` can recognize a draw claim available through an intended next move. A search that only tests the current repetition count or `halfmove >= 100` is not automatically equivalent. Write the referee-compatibility tests first, then implement the intended exact semantics and explicitly document any remaining search approximation.

Further audit coverage does not justify delaying the three reproduced fixes indefinitely. Begin with the terminal evaluator and repetition boundary; use the broader suite to establish confidence and discover adjacent failures. This is a concrete path to fewer flaws and internally consistent decisions, rather than an Elo-optimization campaign.
