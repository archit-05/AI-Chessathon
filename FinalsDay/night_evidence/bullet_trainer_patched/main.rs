//! Bini NNUE trainer on top of `bullet` (github.com/jw1912/bullet, revision pinned in Cargo.toml).
//!
//! The network is exactly what bini_v5/bini_nnue.py evaluates:
//!   inputs  : ChessBucketsMirrored with Bini's 8-bucket king table (KING_BUCKETS below);
//!             a perspective whose king stands on files e-h is mirrored (feature ^ 7, i.e. file flip)
//!   hidden  : (8 x 768 -> HIDDEN) per perspective, shared weights, activation crelu | screlu
//!   output  : one linear row per output bucket (OUT_BUCKETS = 8, by piece count, Bini's formula)
//!   eval    : 400 * output = centipawns from the side to move (eval_scale = 400, like CP_SCALE)
//!
//! Differences to Bini's own trainer that the exporter (tools/bullet_export.py) absorbs:
//!   * feature order inside a king bucket is bullet's  (opp * 6 + type) * 64 + sq
//!     whereas Bini uses                                (type * 2 + opp) * 64 + sq
//!   * the raw weights are float, column-major, in the order of the save format below
//!
//! Output buckets: bullet's `MaterialCount<8>` uses (pieces - 2) / 4 (2-5 -> 0, 6-9 -> 1, ...,
//! 30-32 -> 7); Bini's engine hard-codes min(7, (pieces - 1) * 8 / 32) (2-4 -> 0, 5-8 -> 1, ...,
//! 29-32 -> 7). The exporter cannot re-bucket a trained net, so `BiniMaterial` below reproduces
//! Bini's formula and is what this trainer uses.
//!
//! Saved per checkpoint (<out>/<net-id>-<superbatch>/):
//!   raw.bin              f32 LE, no padding: l0w [8*768][H], l0b [H], l1w [2H][8], l1b [8]
//!                        (+ l0f [768][H] when --factorise; NOT merged into l0w in raw.bin)
//!   quantised.bin        bullet's usual i16 layout (l1w transposed, l0f merged) - unused by Bini
//!   optimiser_state/     weights.bin (named f32 tensors) + AdamW moments; used by --resume
//!
//! Target: sigmoid(output) is fitted to  wdl * result + (1 - wdl) * sigmoid(score / 400),
//! so --wdl is the weight of the GAME RESULT (bullet's convention) = 1 - train_nnue.py's --wdl.

use std::{f32::consts::PI, sync::OnceLock};

use bullet_lib::{
    game::{
        formats::bulletformat::ChessBoard,
        inputs::{ChessBucketsMirrored, get_num_buckets},
        outputs::OutputBuckets,
    },
    nn::{
        InitSettings, Shape,
        optimiser::{AdamW, AdamWParams},
    },
    trainer::{
        save::SavedFormat,
        schedule::{TrainingSchedule, TrainingSteps, lr::LrScheduler, wdl::WdlScheduler},
        settings::LocalSettings,
    },
    value::{
        ValueTrainerBuilder,
        loader::{
            DirectSequentialDataLoader,
            sfbinpack::{MoveType, PieceType, SfBinpackLoader, TrainingDataEntry},
        },
    },
};

const NUM_KING_BUCKETS: usize = 8;
const OUT_BUCKETS: usize = 8;
const EVAL_SCALE: f32 = 400.0;

/// Bini's `_king_table(8)` as bullet's 32-entry array: index = rank * 4 + file' with
/// file' = [0, 1, 2, 3, 3, 2, 1, 0][file] (files e-h fold onto d-a, exactly Bini's `f ^ 7`).
/// Rank 1: files a-b -> 0, c-d -> 1; rank 2: 2 / 3; ranks 3-4: 4 / 5; ranks 5-8: 6 / 7.
#[rustfmt::skip]
const KING_BUCKETS: [usize; 32] = [
    0, 0, 1, 1, // rank 1
    2, 2, 3, 3, // rank 2
    4, 4, 5, 5, // rank 3
    4, 4, 5, 5, // rank 4
    6, 6, 7, 7, // rank 5
    6, 6, 7, 7, // rank 6
    6, 6, 7, 7, // rank 7
    6, 6, 7, 7, // rank 8
];

const _: () = assert!(get_num_buckets(&KING_BUCKETS) == NUM_KING_BUCKETS);

/// Bini's output bucket: min(N - 1, (pieces - 1) * N / 32), pieces = all men on the board (2..=32).
#[derive(Clone, Copy, Default)]
struct BiniMaterial<const N: usize>;

impl<const N: usize> OutputBuckets<ChessBoard> for BiniMaterial<N> {
    const BUCKETS: usize = N;

    fn bucket(&self, pos: &ChessBoard) -> u8 {
        let pieces = pos.occ().count_ones() as usize;
        (((pieces - 1) * N / 32).min(N - 1)) as u8
    }
}

// ------------------------------------------------------------------------------------------------
// Schedulers (own types so the shape is chosen at runtime from the CLI; formulas mirror bullet's
// CosineDecayLR / LinearDecayLR / ExponentialDecayLR / StepLR / ConstantLR / Warmup and LinearWDL)
// ------------------------------------------------------------------------------------------------

#[derive(Clone, Copy, Debug, PartialEq)]
enum LrKind {
    Cosine,
    Linear,
    Exponential,
    Step,
    Constant,
}

#[derive(Clone, Debug)]
struct BiniLr {
    kind: LrKind,
    initial: f32,
    final_lr: f32,
    final_superbatch: usize,
    gamma: f32,
    step: usize,
    warmup_batches: usize,
}

impl LrScheduler for BiniLr {
    fn lr(&self, batch: usize, superbatch: usize) -> f32 {
        let progress = superbatch as f32 / self.final_superbatch.max(1) as f32;
        let base = match self.kind {
            LrKind::Constant => self.initial,
            LrKind::Cosine => {
                if superbatch >= self.final_superbatch {
                    self.final_lr
                } else {
                    let lambda = 1.0 - 0.5 * (1.0 + (PI * progress).cos());
                    self.initial + lambda * (self.final_lr - self.initial)
                }
            }
            LrKind::Linear => {
                if superbatch >= self.final_superbatch {
                    self.final_lr
                } else {
                    self.initial + progress * (self.final_lr - self.initial)
                }
            }
            LrKind::Exponential => {
                if superbatch >= self.final_superbatch {
                    self.final_lr
                } else {
                    self.initial * (self.final_lr / self.initial).powf(progress)
                }
            }
            LrKind::Step => {
                let steps = superbatch.saturating_sub(1) / self.step.max(1);
                self.initial * self.gamma.powi(steps as i32)
            }
        };
        if superbatch == 1 && batch < self.warmup_batches {
            // linear ramp from base / warmup_batches up to base over the first superbatch's batches
            base * (batch + 1) as f32 / self.warmup_batches as f32
        } else {
            base
        }
    }

    fn colourful(&self) -> String {
        format!(
            "{:?} lr {} -> {} over {} superbatches (gamma {}, step {}, warmup {} batches)",
            self.kind, self.initial, self.final_lr, self.final_superbatch, self.gamma, self.step, self.warmup_batches
        )
    }
}

/// WDL blend = weight of the game result in the target; linear taper from `start` (superbatch 1)
/// to `end` (final superbatch). start == end is a constant blend.
#[derive(Clone, Debug)]
struct BiniWdl {
    start: f32,
    end: f32,
}

impl WdlScheduler for BiniWdl {
    fn blend(&self, _batch: usize, superbatch: usize, max: usize) -> f32 {
        let grad = (self.end - self.start) / (max.saturating_sub(1)).max(1) as f32;
        (self.start + grad * superbatch.saturating_sub(1) as f32).clamp(0.0, 1.0)
    }

    fn colourful(&self) -> String {
        format!("wdl (result weight) {} -> {}", self.start, self.end)
    }
}

// ------------------------------------------------------------------------------------------------
// Stockfish binpack filter (a plain `fn` so the loader's `Fn + Clone + Send + Sync + 'static`
// bound holds; the CLI-configurable thresholds live in a OnceLock)
// ------------------------------------------------------------------------------------------------

struct FilterCfg {
    min_ply: u16,
    max_abs_score: u16,
    quiet_only: bool,
    skip_in_check: bool,
}

static FILTER: OnceLock<FilterCfg> = OnceLock::new();

fn sf_filter(entry: &TrainingDataEntry) -> bool {
    let cfg = FILTER.get().expect("filter config not initialised");
    entry.ply >= cfg.min_ply
        && entry.score.unsigned_abs() <= cfg.max_abs_score
        && (!cfg.skip_in_check || !entry.pos.is_checked(entry.pos.side_to_move()))
        && (!cfg.quiet_only
            || (entry.mv.mtype() == MoveType::Normal
                && entry.pos.piece_at(entry.mv.to()).piece_type() == PieceType::None))
}

// ------------------------------------------------------------------------------------------------
// CLI
// ------------------------------------------------------------------------------------------------

struct Args {
    data: Vec<String>,
    binpack: Vec<String>,
    out: String,
    net_id: String,
    hidden: usize,
    act: String,
    factorise: bool,
    wdl: f32,
    wdl_end: Option<f32>,
    lr: f32,
    final_lr: Option<f32>,
    lr_schedule: LrKind,
    gamma: f32,
    step: usize,
    warmup_batches: usize,
    superbatches: usize,
    start_superbatch: usize,
    batch_size: usize,
    batches_per_superbatch: usize,
    save_rate: usize,
    threads: usize,
    queue: usize,
    resume: Option<String>,
    seed: u64,
    device: i32,
    binpack_buffer_mb: usize,
    min_ply: u16,
    max_score: u16,
    eval_scale: f32,
    keep_captures: bool,
    keep_checks: bool,
}

const USAGE: &str = "bini_bullet_trainer - train the Bini NNUE with bullet

  --data FILE...            bulletformat (.bin, 32-byte ChessBoard records) files, repeatable
  --binpack FILE...         Stockfish binpacks instead of --data (filtered, see --min-ply etc.)
  --out DIR                 checkpoint directory                              [checkpoints]
  --net-id NAME             checkpoint name prefix (<out>/<net-id>-<superbatch>)   [bini]
  --hidden N                accumulator size, 512 or 1024                     [512]
  --act screlu|crelu        activation                                        [screlu]
  --factorise               add a 768-feature factoriser (merged by the exporter)
  --wdl X                   weight of the game result in the target (0 = labels only)  [0.0]
  --wdl-end X               taper --wdl linearly to X at the last superbatch
  --lr X                    initial learning rate                             [0.001]
  --final-lr X              final learning rate                               [lr * 0.3^5]
  --lr-schedule KIND        cosine|linear|exponential|step|constant           [cosine]
  --gamma X --step N        for step: lr = lr * gamma^((superbatch-1)/step)   [0.1, 18]
  --warmup-batches N        linear lr warm-up over the first N batches        [0]
  --superbatches N          end superbatch                                    [40]
  --start-superbatch N      first superbatch (with --resume)                  [1]
  --batch-size N                                                              [16384]
  --batches-per-superbatch N                                                  [6104]
  --save-rate N             checkpoint every N superbatches (and at the end)  [10]
  --threads N               data-loading threads                              [4]
  --queue N                 batch queue size                                  [64]
  --resume DIR              load <DIR>/optimiser_state of an earlier checkpoint
  --seed N                                                                    [198273612]
  --device N                GPU ordinal                                       [0]
  --binpack-buffer-mb N     binpack shuffle buffer                            [1024]
  --min-ply N               binpack filter: skip positions before this ply   [16]
  --max-score N             binpack filter: skip |score| above this          [10000]
  --eval-scale X            score units per sigmoid unit (400 = UCI cp; binpacks: 400*k)  [400]
  --keep-captures           binpack filter: keep positions whose best move captures/promotes
  --keep-checks             binpack filter: keep positions with the side to move in check
";

fn take(argv: &[String], i: &mut usize, key: &str) -> String {
    *i += 1;
    argv.get(*i).cloned().unwrap_or_else(|| {
        eprintln!("{key} needs a value\n{USAGE}");
        std::process::exit(2)
    })
}

fn num<T: std::str::FromStr>(s: &str, key: &str) -> T {
    s.parse().unwrap_or_else(|_| {
        eprintln!("bad value {s:?} for {key}");
        std::process::exit(2)
    })
}

fn parse_args() -> Args {
    let mut a = Args {
        data: Vec::new(),
        binpack: Vec::new(),
        out: "checkpoints".to_string(),
        net_id: "bini".to_string(),
        hidden: 512,
        act: "screlu".to_string(),
        factorise: false,
        wdl: 0.0,
        wdl_end: None,
        lr: 0.001,
        final_lr: None,
        lr_schedule: LrKind::Cosine,
        gamma: 0.1,
        step: 18,
        warmup_batches: 0,
        superbatches: 40,
        start_superbatch: 1,
        batch_size: 16_384,
        batches_per_superbatch: 6104,
        save_rate: 10,
        threads: 4,
        queue: 64,
        resume: None,
        seed: 198_273_612,
        device: 0,
        binpack_buffer_mb: 1024,
        min_ply: 16,
        max_score: 10_000,
        eval_scale: EVAL_SCALE,
        keep_captures: false,
        keep_checks: false,
    };
    let argv: Vec<String> = std::env::args().skip(1).collect();
    let mut i = 0;
    while i < argv.len() {
        let key = argv[i].clone();
        match key.as_str() {
            "-h" | "--help" => {
                println!("{USAGE}");
                std::process::exit(0);
            }
            "--data" | "--binpack" => {
                // consume every following non-option token
                while i + 1 < argv.len() && !argv[i + 1].starts_with("--") {
                    i += 1;
                    if key == "--data" {
                        a.data.push(argv[i].clone());
                    } else {
                        a.binpack.push(argv[i].clone());
                    }
                }
            }
            "--out" => a.out = take(&argv, &mut i, &key),
            "--net-id" => a.net_id = take(&argv, &mut i, &key),
            "--hidden" => a.hidden = num(&take(&argv, &mut i, &key), &key),
            "--act" => a.act = take(&argv, &mut i, &key),
            "--factorise" | "--factorize" => a.factorise = true,
            "--wdl" => a.wdl = num(&take(&argv, &mut i, &key), &key),
            "--wdl-end" => a.wdl_end = Some(num(&take(&argv, &mut i, &key), &key)),
            "--lr" => a.lr = num(&take(&argv, &mut i, &key), &key),
            "--final-lr" => a.final_lr = Some(num(&take(&argv, &mut i, &key), &key)),
            "--lr-schedule" => {
                a.lr_schedule = match take(&argv, &mut i, &key).as_str() {
                    "cosine" => LrKind::Cosine,
                    "linear" => LrKind::Linear,
                    "exponential" => LrKind::Exponential,
                    "step" => LrKind::Step,
                    "constant" => LrKind::Constant,
                    other => {
                        eprintln!("unknown --lr-schedule {other}");
                        std::process::exit(2)
                    }
                }
            }
            "--gamma" => a.gamma = num(&take(&argv, &mut i, &key), &key),
            "--step" => a.step = num(&take(&argv, &mut i, &key), &key),
            "--warmup-batches" => a.warmup_batches = num(&take(&argv, &mut i, &key), &key),
            "--superbatches" => a.superbatches = num(&take(&argv, &mut i, &key), &key),
            "--start-superbatch" => a.start_superbatch = num(&take(&argv, &mut i, &key), &key),
            "--batch-size" => a.batch_size = num(&take(&argv, &mut i, &key), &key),
            "--batches-per-superbatch" => a.batches_per_superbatch = num(&take(&argv, &mut i, &key), &key),
            "--save-rate" => a.save_rate = num(&take(&argv, &mut i, &key), &key),
            "--threads" => a.threads = num(&take(&argv, &mut i, &key), &key),
            "--queue" => a.queue = num(&take(&argv, &mut i, &key), &key),
            "--resume" => a.resume = Some(take(&argv, &mut i, &key)),
            "--seed" => a.seed = num(&take(&argv, &mut i, &key), &key),
            "--device" => a.device = num(&take(&argv, &mut i, &key), &key),
            "--binpack-buffer-mb" => a.binpack_buffer_mb = num(&take(&argv, &mut i, &key), &key),
            "--min-ply" => a.min_ply = num(&take(&argv, &mut i, &key), &key),
            "--max-score" => a.max_score = num(&take(&argv, &mut i, &key), &key),
            "--eval-scale" => a.eval_scale = num(&take(&argv, &mut i, &key), &key),
            "--keep-captures" => a.keep_captures = true,
            "--keep-checks" => a.keep_checks = true,
            other => {
                eprintln!("unknown option {other}\n{USAGE}");
                std::process::exit(2);
            }
        }
        i += 1;
    }
    if a.data.is_empty() == a.binpack.is_empty() {
        eprintln!("give exactly one of --data FILE... or --binpack FILE...\n{USAGE}");
        std::process::exit(2);
    }
    if a.act != "screlu" && a.act != "crelu" {
        eprintln!("--act must be screlu or crelu");
        std::process::exit(2);
    }
    if a.hidden == 0 || a.hidden % 32 != 0 {
        eprintln!("--hidden must be a positive multiple of 32 (512 or 1024 for Bini)");
        std::process::exit(2);
    }
    if a.save_rate == 0 || a.superbatches == 0 || a.start_superbatch == 0 || a.start_superbatch > a.superbatches {
        eprintln!("need 1 <= --start-superbatch <= --superbatches and --save-rate >= 1");
        std::process::exit(2);
    }
    a
}

fn print_tables() {
    println!("king buckets (bucket*2+mirror per square from the perspective's own view, a1 = 0):");
    for rank in (0..8).rev() {
        let row: Vec<String> = (0..8)
            .map(|file| {
                let mirror = usize::from(file > 3);
                let ff = if mirror == 1 { 7 - file } else { file };
                format!("{:2}", KING_BUCKETS[rank * 4 + ff] * 2 + mirror)
            })
            .collect();
        println!("  rank {} : {}", rank + 1, row.join(" "));
    }
    let mut line = String::from("output bucket by piece count:");
    for pieces in 2..=32usize {
        line.push_str(&format!(" {pieces}->{}", ((pieces - 1) * OUT_BUCKETS / 32).min(OUT_BUCKETS - 1)));
    }
    println!("{line}");
}

fn main() {
    let args = parse_args();
    let hidden = args.hidden;
    let screlu = args.act == "screlu";
    let factorise = args.factorise;
    let final_lr = args.final_lr.unwrap_or(args.lr * 0.3f32.powi(5));

    let _ = FILTER.set(FilterCfg {
        min_ply: args.min_ply,
        max_abs_score: args.max_score,
        quiet_only: !args.keep_captures,
        skip_in_check: !args.keep_checks,
    });

    println!(
        "bini_bullet_trainer: {}x768 -> {}x2 -> {} ({}), factoriser {}, eval scale {}",
        NUM_KING_BUCKETS, hidden, OUT_BUCKETS, args.act, factorise, args.eval_scale
    );
    print_tables();

    // Save format. Only entries with an id reach raw.bin (raw f32, untransformed, in this order);
    // quantised.bin applies the transforms/quantisation and is bullet's usual layout.
    let l0w = SavedFormat::id("l0w");
    let l0w = if factorise {
        l0w.transform(|store, weights| {
            let factoriser = store.get("l0f").values.f32().repeat(NUM_KING_BUCKETS);
            weights.into_iter().zip(factoriser).map(|(a, b)| a + b).collect()
        })
    } else {
        l0w
    };
    let mut fmt: Vec<SavedFormat> = vec![
        l0w.round().quantise::<i16>(255),
        SavedFormat::id("l0b").round().quantise::<i16>(255),
        SavedFormat::id("l1w").round().quantise::<i16>(64).transpose(),
        SavedFormat::id("l1b").round().quantise::<i16>(255 * 64),
    ];
    if factorise {
        // appended so raw.bin carries the (unmerged) factoriser after l1b
        fmt.push(SavedFormat::id("l0f").round().quantise::<i16>(255));
    }

    let mut trainer = ValueTrainerBuilder::default()
        .dual_perspective()
        .optimiser(AdamW)
        .inputs(ChessBucketsMirrored::new(KING_BUCKETS))
        .output_buckets(BiniMaterial::<OUT_BUCKETS>)
        .save_format(&fmt)
        .loss_fn(|output, target| output.sigmoid().squared_error(target))
        .seed(args.seed)
        .use_device(args.device)
        .build(move |builder, stm, ntm, buckets| {
            let mut l0 = builder.new_affine("l0", 768 * NUM_KING_BUCKETS, hidden);
            if factorise {
                let l0f = builder.new_weights("l0f", Shape::new(hidden, 768), InitSettings::Zeroed);
                l0.weights = l0.weights + l0f.repeat(NUM_KING_BUCKETS);
            }
            let l1 = builder.new_affine("l1", 2 * hidden, OUT_BUCKETS);

            let stm_acc = l0.forward(stm);
            let ntm_acc = l0.forward(ntm);
            let (stm_hidden, ntm_hidden) =
                if screlu { (stm_acc.screlu(), ntm_acc.screlu()) } else { (stm_acc.crelu(), ntm_acc.crelu()) };
            // side to move first, then the other side: w2[b, :H] . act(acc_stm) + w2[b, H:] . act(acc_nstm)
            l1.forward(stm_hidden.concat(ntm_hidden)).select(buckets)
        });

    if factorise {
        // the merged weight l0w + l0f must stay inside the i16/255 range at export
        let clip = AdamWParams { max_weight: 0.99, min_weight: -0.99, ..Default::default() };
        trainer.optimiser.set_params_for_weight("l0w", clip);
        trainer.optimiser.set_params_for_weight("l0f", clip);
    }

    if let Some(dir) = &args.resume {
        trainer.load_from_checkpoint(dir);
        println!("resumed from {dir}");
    }

    let schedule = TrainingSchedule {
        net_id: args.net_id.clone(),
        eval_scale: args.eval_scale,
        steps: TrainingSteps {
            batch_size: args.batch_size,
            batches_per_superbatch: args.batches_per_superbatch,
            start_superbatch: args.start_superbatch,
            end_superbatch: args.superbatches,
        },
        wdl_scheduler: BiniWdl { start: args.wdl, end: args.wdl_end.unwrap_or(args.wdl) },
        lr_scheduler: BiniLr {
            kind: args.lr_schedule,
            initial: args.lr,
            final_lr,
            final_superbatch: args.superbatches,
            gamma: args.gamma,
            step: args.step,
            warmup_batches: args.warmup_batches,
        },
        save_rate: args.save_rate,
    };

    let settings = LocalSettings {
        threads: args.threads,
        test_set: None,
        output_directory: args.out.as_str(),
        batch_queue_size: args.queue,
    };

    if !args.binpack.is_empty() {
        let paths: Vec<&str> = args.binpack.iter().map(String::as_str).collect();
        let loader = SfBinpackLoader::new_concat_multiple(&paths, args.binpack_buffer_mb, args.threads, sf_filter);
        trainer.run(&schedule, &settings, &loader);
    } else {
        let paths: Vec<&str> = args.data.iter().map(String::as_str).collect();
        let loader = DirectSequentialDataLoader::new(&paths);
        trainer.run(&schedule, &settings, &loader);
    }

    // sanity: raw network output (x eval scale = centipawns for the side to move)
    for fen in [
        "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKB1R w KQkq - 0 1",
        "8/8/4k3/8/8/4K3/4P3/8 w - - 0 1",
    ] {
        println!("eval {:8.1} cp  {fen}", EVAL_SCALE * trainer.eval(fen));
    }
    println!("done: checkpoints in {}/{}-<superbatch>/ (raw.bin -> tools/bullet_export.py)", args.out, args.net_id);
}
