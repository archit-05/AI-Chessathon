# PRETRAIN PLAN — finals eve, 11→12 September 2026

**Owner:** pretraining workstream (engine/search/packaging are owned separately).
**Deliverable by morning:** the strongest *validated* network for the current rules, a family of checkpoints (512/768/1024) with optimiser state and a 10‑minute fine‑tune recipe for whatever constraint is announced tomorrow, and gate results nobody has to re‑argue.
**Companion files:** `fleet_checklist.md` (rent, provision, stage data), `run_register.md` (fill before/after every arm and gate).

Honest framing: no six‑hour plan guarantees wins against five engines within ±50 Elo of us. What it can do is turn the one lever that is ours tonight — the evaluation network — into +30…+80 Elo at the real clock, which at an 84 % draw rate is the difference between drawing and winning the decisive games, and make sure tomorrow's constraint finds us with the right net already trained.

---

## 0. Where we stand (verified in the repo, 11 Sep)

| Fact | Value |
|---|---|
| Deployed build | **V8.5** = `bini_astra_v5_noc2b/`, net `fc_b-104`, book 6,105 entries, `submission_V8.5.zip` sha256 `26828c24…` |
| Result | Swiss **6th of 334, 10/13 (8‑4‑1)**; ladder #3 (2799, −15 to #1); zero technical failures |
| Finals format | best‑of‑2, one game each colour; **level match → better Swiss finisher**. We lose ties vs JBG fam (PSL), Miskeen, Lightning Tree (Loss Preventer), Gladiator (AlphaFish), Rataturing; we win ties vs everyone else |
| Platform | one EPYC 9V74 core, 2 GB, 90 s init (our compile 37–60 s), 50 MB unzipped, 120 s + 0.5 s, Python 3.12 + numba/numpy/torch‑cpu/onnxruntime/python‑chess, no network, fresh process per game |
| Platform telemetry (13 Swiss games) | median **522 knps**, depth **18** (p10 15, p90 21), 1.8 s/move, init median 39.5 s (max 60.3 s) |
| Net | 8 king buckets × 768 → **1024** ×2 → 8 output buckets, SCReLU, int16 accumulators (ACC_BOUND 16,355), 12.6 MB |
| Lineage | `k96-96` (bullet, 96 sb × 100,007,936 pos on **712M own SF19 depth‑7 rows**, lr 0.001 cosine, batch 16384, 15 min on one 5090) → `fc_b` (resume, lr 0.0005, **8 sb on 178 clean depth‑10 shards = 35,458,988 rows, 3.68 % \|cp\|>800**) |
| fc_b measured | +29 ±11 at 30k fixed nodes; +17 ±14 book‑free / **+27 ±25 real wrapper** at 120+0.5 |
| Recoverable | `data/gpu_mirror/ckpt/k96-96/` (raw.bin + optimiser_state) — exact resume. fc_b float checkpoint **lost**; only the int16 export survives |
| Data | 22.8 GB depth‑7 shuffle (`bullet_shuf/shuffled_{0..7}.bin`) and 5.8 GB depth‑10 corpus (406 shards: `shard_4*`+`shard_9*` = the 178 clean; `shard_5*` = dirty endgame series) live **only on the Mac** |
| Public data | `https://huggingface.co/datasets/linrock/test80-2024` (public): `test80-2024-{01-jan 7.69 GB, 02-feb 6.91, 03-mar 8.76, 04-apr 12.3, 05-may 8.85, 06-jun 7.9}-2tb7p.min-v2.v6.binpack.zst`. The earlier attempt failed only because it used a `models/` URL |
| Known failure class | eval **resolution**: the net compresses 400–650 cp Stockfish gaps into ~100 cp in holding/liquidation/compensation positions (R108 39.g5 vs fxe3; R113 39.Rc2 vs Qe8+; R114 40…Qh6 vs Bh4; R103/R105 replays) |

### Engine score: 7/10. What separates it from 10

| Gap | Elo at the clock if closed | Who / when |
|---|---|---|
| Eval resolution (above) | +30…+80 | **this plan, tonight** |
| Eval speed: numba emits scalar code for the NNUE dot product; 1536/2048 nets measured −27/−4 at 30+0.125 purely from speed | +40…+80 (would make 2048 shippable) | engine owner, parallel bounded task (§9) |
| Search constants never retuned at a real clock (only LMR_DIV) | +10…+30 | engine owner, if T1 has spare gate capacity |
| Time policy vs the top five (we spend a fixed ~4 % of clock; PSL 63 % more; our missed wins had 39–44 s in hand) | +10…+20 | engine owner, 120+0.5 gates |
| Conversion / tablebases | +5…+10 | secondary |
| Opening prep (book rebuild measured −16.5) | 0…+15 | not tonight |

---

## 1. What budget buys and what it does not

| Resource | Effect | Verdict |
|---|---|---|
| Faster GPUs (H100/B200) | none — the trainer is loader‑bound at 6–10 M pos/s; a 96‑sb 1024 run is 15 min on a 5090 | not needed |
| Second GPU box | parallel arms + redundancy against the credit expiry that killed work once | **rent G2** |
| **Big CPU boxes** | Stockfish labelling is CPU‑bound (~70 pos/s/thread at depth 10, ~35 at depth 12, ~5 at depth 18); timed gates are CPU‑bound (400 games at 120+0.5 = 100 min on 28 workers, ~35 min on 90) | **this is where the money goes** |
| More rows | volume beyond ~500 M is measured flat; what matters is label depth × distribution × purity | buy labelling throughput, not rows |

**Fleet (Vast.ai; see `fleet_checklist.md`):** G1, G2 = 2×RTX 5090 each; L1–L3 = EPYC ≥192 threads each (labelling); T1 = EPYC ≥192 threads, gates only.

---

## 2. Five traps in the tooling (read before launching anything)

1. **`--data` does not shuffle.** `bini_bullet_trainer --data` uses bullet's `DirectSequentialDataLoader`; any *mixed* corpus (clean d10 + N1 + spice) must be physically interleaved first (§4.0). The 712M set is already shuffled.
2. **Resume + cosine schedule.** The LR schedule keys on `superbatch / --superbatches`. `--resume ckpt/k96-96 --start-superbatch 97 --superbatches 104 --lr-schedule cosine` runs the whole fine‑tune at the LR floor (lr·0.3⁵ ≈ 1.2e‑6). fc_b's real schedule is printed in the Mac's `~/chess_d10_mirror/gatelogs/logs/train_fc_b.log` ("LR Scheduler … Start/End Superbatch"); **copy it into the run register at T+0 and replicate it exactly for A1**. If it is unavailable, use `--resume ckpt/k96-96 --start-superbatch 1 --superbatches 8 --lr 0.0005 --lr-schedule cosine` (a fresh 8‑sb cosine) as the default and record the choice.
3. **`EVAL_SCALE = 400` is a `const`** in `bini_v7/tools/bullet_trainer/src/main.rs`. Public binpacks carry Stockfish‑internal scores (≈3–4 units per UCI cp). Either patch a `--eval-scale` flag (§4.C) or slope‑match at export with `--out-scale`; never mix internal‑unit and cp labels in one `--data` run.
4. **Re‑exports are not byte‑identical** (metadata carries the source path); compare tensors `w1/b1/w2/b2` with numpy.
5. **int16 accumulators.** Every export must keep `ACC_BOUND = max|b1| + 32·max|w1| < 32767` (the exporter prints `|w1|max`; k96/fc_b are 505 → 16,355). A net that flips `ACC_DTYPE` to int32 is slower at the clock and every screen result for it is misleading.

Binding evidence: epochs ≈ 10–15 for from‑scratch (41M rows × 96 sb = 236 epochs → −345); fine‑tune length from k96‑96 on clean data 3 sb +25, **8 sb +29**, 16 sb +1, 24 sb −27; endgame share hurts monotonically (0 % +29, 10 % +18, 20 % −1, 38 % +4) → **profile |cp|>800 before every run, ≤ 4 %**; lr/batch = ½ is +9 over k96's lr 0.001; fixed‑node screens inflate eval gains 2–3× and cannot be scaled by a constant; never read a partial gate; compare *difference* intervals (√2 wider); any fallback/"still compiling"/nnue=off line voids a gate.

---

## 3. Timeline (T = first box up; lanes in parallel; critical path A → G)

| Time | Infra (G1/T1) | Lane A — fc_b lineage (G1) | Lanes B/C/D/E (G2, then G1 GPU1) | Lane L — labelling (L1–L3) | Lane G — gates (T1) |
|---|---|---|---|---|---|
| T+0:00–0:45 | rent, provision, **Mac uploads start** (d10 first), binpacks download, trainer build, parity + instrument checks | read `train_fc_b.log`, fix the A1 schedule | — | fleet up: N1 depth‑12 (L1–L2), N2 depth‑18 (L3) | determinism + instrument (fc_b vs k96 ≈ +29) |
| T+0:45–1:30 | d10 landed | **A1 fcb_re** (control) | C‑pilot on jan binpack (loader speed, scale k) | N1 rows flowing to G1 every 15 min | screen A1 vs k96 / vs deployed |
| T+1:30–2:30 | — | **A2 clean+** (8 sb) then **A3 crit5 / A3b crit2.5** | **C1 bp144** launched (G2/GPU0); C0 control (G2/GPU1) | N2 done (≤ 2 M rows, depth 18) | screens A2, A3, A3b |
| T+2:30–3:30 | 712M shuffle landed → copy to G2/T1 | **A6 deep** (16–24 sb on full N1) | **B k96b** (G1/GPU1, 96 sb); **D w768** (G2 when C1 done) | N1 at 100–150 M rows; fleet stops | 30+0.125 timed, 400 games: top 2 of A vs deployed |
| T+3:30–4:30 | — | **A7 deep+crit**; **E seeds** of the best A arm | C1 export (scale‑matched) → `bp_d7` → `bp_d7_ft`; `k96b_ft`; `w768_ft`, `w512_ft` | — | screens B/C/D; 30+0.125 for any arm ≥ +15 over fcb_re |
| T+4:30–5:30 | — | — | — | — | **120+0.5 real wrapper**, 400 games, finalist vs V8.5 (block A); second 400 (block B) if time |
| T+5:30–6:00 | mirror all checkpoints (G2 + Mac), md5, run register, hand‑over | | | | decision by §5 rules |

GPU minutes are not the constraint (~3 h total across both boxes). Gate minutes are: T1 at ~90 workers gives 576‑game screens in ~6 min, 400‑game 30+0.125 gates in ~15 min, 400‑game 120+0.5 wrapper gates in ~35 min.

---

## 4. Lanes with exact commands

Conventions on every box: `~/chess/{bini_v7,bini_astra_v5_noc2b,bini_v85_stable,astra_tests,aichessathon-starter,data,gates,logs}`; `PY=~/chess/venv/bin/python` (platform stack), `T=~/chess/bini_v7/tools/bullet_trainer/target/release/bini_bullet_trainer`, `CK=~/chess/data/ckpt`, `NETS=~/chess/data/nets`, `E=~/chess/bini_astra_v5_noc2b`, `O=~/chess/bini_v7/tools/curated.epd`, `NG=~/chess/bini_v7/tools/node_gate.py`, `X=~/chess/bini_v7/tools/bullet_export.py`.

### 4.0 Corpus tools (numpy, seconds)
Profile (rows, mean cp, |cp|>800 %, quiet %): `$PY ~/chess/bini_v7/tools/bulletformat.py info FILE.bin ...`
Concatenate + shuffle a mixed corpus (32‑byte records):
```python
import numpy as np, sys; sys.path.insert(0, "/root/chess/bini_v7/tools"); import bulletformat as bf
parts = [np.fromfile(p, dtype=bf.DTYPE) for p in FILES]          # e.g. clean shards + N1 shards (+ N2 at 5 %)
arr = np.concatenate(parts); arr = arr[np.random.default_rng(1).permutation(len(arr))]
arr.tofile(OUT); print(len(arr), "rows", float(np.mean(np.abs(arr["score"]) > 800)), "|cp|>800")
```
Spice at p %: take `n_spice = p/(100−p) · n_base` rows of N2 (random subset), then concatenate + shuffle as above. **Blend |cp|>800 must be ≤ 4.5 %.**

### 4.A Lane A — the fc_b lineage (G1/GPU0). Every arm: state epochs and |cp|>800 before launch.
**A1 fcb_re (mandatory control, ~5 min):** exact fc_b recipe from `train_fc_b.log`; default if unknown:
```bash
$T --data ~/chess/data/ft/clean_d10_shuf.bin --resume $CK/k96-96 --start-superbatch 1 --superbatches 8 \
   --lr 0.0005 --lr-schedule cosine --hidden 1024 --act screlu --wdl 0 --save-rate 8 --threads 8 --device 0 --out $CK --net-id fcb_re
$PY $X --checkpoint $CK/fcb_re-8 --hidden 1024 --act screlu --out $NETS/nnue_fcb_re.safetensors \
   --check "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1" --check "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKB1R w KQkq - 0 1" --check "8/8/4k3/8/8/4K3/4P3/8 w - - 0 1"
```
Epochs 8×100.0 M / 35.5 M = 22.5. Screen vs `nnue_k96` (expect ≈ +29 ±22) **and** vs the deployed net (expect ≈ 0 ±22). If fcb_re is < −15 vs the deployed net: re‑check the schedule once; if still failing, all A arms are compared against the deployed net only, and the base becomes the **dequantised fc_b** (w1/255, b1/255, w2/(qb·400), b2/(255²·qb·400), qb = 32 from metadata; inverse of `bullet_to_bini_perm`; written as `optimiser_state/weights.bin` in the named‑tensor format `read_weights_bin` documents, zero moments; first 2 sb at lr 0.00025).

**A2 clean+ :** `clean_d10 + N1(first 30–60 M rows)`, shuffled; same command with `--net-id a2`, 8 sb. Epochs ≈ 8–10.
**A3 crit5 / A3b crit2.5:** A2 corpus + N2 at 5 % / 2.5 %; `--net-id a3`, `a3b`; 8 sb.
**A6 deep :** clean_d10 + **full N1 (≥ 120 M rows)**, `--superbatches 16` (epochs ≈ 10–13; add a 24‑sb variant only if 16 ≥ A2). This is the arm the labelling fleet exists for: fc_b's recipe with 4× the unique in‑distribution rows at deeper labels.
**A7 deep+crit :** A6 corpus + 5 % N2.
**E seeds :** best A arm ×2 with `--seed 11 / --seed 22` on G2 (seed noise ≈ ±10 Elo); keep the best on the screen.
**A5 (GPU‑idle only):** A2 corpus with `--wdl 0.2` — but our own shards carry `result = 0` for walk/arena rows, so use WDL **only** if the corpus's result column is populated; otherwise skip.

### 4.B Lane B — base recipe refresh (G1/GPU1, once the 712M shuffle has landed)
```bash
$T --data ~/chess/data/bullet_shuf/shuffled_{0..7}.bin --hidden 1024 --act screlu --wdl 0 --lr 0.0005 --lr-schedule cosine \
   --superbatches 96 --save-rate 24 --threads 8 --device 1 --out $CK --net-id k96b        # ~15–20 min, 13.5 epochs, measured +9 vs k96 at 30k
# then the winning A recipe on top: --resume $CK/k96b-96 --net-id k96b_ft
```
Cheaper alternative if GPU time is short: **k144h** = `--resume $CK/k96-96 --start-superbatch 1 --superbatches 48 --lr 0.0005 --lr-schedule cosine` on the 712M shuffle (20 cumulative epochs), then the A recipe.

### 4.C Lane C — public‑binpack pretrain (G2)
1. **Pilot (unpatched, 12 sb on jan, ~8 min):** loader speed and the score scale k.
```bash
zstd -d -T16 ~/chess/data/binpacks/test80-2024-01-jan-2tb7p.min-v2.v6.binpack.zst   # and feb…jun in the background
$T --binpack ~/chess/data/binpacks/test80-2024-01-jan-2tb7p.min-v2.v6.binpack --hidden 1024 --act screlu --wdl 0 --lr 0.0005 \
   --lr-schedule cosine --superbatches 12 --save-rate 12 --threads 32 --binpack-buffer-mb 4096 --min-ply 16 --max-score 10000 --device 0 --out $CK --net-id cpilot
$PY $X --checkpoint $CK/cpilot-12 --hidden 1024 --act screlu --out $NETS/nnue_cpilot.safetensors --check "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKB1R w KQkq - 0 1"
BINI_NNUE=$NETS/nnue_cpilot.safetensors $PY tools/net_diag.py ~/chess/data/slope_ref.npz --n 20000 | head -1     # "scale slope pred/label k"
```
Kill/branch: loader < 1 M pos/s → `--threads 64`; still < 1 M → C runs at 48 sb only. k outside [0.8, 5] → wrong file/reading; stop.
2. **Patch** `main.rs` (5 lines, rebuild 2 min): add `--eval-scale X` (default 400.0) to `Args`/`parse_args`, use it in `TrainingSchedule.eval_scale` and the final `eval` print. With `E = 400·k` the raw output is already cp/400, the export needs no out‑scale, and the later fine‑tune on our cp labels runs at E = 400 with no target jump. (Fallback without the patch: train at 400 and export with `--out-scale 1/k`; expect worse resolution in the 300–600 cp band.)
3. **C1 (main arm):**
```bash
BP=~/chess/data/binpacks; $T --binpack $BP/test80-2024-0{1-jan,2-feb,3-mar,4-apr,5-may,6-jun}-2tb7p.min-v2.v6.binpack \
   --hidden 1024 --act screlu --wdl 0 --eval-scale <400*k> --lr 0.0005 --lr-schedule cosine --superbatches 144 --save-rate 24 \
   --threads 48 --binpack-buffer-mb 8192 --min-ply 16 --max-score 3000 --device 0 --out $CK --net-id bp144       # 3–5 B filtered rows → 3–5 epochs; 40–75 min
```
C0 control (G2/GPU1, optional): identical without `--eval-scale`, exported with `--out-scale S_fcb/S_c0`.
4. **Alignment fine‑tunes:** `--resume $CK/bp144-144 --data shuffled_{0..7}.bin --superbatches 12 --lr 0.0005 --net-id bp_d7` (1.7 epochs), then the winning A recipe → `bp_d7_ft`. Screen each stage vs `nnue_k96`.
Kill: `bp144` < −80 vs fc_b at 30k → stop C; `bp_d7_ft` < A‑winner + 10 → research asset only (checkpoints kept for tomorrow). Optional if C1 is positive and a GPU is idle: `--wdl 0.2` on binpacks (they carry real game results).

### 4.D Lane D — width ladder for tomorrow (G2 when free)
```bash
$T --data ~/chess/data/bullet_shuf/shuffled_{0..7}.bin --hidden 768 --act screlu --wdl 0 --lr 0.0005 --lr-schedule cosine --superbatches 96 --save-rate 48 --threads 8 --device 1 --out $CK --net-id w768   # ~12 min
$PY ~/chess/bini_v85_stable/tests/test_bullet_export.py --hidden 768 --act screlu --n 500     # parity for the new width
# fine-tune: --resume $CK/w768-96 + the winning A recipe → w768_ft ; 512: --resume $CK/s96-96 --act crelu + the A recipe → w512_ft
```
1536/2048: **not tonight** (dead at the clock unless §9 lands). Record per width: knps (`tests/bench.py` on T1), ACC_DTYPE, export size (512 6.3 MB, 768 ≈ 9.5 MB, 1024 12.6 MB), screen vs its base, a 200‑game 30+0.125 sanity vs fc_b (for the playbook table).

### 4.L Lane L — labelling fleet (L1–L3; T1 never labels; labellers SIGSTOPped on any box that gates)
`LF=~/chess/bini_v7/tools/label_fleet.py; SF=/usr/local/bin/stockfish`
**N1 in‑distribution, depth 12 (L1+L2, target 100–150 M rows by T+3:00):**
```bash
$PY $LF --out ~/chess/data/n1 --pgn ~/chess/data/src/ownplay/*.pgn ~/chess/data/src/rivals/*.pgn ~/chess/data/src/swiss/*.pgn \
   --json-dir ~/chess/data/src/swiss --min-ply 8 --min-pieces 12 --stride 2 --producers 8 --consumers 176 --depth 12 --stockfish $SF --pin --cpu-start 8
$PY $LF --out ~/chess/data/n1w --epd $O --walk 8 --walks-per-root 2000 --min-pieces 12 --producers 4 --consumers 180 --depth 12 --stockfish $SF --pin --cpu-start 4     # L2
# then Lichess Elite 2025-03..06 whole games (provision_vast.sh downloads them): --pgn ~/chess/data/elite/*.zip --stride 2
```
**N2 critical set, depth 18 (L3, ≤ 2 M rows by T+2:00):** build `~/chess/data/src/n2.epd` from (a) swing positions in `intel/raw/evals.jsonl` (site eval moved ≥ 150 cp on one move, |eval before| < 400; keep before and after), (b) every position from our ladder/Swiss losses and the three Priority‑A games, (c) `hard_fens*.txt` + `tests/pos/{blunders,harvest,marginal,sharp}.epd`, (d) **resolution rows** mined from a 5 M‑row sample of N1: keep rows with |cp| in [250, 900] whose fc_b static eval (int16 forward) differs from the label by > 200 cp. Then
`$PY $LF --out ~/chess/data/n2 --epd ~/chess/data/src/n2.epd --walk 1 --walks-per-root 3 --consumers 180 --depth 18 --fresh --stockfish $SF --pin`
(walks of 1–2 plies keep the root's neighbourhood; the root itself is labelled through the swing list which includes both sides of each move). MultiPV mining tools do not exist tonight; do not build one.
Every 15 min: `rsync -az l1:~/chess/data/n1/*.bin g1:~/chess/data/n1/` (same for n1w, n2). Purity filter on arrival: drop shards until |cp|>800 ≤ 4 %.

### 4.G Lane G — gates (T1 only; ~192 physical cores → ≤ 90 workers)
Screen (576 games, 30k nodes, ±22, ~6 min):
```bash
cd $E && $PY $NG --engine $E --a "BINI_NNUE=$NETS/nnue_CAND.safetensors" --b "BINI_NNUE=$NETS/nnue_fcb.safetensors" \
   --openings $O --games 576 --nodes 30000 --workers 90 --pin --tt-bits 22 --out ~/chess/gates/s_CAND_vs_fcb
```
Timed (400 games at 30+0.125, ±20, ~15 min): same with `--tc 30+0.125 --games 400`.
Real wrapper (400 games at 120+0.5, book on, both arms packaged as directories with the candidate net copied to `nnue.safetensors`, ~35 min):
```bash
cp -r $E ~/chess/cand_CAND && cp $NETS/nnue_CAND.safetensors ~/chess/cand_CAND/nnue.safetensors
cd ~/chess && BINI_JOIN_S=300 $PY astra_tests/arena_astra.py --a ~/chess/cand_CAND --b $E --games 400 --base-ms 120000 --inc-ms 500 \
   --workers 90 --openings $O --manifest-offset 0 --out ~/chess/gates/rw_CAND_A --resume
$PY astra_tests/analyse_gate.py ~/chess/gates/rw_CAND_A.json [~/chess/gates/rw_CAND_B.json]      # pentanomial, contamination-checked
```
`BINI_JOIN_S=300` only inside contended gates; the production cold‑init check runs without it.

---

## 5. Predeclared gate ladder and ship rule

1. **Screen** 576 @30k vs deployed fc_b: promote if ≥ +12; if in [0, +12) and top‑two, extend to 1728 games (±11) and promote if ≥ +10. Compare arms by the *difference* interval.
2. **Timed 30+0.125**, 400 games, at most 4 candidates: promote if ≥ +8 with lower bound > −5.
3. **Real wrapper 120+0.5**, at most 2 candidates: block A 400 games (offset 0; futility stop if ≤ −20 after 200); block B 400 games (offset 1) for the leader.
4. **Ship rule:** pooled 800 wrapper games (or pooled timed + wrapper if only one block fits) with pentanomial 95 % lower bound > 0 **and** point estimate ≥ +8, zero fallback/flag/nnue‑off lines in both arms. Otherwise **V8.5's net stays**; the finalist ships only as a labelled alternative for on‑day selection.
Expected compression: a screen gain survives at 0.36–0.6×; a candidate needs ≈ +20 on the screen to have a real chance of +8 at the clock.

## 6. Kill rules
- Trainer not built by T+1:00 → debug to T+1:30; after that the night is gates + data + kit from existing nets (fc_b, k96, k24, s96), no new training.
- fcb_re > 15 below the deployed net → re‑check the schedule once; then dequantised‑fc_b base.
- A3/A3b both ≤ A2 → drop the spice. A6 ≤ A2 → deep continuation closed (record it).
- C: rules in §4.C. D: never killed; shrinks to 768‑only if the shuffle is late (s96 covers 512).
- Any contaminated gate (fallback, "still compiling", nnue=off, illegal) is void and rerun.
- If no candidate passes §5: V8.5 ships byte‑identical; the deliverable is the kit (nets + optimiser states + fine‑tune recipes + knps/size/init table) and the gate procedure with measured timings.

## 7. Ranked experiments (expected Elo at 120+0.5 vs V8.5; P(>0))
1. **A2/A6 in‑distribution depth‑12 continuation:** +8…+20; ~50 %. Same mechanism that produced fc_b, 4× the unique rows, deeper labels.
2. **A3 critical spice (≤ 5 %):** +5…+12 on top; ~45 %; the only arm aimed directly at the resolution failure.
3. **C binpack pretrain → d7 → A recipe:** +10…+30 if it transfers; ~30 %; the only arm that moves the data ceiling (billions of unique, deeper‑labelled positions).
4. **B k96b / k144h:** +3…+8; ~35 %; cheap.
5. **E seeds:** ±10 selection gain; cheap.
6. **D width ladder:** 0 under current rules; 30–40 % chance of being decisive tomorrow. Not droppable below 768.
Drop order if short: C0, A5, B, then D‑512 (use s96); keep A1, A2, A3, A6, D‑768, C1.

## 8. Finals‑day adaptation playbook (net side)

First, on the brief: run the unchanged finalist under the announced limits and identify the binding constraint; change only the affected subsystem; compare at the actual clock; reserve the last 60–90 min for exact‑package validation.

| Revealed constraint | Action | Time |
|---|---|---|
| Shorter clock | T1: `node_gate --tc <new>` w512_ft vs w768_ft vs finalist, 400 games each → winner → 200 wrapper games at the new clock vs V8.5. Prior: 1024 held +23 over 512 down to 30 s base; below ~10 s expect narrower to win. Increment change → engine owner edits `INCREMENT_MS` in `agent.py` | 20–40 min/gate |
| Smaller memory | net 6–13 MB; lever is `BINI_TT_BITS` (2^24 = 256 MB → 22 = 64 MB → 20 = 16 MB), engine owner; measure peak RSS on a cold import | 0 |
| Smaller package | ≤ 20 MB: 1024 + book fits; ≤ 10 MB: w512_ft; drop the book (`BINI_BOOK=0`) before dropping width | 0 |
| Shorter init | width does not change compile time; engine owner sets `COMPILE_JOIN_S` ≈ budget − 8 s and trims compile | 0 |
| No book | `BINI_BOOK=0`; net unchanged | 0 |
| New opening set given in advance | label the set + 2–8‑ply walks at depth 12 on L1–L3 (~10 min), 3 sb fine‑tune from the finalist at lr 0.0003, screen, timed gate | 60–90 min |
| Chess960 / variant | net is position‑only and fine; engine (castling, book) is the risk — alert the engine owner immediately | engine |
| Longer clock | keep 1024; a 1536 net needs a fresh C1‑recipe run (30–60 min) + a timed gate — only if base time ≥ 5 min | 90 min |
| On‑day fine‑tuning allowed | resume the finalist checkpoint, ≤ 3 sb at lr 0.0003 on ≤ 5 % targeted + 95 % clean; never ship without a timed gate | 45–60 min |

Kit to hand over: `~/chess/finals_kit/` = every width's checkpoint dir (with `optimiser_state/`), export, exact fine‑tune command, knps/size/ACC_DTYPE/init table, gate logs; mirrored to G2 and the Mac, md5 in the run register. Packaging: `bash astra_tests/package_astra.sh cand_X submission_X.zip` (checks layout against the frozen V8 and the 50 MB limit).

## 9. Parallel recommendation for the engine owner (the biggest remaining lever, not this workstream)
A bounded 2‑hour attempt to make `nnue_eval` in `bini_nnue.py` auto‑vectorise: contiguous 1‑D int16 slices per perspective, int32 partial sums in 8–16 independent accumulators, `min/max` clamp on int32, no `np.int64` in the inner loop; measured **in situ** (knps at fixed depth, node‑identical output), not in a microbenchmark. Success = ≥ 1.8× on the eval term (~640 of ~1,430 ns per node). If it lands, Lane D trains 1536 on the C1 recipe and the ladder's top end moves; if not, nothing in this plan depends on it. Seven earlier formulations were slower — treat as an experiment.

## 10. Closed levers — do not spend tonight on these
Rows beyond ~500 M for a fixed recipe; superbatches beyond 96 on 512; 1536/2048 without §9; king‑bucket count; lr/batch other than ½; WDL 0.75 in the PyTorch trainer; endgame/late‑ply enrichment above ~5 %; from‑scratch on < 500 M rows at 96 sb; contempt/draw‑seek; aspiration window; book rebuild; calibration table; ProbCut/qs‑checks/improving.

## 11. Risks
| Risk | Mitigation |
|---|---|
| Mac upload bandwidth | d10 first (gates A); the shuffle gates only B/D; fallback for D: relabel d7 from the elite zips on L1–L3 (~250 M rows/h) or train the ladder on binpacks |
| Binpack scale / temperature | measure k in the pilot; `--eval-scale 400k`; slope‑match every export to S_fcb (within 3 %); sanity `--check` positions; never mix label scales in one run |
| Loader never run on real binpacks | 1‑sb pilot first; watch pos/s and the `--check` evals |
| Overfitting | epochs stated in every command; nothing from scratch on < 500 M rows |
| Box loss / credit | rsync ckpt/nets/gates G1→G2 every 15 min; `mirror_gpu.sh` to the Mac at the end; `arena_astra.py --resume` checkpoints every 10 games |
| Harness contamination | T1 gates only; ≤ 1 worker per 2 physical cores; `analyse_gate.py` rejects contaminated games; `BINI_JOIN_S=300` never in the cold‑init measurement |
| Screen inflation | screens rank, gates ship |
| Init budget | no engine changes here; a net changes init only through `ACC_DTYPE` — verify `ACC_BOUND < 32767` on every export |
| fc_b schedule ambiguity | resolve from `train_fc_b.log` before A1 |
