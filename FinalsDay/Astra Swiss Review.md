# Astra Swiss Review — 11 September 2026

## Verdict

V8.5 is a credible finals contender. The 13-game Swiss finished 8 wins, 4 draws and 1 loss: 10/13, sixth of 334, tied on points with second and half a point behind the winner. Preserve this baseline. There is specific evidence for improving tactical opportunity detection and evaluation of attacking compensation; there is no evidence supporting a wholesale replacement or indiscriminate draw avoidance.

This review inspected all 13 downloaded PGNs and logs, retrieved their public reference evaluations, refreshed the top ten team pages and final standings, checked the London bracket page and relevant deployed search code, and ran five targeted independent Stockfish position checks. It did not replay the BINI engine or prove the internal cause of each error. No engine code, weights, configuration or submission was changed.

The user’s twelve-game listing omits R110, a win against Istanbul's finest. It is present in Downloads. The thirteen local results reconcile exactly with 8–4–1.

## Results and opponents

| Place | Team | Points | W–D–L | Buchholz |
|---|---|---:|---|---:|
| 1 | JBG fam | 10.5 | 8–5–0 | 115.5 |
| 2 | Miskeen | 10 | 8–4–1 | 116.5 |
| 3 | Lightning Tree | 10 | 7–6–0 | 116.5 |
| 4 | Gladiator | 10 | 7–6–0 | 116.5 |
| 5 | Rataturing | 10 | 8–4–1 | 113.5 |
| 6 | Opus Carlsen | 10 | 8–4–1 | 112.5 |
| 7 | Sobriety | 9.5 | 6–7–0 | 114.5 |
| 8 | BetaGo | 9.5 | 7–5–1 | 113.5 |
| 9 | Ryan Vincent | 9.5 | 7–5–1 | 113 |
| 10 | Lubina | 9.5 | 7–5–1 | 112.5 |

Sources: user's final standings and independently fetched [final qualification page](https://aichessathon.com/leaderboard?stage=finalset). The browser search cache returned an older round-11 snapshot; `finalset_page.html` and `swiss_standings.json` contain the fresh round-13 response. Do not mix them.

JBG beat omega3 fish in R120 and Miskeen in R121, then drew us in R122. Lightning Tree beat Stonkfish in R121 and stayed unbeaten. Gladiator beat ms in R121 and stayed unbeaten. Rataturing beat JSP and OMI in R120–121. Mite lost to bentheboss1236 in R118 and finished behind us. These are concrete results, not evidence about undisclosed architecture.

BINI drew the champion and beat catfish, who finished thirteenth. Most of our other wins were against lower finishers. Buchholz is the sum of opponents' scores, not a direct engine-strength measure; our lower value helps explain sixth within the ten-point group. One improved result would add half or one point on the recorded schedule, but it would also have changed subsequent Swiss pairings, so do not claim it guarantees first place.

## What worked

All thirteen logs contain an NNUE-on startup line. None reports fallback. All completed with chess-rule terminations, without a crash, flag or init loss. Startup median was 39.5 seconds, range 37.0–60.3; the longest was R110, missing from the user's excerpt. This is comfortable under 90 seconds but relevant if tomorrow tightens initialization.

We converted eight games to checkmate. White scored seven wins and one draw; Black one win, three draws and one loss. That is a useful reason to test both colors, not proof of a color-specific code defect: opponents and openings differ substantially.

The long draws show persistence rather than early surrender: R113 lasted 157 own moves, R116 112, R119 117, with 7.2–8.5 seconds remaining at their ends. R122 was short, but the reference analysis shows a level position and a sound repetition against the eventual champion.

## The five non-wins

### R113 vs OMI: a concrete missed tactical win

At **39.Rc2**, the engine logged depth 19, +157 cp, 5.33 seconds thinking and 44.14 seconds available before the move. The site SF16/depth16 reference prefers **39.Qe8+**, evaluating the position at +5.07 versus +0.79 after Rc2.

An independent 600,000-node search with full PGN history found Qe8+ at **+7.83, depth 25**, versus Rc2 at **+0.74, depth 19**. One reference line is 39.Qe8+ Kh7 40.Nd7 Rb8 41.Qxb8 Qb5 42.Nf8+ Kg8 43.Qxb5. This is strong finite-search evidence of a missed winning opportunity, not tablebase proof of every continuation.

The relevant failure occurs on move 39, not at the fifty-move termination much later. Merely changing draw utility would not teach the engine this combination. We have not established whether BINI rejected Qe8+ because of evaluation, selective search, move ordering or state. This is now the highest-priority tactical reproduction alongside R108/39.

### R114 vs slopfish: attacking compensation misjudged

The first independently checked decisive disagreement is **40...Qh6**, leaving the h5 rook available to **41.gxh5**. BINI logged **+59 cp, depth 17**, after 1.50 seconds, with 39.39 seconds available before the move. Its next score, after the opponent captured, fell to −127.

Independent reference: **40...Bh4 +0.19**, versus **40...Qh6 −1.54** from Black's view. The preceding **39...exd4** remains approximately equal (+0.10 to +0.19). After 41.gxh5, **41...Qg5** is also the reference's preferred move at about −1.70; the response to the capture is not the first error.

This supports a targeted investigation of whether the engine overestimated the compensation for the rook. It does not prove a simple hanging-piece detection bug: the position contains real threats and material exchanges. It also does not prove more time cannot help this particular case; that experiment has not been performed. Earlier failed time-management gates do not replace a position-specific test.

### R116 vs JSP: an advantage reduced, not a demonstrated forced win

At **29...Qg3**, site reference falls from about +1.04 to −0.10 for Black. Independent reference prefers **29...Qf5 +0.79**, versus Qg3 −0.04. This merits a secondary conversion test. Do not classify a sub-pawn reference advantage as a certain squandered win.

### R119 vs Danya's Disciple: no clear missed win in screening

Reference screening shows mostly modest advantages, peaking around +0.60 for us, and no single large deterioration on our moves. The eventual repetition is consistent with an ordinary drawn game. No independent deep check was performed here; evidence does not justify forcing this draw into the bug category.

### R122 vs JBG: a sound tactical repetition

The actual line includes **15...e5 16.Nd5 Qxc1 17.Nxe7+ Kf8 18.Ng6+ Kg8**, followed by repeated knight checks. Both sides' site review is 98.8% accuracy and 4 ACPL; the reference remains close to equal throughout. The engine's −20 is consistent with its configured draw utility, not necessarily a false claim that the material balance is −0.20 pawns. About 91 seconds remained because the game ended early, not because the clock manager necessarily malfunctioned.

Do not punish this line merely for drawing. Its tournament desirability changes under the knockout tiebreak, but no superior non-repeating line has been established.

## Code implications: diagnosis, not an untested patch

In `bini_astra_v5_noc2b/bini_search.py`, quiet-move LMP, futility/history pruning and SEE pruning can occur before the move is made and `gives_check` is computed (approximately lines 913–940). Consequently, those checks do not universally exempt checking moves in eligible non-PV nodes. Quiescence quiet checks are optional and disabled in the deployed defaults. These are selective-search choices, not automatically rule violations. A root checking move is not simply discarded by the non-PV conditions: trace its continuation and relevant descendant nodes.

For R113, instrument Qe8+ and the follow-up quiet tactic Nd7. Record whether critical continuations are generated, ordered late, pruned, reduced, searched to completion, or evaluated incorrectly. Compare targeted diagnostic settings at fixed nodes, then at the real clock. Do not globally disable pruning or enable all quiet checks without measuring the cost.

The engine also switches contempt to zero when its previous root score is at most −100 after the configured move threshold. That policy depends on recognizing that it is worse. It cannot rescue an attack it incorrectly believes is favorable. The existing nodraw/repetition correctness work and the new strength investigation must remain separate.

## London changes the objective

The [London page](https://aichessathon.com/leaderboard?stage=knockout) still showed 'Bracket pending' when fetched. It specifies two games, one with each color. The [published docs](https://aichessathon.com/docs) say a level knockout tie goes to the better final Swiss standing.

If those rules remain, two draws or one win each favor BINI against a lower Swiss finisher, and eliminate BINI against any of the five higher finishers. Thus the evaluation target for experiments should include two-game match advancement, not only aggregate Elo or draw percentage. No particular first-round opponent is confirmed. Do not infer an eight-team field solely from empty quarterfinal headings.

Do not implement opponent-aware or match-score-aware policies unless the final interface actually supplies that context or organizers explicitly allow configuration between matches. The current FEN/clock interface does not contain it, and processes do not share state across games. Do not blindly increase contempt: earlier tests were negative. Sound defense and taking real winning chances remain the main engine objective.

## Updated work order

1. Preserve V8.5 and its exact archive/hash as the control. This Swiss supports retaining its strengths; it does not isolate a V8.5-over-V8 causal gain.
2. Reproduce **R113/39, R114/40 and R108/39** with correct full history and controlled cold/reconstructed-warm state. Log comparable candidate move scores, PVs, completed iterations and pruning reasons. In R114 explicitly compare current clock, 5 seconds and a longer diagnostic budget; never assume the old R100 result applies here.
3. Make only a causally justified local search fix, if found. Trace raw and corrected evaluation of the critical leaves before declaring the net solely responsible. Avoid simultaneously changing time management, search and weights.
4. Keep one controlled fine-tune experiment available, with broad preserved data plus verified tactics, attacking-compensation, defensive-liquidation and conversion examples. These three known games are development cases, not held-out proof. No from-scratch pretrain as the critical path overnight.
5. Gate candidate strength using paired openings/colors and exact wrappers. Report both game score and simulated two-game advancement under favorable and unfavorable tiebreak status. Simulation must disclose its opening/opponent assumptions. We cannot run the real competitors locally without their agents.
6. Carry R110–112, R115, R117–118, R120–121 as good-play regression examples; do not improve two positions by weakening broad conversion. Require independent held-out positions and completed timed gates before recommending a replacement.
7. On reveal tomorrow, verify allowed pre-existing assets, clock, initialization and memory before tuning. Retest cold startup: observed 60.3 seconds is materially different from assuming all starts are 39 seconds. Reserve the end of the development window for exact-package testing and submission.

## Evidence files

- `swiss_games.json`: all 13 parsed logs, PGN moves/clocks and public reference evaluations.
- `swiss_reference_checks.json`: five independent full-history best-versus-played checks, 600,000 nodes per arm, Stockfish identity and depths recorded.
- `swiss_standings.json`, `finalset_page.html`: fresh final standings.
- `swiss_top_teams.json`: refreshed public team pages; the parser returned 12 Final rows per team, so their extracted history must not be represented as complete 13-game coverage. Our 13 local PGNs supply the complete BINI record.
- `knockout_page.html`: bracket/rules snapshot.

Search reference numbers are finite estimates. They identify concrete engineering tests, not a guaranteed cure or guaranteed tournament win.
