# Astra Finals Plan — 11 September 2026

## Decision

Preserve V8.5 as the control. Make a controlled fine-tune the principal training experiment, alongside a bounded investigation of R108 and preparation for the newly revealed finals constraint. Do not make a new from-scratch pretrain the critical path. No upload or paid training was started by this review.

The aim is stronger move selection and reliable adaptation, not a promise of flawless chess. A GPU can train quickly; it cannot establish generalization or tournament strength by itself.

The invitation text supplied by the owner explicitly allows refinement on finals day. This corrects the earlier assumption that the qualification lock necessarily fixes the London build too. The public docs describe the locked qualification Swiss, but do not specify the new constraint or the on-day development window. Prepare now; verify what existing code, weights, books and external compute can be used when the final instructions arrive. Do not assume a qualification invite from ladder rank.

## Evidence reviewed

Read the FinalsDay link, refreshed the public top ten and their recent results, examined the new R107–109 PGNs/logs in Downloads, checked the existing intel reports and training record, and performed two bounded reference checks on R108. Earlier loss investigations remain relevant; this is not a new exhaustive audit of every historical move or every source file.

Sources: [qualifier ladder](https://aichessathon.com/leaderboard?stage=qualifier), [technical docs](https://aichessathon.com/docs), [rules](https://aichessathon.com/terms). Raw retrieved facts are in `public_snapshot.json`, fetched around 11:33 UTC after R109. Historical intel reports dated 09:18 use an earlier snapshot, incomplete Stockfish coverage and mixed build histories; do not treat them as current-build comparisons.

## Competition snapshot

Last ten means each team's last ten completed, non-void rated games, not a common opponent schedule. Ratings marked provisional by the page: Mite, BINI, Challenger, Loss Preventer, Astral, Gladiator, BetaGo and Sobriety. Ranking is not a confidence interval or proof of relative strength.

| Rank | Bot / team | Rating | Last ten W–D–L |
|---|---|---:|---|
| 1 | Patzer 2.4 / Gijs Smit | 2814 | 4–4–2 |
| 2 | Mite / Ryan Vincent | 2804 | 4–4–2 |
| 3 | BINI Alpha / Opus Carlsen | 2799 | 3–2–5 |
| 4 | Challenger / Stonkfish | 2742 | 4–6–0 |
| 5 | Loss Preventer / Lightning Tree | 2736 | 2–7–1 |
| 6 | ms | 2713 | 3–6–1 |
| 7 | Astral / omega3 fish | 2702 | 5–4–1 |
| 8 | AlphaFish / Gladiator | 2689 | 3–6–1 |
| 9 | BetaGo | 2689 | 1–9–0 |
| 10 | SoberCooper / Sobriety | 2667 | 3–7–0 |

BINI is only 15 rating points below first in this snapshot; the peak-to-current fall is not a direct measurement of code regression. Several rivals are drawing much more often and losing less in this small window. That supports studying defensive reliability, not changing contempt just to increase draws. Patzer beat Mite in R109 immediately after Mite beat us in R108: there is no evidence of an unbeatable opponent. Public results do not reveal opponents' network architecture, training recipe or private search logs. International ladder entries are not automatically London finalists; scope the eventual opponent set to confirmed participants.

## What the new games establish

- R107: win against Lubina. Site SF16/depth16 review: BINI 97.5% accuracy, 10 ACPL. Init 41.2 seconds.
- R108: loss against Mite. Site review: BINI 97.9%, 9 ACPL; Mite 98.9%, 5 ACPL. A high average accuracy score can coexist with a decisive missed defense. Init 42.6 seconds.
- R109: win against JBG fam. Site review: BINI 99.4%, 3 ACPL. Init 39.5 seconds.

These site metrics are shallow-reference summaries, not perfect move assessments. The two wins are useful preserved-good-play controls, not evidence that V8.5 caused an improvement. Build attribution must be matched to platform build IDs; startup duration alone cannot identify a build.

### R108: investigate move 39, not merely the later evaluation collapse

Queens came off at move 11. At **39.g5**, BINI searched depth 21, scored −20, and had about 49.5 seconds before the move. The site's reference changes from approximately equal to −1.39 pawns. Our separate full-history, 500,000-node reference check prefers **39.fxe3**, capturing the rook, at 0.00 and scores the played g5 at −1.96. Its drawing line simplifies through captures into a king ending. These are finite-search estimates; see `r108_reference_checks.json` for depths and method.

BINI subsequently scored 41.Rh7+ at −20 even at depth 27, before falling to −104 on 42.g6. The first clear reference disagreement precedes the logged collapse. Investigating only moves 42 onward would target the symptom too late. The repeated −20 is also a reason to trace draw utility, repetition and TT provenance rather than assume it is a raw NNUE score. This example broadens the target beyond queen attacks to passed pawns, material imbalance, simplification and defensive liquidation. It does not prove the same mechanism caused every previous loss.

## Exact work order for the coding agent

### 1. Establish the baseline and a faithful replay — first 60–90 minutes

Freeze the exact V8.5 archive and its source/weight/config hashes. Save the full float checkpoint and optimizer state for every future experiment on two independent locations; archive export code and data manifests too. Keep the qualification submission untouched.

Replay R108 from the supplied initial FEN with every actual move and the correct history bounds. If the engine proposes a different move, explicitly advance its internal board/history with the recorded game move; do not silently reset to FEN or leave inconsistent state. Verify FEN and history before each call. Exact live TT reproduction may remain unavailable; label reconstructed warm state as reconstructed, never identical.

At moves 37–42, record scores and PVs for the played move and holding alternative, raw NNUE at comparable nodes, correction contribution, draw-return reason, TT cutoff source/bound/depth, and whether the iteration completed. Follow the PV leading to −20. Compare cold/reconstructed-warm state and targeted diagnostic variants, changing one mechanism at a time. Repetition reached in a search path is not automatically the referee's threefold claim. Keep mate, draw utility and centipawn reporting distinct.

Use R103/35, R104 conversion decisions, R105/41 and R100/29 as additional cases, respecting the existing limitations of each reproduction. An inconsistent ablation does not rule out search. A large discrepancy from Stockfish does not alone prove a network bug. Require a reproducible move-ranking or bound error before proposing a search repair. Timebox investigation; produce a cause/evidence/uncertainty table even if unresolved.

### 2. Restore trainability and run a small data pilot — next 1–3 hours

First seek fc_b-104's original float checkpoint, then the k96-96 ancestor. The local exported networks exist, so losing one checkpoint does not make all training impossible. If only quantized fc_b weights remain, a dequantized initialization is an experiment with new optimizer state, not exact continuation: verify feature indexing, king buckets, perspective, scaling, activations and export round-trip parity before training. Do not import a third-party pretrained chess network.

Keep the current 1024 architecture initially. Do not retry a wider network solely because GPUs are available: match inference remains CPU-bound. Reproduce an export and short training step before commissioning a large labeling run.

Start with a stratified 5,000-position labeling benchmark to measure throughput and score/move stability. Include quiet positions, tactical positions, queenless material imbalances, defensive exchanges, conversion positions, and king/pawn/rook endings. Label best and plausible competing moves at a fixed compute budget; deepen ambiguous or unstable cases selectively. Depth 18–20 is a starting budget, not a guarantee of correct labels. Use exact tablebase labels where applicable.

Do not call every capture-best position 'sharp'. Audit the actual training loader and proportions. Split by source game/opening family and deduplicate across splits. The published loss positions are development examples; keep unrelated games and positions genuinely held out. Preserve R107/R109 as explicit regression controls, recognizing that repeated inspection makes them development controls too.

### 3. One controlled fine-tune experiment — same day

Run an unchanged-distribution continuation control and a modest hard-position mixture at the same training budget and learning-rate schedule. A 5–10% hard-example mixture is a starting experiment, not an established optimum; earlier aggressive endgame enrichment lost strength. Keep most broad data, avoid repeated exposure to a tiny loss corpus, and compute effective passes over unique examples rather than relying on superbatch names. Cap candidate count before inspecting results.

The actual local `train_fc_b.log` reports eight roughly 100M-position superbatches in 5m18s on an RTX 5090. That shows the update itself can be minutes once the pipeline works. It does not establish today's hardware availability, labeling speed or end-to-end ETA. Benchmark those first. Reserve most of the working day for data verification and timed testing, not GPU epochs.

Only consider a new from-scratch pretrain as a secondary experiment after the continuation pipeline works, broad data is verified, and enough time remains for completed validation. Do not make tomorrow depend on it. Do not combine a new architecture, data mixture, loss function and search changes into one candidate.

### 4. Strength and correctness validation — allow 3–6 hours after candidates exist

Require export/parity checks across all eight output buckets, random incremental-versus-full NNUE comparisons, existing terminal/repetition tests, legal move handling, resource limits and zero fallback. Verify the exact package, not just a development directory.

Use fixed-node tests to screen. Make shipping decisions on completed paired, color-swapped real-wrapper games at the applicable clock, with book settings controlled, immutable package hashes and per-game checkpointing. Isolate timed CPU workers from labeling and other heavy jobs; determine concurrency with a smoke run. Test against V8.5 and an available diverse reference pool, including a weaker same-width net for conversion. Public opponent PGNs are not executable opponents.

Predeclare sample size, pairing-aware confidence method, candidate count and acceptance rule. A non-inferiority result licenses at most a bounded strength-risk claim; it is not a demonstrated improvement. Use a fresh confirmation set for the selected training candidate. A training loss decrease or solving five known blunders is insufficient. If no candidate wins on completed evidence, retain V8.5.

### 5. Prepare for the revealed constraint — before tomorrow

Build a small, documented configuration surface for clock/increment, init, memory/TT size, model path and book availability. Preserve baseline behavior by default. Prepare a benchmark runner that accepts the revealed limits and reports cold startup, memory, move latency, completed depth, legal moves and fallback counts. Hypothetical tighter clock, memory or book rules are contingency cases, not announced constraints.

Keep V8.5 and at most one validated stronger candidate ready. A smaller own-trained fallback is useful only if already available and tested; do not add another speculative training project solely for an imagined restriction. On reveal, first run compliance/resource smoke tests, then tune only the affected subsystem and compare at the actual clock. Reserve the final 60–90 minutes before the announced freeze for exact-package validation and submission; use the actual available window if shorter.

Prepare a short presentation with architecture, authorship/training provenance, one genuine failure investigation, measured tradeoffs and validation. The team must be able to explain the model and engine it ships.

## Secondary opportunities, ranked below the main work

1. **Selective endgame tablebases:** inventory complete small material classes and dependency closure against the remaining ZIP budget; test WDL/DTZ, fifty-move context, missing files and runtime overhead. Current docs allow endgame tables within seven pieces and the total size limit. R108 reaches five pieces only after a substantial disadvantage, so tablebases are not an established cure for move 39. Do not build a whole project around an assumed rescue.
2. **Profiled CPU savings:** use the actual x86 target to measure accumulator updates, refreshes, move generation and TT traffic. Only implement a local optimization after profiling identifies a hotspot; require numerical/move parity and a timed benefit. More nodes per second does not guarantee better moves. Reusing 1024-width inference is lower risk than a new architecture overnight.
3. **Book consistency:** inspect legal keys, castling/en-passant state, allowed move-number range and fresh-analysis exit quality. Deep opponent preparation in R108 gives a visible clock advantage, but the early queen trade was not itself shown losing. Do not replace the book wholesale after the previous negative gate without new paired evidence.

## Reports required before any recommendation to upload

Return exact build hashes; recovered checkpoint/data provenance; R108 cause table; candidate training exposure and held-out results; completed paired game results and uncertainty; startup/resource results under the finals limits; failed experiments; and one recommendation with a fallback. Never write 'flawless', 'the only possible fix', or 'proven stronger' when the evidence does not establish it. No autonomous upload.
