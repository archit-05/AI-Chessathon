# Astra — Loss Investigation, Evidence Table & Release Recommendation
**11 September 2026. No upload performed or authorized here; owner decides.**

## 0. Frozen baseline (hashed — `FREEZE_MANIFEST.txt`)
- Deployed **V8 = fc_b-104** net (`__metadata__.bullet_file = /root/chess/data/ckpt/fc_b-104/raw.bin`), **not k24**.
- V8 and every `bini_astra_*` candidate share **byte-identical net + book**; candidates differ from V8 **only in `bini_search.py`** (and `bini_board.py` for the C2 line). All preserved untouched. Gate checkpoints preserved (`gate_mirror/`, and resumed on box2).

## 1. Method (per the review constraints)
Each target reconstructed from the PGN with **full legal history**; reproduced via the **real iterative-deepening path** (`think`), not single fixed-depth searches; every search **checked `I_ABORT==0`** with nodes/depth/TT recorded; search **amount controlled via equal-node** (`think(max_nodes)`); referenced against **deep Stockfish d24** (history-free — valid for the non-repetition target positions; R104 endgame to re-check with preserved history). **Live TT is unavailable**; reconstructed context is *not* an exact live-cache reproduction.

## 2. Confirmed causes
| Target | Reproduced? | SF verdict (our move → best) | Cause |
|---|---|---|---|
| **R105 m41 Rfe2** | **Yes** — `think` converges to Rfe2 at d18–20 | Rfe2 **−474** vs **Qe2 −28** (regret 446) | **Net eval resolution** |
| **R103 m35 Bb7** | **Yes** — converges to Bb7 at d21–25 | Bb7 **−670** vs **Kf7 −13** (regret 657) | **Net eval resolution** |
| **R104 conversion 59→83** | trajectory reproduced | +673 at **59.Qd5** (best) → +22 (m70) → **−558** (m81) | **Net eval / conversion** (NOT an unsound sac) |

**Common cause:** the fc_b-104 net **cannot reliably rank a holding move above a losing one** in these positions — it compresses a 400–650 cp Stockfish gap into ~100 cp. Ruled out: **rule bugs** (terminals fire correctly); **search features** (equal-node ablation *inconsistent* — only `no_CONT` recovers R105's Qe2; `no_CORR/no_SEEP/no_NMP` recover R103's Kf7 but `no_CONT` doesn't — no single feature, and disabling core features would regress broadly); **time/depth** (deeper search *entrenches* the blunder); **opening book** (book exits were fine).

## 3. Verified repairs
| Repair | Status | Evidence |
|---|---|---|
| **v5 terminal/draw/repetition correctness** (C1/C1b/C1c/C1d/C2/C2b, `bini_astra_v5`) | **Verified on the exact candidate** | `test_repro` **22/22** vs V8 **7 fail** (incl. 6 dead-material classes: bare KvK etc.; qsearch stalemate; mate-on-100th-halfmove; repetition indexing). `test_v2` **12/12** (C1b max-ply, C2b referee-agreement, all 8 buckets). **Cost:** depth-10 bench V8 364 → v5 350 knps, **+5.8% wall** (Mac; larger than the prior ~1% claim — reconcile on x86; eval changes *only* where the rule fires). |

**Important:** v5 fixes real **rule violations** but **did not cause the recent losses** (those are eval-resolution, not rule bugs). So v5 is a **correctness** improvement, **not** a strength improvement.

## 4. Unresolved hypotheses (left unchanged, gaps reported)
- **R100 m29 Rfa1:** **not reproducible** — `think` finds the save **Qb2** at every node budget (1M–8M). The game's Rfa1 depended on **live warm-TT context (unavailable)**; likely the known **TT-context (C4)** interaction. No repair attempted.
- **Net fine-tune (the real strength fix): BLOCKED** — fc_b-104's float checkpoint is not in the local mirror, not on box2 (`/root/chess` empty), not reconstructable from logs. Requires reviving the dead GPU box to recover `fc_b-104/raw.bin`.
- **R98 book exit / R104 endgame-with-history:** not deeply examined; consistent with the eval class; **no evidence** justifies a book change.

## 5. Release recommendation (gates COMPLETE)
**No validated strength improvement exists for this lock window** — the losses are eval-driven, the eval fix is checkpoint-blocked, and no search-feature or time-management repair is justified by the evidence.

Completed 120+0.5 colour-paired gates on the **exact packaged builds** (box2, 400 games each, build hashes matched to the verified candidates; **0 rejected, 0 fallbacks/flags/nnue-off both arms** in all three):

| gate | comparison | Elo (95% CI, pentanomial) | W–D–L |
|---|---|---|---|
| A | **v5 vs V8** (ship decision) | **−3.5 [−15.3, +8.3]** | 28–340–32 |
| B | v5_noc2b vs V8 | −4.3 [−18.5, +9.8] | 31–333–36 |
| C | v5 vs v5_noc2b (isolates C2b) | −7.8 [−21.1, +5.5] | 28–335–37 |

- **v5 and v5_noc2b are both non-inferior to V8** (predeclared bar: lower bound > −20). Point estimates ~−3 to −4 (consistent with the measured speed cost); CIs span 0; all clean.
- **C2b (repetition policy) is the least-clean element** — its isolation gate lower bound (−21.1) just breaches −20 — so the maximally conservative correctness build is **v5_noc2b** (drops C2b).
- **No build improves the eval-driven losses.**

**Options (owner decides — no automatic upload):**
1. **Lock V8** — zero-change incumbent, safe default. (`submission_v8_0910_0313.zip`, sha256 `47ace193…`.)
2. **Lock v5** — validated non-inferior (−3.5 [−15.3,+8.3]), clean, exact package; fixes 7 verified rule violations (incl. the `endgame_scale` bug implicated in R102's drawn liquidation). A correctness upgrade at no measurable strength cost.
3. **Lock v5_noc2b** — conservative correctness option: same terminal fixes minus the behaviorally-riskiest change (C2b), also non-inferior (−4.3 [−18.5,+9.8]).
- **Do not** ship any unvalidated change.

**Future build (the real fix):** recover fc_b-104's checkpoint → fine-tune to improve eval *resolution* on these position types (loss positions + deep-SF labels + preserved-good-play controls, **validation split by game**) → validate at tournament clock.

## 6. Rollback
`submission_v8_0910_0313.zip` (sha256 `47ace193…`) = current live = rollback. Untouched.
