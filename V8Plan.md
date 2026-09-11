# V8 Plan — the asymmetry build

Written Wednesday 9 September 2026, ~21:00 London. The window ends **Friday 11 September 11:00**
when uploads close. Plan of record for net and search work is `Project Prometheus.md` (section 13
is the experiment log); this file supersedes its Thursday and Friday sections. Intel is
`intel/STRATEGY.txt` (regenerated hourly) and `intel/16_BINI_Alpha.txt`.

V7k went live at 20:27 BST: k96 1024-wide net, correction history, continuation history,
LMR_DIV 1.6, int16 accumulators, 6,105-entry book. Measured +39 ±21 over V6.5 at 30 s + 0.125,
best-ever pressure battery (8 draws, 2 losses).

---

## 0. The verdict in one screen

| | |
|---|---|
| **The V8 thesis** | One asymmetry, two halves. **Turn losses into draws** — measured, half-working, and the whole rating gap. **Turn draws into wins** — real, but *not* by winning from +70, which no engine on this ladder does. By stopping a +70 from decaying, so it becomes a +300, where we already convert 24 of 25. Section 1 has the numbers that earn the claim and the one part of it the data refuses. |
| **The one measured behavioural defect behind half one** | When we are more than +150 ahead we liquidate **0.76 pawns of material per own move** against AlphaFish's 0.51, with a capture rate 1.82× our level-position rate against AlphaFish's 1.43. **We are the worst of eight teams measured on both.** We trade our edges away. That is the mechanism, it is specific, and it is fixable with a tuned evaluation term. |
| **The one measured statistic behind half two** | Every one of our 13 losses carries site ACPL 31–146; every draw carries 1–25; every win 4–35. There is no overlap. We lose **22.0%** of games; Poincare 15.3%, Patzer 15.6%, AlphaFish **9.6%**. We win about as often as anyone. The entire gap is the loss column. |
| **The target is not the ladder** | `Info.md` line 78: *"The ladder only seeds the final Swiss."* Line 80: *"a 13-round Swiss over the locked builds decides the order the 50 London seats fill, by points."* **The build locked at Friday 11:00 is the entire deliverable.** Twenty ladder rounds remain before lock; they are free validation on the real hardware, not score. |
| **The bar may be lower than the leaderboard says** | The final Swiss is entered only by teams with a UK university student. **AlphaFish (#3), Patzer 2.4 (#4) and AI Fellow (#11)** are listed "International" — one of 44 university values, used by 110 of 431 teams. If that means no UK member, the strongest engine on the ladder is not in our Swiss. **Inference, not fact. One email settles it and it is worth 30–55 points of bar.** |
| **The instrument has a defect nobody caught** | `agent._budget` has four **absolute** clock thresholds that `node_gate.py` copies while scaling only the increment. At `--tc 5+0.05` the engine plays **20 ms a move from move 10 to the end of every game**; at 10 s from move 30; at 30 s for the last ~15 moves. **Every "5 s" and "10 s" verdict this week, including V6.5's headline +118 ±23, was a fixed-node verdict wearing a clock.** Four lines fix it. Section 3. |
| **Width has peaked** | 1536 is running at **−89 ±65 (40/400) against k96** at 30 s + 0.125. Consistent with first principles: 1024 already costs 2.38× the nodes for +68 of evaluator, and 12.6 MB of weights is past L3. Treat wider nets as closed unless the final number says otherwise. |
| **Honest odds** | Top five in the final Swiss **0.40** (0.50 if the International teams are out, 0.32 if in). *Comfortably* top five **0.22**. First at the London knockout **0.08**. Section 11. |

---

## 1. The V8 thesis, and the numbers that have to earn it

The directive is that V8's characteristic is converting **draws into wins and losses into draws**.
That is the right frame. It is also a claim, so here is the evidence for each half, including the
part that does not survive contact with the data.

### 1.1 Half two first, because it is the solid half: losses into draws

Measured across all 59 rated games (`intel/raw/BINI_Alpha.json`, site evaluations at Stockfish 16
depth 16):

| result | site ACPL range |
|---|---|
| our wins | 4 – 35 |
| our draws | 1 – 25 |
| **our losses** | **31 – 146** |

No overlap. A game we lose is a game in which our move quality collapsed; a game we draw is a game
in which it did not. R87 is the proof of concept: **−313 against a peer, saved at ACPL 8.**

And the loss column is the whole gap:

| | record | **loss rate** | score |
|---|---|---|---|
| AlphaFish | 38-28-7 | **9.6%** | 71.2% |
| Poincare | 22-28-9 | 15.3% | 61.0% |
| Patzer 2.4 | 31-34-12 | 15.6% | 62.3% |
| Mite | 20-27-10 | 17.5% | 58.8% |
| SoberPaschoud | 32-30-15 | 19.5% | 61.0% |
| Capablanca | 34-27-17 | 21.8% | 60.9% |
| **BINI Alpha** | **27-19-13** | **22.0%** | **61.9%** |
| stockfih (the rating leader) | 30-23-20 | 27.4% | 56.8% |

We win as often as anyone in this table. Patzer scores 62.3% with a *worse* win count than ours
and a loss rate 6 points lower. **Cutting our loss rate from 22% to 14% while holding the win rate
moves our score from 61.9% to about 66.5%, which is +33 Elo, with no new wins at all.**

Note the honest nuance: the collapse pattern is not ours alone. Mite's losses run ACPL 32–86,
Poincare's 35–89. The exception is AlphaFish, whose losses run 0–54 — it loses well-played games,
rarely. So the target is not "stop collapsing", it is "collapse less often", and the levers are the
ones that reduce error on hard positions.

**Where the collapses actually happen** (2,498 of our counted moves against AlphaFish's 5,267):

| bucket | our mean cp loss | AlphaFish | our ≥100 cp rate | AlphaFish |
|---|---|---|---|---|
| moves we spend **> 4 s** on | **30.0** | **6.8** | **9.09%** | **0.00%** |
| 20–40 pawns of material on board | 20.2 | 9.4 | 2.69% | 0.96% |
| |eval| 50–300 | 23.6 | 15.1 | 5.4% | 1.9% |
| endgame (< 20 material) | 3.1 | 4.8 | 0.00% | 0.93% |
| opening (> 60 material), since R60 | 11.4 | 9.7 | 0.43% | 0.35% |

Three readings, all measured. The book fixed the opening (20.1 → 11.4 cp since R60). We do not
blunder in endings. **And the harder the position — measured by our own decision to spend more than
four seconds on it — the worse we get relative to them: 30.0 cp against 6.8, a 4.4× gap on exactly
the moves that decide games.** `PLAN_V4.md` line 22 reached the same place from the other end: our
four losses at that time contained *no tactical blunder at all*, only evaluation slides of 100–300
cp over 6–10 quiet moves in closed structures, with healthy clocks.

So the levers for half two are: **the clock policy** (we leave 12.5% of it unused and our
"think longer" trigger cannot see a slow drift — section 6.1), **correction history** (already
shipped in V7k, +40 fixed / +24 timed, attacking exactly this), and **move-ordering features that
raise quality on hard positions** (capture history, double extensions).

### 1.2 Half one, and the part of it the data refuses

R88 is the case in evidence: our engine's own trace shows +70 at our move 22 and +48 at move 35,
both gone within one to three moves, at site ACPL 3 / 98.8% accuracy, against an opponent who
played one blunder and one mistake. Then a queen-and-pawns ending and 200 moves of perpetual check.

The natural conclusion — "we fail to convert small edges" — is **wrong**, and it is worth being
exact about why, because a plan built on it would waste the last day. Bucketing every analysed game
of seven engines by the **peak evaluation the side ever reached**:

| team | games with peak +50…+150 | W | D | L | score |
|---|---|---|---|---|---|
| **BINI Alpha** | 8 | **0** | 5 | 3 | 31.2% |
| AlphaFish | 8 | **0** | 4 | 4 | 25.0% |
| Mite | 4 | **0** | 3 | 1 | 37.5% |
| stockfih | 15 | **0** | 7 | 8 | 23.3% |
| Patzer 2.4 | 11 | **0** | 6 | 5 | 27.3% |
| SoberPaschoud | 10 | **0** | 6 | 4 | 30.0% |
| Capablanca | 9 | **0** | 5 | 4 | 27.8% |
| **total** | **65** | **0** | **36** | **29** | **27.7%** |

**Zero wins in 65 games, across every engine on this ladder including AlphaFish.** A game whose
maximum evaluation is +50 to +150 is not a game anyone wins from curated near-level openings. Our
31.2% is the second-best figure in the table. R88 was a par result, not a failure, and any plan
that promises to win those games is promising something unprecedented here.

**But the directive is still right, because the conversion happens one band earlier.** The same
data, read as a distribution:

| team | peak < +50 | +50…+150 | +150…+300 | **peak ≥ +300** | conversion from ≥ +300 | overall score |
|---|---|---|---|---|---|---|
| **AlphaFish** | 29% | 12% | 2% | **58%** | 34/38 = 92% | **68.2%** |
| **BINI Alpha** | 34% | 16% | 0% | **50%** | **24/25 = 96%** | 60.0% |
| Capablanca | 34% | 12% | 4% | 49% | 34/36 = 96% | 60.3% |
| SoberPaschoud | 35% | 14% | 5% | 46% | 30/34 = 88% | 56.1% |
| stockfih | 30% | 23% | 2% | 45% | 26/30 = 87% | 52.3% |
| Patzer 2.4 | 40% | 15% | 3% | 43% | 29/32 = 91% | 56.0% |
| Mite | 51% | 9% | 2% | 38% | 17/18 = 94% | 57.4% |

**We convert better than anybody (96%). We reach the winning band less often than AlphaFish (50%
against 58%).** That is the whole of half one, stated so that it can be measured: *raise the share
of games whose peak evaluation reaches +300*. Every eight percentage points there is worth about
four extra wins per fifty games.

**And there is a measured behavioural defect that explains it.** Captures and material liquidation
per own move, split by whether the side is ahead by more than +150 or level within ±50:

| team | capture rate ahead | level | **ratio** | **pawns of material removed per own move when ahead** | level |
|---|---|---|---|---|---|
| **BINI Alpha** | 25.4% | 13.9% | **1.82** | **0.76** | 0.37 |
| Poincare | 22.8% | 15.6% | 1.46 | 0.71 | 0.41 |
| Mite | 22.0% | 14.2% | 1.54 | 0.61 | 0.37 |
| SoberPaschoud | 19.3% | 13.8% | 1.39 | 0.60 | 0.37 |
| stockfih | 19.8% | 17.6% | 1.12 | 0.58 | 0.46 |
| Patzer 2.4 | 17.7% | 13.4% | 1.32 | 0.52 | 0.35 |
| Capablanca | 18.0% | 14.3% | 1.26 | 0.51 | 0.38 |
| **AlphaFish** | 17.6% | 12.3% | **1.43** | **0.51** | 0.32 |

**We are the worst of eight on both measures.** When we are ahead we liquidate half again as fast
as AlphaFish. That is the classic engine anti-pattern — an evaluation that likes being up material
and therefore likes trading, with no term saying that trading toward a drawn structure throws the
win away. It is also exactly what R88 shows: a small edge, then a trade into a queen ending, then
200 moves of perpetual check.

**So half one, restated so it can be earned:**

> V8 does not learn to win from +70. V8 stops giving +70 back. The measurable target is the share
> of games reaching +300, from 50% toward 56%, by not liquidating an edge; our existing 96%
> conversion does the rest.

### 1.3 What the combination is worth, honestly

Base: 27-19-13 in 59 analysed rated games = 61.9%, peak ≥ +300 in 50% of games.

| if | change | new record per 59 | score | Elo vs the field |
|---|---|---|---|---|
| half one lands (peak ≥ +300 rises 50% → 56%, converted at 96%) | +3.4 games from draw to win | 30.4-15.6-13 | 65.0% | +28 |
| half two lands (loss rate 22% → 14%) | +4.7 games from loss to draw | 27-23.7-8.3 | 65.9% | +33 |
| **both** | | **30.4-20.3-8.3** | **69.0%** | **+56** |
| P(half one lands) | 0.35 | | | |
| P(half two lands) | 0.50 | | | |
| P(both) | 0.18 | | | |
| **expected** | | | **65.0%** | **+28** |

That is the number V8 is allowed to claim: **an expected +28 cross-engine Elo from the asymmetry
work, +56 if both halves land**, on top of whatever the remaining generic levers give (section 6).
It is not asserted; every input above is a count from the game record.

---

## 2. The target: a 13-round Swiss, not the ladder

Verbatim from `Info.md` lines 76–95:

- *"Ladder — rated rounds every hour, 08:00 to 22:00 … **The ladder only seeds the final Swiss**"*
- *"Qualification — **a 13-round Swiss over the locked builds decides the order the 50 London seats fill, by points.**"*
- *"Tie-breaks — points, Buchholz, head-to-head, **earlier final submission**"*
- *"Uploads close — 11 September 11:00"*
- *"Eligibility — … **A team enters the final Swiss if at least one member is a UK university student**"*

**2.1 Ladder rounds are validation, not score.** Measured from `intel/history`: one round an hour,
08:00–22:00 only (R75 stood still from Tuesday 22:45 to Wednesday 08:45). About **20 rounds remain
before lock**. Measured rating dynamics over 2,296 cached games: a win is +57, a draw +4, a loss
−44. Twenty rounds could reprice us by 200 points and it buys only a round-1 pairing. **Do not
trade build quality for ladder rounds. Do read every ladder log** — it is the only place we see
real init times, real clock curves and real failures.

**2.2 In a 13-round Swiss for a top-five finish, one loss to the field ends the run.** With ~300
eligible teams and about ten engine-grade entries, the leaders finish on 11–12.5 of 13, decided on
half points and Buchholz. This is the strongest possible argument for half two of the thesis.

**2.3 "Earlier final submission" is the fourth tie-break.** If Friday's candidate is not clearly
better, **do not upload**. The default on Friday morning is to keep what we have.

**2.4 We never see the opponent.** `get_move(fen, time_left_ms)`. Every "exploit team X" line in
`intel/STRATEGY.txt` is unactionable inside the engine. Contempt and draw policy are one fixed
number for all opponents.

---

## 3. The instrument, corrected — read before running anything

Every mistake this week came from an instrument that could not see the thing being changed: the
1024 net rejected three times on fixed nodes and 5 s gates before winning at a platform-like clock;
correction history +40 fixed against +24 timed; SEE_Q +20 against a stale baseline and +4 ±11
against the shipped one. There is a fourth defect and it is larger than all of them.

### 3.1 The `_budget` scaling defect (new)

`agent._budget` mixes relative terms with **absolute** thresholds — `time_left < 4000` (emergency,
20–40 ms a move), `< 10000`, `< 30000`, `RESERVE_MS = 1500`. `tools/node_gate.py` copies the
function verbatim and scales only `INCREMENT_MS`. Simulating a 60-move game gives the budget the
engine actually receives:

| time control | move 0 | move 10 | move 20 | move 30 | move 40 | move 55 |
|---|---|---|---|---|---|---|
| **platform 120+0.5** | 3829 / 8425 | 3274 / 7204 | 2756 / 6063 | 2277 / 5008 | 1840 / 2148 | 1069 / 1222 |
| gate 60+0.25 | 1915 / 4212 | 1637 / 3602 | 1378 / 3031 | 1138 / 1599 | 920 / 1074 | 520 / 617 |
| gate 30+0.125 | 957 / 2106 | 819 / 1562 | 689 / 1139 | 569 / 800 | 460 / 537 | **50 / 100 emergency** |
| gate 10+0.05 | 324 / 697 | 279 / 528 | 236 / 388 | **20 / 40 emergency** | **20 / 40** | **20 / 40** |
| gate 5+0.05 | 177 / 363 | **20 / 40 emergency** | **20 / 40** | **20 / 40** | **20 / 40** | **20 / 40** |

A 5 s gate plays 20 ms a move — about 15k nodes — from move 10 onward. It is a fixed-node gate at a
*lower* node count than our fixed-node gate. **This invalidates every 5 s and 10 s verdict as a
real-clock result**, including P1's +58, R1's +52, P2's −25 (the first 1024 rejection) and V6.5's
headline +118 ±23 / +131 ±41. They remain valid fixed-node results, and V6.5 is very probably a
real gain — the 30 s gates and the 52.5% proxy agree — but no future ladder may be built from them.

**Fix, `tools/node_gate.py` only, never `agent.py` (which always runs at 120 s):**

```python
CLOCK_SCALE = base_ms / 120_000.0      # 1.0 at 120+0.5, 0.5 at 60+0.25, 0.25 at 30+0.125
# inside _budget, replace the four absolute constants with
#   4000*CLOCK_SCALE, 30000*CLOCK_SCALE, 10000*CLOCK_SCALE, RESERVE_MS*CLOCK_SCALE
```

Verify by printing the budget curve at `--tc 120+0.5` and checking it matches `agent._budget`
exactly.

### 3.2 The instrument table

| Name | Shape | Correct for | Blind to | Cost | 95% CI |
|---|---|---|---|---|---|
| **F30k** | `--nodes 30000 --games 1152` `--workers 24` | tree-shape changes and evaluator quality at equal nodes; **contempt**; move ordering; extensions | anything changing ns/node; depth-dependent effects | ~10 min GPU | ±14 |
| **T60** | `--tc 60+0.25 --games 576 --workers 32` *(patched)* | clock policy screen, search features, book | absolute depth; cache pressure | ~40 min GPU | ±22 |
| **T120** | `--tc 120+0.5 --games 576 --workers 24` | everything structural; the ship decision | blind spots we share with ourselves | ~2 h GPU | ±22 |
| **T120-lo** | as T120, `--workers 12 --pin` | width and speed trade-offs without cache contention | as above | ~4 h | ±22 |
| **PROXY** | `proxy_match.py --games 40 --nodes 20000` at 120+0.5 | foreign opponent, real clock | tiny sample | ~3 h VM | ±110 |
| **BATTERY** | `tools/battery.sh <dir>` | crashes, illegality, init, exactness | Elo | ~30 min Mac | n/a |

**Rules, pre-committed.**

1. Anything that changes **nanoseconds per node** — net width, an eval term such as drawishness or
   anti-simplification, extra per-node work — is *screened* on F30k and **decided on T120**
   (T120-lo if width is involved). F30k sees the benefit and is blind to the cost.
2. Anything that changes **tree shape only** — search features, move ordering, extensions, and
   **contempt**, which costs nothing per node — is **decided on F30k with ≥ 1152 games**, then
   confirmed once inside the shipping combination at T120. Twelve times cheaper and correct.
3. Anything that touches **the clock** is decided at **T120 only**.
4. **Tune against the current shipping config, never a historical baseline.**
5. **Two points on a monotonic axis** before a lever is declared dead.

### 3.3 The second metric every gate must report

Elo alone cannot judge half one of the thesis: a change that turns draws into wins *and* losses is
Elo-neutral by construction. `node_gate.py` already tallies a pentanomial and writes every game to
`PREFIX.json`, so **report the decisive-game rate (1 − draw rate) for side A beside the Elo on
every gate**, and the loss rate for half two. The acceptance rules in section 7 use both.

### 3.4 The throughput unlock

The GPU box has a **92-CPU quota** and the labelling fleet is now pointless (712M vs 490M rows at
matched compute = +2 ±22). Gates, not training, are the bottleneck — a bullet run is 2–7 minutes, a
timed gate on the 8-vCPU `gcp-x86` is two hours. At 24 workers a **576-game T120 at the exact
platform clock costs about two hours** and has never been run. Budget for four of them.

**Trap:** at 40 workers, 80 copies of a 12.6 MB net thrash L3 and penalise the *wider* net in a way
the platform never will, where one game owns the machine. Width comparisons run at ≤ 12 workers.
Stagger process starts and give each worker its own `NUMBA_CACHE_DIR`.

---

## 4. R88, and how to tell the four candidate mechanisms apart

The engine's own trace (`~/Downloads/aichessathon-round-88-omi.log`) is more informative than the
result. Extracted scores, our moves:

```
m17  +12   m18   +2   m19  -1   m20 -20   m21 -20   m22 +70   m23 +58   m24 +50
m25  +10   m26  -20   m27 -20   m28 -20  ...  m37..m52 all -20  ...  m207..m261 ~ -1..+4
```

**The −20 plateau is not an evaluation. It is contempt.** `bini_engine.py` sets
`info[I_CONTEMPT] = 20` and the search scores a draw as `−contempt` for us. A root score of exactly
−20, repeated for dozens of moves and appearing as early as move 4, means *"the best line I can
force ends in a repetition, and I value that at −20"*. The engine was never confused about the
position; it knew it was drawn and said so.

That immediately discriminates two of the four candidates:

| candidate | what R88 says | verdict |
|---|---|---|
| **(b) eval optimism / calibration** | the engine scored the position as a **draw** for 200 moves and at −1 to +4 in the queen ending. It was not optimistic; it agreed with the result. | **not supported by this game.** Rank low. |
| **(a) drawishness knowledge** (`endgame_scale` fires only when the board is pawnless: `if bb[0] != ZERO or bb[6] != ZERO: return score`) | the search already returned a draw score long before the queen ending. A drawishness term would have told it what its own search told it. | **would not have changed R88.** It could still matter at the *moment of the trade* — see the discriminator below. |
| **(c) contempt** | directly implicated: the engine compared an uncertain +30 against a certain −20 and took the −20. | **supported.** |
| **(d) anti-simplification when ahead** | supported by R88's queen-ending trade *and*, far more strongly, by the eight-team measurement in section 1.2: we are the worst of eight. | **strongest.** |

**The discriminator the coordinator asked for, and a better one.** The site's per-position
evaluations for R88 are not yet scraped (`intel/raw/BINI_Alpha.json` reaches R87, fetched
18:49Z; the pipeline refreshes hourly). Run `intel/refresh.sh` after the next cycle and compare
Stockfish 16 depth 16 at our moves 22–36 with the trace above. If the site also said +50 to +70,
(a)/(d); if it said ~0, (b). **But do not wait for it, and do not decide on one game.** The
eight-team simplification table is 20,000 moves and it already answers the question: our
liquidation rate when ahead is an outlier, and it is not a one-game artefact.

**A second, cheaper discriminator that separates (a) from (d) directly.** Both are eval terms with
the same per-node cost profile, so run them as two arms of the same F30k screen and read the
decisive-game rate, not just Elo:
- if the **drawishness** arm raises the decisive rate, the engine was walking into structurally
  drawn endings it could not see;
- if the **anti-simplification** arm raises it, the engine was trading edges away before any
  ending existed;
- if neither moves it, the +50–150 band is simply not winnable (which is what the 65-game table
  above already says) and the effort belongs entirely in half two.

---

## 5. The top five, and what is exploitable

| | Rating | Record | CPL | site ACPL | Blunder% | s/move | Book | End clock | Games < 5 s |
|---|---|---|---|---|---|---|---|---|---|
| stockfih | 2821* | 30-24-20 | 15.7 | 23 | 0.4 | 2.02 | yes (15%) | 23 s | 8 of 73 |
| Mite | 2771* | 20-28-10 | 10.2 | 20 | 0.2 | 1.77 | yes (49%) | 24 s | 2 of 57 |
| AlphaFish | 2741 | 39-28-7 | **7.5** | 16 | **0.1** | 1.56 | no | 27 s | 1 of 73 |
| Patzer 2.4 | 2700* | 31-34-13 | 11.2 | 18 | 0.5 | 1.56 | no | 36 s | 0 of 77 |
| Poincare | 2669 | 22-28-10 | 11.7 | 17 | 0.2 | 1.63 | no | 38 s | 0 of 59 |
| **BINI Alpha** | 2493* | 27-20-13 | 15.6 | 25 | 0.8 | 1.84 | yes | 35 s | 0 of 63 |

*= provisional. **The rating leader is not the strongest**: stockfih sits at 2821 on CPL 15.7,
0.4% blunders and a 56.8% score, while AlphaFish scores 71.2% eighty points lower. stockfih's
number is a fresh-upload Glicko artefact on a good run; its real profile is quality fading late
(11.4 → 18.2 cp after move 40), 8 games under 5 s, two repetitions given away while ahead.

**Exploitable, honestly:**
1. **Long, complicated games.** stockfih (8), ms (27), PSL (9), AI Fellow (44), test_bot (41),
   Astral (46) drop under 5 s. We have never been under 5 s in 63 games.
2. **Nobody spends extra time after a swing.** AlphaFish's longest think in 73 games is **4.4 s**.
   A variable clock is a genuine structural edge and we are under-using it (section 6.1).
3. **Free half points:** stockfih 2, AlphaFish 1, ms 1, AI Fellow 5, Danya 2 repetitions accepted
   while more than +150 ahead. `BINI_DRAW_BEHIND=1` already harvests these — keep it.
4. **There are no swindles at the top:** 126 of 138 positions at +300 were converted. The game is
   decided at the first −300.
5. **Our book is a differentiator** — three of the top five have none.
6. **Caution on contempt:** the top five accepted about 70 *level* repetitions and only 3 while
   ahead. They take level draws. Raising our contempt is a trade, not free money.

**Not exploitable:** anything opponent-specific. We never see who we are playing.

---

## 6. Where the remaining Elo is

**Measured out. Do not reopen.** Data volume (+2 ±22 for 712M vs 490M). Superbatches past 96
(144 = −2). King buckets (16 vs 8: +14 vs +15). Eleven search constants (LMR_DIV was the only bad
one, fixed at 1.6, +31 ±11 over 1,728 games; SEE_Q re-measured on the shipped config +4 ±11;
LMR_BASE +2 ±14). numba inference speed (seven implementations in situ; the shipped scalar loop at
702 ns wins; `Info.md` line 40 — no compiler on the image). ProbCut −8, qs_checks −10, improving −7.
**Width** is now all but closed too: 1536 is at −89 ±65 (40/400) against k96.

| # | Lever | Half of the thesis | P(clears) | Elo if it lands | EV | Instrument |
|---|---|---|---|---|---|---|
| 6.1 | Clock policy: spend the 12.5% we leave; a drift trigger | **two** | 0.55 for ≥ +10 | +10 to +20 | **+8** | T120 |
| 6.2 | **Anti-simplification when ahead** | **one** | 0.40 for the acceptance rule | +8 to +18 and −4 pt draw rate | **+6** | F30k screen → T120 |
| 6.3 | Search features never implemented: capture history, double extensions, razoring | **two** | 0.35 each for ≥ +10 | +10 each | **+10** | F30k 1728 |
| 6.4 | Contempt 20 → 32 → 45 | **one** | 0.40 for the acceptance rule | Elo-neutral, −5 pt draw rate | **+4** | F30k 1728 |
| 6.5 | Drawishness beyond pawnless (`endgame_scale`) | **one** | 0.30 for the acceptance rule | +5 to +15 | **+4** | F30k screen → T120 |
| 6.6 | Eval output scale — the ninth constant, never swept | both | 0.35 for ≥ +15 | +15 to +25 | **+6** | F30k 1152 |
| 6.7 | Output buckets 8 → 16 or 32 (free at inference) | both | 0.25 for ≥ +12 | +12 to +20 | **+4** | F30k 1152 |
| 6.8 | Book breadth (opponent replies, 2–3 deep) | two | 0.45 for ≥ +8 | +8 to +15 | **+5** | T120 |
| 6.9 | Second hidden layer 1024 → 32 → 1 | both | 0.30 lands × 0.5 for ≥ +25 | +25 to +50 | **+6** | F30k → T120-lo |
| | **total** | | | | **≈ +53 gate ≈ +38 cross-engine** | |

**6.1 Clock policy.** Over our last 13 rated games (R74–R87, 998 own moves) we used 1,802 s of a
2,059 s budget and left **257 s — 12.5% — unused**, and our longest think in any of them was 8.3 s.
After move 40 the `time_left < 30000` branch caps *hard* at about 2.1 s, a 2.3× cut exactly where
games are decided.
- **T1 (spend it):** `mtg` 34 → 29, `< 30000` → `< 20000`, that branch's cap `t/15` → `t/11`.
  **Leave the `< 10000` and `< 4000` emergency floors untouched** — we have never been under 5 s in
  63 games and must not start.
- **T2 (spend it where we lose):** the "danger" multiplier fires on `best_score < prev_score − 25`
  for a *single* move. Our losses are drifts of 10–20 cp per move over 6–10 moves, so it never
  fires. Keep a rolling window of the last three root scores in `Engine.think` — pure Python,
  ~10 lines, `self.prev_score` already exists at line 267 — and apply 1.6× when the score has
  fallen ≥ 40 cp across them. This is aimed at exactly the failure mode section 1.1 measures.

**6.2 Anti-simplification.** The single most evidence-backed new term. In `bini_eval.py`, when the
side to move is ahead by between +40 and +180 after the network, subtract a small penalty
proportional to how little material remains — i.e. make trading toward a bare position cost
something while the edge is small. Constants only, no position lookup, rules-legal as a tuned
evaluation term. Start at a penalty of 12 cp per 8 pawns of total material removed below 40, and
sweep two points before any verdict.

**6.4 Contempt.** Now behind `BINI_CONTEMPT` (added today, untested). This is the only lever whose
*objective* is not Elo: raising contempt converts draws into wins **and** losses symmetrically, so a
self-play Elo gate will read it as roughly neutral by construction. For a 13-round Swiss where a
top-five finish needs ~11.5/13 and the peers draw each other 40–50% of the time, mild
variance-seeking is correct — but only if it is genuinely free. Acceptance rule in section 7.

**6.6 Eval output scale.** Every margin in the search is a centipawn constant (RFP 75, futility 100,
SEE 60·depth, contempt 20, draw trigger −100, singular `tts − 2·depth`), all tuned against an older
net's scale. The shipped k96 net carries `out_scale 1.0` and its scale relative to v3b has never
been checked — only R1's was (slope 0.982). It can be swept with **zero code risk** by re-exporting
the same checkpoint: `bullet_export.py --out-scale 0.88 / 0.94 / 1.06 / 1.13`, then a `BINI_NNUE=`
A/B. Four exports, four gates, 45 minutes.

**On `bini_calib.py`: rank it last, and prefer 6.6.** Three reasons. (i) R88 shows the engine
agreeing with a draw for 200 moves — not optimism. (ii) The table is a per-bucket *median residual*
of `net − k·label` on an axis (material imbalance) that is strongly correlated with the label, so
any error in the global slope `k` becomes a large apparent bias in the extreme columns — which is
exactly what the table shows (−370 and +356 cp). That is a slope artefact. (iii) The piece-count
axis is **already modelled by the net**: the shipped architecture is `8x768x1024x2->8`, eight
*output buckets indexed by piece count* (`bini_nnue.out_bucket`). A hand-fitted per-piece-count
offset is redundant with a learned per-piece-count output head, and its measured effect on the
current net is −31.

**6.9 Second hidden layer.** The only thing that could move us 30–60 in one step; bullet trains it
natively and the extra layer costs ~32 multiplies against 2,048 today. All the risk is engine-side:
a new jitted forward pass, a new export path, `test_nnue.py` exactness on 3,958 positions.
**Strictly a parallel track with a hard kill at Thursday 14:00.**

---

## 7. Experiment list — ranked, dated, thresholds fixed in advance

**Global ship rule.** A change enters the shipping build only at **≥ +20 at T120 with the 95%
interval clear of zero**, or **≥ +25 at F30k over ≥ 1152 games** for a tree-shape-only change plus a
non-negative T120 on the combination. The combination is always gated as a whole; additivity is the
real open question (V6.5's components predicted +132 and the combination measured +118).

**Thesis acceptance rules — these are what let V8 claim the asymmetry.**
- **Half one (draws into wins).** A change qualifies if, over 1,728 F30k games against the shipping
  build, **Elo ≥ −8 with the interval clear of −20 AND the decisive-game rate rises by ≥ 4
  percentage points**; then the same two conditions at T120 over 576 games. A change that only
  raises the decisive rate by turning draws into losses fails: the *win* share must rise.
- **Half two (losses into draws).** A change qualifies if, over 576 T120 games, **Elo ≥ +12 AND
  side A's loss rate falls**, with no closed-slice veto.

**Global kill rule.** Two points on a monotonic axis before a lever is dead. One gate below
threshold kills a *variant*, not a *lever*.

| ID | Experiment | Instrument | When | Machine | Ship threshold | Kill rule |
|---|---|---|---|---|---|---|
| **I0** | Patch `node_gate.py`'s four absolute clock constants by `CLOCK_SCALE`; verify the 120+0.5 curve matches `agent._budget` | unit check | **Wed 21:15, before anything** | Mac | must pass | blocks everything |
| **I1** | T120 harness proof: 96 games, A = B = V7k, 24 workers | T120 | Wed 21:45 | GPU | 50.0% ± noise, zero timeouts, min end clock > 5 s | if it fails, fall back to patched T60 for everything |
| **I2** | Add decisive-rate and loss-rate reporting to the gate log from `PREFIX.json` | tooling | Wed 21:15 | Mac | must pass | blocks the thesis rules |
| **N1** | 1536 finishes its 400-game 30 s gate; 2048 screened at F30k | F30k 1152 | Wed 23:00 | GPU | ≥ +25 to earn T120-lo | early read is −89 ±65; expect both dead. **Two points, then close width for good.** |
| **A1** | **Anti-simplification term**, two strengths (12 and 24 cp per 8 pawns below 40) | F30k 1728 each | **Thu 00:00–01:00** | GPU | half-one rule | both points fail → term dead |
| **A2** | **Contempt 32 and 45** | F30k 1728 each | Thu 01:00–02:00 | GPU | half-one rule | Elo < −8 at 32 → close; do not test 45 |
| **A3** | **Drawishness in `endgame_scale`**: opposite-coloured bishops, Q+P vs Q+P, rook ending with all pawns on one wing, wrong rook pawn | F30k 1728 | Thu 02:00–03:00 | GPU | half-one rule | fails → dead; do **not** stack it with A1 untested |
| **E1** | Eval output scale 0.88 / 0.94 / 1.06 / 1.13 | F30k 1152 each | Thu 03:00–04:00 | GPU | ≥ +20 → T120 | flat inside ±14 → the scale is right, close it |
| **E2** | Output buckets 16 and 32 | F30k 1152 | Thu 04:00–04:40 | GPU | ≥ +20 → T120 | two points < +20 → closed |
| **F1** | Capture history table (~25 lines) | F30k 1728 | Thu 04:40 | GPU | ≥ +12 | < +12 → dead |
| **F2** | Double extensions on singular fail-low by > 20 (~4 lines) | F30k 1728 | Thu 05:20 | GPU | ≥ +12 | < +12 → dead |
| **F3** | Razoring at depth ≤ 2 (~3 lines) | F30k 1728 | Thu 06:00 | GPU | ≥ +12 | < +12 → dead |
| **B1** | Book breadth: opponent's top-3 replies at our first three book moves over all 308 curated roots, 30 s each, entries ≤ 15 cp | CPU job | Thu 02:00–05:00 | GPU spare threads | ≥ 3× early-move coverage on a replay of our 63 games | < 2× → no gate slot |
| **T1** | Clock: `mtg` 34→29, `<30000`→`<20000`, cap `t/15`→`t/11`; emergency floors untouched | **T120 576** | **Thu 06:30–08:30** | GPU | half-two rule, **and min end clock across all 576 games > 4 s** | any flag or any game ending < 2 s → dead immediately |
| **T2** | Drift trigger: 3-move rolling root score, 1.6× when down ≥ 40 cp | **T120 576** | Thu 08:30–10:30 | GPU | half-two rule, same clock safety | as T1 |
| **X1** | 1024 → 32 → 1 second layer: bullet run, exporter, jitted forward pass, `test_nnue.py` exactness | F30k → T120-lo | Wed 22:00 → **hard kill Thu 14:00** | second track | exactness green **and** ≥ +30 at F30k | not green by 14:00 → deleted, no extension |
| **Q1** | Closed-structure veto slice: 150 positions from our own lost games in Sicilian Closed / Ruy Closed / English Symmetrical / London / Grunfeld, as a second `--openings` file reported separately | inside C1 | built Thu 02:00 | GPU | reported, not decisive | ≥ 25 worse on the slice with the interval clear of zero → **does not ship** |
| **C1** | **Combination gate**: everything that cleared, vs V7k as uploaded | **T120 576** | **Thu 14:00–16:30** | GPU | ≥ +25, interval clear of zero, **and the decisive-rate and loss-rate conditions both hold** | below → ship the largest single cleared change alone |
| **C2** | Absolute anchor: candidate vs Stockfish at 20k nodes, 200 games at 120+0.5 | foreign opponent | Thu 16:30–19:00 | GPU + VM | ≥ 55% (V6.5 52.5% at n=20, V6.0 37.5%, v3b 46%) | < 45% → do not ship whatever C1 says |
| **S1** | **Upload V8.0** | ladder | **Thu 20:00** | Mac → Archit | C1 and C2 clear, battery green on the exact bytes, no Q1 veto | any fail → V7k stays live |
| **R1** | Overnight re-gate of the one change that missed by less than its interval | T120 576 | Thu 21:00 – Fri 06:00 | GPU | ≥ +20 | else nothing |
| **S2** | **Upload V8.1** | ladder | **Fri 10:00, hard stop 10:30** | Mac → Archit | ≥ +20 over V8.0 at T120 and battery green | **default is not to upload**; "earlier final submission" is the fourth tie-break |

**Optional, overnight only, must never take threads from a gate:** relabel the endgame shards
(≤ 16 pieces, ~10M rows) at depth 13 instead of 7 and fine-tune k96 on the mix. Depth 7 is weakest
where a queen ending is decided. P(≥ +15) ≈ 0.20; cost ~3.5 h of otherwise idle CPU. Judge at F30k
against k96, then the half-one rule. **Do not download 6-man tablebases** (150 GB) or ship any
tablebase: ≤ 5-piece positions are a fraction of a percent of the training set and our conversion
from +300 is already 96%.

---

## 8. Schedule to Friday 11:00

Ladder rounds run 08:00–22:00, one an hour; **about 20 remain before lock**. They are validation.

| When (London) | GPU box (2×5090, 92 threads) | VM / `gcp-x86` | Mac / Archit | Hand-over |
|---|---|---|---|---|
| **Wed 21:15** | stop the labelling fleet, free all 92 threads | — | **I0**, **I2** | — |
| Wed 21:45 | **I1** harness proof | — | confirm V7k's live md5 and init line | — |
| **Wed 22:00** | **X1** starts (second track); N1 finishes | — | write the provenance note (section 10) | **V7k live since 20:27; record its platform init time from the first R89 log** |
| Wed 23:00 – Thu 06:00 | **N1, A1, A2, A3, E1, E2, F1, F2, F3** — F30k queue, ~10–15 min each | **B1** book job on spare threads | asleep | — |
| **Thu 06:30** | **T1** T120 | — | read overnight verdicts; write them into `Project Prometheus.md` §13 | — |
| Thu 08:30 | **T2** T120; implement what cleared | — | assemble candidates | — |
| **Thu 12:00** | — | — | — | **Checkpoint A: what cleared, what died, which half of the thesis each serves** |
| **Thu 14:00** | **C1** combination T120 with **Q1** slice | — | **X1 hard kill** if exactness is not green | — |
| Thu 16:30 | **C2** anchor vs Stockfish | PROXY 40 on the VM | battery on the exact V8.0 zip | — |
| **Thu 20:00** | — | — | **S1: upload V8.0** if every threshold cleared | **Hand-over: five numbers (F30k, T120, decisive rate, loss rate, C2), init time, md5, diff vs V7k, rollback zip** |
| Thu 21:00 – Fri 06:00 | **R1** | — | asleep | — |
| **Fri 07:00** | — | — | read R1 and the Thursday ladder logs | **Checkpoint B: upload or hold** |
| Fri 09:00–10:00 | — | — | battery on the exact bytes if uploading | — |
| **Fri 10:00** | — | — | **S2 or nothing.** | **Final hand-over** |
| Fri 10:30–11:00 | — | — | confirm the dashboard shows the intended zip as the latest submission that passed validation | — |

**The 10:30 hard stop is not negotiable.** Validation runs a build plus two smoke games; "your
latest submission that *passed validation*" is what plays. Thirty minutes of slack buys the event.

---

## 9. Do not spend time on

| Do not | Because |
|---|---|
| Trying to win from +50 to +150 | **0 wins in 65 such games across seven engines**, AlphaFish included. Target the +300 share instead (section 1.2). |
| More training data | 712M vs 490M at matched compute = **+2 ±22**, three confirmations. |
| More superbatches past 96 | 24 = +13, 48 = +44, 96 = +59, **144 = +57**. |
| King buckets | 16 = +14 vs 8 = +15 at matched budget. |
| Wider nets | 1024 costs 2.38× the nodes; **1536 is at −89 ±65 against k96**; 12.6 MB of weights is already past L3 and 1536 is 18.9 MB. Close it after the second point. |
| Any of the eleven search constants | Swept. LMR_DIV was the only bad one. SEE_Q on the shipped config +4 ±11; LMR_BASE +2 ±14. |
| Vectorising the eval, leaving numba, int8 weights | Seven implementations measured in situ; the shipped scalar loop (702 ns) wins; no compiler on the image (`Info.md` line 40). A hot-cache microbenchmark said float was 3.9× faster; it is 17–29% *slower* in the engine. int8 needs a trainer change, an exporter change and a new exactness proof — not in 36 hours. |
| Syzygy tablebases at the root, or an endgame-holding gate slice | Conversion from +300 is **24 of 25**, better than AlphaFish's 34 of 38. Endgame cp loss 3.1 with **zero** ≥100 cp errors in 614 moves. Build the **closed-middlegame** veto slice instead. |
| `bini_calib.py` refit / `/tmp/calib_k96.json` | Section 6: slope artefact on the extreme columns, redundant with the net's eight piece-count output buckets, −31 measured, and R88 shows the engine agreeing with a draw rather than being optimistic. Replaced by the out-scale sweep, which is strictly better and carries no code risk. |
| ProbCut, qs_checks, improving | −8 ±19, −10 ±21, −7 ±19. |
| Any 5 s or 10 s gate | Section 3.1. The engine plays 20 ms a move for most of those games. |
| Farming ladder rating | The ladder only seeds the Swiss. |
| Re-rendering this as an artifact | Standing instruction: edit the markdown. |

---

## 10. Risks and their answers

1. **Init failure on the platform** (`init` = no ready line in 90 s = **loss**). V6.0 measured
   35.8–38.1 s on the platform against 22 s on the Mac; V7k carries a 12.6 MB net.
   `COMPILE_JOIN_S = 75` hedges. **After every upload, read the validation log's init line and the
   first rated game's log before anything else.** Over 55 s, roll back.
2. **A wider or heavier eval is punished harder on a slower box** — the platform machine looks
   roughly 1.7× slower than the Mac. This is why width is closing and why A1/A3 (eval terms with a
   per-node cost) must be decided at T120, not F30k.
3. **Cache contention faking a verdict.** Width and eval-cost decisions at ≤ 12 workers.
4. **A late change that breaks what V7k had right.** Friday's default is not to upload. Rollbacks:
   V7k (tonight's md5), V6.5 `6dd0c7181772e850f1a48cd8628a512f`, V6.0
   `3133e32644bbdc24c156f9dacea5f91e`. The battery runs on the exact bytes, every time.
5. **Contempt raising the loss rate while the thesis is about lowering it.** A2's acceptance rule
   explicitly requires the *win* share to rise, not just the decisive share. If contempt only adds
   losses, it fails its own gate — and the two halves of the thesis are then in tension, in which
   case **half two wins**: in a 13-round Swiss a loss costs more than a draw gains.
6. **Compliance.** *"a team that ships a network shows how it was trained"*; *"a database of engine
   moves or evaluations shipped for lookup at runtime is an engine, not training data"*. Write a
   one-page provenance note: the net is trained from random initialisation by `bullet` on ~490M
   positions we labelled ourselves with Stockfish 19 at depth 7 (`peer_label.py`,
   `label_fleet.py`), no published network as a start; the book is **our own engine's** search
   output (`tools/make_book.py` imports `bini_engine`, never Stockfish) and its `score`/`depth`
   fields are our engine's. Confirm no Stockfish output ships inside the zip. Thirty minutes,
   Thursday evening. The new eval terms (A1, A3) are constants, not lookups — say so explicitly.
7. **Known tooling traps.** `proxy_match.py --stockfish` is dead — `tests/uci_sf.py` hardcodes
   `Popen(["stockfish"])`, so the binary must be on PATH. An inline `pkill -f` pattern kills the
   shell carrying it. A stale `bini_*.py` on a gate box silently gates the wrong code: rsync the
   whole tree before every gate.
8. **Over-reading small samples.** 576 games is ±22; 40 games is ±60; 40 of 400 is ±65. Nothing
   under 576 games is a result, and the 1536 read is an early signal, not yet a verdict.

---

## 11. Honest odds

**Where V7k sits.** V6.0 reached a provisional 2495 on two rated games. V6.5 measured +118/+131 over
it, but on the instrument section 3.1 has just invalidated as a real-clock test; treat those as
fixed-node numbers, with the 30 s gates and the 52.5% proxy agreeing in direction. V7k adds +39 ±21
at 30 s. Self-play margins between related builds overstate cross-engine Elo by roughly 1.4–1.6×.
That puts **V7k at about 2600 true, 80% interval 2530–2690** — consistent with our last three rated
games (site ACPL 3, 7, 8, all drawn against ~2500 opponents).

**Where V8 lands.** Section 6's +53 gate Elo is about +38 cross-engine, of which the asymmetry work
is +28 in expectation (section 1.3). **V8 ≈ 2635, 80% interval 2560–2725.** If X1 lands, add 20–35;
that tail is where "a real shot at first" lives.

| Outcome | Probability | Reasoning |
|---|---|---|
| **Half two lands** (loss rate 22% → ≤ 15% in the gate's own loss column) | **0.50** | corrhist already shipped; T1+T2 target the measured drift; F1–F3 raise quality on hard positions |
| **Half one lands** (decisive rate up ≥ 4 pts with the win share rising) | **0.35** | A1 has the strongest evidence of the four candidates; A2 and A3 are backups |
| Both halves land — V8 earns the headline claim outright | **0.18** | |
| V8.0 ships Thursday at ≥ +25 over V7k on T120 | 0.60 | nine independent shots at a +20 threshold, most of them cheap |
| V8 true strength ≥ 2670 (today's fifth place) | 0.35 | needs 6.1 plus one of 6.2 / 6.3 / 6.9 |
| **Top five in the final Swiss** | **0.40** | 0.50 if AlphaFish, Patzer 2.4 and AI Fellow are ineligible; 0.32 if they are in |
| **Comfortably top five** (clear of sixth, not on Buchholz) | **0.22** | needs ~2700 true and a clean 13 rounds |
| Top ten in the final Swiss | 0.78 | the floor is V7k, already inside the top ~8 of the eligible field |
| Zero platform failures across the Swiss | 0.93 | 0 in 63 rated games; residual risk is the wider net's init |
| **First at the London knockout, 12 September** | **0.08** | needs a top-two build *and* five or six mini-matches won; the strongest entrant probably wins 25–30% of that bracket |

**What moves these most, in order.** (1) The `node_gate` patch and the first honest T120 gate —
everything downstream is only as good as the instrument. (2) T1 + T2, the largest EV, the cheapest
code, aimed at the exact failure mode our games show. (3) A1, the only new idea with a
twenty-thousand-move measurement behind it. (4) The eligibility answer, which decides whether we
play for a safe top five or need the risky tail. (5) X1 landing.

**What keeps them from being higher.** We are one build cycle behind the plan; three of the top five
have been measured for six days and remain 100–200 points above our converged rating; and 13 rounds
is a short tournament in which one loss to the field ends a top-five run. The floor is solid: V7k
with zero failures is a comfortable top-ten seat and the London seat itself is very likely.

---

## 12. What Archit does

1. **Tonight, one email to the organisers, two questions.** (a) Does a team listed "International"
   on the leaderboard enter the 13-round final Swiss, or does the Swiss contain only teams with a
   UK university student? (b) When does the final Swiss run — Friday after 11:00, or over the
   Friday ladder slots? Neither is answerable from the site and both change the plan. Highest-value
   five minutes available tonight.
2. **Tonight: bring back V7k's platform init time** from the R89 log and its clock curve.
3. **Thu ~20:00: upload V8.0**, only if the hand-over note carries all five numbers, a green
   battery on the exact bytes and no Q1 veto.
4. **Fri 10:00: usually do nothing.** Upload only if the note says ≥ +20 at T120. Hard stop 10:30;
   then confirm the dashboard shows the intended zip as the latest submission that passed
   validation.
5. **Keep the Mac quiet** during batteries and pressure games.
6. **Thursday evening: read the provenance note** and confirm you can explain, unaided, how the net
   was trained, where the book came from, and that the new evaluation terms are constants rather
   than a lookup table. A finalist team walks through this in person.

---

## 13. One paragraph for whoever picks this up next

V8's characteristic is one asymmetry: **losses into draws, and draws into wins.** Half two is solid
and is the whole rating gap — every loss we have carries site ACPL 31–146 and every draw 1–25, we
lose 22% of games against AlphaFish's 9.6%, and we win as often as anyone; the levers are the clock
policy (we leave 12.5% of the clock unused and our "think longer" trigger cannot see a slow drift),
correction history, and the ordering features we never implemented. Half one is real but must be
stated correctly: **nobody on this ladder wins from +50 to +150 — zero wins in 65 such games across
seven engines** — so the target is not converting small edges but keeping them until they become
+300, where we already convert 24 of 25; and the measured defect is that we liquidate 0.76 pawns of
material per move when ahead against AlphaFish's 0.51, the worst of eight teams. Before running
anything, patch `node_gate.py`'s four absolute clock thresholds: at 5 s the engine plays 20 ms a
move from move 10, so every 5 s and 10 s verdict this week was a fixed-node verdict in disguise;
then use the GPU box's 92 idle threads for real 120 s + 0.5 s gates at about two hours each, which
has never been done. Data, epochs, king buckets, width, eleven search constants and numba inference
speed are measured out — do not reopen them. The ladder only seeds a 13-round Swiss over the build
locked at Friday 11:00, so ladder rounds are validation and the default on Friday morning is not to
upload.
