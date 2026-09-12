# Finals Night — cause table and candidate record (11 September 2026, from 19:00)

Written while the gates run. Every number below comes from a file in `FinalsDay/night_evidence/`
(scripts included). Gate rows marked *pending* are filled in as results complete.

## 1. Baseline identity (unchanged)

| Item | Value |
|---|---|
| Live build | V8.5 = `bini_astra_v5_noc2b`, `submission_V8.5.zip`, sha256 `26828c24…` |
| Swiss | 6th of 334, 10/13, 8–4–1, tied on points with 2nd; Buchholz 112.5 |
| Knockout rule | best of 2, one game per colour; tie → better Swiss standing (beats us only vs JBG fam, Miskeen, Lightning Tree, Gladiator, Rataturing) |
| Infrastructure 19:00 | Vast GPU box: connection refused (gone). Oracle VM (4 ARM) and GCP `gcp-x86` (8 vCPU) alive, generators paused for gates |
| Consequence | No pretrain workstream tonight. One search candidate, validated or not shipped. |

Own-move index in the logs is not the PGN move number: R113 fullmove = m+5, R114 = m+7, R108 = m+8.

## 2. The three decision targets

All reproductions: deployed build, real start FEN, complete game history, fixed node budgets,
cold transposition table, Mac (node counts are machine-independent).

### R113 / 39.Rc2 (Qe8+ wins) — reproduced, cause identified, candidate found

| Budget (nodes) | Baseline move | Score | Depth |
|---:|---|---:|---:|
| 0.5M | Rc2 | +125 | 16 |
| 1.0M | Rc2 | +144 | 19 |
| **2.646M (the game)** | **Rc2** | **+160** | **21** |
| 5.0M | Rc2 (TT PV already Qe8+ Kh7 Nd7) | +160 | 21 |
| 10M | **Qe8+** | +902 | 23 |
| 20M / 40M | Qe8+ | +1033 / +1044 | 25 / 27 |

The live log shows +157 at depth 19 after 2.646M nodes: the cold reproduction matches. Game history
makes no difference (no-history control: Rc2 +160). In-game speed was ~500 knps, so 10M nodes is
~20 s against the 5.3 s spent; it had 44 s on the clock.

From the position after 39.Qe8+ Kh7 the engine finds 40.Nd7 at +814 in 1M nodes, so the win is
visible once the check is *searched*. Root-move ranking by independent 600k-node child searches
puts Qe8+ 11th of 35 (scored as a draw): the combination (Qe8+ Kh7 Nd7 Rb8 Qxb8 Qb5 **Nf8+** Kg8
Qxb5) contains checking quiet moves several plies deep that the search prunes.

Code facts (`bini_search.py`): quiet moves are late-move-pruned, futility-pruned and history-pruned
*before* the move is made, so `gives_check` is unknown there; move ordering gives a checking quiet
move no priority (history only); the check extension applies only at depth ≤ 3.

Single-toggle ablations at 2.646M nodes: `cont_off` → Qe8+ +908; `corr_off` → Qe8+ +817;
`probcut_on` → Qe8+ +777; `seep_off`, `qs_checks_on`, `nmp_off`, `improving_on`, `contempt_0` → still
Rc2. So the position sits near a threshold and several tree-shape changes cross it; the candidate
below is the one with a stated mechanism, and it crosses at depth 18 rather than 22–23.

Reconstructed-warm replay (every earlier own move searched at its logged node count): plays Qe8+ at
1× nodes, but only 22 of 33 earlier moves agreed with the game, so the reconstruction is not
faithful and says nothing about the live state.

### R114 / 40…Qh6 (hangs the h5 rook) — not reproducible cold

Baseline and candidate, 0.7M / 2.1M / 5M nodes: Qh4 (+105…+121) or Kd8; never Qh6. The warm
replay (19/32 agreement) also plays Qh4. The live move came from state we cannot rebuild. No
tonight target; it belongs to the TT/warm-state investigation.

### R108 / 39.g5 (fxe3 holds) — reproduced, evaluation not search

Baseline plays g5 at −20 (draw utility) at 0.87M, 2.6M and 8M nodes (depths 17/22/27); candidate
the same. Child searches at 2M nodes, engine's view: fxe3 −43, g5 +20, Rh7 −765, Bd8 −933. Static
evaluation immediately after g5 is −514 (a rook down) but the search believes the f-pawn regains it
(g5 e5+ Ke3 Bd5 f7 Kxf7 …). The reference says g5 −1.96, fxe3 0.00. This is a misjudged ending
line, not a pruning miss: no search-only fix tonight.

## 3. Candidate CHK

One condition: a quiet move that gives **direct** check (destination in the checking set of its
piece, the same masks the quiescence quiet-check filter already computes) is exempt from late-move
pruning, futility pruning and history pruning. SEE pruning, reductions, extensions, evaluation,
book and time management are untouched. Switch `BINI_CHK_EXEMPT` (0 reproduces baseline search
exactly). Diff: `night_evidence/candidate_chk/`.

| Check | Result |
|---|---|
| R113 at 2.646M nodes | **Qe8+ +851, depth 18** (baseline: Rc2 +160) |
| R113 at 1M / 5M | Ne4 +117 (TT PV already Qe8+) / Qe8+ +882 |
| R114, R108 | unchanged (Qh4; g5 −20) |
| Speed, VM ARM, NNUE on, 5 positions × 4 s | 191.4 → 187.0 knps (≈ −2%) |
| Astra correctness suites (suite, repro, v2, terminal audit, qs repetition, stalemate) | 0 failures |
| Timed regressions, Mac, 2–2.5 s per position, one run each | tactics 38/40 (baseline 39/40); blunders 11/12 (baseline 12/12, the repeat is Qb3 in a −641 position); search 10/11 (baseline 9/11). Fixed-node recheck of the three differing positions (0.5M/1M/3M nodes): baseline finds all three at 0.5M; the candidate finds them only at 3M (f8g7 misses at 1M; d6c5 and e3e2 miss at 0.5M and 1M). The exemption reshapes the tree rather than adding a free gain — aggregate gates decide |
| 30k-node screen, on vs off, 576 games, GCP (`gates/chk_screen30k`) | **+5 ±18** (+136 =312 −128; pentanomial [11,65,135,59,18]). A fixed-node screen is an upper bound: with the ~2% speed cost this reads as neutral |
| Real wrapper 10+0.1 vs exact V8.5, VM (`gates/chk_vm`) | stopped at 163/400: −6 ±54 (37–86–40), no fallbacks. Abandoned as low value once the screen read neutral; the VM went to the Stockfish book build |
| Real wrapper 120+0.5 vs exact V8.5, 400 games, GCP (`gates/chk_real`) | running from 19:52 BST, 6 workers, about 6 h; pre-emptible if a new net needs the box |
| Exact-package cold start, quiet x86 (GCP), production init, no env overrides | V8.5: init 27.9 s, nnue on, legal move, peak RSS 850 MB. Candidate: 28.5 s, nnue on, legal, 849 MB. Both zips 14.05 MB unzipped |

Ship rule: non-inferior at 120+0.5 (zero fallbacks, loss rate not worse), no regression failures,
exact-package smoke under the 90 s init on x86. Otherwise V8.5 goes to London unchanged.

## 4. Open questions only the team can answer

1. The invitation text: does it allow a new upload tomorrow, by what time, and under what limits?
   It is referenced in the plans but not in the repo.
2. What time does the final start, and when does the on-day window close?
3. Who is attending in person (seat verification), and is the presentation deck needed on paper?

## 5. Finals adaptation checklist — what is hard-coded to 120 s + 0.5 s

If tomorrow's brief changes the clock, init budget or memory, these are the exact places to edit
and re-smoke; the platform passes no environment, so env knobs are not a substitute.

| Assumption | Where | What breaks if the brief differs |
|---|---|---|
| Increment is 0.5 s | `agent.py` `INCREMENT_MS = 500`; used in `_budget` (`0.6 * INCREMENT_MS`, emergency branch) | A smaller increment makes every move overspend; a larger one wastes it |
| Base is 120 s | `agent.py` `_budget` absolute thresholds `< 4000`, `< 30000`, `< 10000` ms and `hard ≤ 0.2 * time_left` | At a 30–60 s base the "low clock" caps bind from move one and the engine plays shallow all game |
| Horizon | `mtg = max(18, 34 - 0.4 * own_move)` | Tuned for 60–100-move games at this clock |
| Init budget 90 s | `agent.py` `COMPILE_JOIN_S = 75` (`BINI_JOIN_S`), observed init 37–60 s on the platform | A tighter init budget needs the join lowered and the fallback path re-smoked; a 60 s budget is marginal (R110 took 60.3 s) |
| Memory 2 GB | `bini_search.py` `TT_BITS = 24` (two 128 MB arrays; `Engine(tt_bits=…)` is ignored, only the import-time constant counts) | A 1 GB limit needs `TT_BITS = 23`; a 512 MB limit `22`, then re-time |
| Book window | `agent.py` own-move `< 12` **and now** `board.fullmove_number <= 20` (candidate only; inert with the 8-ply book) | A different opening/endgame rule needs the guard changed |
| One core | `agent.py` single-threaded search; compile in a thread only during init | Nothing to change unless threads are offered |
| Candidate switch | `bini_engine.py` `BINI_CHK_EXEMPT` default 1 (candidate) | Setting 0 in the file restores baseline search exactly |

Rehearsal to run on the x86 box before any upload: extract the exact zip into an empty directory,
import `agent` with the production join (no `BINI_JOIN_S`), require the "ready … nnue=on" line,
play two wrapper games (one per colour) from curated starts, record init seconds and peak RSS.

## 6. Finals kit — clock refactor (ready, proven identical)

`night_evidence/patch_clock.py <build_dir> [BASE_MS] [INCREMENT_MS]` rewrites `agent.py` so the
three absolute low-clock thresholds are fractions of `BASE_MS` (÷30, ÷4, ÷12). At 120000/500 it is
behaviour-identical: `test_budget_identity.py` compares `_budget` on 703,950 (clock, move) grid
points including every threshold edge and reports 0 differences. For a revealed clock of, say,
60 s + 0.3 s the whole change is one command, then the usual smoke and a short timed gate.

## 7. Speed lever (pretrain plan §9) — closed with evidence

Two exact rewrites of the NNUE output layer (`night_evidence/patch_vec.py`: 1-D views, branch-free
clamp, explicit 32→64 widening products; and an int32-per-term form) were benchmarked in situ:

| Machine | shipped kernel | rewrite 1 | rewrite 2 | mismatches / 600 positions |
|---|---:|---:|---:|---:|
| GCP x86 (Sapphire Rapids, AVX-512 capable) | 471 ns | 469 ns | 475 ns | 0 |
| Mac M2 | 1680 ns | 1675 ns | 1703 ns | 0 |

Fixed-depth searches (5 positions, depth 13) give identical node counts for all three builds
(1,574,170) at 428 / 422 / 416 knps. The generated assembly on x86 shows the shipped `nnue_eval`
already uses 256-bit AVX2 (127 ymm references, `vpmuldq`/`vpaddq`), and `nnue_after_make` and
`nnue_refresh_persp` are vectorised too (1007 and 817 ymm references). On the Mac everything is
scalar, which is where the "numba emits scalar code" belief came from. The eval is ~470 ns of a
~2,000 ns node on x86 (~25 %), so even a perfect kernel is worth well under 10 Elo; 512-bit lanes
are not selectable from inside the zip. Verdict: no speed candidate; 1536/2048 remain too slow.

## 8. On-day runbook (docs: "refine your agent under a newly revealed constraint, freeze it, compete")

Boxes: `gcp-x86` = the only x86 test machine (8 vCPU; matches the platform's instruction set);
`priorcrypto-vm` = 4 ARM cores, timing not representative; Grigory's rented fleet if it exists.
Everything below runs from `~/chess` on `gcp-x86`; every script already exists there.

1. **Read the brief; write the constraint down verbatim.** Extract: clock and increment, init
   budget, memory, package size, book/tablebase rule, interface change, freeze time.
2. **Smoke the unchanged shipping candidate under the new limits first** (2 min):
   `~/chess/venv/bin/python pkg_smoke.py <build_dir> <tag>` — init seconds, NNUE on, legal move, peak RSS.
   Only then decide whether anything must change.
3. **Change only the affected subsystem, one command each:**
   - clock/increment: `python patch_clock.py <build_dir> <BASE_MS> <INC_MS>` (proven identical at 120/0.5)
   - memory: edit `TT_BITS` in `bini_search.py` (24 = 256 MB tables, 23 = 128 MB, 22 = 64 MB); re-smoke for RSS
   - package size: drop `book.json` (wrapper tolerates its absence) before dropping net width
   - init budget: set `COMPILE_JOIN_S` in `agent.py` to budget − 8 s; compile is ~28 s on the platform's class of CPU
   - book rules: the candidate wrapper already has the fullmove ≤ 20 guard
   - new net: `bash net_gate.sh <net.safetensors> <tag> [screen_games] [tc5_games] [real_games]`
4. **Gate at the actual clock, not a proxy:** `bash chk_real.sh`-style arena (`<build>/tools/arena_par.py`,
   `--base-ms/--inc-ms` set to the revealed values) for as many games as the window allows; read only
   completed results; zero fallback lines in both arms.
5. **Package with the frozen-layout check:** `bash astra_tests/package_astra.sh <build_dir> <out.zip>`
   (root layout, 50 MB, per-file hashes vs the shipped V8.5). Record the sha256 in this file.
6. **Freeze with 60–90 minutes to spare** if the window allows; otherwise a proportionate block.
   Fallback at every step: `submission_V8.5.zip` (sha256 `26828c24…`), byte-identical to the Swiss build.

## 9. Stockfish opening book (started 21:35) — the unused legal lever

The rules allow a shipped table that answers the opening (move number ≤ 20) "whatever produced
it". Our book was our own engine's 8-ply analysis at 60 s per root. `night_evidence/sf_book.py`
builds, for each of the 1,226 curated roots and for each colour we might be, a tree where our
plies continue with Stockfish 19's best move and the opponent's plies with its top three replies
within 60 cp, six plies deep, 1.2M nodes per analysis (depth ≈ 19–21), lines beyond ±200 cp not
extended, positions with a legal en-passant capture or beyond fullmove 20 not stored. Output is the
wrapper's own `book.json` format, so the candidate is exactly V8.5 plus a new book file.
Build runs sharded on the Mac (3 workers), GCP (6) and the VM (4); merge with `merge_book.py`;
then package smoke and a 120+0.5 real-wrapper gate against V8.5 as shipped.

Preflight for the pretrain plan (GCP, no GPU): determinism gate 16 games mirrored, pentanomial
central; k96 checkpoint re-export tensor-identical to the stored net; fc_b-vs-k96 instrument gate
running; clean d10 corpus building. Export-parity unit test needs its `tools` path fixed (import
error), not a parity failure.

Preflight results (GCP, 21:15–21:45): determinism 16 mirrored games, pentanomial central;
k96 checkpoint re-export tensor-identical to `nnue_k96.safetensors`; **instrument fc_b vs k96
at 30k nodes, 576 games: +27 ±19** (plan expects ≈ +29 ±22, so the gate instrument on this box is
calibrated); **clean d10 corpus built: `~/chess/data/stage/clean_d10_shuf.bin`, 35,458,988 rows,
|cp|>800 = 3.68 %, quiet 78.3 %, depth 10, result column all zero** (so no WDL term on this corpus,
as the plan already notes). The export-parity unit test failed only on an import path.

### Book candidate wrapper: guards and instrumentation (verified 00:20)

`night_evidence/patch_guards.py` changes only the book branch of `agent.py`: the book is consulted
only when fullmove ≤ 20 and no en-passant capture is legal (the key omits en passant); each book
move logs the search budget it saved; one `bookexit` line records hits, saved ms, exit fullmove,
clock and FEN. `test_budget_identity.py` on the patched file: 0 differences over 703,950 points.
Functional test (`wrapper_guard_functional_test.log`): two book hits logged with budgets (7.6 s saved),
exit line correct, a booked position with a legal en-passant capture is searched instead (d2d4, not
the book's e5f6), a booked position at fullmove 25 is searched. The arena copy in `arena_par_stats.py`
writes one JSON record per game (colour, start FEN, result, termination, full stderr), so hits,
exit positions, time saved, fallbacks and timeouts are recorded next to the results by
`book_gate_report.py`, which also computes pair-level (colour-paired) Elo and the pentanomial.

Unused-clock check for the time-allocation track (Overnight Plan §3): every Swiss game that ended
with 40–64 s unused was a short win (38–50 moves); every long game ended with 7–12 s. The unused
clock is decided games, not missed opportunities. Track closed.

## 10. Search-leaf corpus (Overnight Plan avenue 1) — started 01:05

`night_evidence/patch_dump.py` makes a diagnostic copy of the engine that records a sample of the
positions the search hands to the network (interior static evaluations and quiescence stand-pats)
into a preallocated buffer: 64 piece nibbles, packed state, raw network score; six int64 words per
position, no Python in the hot path, search behaviour unchanged. `leaf_dump.py` runs fixed-node
searches (2M nodes) from each curated root and from two plies along the book line, decodes to FEN,
and writes JSONL with the engine's own score. Test on 2 roots (`leaf_test.log`): 1,750 positions,
0 invalid, 869 quiescence / 881 interior, plies 3–22.

First comparison with the training corpus (`leaf_profile.py` vs a clean d10 shard): the search's
positions near the opening are dense (92 % have ≥ 28 pieces) while the corpus has 27 % at ≥ 28
pieces and most of its mass at 12–24; median |score| 75 vs 61. That is the mismatch the plan's
avenue 1 predicts. The full dump (all 1,226 roots, Mac + VM) gives the real profile; a stratified
subset labelled at depth 12 is the fine-tune ingredient for Grigory's lane.

## 11. Decision-error mining (Overnight Plan avenues 2 and 4 as data) — tool validated 01:40

`night_evidence/mine_errors.py` walks our own game records (1,376 self-play gate games on disk, every
move ours) and keeps each position where the move played scores ≥ 100 cp below Stockfish's best at
depth 14, with both moves and both scores, for deep relabelling of the two continuations. Pilot on 20
games (`errors_pilot.jsonl`): 35 errors, 1.8 per game, 27 in the 100–200 cp band, 5 above 500 cp;
8 minutes for 20 games on two Mac workers, so the full set needs the rented box (minutes on 192 cores,
nine hours here). `label_leaf.py` labels leaf-corpus positions at depth 12 into the trainer's npz
convention with the engine's own score kept for resolution analysis.

## 12. Overnight automation (00:40) — what runs without anyone watching

| Job | Where | Trigger | Output |
|---|---|---|---|
| Book main shard (568 roots, 6 plies) | GCP, 6 workers | running | `bookbuild/sfbook_gcp.jsonl` |
| Mop-up of the Mac and VM residues at 4 plies, deterministic merge over the old book, audit, guards, manifest, smoke, **300-game 120+0.5 gate** | GCP `finish_book.sh` → `book_gate.sh` | when the main shard finishes | `gates/sfbook_real.{log,pgn,stats.jsonl}`, `gates/sfbook_manifest.txt`, `cand_sfbook/` |
| Leaf dump, half the roots | Mac, 4 workers | running | `out/leaf_mac.jsonl` (≈1.5 M positions) |
| Leaf dump, other half | VM, 4 workers | when the VM's book shard ends (or is stopped once GCP takes its residues) | `bookbuild/leaf_vm.jsonl` |
| Profile → stage to GCP → depth-12 labelled pilot (100k, stratified) ∥ error mining (150 games) | Mac `mac_night_chain.sh` | after the Mac leaf dump | `leaf_labels_mac_*.npz`, `errors_mac.jsonl`, `leaf_mac_profile.json`, all copied to `gcp-x86:~/chess/data/stage/leaf/` |
| Error mining (80 games) | VM `vm_night_chain.sh` | after the VM leaf dump | `errors_vm.jsonl` |
| Net-vs-Stockfish resolution probe on 400 real games | Mac | running | `resolution_probe.json` |
| **04:50 push**: `GrigoryMorning.md` assembled from the template + live status, small artefacts into this folder, commit, pull --rebase, push (fallback branch `night/finals-evidence`) | Mac `morning_push.sh` | 04:50 | `GrigoryMorning.md` at the repo root |

Nothing here uploads to the platform. V8.5 is untouched.

## 13. Where the evaluation weakness actually is (resolution probe, 01:20)

`night_evidence/resolution_probe.py`: 400 site games (Stockfish 16 depth 16 labels, White view), 34,600
non-check positions, our raw network score vs the label. Output `resolution_probe.json`.

| Pieces on board | positions | slope net-on-SF | mean abs error |
|---|---:|---:|---:|
| 30–32 | 3,638 | 0.78 | 38 |
| 24–29 | 7,737 | 0.97 | 88 |
| 18–23 | 7,593 | 0.87 | 126 |
| 12–17 | 7,334 | 0.58 | 170 |
| 6–11 | 6,782 | 0.28 | 451 |

By label band: 150–299 cp slope 0.87 (MAE 105); 300–599 slope 0.87 (MAE 144); 600–999 slope 1.03;
1000+ (mostly decided endgames) slope 0.25. "Resolution failures" (|SF| ≥ 300 read as |net| < 120):
519 of 11,649 = 4.5 %, of which 508 have ≤ 23 pieces and 7 have ≥ 30.

Reading: the net is close to Stockfish in full-board positions; the compression is an endgame and
late-middlegame phenomenon (≤ 23 pieces). Part of it is label depth (the net predicts depth-7 scores;
deeper search resolves endgames), so the fix is deeper labels concentrated on 12–23 pieces with
|SF| 150–600, not "sharp middlegames" in general. This is the targeting for the N2/spice arms. It also
matches R108 (12 pieces) and the earlier V3-era loss pattern. Caveat: static score vs depth-16 search
score; the per-piece-count trend is robust to that, the absolute MAEs are not.

## 14. Ready-to-train assets aimed at the weak band (01:30)

- `site_spice.py`: the site's Stockfish-16 depth-16 labels over 6,715 archived games, filtered to 12–23
  pieces and |cp| 150–600, deduplicated, trainer npz convention (`site_spice_12_23.npz` + `.jsonl`, staged to
  `gcp-x86:~/chess/data/stage/leaf/`). Deeper than fc_b's depth-7 labels, in-distribution, targeted.
- `endgame_roots.py`: 1,000 endgame-ish positions (12–23 pieces, move ≥ 25) from our own self-play games;
  the VM's leaf dump now samples search leaves from these (`leaf_vm.jsonl`) instead of opening roots.
- `search_resolution.py`: does the compression survive search? 600 endgame positions, 300k-node searches
  vs the depth-16 label (`search_resolution.json`).

### Does the compression survive search? (`search_resolution.json`, 01:35)

600 real positions with 12–23 pieces and |SF16 d16| in 150–600, our engine at 300k nodes (depth ≈ 14):

| Pieces | static slope / MAE / read as <120 cp | search slope / MAE / read as <120 cp |
|---|---|---|
| 12–14 | 1.11 / 155 / 4.0 % | 1.38 / 169 / 1.3 % |
| 15–17 | 0.98 / 132 / 8.7 % | 1.35 / 143 / 0.8 % |
| 18–20 | 1.02 / 174 / 8.3 % | 1.39 / 164 / 0.6 % |
| 21–23 | 1.01 / 126 / 9.0 % | 1.30 / 115 / 0.6 % |

Inside the playable band the static evaluation is unbiased on average and noisy; the search removes
most of the "read as near-equal" cases (4–9 % → ~1 %). The steep low-piece-count slopes in §13 come from
decided endgames (|SF| ≥ 600, net saturating near 900 vs labels near 3000), which rarely change results.
Reading for the evaluation lane: the weakness in play is per-position noise (MAE ≈ 150 cp) and a few
individual misjudgements, not a systematic bias; broad deeper-label continuation (noise reduction) is the
main lever, with the 12–23-piece spice kept ≤ 5 %. Caveat: site labels are Stockfish 16, the training
labels Stockfish 19; their score scales differ, so slopes are relative evidence, not calibration errors.

## 15. Incident log (so nobody trusts a number that was affected)

- 01:40 **Shard-sync clobbering.** The loop that mirrored the Mac/VM book shards to GCP every 10 minutes
  overwrote the same files the GCP mop-up appended to, so the four-ply entries for the Mac-residue roots were
  lost and part of the VM-residue mop-up. Fixed: loop killed, original finisher stopped before merging,
  `finish_book2.sh` redoes the Mac residues after the running VM mop-up, then merges and gates. Mechanism: rsync
  replaces the file by rename, so the writer's open handle kept appending to an orphaned inode and every
  mop-up entry since the previous sync was lost for both files. Both residue sets are being redone (Mac 228 roots,
  VM 62 roots, four plies) before the merge; cost ≈ 35 min on the gate start. The merge reports root coverage.
- 01:36 **Unquoted venv path** in `mac_night_chain.sh` skipped the labelling/mining after the leaf dump;
  relaunched with `mac_post_leaf.sh` (quoted). The leaf dump itself was unaffected.
- 00:40 / 01:38 **Pod launch**: RunPod key not injected until added via the proxy; first A-lane run failed
  because the trainer source had been excluded from the GCP tools sync and nested target dirs did not exist
  (`mkdir -p` added). Third run: code + data pulled, mix 36.5 M rows (3.57 % extreme), trainer built in 15 s,
  A1 training started 01:41.
- Three ssh sessions killed themselves via `pkill -f` patterns matching their own command line; replaced by
  `ps | grep "[x]" | xargs kill`.

## 16. GPU lanes on the RunPod A40 (from 01:41)

`run_a_lane.sh`: A1 `fcb_re` (exact fc_b replicate: resume k96-96, start 97, 104 sb, cosine 0.0005; control) and
A2-lite `a2lite` (clean_d10 + 3 % depth-16 endgame spice, same schedule); exports with ACC_BOUND check and sanity
evals; 30k screens (576 games) and 5+0.05 ladders (400) vs fc_b on the pod's 9 cores. Trainer throughput 3.5 M pos/s.
`run_b_lane.sh`: `k96b` from scratch on the 712 M shuffle (96 sb) → `k96b_ft` (fc_b continuation on top).
`run_a3_site.sh`: `a3site` = clean_d10 + 5 % all-band site depth-16 labels. `screen_queue.sh`: screens k96b_ft,
a3site, k96b as they appear, then the ladder for the best screen. All nets/checkpoints/logs mirror to
`gcp-x86:~/chess/data/stage/{nets_night,ckpt_night}`. Real-clock wrapper gate (`combo_gate.sh … C`) on GCP after the
book gate. Screens are upper bounds; nothing ships on a screen.

Assets at 02:00: `site_all.bin` = 532,217 depth-16 positions across all bands from 6,713 archived games (80 % quiet,
|cp| mean 245), staged on gcp-x86 and the pod; A3-site mix 37,055,639 rows at 3.65 % extreme. A1 `fcb_re` and A2-lite
`a2lite` trained and exported (both ACC_BOUND 16,355 int16; sanity: start +25, KPK +243, knight-down −480/−479);
their 30k screens vs fc_b are running on the pod. Error set so far: 111 errors from 150 self-play games (Mac), a second
150 running; the 100k depth-12 leaf labelling restarted after a stratification bug.

Lane C (02:15): the six test80-2024 binpacks (≈ 52 GB) pulled to the pod in minutes; trainer patched with
`--eval-scale` (Args field, default 400, used in the TrainingSchedule and the banner); `run_c_lane.sh` waits for the
GPU (after B and A3-site), rebuilds, runs the scale pilot (6 sb on jan, slope ratio vs fc_b on a depth-10 chunk, refuses
if k ∉ [0.15, 8]), then bp48 (48 sb, 400/k, max-score 3000), bp_d7 (12 sb on the shuffle), bp_d7_ft (fc_b schedule),
export + bound + sanity, mirror. `screen_one.sh bp_d7_ft` waits for the net and a free box. Expected on the pod:
pilot ~03:10, bp48 by ~04:00, bp_d7_ft by ~04:15, screen by ~05:00.

Control screen (pod, 576 games at 30k): `fcb_re` (exact replicate) vs deployed fc_b = **−10 ±18**
(+110 =339 −127), within seed noise of zero: the pipeline reproduces the lineage; arms are read against both.
Book gate started 02:24 BST (300 games, 6 workers, stats sidecar on).

### Frozen book candidate (02:24)

`book_sf.json`: **58,206 entries, all Stockfish 19, all 1,226 roots covered** (per ply: 1,225 / 2,579 / 3,887 /
8,232 / 12,037 / 12,051 / 18,195 for plies 0–6), 142 same-ply move conflicts resolved deterministically, 0 kept
from the old book. Audit: 0 bad keys, 0 illegal moves. Candidate = exact V8.5 code + this book + the wrapper
guards; manifest `night_evidence/book/sfbook_manifest.txt` (book sha256 13ce997a…, zip 72f24cd9…, 25,733,859 bytes
unzipped). Cold start on quiet x86: 27.9 s, NNUE on, legal move, 818 MB peak. Gate: 300 games, 120+0.5, 6 workers,
vs V8.5 as shipped, started 02:24 BST; report via `book_gate_report.py`.

02:40: `run_c2_lane.sh` armed (continues bp48 to 96 sb after Lane C, re-aligns, re-fine-tunes, exports; screened by
`screen_one.sh bp96_d7_ft`); `run_onday_ft.sh` (≤ 3 sb at lr 0.0003 from any checkpoint) and `gate_worker.sh`
(turns an extra A40 pod into a 120+0.5 wrapper gate worker on a disjoint opening slice) staged.

02:45: decision-error set so far 266 positions (Mac 111 + 131 from 300 self-play games, VM 24 from 80 endgame-root
games), `errors_all.jsonl` staged; the VM mines 400 more games and the Mac 176 more after the labelling pilot ends.

02:50: `run_c3_lane.sh` armed (bp96 → 144 sb, re-align, re-fine-tune, export, screen) and `morning_gate_chain.sh` armed on
GCP (after the book gate: report, best screened net ≥ +12 → `combo_gate.sh C` 200 games, then `A`). Archit's instruction:
double or triple the exposure as needed; real-clock gates when GCP is free, no rush.

03:00 **Gate pacing.** The GCP box is 8 vCPU = 4 physical cores; with 6 workers (12 engines) each game runs at about
half speed on wall-clock, (the two "Stockfish" entries seen in `ps` were zombies of the paused generators, no CPU; the
stopped generator drivers were killed at 03:03 to clean up). Observed ~26–36 games/h, so 300 games would end after 10:00. Read point revised at 03:15 once the pace settled at ~64 games/h (45 games by 03:12, zero fallbacks): **300 games or 08:00 BST, whichever first** (the morning chain stops the gate there, writes the report and starts the net gates; 150 games each). This is a fixed
read point declared before seeing the result, not an early stop on excitement.

03:10: exposure target confirmed at 144 superbatches (C → C2 → C3). Intermediate checkpoints every 16 sb in the binpack
runs; `mirror_loop.sh` on the pod mirrors checkpoints/nets/logs to GCP every 10 min.

03:15 results: Lane B done: `k96b` (from-scratch on the 712 M shuffle, 96 sb) and `k96b_ft` (fc_b continuation) exported,
ACC_BOUND 16,311 / 16,314 int16, mirrored. Screen `a2lite` vs fc_b: **+1 ±18** (576 games; +124 =330 −122): the 3 %
endgame spice is neutral at fixed nodes. The A-lane's 5+0.05 ladders for the control and the neutral arm were skipped
to free the pod's cores for the k96b_ft, A3-site and Lane C screens (ladder only for the best screen).

03:22: A3-site trained and exported; Lane C pilot (6 sb on the January binpack) started 02:52 BST to measure loader
speed and the score-scale ratio k; the k96b_ft screen is running on the pod's cores.

03:02 **Lane C pilot**: 6 sb on the January binpack at 2.6 M pos/s. Slope pred/label on a depth-10 chunk: pilot
1.250, fc_b 0.781 → k = 1.60 → binpack labels are ~1.6× our centipawns → `--eval-scale 249.8` for the big run
(raw output stays cp/400). Caveat: an under-trained pilot may compress differently from fc_b, so k is approximate;
the two alignment fine-tunes at scale 400 on our labels re-fit the output scale regardless. bp48 started 03:02.

03:50 **Lane C done**: bp48 (48 sb on jan–jun at eval-scale 249.8, 32 min), bp_d7 (12 sb on the shuffle), bp_d7_ft (fc_b
schedule) exported; ACC_BOUND 15,778 / 14,422 / 14,358 int16; sanity bp_d7_ft: start +15, KPK +213, knight-down −425.
C2 (bp96) training from 03:45. Screen `k96b_ft` vs fc_b: **−9 ±18** (576): the refreshed base is not a gain.
Bug fixed: `screen_one.sh` watchers for the C2/C3 nets had given up when Lane C finished (wrong status file); relaunched.

03:55: screen order on the pod fixed: the queue's low-value k96b screen was removed so `bp_d7_ft` screens right after
`a3site`; `ladder_best.sh` runs the 5+0.05 ladder for the best complete screen once the Lane C nets are screened
(deadline 08:30 UTC).

04:30 **C2 done**: bp96 (03:45–04:17), bp96_d7, bp96_d7_ft exported (ACC_BOUND 14,861 int16). **C3 (bp144) training
from 04:28.** Screens so far vs fc_b (576 games, 30k): fcb_re −10, a2lite +1, k96b_ft −9, a3site −4 — all within noise
of zero; `bp_d7_ft` screening now, `bp96_d7_ft` and `bp144_d7_ft` queued; ladder for the best afterwards.

04:35: leaf labelling pilot finished at 02:50: **100,000 search-leaf positions labelled at depth 12** (stratified; 28 pos/s
on three Mac workers), `leaf_labels_mac_000.npz` + `.labels.jsonl` (net score next to the label), staged on GCP and the pod.
The Mac now mines the last 176 self-play games (a pattern bug had left that job unstarted).
