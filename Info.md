Skip to contentDocs | AI Chessathon
AI Chessathon
Docs
Leaderboard
Daily Five
Rules
Dashboard
Participants

Build against this.
Quickstart
Agent API
Wire protocol
Match environment
Clocks and scoring
Submissions
Failure reference
Quickstart
Fork the starter repo for a working agent, baselines to beat, and a harness that plays games locally under the real clock. Or start from scratch, below.

A submission is a zip of 50 MB unzipped at most. These sit at its root, not inside a folder.

agent.zip
├── agent.py            required
└── model files         weights, books, anything else
The smallest legal agent looks like this.

import chess
import random

def get_move(fen: str, time_left_ms: int) -> str:
    board = chess.Board(fen)
    return random.choice(list(board.legal_moves)).uci()
The environment is fixed. The container ships Python 3.12, the full standard library, and five preinstalled packages at fixed versions.

torch 2.13.0+cpu     numpy 2.5.2      python-chess 1.11.2
onnxruntime 1.29.0   numba 0.67.0
Nothing installs at validation and a requirements.txt in your zip is ignored, so importing anything outside that set crashes your agent in its smoke games. Ask at hello@aichessathon.com for a package the stack lacks and any addition is announced to every team.

Native binaries inside the zip are rejected. What you ship has to be source a judge can read, so a flagged game can be cleared by reading your agent instead of by statistics alone. File modes inside the zip are ignored and every file is readable. Compiled speed comes from numba, which JIT compiles your Python in process, and each jitted function pays that compile cost the first time it runs. Cython does not work here, because a compiled extension is a native binary and native binaries are rejected, and the image carries no compiler to build one at runtime. Your zip goes first on sys.path, so a file named after a module you import, chess.py or types.py, shadows the real one.

Agent API
agent.py exposes one function.

def get_move(fen: str, time_left_ms: int) -> str
Name	Type	Meaning
fen	str	the position to move in, standard FEN
time_left_ms	int	your remaining clock in milliseconds
returns	str	a legal move in UCI, e.g. e2e4 or e7e8q
One process serves one game, started fresh for every game. Load your model at import. The 90s init budget covers importing your agent and runs before the clock starts, so work you defer to your first get_move comes out of your match clock. The process stays alive between moves, so state you keep in memory carries across your own moves. Your process is suspended while your opponent moves, so work you leave running between your own moves does not run. During your own move one thread is fastest, since threads past the first share the single core and cost you time. The referee claims threefold and fifty-move draws automatically, so an agent that wants to avoid a repetition tracks the positions it has been asked about.

Wire protocol
The runner talks to your process over stdin and stdout, one JSON object per line. You only implement get_move. The provided runner handles the wire. Each request looks like this.

{"fen": "rnbqkbnr/...", "time_left_ms": 87500}
Each response looks like this.

{"move": "e2e4"}
your colour	the side to move in the fen
time_left_ms	your clock before this move. The increment lands after you move
malformed output	counts as an illegal move, which loses the game
Your own output cannot corrupt this. The runner moves the protocol onto a private handle and points file descriptor 1 at stderr before importing your agent, so print is safe. Everything you write to stdout or stderr is kept, up to 8 KB as the first 4 KB and the last 4 KB. It appears in your validation log, and after every rated game in a log your dashboard offers alongside the PGN. That log also carries your init time, your time on every move, and the clock you had left. Only your own team can read it.

Match environment
CPU	one core of an AMD EPYC 9V74 at 2.60 GHz, yours alone while you think
Memory	2 GB
Network	none, in either direction
GPU	none
Filesystem	read-only, plus 256 MB scratch at /tmp, where HOME and the cache paths already point. It starts empty for every game and is deleted with it, so it is scratch space, not a cache between games
Processes	128. On one core, threads past the first cost you time
Hardware	identical for every game, both agents on one machine
No network means no hosted inference and no engine APIs, by construction. Everything your agent needs ships inside the zip.

Clocks and scoring
Time control	120s per side, plus 0.5s per move
Init budget	90s before the clock starts
Game end	FIDE rules. A game still running at 600 plies is drawn
Ladder	rated rounds every hour, 08:00 to 22:00, ranked by a Glicko-2 rating shown as a single Elo-style number. The ladder only seeds the final Swiss
Openings	every game starts from a curated position that is close to level. Knockout ties play each position once with each colour
Qualification	a 13-round Swiss over the locked builds decides the order the 50 London seats fill, by points. An odd field gives one team a 1-point bye. Seats go one per UK member and at most two per team
Prizes	£1,000 winner, £500 runner-up, £250 third at the London final. Third is the losing semi-finalist with the better final Swiss standing. Awarded to the team, split as the team decides
Tie-breaks	points, Buchholz, head-to-head, earlier final submission
Daily Five	6 to 10 September. One attempt a day, five positions, 20 minutes. One wrong move ends a position. Your five are drawn for you. Start by 23:40 London. Anyone signed in may play
Daily Five ranking	positions solved, then the time of your last solve, then who finished first. Giving up costs no time. A position withdrawn as broken counts as solved and adds no time
Daily Five wildcards	the top 3 eligible participants each day earn a Finals Day Wildcard, a seat at the London final and not a place in the bracket. One per person across the five days, so places roll down. Eligible means a UK university student who is not an organiser and not on a disqualified team
Daily Five fair play	no engines, no other people, no other accounts, no looking positions up. Every move is timed. Invitations follow review and may include solving a position in person at the final
Teams	1 to 3 people, one team per person. Creating, joining and leaving a team close 11 September 11:00
Eligibility	the ladder is open worldwide. A team enters the final Swiss if at least one member is a UK university student, and only its UK members can take a London seat, verified before invites
House bots	play the ladder and show their public CCRL Blitz ratings. They cannot qualify
Submissions
Size	50 MB unzipped
Rate	10 uploads per team per day
Which plays	your latest submission that passed validation
Validation	build, then two smoke games at the match clock, one as each colour. The verbatim log appears on your dashboard
Uploads close	11 September 11:00
Third party engines are prohibited. That covers Stockfish, Lc0, Maia, any wrapper around one and any port or translation of one. Your moves come from code you wrote. Use any AI support you like to write it, as long as the submission keeps to these rules and you can explain it when asked. An engine you wrote yourself before the event is your own code. A model is not required, a classical search is a full entry. Any network you ship is one you trained yourself, and training it on positions an existing engine labelled is allowed. Starting from a published chess network is not, so fine-tuning or re-exporting one counts as shipping it. What ships inside the zip is what the ban covers, and a database of engine moves or evaluations shipped for lookup at runtime is an engine, not training data.

What you ship has to be source a judge can read, so a flagged game can be cleared by reading your agent instead of by statistics alone. Model weights are not binaries, so .onnx, .safetensors and .pt are fine. Opening books and endgame tablebases are permitted as shipped data, and chess.polyglot and chess.syzygy are in the base image. Every submission faces automated and human checks. Each finalist team walks through how its agent was built, and a team that ships a network shows how it was trained. Disqualification can be retroactive, and obfuscated agents are disqualified.

Failure reference
Termination	Cause	Result
illegal	illegal or malformed move	loss
crash	your process exited, threw, or ran out of memory	loss
flag	clock ran out mid-game	loss, or a draw when the other side cannot mate
init	no ready line within the 90s init budget	loss
ply_cap	the game reached 600 plies	draw
void	both sides failed	no result recorded
AI Chessathon
Sponsored by

Event
Format
Team
Register
Archive
Legal
Competition rules
Privacy notice
Contact
Email us

Starter Repository: https://github.com/advitrocks9/aichessathon-starter.git

Skip to content
advitrocks9
aichessathon-starter
Repository navigation
Code
Issues
Pull requests
Agents
Actions
Projects
Security and quality
Insights
advitrocks9
aichessathon-starter
Public
Go to file
t
T
advitrocks9
advitrocks9
fix(harness): draw a capped game and a flag against a bare king
91f70e5
 · 
7 hours ago
Name		
.github/workflows
ci: run the arena on macos and windows
5 days ago
baselines
feat: add a numba baseline
5 days ago
docs
fix(harness): draw a capped game and a flag against a bare king
7 hours ago
harness
fix(harness): draw a capped game and a flag against a bare king
7 hours ago
.gitignore
feat(harness): run an agent through the platform's runner and referee
last week
AGENTS.md
fix(harness): draw a capped game and a flag against a bare king
7 hours ago
CLAUDE.md
docs: the contract, the footguns and where strength comes from
last week
LICENSE
feat(harness): run an agent through the platform's runner and referee
last week
Makefile
feat: play from a given start position
5 days ago
README.md
fix(harness): draw a capped game and a flag against a bare king
7 hours ago
agent.py
feat(agent): ship a legal random mover as the starting point
last week
pyproject.toml
feat: match the platform dependency stack
5 days ago
uv.lock
feat: match the platform dependency stack
5 days ago
Repository files navigation
README
MIT license
AI Chessathon starter
Fork this to build an agent for AI Chessathon. It gives you a working submission, baselines to beat, and a local harness that speaks the same protocol and enforces the same clock as the platform, so you can see whether a change actually helped before you upload it.

git clone https://github.com/advitrocks9/aichessathon-starter
cd aichessathon-starter
make setup
make play
That plays your agent against a baseline over a full 120 s + 0.5 s game and prints the result. When you like it, make zip and drop submission.zip on your dashboard.

Writing an agent
agent.py is the whole submission. One function:

def get_move(fen: str, time_left_ms: int) -> str:
    return "e2e4"
The fork ships a legal random-mover, so the loop works before you write anything. Replace the body.

make play                                          # one game, real time control
make arena                                         # 20 fast games, prints a score
make play FEN="<fen>"                              # start from a given position
uv run python -m harness.play --black baselines/minimax --pgn game.pgn
uv run python -m harness.arena --opponent ../my-old-version --games 200
Anything your agent prints shows up under the result, so print debugging works. The platform keeps it too. Every rated game leaves a log on your dashboard next to the PGN, holding your output plus your init time, your time on each move, and the clock you had left. Only your team can read it.

The ladder
Measured with harness/arena.py. Beating greedy is a search. Beating minimax is a search plus an evaluation worth searching with.

Matchup	Games	Time control	Score
random vs greedy	20	10 s + 0.1 s	10.0% (+1 =2 -17)
greedy vs minimax	6	120 s + 0.5 s	0.0% (+0 =0 -6)
numba vs minimax	6	10 s + 0.5 s	66.7% (+2 =4 -0)
baselines/random plays a uniformly random legal move. It is what agent.py starts as.
baselines/greedy searches one ply on material.
baselines/minimax searches two plies on material and mobility, with no time management.
baselines/numba is minimax with the evaluation jitted. It is barely stronger, which is the point: jitting a shallow search buys headroom, not depth. Read it for the warm-up call at the bottom, which is how you keep compilation off your clock.
What's here
agent.py             your submission
baselines/           random, greedy, minimax, numba; each is a directory with an agent.py
harness/runner.py    the process the platform runs your agent in
harness/referee.py   the clock, legality, draw and cap rules
harness/rules.py     the event constants the harness enforces
harness/sandbox.py   the one process, spoken to as the platform speaks to a container
harness/play.py      one game between two agent directories
harness/arena.py     many games, with a score
harness/package.py   builds submission.zip with agent.py at the root
docs/IDEAS.md        where the strength actually comes from
Local games start from the normal position unless you pass --fen. Rated games start from curated neutral positions.

The harness is here so your games are honest, not so you can pre-validate an upload. Acceptance happens on the platform, and the validation log on your dashboard is the authority on it.

The rules
aichessathon.com/docs is canonical and changes. Read it before you upload.

About
Fork this to build an AI Chessathon agent.

aichessathon.com
Topics
Resources
Readme
MIT license
Activity
Stars
10 stars
Watchers
0 watching
Forks
136 forks
Report repository
Releases
No releases published
Packages
No packages published
Contributors
1
 (1)
@advitrocks9
advitrocks9Advit Arora
Languages
Python
98.1%
Makefile
1.9%
Footer
© 2026 GitHub, Inc.
Footer navigation
Terms
Privacy
Security
Status
Community
Docs
Contact
Manage cookies
Do not share my personal information
 
Copied!