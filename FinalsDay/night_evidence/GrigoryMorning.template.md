# GrigoryMorning — handover, 12 September 2026, written at __NOW__

Everything below was produced overnight by the engine/packaging side. Nothing has been uploaded to the
platform. V8.5 (`bini_astra_v5_noc2b`, `submission_V8.5.zip`, sha256 `26828c24…`) is untouched and
remains the control and the fallback. Full evidence: `FinalsDay/Finals Night Cause Table.md` and
`FinalsDay/night_evidence/` (every script, log and manifest named here lives there or at the box paths given).

## 0. Read this first (five lines)

1. **Stockfish opening book** built for the 1,226 curated roots, guards verified, exact package frozen and
   smoked, **300-game real-clock gate running on `gcp-x86`** (status at push time in §6). Report command:
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

## 5. Morning sequence (recommended)

1. Read §6, then run the gate report; apply the decision rule with Archit.
2. Your A1 with the resolved schedule (§0.3), against fc_b, on the staged corpus; then A2/A6 with N1 if the fleet
   exists; the leaf pilot and error set as ≤ 5 % spice in A3-style arms only.
3. Any net: `net_gate.sh` first; if it passes the screen and the ladder, `combo_gate.sh … C` is the shipping check.
4. On the brief: `FinalsDay/Finals Night Cause Table.md` §5 (hard-coded assumptions) and §8 (runbook).

## 6. Live status at push time (auto-filled)

__STATUS__
