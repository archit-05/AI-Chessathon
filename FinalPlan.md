# Final Plan — 12 September 2026

Revised against repository commit `2d78e2cb`, including the V11 evidence introduced in `6cc77c3c`, and the user's update that three A40s are available. `git pull --ff-only origin main` was already up to date at this revision. This is an execution plan, not a report of newly trained models. Hardware availability is user-reported; SSH connectivity, installed assets, live jobs and current platform deployment have not been inspected. Preserve `GrigoryMorning.md` as the historical handover.

## Objective and decision

Maximize the probability of winning the knockout. Pursue a materially stronger complete engine, with the existing network as the control. Unlimited development compute enables more preparation, better labels and much stronger measurement; it does not remove deployment limits, experimental uncertainty or the submission deadline. No numerical Elo gain or undefeated result is promised.

Assume today's 14:00 BST freeze unless the team supplies a changed deadline. The public rules still confirm it. The user requests maximum performance/velocity and has three A40s available. One pod's supplied profile is nine Xeon Gold 6342 vCPUs, 50 GB host RAM and 300 GB container disk; verify the other pods separately. Finish model exports by 12:30, select one release challenger by 12:45, and reserve the end for confirmation and platform validation. Missed intermediate deadlines shrink the candidate set; they do not move the final deadline.

The immediate strategy is V11 runtime correctness plus the strongest of the existing bp336 network and three focused, same-architecture training candidates. External CPUs test networks while each A40 runs one independent arm. Faster startup and deeper opening preparation remain independent opportunities when ready early enough. New endgame integrations and search mechanisms move off today's critical path: model comparisons need stable code and enough completed games.

## What changed in this revision

1. V11 replaces V10 as the comparison and release foundation. V10's first searched move double-charged compilation time and often searched only 4,096 nodes at depth 6. Recorded V11 pod runs searched roughly 0.74–0.92 million nodes at depth 15–16 after compilation. Platform V10 acceptance is recorded; platform V11 acceptance is not established by the files read here.
2. Both recorded V11 archives have different `bini_engine.py` hashes, despite the handover describing a net-only comparison. Inspect that source difference before interpreting the gate; it might be harmless, but its effect is currently unknown. Construct both comparison packages from one verified V11 source tree, changing only the network.
3. Three A40s run three independent arms. Shared training across GPUs adds pipeline changes without demonstrated benefit in the remaining window. The nine-vCPU profile is known for only one pod; do not assume 27 dedicated physical CPU cores.
4. Replace a blanket 5% hard-example mixture with an exposure cap based on unique checked examples. A small deeply labeled set must not be repeated hundreds of times merely to meet a mixture percentage.
5. Existing scripts are references, not universal launch commands: `run_onday_ft.sh` restarts a hotter schedule, `screen_one.sh` has incomplete lane mapping, and `build_packages.py` can include an `nbcache/` directory. Handle these explicitly before execution.

## Three A40s: allocation and first ten minutes

The supplied three-minute uptime is a reason to verify staging, not evidence that the old pod's checkpoints/data are present. No new SSH endpoints were supplied; reuse an old endpoint only after confirming its identity.

- Verify GPU identity/VRAM with `nvidia-smi`, CUDA/trainer compatibility, CPU quotas/throttling, free RAM, disk and volume persistence. The reported 50 GB is host RAM, not GPU memory. Inspect existing jobs before changing their scheduling.
- Stage only V11 source/archive, both baseline exports, the required float checkpoints with optimizer state, trainer/exporter, clean corpus and checked candidate data first. The 35.46M-row binary at 32 bytes per row is approximately 1.13 GB; verify actual size and checksum. Transfer the approximately 22 GB shuffle and 52 GB binpacks only to the third arm if its longer recipe is feasible.
- Run one training process per A40. Start with the established batch size 16,384 and four loader threads per pod, benchmarking six if loading limits GPU utilization. Keep resources for orchestration/exports. No Stockfish labeling or large CPU match gates during the throughput pilot.
- Use a throwaway short pilot to measure completed steps/second, peak VRAM/RAM and export time. Keep the original batch size unless measurements require a documented change. Stream data using the established loader rather than loading all corpora into host RAM.
- Keep at least 60 GB disk headroom on a 300 GB pod. Mirror chosen checkpoint/optimizer states, manifests, logs and exports to a second host. Verify container-disk persistence before relying on it.
- Publish staging + training + export/parity + gate estimates. Artifacts must exist by 12:30. If new labels are not ready, advance existing bp336 and a predeclared schedule/control experiment; do not disguise an old unsuccessful data mixture as a new hypothesis.

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
| V11 first-move accounting | Pod ready line 21.8 s; first search depth 15–16 following compile wait | Required reference behavior; V10 validation alone is insufficient |
| Compilation structure | 73 dispatchers, 186 specializations in recorded census; HCE and NNUE reachable from production search | Profile unnecessary compilation and type proliferation |
| R113 tactical miss | Local checking-move exemption fixes known example, aggregate screen neutral | Known-position success alone cannot justify enabling it globally |
| R108 defensive miss | Existing diagnostic points toward misjudged ending continuation | Train and test defensive liquidation/compensation decisions; do not assume more depth cures it |
| Contempt 40 | Timed +10.4 [−16.1, +37.0]; original lower-bound rule was relaxed | Treat as an uncertain policy choice, not a proven strength gain |
| Endgame correction fix | Mechanism identified; full timed gate incomplete in handover | Fetch completed results before treating it as accepted evidence |

The handover references V11 ZIPs in the repository root, but they are absent in this local checkout. Retrieve remote packages and verify against `FinalsDay/night_evidence/packages_manifest.txt`: V11 V8.5-net SHA-256 `95897ef6d8f86e92afcd47add4b0f05ac65457f4b452f705177b3a2ca2ab32cb`; V11 bp336 SHA-256 `0cd05c03202610bed3e6bd668115ebc2898d932010c7859257336d41b042ac9d`. These identify existing artifacts, not a newly normalized comparison pair. After resolving the differing engine source, rebuild and record new hashes. A mutable filename such as `PrometheusBuild.zip` is not sufficient identity.

## 1. Build a trustworthy test fleet first

Use one verified V11 source/configuration for both V8.5 and bp336, including the first-move accounting fix. Require identical non-weight hashes. Bare V8.5 is not a valid finals-clock comparator because startup failures contaminate the result. V10-wrapper results remain historical evidence: even a symmetric bug can interact differently with two networks. Do not pool them into final V11 confirmation.

Fix the reporting path before aggregating more workers. In `night_evidence/merge_gate.py`, rows are grouped solely by FEN; the first two scores are used when any two exist. Repeated roots can discard later games or combine the same candidate colour. Voids and unknown results also currently become half-points. These are code findings, not proof that a particular existing report is wrong.

The replacement report must:

- Record immutable candidate/opponent hashes, run ID, explicit pair ID, opening ID, candidate colour, seed, host/CPU, clock and init limits for each game.
- Verify one game of each colour per pair; deduplicate retries; separately list unfinished, void and failed games. Do not reclassify failures into normal chess draws.
- Retain every valid complete pair; cluster repeated opening families when calculating uncertainty. Different seeds do not make repeated deterministic games independent evidence.
- Separate development and untouched confirmation openings by root family/source game. Keep known regression positions outside the unseen-strength claim.
- Report W/D/L, paired confidence intervals, timing/failures, book coverage and performance by CPU class and opponent. Use x86 representative of the platform for the primary shipping decision; ARM results are supporting evidence.

Use paired-outcome statistics, as described in [Fishtest's methodology](https://official-stockfish.github.io/docs/fishtest-wiki/Fishtest-Mathematics.html). Fix sample sizes and candidate selection before results. Repeatedly checking an ordinary confidence interval and stopping on a win is not an equivalent sequential test.

The three A40s address training parallelism. The next resource priority is a ready x86 match fleet, targeting 512 dedicated physical cores in independently verifiable allocations, followed by 64–256 separate label-generation cores. Expand labeling only while outputs can reach a training arm before cutoff. Dispatch the first working match shard immediately; do not wait for the entire fleet. More GPU capacity is secondary until these dependencies are met.

Benchmark provisioning, data transfer and finished games/core-hour immediately. At five to six minutes per game slot, 512 slots provide roughly 5,100–6,100 games/hour before overhead; startup, tails and contention reduce that. Measure, do not promise that throughput. Pin/schedule agent execution to reproduce a single active core and prevent concurrent startup workloads from creating artificial init losses. Keep CPU labeling off match hosts. Three nine-vCPU pods, even if their profiles match, do not provide the planned thousands of full-clock games in this window. Report allocated physical cores/CPU quotas separately from advertised vCPUs.

Test against the compliant V8.5 control, a fixed diverse panel of our own archived engines, and offline reference engines calibrated to produce informative competitive results. Freeze reference budgets after a pilot. Do not reuse the meaningless nominal Stockfish-2400 setup that lost 60/60. These references are test opponents, never submission code. Opponent PGNs inform scenarios but cannot reproduce opponents' private agents.

## 2. Recover startup time without weakening search

After incorporating V11's first-move fix, run at most two isolated source experiments, each bounded by the 12:30 artifact cutoff and only with separate execution capacity that does not delay model work:

1. Normalize redundant scalar argument types/array layouts at proven duplicate call sites. Preserve signedness, bitboard width, overflow semantics and board representation. Start with the largest repeated specializations, not arbitrary global casts.
2. Build an NNUE-only production search compilation path. `evaluate()` currently retains a call to the classical evaluator, and warm-up runs both modes. Remove the unused compiled HCE branch from this candidate while keeping the existing Python emergency fallback. Audit other call sites so HCE is not still compiled elsewhere.

The hypothesis is less code to compile, not a guaranteed number of seconds saved. Merely deleting an extra warm-up call may save nothing because Numba compiles reachable functions. Explicit signatures can avoid additional specializations but can also change conversions or compilation order; [Numba documents these semantics](https://numba.readthedocs.io/en/stable/user/jit.html).

Measure cold import, ready line, full NNUE readiness, first legal reply, steady search speed and peak memory on production-version Python/Numba. Use fresh interpreters and scratch, read-only extracted package files and no development environment overrides. Include all special moves and both colours. Test numerical and fixed-node move parity for changes intended to preserve behavior, plus the existing correctness suites.

Target full usable NNUE readiness within 25 seconds on representative hardware; this is a target to test. Keep a readiness margin under 30 seconds even when the full target is missed. A timed thread join is not proof that the ready line is always timely: GIL contention and work after the join still matter. Report worst measured startup, not just the mean. Do not assume that `nogil=True` releases the GIL during compilation.

Reject changes that trade a small startup saving for the already measured 11–15% sustained slowdown. Retain the 21-second-join build if improvements fail. The proposed three-second join in the old handover moves more compilation onto our game clock and is only a contingency, not a speed improvement.

## 3. Train a better compact network with stronger decision labels

Keep the existing 1024-width inference layout for today's main experiments. Its training/export pipeline already works and every inference is CPU-bound. Reuse our own float checkpoints and exact feature/scaling conventions. Verify checkpoint availability first: the existence of an exported V8.5 net does not establish that its original float/optimizer state is available. If fc_b state is missing, use the verified own ancestor and exact continuation recipe, label that reconstruction accurately, and compare against its reproduced parent. More GPUs run independent arms; do not introduce an untested distributed trainer today.

Run three training arms, one per A40, alongside immediate external CPU tests of N0. This is the development candidate budget; checkpoint selection stays on development data.

| Arm | Initialization and change | Purpose |
|---|---|---|
| N0, external CPU tests | Existing `bp336_d7_ft` export in normalized V11 | Strongest-screened candidate already available; test immediately |
| N1, A40 A | Own `bp336_d7-12` aligned checkpoint; new verified mixed corpus; start-97/end-104 fine-tune | Strong pretraining plus better final decision labels |
| N2, A40 B | Own `k96-96` checkpoint; exactly N1's corpus and fine-tune schedule | V8.5's lineage with the same new data |
| N3, A40 C | Own raw `bp336-336`: at most 16–32 further superbatches if staged data and timing allow, then established 12-superbatch d7 alignment and eight-superbatch final fine-tune | Additional broad exposure; all stages must export by 12:30 |

N1 versus N2 holds fine-tuning data and schedule fixed while comparing two pretraining lineages. Optimizer history also differs; attribute results to the whole initialization. Compare N1 with N0, and N2 with V8.5. Verify checkpoint stage: `bp336-336`, `bp336_d7-12` and `bp336_d7_ft-104` are not interchangeable.

If A40 C lacks staged binpacks/shuffle or its total ETA misses cutoff, select its alternative before seeing results: `bp336_d7-12` on N1's corpus with eight superbatches and a linear LR schedule from 5e-5 to 1.2e-6. This is an experimental stronger update, not a proven recipe. Name it `N3_lr`; do not run both N3 alternatives and silently choose the winner. If new labels are unavailable, use unchanged clean data and label this a schedule-only experiment.

For the pretraining alternative, retain binpack eval scale 249.8, filters and mandatory alignment. The scheduler uses absolute superbatch/end indices: extending the endpoint changes the effective learning rate. Print first/middle/final rates before launch; copying old flags with a new end index is not schedule-neutral. Benchmark the entire three-stage pipeline.

The historical fc_b recipe uses start 97/end 104 and nominal LR 0.0005 near the cosine floor. `run_onday_ft.sh` instead restarts at superbatch 1 with LR 0.0003; do not use it unchanged for N1/N2. Trainer defaults are 16,384 × 6,104 = 100,007,936 examples per superbatch, approximately 800M exposures for eight superbatches. Record effective passes over unique examples.

Use the existing 35.46M-row clean corpus as the preservation base. Let B be its unique count and D the new unique checked examples after deduplication. Set hard-example fraction p = min(0.05, 2D / (B + 2D)). This proposed guard caps average reuse of a hard example at twice that of a broad example. For D = 100,000 and B approximately 35.46M, p is about 0.56%, not 5%; at one million new examples the 5% ceiling applies. Check actual loader sampling, not just output-file rows. This is an experimental exposure limit, not a proven optimum.

Audit score/phase/source distributions and retain the existing 4.5% extreme-score rejection threshold. Earlier 3–5% site/spice experiments were near neutral: N1/N2 need newly verified disagreement/continuation labels to test a different hypothesis. Stratify dense search leaves by phase. Keep check positions out of a quiet-only loader unless its semantics are deliberately changed and tested.

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

These are secondary designs. Start a new integration today only if dedicated execution capacity can finish it by 12:30 and preserve the model-testing schedule. Otherwise retain the current endgame fix and search behavior for this final.

**Exact endgame assistance.** Inventory small complete Syzygy material classes plus capture/promotion dependencies. Prioritize those actually encountered and those with verified misplays. Root probing is the smallest integration. Use WDL and DTZ with the actual fifty-move counter, repetition history, cursed wins, promotions and missing-file fallback; [python-chess explains the dependency and DTZ requirements](https://python-chess.readthedocs.io/en/latest/syzygy.html). WDL alone at a nonzero halfmove clock is not a safe unconditional win label. Test progress over full endings, not just legal responses. If complete useful classes cannot fit, defer shipping tables; use them offline for labels. Do not assume all seven-piece tables fit or that an incomplete sample guarantees conversion. Root lookup cannot repair an earlier decision before a supported ending is reached.

**Selective tactical verification.** The global checking-move exemption was neutral, so do not simply switch it on again. If an independently implemented candidate can be ready by 12:20, test a bounded second search only when root best-move instability, a large score swing or a risky irreversible move triggers it. Reserve a small explicit share of the same total time, cap the verification budget, and compare with the unchanged search given exactly the same overall budget. Conflicting short searches are not automatically independent evidence; specify TT/history isolation. Require diverse held-out tactics and full-clock improvement. Otherwise close this lane without delaying release.

## 6. Optimize for knockout wins without guessing hidden match state

Compare contempt 20 and 40 for the shortlisted engine on development games. Report game score, wins, losses and the distribution of paired-opening scores. Estimate four-, six- and eight-game advancement by resampling whole opening pairs, with uncertainty and assumptions about opponents and opening distribution stated.

More decisive games help an otherwise equal underdog, but increased losses can outweigh the benefit. Do not maximize draw avoidance in isolation. The FEN/clock interface does not provide match score or opponent identity; do not invent score-aware behavior or persistent cross-game state. Use a fixed tested policy, informed by the confirmed bracket where available. Changes to draw utility also need TT-score consistency checks.

## 7. Schedule and release rule

| BST cutoff | Deliverable |
|---|---|
| Immediately | Retrieve V11; resolve differing engine hashes; record live jobs; repair pairing; start N0 games on first ready workers |
| 12:10 | Three pod identities/assets verified; label snapshot frozen for N1/N2; throughput pilots complete; choose N3 recipe by total ETA |
| 12:10–12:30 | Three independent A40 arms; export/parity as each finishes; external CPUs begin development games immediately |
| 12:30 | Stop new candidate development; require immutable exported artifacts from each advancing lane |
| 12:30–12:45 | Select components on development evidence; test interaction candidates; select exactly one release challenger |
| 12:45–13:20 | Fresh, untouched confirmation of the exact challenger versus normalized V11 V8.5 reference; target 2,000 games if measured throughput supports it |
| 13:20 | Fixed decision; do not extend a losing/inconclusive experiment to search for a favourable result |
| By 13:30 | Verify exact ZIP/hash and finish the chosen upload workflow; inspect validation and the next available practice round |
| 13:30–14:00 | Reserved for platform problems and a verified compliant fallback |

Predeclare one primary comparison and its sample count after the throughput pilot, before reading confirmation outcomes. Proposed definition of demonstrated improvement: paired point estimate at least +10 Elo and 95% lower bound above zero, no candidate-attributable failures, and no material regression against the frozen opponent panel. The +10 threshold is a decision preference, not a predicted gain. With insufficient evidence, retain the validated reference or explicitly label a risk-taking selection as uncertain; do not call it proven stronger. Do not weaken the rule after looking at results.

Network-only and code-only wins do not establish that their combination wins. The final confirmation must use the exact combined source, network, book and settings. If it fails, use an already verified reference package; last-minute edits create a new candidate. Test startup failures, legal moves, clocks, memory, scratch and unpacked size through the exact archive. Zero observed failures is a release condition, not proof of zero future risk.

Use a predetermined dispatch set and allow for long games. Do not fill a sample with only the first finishing pairs: game duration can correlate with outcome. Report unfinished assignments and their potential effect; a badly incomplete confirmation is inconclusive. Until the larger fleet is live, reduce candidate count and announce the smaller achievable sample before looking at outcomes.

## Execution checks derived from the actual scripts

- `screen_one.sh` routes generic `bp*` names to `c_lane.status`; it has no explicit bp336/new-arm completion mapping and waits for other node gates. For N1/N2/N3, dispatch by immutable artifact hash and explicit job status; do not invoke an old queue script expecting it to recognize new names.
- Several launch scripts use `set -u` and pipelines through `tee`. An apparent final success message is not sufficient: check training, exporter, parity and transfer exit status independently, require artifacts and hashes, and make execution wrappers fail on pipeline errors. Remote failures must not leave a stale net eligible for promotion.
- `build_packages.py` automatically adds files under `nbcache/` when present. The rule-compliant release path must explicitly reject native cache files rather than relying on the directory being empty. Inspect ZIP members and unpacked size before uploading.
- A40 training success does not verify the deployment interpreter. Run exact ZIP tests with the documented production stack and no development environment overrides. Keep the correct first-move clock in the test; report the old battery's artificial five-second first-call timeout separately from a tournament-clock failure.
- For every network log float-checkpoint hash, optimizer provenance, corpus hash/unique counts, LR sequence, example exposures, exporter revision, exported hash, numerical bounds and V11 source hash. The release report must establish these identities before combining worker results.

## If the deadline is extended

Extra time changes the opportunity set more than extra GPUs alone. With another day or more, add an own-trained small policy model for ordering root/shallow moves, value-network distillation at several CPU-efficient widths, pairwise ranking supervision with correct search-leaf alignment, iterative hard-example mining, and carefully isolated feature/architecture experiments. Train larger offline teachers from our own checkpoints where useful, then distill into the deployment architecture. Jointly tune search margins and time allocation for the selected net with held-out timed confirmation. These are research hypotheses, not suitable last-hour dependencies.

## Required handoff

Deliver the selected exact archive and SHA-256, reproducible source/config/training manifests, complete comparison results and uncertainty, failures and discarded arms, measured cold startup/first-move cost, and a compliant fallback. Record whether the platform actually accepted it. This planning task changes no engine implementation, starts no rentals/training and uploads nothing.
