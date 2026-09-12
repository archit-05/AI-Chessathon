# Overnight Plan

## 1. Strategy and the gap to close

The gap is that we still choose losing moves in some positions where a stronger engine finds a defence or a win, and we have not yet demonstrated a replacement that makes those decisions better at the actual match clock. Fixing the rules made us more correct, but winning requires better move selection; the evidence points to evaluation weaknesses and some search misses, without proving one universal cause or revealing our rivals’ private engines. We should therefore keep V8.5 as the control and run three focused improvements alongside it: train on a large, varied corpus with deeper, checked labels for difficult attacks, sacrifices and defensive positions; build and validate the permitted Stockfish opening book; and test whether spending more of the clock at genuinely difficult decisions improves results. Use GPUs for controlled training candidates and separate CPUs for labeling and matches, preserve unseen positions and games for evaluation, and compare each change before testing the combined build against strong opponents at tournament time controls. Choose the network that produces the strongest whole engine, including its search-speed cost—not the largest network or the lowest training loss. Because tied matches favour higher seeds, measure outright two-game match wins as well as average score. Our route to winning is to turn better data and preparation into demonstrably better decisions, then finish the validation before the deadline; more hardware helps us do that faster, but cannot guarantee the result.

## 2. Engineering directive

### Objective, baseline and rules

Treat tonight’s objective as maximising our probability of winning the finals with an evidence-backed, reproducible build: preserve V8.5 and its exact archive, configuration and weight hashes as the control, first verify the latest finals rules, opening-book permissions, resource limits and match-tiebreak semantics, then work in isolated candidate directories with a fixed cutoff that leaves enough time for a completed combined-build gate and packaging.

### Reconstruct the failures

Reconstruct the critical decisions from the downloaded losses and missed wins using the actual starting FEN, played move history, remaining clock and deployed version; distinguish exact live-state reproductions from approximations where TT or history state is missing, and identify the earliest consequential mistake rather than merely the eventual evaluation collapse.

### Establish the mechanism

For each reproducible failure, compare the played move and credible alternatives using independent deeper Stockfish analysis with score perspective, bounds and depth stability checked; inspect root scores, searched continuations and relevant pruning decisions to separate evaluation misranking, search omission, repetition handling and inadequate time, and do not declare any category universally responsible because one ablation failed.

### Three improvement tracks

Run three bounded improvement tracks in parallel where resources permit:

- **Evaluation:** using the verified training pipeline for a substantial new pretrain plus a smaller continuation control, with corpus deduplication, distribution profiling, game/source-separated validation, deeply relabeled tactical and defensive examples, representative quiet/endgame controls, and our known failures confined to training or explicit regression sets rather than counted as unseen evidence
- **Opening preparation:** building a rules-compliant Stockfish book with bounded branching through plausible opponent replies, a capped compute budget, stable move selection, exact position-key semantics including castling and en-passant, legal-move validation, safe out-of-book fallback and measured coverage on withheld roots
- **Time allocation:** first checking whether unused clock reflects genuinely missed opportunities rather than short or already decided games, then testing one capped spending adjustment with a hard deadline margin through the real wrapper.

### Keep experiments interpretable

Keep speculative search changes separate and advance them only when a reproducible mechanism survives negative controls; do not bundle increased contempt, reduced pruning, a new net and a new book into an uninterpretable candidate.

### Compute and recovery

Benchmark the actual trainer before scaling GPU rentals within the authorised budget, run independent jobs per GPU unless distributed training is already validated, keep labeling and match workers from contending, and checkpoint training state and every completed game off-host.

### Validation and candidate selection

Select candidates by exported integer-network parity, accumulator and terminal-state regressions, startup time, peak memory, package size and actual CPU search performance—not training loss alone—then use fixed-node tests only to screen, followed by completed, colour-paired real-clock comparisons on identical openings against the baseline and a fixed strong-opponent panel; predeclare the selection criterion and sample budget, report uncertainty and two-game match advancement under the verified tiebreak, audit zero fallbacks and timeouts, and never promote a partial result or treat non-inferiority as demonstrated improvement.

### Final build and handover

Finally, test the exact combined archive because individually useful changes can interact, deliver its full hashes, reproducible commands, completed results, unresolved risks and rollback archive, and recommend the strongest supported candidate while retaining V8.5 if the evidence does not justify replacing it; do not upload without explicit authorisation, and spend the night pursuing measurable improvements in move selection rather than promising a flawless engine or a guaranteed win.

## 3. Overlooked avenues to investigate

The most overlooked possibility is that we are optimising the wrong intermediate targets. More accurate scores, more nodes and more training data are useful only when they change a consequential decision for the better. Several approaches below could expose that gap. I cannot establish that the team has never tried them, but they are not demonstrated in the reports you shared.

| Overlooked avenue | What to do concretely | Why it could matter |
| --- | --- | --- |
| 1. Train on the positions our search actually evaluates | Instrument a small, representative set of searches and sample their leaf positions—including rejected variations. Compare those positions with the training corpus, then deeply label a balanced subset. | Actual game positions may differ substantially from the positions the network sees inside search. A huge new corpus could preserve that mismatch. |
| 2. Teach the distinction between two moves | Build examples containing a position, a verified holding/winning continuation and a plausible losing continuation. Test an auxiliary ranking objective alongside the existing evaluation loss, with consistent score perspective and unseen-game validation. | Our reported failure is often “cannot distinguish the good move from the bad move.” Average prediction error does not directly measure that ability. |
| 3. Audit the exact interface between training and search | Compare floating-point inference, exported integer inference, a fully rebuilt accumulator and the incrementally updated accumulator on the same positions and move sequences. Include captures, promotions, castling, bucket changes and unmake operations. | Before spending heavily on training, establish that the deployed engine receives the evaluation the trainer intended. Existing passing tests reduce this risk but do not replace representative sequence testing. |
| 4. Run controlled interventions to establish causality | In a diagnostic build, force the independently verified good root move to receive a full search; separately trace and selectively override suspect leaf evaluations. Record which intervention changes the decision. | If fully searching the good move still rejects it, that implicates evaluation downstream. If it becomes best, move ordering or selective search deserves attention. This is stronger evidence than “more depth did not help.” |
| 5. Choose openings our engine can actually handle | Among objectively sound book alternatives, play out the resulting positions with our engine against a fixed opponent panel. Measure conversion, defensive failures and match results on held-out openings. | Stockfish’s favourite position may require precision our engine lacks. Preparation should deliver positions where our engine plays well, while preserving objective soundness. |
| 6. Investigate selective verification instead of global extra thinking | Test a small, capped verification budget before irreversible decisions: a sacrifice, liquidation or move whose score depends on a narrow tactical line. Require measured benefit over simply giving the normal search the same total time. | The opportunity may be a second look at a few consequential decisions—not spending more on every move. This is a hypothesis, not a reason to add an untested heuristic. |
| 7. Use exact endgames as an offline microscope | Use tablebases to assess suitable endgame positions and counterfactual alternatives, with fifty-move semantics handled correctly. Separate genuinely missed wins from unavoidable draws. | Exact outcomes can expose evaluation and search errors without relying on another engine’s approximate centipawn score. This requires no tablebases in the submission. [Python-chess documentation](https://python-chess.readthedocs.io/en/stable/_modules/chess/syzygy.html) |
| 8. Make the experiment more informative before making it larger | Preserve colour-swapped opening pairs, analyse results at the pair level, and maintain both a representative match set and a separate diagnostic challenge set. Reserve untouched confirmation games for the selected candidate. | We could be spending scarce CPU hours obtaining noisy or selection-biased answers. Stockfish’s testing framework explicitly accounts for paired outcomes. [Fishtest methodology](https://official-stockfish.github.io/docs/fishtest-wiki/Fishtest-Mathematics.html) |

## 4. Immediate priorities

The first avenue is the one I would investigate immediately. We have repeatedly discussed deeper labels, but “deeper labels for the right positions” is the actual requirement. If the network was mostly trained on ordinary positions and the search routinely asks it to judge unusual tactical continuations, another billion ordinary examples may barely touch the weakness.

The second priority is the causal experiment in row 4. “The net is wrong” and “the search never properly examines the defence” demand different fixes. We should make the engine reveal which mechanism applies to each failure before assigning the entire overnight budget to one explanation.

I would run those two investigations while the established pretrain proceeds, then use the findings to steer its data and select a small number of testable changes. The potential breakthrough is making the training data, search decisions and validation measure the same thing: finding the move that preserves or improves the actual game outcome.
