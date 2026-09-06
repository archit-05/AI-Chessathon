# V3 — the overnight plan (Sunday 6 Sept 2026, 22:40)

Built on three things that did not exist this morning: fourteen rated games on the platform, the
intel corpus on the top twenty (every public game, site grades, clocks, head-to-head), and the
measurements of every change we tried today. PLAN.md carries the full history; this file is the
plan for tonight and Monday morning.

## 1. What is working (evidence, not opinion)

- **The engine core.** 700–840k nodes/s on the EPYC, depth 13–21, compile 25–29 s, zero
  failures in 14 rated games and in ~600 local games today. Perft-exact move generation, exact
  NNUE incremental updates, a wrapper that cannot crash or play an illegal move.
- **Move quality where positions are calm.** Site grader (Stockfish 16, depth 16): our v2/v2.1
  games score ACPL 3–12 in ten of fourteen games, 0.0% blunders since v2; "recent form" 7.0 cp per
  move. The podium sits at 8.3 (AlphaFish), 10.8, 11.0, 11.7, 11.7. In ordinary positions we are
  already grading at their level.
- **Conversion.** Nine of ten winning positions converted to mate; no fifty-move drift, no
  repetition while ahead (the intel counts zero for us). Mop-up needs no extra terms: the
  conversion package measured nothing and did not ship.
- **Repetition discipline.** Fixed contempt of 20 already takes the perpetual when lost (R43)
  and refuses it when ahead. No dual regime: the site's voiding of repetition games was a one-off
  pass; draws since R35 stand.
- **The method.** Every change gated by games; three local defects (clock drain, floor breach,
  starvation) were caught by the battery before they could reach the platform; one platform
  defect (R37 clock) was diagnosed from the log and fixed the same day.

## 2. Why we drew and lost today (mechanics, and where each fix stands)

| Game | What happened | Mechanism | Status |
|---|---|---|---|
| R37 draw (v2) | 66-move level game, clock 63/31/12/6 s | old policy let an iteration run to 3× the budget; time trouble forced repetition | fixed in v2.1 (predictive iteration start), verified 9.7 s min over 133 moves |
| R40 loss (v2.1) | Grünfeld as Black, slow squeeze, mated with 70 s unused; no tagged blunder | evaluation drifted −15 → −188 over six moves; the stable-move discount starved the search where the obvious move was stable and wrong | time side fixed in v2.2 (danger multiplier when the score falls, half-budget floor); evaluation side is v3/v3b |
| R42 draw (v2.1) | 152-move level game, ACPL 3 vs 3, 20 s left | none | nothing to fix |
| R43 draw (v2.1) | 17.Rd4?? hung a rook (−328), then a perpetual a queen down | net scores White's attack +211 in a level position; quiet defensive replies get reduced/pruned so the root keeps +36 at depth 17; Stockfish sees −328 at depth 20 | open: evaluation of sharp positions (v3b data), root guard (tonight), targeted sacrificial data (Monday); now a hard regression test |

The pattern behind R36, R40 and R43 (our only games with ACPL above 12): activity over-rated
in sharp middlegames. It is one class of error, reproducible from a FEN, and it is the thing a
top-five engine punishes every time.

## 3. How the top teams operate (from the intel corpus)

- **Architecture.** Every one is a classical alpha-beta searcher with a strong evaluation. No
  books (Anchoa plays a fifth of early moves instantly, the rest do not). Strength is uniform move
  quality, not depth bursts. AlphaFish: 8.3 cp per move, one blunder in 2,175 moves, 12-4-0 vs
  the top ten. The next four: 10.8–11.7 cp, 39–57% vs the top ten, all re-uploaded in the last
  five rounds.
- **Clocks.** A fixed 3–4% of the remaining clock per move: 3–4 s in the opening, 1–1.5 s by
  move 40, 0.5–0.8 s late, 27–40 s unused at the end. None of them spends more after a big
  evaluation swing (AlphaFish 1.3 s after a swing vs 1.7 s otherwise; Capablanca 1.1 vs 1.9).
  test_bot is the exception the other way: 18 games under 5 s.
- **Draws.** Threefold is the dominant draw type; the top five accepted 23 level repetitions
  and 3 while ahead. AlphaFish plays instantly once it holds a mate score and repeated with a
  mate on the board (R32). Draw rates 29–42%.
- **Conversion.** 90 of 98 positions at +300 or better were won by the top five; the misses are
  technique (a mate thrown into a repetition, fifty-move drift). Below the top five the leaks
  widen.
- **Endgame fade.** Capablanca's error rate rises from 9 to 14 cp after move 40; several others
  drop under 5 s in a third of their games. Long games favour a side whose depth does not fall.
- **What this means for us.** There is no clock habit to exploit at the very top and no opening
  trick; the edge is (a) spending our clock where the game is decided while theirs thins out,
  (b) never conceding the half point they concede, and (c) closing the sharp-position blind spot
  so their accuracy has nothing to punish.

## 4. V3: what it is

V3 = v2.2 (time policy v2.2 + NNUE v3) plus every overnight item that gates positive:

1. **Search batch 2** — capture history and one-ply continuation history in move ordering,
   history-driven reductions. Gate: 150 games vs v2.1 (running now), then re-gated in the V3
   assembly.
2. **NNUE v3b** — v3 fine-tuned for two epochs on 155M quiet positions plus Stockfish-labelled
   whole-game positions oversampled ×10 (sharp middlegames from real games, the distribution the
   Lichess set lacks). Gate: 300 games vs v2.2, real-clock centipawn loss, the R43 regression
   test.
3. **Root guard** — when the chosen root move hangs material by static exchange and the score
   is not a mate, treat the move as unstable: keep deepening to the hard limit and require the
   score to hold at the deeper iteration before committing. Cheap, targeted at the R43 class.
   Gate: blunder regression + 150 games vs v2.2 showing no loss.

Fallback at every step is the already-packaged v2.2.

## 5. The overnight schedule (times are targets; each step is chained and gated)

| When | Step | Decision rule |
|---|---|---|
| now–00:30 | batch-2 gate vs v2.1, 150 games | keep if ≥ +20 Elo with the interval clear of zero; otherwise drop |
| 00:30–03:30 | Stockfish depth-10 labelling of 1.5M whole-game positions (4 workers) | proceed regardless |
| 03:30–06:00 | v3b fine-tune: resume v3, lr 5e-4, two epochs, whole-game set ×10 | export, consistency + exactness checks |
| 06:00–08:30 | v3b gate: 300 games vs v2.2 (3 workers) + centipawn loss at the real clock + R43 test | keep if ≥ +20 and CPL ≤ v3's 11.7; a loss on R43 alone does not block |
| 01:00–02:00 (parallel, one process) | root guard implemented and unit-tested in the working copy | blunder regression must pass |
| 08:30–09:30 | root guard gate: 150 games vs v2.2 | keep if not negative and R43 avoided |
| 09:30–10:30 | V3 assembly + full battery: tactics 40, mate suites, wrapper/NNUE suites, torture 30, real-clock pressure 10, blunder regression, zip byte-check, fresh-extraction game | all green or it does not ship |
| ~10:30 | V3 handed over and pushed | |

Monday daytime, after V3: targeted sacrificial/attacking dataset (positions from the Elite games
where Stockfish's best move gives up or wins ≥ 2 pawns of material, labelled at depth 12), a
further fine-tune, and the SF 2600/2800 calibration ladder. Wednesday freeze stands.

## 6. Definition of done for V3

- Beats v2.2 in gated games; real-clock centipawn loss ≤ 11 (v3: 11.7, v2.1: 13.3).
- Does not play 17.Rd4 from the R43 position at the real budget.
- Battery green: 0 failures, min clock ≥ 5 s over ten real-clock games vs full-strength
  Stockfish, tactics ≥ 38/40, torture 30/30 with 0 fallback.
- Compile ≤ 35 s on the EPYC (current 27–29 s; the net is the same size).
