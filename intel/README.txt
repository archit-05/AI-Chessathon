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
  ./refresh.sh                 scrape + analyse + render (first run ~1-3 h of single-core Stockfish;
                               later runs only analyse new games, typically a few minutes)
  ./refresh.sh --no-scrape     re-analyse and re-render without touching the network
  ./refresh.sh --report        re-render only (after editing notes/*.txt)
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
  refresh.sh                   the one-command refresh (see above)
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
  Centipawn loss (CPL) Stockfish 19, 120,000 nodes per position, Threads 1, Hash 64, loss = eval before
                       the move minus eval after it (mover's view), clipped to [0, 1000]; only positions
                       inside +-800 count, so decided games do not distort the average.  Positions that
                       are already decided (previous evaluation at or beyond +-1000) are evaluated with
                       30,000 nodes and never enter the CPL statistics; if such a look comes back inside
                       the band it is redone at 120,000.  Blunder = a loss of 200 cp or more.
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
  - CPL at 120k nodes is a proxy for strength, not an Elo.  It also depends on how sharp the assigned
    openings were and on how quickly the opponent collapsed (decided positions are excluded).
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
