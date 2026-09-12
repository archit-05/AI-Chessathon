# Final Plan — 12 September 2026

Prepared from repository commit `7719f9a3`, the morning handover, source inspection, and current public rules. This is a proposed execution plan, not a report of newly completed experiments. Remote jobs, hardware availability and platform uploads have not been checked. Preserve `GrigoryMorning.md` as the historical handover.

## Objective and decision

Maximize the probability of winning the knockout. Pursue a materially stronger complete engine, with the existing network as the control. Unlimited development compute enables more preparation, better labels and much stronger measurement; it does not remove deployment limits, experimental uncertainty or the submission deadline. No numerical Elo gain or undefeated result is promised.

Assume today's 14:00 BST freeze unless the team supplies a changed deadline. The public rules currently confirm it. The user has confirmed maximum performance/velocity and that additional RunPod resources can be obtained; no changed deadline or exact fleet inventory was supplied. The useful window is approximately two hours at plan preparation; finish candidate development by 12:20, select one release challenger by 12:40, and reserve the end for confirmation and platform validation. Rebase these times only if the actual deadline changes.

The strongest feasible strategy is to combine three independently measured sources of gain: recover playing time lost to startup, improve the decisions made by the same compact NNUE architecture, and deepen useful opening preparation. Endgame lookup and selective tactical verification are bounded additional experiments. Buy enough CPU capacity to make testing concurrent with development.

## Verified contract

The live [competition documentation](https://aichessathon.com/docs) specifies 30-second initialization; 120 seconds plus 0.5 seconds per move; one EPYC 9V74 core; 2 GB RAM; no GPU/network; 256 MB fresh scratch; and a 50 MB unpacked submission. Only our own engine and own-trained network may ship. Native binaries and third-party engine ports are prohibited. Engine-labeled training data is allowed. Lookup tables may answer positions at fullmove 20 or earlier, or with at most seven pieces. Matches contain four games, six in semifinals and eight in the final; tied matches favour the better Swiss standing. Processes are suspended on the opponent's turn. Submission closes at 14:00 BST; practice rounds run every ten minutes until 13:50.

## What the evidence actually supports

| Asset or hypothesis | Current evidence | Consequence |
|---|---|---|
| V8.5 network | Strong established entry; Swiss 8–4–1, sixth | Retain as control and legitimate release option |
| New opening book | 300 games, +40 =235 −25; pair Elo +17.4 [−1.9, +36.8] | Best demonstrated selected improvement, but positive point estimate is not proof of a positive true gain |
| bp336 network | 576 fixed-node games, +23 ±19 | Highest-priority existing challenger; real-clock improvement remains unconfirmed here |
| Smaller training experiments | Most near zero or negative; bp144 plus book did not establish extra value | Spend new training on a different data hypothesis or a bounded continuation, not many replicas of failed recipes |
| Startup | Typical platform compile 37–44 seconds; outliers 51/60 seconds | 21-second join buys readiness, not free compilation; saved compilation time can become useful search time |
| Compilation structure | 73 dispatchers, 186 specializations in recorded census; HCE and NNUE reachable from production search | Profile unnecessary compilation and type proliferation |
| R113 tactical miss | Local checking-move exemption fixes known example, aggregate screen neutral | Known-position success alone cannot justify enabling it globally |
| R108 defensive miss | Existing diagnostic points toward misjudged ending continuation | Train and test defensive liquidation/compensation decisions; do not assume more depth cures it |
| Contempt 40 | Timed +10.4 [−16.1, +37.0]; original lower-bound rule was relaxed | Treat as an uncertain policy choice, not a proven strength gain |
| Endgame correction fix | Mechanism identified; full timed gate incomplete in handover | Fetch completed results before treating it as accepted evidence |

The handover references V10 ZIPs in the repository root, but they are absent in this local checkout. Retrieve the exact remote packages and manifests during execution; do not silently substitute the old source directory or bare V8.5.

## 1. Build a trustworthy test fleet first

Use `ship_v85` with the startup fix as the reference, and `ship_bp336` with otherwise identical settings as the first challenger. Bare V8.5 is not a valid finals-clock comparator because startup failures contaminate the result.

Fix the reporting path before aggregating more workers. In `night_evidence/merge_gate.py`, rows are grouped solely by FEN; the first two scores are used when any two exist. Repeated roots can discard later games or combine the same candidate colour. Voids and unknown results also currently become half-points. These are code findings, not proof that a particular existing report is wrong.

The replacement report must:

- Record immutable candidate/opponent hashes, run ID, explicit pair ID, opening ID, candidate colour, seed, host/CPU, clock and init limits for each game.
- Verify one game of each colour per pair; deduplicate retries; separately list unfinished, void and failed games. Do not reclassify failures into normal chess draws.
- Retain every valid complete pair; cluster repeated opening families when calculating uncertainty. Different seeds do not make repeated deterministic games independent evidence.
- Separate development and untouched confirmation openings by root family/source game. Keep known regression positions outside the unseen-strength claim.
- Report W/D/L, paired confidence intervals, timing/failures, book coverage and performance by CPU class and opponent. Use x86 representative of the platform for the primary shipping decision; ARM results are supporting evidence.

Use paired-outcome statistics, as described in [Fishtest's methodology](https://official-stockfish.github.io/docs/fishtest-wiki/Fishtest-Mathematics.html). Fix sample sizes and candidate selection before results. Repeatedly checking an ordinary confidence interval and stopping on a win is not an equivalent sequential test.

Initial resource request, subject to actual availability: 256–512 dedicated physical x86 cores for matches; a separate 256–512 cores for labels/book analysis; four already-ready GPUs for independent training arms. Benchmark provisioning, data transfer and finished games/core-hour immediately. At five to six minutes per game slot, 512 slots provide roughly 5,100–6,100 games/hour before overhead; startup, tails and contention reduce that. Measure, do not promise that throughput. Pin/schedule agent execution to reproduce a single active core and prevent concurrent startup workloads from creating artificial init losses. Keep CPU labeling off match hosts.

Test against the compliant V8.5 control, a fixed diverse panel of our own archived engines, and offline reference engines calibrated to produce informative competitive results. Freeze reference budgets after a pilot. Do not reuse the meaningless nominal Stockfish-2400 setup that lost 60/60. These references are test opponents, never submission code. Opponent PGNs inform scenarios but cannot reproduce opponents' private agents.

## 2. Recover startup time without weakening search

Run two isolated source experiments, each with a 30-minute development cutoff:

1. Normalize redundant scalar argument types/array layouts at proven duplicate call sites. Preserve signedness, bitboard width, overflow semantics and board representation. Start with the largest repeated specializations, not arbitrary global casts.
2. Build an NNUE-only production search compilation path. `evaluate()` currently retains a call to the classical evaluator, and warm-up runs both modes. Remove the unused compiled HCE branch from this candidate while keeping the existing Python emergency fallback. Audit other call sites so HCE is not still compiled elsewhere.

The hypothesis is less code to compile, not a guaranteed number of seconds saved. Merely deleting an extra warm-up call may save nothing because Numba compiles reachable functions. Explicit signatures can avoid additional specializations but can also change conversions or compilation order; [Numba documents these semantics](https://numba.readthedocs.io/en/stable/user/jit.html).

Measure cold import, ready line, full NNUE readiness, first legal reply, steady search speed and peak memory on production-version Python/Numba. Use fresh interpreters and scratch, read-only extracted package files and no development environment overrides. Include all special moves and both colours. Test numerical and fixed-node move parity for changes intended to preserve behavior, plus the existing correctness suites.

Target full usable NNUE readiness within 25 seconds on representative hardware; this is a target to test. Keep a readiness margin under 30 seconds even when the full target is missed. A timed thread join is not proof that the ready line is always timely: GIL contention and work after the join still matter. Report worst measured startup, not just the mean. Do not assume that `nogil=True` releases the GIL during compilation.

Reject changes that trade a small startup saving for the already measured 11–15% sustained slowdown. Retain the 21-second-join build if improvements fail. The proposed three-second join in the old handover moves more compilation onto our game clock and is only a contingency, not a speed improvement.

## 3. Train a better compact network with stronger decision labels

Keep the existing 1024-width inference layout for today's main experiments. Its training/export pipeline already works and every inference is CPU-bound. Reuse our own float checkpoints and exact feature/scaling conventions. Verify checkpoint availability first: the existence of an exported V8.5 net does not establish that its original float/optimizer state is available. If fc_b state is missing, use the verified own ancestor and exact continuation recipe, label that reconstruction accurately, and compare against its reproduced parent. More GPUs run independent arms; do not introduce an untested distributed trainer today.

Prioritize three arms, with a fourth only if it will export by 12:20:

| Arm | Initialization and change | Purpose |
|---|---|---|
| N0 | Existing bp336 export, no new training | Immediate strongest-screened candidate |
| N1 | Own fc_b checkpoint; broad deeper labels plus capped decision examples | Preserve established general play while targeting demonstrated errors |
| N2 | Own bp336 checkpoint; same verified fine-tuning data/schedule | Test whether broad pretraining plus better final labels compounds |
| N3, conditional | Continue own bp336 pretraining for a measured bounded budget, then established d7 alignment and fc_b fine-tune | Test whether the exposure trend extends; terminate if the export misses cutoff |

N1 versus N2 isolates initialization when data and optimization are matched. Compare each with its unmodified parent. Record exact start/end superbatch semantics: the historical fc_b recipe is start 97/end 104, not a newly restarted hot eight-superbatch schedule. Measure effective passes over unique examples. Never feed a small pilot repeatedly for hundreds of millions of updates and call it diversity.

Use the existing 35.46M-row clean corpus as the preservation base. Start at 95% broad data and 5% newly verified hard/leaf positions, with the exact mixture audited before training. This is a proposed starting setting, not a proven optimum. Most search leaves in the existing dump are dense, so balance sampling by phase rather than using raw dump frequencies. Keep check positions out of a quiet-only loader unless its semantics are deliberately changed and tested.

Spend CPU labeling effort on disagreement: positions where our current net, bp336 and a deep teacher rank plausible continuations differently; sacrifice compensation; defensive exchanges; pawn races; quiet checking combinations; and conversion choices. Include strong-play controls and broad middlegames. Trace each candidate continuation into quiet or stabilized leaves the deployed net actually evaluates. Standardize side-to-move/White score perspective, mate handling, scale and bound types.

Use depth 18–22 or a calibrated node budget as initial teacher effort, then deepen unstable comparisons. A requested depth is not ground truth. Use exact tablebase labels where applicable. Start with a throughput/quality pilot; create as many unique stable examples as can be labeled, checked and ingested before cutoff. Publish achieved counts, not an aspirational billion-position target.

Measure held-out move/continuation ranking and calibration by phase alongside loss. For today, preserve the established value-training objective. A new pairwise ranking loss is an attractive follow-on but requires a verified loader/trainer change; do not smuggle that change into N1/N2. Float/export/accumulator parity, all king/output buckets, numerical bounds and timed CPU performance precede games. Raw weight averaging across separately trained nets is not a valid shortcut.

## 4. Turn offline analysis into a more useful opening book

The existing book only extends four to six plies from many historical roots and averages roughly four hits. With abundant CPUs, test deeper preparation around its frequent exits. The 1,226 roots are an observed collection, not the unpublished complete finals opening set. Exact historical coverage is therefore conditional on roots recurring.

Keep the current book as control. Build one challenger that expands top plausible replies at frequent exits and transpositions, using fresh practice/public games to prioritize branches. Use several credible opponent continuations rather than a single predicted reply. Establish a baseline depth/coverage policy, then assign additional analysis by observed reach frequency, teacher uncertainty and the cost of our current exit mistakes. Stop low-value branching when byte or time budgets are reached.

For our move, compare a few independently checked sound alternatives. Prefer those that remain sound at deeper reference effort and that our actual timed engine handles well against the fixed panel. A favourable teacher score whose continuation requires precision our engine lacks is a poor practical exit. Include held-out response branches; do not score the book only on the lines used to build it.

Move research metadata out of the shipping table. Measure compact records plus index and exact state verification; a hash hit alone must not silently select another position's move. Preserve side, castling and en-passant semantics, legal move checks, and fullmove guards. Existing conservative en-passant skipping is acceptable for the first challenger. Audit repeated-position choices against game history so automatic book moves do not blindly choose a draw.

Optimize measured saved clock, exit quality and real-clock results per byte. Give the whole package a working ceiling of 47 MB, leaving margin for code/indexing changes. Allocate remaining bytes between the selected network, book and optional endgames after measuring their actual benefit; do not assume the maximum book is automatically best.

## 5. Two bounded additional opportunities

**Exact endgame assistance.** Inventory small complete Syzygy material classes plus capture/promotion dependencies. Prioritize those actually encountered and those with verified misplays. Root probing is the smallest integration. Use WDL and DTZ with the actual fifty-move counter, repetition history, cursed wins, promotions and missing-file fallback; [python-chess explains the dependency and DTZ requirements](https://python-chess.readthedocs.io/en/latest/syzygy.html). WDL alone at a nonzero halfmove clock is not a safe unconditional win label. Test progress over full endings, not just legal responses. If complete useful classes cannot fit, defer shipping tables; use them offline for labels. Do not assume all seven-piece tables fit or that an incomplete sample guarantees conversion. Root lookup cannot repair an earlier decision before a supported ending is reached.

**Selective tactical verification.** The global checking-move exemption was neutral, so do not simply switch it on again. If an independently implemented candidate can be ready by 12:20, test a bounded second search only when root best-move instability, a large score swing or a risky irreversible move triggers it. Reserve a small explicit share of the same total time, cap the verification budget, and compare with the unchanged search given exactly the same overall budget. Conflicting short searches are not automatically independent evidence; specify TT/history isolation. Require diverse held-out tactics and full-clock improvement. Otherwise close this lane without delaying release.

## 6. Optimize for knockout wins without guessing hidden match state

Compare contempt 20 and 40 for the shortlisted engine on development games. Report game score, wins, losses and the distribution of paired-opening scores. Estimate four-, six- and eight-game advancement by resampling whole opening pairs, with uncertainty and assumptions about opponents and opening distribution stated.

More decisive games help an otherwise equal underdog, but increased losses can outweigh the benefit. Do not maximize draw avoidance in isolation. The FEN/clock interface does not provide match score or opponent identity; do not invent score-aware behavior or persistent cross-game state. Use a fixed tested policy, informed by the confirmed bracket where available. Changes to draw utility also need TT-score consistency checks.

## 7. Schedule and release rule

| BST cutoff | Deliverable |
|---|---|
| Immediately | Exact compliant reference retrieved; live job states recorded; pair reporting corrected; benchmarked match/label workers; bp336 direct gate underway |
| 12:00 | Throughput and cold-start measurements; label pilot audited; N1/N2 running; deeper book branches building |
| 12:20 | Stop new candidate development; require immutable exported artifacts from each advancing lane |
| 12:20–12:40 | Development gates select components; test their combination to detect interactions; select exactly one release challenger |
| 12:40–13:20 | Fresh, untouched confirmation of that exact challenger versus compliant reference; target 2,000 games if measured fleet throughput supports it |
| 13:20 | Fixed decision; do not extend a losing/inconclusive experiment to search for a favourable result |
| By 13:30 | Verify exact ZIP/hash and finish the chosen upload workflow; inspect validation and the next available practice round |
| 13:30–14:00 | Reserved for platform problems and a verified compliant fallback |

Predeclare one primary comparison and its sample count after the throughput pilot, before reading confirmation outcomes. Proposed definition of demonstrated improvement: paired point estimate at least +10 Elo and 95% lower bound above zero, no candidate-attributable failures, and no material regression against the frozen opponent panel. The +10 threshold is a decision preference, not a predicted gain. With insufficient evidence, retain the validated reference or explicitly label a risk-taking selection as uncertain; do not call it proven stronger. Do not weaken the rule after looking at results.

Network-only and code-only wins do not establish that their combination wins. The final confirmation must use the exact combined source, network, book and settings. If it fails, use an already verified reference package; last-minute edits create a new candidate. Test startup failures, legal moves, clocks, memory, scratch and unpacked size through the exact archive. Zero observed failures is a release condition, not proof of zero future risk.

## If the deadline is extended

Extra time changes the opportunity set more than extra GPUs alone. With another day or more, add an own-trained small policy model for ordering root/shallow moves, value-network distillation at several CPU-efficient widths, pairwise ranking supervision with correct search-leaf alignment, iterative hard-example mining, and carefully isolated feature/architecture experiments. Train larger offline teachers from our own checkpoints where useful, then distill into the deployment architecture. Jointly tune search margins and time allocation for the selected net with held-out timed confirmation. These are research hypotheses, not suitable last-hour dependencies.

## Required handoff

Deliver the selected exact archive and SHA-256, reproducible source/config/training manifests, complete comparison results and uncertainty, failures and discarded arms, measured cold startup/first-move cost, and a compliant fallback. Record whether the platform actually accepted it. This planning task changes no engine implementation, starts no rentals/training and uploads nothing.
