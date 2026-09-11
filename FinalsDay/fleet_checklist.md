# Fleet checklist — rent, provision, stage data (T+0:00 → T+0:45)

Order matters: the Mac uploads are the long pole (~30 Mbps). Start them before anything else.

## 0. Before renting (5 min, Mac)
- [ ] Open `~/chess_d10_mirror/gatelogs/logs/train_fc_b.log`; copy the **"LR Scheduler"** and **"Start/End Superbatch"** lines into `run_register.md` (they define the exact fc_b recipe; see PRETRAIN_PLAN §Lane A1 trap).
- [ ] Confirm the clean shard list (178 shards, 35,458,988 rows) — `shard_4*.bin` + `shard_9*.bin` in the d10 mirror; note the directory.
- [ ] Confirm `data/gpu_mirror/bullet_shuf/shuffled_{0..7}.bin` exist on the Mac (8 × 2.85 GB).
- [ ] If `hp_lr05-96` (lr‑0.0005 from-scratch checkpoint, +10 vs k96) exists in the Mac mirror, it replaces k96‑96 as the base for every resume arm; note its path.

## 1. Rent (Vast.ai)
- [ ] **G1**: 2× RTX 5090, ≥64 vCPU, ≥300 GB NVMe, ≥1 Gbps down, CUDA 12.8 devel image with `/venv/main` torch (the template `provision_vast.sh` expects). Record instance id.
- [ ] **G2**: same spec.
- [ ] **L1–L3**: CPU instances, AMD EPYC ≥192 threads, ≥128 GB RAM, ≥100 GB disk each (Vast "CPU" filter; fallback GCP c3d-standard-360 / Hetzner AX/Dedicated).
- [ ] **T1**: EPYC ≥192 threads, ≥64 GB, **nothing else scheduled on it**.
- [ ] Add each host to `~/.ssh/config` as `g1 g2 l1 l2 l3 t1` (BatchMode).
- [ ] Rent through the finals window (tomorrow evening): G1/G2 are the on-day fine-tune machines.

## 2. Start the uploads (Mac → G1), in this order
```bash
rsync -az --partial --info=progress2 ~/chess_d10_mirror/<d10 shards dir>/ g1:~/chess/data/d10/ && \
rsync -az --partial --info=progress2 ~/Desktop/AI\ Chessathon/data/gpu_mirror/bullet_shuf/ g1:~/chess/data/bullet_shuf/
```
- [ ] d10 landed (5.8 GB, ~25 min)   - [ ] shuffle landed (22.8 GB, ~1.7 h)   → then box-to-box: `g1 → g2, t1` at 1 Gbps.

## 3. Provision every box (parallel, ~25 min)
```bash
for h in g1 g2 l1 l2 l3 t1; do rsync -az --exclude __pycache__ bini_v7 bini_astra_v5_noc2b bini_v85_stable astra_tests aichessathon-starter $h:~/chess/; done
for h in g1 g2 l1 l2 l3 t1; do ssh $h 'mkdir -p ~/chess/logs && nohup bash ~/chess/bini_v7/tools/provision_vast.sh > ~/chess/logs/provision.log 2>&1 &'; done
# provision_vast.sh also starts a 21.7 GB lichess_db_eval download we do not need tonight: on each box `pkill -f lichess_db_eval` once SF has built.
```
- [ ] Stockfish 19 built on all six (`stockfish bench` prints Nodes/second)
- [ ] G1/G2: `source ~/.cargo/env && cd ~/chess/bini_v7/tools/bullet_trainer && cargo build --release --features cuda`
- [ ] G1/G2: binpacks downloading (`curl -L -C - --retry 10 https://huggingface.co/datasets/linrock/test80-2024/resolve/main/test80-2024-0{1-jan,2-feb,3-mar,4-apr,5-may,6-jun}-2tb7p.min-v2.v6.binpack.zst`), then `zstd -d -T16`.

## 4. Small artefacts to every box (from this Windows clone, ~200 MB)
```bash
rsync -az data/gpu_mirror/ckpt/k96-96 data/gpu_mirror/ckpt/s96-96 data/gpu_mirror/ckpt/s144-144 g1:~/chess/data/ckpt/
rsync -az data/gpu_mirror/nets/ g1:~/chess/data/nets/
rsync -az bini_astra_v5_noc2b/nnue.safetensors g1:~/chess/data/nets/nnue_fcb.safetensors
rsync -az data/gpu_mirror/gates/*.pgn l1:~/chess/data/src/ownplay/        # 3.5M curated-opening positions
rsync -az intel/raw/*.pgn intel/raw/evals.jsonl l1:~/chess/data/src/rivals/
rsync -az "Swiss Round 13"/*.pgn FinalsDay/swiss_games.json l1:~/chess/data/src/swiss/
rsync -az data/hard_fens*.txt bini_v85_stable/tests/pos l1:~/chess/data/src/hard/
rsync -az bini_v7/tools/curated.epd t1:~/chess/bini_v7/tools/
```
- [ ] L1 fans `~/chess/data/src` out to L2/L3.

## 5. Green-before-GPU (G1 + T1, ~10 min) — all must pass
- [ ] `tests/test_bullet_export.py --hidden 1024 --act screlu --n 1000` → "bullet export consistency ok"
- [ ] `tests/test_bullet_export.py --hidden 768 --act screlu --n 500`
- [ ] `bullet_export.py --checkpoint ckpt/k96-96 --hidden 1024 --act screlu --out nets/k96_re.safetensors` → tensors identical to `nets/nnue_k96.safetensors`
- [ ] T1 determinism: node_gate 16 games A==B → 50.0 %, [0,0,8,0,0]
- [ ] T1 instrument: fc_b vs k96 @30k, 576 games → ≈ +29 ±22
- [ ] slope reference: `net_diag.py` on a 20k-row clean-d10 npz with `BINI_NNUE=nnue_fcb` → record S_fcb
- [ ] corpus profiles (`bulletformat.py info`) for clean_d10 and d7 → run register

## 6. Labelling fleet up (L1–L3, from T+0:45)
- [ ] N1 depth‑12 fleet running, `--pin`, rows/s printed every 60 s (expect ~35 pos/s/thread)
- [ ] N2 depth‑18 fleet running on one box (≤ 2M rows)
- [ ] Every 15 min: `rsync` new shards to G1 (`~/chess/data/n1`, `~/chess/data/n2`)

## 7. Backups (every 15 min, automated)
- [ ] `rsync -az g1:~/chess/data/ckpt g2:~/chess/data/ckpt_mirror` and to the Mac (`mirror_gpu.sh` at the end)
- [ ] md5 of every export in the run register
