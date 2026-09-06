# v2.2 as a leap, not a step (Sunday 6 Sept 2026, 23:10)

Goal: the build that plays from 08:00 Monday must be materially stronger than v2.1 on the ladder,
not marginally, and it must be built from what today's games and the intel actually show.
Everything below is gated before it ships; the packaged v2.2 (time policy + v3 net) is the floor.

## 1. The whole system, judged by the day

What performed:
- Platform robustness is perfect (14 games, 25–29 s init, 0 failures); the wrapper, board and
  search are not where points are lost.
- Calm-position play is podium-grade on the site's grader (ACPL 3–12, 0.0% blunders since v2).
- Conversion and repetition discipline are sound (9/10 won positions mated; perpetual taken when
  lost; never repeated while ahead).

What under-performed, in order of points lost:
1. **Clock.** We ended games with 65–104 s unused in 9 of 14 games. The top five end with 27–40 s
   and spend 3–4 s in the opening; we spent 1.1–2.4 s. Every second unused is depth not searched;
   in R40 it was 70 s in a game we lost by inches, in R43 100 s in a game we nearly lost.
2. **Sharp-position evaluation.** R36, R40, R43: the net over-rates its own activity, the search
   prunes the quiet refutations, and the root commits to a move Stockfish refutes at depth 20.
   One class of error, reproducible, now a regression test.
3. **Opening phase.** Our first fifteen own moves are our weakest phase (site loss highest there);
   no book, and the curated positions put us straight into theory we search at 1–2 s.

## 2. What the other teams did well, and what we can take from it

- **Consistency over brilliance.** AlphaFish: 8.3 cp per move, one blunder in 2,175 moves. It does
  not win by finding more than we do; it wins by never giving a half point back. The equivalent
  for us is closing the sharp-position class and using the clock, not new tricks.
- **They use the opening clock.** 3–4 s per move for the first fifteen, then 2 s, then 1 s. We
  did the reverse today (1–2 s early, occasional 6 s spikes). Front-loading is right: the opening
  is where the curated positions are sharpest and where our error rate is highest.
- **They convert and they defend.** 90 of 98 won positions converted; the losses they suffer are
  technique. Our conversion is already there; our defence in slightly worse positions is not (R40).
- **Their weaknesses are real but narrow.** Fixed clock shares that thin out after move 40 (all
  of them), no extra time after swings (all of them), instant play with a mate score and
  repetition with a mate on the board (AlphaFish R32), time trouble (test_bot in 18 games, Mate in
  One in 7). We exploit these only by being sound ourselves for 70 moves and keeping our depth up
  when theirs falls.

## 3. How today's draws and loss become wins

- R37 (draw): with v2.1's clock policy we keep 25–35 s at move 60 instead of 6 s; the level ending
  is then played at depth 15+ instead of 10, and a 1650 opponent is outplayed. Fixed.
- R40 (loss): 2.7 s a move from the start plus the danger multiplier puts 15–20 s more into moves
  14–20 where the score slid; at depth 17–18 instead of 15 the squeeze is at least resisted.
  Turning it into a win needs the evaluation to see the plan earlier: v3/v3b.
- R42 (draw): a 152-move level game; a win needs a better endgame evaluation than the opponent,
  not more time. v3b's whole-game data is the lever; otherwise it stays a draw.
- R43 (draw from a lost position): not playing 17.Rd4 wins the game, since we were fine before it.
  Root guard + less pruning on the main line + v3b.

## 4. What goes into the morning build ("v2.2 leap"), all measured tonight

A. **Use the clock like the top, then better.** Budget horizon max(18, 34 − 0.4·n): 3.7 s at
   move 1, ~3 s through move 15, 2.3 s at move 30, 1.6 s at move 50, still capped hard under 30 s.
   Target: 15–25 s left at the end instead of 60–100. Expected worth: about one extra ply on every
   move, the single biggest lever available tonight. Verified by the real-clock pressure test.
B. **Main-line safety.** At PV nodes: no multi-cut, no futility pruning, no late-move reduction of
   the first three moves. Costs a few percent of speed on the main line, buys the quiet defensive
   resources that today's search reduced away. Aimed at the R43 class.
C. **Root guard.** If the chosen root move hangs material by static exchange and the score is not
   a mate, the driver treats the move as unstable: keeps deepening to the hard limit and only
   commits if the score holds at the deeper iteration; otherwise takes the second-best move. Aimed
   at the R43 class; verified by the regression test.
D. **Search batch 2** (capture and continuation history, history-driven reductions), if its gate
   (running now) is positive.
E. **NNUE v3** (already in v2.2), or **v3b** if the overnight fine-tune gates in time.

## 5. Overnight schedule

| When | Step | Rule |
|---|---|---|
| now–00:30 | batch-2 gate finishes (150 games vs v2.1) | keep if positive with the interval clear of zero |
| 23:30–01:00 | implement A, B, C in the working copy; unit tests; R43 regression; tactics 40 | all pass or the item is dropped |
| 01:00–02:45 | gate "leap" candidate (A+B+C+D if kept, on the v3 net) vs v2.2: 200 games, 3 workers | ship if ≥ +25 Elo, interval clear of zero; otherwise gate A+C only |
| 02:45–03:45 | real-clock pressure 10 games; torture 30; wrapper/NNUE suites | min clock ≥ 5 s, 0 failures |
| 03:45–04:15 | package, byte-check, fresh-extraction game, push | hand-over ready for 08:00 |
| 00:30–06:00 (parallel) | labelling 1.5M whole-game positions → v3b fine-tune | v3b gate 06:00–08:30 vs the leap build |
| 08:30– | V3 = leap build + v3b if it gates; full battery; hand-over ~10:30 | |

## 6. What "leap" honestly means

Adding one ply everywhere (A), removing the main-line pruning that hid refutations (B+C), the
ordering gain (D) and the stronger net (E) is, by the numbers we have, in the region of
+100 to +150 Elo over v2.1 on this ladder, on top of v2.2's own +40 to +60. That is the
difference between losing to 1800s occasionally and beating them almost always, and it moves the
realistic Monday-evening target to 2000–2150 and a top-30 rank. It is not yet the tier that beats
AlphaFish; that is the evaluation work (v3b tonight, the sacrificial set Monday) and it is gated
the same way.

## 7. Execution log (night of 6 Sept, written as it happens)

- 22:00  Working copy `bini_leap` = v2.2 files (v2.1 search + v2.2 clock + v3 net) plus A and C.
  - A: `mtg = max(18, 34 - 0.4·n)`; low-clock caps unchanged. Budget curve: 3.8/8.4 s at move 1,
    3.0/6.6 s at move 15 (75 s left), 2.35/5.2 s at move 30 (45 s left), 1.7/2.0 s at move 50 (25 s left).
  - C: root guard implemented as a driver rule, not a veto: when the best root move has SEE < -150
    and the score is not a mate, the iteration factor is forced to 2.5 (up to the hard limit) so the
    search keeps deepening before committing. Logged as `rg<n>` on the move line. Fires for 17.Rd4 in
    the R43 position (SEE -500).
- 22:10  B (main-line safety: no multi-cut at PV nodes, LMR only from the 7th move at PV) built as
  `bini_leap_b`. Regression: it plays 17.Rd4 (R43) at 2.0, 3.0 and 3.8 s while A+C avoids it at all
  three (b2b3 +90). Same 39/40 tactics. B is DROPPED on this evidence, per the instruction to drop it
  unless clearly positive; a second 200-game gate for it would not fit the night anyway.
- 22:15  Suites on A+C: test_search gate 2 passed (9/11 tactics), blunders 2/2, puzzles 39/40 (98%).
- 22:20  Top-team proxy calibrated: unrestricted Stockfish at N nodes, move loss judged by the site
  grader (120k nodes) on 120 quiet middlegame positions: 15k nodes -> CPL 8.9, 30k -> 5.0, 60k -> 4.2.
  The proxy for the 20 real-clock games is Stockfish at 10k nodes (about CPL 11 by extrapolation,
  measured again from the games).
- 22:25  Gate cadence decided: 200 games at 30 s + 0.5 s (same increment as the platform, four times
  faster per move, 3 workers). Real clock (120 s + 0.5 s) is used for the 10 pressure games and the 20
  proxy games. Labelling reduced to 2 workers / 1.5M positions so the gate is not starved.
- 22:29  Batch 2 (D) final: 150 games, +5 +/-56, zero fallbacks. EXCLUDED.
- 22:29  Leap gate started: bini_leap vs bini_v22, 200 games, 30 s + 0.5 s, 3 workers
  (bini/tests/arena/leap_vs_v22.log). v2.2 baseline vs the Stockfish 10k proxy running at 1 worker.
  Labelling relaunched at 2 workers / 1.5M positions (10 chunks; the v3b fine-tune waiter is unchanged).
- 22:40  Second R43 position from the intel session added to tests/pos/blunders.epd (15.Rad1?!).
  Stockfish (2M nodes): after 15.Rad1 Black stands +41 (15...Bg4 16.Qg3 Bxd1 17.Rxd1 Kh7 18.Rd6 Qc4);
  best 15.Bd5 keeps +35. The leap build plays Rad1 at 3.8 s (+63 at depth 15): it sees 15...Bg4 and
  still scores the exchange sacrifice as good for White. Same net as v2.2, same result, so this is not a
  regression of tonight's build: it is the net's attacking-compensation bias, the same family as 18.Rd4,
  and the reason the v3b fine-tune uses whole-game positions. Recorded as a known miss for V3.

## 8. V3 (Monday), agreed shape

One build for the whole of Monday morning (v2.2), then V3 in the afternoon if and only if it gates.
- Net: v3b = v3 fine-tuned 2 epochs on the quiet set plus 1.5M whole-game Stockfish-labelled positions
  (oversampled x10). Gate: 300 games at 10 s + 0.1 s vs the shipped v2.2; must be positive with the
  interval clear of zero; CPL on 20 real-clock proxy games not worse than v2.2; both R43 positions.
- Search: nothing new in V3 unless it gates on its own (candidates for Tuesday: contempt 30-40 for
  draw aversion against weaker opponents, gated separately at 10 s).
- Battery: identical to tonight's, uncompressed. Package, byte-check, fresh-extraction game, push.
- Later in the week (freeze Wednesday night, upload Thursday afternoon): larger net trained from scratch
  on the full data, 4 epochs; search speed work (target +20% nps); parameter tuning one change at a time.

