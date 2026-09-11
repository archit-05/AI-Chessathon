# Run register — finals-eve pretraining (11–12 Sep 2026)

One row per training arm, one row per gate. Fill **before launch** (corpus, rows, |cp|>800, epochs, command) and **after** (checkpoint, export hash, results). Nothing ships from a row with a blank "wrapper 120+0.5" cell.

## Fleet

| Box | Provider / id | Spec | Role | Up at | Down at | Notes |
|---|---|---|---|---|---|---|
| G1 | | 2×5090 | training A/B, screens, checkpoint home | | | |
| G2 | | 2×5090 | lanes C/D/E, checkpoint mirror | | | |
| L1 | | EPYC ≥192 thr | labelling | | | |
| L2 | | EPYC ≥192 thr | labelling | | | |
| L3 | | EPYC ≥192 thr | labelling | | | |
| T1 | | EPYC ≥192 thr | gates only | | | |

## Green-before-GPU checks

| Check | Command | Expected | Result | Time |
|---|---|---|---|---|
| Export parity | `tests/test_bullet_export.py --hidden 1024 --act screlu --n 1000` | ok | | |
| k96 re-export | `bullet_export.py --checkpoint ckpt/k96-96 …` vs `nets/nnue_k96.safetensors` | tensors identical | | |
| Determinism | node_gate 16 games, A == B | 50.0%, pentanomial [0,0,8,0,0] | | |
| Instrument | fc_b vs k96 @30k, 576 | ≈ +29 ±22 | | |
| fc_b slope | `net_diag.py slope_ref.npz` with BINI_NNUE=fc_b | S_fcb = | | |
| knps 1024 on T1 | `tests/bench.py` | (record) | | |

## Corpora

| Name | Source | Label depth | Rows | |cp|>800 % | mean pieces | ≤12-piece % | quiet % | Shuffled file | Notes |
|---|---|---|---|---|---|---|---|---|---|
| clean_d10 | shard_4* + shard_9* (Mac mirror) | 10 | 35,458,988 (expected) | 3.68 (expected) | | | | | fc_b's corpus |
| d7_712M | bullet_shuf/shuffled_{0..7} | 7 | 712,492,857 | 9.9 | | | | already shuffled | k96's corpus |
| N1 | own gate PGNs + Swiss + rivals + walks + elite | 12 | | | | | | | in-distribution |
| N2 | swing/loss/hard/resolution rows | 18 | | | | | | | ≤ 5 % spice |
| bp_jan..jun | HF linrock/test80-2024 | SF internal | | | | | | native binpack | scale k = |

## Training arms

| Arm | Base ckpt | Corpus (mix) | Unique rows | Superbatches | Epochs = sb×100M/rows | lr / schedule | Seed | Cmd (file:line in PRETRAIN_PLAN) | Started | Ckpt dir | Export (.safetensors) | md5 | out_scale | ACC_BOUND | Sanity (start / rook-down / KPK) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A1 fcb_re | k96-96 | clean_d10 | 35.5M | 8 | 22.5 | 0.0005 / (from train_fc_b.log) | | | | | | | | | |
| A2 clean+ | k96-96 | clean_d10 + N1 | | 8 | | 0.0005 | | | | | | | | | |
| A3 crit5 | k96-96 | A2 + 5 % N2 | | 8 | | 0.0005 | | | | | | | | | |
| A3b crit2.5 | k96-96 | A2 + 2.5 % N2 | | 8 | | 0.0005 | | | | | | | | | |
| A6 deep | k96-96 | clean_d10 + full N1 | | 16–24 | | 0.0005 | | | | | | | | | |
| A7 deep+crit | k96-96 | A6 + 5 % N2 | | 16–24 | | 0.0005 | | | | | | | | | |
| E seed2/3 | k96-96 | (A winner) | | | | | | | | | | | | | |
| B k96b | scratch | d7_712M | 712M | 96 | 13.5 | 0.0005 cosine | | | | | | | | | |
| B k96b_ft | k96b-96 | (A winner) | | | | | | | | | | | | | |
| C bp144 | scratch | bp jan–jun | | 144 | | 0.0005 cosine, eval-scale 400k | | | | | | | | | |
| C bp_d7 | bp144-144 | d7_712M | 712M | 12 | 1.7 | 0.0005 | | | | | | | | | |
| C bp_d7_ft | bp_d7-12 | (A winner) | | | | | | | | | | | | | |
| D w768 | scratch | d7_712M | 712M | 96 | 13.5 | 0.0005 cosine | | | | | | | | | |
| D w768_ft | w768-96 | (A winner) | | | | | | | | | | | | | |
| D w512_ft | s96-96 (crelu) | (A winner) | | | | | | | | | | | | | |

## Gates

| Gate | A (candidate) | B (reference) | Instrument | Games | Workers | Fallbacks/flags A / B | W–D–L | Score % | Elo ± | Pentanomial | Verdict | Log path |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| | | | 30k / 30+0.125 / 120+0.5 wrapper | | | | | | | | | |

Rules: never read a partial gate; compute the *difference* interval when comparing two arms (√2 × single-arm ±); any fallback / "still compiling" / nnue=off line voids the gate.

## Decision

| Item | Value |
|---|---|
| Finalist net | |
| Pooled timed + wrapper vs V8.5 | |
| Ship / hold | |
| Alternates packaged (w512_ft, w768_ft, fcb_re) | |
| Checkpoints mirrored to (2 locations, md5 verified) | |
| Handed to packaging owner at | |
