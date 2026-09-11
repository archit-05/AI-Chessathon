# V6 handover (Wednesday 9 September 2026, 13:05 London, final) — from the Fable session to Opus

Deadline: V6.0 handed to Archit for upload by 19:30 today; V6.1 Thursday by 15:00 only at ≥ +30
over what is live. Plan of record and full log: `Project Prometheus.md` (section 13). Rules that
are not negotiable: games decide (576 fixed-node, then 576 at 5 s, 200 at 10 s, 40 proxies);
one evaluator per training set; no result blend; nothing ships without the battery on the exact
zip; kill patterns live in script files, never inline in an ssh command.

## 1. Where we are (numbers, all vs v3b = the shipped net, 576 games unless stated)

| Net | Trainer / data | 30k nodes | 5 s + 0.05 | 10 s | Proxies |
|---|---|---|---|---|---|
| P1 | our trainer, 96M own labels, 512 CReLU | **+55 ±23** | **+58 ±24** (58.3%) | +101 ±46 at 120/200 (running, box B) | running on the VM (`gates/v6p1_proxy_{0,20}.log`; reference 46%) |
| R1 | bullet, same labels, 512 CReLU, 8 output buckets | **+72 ±23** (60.2%) | running on box A (`gates/r1_tc5.log`) | – | – |
| P2 | our trainer, 1024 SCReLU | +43 | **−17 ±27**: too slow at the real clock; 1024 waits for the speed pass | – | – |
| r1b / r1e | bullet 12 superbatches; bullet 1024 | judging on the GPU box (`logs/r1.log`) | – | – | – |
| C0 / P3 / P2b | Lichess mix; result blends | −152 / −149 / −162: closed for good | | | |

Instrument calibrated (v3b > v3 +24 > v2 +55; determinism exact). Labelling: ~120M own rows
(603 shards) at ~30k positions/s, ~1,400 shards (280M) queued; all depth 7, Stockfish 19.

**V6.0 candidate today = the V5 engine + the best net that clears the whole ladder + the 2,018-entry
book.** `bini_v6a` (P1) is assembled and its battery is running on the Mac (init 22 s, wrapper,
exactness, perft, mates 80/80, puzzles 40/40, blunders 12/12 green so far;
`$SCRATCH/battery_v6a.log`). If R1 clears 5 s at ≥ P1's margin, R1 replaces P1 (assemble a new
dir, rerun the battery); P1's zip is the fallback either way.

## 2. Machines and the running jobs

| Machine | What runs | Files |
|---|---|---|
| GPU box `ssh gpu` (2× 5090, 92-CPU quota; **credit ends ~19:20 today** unless topped up) | labelling fleet (`./keeper_ctl.sh status|stop|start 64 7`), day chain (`daychain.sh`: 12:15 and 14:15 London, our trainer, 16 buckets + factoriser), bullet variants (`r1_variants.sh`) | `~/chess/logs/{daychain,r1,label_keeper}.log`; `grep RESULT ~/chess/logs/*.log`; nets in `~/chess/data/nnue_*.safetensors`; gates in `~/chess/gates/` |
| box B `gcp-x86b` | P1 10 s gate then generators resume (`ladder_b.sh`) | `~/chess/gates/p1_tc10.log`, `ladder_b.log` |
| box A `gcp-x86` | R1 5 s gate (generators paused: `bini_v5/tools/pause_gen.sh resume` when done); `./stop_gate.sh` stops a match | `~/chess/gates/r1_tc5.log` |
| VM `priorcrypto-vm` | P1 proxies, 2 × 20 games (generators paused) | `~/chess/gates/v6p1_proxy_0.log`, `_20.log`; final line "PROXY MATCH" |
| Mac | battery on `bini_v6a`; assembly and packaging | `bini_v5/tools/assemble_v5.sh`, `battery.sh`, `package.sh` |

Fixed-node verdict on the GPU box (6 min): `cd ~/chess/bini_v5 && ~/chess/venv/bin/python
tools/node_gate.py --engine . --a BINI_NNUE=<net> --b BINI_NNUE=~/chess/data/nnue_v3b.safetensors
--openings tools/curated.epd --games 576 --nodes 30000 --workers 24 --tt-bits 22 --out ~/chess/gates/<name>`.
Timed: `--tc 5+0.05 --workers 4 --tt-bits 24` on a GCP box with generators paused.
bullet run (a minute): see `r1_variants.sh` (`--wdl 0.0` always); export with
`bullet_export.py --checkpoint <ckpt> --hidden H --act A --out <net>`; own labels must be converted
and shuffled first (`r1_prep.sh`; rerun it when the label count has grown).

## 2b. Chains armed at 12:00 (everything below runs by itself; read, do not restart)

| Where | Script | What it does | Log |
|---|---|---|---|
| GPU box | `afternoon.sh` | scale-matches R1 to v3b's output scale (slope of static evals on 3,000 positions) → exports `nnue_r1s` → judges r1s vs r1; then bullet sweep r1c (lr 0.002), r1d (24 superbatches); then at 13:00, 15:00, 17:00 UTC re-shuffles all labels and trains 512 CReLU 12 sb, judged vs v3b and vs r1 | `logs/afternoon.log` |
| GPU box | `r1_variants.sh` | r1b (12 sb) and r1e (1024 SCReLU) verdicts | `logs/r1.log` |
| GPU box | `daychain.sh` | our trainer, 16 buckets + factoriser, 512 and 1024, at 11:15 and 13:15 UTC | `logs/daychain.log` |
| GPU box | `thursday.sh` | 17:30 UTC: r1_final (512, 24 sb) and r1e_final (1024, 24 sb) on every label, judged | `logs/thursday.log` |
| GPU box | fleet + `produce_gates` | labelling to ~300M; today's ~5,000 arena games (gates/*.pgn) queued as shards 4000+ (the data loop's first cycle) | `logs/label_keeper.log` |
| box A | `gate_r1_a.sh` → `ladder_a.sh` | R1 5 s (576) then R1 10 s (200), then generators resume | `gates/r1_tc5.log`, `r1_tc10.log`, `ladder_a.log` |
| box B | `ladder_b.sh` | P1 10 s (200), then generators resume | `gates/p1_tc10.log`, `ladder_b.log` |
| VM | `vm_chain.sh` | P1 proxies → R1 proxies (candidate `bini_v6r`) → generators resume | `gates/vm_chain.log` |
| Mac | battery on `bini_v6a` (P1) | green through torture; pressure games running | `$SCRATCH/battery_v6a.log` |
| Mac | `mirror_gpu.sh` at 18:35 London | pulls nets, gates, logs, ckpt, bullet_shuf to `data/gpu_mirror/` (add `also-labels` for the 40 GB label set) | `$SCRATCH/mirror.log` |

Candidate dirs on the Mac: `bini_v6a` (P1, battery running), `bini_v6r` (R1, needs its battery once
R1's ladder is green). If r1s (scale-matched) beats r1 at fixed nodes, re-export the final net with
that `--out-scale` and assemble again; the battery must run on the exact zip that ships.

## 0. The directive (Archit, 13:00)

**V6.0 tonight is the highest-stakes build: the generational leap, at all costs, without lowering the
bar.** The GPU box will be **paused for a couple of hours after the V6 build** and then come back.
Consequences, in order: (1) every net that could ship tonight must be exported before the pause; (2)
the timed ladder, proxies and battery do not need the GPU box (GCP boxes, VM, Mac), so they continue
through the pause; (3) before pausing run `bash bini_v5/tools/mirror_gpu.sh also-labels` from the Mac
(the labels are the asset; a stop/start keeps the container filesystem, a destroy wipes it); (4) after
the restart run `~/chess/resume.sh` (restarts the labelling keeper and prints state), then relaunch
whichever chain is needed. Nothing in section 4's Thursday plan changes except that its overnight
labelling and SPSA start when the box is back.

**Tonight's shape.** V6.0 at ~17:00 with the best net that has cleared the whole ladder by then (R1 at
+72/+46-so-far, or the 14:00/16:00 retrains if they beat it). V6.0b at ~21:00 only if the 18:00
London retrain (400M+ rows, endgames 2×) beats the V6.0 net at 30k nodes and clears 5 s, 10 s and
proxies on the CPU boxes by 20:30, plus the battery. Both zips kept; the live one is the rollback.

## 2c. Verdicts landed at 12:10 (576 games at 30k nodes vs v3b) and one broken step

- r1 (bullet 512 CReLU, 6 superbatches) **+72 ±23**; r1b (12 superbatches) +38; r1e (1024 SCReLU, 12
  superbatches) +9. More superbatches did not help and the 1024 net is *worse* at this volume, so the
  Thursday lever is volume and the loop, not width; r1e_final is exploratory only.
- **r1s is invalid: ignore its −458.** `afternoon.sh` step 1 computed an empty slope (the static-eval
  snippet failed silently) and exported with `--out-scale ""`. Redo by hand: compute the slope of v3b's
  static eval against r1's on ~3,000 positions (both nets through `Engine.static_eval`, or `net_diag.py`
  on the site chunk), export `bullet_export.py --checkpoint data/ckpt/r1-6 --hidden 512 --act crelu
  --out-scale <slope>`, judge vs r1. If the slope is within 0.9–1.1 nothing is needed.
- r1c (lr 0.002) +8, r1d (24 superbatches) +53, r1s2 (scale 0.982) vs r1 +5: **lr 0.001 and 6
  superbatches per 100M rows stays the recipe; the scale is confirmed a non-issue.** The 13:00/15:00/
  17:00 UTC retrains (12 superbatches on the growing set, endgame shards 2× from now on via
  `r1_prep.sh`) are the tonight candidates; judge each vs r1, not only vs v3b.
- Labelling: 1,698 shards (~340M rows) at 13:00; the Lichess queue is nearly consumed (417 left); the
  endgame streams (7000+, 9000+) are being produced and labelled next.
- The arena games (14 PGNs, 863k positions) are in the labelling queue as shards 4000–4013.

## 3. The afternoon, in order

1. **12:00** Read P1's 10 s and proxies, R1's 5 s. Whichever of P1/R1 has the better full ladder is
   the V6.0 net. If R1: `bash tools/assemble_v5.sh bini_v6r ../data/nnue_v6_r1.safetensors
   ../data/book.json 0 1 0` from `bini_v5/`, then R1's 10 s (box B) and proxies (VM or box A),
   then `battery.sh ../bini_v6r` on a quiet Mac.
2. **12:15 / 14:15** Day-chain runs A and B land (`daychain.log`). Rerun `r1_prep.sh` at ~13:00
   and ~15:00 and train bullet 512 CReLU on the larger set (12 superbatches); judge vs the
   current best at 30k nodes. Anything ≥ +30 over the current best goes through 5 s → 10 s →
   proxies. **Last net that can still make tonight starts its 5 s gate by 15:30.**
3. **16:30–18:30** Battery on the final zip, `package.sh`, unzip byte-check, one fresh-extraction
   game. Rollback zip = the current live upload.
4. **19:30 hand-over to Archit** with: net name and its four numbers, compile time, zip name,
   md5, what changed vs the live build.
5. **Before 19:20**: rsync `~/chess/data/labelled`, `~/chess/data/nnue_*.safetensors` and
   `~/chess/gates` off the GPU box to box B (`~/chess/mirror/`) unless the credit is topped up.

## 3b. Tonight's marginal gains, in order (no engine code)

1. **Scale-match: done, not needed.** Slope of v3b's static eval vs R1's on 3,000 positions = 0.982
   (`logs/scale.log`; `scale_match.sh`, `tools/static_dump.py`). R1 is on v3b's scale; the r1s2 vs r1
   verdict in `logs/scale.log` is only the confirmation. Repeat the slope for any *other* net that ships
   (the recipe):
   static evals of v3b and the candidate on ~3,000 labelled positions (`Engine.static_eval` after
   `set_position(fen, [])`, one process per net with `BINI_NNUE` set), slope by least squares on
   |eval| < 800, `bullet_export.py --checkpoint <ckpt> --hidden 512 --act crelu --out-scale <slope>`,
   600 games vs the unscaled net, then the 5 s gate. This also puts the draw trigger (−100) and the
   contempt (20) back on the scale they were tuned on.
2. **The afternoon retrains** (14:00, 16:00, 18:00 London in `afternoon.log`): whichever beats r1
   at 30k nodes and can start its 5 s gate by 15:30 competes for the slot; 10 s and proxies stay
   mandatory.
3. **Bigger book: done.** `data/book_v6.json` = union of `book.json` (2,018) and the graded deep pass
   `book_pass1.json` (4,926, all ≤ 15 cp, deeper entry wins on overlap): **6,105 entries, none over
   15 cp**. `bini_v6r` (R1) is re-assembled with it; `bini_v6a` (P1, battery running) still carries the
   2,018-entry book. Whatever ships gets `book_v6.json` and its own battery.
4. Optional, only if a GCP box is idle: the midgame time boost (`BINI_MIDGAME_BOOST=1.25`; add the
   env read to `node_gate.py`'s copy of `_budget` first), one 5 s gate.
Do not touch tonight: the speed pass, SPSA, correction history, the 1024 net.

## 3c. What the top of the ladder taught us (12:50) and the coding tasks it creates for Opus, today

The leader drew the number two over 155 moves at 3 cp per move each; the top eight are within 50
points and draw 40–50% of their games against each other while never losing to the field below
2500. So: quality is ACPL, the endgame is where they separate, draws against peers are the plan,
and a fresh strong build climbs to its level within ~15 rounds. Done already: an **endgame stream**
(≤ 16 pieces) from the whole Lichess evaluation database (shards 7000+) and from the elite games
after ply 30 (shards 9000+) is in the labelling queue; `r1_prep.sh` should include shards
7000–9999 **twice** in the shuffle (same evaluator, deliberate 2× weight on endgames). The three
coding tasks below go into V6.0b tonight if they clear their gates, else V6.1; each is gated
alone; none touches the net.

**Task A — 4-man tablebase at the root (`bini_tb.py`, wrapper only, no jitted code).**
Download the Syzygy 3-4-men WDL files (about 30 MB; `chess.syzygy` is in the platform image;
tablebases are permitted as shipped data) into `bini_v5/tb/`; check the zip stays under 50 MB
unzipped with the net and book. In `agent.py`, when the position has ≤ 4 pieces (and ≤ 5 if the
5-man WDL fits, it does not): open the tablebase once at import, and at the root probe
`probe_wdl` after every legal move (python-chess; ~1 ms per probe, only in these positions); keep
the moves in the best WDL class (win > cursed win > draw > blessed loss > loss from our view), and
prefer among winning moves the ones that capture or push a pawn (zeroing the 50-move clock), then
hand only that move set to the engine by playing the search as usual and overriding its choice
if it is outside the set. Log `tb` in the move line. Tests: (1) `tests/test_tb.py`: KQK, KRK,
KBNK-free set of 40 EPDs with known WDL, the chosen move never leaves the best class; (2) 20
games each from KPK won/drawn and KRvKP positions vs Stockfish at 20k nodes (`node_gate.py`
`--openings` with an endgame EPD, `--tc 5+0.05`): wins converted 100%, draws held 100%; (3) the
full battery, compile time unchanged (the probe is Python). Ship only through a 5 s gate on the
curated openings that is not negative (it will be level: the effect is in the endings).

**Task B — endgame-holding gate slice.** Build `tools/endgames.epd`: 150 positions with ≤ 12
pieces and |site eval| < 50 from the arena PGNs on the boxes (`gates/*.pgn`) and from the site's
games; add it as a second opening file to every timed gate (`node_gate.py --openings`), reported
separately in the gate log (score, draws held). A V6 candidate must not be worse than the live
net on this slice.

**Task C — data: endgame weight and the loop.** In `r1_prep.sh`, include `data/labelled/shard_007*`
and `shard_009*` twice in the concatenation before the shuffle; rerun the prep and the 512 CReLU
bullet run (6 superbatches per 100M rows), judge vs r1 at 30k nodes and on the endgame slice.

Draw discipline stays as built: contempt 20, a repetition scores 0 once we are ≤ −100 after our
20th move (`BINI_DRAW_BEHIND=1`), never repeat while better. No change without its own gate.

## 4. V6.1 — the final training run, done so it is a real top-five candidate

**The bar.** V6.0 tonight is about 2450–2500 on the ladder. Top five is 2610+; the leader is 2811.
V6.1 is "top-five material" only if it measures, against v3b: **≥ +150 at 30k nodes, ≥ +120 at
5 s, ≥ +100 at 10 s, proxies ≥ 55%** (reference 46%; the proxy opponent is Stockfish held to
AlphaFish's level). Anything below that still ships if it is ≥ +30 over V6.0, but do not call it
top five. First place also needs the knockout draw; the Swiss on Friday plays the locked build.

**What the evidence says the run needs (each item measured today).** Volume is the lever
(46M → −21, 96M → +55/+72; nothing else moved a net that much). One evaluator only. Six
superbatches per 100M beat twelve at 100M; the 1024 net was worse at 100M; the result blend is
dead. So the final run is bullet, 512 CReLU, 8 output buckets, on **≥ 600M own depth-7 labels**,
with the epoch count swept rather than assumed, and 1024 only if the speed pass lands.

**Timeline (London), GPU box needed throughout.**

| When | GPU box | GCP boxes + VM | Mac / Opus |
|---|---|---|---|
| Wed 19:30–Thu 06:00 | fleet labels the whole Lichess evaluation database and the elite odd plies (→ ~500M); **data-loop cycle 1**: 10,000 fixed-node games V6.0-net vs R1 from the 288 roots + top-ten openings (`node_gate.py`, 24 workers, ~1.5 h) → `fen_producer.py --pgn` → fleet (→ +8M in-distribution rows); **SPSA** of the search constants at fixed nodes on the R1 net (`tools/spsa.py` adapted to `node_gate.py`; 8 constants; 120 games per pair; ~100 iterations, ~3 h) | generators paused; nothing else | **speed pass** (int16 accumulators, one `in_check` per node): exact `test_nnue.py`, identical node counts at fixed depth on 200 positions; correction history at 600 games (`BINI_CORR=1`) |
| Thu 06:00–06:45 | `r1_prep.sh` on everything (≥ 600M rows, shuffled); **four final runs** (a minute each): 512 CReLU at 3 and 6 epochs (18 / 36 superbatches), 512 with 16 king buckets (edit `KING_BUCKETS` in `bullet_trainer/src/main.rs` to `_king_table(16)`'s map, export `--king-buckets 16`), 1024 SCReLU only if the speed pass is in | – | – |
| Thu 06:45–07:30 | verdicts: each vs r1 and vs v3b, 600 games at 30k nodes; keep the best two | – | – |
| Thu 07:30–11:00 | data-loop cycle 2 with the best net (optional, only for a Friday V6.2) | **timed ladder of the best two in parallel**: 5 s 576 (box A / box B), then 10 s 200, proxies 40 split VM + a box | assemble the winner (`assemble_v5.sh <dir> <net> ../data/book.json 0 1 0`, plus the SPSA constants and the speed pass if they cleared their own 5 s gates) |
| Thu 11:00–13:00 | – | – | battery on the exact zip, `package.sh`, byte-check, fresh-extraction game |
| **Thu 13:30** | – | – | **V6.1 upload** (rollback = V6.0) |
| Thu 14:00–Fri 09:00 | cycle 2 net through the ladder overnight | – | Friday 09:00 V6.2 upload only at ≥ +30 over V6.1 (uploads close 11:00) |

**Rules that make it "done right".** One change per gate. The SPSA constants, the speed pass and
the net are each gated alone at 5 s before they are combined; the combination gets the full ladder.
No run on fewer than 600 games is a result. Nothing from a Lichess or site label enters the set.
The battery runs on the exact bytes that ship.

**Compute.** The GPU box is the fleet, the arena and the trainer; it must not stop. From Wed 19:20:
**24 hours covers V6.1 (to Thu ~13:00) and 40 hours covers a Friday V6.2 as well**; at $1.23/h
that is $30 and $50. Top up $60 today and the question never comes back. If the box is lost,
`mirror_gpu.sh also-labels` first (the labels are the asset; everything else is a script).

## 5. Traps that cost time today

Stockfish 19 exits with code 1 on analysis-board fantasy positions in the Lichess evaluation
database (material filter + in-worker restart now in `peer_label.py`). A `pgrep -f`/`pkill -f`
pattern typed inline kills the shell carrying it. Box A's `bini_v5` was stale (`bini_eval.py`
without `calibrate`): rsync all `bini_*.py` before a gate. The VM has Stockfish at
`~/chess/Stockfish/src/stockfish`, not on PATH. bullet must be built with `--features cuda` and
`CUDA_PATH=/usr/local/cuda`, else it is a mock backend. `train_nnue.py` on the box carries
`--rows-per-chunk 200000` and reads `shard_*.npz`; the Mac copy does not.
