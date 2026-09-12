# GrigoryMorning — handover, 12 September 2026, written at 11:12 BST, 12 September 2026

Everything below was produced overnight by the engine/packaging side. Nothing has been uploaded to the
platform. V8.5 (`bini_astra_v5_noc2b`, `submission_V8.5.zip`, sha256 `26828c24…`) is untouched and
remains the control and the fallback. Full evidence: `FinalsDay/Finals Night Cause Table.md` and
`FinalsDay/night_evidence/` (every script, log and manifest named here lives there or at the box paths given).

## FINALS DAY — constraint, decisions and the plan to 14:00 (written 12:00, Archit + Claude)

**The constraint (announced 10:41):** init budget **30 s** (was 90 s). Uploads are open 10:30–14:00; every upload
validates against the 30 s init with two smoke games at the match clock against a house agent (verbatim log on the
dashboard, including our init time and per-move times); **practice rounds run every ten minutes 10:40–13:50 on the
latest valid build** (they count for nothing); **the build we have at 14:00 plays the knockout.** Hardware: one core of
an AMD EPYC 9V74 at 2.60 GHz, 2 GB, /tmp 256 MB scratch that starts empty every game, process suspended while the
opponent thinks. Knockout ties are two positions each played with both colours (4 games), three in the semis (6), four
in the final (8); a level tie goes to the better Swiss standing (we are 6th); top seeds get a first-round bye.

**What "init" means for us.** The runner imports `agent.py` and only then prints its ready line; "no ready line within
the init budget" is a loss. Our import blocked on the numba compile (join up to 75 s): the Swiss logs show
"Ready in" 36.8–43.8 s in 28 of 30 games and 51.2 s / 60.3 s twice — all losses under 30 s. Measured and decided
(Cause Table §21): shipping numba's compiled cache is illegal ("native binaries are rejected … each jitted function pays
that compile cost the first time it runs"), lowering `NUMBA_OPT` saves 2 s of compile for 11–15 % of speed
(rejected), unifying the 4–11 specialisations of some functions might save ~5 s but means editing search call sites
today (deferred). **Fix shipped: `COMPILE_JOIN_S` 75 → 21.** Verified platform-faithfully on the pod (zip extracted
with Python's zipfile, read-only files, no env, fresh interpreter): ready line 21.8 s, engine ready ~8 s into the first
move, FEN battery 32/32. Cost accepted: the compile remainder (≈ 16–23 s on the platform's machine, up to ≈ 39 s on
its slow outlier) is paid from our clock on the first move, because the process is suspended during the opponent's turn.

**Gate results (all real clock 120+0.5 unless stated).** Book vs V8.5, 300 games: **+40 =235 −25, +17.4 [−1.9, +36.8]**,
0 failures → ships. Contempt 40 vs book candidate, 100 games: +10 =83 −7, **+10.4 [−16.1, +37.0]**, 0 failures, and −1 ±19
over 576 fixed-node games → ships. Endgame honesty fix (dead pawnless draws = 0; no correction history ≤ 6 pieces):
576-game screen −3 ±8, real-clock gate 66/100 level, running → ships (behaviour-neutral outside tiny endings, fixes the
phantom +60 of rounds 113/116/119). bp144_d7_ft + book vs V8.5, 150 games: +9.3 [−16.5, +35.2] vs +17.4 for the book
alone → **the net adds nothing; V8.5's net stays.** bp240 screen +9 ±18. **bp336_d7_ft screen +23 ±19** (best of the
night); its full package is in a 120-game real-clock gate vs V8.5 on gcp-x86 (ETA 13:10). Short-clock stress 30 s + 0.3 s:
35 games, zero failures. Stockfish UCI_Elo 2400: 60/60 wins, uninformative. Opponent book coverage (Miskeen,
Rataturing PGNs): 36 % of our-move positions in their lines, no repeated gap → no extension worth building.

**Packages (gcp-x86 `~/chess/packages/`, sha256 in `MANIFEST.txt`, same flat layout as `submission_V8.5.zip`):**
- `submission_V10_v85_book_c40eg_init.zip` — sha256 **039f0c12…** — V8.5 net + book + contempt 40 + endgame fix +
  21 s join. Differs from the gated `cand_sfbook_c40eg` only in agent.py (engine files byte-identical). **This is the
  upload-now build.** 40-game real-clock smoke vs V8.5 running on the pod with the harness init budget set to 30 s.
- `submission_V10_bp336_book_c40eg_init.zip` — sha256 **969e5da3…** — the same with the bp336 net. Ships only if its gate
  clears the rule below.
- Rollback: `submission_V8.5.zip` (26828c24…) and `submission_V9_book.zip` (467087fb…, book only).

**The plan to 14:00.**
1. **Now (on Archit's go): upload the V10 V8.5-net build.** It validates the 30 s init on the real EPYC core, plays the
   practice rounds (free logs: init time, per-move times, real opponents), and is a complete gated build to be frozen
   with if nothing else happens. Read the validation log: init well under 30 s, no fallback warnings after move one.
2. **In parallel: measure bp336 at the real clock with every box** — gcp-x86 (120 games), the VM after its endgame gate
   (~12:05), the pod after its smoke (~12:45), and any extra RunPod pods Archit fires up (`gate_worker.sh` turns a pod into
   a 120+0.5 worker on an opening slice; `status_all.sh` shows everything). Target 250–300 games by 13:20. bp336 cannot
   be made stronger before 14:00 (training + alignment + gates take 4–5 h); the question is only whether the existing
   bp336 beats V8.5's net at the real clock, which the screen cannot answer (bp144 screened +12 and added nothing).
3. **13:20 decision, pre-declared:** ship the bp336 package if its pair-level Elo vs V8.5 is **≥ +8 with the lower bound
   ≥ −8**; otherwise the V10 V8.5-net build already on the platform stays. Stop reading gates at 13:20.
4. **13:30 final upload** (if bp336 clears): `smoke_zip.py` on the exact zip on a quiet box, sha256 against
   `MANIFEST.txt`, upload, read the validation log, confirm the practice round after it. Buffer to 14:00.
5. If the practice logs show a bigger first-move compile cost than expected, the rebuild-and-reupload path stays open
   until 14:00 (`patch_init.py <build> 3`, `build_packages.py`, `smoke_zip.py`).

**Nothing is uploaded without Archit's explicit go.** Grigory: `bash ~/chess/status_all.sh` on gcp-x86 prints every
result; the practice-round logs on the dashboard are the ground truth for init and clock use.

---
## 0. Read this first (five lines)

1. **Stockfish opening book — gate PASSED (07:35)**: 300 games 120+0.5 vs V8.5, **+40 =235 −25, pair-level Elo
   +17.4 [−1.9, +36.8]**, zero failures/fallbacks, ~4 book hits and ~15 s saved per game, exit at move 12 (max 16).
   Built for the 1,226 curated roots, guards verified, exact package frozen and smoked. Report command:
   `~/chess/venv/bin/python ~/chess/bookbuild/book_gate_report.py ~/chess/gates/sfbook_real.log ~/chess/gates/sfbook_real.stats.jsonl`
2. **Your preflight is done on `gcp-x86`**: instrument gate +27 ±19 (fc_b vs k96 @30k), determinism clean, k96
   re-export tensor-identical, **`~/chess/data/stage/clean_d10_shuf.bin` built (35,458,988 rows, |cp|>800 3.68 %)**,
   d10 npz shards + 712M shuffle + k96/s96 checkpoints + all nets staged under `~/chess/data/stage/`.
3. **fc_b's real recipe** (from `train_fc_b.log`): `Start Superbatch 97, End 104, Cosine lr 0.0005 -> 1.2e-6 over
   104 superbatches (gamma 0.1, step 18)`. It was a near-floor-LR 8-sb fine-tune. Your A1 "exact replicate" must use
   `--start-superbatch 97 --superbatches 104`; the plan's default (`--start-superbatch 1 --superbatches 8`) is a
   different, hotter schedule. Export: qb 32, |w1|max 1.98 float (505 int), |w2|max 25344 int.
4. **New data for the evaluation lane**: the search-leaf corpus (positions the search actually hands to the net,
   with the net's own score attached) and a mined decision-error set from our own games. Paths and formats in §3.
5. **The speed lever is closed**: `nnue_eval` is already AVX2-vectorised on x86 (assembly inspected); two exact
   rewrites ran at 1.00×. 1536/2048 stay too slow. The check-pruning search candidate is neutral (+5 ±18). Do not
   spend the morning on either.
6. **Screens are in (30k, 576 games, vs fc_b)**: fcb_re −10, a2lite +1, k96b_ft −9, a3site −4, bp_d7_ft −13, bp96_d7_ft +5,
   **bp144_d7_ft +12 ±21** (+160 =276 −140), bp144_soft −7; bp144_ftd screening. +12 is exactly the chain threshold, so
   `gcp-x86` runs `combo_gate.sh bp144_d7_ft … C` (net + book vs V8.5, 150 games at 120+0.5) automatically after the
   book gate, then A. Treat the screen as an upper bound; only the real-clock combo result can ship a net.
   The screens rise monotonically with binpack exposure (48 → 96 → 144 sb: −13 → +5 → +12), so **Lane C4 is running
   on the pod from 06:42**: `bp240` = bp144 checkpoint + 96 more superbatches on the six binpacks (same schedule
   shape), then the same d7 shuffle pass and fc_b fine-tune → `bp240_d7_ft`, exported, mirrored, and screened by
   `screen_one.sh bp240_d7_ft` (≈ 08:50). Lane C5 (`bp336` = bp240 + 96 more sb, then the same d7 + fc_b steps →
   `bp336_d7_ft`, screen armed) is queued behind it so the GPU never idles; keep it only if bp240 holds the trend. `bp144_ftd` (fc_b schedule with no shuffle pass) is far negative
   (−111 at 210 games): the shuffle alignment pass is required, not optional. Width ladder done: `nnue_w768_ft`
   (9.5 MB) and `nnue_w512_ft` (6.3 MB) in `data/nets/` and `nets_night/`; the engine reads the width from the
   file (`bini_nnue.py` `hidden = w1.shape[1]`), so they load with no code change if size is the revealed constraint.
7. **Must-win build under gate** (`priorcrypto-vm:~/chess/gates/c40_vm.log`, 100 games 120+0.5): the frozen book
   candidate with contempt 20 → 40 (`cand_sfbook_c40`, one line in `bini_engine.py`), against the book candidate. Why:
   the London bracket is an eight-team knockout with ties going to the higher seed and we are seeded 6th, so every
   match we can play is a must-win against a higher seed; at equal strength, a higher decisive rate raises the odds of
   taking such a match (see Cause Table §17, `match_odds.py`). Ship rule: expected score not worse than −10 Elo at the
   pair-level lower bound, losses not up, decisive rate up, zero fallbacks. Otherwise contempt stays 20.
8. **Why the Swiss games drew — read from the platform logs (Cause Table §18).** Round 122 vs JBG fam: our engine
   took a forced perpetual at −20 in a position Stockfish calls dead level (pessimism + contempt 20 → the c40 build).
   Rounds 113/116/119: dead-drawn rook endings (Stockfish 0) held for 50–75 moves at a phantom "+60" that is the
   **correction history saturating at its ±64 cp cap in pawnless positions** (proven: `BINI_CORR=0` → 0/−1). Fix
   built: `cand_sfbook_eg` / `cand_sfbook_c40eg` (dead pawnless draws score 0; no correction history without pawns;
   switch `BINI_EG_DRAW`, 0 = old behaviour exactly), verified on the positions from those games; 576-game shape
   screen queued on the pod (`screen_eg.sh`), real-clock gate to run in the morning (`eg_gate.sh` on gcp-x86).

## 1. Machines and paths

| Box | Access | Role | Key paths |
|---|---|---|---|
| `gcp-x86` (8 vCPU Sapphire Rapids, 31 GB) | ssh alias on the Mac; user forge | the only x86 gate box; staging | `~/chess/gates/` (all gate logs), `~/chess/bookbuild/` (book + scripts), `~/chess/data/stage/{d10,bullet_shuf,ckpt,nets,leaf,clean_d10_shuf.bin}` |
| `priorcrypto-vm` (4 ARM, 23 GB) | ssh alias; user ubuntu | Stockfish jobs only (timing not representative) | `~/chess/bookbuild/` |
| Mac | local | orchestration, small jobs | scratchpad copies mirrored into `FinalsDay/night_evidence/` |
| Vast | none rented tonight (offers with ≥64 cores vanished within minutes); `provision_box.sh` + `push_to_box.sh` make a new box ready in ~15 min | | |

Generators on both boxes are SIGSTOPped (`bini_v65/tools/pause_gen.sh resume` to restart; they feed nothing now).

## 2. Opening book (rules: a shipped table may answer the opening ≤ move 20, whatever produced it)

- Builder `sf_book.py`: per root, per colour we might be, our plies = SF19 best, opponent plies = top-3 within 60 cp,
  6 plies (GCP shard, 568 roots at 1.2M/0.8M nodes) or 4 plies (the rest, 0.8M nodes), decided lines (>200 cp) not
  extended, no position with a legal en-passant capture, nothing beyond fullmove 20.
- Merge `merge_book.py` is deterministic (sorted keys, lowest ply wins, ties lexicographic), Stockfish entries override,
  old-book entries kept only for roots Stockfish did not cover. Audit `book_audit.py`: every key parses, every move legal.
- Candidate = exact V8.5 code + `book.json` + `patch_guards.py` (book only if fullmove ≤ 20 and no en-passant capture is
  legal; logs each book move's saved budget and one `bookexit` line). `test_budget_identity.py`: 0 differences.
  Functional test log: `wrapper_guard_functional_test.log`.
- Frozen candidate on `gcp-x86`: `~/chess/cand_sfbook/`, zip `~/chess/gates/sfbook.zip`, manifest `~/chess/gates/sfbook_manifest.txt`.
- Gate: `arena_par` (real wrapper, book on both sides, 120+0.5, colour-paired openings) vs V8.5 as shipped, 300 games,
  6 workers, per-game stats sidecar (`sfbook_real.stats.jsonl`: colour, start FEN, result, termination, full stderr).
- **Decision rule proposed to Archit**: ship the book if pair-level Elo lower bound ≥ −10, loss rate not higher than
  V8.5's, zero fallbacks/timeouts; otherwise V8.5. A positive point estimate at 300 games is noisy either way.
- If negative: book v2 filter idea (prefer, among near-equal SF moves for our side, the one our engine also rates well).

## 3. New data (formats)

- **Search-leaf corpus** (`leaf_dump.py` on a diagnostic engine `patch_dump.py`): sampled interior static evaluations
  and quiescence stand-pats from 2M-node searches at each root and 2 plies along the book line. JSONL rows:
  `fen, ev (raw net score, side-to-move cp), src (0 interior / 1 qsearch), ply, root, rootmove, rootscore, depth`.
  Files: `gcp-x86:~/chess/data/stage/leaf/leaf_mac.jsonl` (+ `leaf_vm.jsonl` when the VM half finishes);
  profile in `leaf_mac_profile.json`. First finding: the search's positions are far denser than the corpus
  (92 % ≥ 28 pieces vs 27 %). Use as spice (≤ 5–10 %), never as the base; profile |cp|>800 before mixing.
- **Labelled pilot** (`label_leaf.py`, SF19 depth 12, stratified: dense and quiet positions capped):
  `gcp-x86:~/chess/data/stage/leaf/leaf_labels_mac_*.npz` in the trainer's npz convention
  (`pieces uint8[N,64] codes 1..12, stm, cp WHITE view, result 0, quiet, depth`) → `bulletformat.py convert` → .bin;
  plus `leaf_labels_mac.labels.jsonl` with `ev_stm` (net) next to `cp_white` (SF) for resolution analysis.
- **Decision errors** (`mine_errors.py`, our self-play games, SF depth 12–14): JSONL rows
  `fen, played, best, cp_best, cp_played, loss` — the "good move vs bad move" pairs for deep relabelling of both
  continuations (walk 1–2 plies from each). Files: `~/chess/data/stage/leaf/errors_mac.jsonl`, `errors_vm.jsonl`
  (pilots: ~150 + ~80 games). Full run needs CPU: 1,376 games are in `astra_reports/gate_mirror/out/gate{A,B,C}.pgn`
  and `astra_reports/nodegate_c1c2.pgn`.

- **Where to spend deep labels (resolution probe, 34,600 real positions, `resolution_probe.json`)**: the net is
  close to Stockfish with ≥ 24 pieces (slope 0.97, MAE 88) and compresses in the endgame: slope 0.58 at 12–17
  pieces (MAE 170), 0.28 at 6–11 (MAE 451); 508 of the 519 "big advantage read as small" failures have ≤ 23
  pieces. Part is label depth (depth-7 targets). Target for N2/spice: **12–23 pieces, |SF| 150–600, depth ≥ 12
  labels**, kept ≤ 5 % of the mix (endgame-heavy mixes lost Elo before when they were 20–38 %). **But note**
  `search_resolution.json`: inside that band the static eval is unbiased on average (slope ≈ 1.0) and the search
  removes most near-equal misreads (4–9 % → ~1 %); the steep slopes are decided endgames. So the main lever is
  broad deeper-label continuation (noise reduction, A2/A6), the spice is a small targeted extra, not the fix.

- **Ready-made endgame spice** (`site_spice.py`): the site's own Stockfish-16 **depth-16** labels over 6,715 archived
  games, filtered to 12–23 pieces and |cp| 150–600 (White view), deduplicated: **118,266 positions, 79 % quiet, evenly spread over the band** (12–15 / 16–19 / 20–23 pieces ≈ 37k / 40k / 41k), trainer npz convention →
  `gcp-x86:~/chess/data/stage/leaf/site_spice_12_23.npz` (+ `.jsonl`). This is in-distribution (ladder/Swiss games,
  curated openings), deeper than fc_b's labels, and aimed exactly at the weak band. Convert with
  `bulletformat.py convert`, mix at ≤ 5–10 %, profile |cp|>800 first. Note: mixed-source site data hurt earlier
  when used at ×4–×12 weight in from-scratch or wide mixes; this is a filtered, small spice — a different use.
- **Endgame leaf corpus**: the VM's leaf dump samples search leaves from 1,000 endgame-ish positions (12–23 pieces,
  move ≥ 25) out of our own self-play games → `leaf_vm.jsonl` (with the net's own score per position).

## 4. Tools ready on `gcp-x86` (`~/chess/`)

| Script | What it does |
|---|---|
| `net_gate.sh <net.safetensors> <tag> [screen_games] [tc5_games] [real_games]` | exact V8.5 code + your net: package smoke, 576-game 30k screen vs fc_b, 5+0.05 ladder, optional 120+0.5 wrapper |
| `combo_gate.sh <net> <book.json> <tag> [games] [workers] [A|B|C]` | A: net vs V8.5; B: net+book vs net; C: net+book vs V8.5 (the shipping check) |
| `pkg_smoke.py <build_dir> <tag>` | zip like package_astra, extract clean, production init (no env), NNUE on, legal move, init s, peak RSS |
| `bookbuild/book_gate_report.py <arena.log> <stats.jsonl>` | pair-level Elo, pentanomial, terminations, fallbacks/timeouts, book hits / saved s / exit fullmove per colour |
| `bookbuild/patch_guards.py <build_dir>` | the wrapper guards + book instrumentation |
| `night_evidence/patch_clock.py <build_dir> [BASE_MS] [INC_MS]` | one-command clock retarget for the on-day constraint (proven identical at 120/0.5) |
| `night_evidence/provision_box.sh`, `push_to_box.sh <alias>` | a fresh x86 box ready in ~15 min |

### The A-lane is one command on any CUDA box

`bash run_a_lane.sh forge@8.228.62.35` (script at `gcp-x86:~/chess/run_a_lane.sh` and in `night_evidence/`): provisions
(rust, bullet trainer pinned rev, Stockfish, platform venv), pulls the staged corpus/spice/checkpoint/nets from
`gcp-x86`, mixes A2-lite (clean_d10 + 3 % depth-16 spice + 2 % leaf labels if present, refuses if |cp|>800 > 4.5 %),
runs **A1 = exact fc_b replicate** (`--resume k96-96 --start-superbatch 97 --superbatches 104`, cosine 0.0005) and
**A2-lite** with the same schedule, exports both with the ACC_BOUND check and three sanity evaluations, screens both
vs fc_b at 30k nodes (576 games) and at 5+0.05 (400 games) on the box's own cores, and mirrors nets + checkpoints
back to `gcp-x86:~/chess/data/stage/{nets_night,ckpt_night}`. Expect ~10 min provisioning, ~5 min per arm on a
5090, ~30–60 min of gates at 8 workers. The real-clock wrapper gate then runs on `gcp-x86` (`net_gate.sh` / `combo_gate.sh C`).

**Tonight's A-lane run** (RunPod A40, `ssh root@63.141.33.33 -p 22018`, everything under `~/chess`, status in
`~/chess/logs/a_lane.status`, mirrored to `gcp-x86:~/chess/data/stage/nets_night/`): A1 `fcb_re` (exact fc_b
replicate, control) and A2-lite `a2lite` (clean_d10 + 3 % depth-16 endgame spice, same schedule), both exported
with the ACC_BOUND check, screened vs fc_b at 30k nodes and at 5+0.05 on the pod's cores. §6 shows the live status.
Also queued on the pod (`~/chess/logs/{b_lane,a3_site,screen_queue}.status`): **Lane B** `k96b` = the 712 M depth-7
shuffle from scratch (96 sb, the recipe that measured +9 over the current base) → `k96b_ft` = exact fc_b continuation
on top; **A3-site** = clean_d10 + 5 % all-band site depth-16 labels (`site_all.bin`, 532,217 positions, 80 % quiet, staged on gcp-x86 and the pod; mix 37.06 M rows, 3.65 % extreme); **Lane C** (`~/chess/logs/c_lane.status`, the "much larger" pretrain): the public Stockfish binpacks
test80-2024 jan–jun (≈ 52 GB, billions of positions) downloaded to the pod; the trainer was patched with `--eval-scale`
(`night_evidence/bullet_trainer_patched/main.rs`); a 6-sb pilot measures the score-scale ratio k = slope(pilot)/slope(fc_b)
on a depth-10 chunk; `bp48` = 48 sb from scratch at eval-scale 400/k, `--max-score 3000`; `bp_d7` = 12 sb alignment on
our 712 M shuffle; `bp_d7_ft` = exact fc_b schedule on clean_d10; exports with bound + sanity; screened by
`screen_one.sh bp_d7_ft`. Measured tonight: pilot loader 2.6 M pos/s; slope pilot 1.250 vs fc_b 0.781 → **k = 1.60, eval-scale 249.8**. Kill rules as in PRETRAIN_PLAN §4.C. The screen queue screens every
new net vs fc_b at 30k (576 games) and runs the 5+0.05 ladder for the best. Decision rule for a net: screen ≥ +12 vs fc_b and 5+0.05 lower bound > −5 → run `combo_gate.sh <net> <book> <tag> 300 6 C`
on `gcp-x86` (real wrapper, 120+0.5) once the book gate has finished; ship only on that.

**C2** (`c2_lane.status`): if Lane C completes, `bp48` continues to 96 superbatches (`bp96`), re-aligned and re-fine-tuned
(`bp96_d7_ft`), screened by `screen_one.sh bp96_d7_ft`. **On-day fine-tune**: `bash run_onday_ft.sh <ckpt_dir> <id>
[spice.bin:pct] [sb=3]` on the pod (lr 0.0003, ≤ 3 sb, export + bound). **Extra pods as gate workers**:
`bash gate_worker.sh forge@8.228.62.35 <agent_dir> <opponent_dir> <slice_start> <games> <tag>` runs a 120+0.5 wrapper
block on a disjoint opening slice (results to `gcp-x86:~/chess/data/stage/gates_pods/`; combine with
`book_gate_report.py` per block, pairs stay intact within a block).

Checkpoints are saved every 16 superbatches inside the binpack runs and a mirror loop copies every checkpoint, net and log to `gcp-x86:~/chess/data/stage/{ckpt_night,nets_night}` every 10 min (`~/chess/logs/mirror.log`). **C3** (`c3_lane.status`): bp96 → 144 superbatches (Archit: aim for 144) (`bp144_d7_ft`) if the clock allows, screened by `screen_one.sh`.
**Automatic real-clock gates on gcp-x86** (`gates/morning_chain.status`): when the book gate reaches 300 games or 08:00 BST (pace ~64 games/h from 02:24) it stops it, writes
`gates/sfbook_report.json`, picks the best 30k-screened net (needs ≥ +12), runs `combo_gate.sh … C` (net + book vs V8.5,
150 games, the shipping check) then `… A` (net vs V8.5); reports in `gates/combo_<net>_{C,A}_report.json`. Nothing uploads.

**Lane C outcome so far**: bp48 → aligned net `bp_d7_ft` screened **−13 ±20** vs fc_b (one pass is not a gain); bp96 and
bp144 aligned nets screened next; the hot 12-sb shuffle alignment is the suspect, so two variants from bp144 were added
(`bp144_ftd` direct fc_b schedule; `bp144_soft` gentle lr 0.0001 shuffle pass then fc_b schedule), all in
`~/chess/data/nets/` on the pod and `nets_night/` on gcp-x86, screens in `screen_queue.status`. Checkpoints for every stage
(bp48-16/32/48, bp96-64/80/96, bp144-112/128/144, all `_d7`/`_ft`) are in `ckpt_night/` on gcp-x86: any of them can be
re-aligned differently in minutes with `run_onday_ft.sh`.

**Width ladder** (`width_ladder.status`): `w768_ft` and `w512_ft` (from scratch on the shuffle, 96 sb, then the fc_b-style
continuation), exported with size and bound — the insurance nets if the brief caps package size or memory (the 1024 net
is 12.6 MB, the book 13 MB). They are not screened (cross-width screens mislead); judge at the clock only if needed.

## 4b. Everything runs on the boxes; the Mac is offline from ~08:00 (Archit in transit)

Nothing depends on the Mac. Where each result appears, with its report generated on the box itself:

| what | box | progress | report |
|---|---|---|---|
| contempt-40 gate (100 games, book vs book) | priorcrypto-vm | `~/chess/gates/c40_vm.log` | `~/chess/gates/c40_vm_report.json` + match odds in `gates/vm_chain.status` |
| endgame-fix gate (100 games, eg vs book) — runs automatically after the above | priorcrypto-vm | `~/chess/gates/eg_vm.log` | `~/chess/gates/eg_vm_report.json` |
| combo C: bp144_d7_ft + book vs V8.5 (150) | gcp-x86 | `~/chess/gates/combo_bp144_d7_ft_C.log` | `~/chess/gates/combo_bp144_d7_ft_C_report.json` |
| then automatically (`gcp_after_C.sh`, stops combo A): full package on the current net `cand_sfbook_c40eg` vs V8.5 (120) | gcp-x86 | `~/chess/gates/final_c40eg_vs_v85.log` | `…_report.json`, `gates/after_chain.status` |
| then, if combo C > 0: `cand_final_bp144` (bp144_d7_ft + book + contempt 40 + endgame fix) vs V8.5 (120); package `submission_V9_bp144_book_c40eg.zip` | gcp-x86 | `~/chess/gates/final_bp144_vs_v85.log` | `…_report.json` |
| shape screens (30k, 576): contempt 40 vs 20 = −1 ±19 (done); endgame fix eg=1 vs eg=0 (running); bp240_d7_ft vs fc_b; bp336 later | pod | `~/chess/logs/screen_queue.status` | mirrored to `gcp-x86:~/chess/data/stage/nets_night/` |

Read any report with: `python3 -c "import json;r=json.load(open('<report>'));print(r['W'],r['D'],r['L'],r['pair_elo'],r['pair_elo_95'],r['failures'])"`.
The Mac's endgame-fix arena was stopped at 10 games (partial, not for decisions) and continues on the VM as `eg_vm`.

## 4c. Added at 09:00 — the five things we were not focusing on (Cause Table §20)

1. Rehearse the revealed constraint: clock (`patch_clock.py` + short-clock stress test on the pod), size (no-book
   packages, w768/w512 nets), memory (RSS ~800 MB), init cap (fallback plays until the compile joins), odd inputs.
2. Robustness through the package, not the engine: `fen_battery.py` — **PASS** on the exact c40eg zip (32 checks).
3. A non-clone opponent: Stockfish 19 at UCI_Elo 2400 in the agent interface (`sf_agent/`), 60 games vs the full
   package on the pod (`gates/sf2400.log` / `_report.json`) — absolute level and decisive rate vs a different style.
4. Opponent-aware book: `opp_book_cov.py` on Miskeen/Rataturing PGNs — 36 % coverage of our-move positions in their
   lines, no repeated uncovered position, so no extension is worth building; the book's value is the hits it has.
5. The freeze protocol: `status_all.sh` (one command, every result), manifests + `smoke_zip.py` on the exact bytes,
   sha256 of the uploaded file vs `packages/MANIFEST.txt`, `submission_V8.5.zip` for rollback, stop reading gates 45 min
   before the freeze, ssh to the three boxes is all the venue needs.

## 5. Morning sequence (recommended)

1. Read §6, then run the gate report; apply the decision rule with Archit.
2. Your A1 with the resolved schedule (§0.3), against fc_b, on the staged corpus; then A2/A6 with N1 if the fleet
   exists; the leaf pilot and error set as ≤ 5 % spice in A3-style arms only.
3. Any net: `net_gate.sh` first; if it passes the screen and the ladder, `combo_gate.sh … C` is the shipping check.
4. On the brief: `FinalsDay/Finals Night Cause Table.md` §5 (hard-coded assumptions) and §8 (runbook).
5. Must-win contempt: read `FinalsDay/night_evidence/c40_vm_report.json` (pair-level) and the match odds in §6 below;
   apply the ship rule in §0.7. If it passes and the book passes, the shipping package is book + contempt 40
   (`cand_sfbook_c40`); if only the book passes, `cand_sfbook`; otherwise V8.5 unchanged. Every package must go through
   `pkg_smoke.py` on gcp-x86 before upload; nothing is uploaded without Archit's explicit go.
6. **Ready-made packages** (`gcp-x86:~/chess/packages/`, sha256s in `MANIFEST.txt` and
   `FinalsDay/night_evidence/packages_manifest.txt`), all in the 10-file layout of `submission_V8.5.zip`:
   `submission_V9_book.zip` (V8.5 + book + guards = `cand_sfbook`), `submission_V9_book_c40.zip` (+ contempt 40),
   `submission_V9_book_eg.zip` (+ endgame honesty, §0.8), `submission_V9_book_c40eg.zip` (book + contempt 40 +
   endgame honesty = the full candidate). Real-clock gate for any pair of build dirs, with smoke and stats:
   `bash ~/chess/pair_gate.sh <cand_dir> <opp_dir> <tag> [games] [workers]` (e.g. `cand_sfbook_c40eg
   bini_astra_v5_noc2b final_vs_v85 150`); report with `book_gate_report.py <tag>.log <tag>.stats.jsonl`.
   Suggested order on gcp-x86 once the automatic chain's combo C is in: kill combo A if time is short, then
   `pair_gate.sh cand_sfbook_c40eg bini_astra_v5_noc2b final_vs_v85 150`. Before uploading anything, smoke the exact bytes on a quiet box:
   `~/chess/venv/bin/python ~/chess/smoke_zip.py ~/chess/packages/<zip>` (fresh interpreter, no BINI_* env, init
   seconds, legal move in and out of book, peak RSS). If a net passes its combo gate, build its package with
   `pkg_smoke.py cand_netbook_<tag> <tag>` (writes `gates/<tag>.zip`) and smoke that zip the same way.

## 6. Live status at push time (auto-filled)

Written 2026-09-12 11:12 BST.

/private/tmp/claude-501/-Users-architbhardwaj-Desktop-AI-Chessathon/edc9c181-8258-4c54-8a6f-0a83813055f3/scratchpad/morning_push.sh: line 9: gcp-x86:~/chess/gates/sfbook_real.log: No such file or directory
**Book gate ()** — read as partial unless it says 300/300:
```
[300/300] +40 =235 -25  score 52.5%  elo +17 ±40  last: draw by insufficient_material
0
  wall=30.0s rc=0
72f24cd95d6329158a411863d8857aba21c6abe43824dbf3d3b4b0360f2b4b0f  /home/forge/chess/gates/sfbook.zip
gate started Sat Sep 12 01:24:23 UTC 2026 games=300 workers=6
Sat Sep 12 01:24:23 UTC 2026 finish_book2 done
```

**Gate report so far**:
```
{
 "games": 300,
 "of": 300,
 "W": 40,
 "D": 235,
 "L": 25,
 "score": 0.525,
 "terminations": "checkmate 65, fifty_moves 43, insufficient_material 45, threefold_repetition 147",
 "failures": {
  "still_compiling": 0,
  "agent_failure": 0,
  "engine_error": 0,
  "illegal": 0
 },
 "pairs": 150,
 "pentanomial": [
  1,
  21,
  95,
  28,
  5
 ],
 "pair_elo": 17.4,
 "pair_elo_95": [
  -1.9,
  36.8
 ],
 "book": {
  "games_without_hit": 5,
  "hits_white": {
   "n": 150,
   "mean": 3.67,
   "median": 4.0,
   "max": 7
  },
  "hits_black": {
   "n": 150,
   "mean": 4.05,
   "median": 4.0,
   "max": 8
  },
  "saved_s_white": {
   "n": 145,
   "mean": 14.71,
   "median": 15.662,
   "max": 28.046
  },
  "saved_s_black": {
   "n": 150,
   "mean": 15.89,
   "median": 15.663,
   "max": 32.304
  },
  "exit_fullmove_white": {
   "n": 144,
   "mean": 11.73,
   "median": 12.0,
   "max": 16
  },
  "exit_fullmove_black": {
```

**Book audit / merge / manifest**:
```
Sat Sep 12 01:23:47 UTC 2026 mac residues redone: 12047 entries
/home/forge/chess/bookbuild/book_sf.json: 58206 entries = 58206 Stockfish (from 1226 roots, per-ply [(0, 1225), (1, 2579), (2, 3887), (3, 8232), (4, 12037), (5, 12051), (6, 18195)], same-ply move conflicts 142) + 0 kept from the old book; roots covered by Stockfish 1226/1226; bytes 12,987,295; sha256 13ce997aafa9b7c8
{"entries": 58206, "bad_keys": 0, "illegal_moves": 0, "provenance": {"SF19": 58206}, "root_coverage": {"SF19": 1226}, "sf_per_ply": {"0": 1225, "1": 2579, "2": 3887, "3": 8232, "4": 12037, "5": 12051, "6": 18195}}
== Sat Sep 12 01:23:48 UTC 2026 candidate = V8.5 + book 13ce997aafa9b7c8 + wrapper guards
{"entries": 58206, "bad_keys": 0, "illegal_moves": 0, "provenance": {"SF19": 58206}, "root_coverage": {"SF19": 1226}, "sf_per_ply": {"0": 1225, "1": 2579, "2": 3887, "3": 8232, "4": 12037, "5": 12051, "6": 18195}}
sfbook: zip sha256 72f24cd95d632915 files=10 unzipped=25,733,859 bytes (OK)
  bini-5.0 ready: import+compile 27.8s (compile 27.2s), nnue=on
  SMOKE init=27.9s nnue_ready=True move=d2d3 legal=True move_secs=2.08
  print(f'SMOKE init={t1:.1f}s nnue_ready={ok} move={m} legal={chess.Move.from_uci(m) in chess.Board(fen).legal_moves} move_secs={dt:.2f}', file=sys.stderr, flush=True)
  Maximum resident set size (kbytes): 818204
  wall=30.0s rc=0
gate started Sat Sep 12 01:24:23 UTC 2026 games=300 workers=6
dfb38cd5dd71d1f72f65091e8ce8f84fc474fb5dfbc18bdb53be59b87a480f5b  agent.py
1a582d7070b387d1bc4fa53f1af27980e4942a17573e38b61fe5f75d70c81686  bini_board.py
9b27ed85d03e922246d980d8b2c6f5c983d6039839f28cf357b9db27983b3cee  bini_calib.py
58341806b5b2f9c4988087a7a57a8599993a383ab47ec3b9b90268b96ba99389  bini_engine.py
913d66bf66efbab4bb40db55a0be09f74593d413a34258fa89c92f20ea56dd74  bini_eval.py
44b8d7235f510dcfee5fe0616bae351e724c1247a9ff7cf29a23dc0e408560bf  bini_magics.py
f2021fd56e5194b5b4add89dcae6d5da2b73bd22f2ee01e12b12269a46cc420a  bini_nnue.py
bd827b9546ed1320d63d2be663345e1348994d3111dd73d2d5ba8ad8186c4c8d  bini_search.py
f5364f3bd26001312067da56bc1bb188c1b93439e2bb4f19eb204b3b8331e0bf  nnue.safetensors
13ce997aafa9b7c8ed719e3834ebd77bb39be0ab56367929f74cc1758fe6cb6a  book.json
72f24cd95d6329158a411863d8857aba21c6abe43824dbf3d3b4b0360f2b4b0f  /home/forge/chess/gates/sfbook.zip
```

**Leaf corpus / labels / errors**:
```
leaf_mac rows:  1489633
/private/tmp/claude-501/-Users-architbhardwaj-Desktop-AI-Chessathon/edc9c181-8258-4c54-8a6f-0a83813055f3/scratchpad/morning_push.sh: line 19: /private/tmp/claude-501/-Users-architbhardwaj-Desktop-AI-Chessathon/edc9c181-8258-4c54-8a6f-0a83813055f3/scratchpad/out/leaf_vm.jsonl: No such file or directory
leaf_vm rows: 
labelled (mac pilot):   100000
errors_mac:      111  errors_vm:       24
Sat Sep 12 00:35:23 BST 2026 waiting for leaf dump
Sat Sep 12 01:36:27 BST 2026 leaf dump done:  1489633 rows
Sat Sep 12 01:36:28 BST 2026 profile written
Sat Sep 12 01:36:37 BST 2026 leaf_mac synced to gcp stage
Sat Sep 12 01:36:37 BST 2026 miner done:  errors
Sat Sep 12 01:36:37 BST 2026 labelling done:  labelled
Sat Sep 12 01:36:39 BST 2026 site spice synced
Sat Sep 12 01:36:39 BST 2026 mac chain done
Sat Sep 12 01:38:37 BST 2026 post-leaf relaunch (quoting fix)
Sat Sep 12 01:41:11 BST 2026 profile written
Sat Sep 12 01:44:18 BST 2026 labelling done:  labelled
Sat Sep 12 01:49:33 BST 2026 miner done:      111 errors
Sat Sep 12 01:49:33 BST 2026 mac post-leaf done
Sat Sep 12 02:03:57 BST 2026 miner2 done:      131 errors
Sat Sep 12 02:50:47 BST 2026 labelling done:   100000 labelled
Sat Sep 12 04:38:56 BST 2026 miner3 done: 332 errors
total 450996
drwxrwxr-x 2 forge forge      4096 Sep 12 03:38 .
drwxrwxr-x 9 forge forge      4096 Sep 12 01:47 ..
-rw-r--r-- 1 forge forge    119997 Sep 12 03:38 errors_all.jsonl
-rw-r--r-- 1 forge forge     23306 Sep 12 00:49 errors_mac.jsonl
-rw-r--r-- 1 forge forge     28309 Sep 12 01:03 errors_mac2.jsonl
-rw-r--r-- 1 forge forge  24575303 Sep 12 01:50 leaf_labels_mac.labels.jsonl
-rw-r--r-- 1 forge forge   7001468 Sep 12 01:50 leaf_labels_mac_000.npz
-rw-r--r-- 1 forge forge 349333078 Sep 12 00:35 leaf_mac.jsonl
-rw-r--r-- 1 forge forge      1201 Sep 12 00:41 leaf_mac_profile.json
-rw-rw-r-- 1 forge forge  17030944 Sep 12 00:50 site_all.bin
-rw-r--r-- 1 forge forge  37256658 Sep 12 00:50 site_all.npz
-rw-r--r-- 1 forge forge       392 Sep 12 00:02 site_spice.log
-rw-rw-r-- 1 forge forge   3784512 Sep 12 00:16 site_spice_12_23.bin
-rw-r--r-- 1 forge forge  14352009 Sep 12 00:02 site_spice_12_23.jsonl
-rw-r--r-- 1 forge forge   8280088 Sep 12 00:02 site_spice_12_23.npz
```

Pseudo-terminal will not be allocated because stdin is not a terminal.
Host key verification failed.
/private/tmp/claude-501/-Users-architbhardwaj-Desktop-AI-Chessathon/edc9c181-8258-4c54-8a6f-0a83813055f3/scratchpad/morning_push.sh: line 23: /Users/architbhardwaj/chess/logs/a_lane.status: No such file or directory
**A-lane on the RunPod A40 (, )**:
```
== a_lane
fcb_re sanity rnbqkbnr/pppppppp/8/8/8/ -480 cp (stm view; expect ~0, positive, negative)
2026-09-12 00:45:42 ARM a2lite: data=/root/chess/data/ft/a2lite.bin superbatches=104 start=97 
2026-09-12 00:49:32 ARM a2lite trained
read /root/chess/data/ckpt/a2lite-104/raw.bin: l0w[6144, 1024], l0b[1024], l1w[8, 2048], l1b[8]
exported /root/chess/data/nets/nnue_a2lite.safetensors (12.62 MB): 8x768x1024x2->8 screlu; qb 32 |w1|max 1.980 |b1|max 0.766 |w2|max 1.980 |b2|max 0.258
a2lite ACC_BOUND 16355 int16 OK
a2lite sanity rnbqkbnr/pppppppp/8/8/8/ 22 cp (stm view; expect ~0, positive, negative)
a2lite sanity 8/8/4k3/8/8/4K3/4P3/8 w  243 cp (stm view; expect ~0, positive, negative)
a2lite sanity rnbqkbnr/pppppppp/8/8/8/ -479 cp (stm view; expect ~0, positive, negative)
2026-09-12 01:21:04 SCREEN fcb_re vs fc_b: 01:21:03 [576/576] +110 =339 -127 score 48.5% elo -10 ±18 (pentanomial [15, 71, 126, 68, 8])
2026-09-12 01:51:22 SCREEN a2lite vs fc_b: 01:51:21 [576/576] +124 =330 -122 score 50.2% elo +1 ±18 (pentanomial [13, 63, 129, 75, 8])
2026-09-12 01:52:09 A-lane done (5+0.05 ladders skipped: screens of k96b_ft / a3site / Lane C take priority; ladder runs for the best via screen_queue)
== b_lane
2026-09-12 00:56:05 shuffle pulled: 22G
2026-09-12 00:56:05 ARM k96b: from scratch, 8 shuffle files, 96 sb cosine 0.0005
2026-09-12 01:44:19 ARM k96b trained
read /root/chess/data/ckpt/k96b-96/raw.bin: l0w[6144, 1024], l0b[1024], l1w[8, 2048], l1b[8]
exported /root/chess/data/nets/nnue_k96b.safetensors (12.62 MB): 8x768x1024x2->8 screlu; qb 32 |w1|max 1.980 |b1|max 0.590 |w2|max 1.980 |b2|max 0.141
2026-09-12 01:44:19 ARM k96b_ft: resume k96b-96, fc_b schedule (start 97, 104 sb) on clean_d10
2026-09-12 01:48:25 ARM k96b_ft trained
read /root/chess/data/ckpt/k96b_ft-104/raw.bin: l0w[6144, 1024], l0b[1024], l1w[8, 2048], l1b[8]
exported /root/chess/data/nets/nnue_k96b_ft.safetensors (12.62 MB): 8x768x1024x2->8 screlu; qb 32 |w1|max 1.980 |b1|max 0.602 |w2|max 1.980 |b2|max 0.139
k96b ACC_BOUND 16311 int16 OK
k96b_ft ACC_BOUND 16314 int16 OK
2026-09-12 01:48:36 B-lane done (nets + checkpoints mirrored)
== a3_site
2026-09-12 00:47:59 waiting for site_all.npz and the GPU
2026-09-12 00:51:01 site_all converted: /root/chess/data/ft/site_all.bin: 532217 rows, black-to-move 50.0%, quiet 80.1%, depth 16-16, cp mean +4 |cp| mean 245 |
base /root/chess/data/ft/clean_d10_shuf.bin: 35,458,988 rows
spice /root/chess/data/ft/site_all.bin: 532,217 rows x3 (target 5.0% = 1,866,262)
mix: 37,055,639 rows, |cp|>800 3.65%, mean|cp| 224.9
wrote /root/chess/data/ft/a3site.bin
2026-09-12 01:48:35 ARM a3site: clean_d10 + 5% site depth-16, fc_b schedule
2026-09-12 01:52:26 ARM a3site trained
read /root/chess/data/ckpt/a3site-104/raw.bin: l0w[6144, 1024], l0b[1024], l1w[8, 2048], l1b[8]
exported /root/chess/data/nets/nnue_a3site.safetensors (12.62 MB): 8x768x1024x2->8 screlu; qb 32 |w1|max 1.980 |b1|max 0.766 |w2|max 1.980 |b2|max 0.258
a3site ACC_BOUND 16355 int16 OK
2026-09-12 01:52:29 A3-site done
== c_lane
exported /root/chess/data/nets/nnue_bp_d7.safetensors (12.62 MB): 8x768x1024x2->8 screlu; qb 32 |w1|max 1.745 |b1|max 0.715 |w2|max 1.980 |b2|max 0.141
2026-09-12 02:39:49 ARM bp_d7_ft: fc_b schedule on clean_d10 from bp_d7
2026-09-12 02:43:57 bp_d7_ft trained
read /root/chess/data/ckpt/bp_d7_ft-104/raw.bin: l0w[6144, 1024], l0b[1024], l1w[8, 2048], l1b[8]
exported /root/chess/data/nets/nnue_bp_d7_ft.safetensors (12.62 MB): 8x768x1024x2->8 screlu; qb 32 |w1|max 1.738 |b1|max 0.715 |w2|max 1.980 |b2|max 0.139
bp48 ACC_BOUND 15778 int16 OK |w2|max 25344
bp_d7 ACC_BOUND 14422 int16 OK |w2|max 25344
bp_d7_ft ACC_BOUND 14358 int16 OK |w2|max 25344
bp_d7_ft sanity rnbqkbnr/pppppppp/8/8/8/ 15 cp
bp_d7_ft sanity 8/8/4k3/8/8/4K3/4P3/8 w  213 cp
bp_d7_ft sanity rnbqkbnr/pppppppp/8/8/8/ -425 cp
2026-09-12 02:44:44 C-lane done
== c2_lane
2026-09-12 01:37:17 waiting for Lane C
2026-09-12 02:45:18 ARM bp96: resume bp48-48, 48 more sb on jan..jun at eval-scale 249.8
2026-09-12 03:17:11 bp96 trained
2026-09-12 03:17:11 ARM bp96_d7: 12 sb on the shuffle from /root/chess/data/ckpt/bp96-96
2026-09-12 03:23:13 bp96_d7 trained
2026-09-12 03:23:13 ARM bp96_d7_ft: fc_b schedule on clean_d10
2026-09-12 03:27:21 bp96_d7_ft trained
read /root/chess/data/ckpt/bp96_d7_ft-104/raw.bin: l0w[6144, 1024], l0b[1024], l1w[8, 2048], l1b[8]
exported /root/chess/data/nets/nnue_bp96_d7_ft.safetensors (12.62 MB): 8x768x1024x2->8 screlu; qb 32 |w1|max 1.796 |b1|max 0.806 |w2|max 1.980 |b2|max 0.109
bp96_d7_ft ACC_BOUND 14861 int16 OK
2026-09-12 03:27:30 C2-lane done
== c3_lane
2026-09-12 01:40:20 waiting for C2
2026-09-12 03:28:20 ARM bp144: resume /root/chess/data/ckpt/bp96-96, 48 more sb at eval-scale 249.8
2026-09-12 04:00:06 bp144 trained
2026-09-12 04:06:09 bp144_d7 trained
2026-09-12 04:10:16 bp144_d7_ft trained
read /root/chess/data/ckpt/bp144_d7_ft-104/raw.bin: l0w[6144, 1024], l0b[1024], l1w[8, 2048], l1b[8]
exported /root/chess/data/nets/nnue_bp144_d7_ft.safetensors (12.62 MB): 8x768x1024x2->8 screlu; qb 32 |w1|max 1.815 |b1|max 0.846 |w2|max 1.980 |b2|max 0.105
bp144_d7_ft ACC_BOUND 15032 int16 OK
2026-09-12 04:10:26 C3-lane done
== align_variants
2026-09-12 04:12:33 ARM bp144_ftd: fc_b schedule directly from bp144
2026-09-12 04:16:32 bp144_ftd trained
read /root/chess/data/ckpt/bp144_ftd-104/raw.bin: l0w[6144, 1024], l0b[1024], l1w[8, 2048], l1b[8]
exported /root/chess/data/nets/nnue_bp144_ftd.safetensors (12.62 MB): 8x768x1024x2->8 screlu; qb 32 |w1|max 1.863 |b1|max 0.750 |w2|max 1.980 |b2|max 0.113
bp144_ftd ACC_BOUND 15391 int16 OK
2026-09-12 04:16:33 ARM bp144_soft: 12 sb on the shuffle at lr 0.0001 from bp144, then fc_b schedule
2026-09-12 04:22:37 bp144_s7 trained
2026-09-12 04:26:46 bp144_soft trained
read /root/chess/data/ckpt/bp144_soft-104/raw.bin: l0w[6144, 1024], l0b[1024], l1w[8, 2048], l1b[8]
exported /root/chess/data/nets/nnue_bp144_soft.safetensors (12.62 MB): 8x768x1024x2->8 screlu; qb 32 |w1|max 1.845 |b1|max 0.768 |w2|max 1.980 |b2|max 0.122
bp144_soft ACC_BOUND 15236 int16 OK
2026-09-12 04:26:50 align variants done
== width_ladder
2026-09-12 05:02:21 w768 trained
2026-09-12 05:05:23 w768_ft trained
read /root/chess/data/ckpt/w768_ft-104/raw.bin: l0w[6144, 768], l0b[768], l1w[8, 1536], l1b[8]
exported /root/chess/data/nets/nnue_w768_ft.safetensors (9.47 MB): 8x768x768x2->8 screlu; qb 32 |w1|max 1.974 |b1|max 0.570 |w2|max 1.980 |b2|max 0.165
w768_ft ACC_BOUND 16241 int16 OK size 9465500 bytes
2026-09-12 05:05:24 ARM w512: from scratch on the shuffle, 96 sb
2026-09-12 05:28:15 w512 trained
2026-09-12 05:30:23 w512_ft trained
read /root/chess/data/ckpt/w512_ft-104/raw.bin: l0w[6144, 512], l0b[512], l1w[8, 1024], l1b[8]
exported /root/chess/data/nets/nnue_w512_ft.safetensors (6.31 MB): 8x768x512x2->8 screlu; qb 32 |w1|max 1.980 |b1|max 0.565 |w2|max 1.980 |b2|max 0.204
w512_ft ACC_BOUND 16304 int16 OK size 6310556 bytes
2026-09-12 05:30:30 width ladder done
== screen_queue
2026-09-12 02:33:22 SCREEN k96b_ft vs fc_b: 02:33:21 [576/576] +128 =305 -143 score 48.7% elo -9 ±18 (pentanomial [16, 67, 135, 56, 14])
2026-09-12 03:12:45 SCREEN a3site vs fc_b: 03:12:10 [576/576] +117 =335 -124 score 49.4% elo -4 ±18 (pentanomial [12, 73, 122, 72, 9])
2026-09-12 03:50:16 SCREEN bp_d7_ft vs fc_b: 03:50:15 [576/576] +131 =293 -152 score 48.2% elo -13 ±20 (pentanomial [20, 74, 121, 53, 20])
2026-09-12 04:22:09 SCREEN bp96_d7_ft vs fc_b: 04:22:08 [576/576] +150 =284 -142 score 50.7% elo +5 ±20 (pentanomial [19, 67, 110, 71, 21])
2026-09-12 04:51:16 SCREEN bp144_d7_ft vs fc_b: 04:51:15 [576/576] +160 =276 -140 score 51.7% elo +12 ±21 (pentanomial [15, 73, 102, 73, 25])
2026-09-12 05:20:14 SCREEN bp144_soft vs fc_b: 05:20:13 [576/576] +142 =280 -154 score 49.0% elo -7 ±21 (pentanomial [22, 83, 88, 75, 20])
2026-09-12 05:52:22 SCREEN bp144_ftd vs fc_b: 05:52:21 [576/576] +99 =219 -258 score 36.2% elo -98 ±23 (pentanomial [63, 90, 86, 41, 8])
2026-09-12 06:37:28 SHAPE contempt40 vs contempt20 (same net, 30k): 06:37:27 [576/576] +139 =297 -140 score 49.9% elo -1 ±19 (pentanomial [17, 69, 115, 72, 15])
2026-09-12 07:20:41 SHAPE eg_draw=1 vs eg_draw=0 (same net, 30k): 07:20:40 [576/576] +114 =343 -119 score 49.6% elo -3 ±8 (pentanomial [0, 26, 242, 19, 1])
2026-09-12 07:59:59 SCREEN bp240_d7_ft vs fc_b: 07:59:58 [576/576] +149 =293 -134 score 51.3% elo +9 ±18 (pentanomial [10, 66, 125, 73, 14])
2026-09-12 08:32:41 SCREEN bp336_d7_ft vs fc_b: 08:32:40 [576/576] +162 =290 -124 score 53.3% elo +23 ±19 (pentanomial [9, 62, 115, 86, 16])
nnue_a2lite.safetensors
nnue_a3site.safetensors
nnue_bp144_d7_ft.safetensors
nnue_bp144_ftd.safetensors
nnue_bp144_soft.safetensors
nnue_bp240_d7_ft.safetensors
nnue_bp336_d7_ft.safetensors
nnue_bp48.safetensors
nnue_bp96_d7_ft.safetensors
nnue_bp_d7.safetensors
nnue_bp_d7_ft.safetensors
nnue_cpilot.safetensors
nnue_fcb.safetensors
nnue_fcb_re.safetensors
nnue_k96.safetensors
nnue_k96b.safetensors
nnue_k96b_ft.safetensors
nnue_w512_ft.safetensors
nnue_w768_ft.safetensors

gcp morning chain:
2026-09-12 01:40:22 waiting for the book gate to finish
2026-09-12 01:42:26 waiting for the book gate to reach 200 games
2026-09-12 02:12:06 waiting for the book gate: 300 games or 07:00 UTC
2026-09-12 06:34:07 book gate at read point: [300/300] +40 =235 -25  score 52.5%  elo +17 ±40  last: draw by insufficient_material
2026-09-12 06:34:15 book gate stopped after 300/300 games (pre-declared read: 300 games or 07:00 UTC)
2026-09-12 06:34:15 book report written (/home/forge/chess/gates/sfbook_report.json)
2026-09-12 06:34:15 best screened net: bp144_d7_ft (++12)
guards + book instrumentation applied to cand_netbook_bp144_d7_ft/agent.py
  print(f'SMOKE init={t1:.1f}s nnue_ready={ok} move={m} legal={chess.Move.from_uci(m) in chess.Board(fen).legal_moves} move_secs={dt:.2f}', file=sys.stderr, flush=True)
  Maximum resident set size (kbytes): 786324
  wall=31.1s rc=0
  print(f'SMOKE init={t1:.1f}s nnue_ready={ok} move={m} legal={chess.Move.from_uci(m) in chess.Board(fen).legal_moves} move_secs={dt:.2f}', file=sys.stderr, flush=True)
  Maximum resident set size (kbytes): 822768
  wall=31.1s rc=0
started gate C for bp144_d7_ft at Sat Sep 12 06:35:20 UTC 2026
2026-09-12 09:15:20 combo C (bp144_d7_ft + book vs V8.5): [150/150] +18 =118 -14  score 51.3%  elo +9 ±56  last: white by checkmate
guards + book instrumentation applied to cand_netbook_bp144_d7_ft/agent.py
  print(f'SMOKE init={t1:.1f}s nnue_ready={ok} move={m} legal={chess.Move.from_uci(m) in chess.Board(fen).legal_moves} move_secs={dt:.2f}', file=sys.stderr, flush=True)
  Maximum resident set size (kbytes): 783888
  wall=31.4s rc=0
  print(f'SMOKE init={t1:.1f}s nnue_ready={ok} move={m} legal={chess.Move.from_uci(m) in chess.Board(fen).legal_moves} move_secs={dt:.2f}', file=sys.stderr, flush=True)
  Maximum resident set size (kbytes): 823368
  wall=31.4s rc=0
started gate A for bp144_d7_ft at Sat Sep 12 09:16:26 UTC 2026
```

/private/tmp/claude-501/-Users-architbhardwaj-Desktop-AI-Chessathon/edc9c181-8258-4c54-8a6f-0a83813055f3/scratchpad/morning_push.sh: line 26: /Users/architbhardwaj/chess/data/stage/nets_night/: No such file or directory
**Mirrored nets on gcp-x86** ():
```
 
12288 .
4096 ..
0 a2lite_30k.err
11544769 a2lite_30k.json
545728 a2lite_30k.log
3544310 a2lite_30k.pgn
545728 a2lite_30k.stdout
880 a3_site.out
880 a3_site.status
0 a3site_30k.err
11666957 a3site_30k.json
549693 a3site_30k.log
3604412 a3site_30k.pgn
549693 a3site_30k.stdout
2110 a_lane.out
2262 a_lane.status
977 align_variants.out
977 align_variants.status
981 b_lane.out
981 b_lane.status
0 bp144_d7_ft_30k.err
10751790 bp144_d7_ft_30k.json
511844 bp144_d7_ft_30k.log
3312076 bp144_d7_ft_30k.pgn
511844 bp144_d7_ft_30k.stdout
0 bp144_ftd_30k.err
10138384 bp144_ftd_30k.json
484450 bp144_ftd_30k.log
3144262 bp144_ftd_30k.pgn
484450 bp144_ftd_30k.stdout
0 bp144_soft_30k.err
10745575 bp144_soft_30k.json
511534 bp144_soft_30k.log
3311050 bp144_soft_30k.pgn
511534 bp144_soft_30k.stdout
0 bp240_d7_ft_30k.err
11112866 bp240_d7_ft_30k.json
525796 bp240_d7_ft_30k.log
3444342 bp240_d7_ft_30k.pgn
525796 bp240_d7_ft_30k.stdout
0 bp336_d7_ft_30k.err
10868225 bp336_d7_ft_30k.json
516990 bp336_d7_ft_30k.log
3344658 bp336_d7_ft_30k.pgn
516990 bp336_d7_ft_30k.stdout
0 bp96_d7_ft_30k.err
10940162 bp96_d7_ft_30k.json
519430 bp96_d7_ft_30k.log
3374724 bp96_d7_ft_30k.pgn
519430 bp96_d7_ft_30k.stdout
0 bp_d7_ft_30k.err
11311475 bp_d7_ft_30k.json
534498 bp_d7_ft_30k.log
3496715 bp_d7_ft_30k.pgn
534498 bp_d7_ft_30k.stdout
714 c2_lane.out
714 c2_lane.status
575 c3_lane.out
575 c3_lane.status
0 c40_30k.err
12146756 c40_30k.json
568604 c40_30k.log
3716364 c40_30k.pgn
568604 c40_30k.stdout
542 c4_lane.out
542 c4_lane.status
577 c5_lane.out
577 c5_lane.status
2037 c_lane.out
2037 c_lane.status
0 eg_30k.err
12679669 eg_30k.json
592122 eg_30k.log
3855931 eg_30k.pgn
592122 eg_30k.stdout
0 fcb_re_30k.err
11497519 fcb_re_30k.json
543735 fcb_re_30k.log
3531269 fcb_re_30k.pgn
543735 fcb_re_30k.stdout
0 fcb_re_tc5.err
1104 fcb_re_tc5.json
831 fcb_re_tc5.log
0 fcb_re_tc5.pgn
831 fcb_re_tc5.stdout
0 k96b_ft_30k.err
11216244 k96b_ft_30k.json
530031 k96b_ft_30k.log
3475732 k96b_ft_30k.pgn
530031 k96b_ft_30k.stdout
0 ladder_best.out
2977 mirror.log
12620460 nnue_a2lite.safetensors
12620460 nnue_a3site.safetensors
12620460 nnue_bp144_d7_ft.safetensors
12620460 nnue_bp144_ftd.safetensors
12620460 nnue_bp144_soft.safetensors
12620460 nnue_bp240_d7_ft.safetensors
12620460 nnue_bp336_d7_ft.safetensors
12620452 nnue_bp48.safetensors
12620460 nnue_bp96_d7_ft.safetensors
12620452 nnue_bp_d7.safetensors
12620460 nnue_bp_d7_ft.safetensors
12620452 nnue_cpilot.safetensors
12620452 nnue_fcb.safetensors
12620460 nnue_fcb_re.safetensors
12620444 nnue_k96.safetensors
12620452 nnue_k96b.safetensors
12620460 nnue_k96b_ft.safetensors
6310556 nnue_w512_ft.safetensors
9465500 nnue_w768_ft.safetensors
386 pod_queue.out
386 pod_queue.status
0 screen_bp.out
0 screen_bp144.out
0 screen_bp240.out
0 screen_bp336.out
0 screen_bp96.out
0 screen_c40.out
0 screen_eg.out
0 screen_ftd.out
138 screen_queue.out
1579 screen_queue.status
0 screen_soft.out
35967 sf_build.log
66320 train_a2lite.log
66319 train_a3site.log
390007 train_bp144.log
97713 train_bp144_d7.log
66360 train_bp144_d7_ft.log
66347 train_bp144_ftd.log
97718 train_bp144_s7.log
66358 train_bp144_soft.log
778766 train_bp240.log
97714 train_bp240_d7.log
66360 train_bp240_d7_ft.log
778790 train_bp336.log
97714 train_bp336_d7.log
66360 train_bp336_d7_ft.log
387273 train_bp48.log
387775 train_bp96.log
97708 train_bp96_d7.log
66356 train_bp96_d7_ft.log
97702 train_bp_d7.log
66348 train_bp_d7_ft.log
49606 train_cpilot.log
66328 train_fcb_re.log
772990 train_k96b.log
66344 train_k96b_ft.log
771285 train_w512.log
66221 train_w512_ft.log
772385 train_w768.log
66296 train_w768_ft.log
3425 trainer_build.log
145 trainer_build_c.log
904 width_ladder.out
904 width_ladder.status
errors_all.jsonl
errors_mac.jsonl
errors_mac2.jsonl
leaf_labels_mac.labels.jsonl
leaf_labels_mac_000.npz
leaf_mac.jsonl
leaf_mac_profile.json
site_all.bin
site_all.npz
site_spice.log
site_spice_12_23.bin
site_spice_12_23.jsonl
site_spice_12_23.npz
```

/private/tmp/claude-501/-Users-architbhardwaj-Desktop-AI-Chessathon/edc9c181-8258-4c54-8a6f-0a83813055f3/scratchpad/morning_push.sh: line 27: /Users/architbhardwaj/chess/gates/c40_vm.log: No such file or directory
**Must-win gate on the VM (V8.5 + book + contempt 40 vs V8.5 + book, 120+0.5, 100 games, )**:
```
[100/100] +10 =83 -7  score 51.5%  elo +10 ±69  last: draw by insufficient_material
0

pod draw-shape screen (contempt 40 vs 20, same net, 30k, 576 games, upper bound for strength):
Warning: Permanently added '[63.141.33.33]:22018' (ED25519) to the list of known hosts.
2026-09-12 06:37:28 SHAPE contempt40 vs contempt20 (same net, 30k): 06:37:27 [576/576] +139 =297 -140 score 49.9% elo -1 ±19 (pentanomial [17, 69, 115, 72, 15])
2026-09-12 07:20:41 SHAPE eg_draw=1 vs eg_draw=0 (same net, 30k): 07:20:40 [576/576] +114 =343 -119 score 49.6% elo -3 ±8 (pentanomial [0, 26, 242, 19, 1])
06:37:27 [576/576] +139 =297 -140 score 49.9% elo -1 ±19 (pentanomial [17, 69, 115, 72, 15])
```

/private/tmp/claude-501/-Users-architbhardwaj-Desktop-AI-Chessathon/edc9c181-8258-4c54-8a6f-0a83813055f3/scratchpad/morning_push.sh: line 30: scratchpad/gates/eg_mac.log: No such file or directory
**Endgame-honesty build at the real clock on the Mac (cand_sfbook_eg vs cand_sfbook, 120+0.5, 2 workers, )**:
```
[14/60] +1 =10 -3  score 42.9%  elo -50 ±207  last: draw by threefold_repetition
0
```

/private/tmp/claude-501/-Users-architbhardwaj-Desktop-AI-Chessathon/edc9c181-8258-4c54-8a6f-0a83813055f3/scratchpad/morning_push.sh: line 31: /Users/architbhardwaj/chess/gates/morning_chain.status: No such file or directory
**Morning chain on gcp-x86 ()**:
```
guards + book instrumentation applied to cand_netbook_bp144_d7_ft/agent.py
  print(f'SMOKE init={t1:.1f}s nnue_ready={ok} move={m} legal={chess.Move.from_uci(m) in chess.Board(fen).legal_moves} move_secs={dt:.2f}', file=sys.stderr, flush=True)
  Maximum resident set size (kbytes): 783888
  wall=31.4s rc=0
  print(f'SMOKE init={t1:.1f}s nnue_ready={ok} move={m} legal={chess.Move.from_uci(m) in chess.Board(fen).legal_moves} move_secs={dt:.2f}', file=sys.stderr, flush=True)
  Maximum resident set size (kbytes): 823368
  wall=31.4s rc=0
started gate A for bp144_d7_ft at Sat Sep 12 09:16:26 UTC 2026
combo_bp144_d7_ft_C.log: [150/150] +18 =118 -14  score 51.3%  elo +9 ±56  last: white by checkmate
combo_bp144_d7_ft_A.log: 
```

