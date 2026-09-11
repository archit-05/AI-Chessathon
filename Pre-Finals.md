# Pre-Finals — BINI Alpha / Opus Carlsen

**Owner-approved direction:** improve the proven engine, prepare thoroughly for the revealed finals constraint, **and pursue a very large pretrain as a separate, real workstream**. Both tracks matter. Neither is permission to upload an unvalidated build.

**Prepared:** 11 September 2026, following the completed qualification Swiss. Planning horizon: at least twelve hours before the in-person final opens and its brief is revealed. Re-anchor the schedule to the actual remaining time when execution starts.

## 1. The objective and operating principles

Maximize our chance of winning the London knockout by arriving with the strongest validated agent we can produce, a reliable baseline, reproducible training artifacts, and the tools to adapt quickly to the newly revealed constraint.

We cannot promise a perfect engine or a comfortable win. “10/10” means meeting explicit engineering acceptance criteria, not claiming that finite tests prove perfect chess. Treat correctness, strength, speed and tournament strategy as separate properties.

1. Preserve what produced **10/13: eight wins, four draws, one loss**. Do not replace the engine simply because another architecture is larger.
2. Investigate decisive moves, not just alarming score plots or game termination labels.
3. Maintain three distinct statuses for every claim: **observed**, **hypothesis**, **validated intervention**. A reproduced error is not yet a proven cause; a proven cause is not yet a stronger release.
4. Pursue the large pretrain seriously, with measured compute and a full validation path. Keep it independent of the incumbent-improvement track so either can succeed.
5. Let actual CPU match performance decide which model ships. Training hardware and deployment hardware solve different problems.
6. Use the final hours for confirmation and packaging, not surprise architecture changes.
7. No automatic upload, unrequested external messages, or changes to the locked qualification artifact. This document authorizes planning; launching paid compute requires the owner's existing spending authorization or an agreed budget.

## 2. Baseline identity: protect before doing anything

| Item | Current control |
|---|---|
| Friendly name | V8.5 |
| Implementation | `bini_astra_v5_noc2b` |
| Submission | `submission_V8.5.zip` |
| SHA-256, rechecked when preparing this plan | `26828c240ebcd9ae175f0af8b800131f16e26d01c21b6ae590af02cbc73174dd` |
| Network | `fc_b-104`, own-trained |
| Prior fallback | `submission_v8_0910_0313.zip`, original V8 |
| Network/book difference versus V8 | None; V8.5 retains both |
| Main code difference versus V8 | Board/search correctness work; excludes the behaviorally riskier C2b repetition policy |
| Qualification Swiss | Sixth, 10/13, 8–4–1; tied on points with second |
| Direct historical V8.5 versus V8 gate | −4.3 Elo, 95% interval [−18.5, +9.8], 400 games, 31–333–36 |

The gate passed the previously chosen −20 non-inferiority margin. It did **not** prove zero strength cost or a strength gain. The Swiss shows competitive performance but cannot isolate the effect of the changes without a matched control.

Create a run manifest recording the full source, weights, book, package, interpreter and dependency hashes/versions. Use separate candidate directories or branches. Never overwrite the control's weights with a checkpoint under test. Give every exported candidate a unique ID.

## 3. Current architecture and deployment constraints

### Engine

- Python wrapper exposing `get_move(fen, time_left_ms)` and returning a UCI move.
- numba-jitted bitboard engine with iterative deepening, PVS alpha-beta, transposition table, null-move search, late-move reductions/pruning, futility, SEE, singular extensions, aspiration and histories.
- NNUE: eight king buckets over 768 piece-square features, 1024-wide accumulators for two perspectives, eight output buckets, SCReLU, quantized weights/int16 accumulators.
- `fc_b-104` continues the team's own `k96-96` lineage. Old reports sometimes discuss k24; do not confuse it with the deployed network.
- Default TT has 2^24 entries, approximately 256 MB for the key/data arrays alone. Overall memory also includes search stacks, NNUE accumulators, Python and JIT runtime.
- Opening book uses prepared moves when a legal hit exists. Current wrapper checks its own move count below twelve before consulting it.
- Time budget uses `max(18, 34 - 0.4 * own_move_count)`, increment allowance and hard caps, with additional search stability/danger behavior. **Own move count is not necessarily the PGN fullmove number**, because games start partway through an opening.
- Shipped defaults include contempt 20, correction/continuation/SEE pruning enabled, calibration disabled, aspiration 25, quiet-check quiescence disabled, ProbCut disabled and improving flag disabled. Feature presence in source is not evidence that it is enabled.
- Draw utility can become neutral when the previous root score is sufficiently negative after the configured own-move threshold. This depends on the engine recognizing that it is worse.

### Published qualification environment — verify against tomorrow's brief

| Constraint | Current published specification | Consequence |
|---|---|---|
| Clock | 120 seconds + 0.5 seconds per move | Wall-clock strength matters |
| Init | 90 seconds | Cold JIT and loading must finish with margin |
| CPU | One AMD EPYC core, 2 GB RAM | GPU training does not provide GPU inference |
| Process | Fresh per game; persists across own moves; suspended during opponent's turn | No pondering or cross-game state |
| Network | None during play | All runtime assets must ship |
| Package | At most 50 MB unzipped; `agent.py` at root | Larger weights compete with book/tablebase space |
| Runtime | Python plus preinstalled numpy, python-chess, numba, torch CPU, onnxruntime | Native engine binaries are rejected; no deployment compiler |
| Filesystem | Read-only except limited `/tmp` scratch | No persistent compilation cache between games |
| Network provenance | Shipped networks must be trained by us | Do not initialize from a third-party published chess network |
| Training data | Engine-labelled positions allowed | Deep Stockfish can be a label teacher |
| Stored answers | Opening fullmove number ≤20; endgame ≤7 pieces | Do not ship memorized middlegame answers |

Sources: [technical documentation](https://aichessathon.com/docs), [competition rules](https://aichessathon.com/terms). This table is a qualification baseline, not an assertion that the unrevealed finals limits are identical.

Prepare to verify both the permitted use of pre-existing assets and access to external training compute on the day. Do not speculate that a particular new restriction will be imposed.

## 4. Capability assessment: where we are below “10/10”

Scores below are **qualitative engineering judgments**, not measurements or comparisons with Stockfish. They identify where effort should go. They do not mean 8/10 implies an 80% probability of correctness.

| Capability | Working score | Evidence / gap | Practical completion criterion |
|---|---:|---|---|
| Terminal-rule handling | 8/10 | Substantial tested corrections; no exhaustive proof across all entry points and state contexts | Existing regressions pass; boundary/oracle tests cover any changed paths; exact draw utility distinguished from terminal truth |
| Board/history integrity | 8/10 | Index/null-boundary fixes exist; faithful replay and path-dependent state remain important | Make/unmake and history invariants survive legal sequences, special moves and candidate changes |
| Tactical decision quality | 6/10 | R113 missed a forcing winning opportunity; R114 misjudged compensation | Causal diagnosis and improved unseen tactical decisions without broad regression |
| Defensive move selection | 6/10 | R108 rejected a holding capture | Improve hold-versus-loss ranking on independent defensive examples |
| NNUE evaluation/generalization | 7/10 | Strong overall performance; targeted ranking failures; training distribution risks | Better held-out move ranking and completed timed strength; export parity retained |
| Search selectivity | 7/10 | Strong depth, but reductions/pruning can conceal important continuations | Instrument suspected failures; justify changes with causal and timed evidence |
| TT/repetition interaction | 6/10 | Historical warm/cold score disagreement; retained cycle heuristic; live state unavailable | Trace draw/bound provenance and prevent demonstrated invalid reuse without crippling search |
| Time management | 8/10 | Swiss had no flags and long games survived; spending may miss high-value opportunities | Position-specific time-response evidence plus paired clock validation |
| CPU efficiency | 7/10 | Competitive numba search; target measurements vary roughly 0.5–0.7M nodes/s | Profile-led savings that improve useful search under the clock |
| Opening preparation | 6/10 | Old-net book retained; only 12/78 first-six Swiss moves instant | Legal, rule-compliant preparation with measured timed benefit |
| Endgame/conversion | 7/10 | Eight Swiss wins; missed tactical conversion, not all draws defective | Preserve good conversions and improve verified missed opportunities |
| Cold startup / reliability | 8/10 | All Swiss NNUE-on; 37–60.3 seconds init | Margin under actual final limits; no fallback disguised as valid operation |
| Training reproducibility | 5/10 until restored | Float checkpoint recovery unresolved; earlier GPU failure lost work | Reloadable checkpoints, manifests and two independent backups proven |
| Test methodology | 8/10 | Paired wrapper gates exist; historical partial-result and fallback traps | Immutable candidates, complete results, independent confirmation and diagnostics |
| Opponent intelligence | 6/10 | Rich public games; older reports invent depth/architecture labels from ACPL | Use measured behavior with uncertainty; no unsupported architectural claims |
| Finals adaptation readiness | 5/10 until exercised | New brief unknown; controlled configuration/testing needed | Demonstrate a constraint change, package rebuild and clean smoke cycle |

Do not turn this into a quest to add features to every row. A stable 8/10 capability can be more valuable than an untested attempt at 10/10. Close the gaps with the highest expected effect on actual decisions and execution.

## 5. Known issues and investigation ledger

### Priority A: three concrete decision targets

| Target | Observed BINI behavior | Independent reference evidence | Still unknown |
|---|---|---|---|
| **R113, White 39.Rc2 vs OMI** | +157 cp, depth 19, 5.33 seconds, 44.14 seconds before move | Qe8+ about +7.83 at depth 25; played Rc2 about +0.74 at depth 19, 600k nodes per arm | Which search/evaluation decision rejected the combination |
| **R114, Black 40…Qh6 vs slopfish** | +59 cp, depth 17, 1.50 seconds, 39.39 seconds before move; opponent captured rook with gxh5 | Bh4 about +0.19 versus Qh6 −1.54 from Black's view | Compensation error, selective-search miss, time-sensitive instability or interaction |
| **R108, White 39.g5 vs Mite** | Roughly draw utility despite declining the rook capture; later still −20 at depth 27 | fxe3 0.00 versus g5 about −1.96, 500k nodes per arm | Evaluation versus cached/cycle draw versus search interaction |

Reference values are finite-search estimates, not complete proofs. Preserve history in every recheck. R113's instructive continuation begins Qe8+ Kh7 Nd7. Follow the entire relevant line, not just the first checking move.

### Priority B: secondary and unresolved concerns

- R116/29…Qg3 reduced a reference advantage from roughly +0.79 to equality; not a proven forced win.
- Older R103/R105 investigations support move-ranking problems but do not establish a universal network-only cause. Different ablations helping different examples do not eliminate search as a contributor.
- R100's exact live cache is unavailable. Distinguish a cold reproduction of the move from a faithful reproduction of the complete live state.
- R104's conversion opportunities must be analyzed with complete history; do not identify an earlier sacrifice as a blunder merely because a later game was lost.
- Main-search quiet pruning and SEE decisions can occur before `gives_check` is computed. A checking continuation can therefore be affected at eligible non-PV nodes. This is a specific diagnostic target, **not automatically a rule bug**. Root checking moves are not simply discarded by those non-PV conditions.
- Quiescence omits optional quiet checks by default. Enabling them everywhere may cost more than it gains. Test targeted behavior only after a relevant missed continuation is traced.
- TT scores and repetition are path-dependent concerns. Reconstructed warm state is not identical to lost live TT. Preserve mate-distance and bound semantics in any intervention.
- `Engine.__init__(tt_bits=...)` currently calls the module's `new_tt()` without using that argument. The effective sizing control is the import-time `BINI_TT_BITS` setting. A finals memory tool must verify actual allocated arrays, not assume the constructor parameter works.
- Book lookup is limited by own move count. Verify an explicit absolute fullmove-number guard against the published move-20 rule and audit whether any prepared answer is reachable outside the allowed range. This plan has **not established an actual prohibited book move**.
- Audit book-key en-passant/castling semantics, legality and collision handling. Legal-move checking prevents illegal output but does not guarantee the lookup identified the intended position.
- Historical reports saying “no possible strength improvement” or “only retraining can fix it” overstate the evidence. Likewise, the loss of one float checkpoint is not proof that no trainable initialization can be recovered.

### What is already repaired, rather than a fresh V8.5 defect

The V8.5 correctness work addressed terminal-material recognition, stalemate-related paths, mate precedence over draw checks, repetition indexing/null-history boundaries and terminal precedence at TT cutoffs. Preserve the tests that established these changes. It intentionally did not adopt C2b's altered repetition policy. A second-occurrence search cycle heuristic is not automatically equivalent to an illegal referee claim.

Do not classify K+B versus K+N as universally dead material. Material class, theoretical best-play draw and impossibility of any legal mate are different concepts. Use the referee's actual oracle and precise rule semantics.

### Draws that are not established defects

R119's screening showed modest advantages, not a clear missed win. R122's tactical repetition against JBG was reference-consistent with equality. Its −20 score can be configured draw utility. It is not evidence of a wrong material score. R102's liquidation was already objectively drawn in the reviewed alternatives; the old false positive score did not establish that a win was lost there.

## 6. Twelve-hour execution schedule

Use independent workstreams when staffing and compute permit. Each needs a named owner and artifacts; do not create hidden simultaneous edits to the same files.

| Time from start | Incumbent/search track | Training/data track | Large-pretrain track | Validation/release track |
|---|---|---|---|---|
| 0–1 h | Freeze hashes; construct faithful critical-position replays | Locate checkpoint, trainer and data; verify backups | Inventory actual GPUs/VRAM; choose architecture and exposure budget | Verify harness environment and clean A-vs-A smoke |
| 1–2 h | Trace three failures and produce cause table | Benchmark stratified labels; create split manifest | Prove training/export round trip; short throughput/learning pilot | Reserve isolated CPU workers and fixed test sets |
| 2–4 h | Implement at most one justified local search change | Controlled continuation and targeted-data fine-tune | Begin large pretrain after pilot checks pass | Run correctness and deterministic screening as candidates arrive |
| 4–6 h | Evaluate time sensitivity and profiling opportunities | Export a bounded candidate shortlist | Evaluate checkpoints at predeclared intervals; retain best development candidate | Start complete timed comparisons; checkpoint every game |
| 6–9 h | Stabilize or reject local changes | Hold candidate identities fixed | Continue only while enough validation time remains | Complete selection gate; launch fresh confirmation |
| 9–10 h | No new speculative features | Stop generating untestable candidates | Select tested candidate or classify run as research-only | Decide strongest eligible candidate using completed evidence |
| 10–12 h | Freeze source and configuration | Verify checkpoint backups and provenance | Save final trainable artifacts even if not selected | Exact-package resource checks, presentation and constraint rehearsal |

Recalculate this schedule after the first throughput measurements. A longer pretrain may continue for research, but it is ineligible to ship without the remaining verification. Do not consume tomorrow's adaptation window trying to rescue an unfinished pipeline.

## 7. Workstream A — investigate and improve the existing engine

### A1. Faithful reproduction

For each target retain initial FEN, all played moves, own color, before-move clock, actual chosen move, network/config hash and log score/depth. Rebuild actual game history, including intermediate opponent positions. Assert board/FEN agreement and history bounds before every tested turn.

If the engine proposes a different move during replay, explicitly advance its internal position/history using the recorded game move. Do not silently allow the next wrapper update to reset state and call the result a warm replay. Separate: cold FEN-only diagnostic, cold full-history diagnostic, reconstructed warm replay and unavailable original live state.

Record completed iterative-deepening results. An aborted final iteration under a node/time cap is normal; do not confuse it with a valid completed result at that depth or require an always-zero abort flag under intentional capped searches.

### A2. Compare decisions, not unrelated scores

Analyze the candidate root moves from the same position, side, search conditions and history. Trace raw NNUE, corrected evaluation, terminal/draw returns, TT score provenance/bound/depth, and PV completion. Avoid comparing a pre-move network evaluation with a post-move reference score and calling the difference a calibration error.

Instrument whether the key continuation was generated, ordered late, pruned, reduced, re-searched, or evaluated unfavorably. Start with Qe8+/Nd7, the defense to Qh6, and fxe3 versus g5. Keep instrumentation out of performance candidates.

Run a small budget sweep where relevant: actual logged time, approximately five seconds and a longer diagnostic allowance. A positive result licenses a time-policy experiment; it does not establish a global multiplier. A negative result in one old game does not generalize to all new failures.

### A3. Intervention discipline

Change one mechanism at a time. Keep baseline net/book/time fixed for a search candidate. Require regression tests specifically covering a correctness repair and independent position/game checks for strength. Do not disable all pruning, globally enable quiescence checks, or add a blanket material penalty just because it fixes one example.

Deliverable: `cause_table` with each target's observed behavior, experiment, competing explanations, conclusion and remaining uncertainty; immutable candidate source and a minimal diff if justified.

## 8. Workstream B — controlled continuation and fine-tune

### B1. Restore the baseline training path

Search for fc_b-104 float weights and optimizer state, then the k96-96 ancestor and backups. Local exported networks exist in `/Users/architbhardwaj/chess_d10_mirror/nets`. Training logs exist under the mirror's `gatelogs/logs` directory. Record exact recovered lineage.

If only quantized own-trained weights survive, dequantization may provide an initialization, but it is not exact checkpoint recovery. Rebuild the known feature mapping, king-bucket mirroring, perspective ordering, SCReLU, output buckets and scaling. Demonstrate inference/export round-trip agreement first. Use new optimizer state and label the lineage honestly.

### B2. Data selection and labels

Benchmark approximately 5,000 stratified positions first. Cover quiet development, forcing tactics, queenless imbalances, defensive liquidation, passed pawns, king safety, conversion and draw boundaries. “Best move is a capture” is not an adequate definition of sharpness. Inspect what the actual loader filters, not merely what an upstream generator wrote.

Retain broad data as the majority. Treat 5–10% verified difficult examples as an initial experimental mixture, not a promised optimum. Prior large endgame enrichment hurt performance. Cap positions per source game; deduplicate and split by game/opening family before sampling derivatives. Avoid leaking adjacent positions, variations, mirrors or repetitions across splits.

Use a standard teacher configuration and compute budget, preserve score perspective, history where available, bound/mate/WDL metadata and teacher version. Deepen uncertain best-versus-alternative rankings rather than insisting every row gets one nominal depth. Use exact small-endgame labels where available and rule-correct. Mark genuinely ambiguous rankings instead of forcing artificial hard negatives.

### B3. Controlled experiment

Compare unchanged-distribution continuation against the modest targeted mixture at the same architecture, training exposure and schedule. Keep the existing loss/export mechanism initially. Record effective passes over unique positions, not just superbatch names. Select checkpoints on development data only; reserve unseen games for confirmation.

Measure top-move ranking and severe regret, defensive hold selection, tactical conversion, broad evaluation quality and quantized inference. Training loss alone is insufficient. Cases repeatedly inspected by the team are development examples, never independent proof.

## 9. Workstream C — very large pretrain: committed parallel experiment

This is an explicit part of the owner's plan. It must receive a concrete dataset, architecture, compute schedule, checkpoint policy and validation route. Do not silently omit it because the incumbent track is lower risk.

### C1. Define “large” in two dimensions

- **Large data/exposure:** broad, diverse, deduplicated positions and an intentional total number of training presentations.
- **Large network:** more parameters and higher inference cost. This is a separate hypothesis.

Do not assume that doubling width plus repeating a small corpus produces a stronger engine. Earlier 1536/2048-width experiments were not convincing; the new run must explain what materially differs and still beat a real-clock control.

### C2. Initial architecture decision

Use **2048 width with the existing feature/bucket family as the initial larger-model candidate**, subject to successful trainer/export support and measured memory/throughput. It is a concrete starting choice, not a promise that it will be deployed. Keep the current 1024 model as the primary comparison; if resources permit, a fresh 1024 pretrain on the same data helps separate data gains from width gains.

The first layer alone has approximately 6144 × width weights. At two bytes per weight this is about 12.6 MB at 1024, 25.2 MB at 2048 and 50.3 MB at 4096, before other tensors/files. Verify actual tensor layout and exported ZIP size. A conventional 4096-wide version therefore exceeds a 50 MB decimal package cap on its first layer alone. It must not be presumed deployable.

If the owner wants a substantially larger 4096+ teacher, run it only as an explicitly **training-only** candidate with a planned smaller student. Distillation adds another training, export and testing stage; do not rely on its completion before finals. A larger teacher trained on the same shallow labels is not automatically a better source of truth. Compare it with the reference labels before distilling.

### C3. Mandatory preflight before the long run

1. Confirm actual GPU count/model, usable VRAM, storage, driver, trainer support and remaining authorized credit. Historical access to two 5090s is not proof both are available now.
2. Run a forward/backward pilot, save, reload and export. Verify all buckets and quantized evaluation on a sample with known feature mapping.
3. Measure examples/second, peak memory, data-loader utilization and export time. Use a working single-GPU path first; do not introduce untested distributed training just to use both GPUs.
4. Prefer one GPU for continuation and one for the large pretrain when two independent devices are available. If only one exists, schedule explicit allocations and protect validation time.
5. Fix the architecture, dataset manifest, initialization seed, optimizer, precision, learning-rate schedule, effective batch, total examples and checkpoint intervals before the run.
6. Demonstrate a short learning curve against an untouched development partition. Stop and repair NaNs, overflow, input/label errors or failed export immediately.

### C4. Exposure arithmetic and dataset scale

A superbatch in the historical trainer is approximately **100,007,936 positions**. Compute:

`effective passes = total position presentations / number of unique training positions`

Write both values in every run report. Dataset rows may contain duplicates; unique and raw row counts must be distinguished. Do not accidentally turn a small corpus into hundreds of passes by copying an old superbatch count. Previously reported severe losses from overexposure make this a hard preflight item.

Use the existing broad labelled shards where valid rather than waiting for an entirely new huge deep-labelled corpus. Combine quality-controlled broad coverage with selectively stronger labels. Set the final target size and number of passes after inventory and throughput measurement; do not promise one million deep labels in two hours without a benchmark on the actual hardware.

The historical fc_b continuation processed eight superbatches in 5m18s on one 5090. That is evidence of past throughput for that configuration, not an ETA for a new architecture, data loader or from-scratch convergence.

### C5. Checkpoints, selection and stopping

Save weights, optimizer, scaler where used, RNG state, configuration and data position. Copy checkpoint artifacts plus checksums to a second independent machine/storage location on a bounded schedule. Verify a reload, not just file existence. Save run logs incrementally.

Choose checkpoint evaluation intervals and a small finalist count in advance. Monitor training versus development loss, held-out move ranking, material/phase breakdowns and quantized export behavior. Do not inspect the final confirmation set repeatedly. Record failed runs, not just the best checkpoint.

A checkpoint can continue as research even if it misses the deployment window. It cannot bypass gates because it used more hardware. If 2048 improves fixed-node results but loses at the clock, retain the smaller engine; a distillation follow-up is a separate experiment.

## 10. Workstream D — performance, books and optional endgames

### CPU performance

Profile the actual x86 environment with representative positions, repeated warm measurements and uncontended workers. Measure NNUE updates/refreshes, move generation, TT traffic and other demonstrated hotspots. Separate cold startup, steady nodes/second, time-to-completed-depth and actual playing results.

Only implement local optimizations with exact state/numeric parity where expected. Explicitly examine overflow limits if quantization, accumulator width or activation scaling changes. A speed gain caused by silently skipping NNUE is a failure.

### Books

Compare actual hit rates, legal state keys, allowed absolute move number, per-entry provenance and reference exit quality. Mite's 43/78 versus our 12/78 instant first-six Swiss moves suggests greater active preparation on its encountered positions; it does not prove a better book or universal coverage. Test any revised book separately at real time with matched openings and colors.

Do not install memorized middlegame answers as a shortcut. Negative book gates already exist; coverage alone is not an acceptance metric.

### Small tablebases

Treat selective endgame tables as secondary. Inventory complete material-class dependencies, uncompressed archive cost, Python runtime support, lookup latency and fifty-move-aware WDL/DTZ decisions. Test missing-table fallbacks. Do not assume all useful five- or seven-piece data fits. These tables do not answer the 12-piece R108 decision or the middlegame R113 combination.

## 11. Validation protocol and release decisions

### Layer 1: integrity and meaningful correctness checks

- Exact export metadata, expected shapes/scales and all eight output buckets.
- Incremental NNUE versus full refresh across legal random sequences and castling, en-passant, promotion, capture and king-bucket transitions; numerical range/overflow checks where affected.
- Board/hash/make-unmake parity and history preservation for touched code.
- Existing terminal, repetition, null-boundary, mate-distance, stalemate and TT-terminal regressions.
- Legal UCI return and completed wrapper operation from curated start FENs.
- Cold startup and peak memory under the applicable limits; explicit NNUE-on and zero fallback.

Do not expand testing endlessly for unchanged low-impact files. Tests must verify a meaningful invariant or regression, not restate implementation.

### Layer 2: deterministic screening

Use fixed nodes for cheap screening and causal probes. Record completed depth and timing as diagnostics. A wider network receives no deployment credit merely for better fixed-node play. The historical screen-to-clock attenuation was substantial, and some attractive screens reversed under time.

### Layer 3: completed timed selection

- Use `arena_par` or the verified real wrapper. `node_gate` cannot isolate time constants through its shared budget global.
- Pair openings with colors swapped. Fix seeds, opponent versions and candidate hashes. Compare the candidate directly with its intended control.
- Include V8.5 and a small available diverse opponent pool. A weaker same-width net is useful for conversion-policy tests. Public rival PGNs are not executable opponents.
- Isolate timed CPU capacity from deep labeling/training data preparation. Determine concurrency by smoke tests rather than maximum advertised thread count.
- Set a sufficient test-machine compile allowance such as the established `BINI_JOIN_S=300` for contention diagnostics, **but separately verify the production package under the real 90-second or revealed init limit**. A relaxed local allowance cannot prove deployment startup compliance.
- Persist each game result atomically, including diagnostics and identifiers. At worst lose the in-progress game after a crash, not 260 completed games.
- Predeclare sample size, pairing-aware uncertainty calculation, meaningful regression margin, candidate count and selection procedure. Report all completed arms.
- Do not read partial Elo as a shipping verdict. Stop for technical invalidity when appropriate; do not selectively stop an exciting score.

### Layer 4: fresh confirmation and package validation

Confirm the selected candidate on an unused opening/game set. Tests on repeatedly reviewed losses are not the confirmation. If a combined search-plus-net candidate is proposed, gate the combined package: separate gains need not add.

Test exact ZIP contents: root layout, duplicate/path hazards, required files, valid source, dependency availability, extracted size and SHA-256. Extract into a clean directory and run the wrapper. Confirm inference and settings match the gated build; do not alter weights/configuration after the gate and retain its result label.

### Decision language

- **Validated correctness repair:** demonstrated failing invariant repaired with relevant regression coverage; strength cost separately quantified.
- **Non-inferior:** passes a declared regression margin, not proof of equal strength.
- **Demonstrated strength improvement:** completed, properly analyzed evidence supports a gain under relevant conditions, with independent confirmation and selection uncertainty addressed.
- **Promising but unresolved:** safe to preserve for future work, insufficient to replace a strong baseline solely on optimism.

If no candidate clears the applicable bar, ship the unchanged validated baseline when permitted. The large-pretrain run is still valuable if it leaves reproducible artifacts and a clear result, including a negative one.

## 12. Opponents and knockout strategy

Observed Swiss results: PSL 8–5–0, BINI 8–4–1, Mite 7–5–1. PSL's healthy-clock median was about 4.13 seconds versus BINI 2.53 and Mite 2.55; PSL ended seven games below ten seconds. This is a measured budget difference, not evidence of deeper search or a larger model.

The [London page](https://aichessathon.com/leaderboard?stage=knockout) specifies a two-game match, one game per color. Published documentation gives a tied match to the better Swiss finisher. If unchanged, a level match favors us against lower finishers and loses against any of the five above us. Confirm the actual bracket and final rules; do not infer entrants from empty bracket headings.

Include simulated two-game advancement with favorable/unfavorable tiebreak status in candidate analysis, alongside game score. Disclose assumptions and schedule differences. Do not introduce opponent-aware or match-score-aware runtime policies unless the interface actually supplies that context or allowed configuration makes it available. The current FEN/clock interface does not, and processes do not share state across games.

Do not raise contempt globally to avoid two draws: past tests were negative, and choosing a losing attack is not a sound way to chase a win. The primary goal remains finding actual wins and actual defenses.

## 13. Tomorrow: brief, adaptation and freeze

1. Read the final brief completely. Extract permitted assets/compute, move interface, clock/increment, initialization, memory, package limit, opening/endgame rules, match tiebreak and freeze time.
2. Confirm invitations/attendance through the team's ordinary organizer channel; do not assume ladder rank alone establishes a seat.
3. Run the unchanged chosen candidate under the revealed limits before changing anything. Identify the binding constraint.
4. Adjust only relevant controls first: clock/increment, TT size, model selection, book availability or startup. Verify effective settings in fresh processes, especially import-time constants.
5. Do not depend on new fine-tuning after arrival. If permitted and genuinely useful, treat it as another candidate requiring time for export and validation.
6. Reserve the final 60–90 minutes, or a proportionate block if the window is shorter, for exact-package checks and the permitted submission process.
7. Retain the known-good ZIP and clearly marked alternatives. Do not promise instant rollback if the final freeze forbids it.

A rehearsal tonight should demonstrate a changed resource configuration, clean extraction, cold start, two colors, legal output and reproducible manifest. Avoid building many speculative variants for constraints that may never appear.

## 14. Presentation and team execution

Prepare a short explanation that every team member understands: architecture, own-training provenance, why CPU inference constrains width, one observed failure, the experiment that isolated it, the measured remedy if one exists, and the actual validation result. Show failures and tradeoffs honestly. Technical explanation is part of preparation even where match results determine the winner.

Assign one person/agent responsibility for integration and manifests. Independent contributors own separate candidate directories and bounded tasks. Every handover includes exact commands/configuration, changed files, output locations, tested artifact hashes, completed checks and unresolved items. No contributor may silently replace another's control or report a result from a different package.

## 15. Required deliverables and checkpoint reports

Create an execution subdirectory under `FinalsDay` and maintain:

| Deliverable | Minimum contents |
|---|---|
| Baseline manifest | Source/net/book/ZIP hashes, environment, current rules snapshot |
| Run register | Run ID, owner, hypothesis, control, compute allocation, status and cost budget |
| Cause table | Three main decision traces, alternative explanations, evidence and candidate intervention |
| Data manifest | Raw/unique counts, filters, label method, source provenance, splits and effective passes |
| Training manifests | Architecture, seed, optimizer, LR, batch, precision, total examples, throughput and checkpoint locations |
| Backup check | Two independent copies, checksums and successful reload |
| Candidate manifest | Exact source/weights/settings/ZIP mapping |
| Gate reports | Complete paired results, uncertainty, opponents/openings, diagnostics, invalid games and checkpoint files |
| Resource report | Cold init distribution, NNUE status, memory and CPU/latency under intended limits |
| Decision report | Chosen build, rejected candidates, supported claims, limitations and fallback |
| Finals checklist | Revealed constraints, actual freeze deadline, validated package, presentation and submission status |

Report at approximately hour 2, hour 6 and hour 10, plus immediately for material failures. Early reports describe process health and completed measurements, not provisional Elo excitement. Record cost and remaining time at each checkpoint.

## 16. Failure contingencies

| Failure | Response |
|---|---|
| GPU unavailable or credits exhausted | Preserve checkpoints; continue local diagnosis, data audit and validation; do not make unapproved purchases |
| Original float checkpoint absent | Try own ancestor; dequantized initialization only after parity checks; label non-exact lineage |
| Large model OOM or export exceeds limits | Reduce batch for training if appropriate; distinguish training-only teacher from deployable student; never bypass runtime/package constraints |
| Training loss improves but timed play worsens | Reject deployment; investigate generalization or inference cost; retain baseline |
| Candidate fixes known moves but fails controls | Reject or narrow the intervention; do not redefine the tests to fit it |
| Timed gate has fallback or contention | Classify affected results invalid; repair environment and rerun the needed comparison |
| Late checkpoint lacks confirmation time | Save as research, keep the validated release |
| New brief invalidates selected candidate | Use tested baseline/configuration adaptation, then verify; avoid a rushed new architecture |
| No validated gain | Keep V8.5 and arrive prepared; do not manufacture a “new version” to justify effort |

## 17. Existing evidence to read first

- [Astra Finals Plan](</Users/architbhardwaj/Desktop/AI Chessathon/FinalsDay/Astra Finals Plan.md>): original preparation plan.
- [Astra Swiss Review](</Users/architbhardwaj/Desktop/AI Chessathon/FinalsDay/Astra Swiss Review.md>): all thirteen games and five independent reference checks.
- [Astra Rival Systems Comparison](</Users/architbhardwaj/Desktop/AI Chessathon/FinalsDay/Astra Rival Systems Comparison.md>): observed rival behavior, architecture uncertainty and corrected intelligence assumptions.
- `FinalsDay/swiss_games.json`, `swiss_reference_checks.json`, `r108_reference_checks.json`: game and diagnostic evidence.
- `FinalsDay/rival_comparison_metrics.json`, `rival_comparison_validation.json`: fresh thirteen-game comparison for each rival.
- `astra_reports/gate_mirror/out/gateB.json`: direct noc2b-versus-V8 packaged gate.
- `external_review_20260910/V8.5_upload_verification.json`: prior package review, including the local Mac cold-start limitation.
- `/Users/architbhardwaj/chess_d10_mirror/gatelogs/logs/train_fc_b.log`: actual historical trainer lineage and exposure arithmetic.

**Final instruction:** pursue both the incumbent-improvement track and the large pretrain; produce evidence for each; select by correctness, real-clock performance and the revealed rules. Arrive with a validated engine and the capacity to adapt—not a dependency on an unfinished experiment.
