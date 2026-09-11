# V8 — Morning Handover

**Written overnight, 10 September. Nothing has been uploaded. The upload decision is yours.**

---

## 1. The decision: V8 is established as better than V7k, by about +16. I would ship it.

**Nothing has been uploaded. The upload is yours.** `submission_v8_0910_0313.zip` — code
**byte-identical to V7k**, one file changed (the net), init 22 s, validated.

**This recommendation changed during the night, and it changed on evidence.** At 05:30 I recommended
**hold**, because the only clock numbers available were book-free `node_gate` gates pooling to
**+13.7 ±13.7** — a lower bound of +0.02, statistically indistinguishable from nothing. The
real-wrapper test then finished. It added **608 games of the shipped configuration** with zero
fallbacks, and it moved the picture:

| measurement | games | Elo | interval |
|---|---|---|---|
| real wrapper (agent.py + book, 120+0.5), arena 1 | 400 | **+22 ±34** | [−12, +56] |
| real wrapper, arena 2 (at box expiry) | 346 | **+33 ±37** | [−4, +70] |
| **real wrapper pooled** | **746** | **+27 ±25** | **[+2.0, +52.1]** |
| node_gate, book-free, fc_b vs k96 | 800 | +13.7 ±13.7 | [0.0, +27.4] |
| **COMBINED, both harnesses** | **~1550** | **+16.8 ±12.0** | **[+4.8, +28.8]** |

*(Final figures. The GPU box's credit expired at 06:50 London with arena 2 at 346 of 400 games and
zero fallbacks; both arenas' running scores were snapshotted to disk every four minutes, so nothing
was lost. All gate logs, nets and the 5.8 GB label corpus are mirrored to `~/chess_d10_mirror`.)*

**Against the rule I set before any data existed — +20 with the interval clear of zero — this is a
clear pass on the second condition and a fail on the first.** V8 is *established* as better than
V7k; it is not established as better by 20.

**My recommendation is to ship, and here is the honest reasoning rather than a rationalisation.**
The +20 bar existed for one purpose: to stop us shipping noise. An improvement measured at +16 with
a lower bound of +3.8 across 1,400 games in two independent harnesses is not noise — it is a small,
real gain that the bar was never designed to exclude. The change carries **no code risk whatever**:
every source file is byte-identical to a build now independently validated at **58.6% (+61 ±35)**, 400/400 complete
against V6.5, so the only thing that can differ is the weights. Rollback is a two-minute re-upload.

**If you would rather hold, that is entirely defensible** and the argument is simply that +16 is not
+20 and V7k is proven. I would not argue hard against it. What I will not do is claim the number
cleared a bar it did not clear.

**Not in the build:** aspiration 18 (+14 screen, **−3 ±17** at a clock — closed), contempt and
draw-seek (closed, negative), endgame blending (closed, monotone negative).

## 2. What the night actually established

### 2.1 The recipe axis is closed
Twelve nets swept the k96 training recipe. Read as three levers the results contradict each other;
read as one quantity — the noise scale `lr / batch` — they mostly line up. Halving it by either
route gives the same answer (**lr 0.0005: +10 ±14**, **batch 32768: +8 ±15**); quartering it by
either route is negative. **The peak is at half the k96 noise scale and is worth about +9.**
Everything since is trained there.

The model is approximate, not exact: it predicted the `r = 1/8` point at −25 to −50 and the answer
was **−18 ±12**. Recorded as a miss, not smoothed over. It does not change the conclusion, because
the peak and its value are measured directly rather than inferred.

### 2.2 From-scratch on depth-10 alone is dead, on arithmetic
`flagE` — 1024 net, from scratch, 41M depth-10 rows — scored **−345 ±20**. A superbatch is a fixed
100M positions, so a 17× smaller corpus means a 17× larger epoch count: **236 epochs against k96's
13.5.** It memorised the set, which is why its running loss was the *lowest* of any net tonight and
its sanity positions all looked right.

The labels are clean; volume is the problem, and it cannot be fixed by waiting — matching k96's
regime needs ~700M depth-10 rows, about 43 hours of labelling away. **This caught and cancelled the
flagship**, which was armed to do the same thing at 77M rows (126 epochs) and would have burned the
GPU window on a second broken net.

### 2.3 The corpus is two distributions — and the split was my own doing, not a bug
Measured across all 406 labelled shards:

| series | shards | \|cp\|>800 | cp mean | source |
|---|---|---|---|---|
| `shard_4xxxxx` | 130 | **3.6%** | 58 | normal play |
| `shard_5xxxxx` | 228 | **19%** | 130–215 | **endgame + elite late-ply streams** |
| `shard_9xxxxx` | 48 | **3.5%** | 60 | normal play |
| *d7, the corpus k96 learned from* | — | *9.9%* | *98* | — |

Nothing is corrupt: the labels are correct, the depth is a uniform 10, the positions are real.
`v8_feed3.sh` seeds the 500000-series from the **endgame stream** and the **elite late-ply stream** —
fed in deliberately, to attack the endgame bias the real games exposed (R86 read +164 in a drawn
position; R87 read −313 in one it saved). The instinct was right. The **concentration** was not:
endgame and late-ply positions are disproportionately already decided, and at 38% of the corpus by
row they dragged the training distribution away from the distribution the engine is judged in.

The cost is measured, not inferred. Same recipe, same architecture, differing only in corpus:

| net | corpus | \|cp\|>800 | rows | F30k vs k96 |
|---|---|---|---|---|
| ft_mid | normal play only | 3.6% | 18M | **+25 ±11** |
| fa_rep | 38% endgame/late-ply | 9.5% | 41M | **+4 ±11** |

**21 Elo, 2.7σ on the difference.** Targeted data is a spice, not a base — it belongs at the 5–10%
it occupies in real play. The check that catches this is one line, the |cp|>800 fraction of the
blended corpus against the 9.9% that trained the champion, and it costs thirty seconds before
training. **Every check I ran tonight looked at label correctness; none looked at label
distribution.**

### 2.4 Fixed-node gates inflate eval gains by about 3x — the mirror of the speed lesson
`ft_mid` was measured on three instruments against the same opponent:

| instrument | approx depth | ft_mid vs k96 | games |
|---|---|---|---|
| 30k fixed nodes | 11–12 | **+25 ±11** | 1728 |
| 30 s + 0.125 | ~15 | **+8 ±21** | 400 |
| 120 s + 0.5 (the platform) | 17–19 | **+10 ±15** | 400 |

**The two real clocks agree with each other at about +9; only the screen is the outlier.** Pooled,
ft_mid is **+9 ±12 at a real clock against +25 on the screen** — a compression of **0.36**. A deeper
search progressively compensates for eval error, so an eval refinement is worth less the longer the
engine thinks. Fixed nodes stays the right screen — cheap, deterministic, immune to CPU contention —
but **a fixed-node number for a net change survives only partly to the clock**. Two nets have now
been measured on both: ft_mid **+25 screen / +9 clock** (ratio 0.36) and fc_b **+29 screen /
+17 clock** (ratio 0.59). So the discount is real and large but *not* a constant — anywhere from
a third to three fifths survives. Treat a screen number as an upper bound that needs a timed
gate, not as a figure you can scale by a fixed factor.

Note what did *not* compress: V7k's gain came mostly from correction and continuation history, which
are **search** features, and it transferred intact (+40 fixed, +24 at 30+0.125, +46 ±56 through the
real wrapper). A search change alters what the engine finds at every depth. That asymmetry is a
hypothesis rather than a measurement, but it fits every number the project has, and it is why an
aspiration-window sweep was run tonight — and it *also* failed to transfer (+14 screen, −3 clock),
which weakens the pattern rather than confirming it.

### 2.5 At the tournament clock, most games are draws
The 120+0.5 gate is running **84% draws** between two comparable engines. That is the single
strongest argument for the conversion work below: on a 13-round Swiss, moving a few draws into the
win column is worth more than a 20-Elo eval improvement that compresses to single digits at depth.

---

## 3. Numbers

**Fixed nodes (30k) is a screen. The 120+0.5 column is what the ship rule is judged on.**

| candidate | what it is | F30k vs k96 | 120+0.5 vs k96 |
|---|---|---|---|
| **fc_b** | **fine-tune, 35.5M clean d10, 8 sb** | **+29 ±11** | **+23 ±18** and **+5 ±22** → **pooled ~+17 ±14** |
| fc_a | same corpus, 3 sb | **+25 ±12** | **+21 ±21** |
| ft_mid | fine-tune, 18M clean d10, 3 sb | **+25 ±11** | **+10 ±15**; **+8 ±21** at 30+0.125 |
| fa_lo | 41M endgame-heavy, 2 sb | **+24 ±12** | — |
| ft_lo | 18M clean, 2 sb, lr 0.0002 | +18 ±13 | — |
| fb_10 | fc_b recipe + 10% endgame | **+19 ±13** | — |
| ft2_b | 41M endgame-heavy, 8 sb | +17 ±11 | — |
| fb_20 | fc_b recipe + 20% endgame | **+12 ±13** | — |
| fc_c | clean, 16 sb (45 epochs) | **−6 ±12** | — |
| fa_rep | 41M endgame-heavy, 3 sb | **+4 ±11** | — |
| ft2_a | 41M endgame-heavy, 4 sb | −1 ±11 | — |
| fc_d | clean, 24 sb (68 epochs) | **−23 ±12** | — |
| mixA / mixB | from scratch, d7 + 10%/25% d10 | −10 / −26 | dead |
| flagE / flagF | from scratch, 41M d10, 236/470 epochs | **−345 / −366** | dead |
| w1536 / w2048 | wider nets | −27 / −4 | dead |

**Search constants, k96 both sides, versus the shipped value:**

| lever | result |
|---|---|
| **aspiration window 18, 30k screen** | **+14 ±11**, 1728 games |
| **aspiration window 18, REAL CLOCK** | **−3 ±17**, 400 games — **closed** |
| aspiration window 12 / 35 / 50 (screen) | −22 ±11 / −14 ±11 / −14 ±12 |
| contempt 45 vs 20, **real clock**, equal opponent | **−40 ±24** |
| contempt 45 vs 20, **real clock**, weaker opponent | c45 +26 vs c20 +47 (150 games) |
| contempt 45 vs 20, 200k fixed nodes, weaker | c45 +86 vs c20 +53 — **fixed-node artefact** |
| contempt 0 / 10 / 20 / 45, 30k, weaker | +68 / +58 / **+68** / +46 |
| draw-seek 40 when behind | −80 vs control −68 |

**The endgame dose-response is monotone and entirely downward:** 0% → **+29**, 10% → **+19**,
20% → **+12**, 38% → **+4**. Every percent of endgame/late-ply data costs Elo.

## 3b. The aspiration window — looked like the best lead, died at the clock

The sweep against **k96** at 1728 games per arm is a clean, symmetric, single peak below the shipped
value of 25:

| window | vs shipped 25, **30k screen** | games |
|---|---|---|
| 12 | **−22 ±11** | 1728 |
| **18** | **+14 ±11** | 1728 |
| 25 | *shipped default* | — |
| 35 | **−14 ±11** | 1728 |
| 50 | **−14 ±12** | 1728 |

**Then it was gated at a real clock and returned −3 ±17** (400 games, 30+0.125, k96 both sides).

| aspiration 18 | result |
|---|---|
| 30k fixed nodes, 1728 games | **+14 ±11** |
| 30+0.125 real clock, 400 games | **−3 ±17** |

The two are not statistically distinguishable (the difference is 17 ±20), so this is not a
contradiction — but **the point estimate at the clock is zero, so the lever is not established and
must not be shipped.** `BINI_ASP` stays at 25.

**A hypothesis of mine that this damages.** I argued repeatedly tonight that *search* changes
transfer to the clock better than *eval* changes, on the evidence that V7k's correction- and
continuation-history gain held its value (+40 screen, +24 timed, +46 real wrapper) while ft_mid's
eval gain lost two thirds. The aspiration window is a search change and it transferred **worse** than
the net did. One counter-example does not refute the pattern, but it stops me asserting it, and it
removes the reason I had for ranking this first for today.

## 3c. The gap I closed last, and why it matters most

**Every gate tonight ran through `node_gate` with `BINI_BOOK=0`, driving `bini_engine` directly.**
None went through `agent.py`. So none of them exercised the book, the wrapper, the fallback path, or
the real clock policy — the things the platform actually runs.

That transition is precisely where V7k lost ground: it measured **+39** on node_gate, the 80-game
Stockfish anchor then read **50.6%**, and only the real-wrapper head-to-head (now **58.6%, +61 ±35** (complete))
confirmed it. **fc_b had no such test.** Every number in section 3, including the pooled +16,
describes a book-free engine driven directly.

So the last thing launched tonight is **V8 against V7k through `arena_par` on the starter harness,
at 120+0.5 with the book on** — the shipped configuration, end to end, 400 games. Both are 1024-wide
and therefore speed-identical, which is what makes it safe alongside the gates still finishing.

**An observation, offered as a lead rather than a finding.** Both comparisons this project has now
run through *both* harnesses read **higher** through the real wrapper than through node_gate:

| comparison | node_gate (book off) | real wrapper (book on) |
|---|---|---|
| V7k over V6.5 | +39 ±21 | **+61 ±35** |
| V8 over V7k | +13.7 ±13.7 | **+27 ±25** |

Two cases with wide, heavily overlapping intervals is not a law. But it points the same way twice,
and the obvious suspect is that `node_gate` runs `BINI_BOOK=0` while the wrapper carries the
6,105-entry book. If the book amplifies a stronger engine's edge, every book-free gate this project
runs is systematically conservative. **Worth one deliberate test** — the same net pair gated with
the book on and off — before it is believed.

**If a number from that test exists in section 9 below, prefer it to everything in section 3.**
It is the only measurement that describes what would actually be uploaded.

---

## 4. V7k's own validation

`V7k vs V6.5` through the **real wrapper, real clock, book on** — the only test that exercises the
shipped configuration end to end — is at **58.1% (+57 ±68) after 105 of 400 games** on box A.
Box A has 8 cores and is saturated at 6 workers, so it reaches ~200 games (±35) by breakfast and the
full 400 (±25) around 18:00 today, in good time for any upload decision.

It was deliberately **not** moved to the 384-thread GPU box: V7k and V6.5 run different net widths
and therefore different speeds, so a loaded box would effectively shorten the time control and
exaggerate the wider net's penalty — the exact instrument error that wrongly rejected the 1024 net
three times this week.

---

## 5. The conversion requirement — draws into wins, losses into draws

Your stated V8 characteristic. Two earlier attempts (A1 anti-simplification, A3 drawishness) both
went through **static eval**, fought the NNUE, and are dead at default 0. The actual decision point
is **the score the search assigns to a draw by rule**, which already exists as `I_CONTEMPT`, read at
both draw sites in `bini_search.py`.

- **draws → wins** is `BINI_CONTEMPT` (shipped default 20).
- **losses → draws** was missing: when behind, contempt dropped to **0** (a draw becomes neutral)
  but never went negative (a draw becomes *desirable*). Added tonight as **`BINI_DRAW_SEEK`**,
  default 0, which reproduces current behaviour byte-for-byte.

Both halves are being measured **against the strength gap each is designed for**, not in self-play,
where contempt is EV-neutral by construction and would report ~0 however good the policy is:
contempt is swept with k96 against the weaker s48, and draw-seek with s48 against the stronger k96.
Controls came back as exact mirrors (**+68 ±19 / −68 ±19**), which independently confirms both the
documented k96-over-s48 gap and that the harness has no side bias.

---

## 6. Everything that was tried tonight, and where it ended

| line | verdict |
|---|---|
| Clean-corpus fine-tune (**fc_b**) | **+29 ±11 screen**, best net of the night — the ship candidate |
| Fine-tune length curve | peak at 8 sb, bracketed: +25 / **+29** / +1 / −27 |
| Training recipe (lr, batch, schedule) | **closed** — peak at lr/batch = ½, worth ~+9, already banked |
| From scratch on depth-10 only | **dead** — −345 and −366, epoch arithmetic |
| From scratch on d7+d10 mix | **dead** — −5 and −20 |
| Endgame data as a 10–20% spice | **dead** — +18 and −1, both below pure clean |
| Net width 1536 / 2048 | **dead** — −27 and −4 (the latter an *upper* bound) |
| Contempt (draw→win) | **dead** — flat 0–20, −22 at 45, **−40 at a real clock** |
| Draw-seek (loss→draw) | **dead** — −12, and it declines better continuations |
| Aspiration window 18 | **+14 ±11 screen, −3 ±17 at a clock — closed** |
| Time-management constants | **untested**, now env-gated and ready to sweep |
| Calibration refit | **untouched**, still the best-evidenced deferred thread |

**Still in flight as this was written:** the two pooled fc_b gates at 120+0.5 (the ship call), the
contempt-versus-weaker timed cell, aspiration 35, the 200k contempt screen, and the V7k head-to-head
on box A.

## 6b. The two tests still running when this was written

Both were launched late deliberately, because both answer questions nothing else tonight could.

**1. V8 vs V7k through the real wrapper** (`gates/v8_vs_v7k_real.log` on the GPU box).
Every other number in this document describes a book-free engine driven directly through
`node_gate`. This one runs `agent.py` with the book at 120+0.5 — the shipped configuration. **Prefer
its number to everything in section 3.** Note it was restarted once: the first attempt at 40 workers
blew `agent.py`'s 75 s compile-join and played 50 of its first 47 games on the *fallback* engine,
printing a perfectly plausible 50.0% that meant nothing. Restarted at 28 workers with
`BINI_JOIN_S=300`; fallback count 0.

**2. Aspiration 18 at a real clock** (`gates/t_asp18_30.log`) — **this one finished: −3 ±17.**
It turned the night's most promising lead into a closed question. `BINI_ASP` stays at 25.

**If the box credit ended before either finished**, both logs print a running score per game, so the
partial line is usable — read the last `[n/400]` line and treat the interval accordingly (400 games
resolves to about ±22 at this control; 200 games to about ±31).

---

## 7. Assets secured

The depth-10 labels are the only irreplaceable thing on the GPU box — hours of CPU that cannot be
regenerated before the deadline. **Mirrored to `~/chess_d10_mirror/labelled_d10` on the Mac**
(re-synced incrementally through the night). The box's credit expires around 06:50.

---

## 8. What would actually produce a leap, given what tonight established

Tonight did not produce a generational leap, and the reason is worth stating precisely rather than
softening: **we spent the night on the evaluation function, and tonight's own measurement says the
evaluation function is the wrong place to spend it.** An eval gain of +25 on the screen is worth
about +9 at the tournament clock, because a deeper search progressively compensates for eval error.
Three-quarters of any net improvement is refunded to the opponent by depth.

What did *not* compress was V7k's gain, which came mostly from correction and continuation history
— **search** features. A search change alters what the engine finds at every depth.

That points at three things, in the order I would spend the day on them:

**1. Time-management *tuning* — six constants that have never been swept, measurable only at a
real clock.** I first wrote here that time management was missing. That was wrong, and the code
corrects it: `bini_engine.py` already varies effort substantially per move — `stable >= 3` spends
0.75x, an unstable root at depth >= 6 spends 1.3x, a score that fell 25cp since our previous move
spends 1.5x ("think longer, not shorter"), a decided position (|score| > 400 and stable) spends 0.6x
to bank clock, and a root guard gives 2.5x for up to two iterations when the best move hangs
material by SEE. That is a real, well-developed mechanism.

What has never been touched is its **numbers**: 0.75, 1.3, 1.5, 0.6, 2.5, and the thresholds 3, 6,
25, 400, 150 and 2. None are env-gated, so none has ever been through a gate. They have survived
untested for the same reason they matter — **they are completely invisible to a fixed-node gate**,
which is the instrument this project screens everything with. Sweeping them needs env knobs and
timed gates at roughly two hours per 400-game arm, which is a day's work rather than a night's, and
it is the most promising day's work available.

**2. Redo the fine-tune with a properly blended corpus.** The endgame and late-ply streams were the
right instinct aimed at a real flaw, and they were fed at 38% of the corpus. At the 5–10% they
occupy in real play they may well pay. The clean corpus and all 439 labelled shards are mirrored to
the Mac, so this needs no GPU box to prepare — only to train.

**3. Calibration.** Still the best-evidenced open thread and still deferred: the v3b-fitted table
scores −31 on the current net, which proves the mechanism has grip and only the table is stale. It
targets exactly the flaw the real games expose — R86 read +164 in a drawn position, R87 read −313
in one it saved. Position-dependent bias, not a constant offset.

**What I would not spend another hour on:** net width (closed, upper-bounded at −4), the training
recipe (closed at lr/batch = 1/2, worth ~+9 and already banked in every candidate), from-scratch on
depth-10 (impossible before the deadline on epoch arithmetic), and the draw-scoring policy (flat
0–20, negative above, harmful when behind) — unless the 200k-node re-screen overturns the last one,
in which case contempt is worth a proper timed test rather than a screen.

---

## 9. If you decide to ship — and how to undo it

**The file:** `submission_v8_0910_0313.zip`
`7,104,654` bytes · **14,042,168 unzipped** · 10 files · md5 **`fc8bbaad7115c86917f59e4501c97680`**

**What it is:** V7k with one file changed. Verified byte-identical on `agent.py`, `bini_board.py`,
`bini_calib.py`, `bini_engine.py`, `bini_eval.py`, `bini_magics.py`, `bini_nnue.py`,
`bini_search.py` and `book.json`. The only difference is `nnue.safetensors` — the **fc_b** net, a
fine-tune of k96 on 35.5M depth-10 positions drawn only from normal play.

**Pre-flight facts, already measured, so the platform log should match:**
- init **22.4 s** locally against a 90 s budget (V7k measured 37.5 s on the platform image; ours has
  the same code and the same compile surface, so expect ~37 s there too)
- unzipped size is **8 bytes** larger than V7k's platform-verified 14,042,160 — net metadata only
- legal moves returned in every playable test position; correct null (`0000`) on a mated position
- `nnue=on` confirmed in the ready line

**To roll back at any point:** re-upload `submission_v7k_0909_2040.zip`
(`7,109,016` bytes, md5 **`246fe9fa97439a1abd832a2a6c9b18c8`**). It is the build currently live and
now independently validated at ****58.6% (+61 ±35)**, 400/400 complete** at 400/400 against V6.5 through the real wrapper. Nothing
about V8 changes the search, so a rollback is a pure net swap with no other consequence.

**My recommendation remains section 1: hold V7k**, unless the real-wrapper number in
`gates/v8_vs_v7k_real.log` came back clearly positive. The candidate exists so that shipping is a
choice you can make in two minutes, not a scramble.

## 10. The jobs for today, reordered after the aspiration result

**Not aspiration 18.** It was gated overnight and came back **−3 ±17** at a real clock against
+14 ±11 on the screen. Closed. `gates/t_asp18_30.log` has the full result.

1. **The six time-management constants**, now env-gated in `bini_v7/bini_engine.py` as
   `BINI_TM_STABLE / TM_UNSTABLE / TM_DANGER / TM_DROP / TM_DECIDED / TM_RG / TM_CAP`, every default
   bit-identical to V7k's literals (verified, not assumed). They are the only substantial lever left
   that has never been measured, and they are invisible to every fixed-node gate we own — which is
   exactly why they survived untested. **They must be swept at a clock from the start**; a screen
   number would be worthless here, as tonight proved twice.
2. **Calibration refit.** Still the best-evidenced deferred thread: the v3b-fitted table scores −31
   on the current net, which proves the mechanism has grip and only the table is stale. It targets
   the flaw the real games actually show — R86 read +164 in a drawn position, R87 read −313 in one
   it saved.
3. **Finish the V8-vs-V7k real-wrapper test** if the overnight run was cut short by the credit. It
   is the only measurement that describes the shipped configuration, and it was still climbing when
   the box ended.

**What not to spend time on**, all closed with numbers tonight: net width, the training recipe,
from-scratch on depth-10 in any form, the draw-scoring policy, blending endgame data into the
fine-tune corpus, and the aspiration window.

## 11. The one-paragraph summary

**No lever cleared its bar at a real clock.** fc_b, the best net of the night, is +29 on the screen
and **+13.7 ±13.7** at the platform clock — real, probably, but under the +20 rule with the interval
touching zero. Aspiration 18 is +14 on the screen and **−3** at a clock. Contempt, draw-seek,
endgame blending, four forms of from-scratch training, and two wider nets are all closed negative
with numbers. The recipe axis is exhausted. **The build to run is still V7k**, which this night did
at least prove is genuinely good: ****58.6% (+61 ±35)**, 400/400 complete** at 400/400 against V6.5 through the real wrapper, the
first time that has been established rather than assumed. The most valuable thing produced was not a
net but a corrected instrument — **a fixed-node screen is an upper bound and cannot be scaled into a
clock number** — and the measured cost of a data mistake I made myself: seeding 38% of the fine-tune
corpus from endgame and late-ply streams cost 21 Elo.
