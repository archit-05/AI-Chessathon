# Astra Rival Systems Comparison — BINI, Mite and PSL

## What can actually be reverse-engineered

We have BINI's source, packaged weights and private logs. For Ryan Vincent's Mite and JBG fam's PSL God Matt Bomer, we have public moves, clocks, results and third-party reference evaluations. No rival source, private search telemetry, weights or training manifest was obtained. Targeted public searches did not locate an attributable architecture disclosure. Thus this is a measured behavioral reconstruction, with an explicit boundary around private implementation.

A move and its elapsed time do not uniquely determine the implementation. Alpha-beta with a small network, classical evaluation, a different selective search, or another design can produce the same output. Neither rating nor centipawn loss identifies a network's width, nodes per second, depth or training compute.

## Important correction to the project's intelligence reports

`intel/strategy.py::strength_class` assigns phrases such as 'depth 8–12' and 'hand-crafted evaluation' using thresholds on mean centipawn loss. `intel/report.py::profile` does the same and upgrades confidence using sample size alone. These are labels generated from assumptions, not architectural measurements. The report even describes our known NNUE engine as depth 8–12 despite our actual substantially deeper logs.

Do not use these labels to plan architecture changes. Likewise, an aggregate comparison of time spent after a reference-score swing does not establish that an opponent fails to recognize critical positions: clock, move number, forced moves and position difficulty confound it. Going below five seconds does not establish poor time management. The older claim that clock changes buy depth 'without any risk of flagging' is not defensible.

The older reports also mix historical builds and competition stages. Their claim that a book is absent when early instant moves are scarce should be softened to 'no observable instant-book use in this sample'. Their existing timing and result data can still be useful if filtered and checked.

## Measurement scope

Freshly fetched team pages were resolved for streamed HTML fragments before parsing; this recovered all thirteen Final rows for all three teams, fixing the twelve-row coverage limitation in the preceding Swiss review. Public game data came from the existing game cache where complete and was fetched otherwise. All 39 team-game observations have PGNs and reference evaluations. BINI's local logs cross-check its private behavior.

Time per own move = preceding own clock + 0.5-second increment − new own clock; the first clock is 120 seconds. 'Instant' means under 50 ms, not zero. All instant moves counted in the first-six metric had more than one legal move, so a forced single move does not explain that comparison. Clock-bin medians exclude instant and single-legal-move decisions. They still do not control position difficulty or opening selection.

Results were independently checked to sum to BINI 8–4–1, Mite 7–5–1, PSL 8–5–0 across thirteen unique rounds each. Cached completed PGNs are used as factual game records; platform annotations are finite reference estimates.

## Performance: same stage, different schedules

| Measurement | BINI Alpha | Mite / Ryan Vincent | PSL God / JBG fam | Interpretation |
|---|---:|---:|---:|---|
| Swiss place | 6 | 9 | 1 | Actual finish; not a controlled engine comparison |
| Points | 10 | 9.5 | 10.5 | Half-point separation on either side of us |
| W–D–L | 8–4–1 | 7–5–1 | 8–5–0 | PSL's outcome edge over BINI was avoiding a loss while retaining eight wins |
| Buchholz | 112.5 | 113 | 115.5 | PSL's opponents accumulated more points; not a complete strength adjustment |
| Own moves sampled | 916 | 862 | 702 | Different game lengths affect averages |
| Mean seconds/move | 1.73 | 1.85 | 2.27 | Not inference throughput or nodes/sec |
| Median seconds/move | 1.59 | 1.75 | 1.69 | Means obscure the distribution of budgets |
| Mean clock remaining at finish | 33.3 s | 30.5 s | 24.2 s | Early finishes inflate this; unused time is not necessarily waste |
| Games ending under 10 seconds | 3/13 | 3/13 | 7/13 | PSL accepts more low-clock endings in this sample |
| First six own moves under 50 ms | 12/78 (15.4%) | 43/78 (55.1%) | 0/78 | Strong opening-preparation signature for Mite |
| Mean site ACPL, equally weighted by game | 10.9 | 15.6 | 9.9 | SF16/depth16 proxy, sensitive to game course and decided positions |
| Our reference error mean, competitive positions only | 6.39 cp | 8.17 cp | 8.61 cp | BINI is not uniformly worse by this alternative metric |
| Positions in that error sample | 825 | 774 | 628 | Before AND after reference scores restricted to absolute value under 800 cp |
| Errors at least 100 cp in that sample | 6 | 7 | 3 | Error frequency differs from average error and outcome impact |
| Errors at least 200 cp in that sample | 1 | 1 | 1 | Identical counts conceal different consequences |

For our reference metric, CPL = max(0, own-view reference-before minus reference-after). It compares independent site evaluations before and after, not a single exhaustive root analysis. It excludes positions already outside the stated range; clipping, perspective, weighting and game-length differences explain why it is not the site's ACPL. Long equal positions can dilute BINI's average. Do not optimize exclusively for either scalar.

The three >=200 cp cases illustrate the problem with treating every error equally: BINI's R113/39 missed a large winning opportunity and the game drew; Mite's R120/32 reduced a winning advantage but it still won; PSL's R120/82 reduced a winning advantage but it still won. Neither a high accuracy percentage nor a single blunder count explains the tournament result alone.

## Clock policy: the strongest quantitative distinction

| Clock before move | BINI median | Mite median | PSL median |
|---|---:|---:|---:|
| Above 60 seconds | 2.53 s (332 moves) | 2.55 s (351) | 4.13 s (204) |
| 30–60 seconds | 1.75 s (189) | 1.78 s (166) | 2.74 s (113) |
| 10–30 seconds | 0.89 s (213) | 1.18 s (157) | 1.41 s (167) |
| At most 10 seconds | 0.52 s (108) | 0.51 s (79) | 0.65 s (175) |

PSL spends about 63% longer at the median in the high-clock bin. This is consistent with more aggressive budget allocation, but it does not distinguish a larger soft target, greater difficulty, more unstable iterations or slower inference. It does not prove it searches more nodes or is deeper. The lower ending clocks are consistent with the cost of that allocation.

Mite and BINI are remarkably similar in the two high-clock bins. A story that Mite wins mainly because it spends vastly more thinking time is not supported by these figures. It does spend somewhat longer in the 10–30-second bin; investigate any desired change with actual paired tests rather than transplanting these medians.

In R122 both sides faced the same game: PSL finished with 65.2 seconds, BINI with 91.1. The position nevertheless ended in a sound repetition. More spending did not establish an edge there.

## Architecture comparison and confidence

| Component | BINI: known implementation | Mite: evidence and inference | PSL: evidence and inference | Confidence / unresolved gap |
|---|---|---|---|---|
| Runtime | Python with numba-jitted bitboard engine | Runtime unknown | Runtime unknown | No claim of Rust/C++/numba from PGNs; all must obey platform rules |
| Search family | Iterative-deepening PVS alpha-beta with selective pruning | Multi-second decisions and strong tactical play are compatible with a search engine | Same | Compatible does not identify alpha-beta versus another system |
| Evaluation | Own-trained, quantized, king-bucketed 1024-width NNUE with SCReLU and output buckets | No evidence establishing NNUE, width, activations or size | Same | Unknown; a larger pretrain is not an observed rival feature |
| Training | Own Stockfish-labelled data; fc_b continuation lineage documented locally | Teacher, depth, data diversity, loss and optimizer unknown | Same | Winning moves do not reveal the training recipe |
| Search depth / NPS | Actual BINI per-move telemetry exists | Neither depth nor NPS public | Neither public | Cannot derive from ACPL or elapsed time |
| Opening preparation | JSON book, instant legal hit, then normal search | 55% instant early moves, including repeated seven-move instant prefixes in several games | No instant early move in thirteen games | Strong evidence of Mite prepared/cached opening answers; PSL book absence not proved |
| Prepared answer quality | Old book remains a known development concern; replacements have not demonstrated a gain | Coverage/activity appears greater in this sample; analysis depth/source unknown | Unmeasured if a book is consulted inside search | More coverage is not necessarily stronger preparation |
| Clock allocation | Explicit clock budget plus stability/danger adjustments | High-clock timings similar to BINI | Substantially longer high-clock timings; more low-clock finishes | Observed distributions strong; exact formula unknown |
| Tactical reliability | Missed Qe8+ in R113; misjudged Qh6 in R114; many strong wins | Punished our R108 g5; also lost its own R118 | Converted eight wins and avoided defeat in Swiss | Observable outcomes; causal subsystem not isolated |
| Quiescence / pruning | LMP, futility/history and SEE may precede gives-check detection; optional quiet checks disabled by default | Unknown | Unknown | No evidence rivals have safer pruning or a special tactical verifier |
| Draw policy | Contempt 20; threshold-based switch to neutral draw utility; second-occurrence search heuristic retained | Five Swiss draws; no clear large missed winning advantage in the maximum reference scores of these draws | Five draws, including tactical repetition against BINI | Results cannot reveal contempt constants or exact repetition handling |
| Endgame knowledge | Known terminal corrections; no general tablebase cure established | No tablebase or specialized evaluation evidence | Same | Strong conversion does not identify tablebases |
| Transposition/history state | Known persistent TT and histories; path-dependent draw concerns remain investigatory | Unknown | Unknown | Warm-state performance cannot be reconstructed exactly without logs/state |
| Initialization | All Swiss NNUE-ready, 37–60.3 seconds | Private init not established from inspected public data | Same | Do not substitute move clock for startup time |
| Hardware advantage | Fixed platform CPU for matches | Same published execution limits | Same published execution limits | More private training hardware is possible but unobserved; no evidence of more match hardware |

## The three engines in plain English

**Mite:** a system with a strong observable preparation signature, ordinary-looking clock scaling once it starts thinking, and the ability to punish a particular defensive mistake. In R108 its opening responses included numerous near-instant moves, and it eventually converted after we declined the holding rook capture. The strongest evidence is preparation plus effective decisions in that game, not a demonstrably larger or deeper model. Its Swiss result was weaker than ours and it lost to bentheboss1236. It is not uniformly superior to BINI.

**PSL:** a system that spends more clock on its decisions and, in this Swiss, converted eight wins without suffering a defeat. It searches or otherwise computes from the beginning rather than displaying Mite's instant-opening pattern. It still accepts sound draws, including against us, and its own low-clock R120 had reference inaccuracies. There is no basis for declaring it flawless or assuming its network has more parameters.

**BINI:** a proven search-plus-NNUE system with substantial selective-search machinery, conservative relative clock spending, some opening preparation and eight successful conversions. Its broad move quality is competitive. The concrete weakness is that selected consequential decisions are misranked or missed: a winning forcing line in R113, compensation for a rook in R114 and a holding liquidation in R108. These can arise from evaluation, selective search or their interaction; score differences alone do not separate them.

## What to learn, and what not to copy

| Observation | Engineering response | Acceptance evidence |
|---|---|---|
| Mite has more instant prepared moves | Audit our actual book hits, legal keys, expected coverage, depth and reference exit quality. Test a small corrected book candidate if justified. | Completed paired timed games with the same opening set; not coverage alone |
| PSL spends more with a healthy clock | Diagnose whether additional time solves our critical positions, then test an isolated budget candidate if it does. | Better moves at measured costs, no clock regressions, completed wrapper comparison |
| BINI misses a forcing win | Instrument Qe8+ and Nd7 in R113: generation, ordering, reductions/prunes, leaf evaluation and bound provenance. | Reproducible causal improvement plus independent tactical and positional controls |
| BINI misjudges sacrifices / liquidations | Contrast best and played moves in R114/40 and R108/39; deepen and verify labels; add diverse analogous positions if evaluation is implicated. | Unseen-game ranking gains and timed strength, not memorized examples |
| PSL avoids defeat while winning eight | Evaluate both conversion and defensive failure rate, and paired-match advancement under the knockout tiebreak. | Consistent benefit across opponents/openings; not an isolated 13-game result |
| Rival model sizes unknown | Do not pick our model size by imagining theirs. Compare measured strength-per-second at actual CPU limits. | A validated candidate outperforming the baseline at the real clock |

The most valuable next experiment is a three-position causal audit, followed by one isolated repair or controlled fine-tune. A large new pretrain remains an optional experimental lane, not an inference from how either rival behaves.

## Stronger future identification, if more evidence becomes available

Ask for a public technical presentation or architecture disclosure when available; do not infer identity-linked private repositories or seek hidden artifacts. A faithful executable rival under the same clock would enable matched-position tests, but public PGNs alone do not. For BINI, diagnostic instrumentation can distinguish the same competing explanations cheaply because we own the code. Use that advantage before copying an imagined opponent.

## Reproducibility and sources

- Public [Mite team page](https://aichessathon.com/team/8c22f2a5-3bce-4b66-b93a-8f4ab4318b0f), [PSL/JBG team page](https://aichessathon.com/team/10021bb5-71a5-4b10-bde5-14e1f667501a), [BINI team page](https://aichessathon.com/team/f0286356-626d-4dd2-86ab-fd6d779063cb).
- `rival_comparison_raw.json`: refreshed teams and public games, including per-position reference arrays and clocks.
- `rival_comparison_metrics.json`: all reconstructed own-move observations and aggregate metrics.
- `rival_comparison_validation.json`: thirteen-round/result reconciliation and clock-bin counts/medians.
- `compare_rivals.py`: collection and analysis implementation. Team pages use resolved streaming fragments; metrics include only Final games selected for this comparison.
- `Astra Swiss Review.md`, `swiss_reference_checks.json`, `r108_reference_checks.json`: independently checked BINI decisions and their limitations.

No deployed code, network or archive was changed. No rival architecture was established beyond what is explicitly marked as known.
