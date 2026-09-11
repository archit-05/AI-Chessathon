# bini_bullet_trainer

Trains the Bini NNUE with [bullet](https://github.com/jw1912/bullet) (Rust, CUDA) and saves float
weights that `bini_v5/tools/bullet_export.py` turns into `nnue.safetensors` for `bini_nnue.py`.

Pinned bullet revision: `629ee50000b2afb7b3337595401c830d3b1e0f42` (main, 2026-08-29). Every
layout statement below was read from that revision's source; bump the `rev` in `Cargo.toml`
only after re-checking `crates/bullet_lib/src/value/save.rs`, `game/inputs/chess_buckets.rs`
and `game/outputs.rs`.

## Architecture (identical to bini_nnue.py)

| piece | bullet trainer | Bini engine |
|---|---|---|
| king buckets | `ChessBucketsMirrored::new(KING_BUCKETS)` — 32-entry array, index `rank*4 + [0,1,2,3,3,2,1,0][file]`, mirror (`feature ^ 7`) when the own king is on files e-h | `_king_table(8)`: rank 1 a-b→0 c-d→1, rank 2 →2/3, ranks 3-4 →4/5, ranks 5-8 →6/7, `sq ^= 7` when mirrored |
| feature inside a bucket | `(opp*6 + type)*64 + sq` (bullet `Chess768`) | `(type*2 + opp)*64 + sq` — **the exporter permutes** |
| hidden | `(8*768 -> H) x 2`, shared, `--hidden 512\|1024`, `--act screlu\|crelu` | `HIDDEN`, `act` from the file's metadata |
| output buckets | `BiniMaterial<8>` = `min(7, (pieces-1)*8/32)` (custom `OutputBuckets` impl) | `out_bucket()` / `nnue_eval`: `min(NO-1, (pieces-1)*NO//32)` |
| output | `l1.forward(stm.concat(ntm)).select(bucket)`, side to move first; `eval_scale = 400` | `(Σ act·w2[ob,:H] + Σ act·w2[ob,H:] + b2[ob]) // b2[NO]` = centipawns |

Why not bullet's `MaterialCount<8>`: it buckets by `(pieces-2)/4` (2-5→0, 6-9→1, …, 30-32→7) while
the engine hard-codes `(pieces-1)//4` capped at 7 (2-4→0, 5-8→1, …, 29-32→7). Eight of the 31 piece
counts (5, 9, 13, …, 29) would land in a neighbouring bucket and an exporter cannot re-bucket a
trained output layer, so the trainer reproduces Bini's formula instead (it is 5 lines; the trait
is public).

WDL convention: the target is `wdl * game_result + (1 - wdl) * sigmoid(score/400)`, i.e. `--wdl`
is the weight of the game result (bullet's convention) = `1 - train_nnue.py --wdl`.

## Checkpoint contents (`<out>/<net-id>-<superbatch>/`)

| file | content |
|---|---|
| `raw.bin` | f32 little-endian, no header, no padding, **untransformed** weights in save-format order: `l0w` `[8*768][H]` (column-major `H x 6144`, so each input feature's H weights are contiguous), `l0b` `[H]`, `l1w` `[2H][8]` (column-major `8 x 2H`: for each hidden index j the 8 bucket weights are contiguous), `l1b` `[8]`; with `--factorise` additionally `l0f` `[768][H]` **not merged** into `l0w` |
| `quantised.bin` | bullet's usual i16 file (l0w+factoriser ×255 rounded, l0b ×255, l1w ×64 transposed, l1b ×255·64, padded to 64 bytes with "bullet") — not used by Bini |
| `optimiser_state/weights.bin` | named f32 tensors: for each weight (sorted by id) `id\n`, `u64` element count, f32 LE values; the exporter accepts this file too |
| `optimiser_state/*` | AdamW moments, for `--resume` |
| `log.txt` | `superbatch,batch,loss` |

`raw.bin` size = `4 * (6144*H + H + 2*H*8 + 8 [+ 768*H])` bytes, e.g. H=512: 12,648,480 bytes
(14,221,344 with the factoriser); H=1024: 25,296,928 (28,442,656). The exporter auto-detects the
factoriser from the size.

## Build

Needs Rust ≥ 1.87 (edition 2024) and, for the GPU, the CUDA toolkit with `CUDA_PATH` pointing at
the install (contains `bin`, `lib`, `include`). Build on the training box, not the Mac:

```sh
curl https://sh.rustup.rs -sSf | sh -s -- -y && . "$HOME/.cargo/env"
export CUDA_PATH=/usr/local/cuda            # adjust; nvcc must be on PATH
cd bini_v5/tools/bullet_trainer
cargo build --release --features cuda        # first build fetches and compiles bullet (~10 min)
```

Without a GPU (`cargo build --release`) bullet falls back to a mock device: it compiles and runs
but does not train; useful only to check the binary parses arguments. AMD: `--features rocm`,
macOS: `--features metal` (untested here).

## Data

`--data` takes bulletformat files (32-byte `ChessBoard` records; `bini_v5/tools/bulletformat.py`
writes them from our `.npz` chunks or from Stockfish binpacks). Shuffle/interleave them first
(`cargo b -r --package bullet-utils` inside a bullet clone, or `bulletformat.py`'s shuffle).
`--binpack` reads Stockfish `.binpack` files directly through bullet's `SfBinpackLoader` (plain
dependency of the crate, no extra cargo feature) with the filter from bullet's example
(`ply >= 16`, not in check, `|score| <= 10000`, best move a quiet normal move; relax with
`--keep-captures --keep-checks --min-ply --max-score`).

## Run

Smoke test (a couple of minutes on any GPU, one checkpoint):

```sh
./target/release/bini_bullet_trainer --data /data/bini/sample.bin \
    --hidden 512 --act screlu --superbatches 1 --batches-per-superbatch 64 --batch-size 16384 \
    --save-rate 1 --out /data/bini/ckpt --net-id smoke
python3 ../bullet_export.py --checkpoint /data/bini/ckpt/smoke-1 --hidden 512 --act screlu \
    --out /data/bini/smoke.safetensors
```

Real run (100 M positions per superbatch at the defaults 16384 x 6104):

```sh
./target/release/bini_bullet_trainer --data /data/bini/shuffled_*.bin \
    --hidden 1024 --act screlu --wdl 0.25 --lr 0.001 --lr-schedule cosine --superbatches 400 \
    --save-rate 20 --threads 8 --out /data/bini/ckpt --net-id bini1024
```

`--resume DIR --start-superbatch N` continues from a checkpoint's `optimiser_state`.
Run with `--help` for every option. The binary prints the king-bucket table and the piece-count →
output-bucket map at start-up so a log always records the mapping the exporter assumes.

## Export

```sh
python3 bini_v5/tools/bullet_export.py --checkpoint ckpt/bini1024-400 --hidden 1024 --act screlu \
    --out bini_v5/nnue.safetensors [--out-scale 1.0]
BINI_NNUE=bini_v5/nnue.safetensors python3 bini_v5/tests/test_nnue.py
```

## Not verified here

No Rust toolchain on the Mac (`cargo` absent), so `src/main.rs` has not been compiled. It follows
`examples/progression/3_input_buckets.rs` and `examples/simple.rs` of the pinned revision line by
line (builder chain, save format, loader constructors, sfbinpack filter); the only additions are a
custom `OutputBuckets` impl, own `LrScheduler`/`WdlScheduler` impls (trait methods `lr`/`blend` +
`colourful`) and a hand-rolled argument parser. Expect at most trivial fixes at first compile.
