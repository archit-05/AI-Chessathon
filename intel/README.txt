OPPONENT INTELLIGENCE - AI Chessathon top 20 (+ Opus Carlsen)
=============================================================

WHAT THIS IS
  One plain-text dossier per team in the current top 20 of https://aichessathon.com/leaderboard
  (TOP_N in common.py), plus one for us (team Opus Carlsen), built from every public rated game of
  theirs, the site's own per-game review, and a uniform Stockfish analysis.  Read 00_summary.txt
  first (league table, key findings, head-to-head, time and draw tables), then the dossier of the
  opponent you care about.  Dossiers of teams the Stockfish pass has not reached yet still carry
  identity, results, site review numbers, openings and (once analysed) everything else; the header
  line says "N of M analysed".

HOW TO REFRESH
  ./refresh.sh                 scrape + analyse + render (a few minutes: the analysis uses the site's
                               own per-position evaluations, so no engine runs)
  ./refresh.sh --no-scrape     re-analyse and re-render without touching the network
  ./refresh.sh --deep          optional: our own Stockfish 19 pass at 120k nodes per position (one
                               niced process, hours; cached in raw/evals.jsonl) as a second opinion
  ./refresh.sh --auto          scrape, keep one Stockfish pass running in the background, render,
                               archive the next Strategy_N, commit intel/ (the three-hourly schedule)
  ./refresh.sh --report        re-render only (after editing notes/*.txt); updates STRATEGY.txt
                               without adding a numbered entry
  Everything runs under nice -n 15 with ONE Stockfish process, so it can share the machine with
  training or arena jobs.  Python comes from ../aichessathon-starter/.venv (python-chess needed).
  Stockfish is expected at /opt/homebrew/bin/stockfish (common.py: SF_PATH).

FILES
  00_summary.txt               league table; our row; key findings; the leader's losses; head-to-head
                               matrix among the top 10; time-management and draw/conversion tables;
                               what changed since the previous refresh; list of dossiers
  <rank>_<Bot>.txt             dossier: identity, results by opponent tier, move quality, time
                               management, draw behaviour, endgame conversion, openings, style,
                               likely engine profile, how to play them, analyst notes
  STRATEGY.txt                 the latest strategic report: reverse-engineered profile of each top-10
                               system, where the top ten leak points, the bar the top five set, what
                               it means for our build, the curated openings, who is climbing across
                               the whole ladder, our own games, head-to-head; ends with the
                               hand-written synthesis from notes/strategy.txt
  strategy/Strategy_N.txt      the numbered series of those reports (one per scheduled or full
                               refresh, about every three hours); each opens with a diff against
                               Strategy N-1 (rank/rating/record moves, fresh-upload flags, CPL
                               becoming measurable, Stockfish coverage).  Strategy_N.json holds the
                               rows used for the diff.
  ladder/hourly_<stamp>.txt    hourly snapshot (snapshot.py): top-12 table, rating jumps, our games,
                               then whole-leaderboard movement: biggest gains over the last round,
                               the last three rounds and since yesterday's close, biggest falls,
                               fresh-upload flags, new teams, "climbing a lot" (100+ over three
                               rounds or 150+ since yesterday's close) and details on the climbers
                               (identity, rating by round, last three games with site ACPL, time use)
  raw/ladder/leaderboard_<stamp>.json   every leaderboard row at every hourly snapshot (all teams)
  ladder.py                    the whole-leaderboard movement report; --seed fetches every team page
                               once so rating-by-round is known for all teams
  snapshot.py                  hourly snapshot (compact part for the engine session + ladder movement)
  refresh.sh                   the one-command refresh (see above); --auto is what the schedule runs
  scrape.py                    leaderboard + team pages + game pages -> raw/
  analyse.py                   Stockfish evaluation of every position -> raw/<Bot>.json
  report.py                    renders dossiers, summary and history from raw/
  common.py                    paths and analysis constants (nodes, thresholds)
  notes/<Bot>.txt              optional hand-written analyst notes appended to a dossier;
                               notes/summary.txt is appended to the summary.  Not regenerated.
  history/summary_<stamp>.txt  copy of every summary ever generated (+ .json for the diff)
  raw/leaderboard.json         every ladder row at scrape time (rank, uuid, bot, team, university,
                               rating, games, W-D-L, House/Engine tag, provisional flag)
  raw/targets.json             the teams covered by this refresh
  raw/<Bot>.pgn                all rated games of that team, oldest round first, with [%clk]
  raw/<Bot>.scrape.json        identity, rating history and per-game facts that need no engine
  raw/<Bot>.json               the same plus per-move Stockfish facts (own moves only) and
                               per-game summaries (peak/low evaluation, loss per move, worst move,
                               opponent's loss per move, opponent's worst move, final evaluation)
  raw/evals.jsonl              evaluation cache keyed by FEN: cp from White's view (mate = +-(10000-n)),
                               mate distance, Stockfish's first choice, depth, nodes used
  raw/cache/games/<uuid>.json  one file per game page: PGN, opening name, termination text, the
                               site's own per-move tags (best/excellent/.../blunder), the site's
                               "Game review" block (Stockfish 16 depth 16: accuracy, ACPL, tallies
                               for White then Black), state
  raw/cache/teams/<uuid>.json  team pages (also of opponents, for their rating at the time)

DEFINITIONS
  Team attribution     PGN White/Black headers carry the TEAM name (e.g. "Emile Andrieu"), not the
                       bot name ("AlphaFish"); files and tables use the bot name, dossiers show both.
  Evaluations          by default the site's own per-position analysis embedded in every game page
                       (Stockfish 16, depth 16: a centipawn score from White's view for the start
                       position and after every ply, mates as +-(10000-n), and the engine's first
                       choice per position).  The same numbers drive the site's eval bar and move tags,
                       and they are identical for every team.  --deep replaces them with our own
                       Stockfish 19 at 120,000 nodes (Threads 1, Hash 64; decided positions at 30,000).
  Centipawn loss (CPL) loss = eval before the move minus eval after it (mover's view), clipped to
                       [0, 1000]; only positions inside +-800 count, so decided games do not distort the
                       average.  Blunder = a loss of 200 cp or more.  Shown as n/a under 200 moves.
  Phases               own moves 1-15, 16-40, 41+ counted from the curated start position.
  Time per move        from the [%clk] comments (clock after the move, increment included):
                       spent = previous own clock - clock after move + 0.5 s.
  Ahead / behind       Stockfish evaluation from the mover's point of view; a repetition "while ahead"
                       means the final position evaluated above +150 for that team.
  Conversion           a game counts as "won position" when the team's evaluation reached +300 at any
                       point; "non-conversion" when such a game was not won.  "Saved" is the mirror.
  Opponent tiers       by the opponent's rank on the leaderboard at scrape time (top 10, 11-20,
                       21-50, rest).
  sACPL / site review  the ACPL and accuracy the site itself shows under "Game review" (Stockfish 16,
                       depth 16, as rendered by the server; the browser may show a deeper re-analysis
                       with different numbers).  Available for every game at once, so it is the
                       quickest like-for-like comparison; our 120k-node CPL is the finer measure.
  Rating at the time   the opponent's rating after its previous rated round, read off its rating graph.
  Void games           games the site marks Void (result "*", never rated) are kept in raw/ but
                       excluded from every statistic.
  Provisional          the site dims a rating with fewer than six games on the current build, i.e. a
                       new upload within the last five rated rounds.  Games before that upload may
                       describe an older bot.

CAVEATS
  - CPL from depth-16 evaluations is a proxy for strength, not an Elo.  It also depends on how sharp
    the assigned openings were and on how quickly the opponent collapsed (decided positions are
    excluded).  The site's ACPL (sACPL) counts every position, so it runs higher.
  - Samples are small: 22-30 games per team, 0-3 games per opponent pair, 1-6 games per opening
    family.  Treat anything built on fewer than ~5 games as a hint, not a fact.
  - Tiers use today's ranks; the opponent may have been much weaker or stronger when the game was played.
  - The site does not show team members; "solo" is a guess from the team name.
  - Rating jumps of 100+ in the first ten rounds are normal Glicko-2 behaviour; only later jumps, or
    the provisional flag, indicate a new upload.
  - The site's own move tags and review (Stockfish 16, depth 16) are a different yardstick from our
    120k-node CPL: expect the site's ACPL to run higher and to include decided positions.
  - Stockfish's first choice at 120k nodes is not a book: "matches Stockfish" in the opening section
    measures move agreement, not whether the bot has a book.  Instant moves (<50 ms) do.
