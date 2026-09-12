# GrigoryMorning — handover, 12 September 2026, written at __NOW__

Everything below was produced overnight by the engine/packaging side. Nothing has been uploaded to the
platform. V8.5 (`bini_astra_v5_noc2b`, `submission_V8.5.zip`, sha256 `26828c24…`) is untouched and
remains the control and the fallback. Full evidence: `FinalsDay/Finals Night Cause Table.md` and
`FinalsDay/night_evidence/` (every script, log and manifest named here lives there or at the box paths given).

## LAST UPLOAD (13:45) — V18: V17 + 25 % more middlegame time + draw-when-losing threshold at −150

`submission_V18_bp336_book_c80eg_r50_nocorr_dcp150_mb125_init_fastcompile2.zip`, sha256 **6ff2ee09…**. Battery clean;
constants verified in the zip. If its validation passes it is the frozen build; otherwise **V17 (23d02925…, validated:
ready 23.8–23.9 s, first move 2.7–4.5 s)** plays. Correction-history screen final: corr off vs on −13 ±26 at fixed
nodes — accepted against the plateau/draw-loop harm measured at the real clock (§29).

## FINAL CALL (13:36) — V17: V16 with the correction history switched off

`submission_V17_bp336_book_c80eg_r50_nocorr_init_fastcompile2.zip`, sha256 **23d02925…** (Cause Table §29). Why: the
correction history saturates at ±64 cp whenever nothing irreversible happens, learns the repetition draw score as if it
were an evaluation error, and produces the flat −40/−60/−70/−80/+95 plateaus behind every draw we analysed today and
the round-17 loss (king walk chosen among moves that all read −70). Switching it off (pre-existing runtime flag) removes
the mechanism; battery 32/32; a 288-game fixed-node screen (off vs on at contempt 80) runs as the safety check. V16
(b237926f…, validated on the platform: ready 23.7–23.9 s, first move 4.6–5.7 s) is the fallback if that screen shows a
disaster before the freeze.

## FINAL UPLOAD (13:27) — V16: bp336 + book + contempt 80 + endgame honesty + fifty-move scaling + init fixes

`submission_V16_bp336_book_c80eg_r50_init_fastcompile2.zip`, sha256 **b237926f…** (Cause Table §28). Fifty-move
scaling screen +7 ±20 at 520/576 (behaviour otherwise identical to V15); contempt 80 on Archit's "draw only when
genuinely losing" directive (a −80 read ≈ −0.5 pawn true; draw_behind −100 kept). Battery 32/32 on the exact zip.
Fallbacks: V15 (e56c96b0…), V14 (c859f498…). After 14:00: `stop_all.sh`, terminate the three RunPod pods.

## FINAL STATE (13:15) — V15 live; V16 (fifty-move scaling) decided by its screen at 13:25

**Autopsy and the road to a winning engine: Cause Table §27** — flat/cautious evaluation in level positions and
optimism when ahead (the net), correction-history plateaus (the search), a draw policy that sat where the pessimism
bites (fixed), speed, and self-play-only measurement. The next-event programme, in Elo-per-day order: decision-grade
labels + plan-ranking objective + calibration; search tuning at the real clock (correction cap, fifty-move scaling,
SPSA on the pod fleet); numba-only speed work; 3–4-piece Syzygy and a deeper book; an opponent panel tracking decisive
rate. All tooling for it is in `FinalsDay/night_evidence/`.


Live build: **V15** `submission_V15_bp336_book_c70eg_init_fastcompile2.zip` (e56c96b0…). Net read at 13:09: bp336 vs
V8.5's net, **358 real-clock games, +60 =252 −46, 101 pairs, pair Elo +13.8 [−9.6, +37.2]**, zero failures → bp336 stays.
Practice round 14 (V14) drew by fifty moves after 40 moves at a flat +95 (Cause Table §26: the correction-history plateau
in a rook+bishop ending, which also penalises progress moves). **V16** = V15 + Stockfish's fifty-move scaling of the
static evaluation (`patch_rule50.py`, switch `BINI_RULE50`): `submission_V16_bp336_book_c70eg_r50_init_fastcompile2.zip`
(2a409da8…), battery 32/32, scaling verified (−88 → −49 at clock 90). It replaces V15 only if the 576-game on-vs-off
screen on pod 3 is ≥ −5 and its platform validation is clean, uploaded by 13:40; otherwise V15 is the frozen build.
After 14:00: `stop_all.sh`, terminate the three RunPod pods.

## THE FROZEN BUILD (deployed 12:55) — PrometheusBuild V15

`submission_V15_bp336_book_c70eg_init_fastcompile2.zip`, sha256 **e56c96b0…** (full hash and the component-by-component
evidence in Cause Table §25). bp336 net + Stockfish book + contempt 70 (draw_behind −100) + endgame honesty + 21 s join +
fast compile + first-move fix. Platform: ready line 22–24 s in every upload; V14 (same but contempt 60) won both of its
practice games. Net comparison at the real clock: bp336 +15 [−12, +43] over 313 games vs V8.5's net in identical
packages. Fallbacks (validated): V14 bp336 c60 (c859f498…), V14/V13 with the V8.5 net, `submission_V9_book.zip`,
`submission_V8.5.zip`. **After 14:00: stop the arenas and terminate the three RunPod pods** (`stop_all.sh`).

## FINALS DAY — constraint, decisions and the plan to 14:00 (written 11:15, Archit + Claude)

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

**V10 on the platform (validation log 11:20):** ready in 22.3 s of 30 in both smoke games; the book fired; but the
first engine move ran only 4,096 nodes at depth 6 (`m1 d6 … 4096n 18103ms`): after the compile wait the hard time cap
was charged for the wait a second time and collapsed to 8 ms. **Fixed in V11** (`patch_firstmove.py`, one variable;
engine files unchanged): validated on the pod, move one is now a normal depth-16 search after the wait. **V11 is the
build to have on the platform**: `submission_V11_v85_book_c40eg_init.zip` (sha256 95897ef6…); the bp336 alternative is
`submission_V11_bp336_book_c40eg_init.zip` = `PrometheusBuild.zip` (0cd05c03…). The V10 zips remain only as history.

**V12/V13 (12:15) — the compile itself shortened, behaviour-identical (Cause Table §23):** numba was compiling a
separate specialisation per constant argument (60 of 109 were literal duplicates of ten helpers) — explicit signatures
fix that (`patch_sigs.py`); the never-executed 193-line classical evaluation is stubbed (`patch_hce.py`). Verified on the
pod: compile −28 %, fixed-node search identical on 12 positions, battery clean. **Current ship files:**
`submission_V13_v85_book_c40eg_init_fastcompile2.zip` (V8.5 net, sha256 6d546cfd…) and
`submission_V13_bp336_book_c40eg_init_fastcompile2.zip` = `PrometheusBuild.zip` (bp336 net, f03394d6…). Gate results
complete: book +17.4 (300), contempt 40 +10.4 (100), endgame fix +3.5 (100), all zero failures.

**V14 (12:30, Cause Table §24) — contempt 40 → 60.** Practice rounds 6–9 on the platform: two draws by repetition
taken at a −40 read in positions Stockfish scores 0.00, one fortress draw from a worse position (the draw_behind rule
working), one grind loss to Rataturing. Contempt 60 with draw_behind at −100 unchanged. **Current ship files:**
`submission_V14_v85_book_c60eg_init_fastcompile2.zip` (V8.5 net, 31ca0e4e…) and
`submission_V14_bp336_book_c60eg_init_fastcompile2.zip` = `PrometheusBuild.zip` (bp336 net, c859f498…). The net
comparison (bp336 vs V8.5 net, five boxes) is read at 13:25 with the corrected pair-wise merger.

**Packages (gcp-x86 `~/chess/packages/` and copied to the repo root; sha256 in `MANIFEST.txt`; same flat layout as `submission_V8.5.zip`):**
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
3. **13:20 decision, pre-declared (revised 11:35):** the comparison is **`ship_bp336` vs `ship_v85`** — identical
   packages except the net, both with the 21 s join, so it isolates the net and both sides pass a 30 s init (bare V8.5
   cannot, and "vs bare V8.5" would be confounded by the book's own +17). Runs on gcp-x86 (150, seed 3), pod (120, seed
   11), VM (100 after its endgame gate, seed 7); combine with `merge_gate.py <stats.jsonl>...`. **Ship bp336 if pair Elo
   ≥ +5 with lower bound ≥ −10 over ≥ 200 games**; otherwise the V10 V8.5-net build already on the platform stays. Stop
   reading gates at 13:20.
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

__STATUS__
