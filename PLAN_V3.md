# Plan V3 — from second to a clear first

Saved Sun 6 Sept 2026, 07:30. Living document; PLAN.md carries the full history.

## The plan

Evidence: site move grades — AlphaFish 90.3% best/excellent, 0.7% errors, flat 1.7 s/move (max
4.4 s), 9/11 vs top-12, its only loss a 102-ply middlegame; places 2–6 at 85–90% / 0.9–1.6%; our v2
centipawn loss 11.3 vs AlphaFish 6.3 and peers 18–28. v2 is likely second strongest today.

Levers, by Elo per day:
1. Evaluation v3: ~320M quiet Lichess positions + Stockfish-labelled whole-game positions, 6–8
   epochs; then a fine-tune on positions from our own search trees labelled at depth 12. Gate:
   300 games vs v2 + real-clock centipawn loss (target < 8).
2. Search: batch 1 (singular/multi-cut, IIR, qsearch TT) under gate; batch 2 capture history,
   continuation history, history-driven LMR, staged move generation (+10–20% nps).
3. Conversion: mop-up on top of the net, halfmove-clock-aware progress bonus when winning, KPK
   bitbase at import, a won-endgame conversion suite at the real clock; contempt re-tuned.
4. Time: finish with 10–15 s (field: 20–40 s), spend on swings, save when decided; tuned from
   ladder logs. AlphaFish's flat allocation is the structural edge in sharp middlegames.
5. Book from Elite games, Monday, only if the arena says so.
Not doing: opponent-specific behaviour or untestable sharpness terms.

Schedule: Sun batch-1 gate → v2.1, stream 150M more, start v3 tonight; Mon v3 gate, batch 2,
conversion + endgame suite, book; Tue own-search fine-tune, SF 2600/2800 ladder; Wed freeze,
1,000-game regression, package; Thu final upload (afternoon); Fri rollback only.

## Standing rules

- Nothing ships without a gate: 200+ games at 10 s + 0.1 s against the current shipped build,
  zero failures, plus a real-clock check for anything touching time or conversion.
- The shipped build is tagged in git (`v2-upload` today); rollback is one command.
- Local measurements are taken on a quiet machine; the training GPU job is the only background
  load allowed during gates.
- Intel refreshes (leaderboard snapshots, our rated results, site move grades) are requested
  from the intel agent after each block of rated rounds and folded into the calibration.

## Definition of done for V3

- Real-clock centipawn loss under 8 (AlphaFish: 6.3), blunder rate under 0.3%.
- 65%+ against the v2 build over 300 games; conversion suite 10/10 against Stockfish's defence.
- Site move grades on rated games at or above AlphaFish's 90% best/excellent.
- Compile under 45 s on the EPYC, zero failures across 1,000 local games.
