# Task: opponent intelligence on the AI Chessathon top 10

You are working in the repository at `/Users/architbhardwaj/Desktop/AI Chessathon` (git, branch
`main`). Our engine lives in `bini/`; **do not modify anything under `bini/`, `aichessathon-starter/`
or `data/`**, and do not run our engine. Other long-running jobs (training, arenas) may be using the
CPU: run everything you start under `nice -n 15`, use at most one Stockfish process at a time, and
keep total extra CPU to roughly one core. Python: use
`/Users/architbhardwaj/Desktop/AI Chessathon/aichessathon-starter/.venv/bin/python` (it has
python-chess, numpy, torch). Stockfish 19 is installed at `/opt/homebrew/bin/stockfish`.

## Goal

Build and maintain a dossier on every team in the top 10 of https://aichessathon.com/leaderboard
(plus us, team "Opus Carlsen", bot "Bini"), so we know each opponent's strengths, weaknesses and
habits and can recalibrate our build against them. Output goes in a new folder `intel/` as plain
text files that a human reviews, plus the raw data and a script that refreshes everything in one
command. Commit when done (message: "intel: <what>"; add
`Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>` as the last line).

## What already exists (reuse, do not rewrite)

- `bini/tools/scrape_games.py <team name or uuid> <out.pgn>` downloads every public game of a
  team. Site structure: the leaderboard rows carry `data-href="/team/<uuid>?from=lb"`; a team page
  links `/game/<uuid>`; each game page embeds the full PGN (with `[%clk ...]` per move and a
  `[FEN]` start position, since rated games start from curated openings) in an
  `href="data:application/x-chess-pgn;charset=utf-8,..."` attribute (URL-encoded).
- `bini/tools/cpl.py games.pgn --nodes 120000 [--player NAME]` prints mean/median centipawn loss
  and blunder rate per player using Stockfish. Note: its output is sorted by centipawn loss, so
  use `--player` to make sure the team's own row is printed.
- `data/opp_games/*.pgn` holds games scraped on 5 Sept 23:45 for AlphaFish, Capablanca, Anchoa,
  Mate in One, Patzer 1.2 and Opus Carlsen; refresh them.
- The leaderboard page also renders a per-team rating history (rating after each rated round)
  on the team page; house bots are labelled and show a CCRL rating.

## Deliverables (all under `intel/`)

1. `intel/refresh.sh` — one command that re-scrapes the current top 10 (+ Opus Carlsen), re-runs
   the analysis and regenerates every file below. Idempotent; skips games already downloaded.
2. `intel/raw/<team>.pgn` and `intel/raw/<team>.json` — the games and the extracted per-game
   facts (round, colour, opponent, opponent rating at the time if visible, opening name from the
   game page, start FEN, result, termination, number of own moves, time used per move from the
   clocks, final clock, our estimate of eval swing).
3. `intel/<rank>_<team>.txt` — one dossier per team, 60–120 lines, written for a strong chess
   player who will read it in two minutes. Sections, in this order:
   - **Identity**: bot name, team name, university, solo or team, rank, rating, record,
     rating trajectory (first rated round, peak, current; any jump of 100+ points between rounds
     suggests a new upload — list those rounds).
   - **Results by opponent tier**: score vs top-10 teams, vs ranks 11–50, vs the rest; list
     every game vs another top-10 team with result and termination.
   - **Move quality**: mean and median centipawn loss, blunder rate (>=200cp), split by game
     phase (moves 1–15 of their own from the start FEN, 16–40, 41+) and by colour. State the
     Stockfish node count used so numbers are comparable across teams.
   - **Time management**: seconds per move (mean, median, max), how much clock is left at the end,
     whether they ever drop under 5 s, whether spending rises in complex positions (compare time
     spent on moves where the evaluation swung by >100cp vs the rest). Flag anything exploitable
     (fixed time per move, panic at low clock, unused time).
   - **Draw behaviour**: how their draws arise (threefold, fifty-move, insufficient material,
     ply cap), and crucially whether they repeat while *ahead* (eval > +150 at the repetition) or
     only while behind. Count each case.
   - **Endgame conversion**: games where they were +300 or better and did not win; games where
     they were −300 or worse and did not lose. Note the reasons if visible (fifty-move drift,
     shuffling, no mating technique).
   - **Openings**: which curated openings they got, results by opening family, any family where
     they underperform; whether their play in the first 6 own moves matches Stockfish's choices
     (book-like) or diverges early.
   - **Style**: captures per move, sacrifices (material given up then recovered), average game
     length, checkmates delivered vs resignations (none here: games end only by rule), whether
     they steer into simplifications when ahead.
   - **Likely engine profile**: your inference of search depth/speed and evaluation type from the
     above (e.g. "shallow material engine that repeats when ahead" vs "deep search, NNUE-like
     evaluation, near-engine move quality"). Be explicit about confidence.
   - **How to play them**: three to five concrete, evidence-backed recommendations for our
     engine's settings against this opponent (contempt, when to avoid simplification, whether
     they can be out-searched in tactics, whether to press in endgames, time-pressure pressure).
4. `intel/00_summary.txt` — a league table (rank, team, rating, record, mean centipawn loss,
   blunder %, mean s/move, draw %, repeats-while-ahead count, endgame non-conversions) followed by
   the five most important cross-team findings, our own row for comparison, and a short section
   "what changed since last refresh" (diff against the previous summary, which you keep as
   `intel/history/summary_<timestamp>.txt`).
5. `intel/README.txt` — how to refresh, what each file means, and caveats (centipawn loss at
   120k nodes is a proxy, not an Elo; small samples per opponent pair).

## Method notes

- Use python-chess for everything. Attribute moves to the team by matching the PGN `White`/`Black`
  header against the team name (headers use the *team* name, not the bot name; check a game to
  confirm and handle HTML entities like `&#x27;`).
- Evaluate with one Stockfish at 120,000 nodes per position, `Threads 1`, `Hash 64`, so every
  team is measured the same way; cache evaluations by FEN in `intel/raw/evals.jsonl` so refreshes
  only analyse new games.
- "Ahead/behind" uses the Stockfish evaluation from the mover's point of view at that position.
- Keep each dossier plain text, no markdown tables wider than 100 characters, numbers rounded
  sensibly. Every claim must be traceable to a count or a game (cite round numbers).
- Finish by printing the league table and the five findings to the terminal.

Report back with: the list of files written, the league table, the five findings, and anything
about the site that blocked you.
