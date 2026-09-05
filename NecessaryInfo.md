Skip to contentAI Chessathon
AI Chessathon
Docs
Leaderboard
Daily Five
Rules
Dashboard
Sponsored by

Build a chess agent. Put it on the board.
The UK's first chess hackathon.

Register now
See the format
Qualification
4–11 September 2026 · Online
Final
12 September 2026 · Encode Club, London
Eligibility
Open worldwide. A London seat needs a UK university student.
Prizes
£1,750 to the podium
Match simulation
Boards
Code
Qualification · 4–11 Sep 2026 · 3 boards

Board 01: Agent 04 versus Agent 17. Starting position.
Board 01
Opera
Agent 17
10:00
8
7
6
5
4
3
2
1a
b
c
d
e
f
g
h
Agent 04
10:00
Start position
Eval 0.0
Board 02: Agent 12 versus Agent 09. Starting position.
Board 02
Evergreen
Agent 09
10:00
8
7
6
5
4
3
2
1a
b
c
d
e
f
g
h
Agent 12
10:00
Start position
Eval 0.0
Board 03: Agent 21 versus Agent 02. Starting position.
Board 03
Century
Agent 02
10:00
8
7
6
5
4
3
2
1a
b
c
d
e
f
g
h
Agent 21
10:00
Start position
Eval 0.0
01 · Organisers

Organising Team

Arham Shuaibon LinkedIn
Lead
Software Engineer @ Combinely (YC X25). Palantir and Null Fellow. Previously interned at Disney, JPM, and Bank of America.

Advit Aroraon LinkedIn
Engineering
Spring Intern @ Millennium & SIG. Previously ML Research @ Guild Robotics (SF). Imperial Joint Maths & Computer Science.

Tanuj Kakumanion LinkedIn
Growth
Founder of simplytk. Ex-A* AI (10k users). Spring Intern @ Citadel, Optiver, IMC Trading. Imperial Econ & Data Science.

Vincent Leeon LinkedIn
Operations
Incoming Quant Research Intern @ Optiver. Imperial BSc in Mathematics with Statistics.
02 · The challenge

One function plays every game.
You ship get_move. The server runs it against the field, round after round.

agent.py
PIECE = {"P": 1, "N": 3, "B": 3, "R": 5, "Q": 9, "K": 0}
CENTER = {"d4", "d5", "e4", "e5"}
 
def evaluate(pos):
    score = 0.0
    for sq, piece in pos.pieces():
        sign = 1 if piece.white else -1
        score += sign * PIECE[piece.kind]
        if sq in CENTER:
            score += sign * 0.12
    if pos.in_check:
        score += -0.35 if pos.side == "w" else 0.35
    return score
 
def search(pos, depth, alpha, beta):
    if depth == 0 or pos.done():
        return evaluate(pos)
    best = -99.0
    for move in pos.legal_moves():
        pos.push(move)
        value = -search(pos, depth - 1, -beta, -alpha)
        pos.pop()
        best = max(best, value)
        alpha = max(alpha, value)
        if alpha >= beta:
            break
    return best
 
IMMORTAL = {"Qh4+", "Bxb5", "Be7#"}  # Anderssen vs Kieseritzky, 1851
 
def pick_move(pos, clock):
    depth = 3 if clock > 90 else 2
    choice, best = None, -99.0
    for move in pos.legal_moves():
        pos.push(move)  # Immortal, 1851
        value = -search(pos, depth, -8, 8)
        pos.pop()
        if move.san in IMMORTAL:
            value += 0.08
        if value > best:
            choice, best = move, value
    return choice
01

Write the code

agent.zip
server
02

Submit

Agent 17
Elo 1488
Agent 04
Elo 1512
Start position
Eval 0.0
03

Play

03 · Format

Three steps to the final.
01

Register

Tell us about yourself, confirm your email, set up your team.

Site form
02

Qualify

Rated matches 4–11 September 2026, open worldwide. A final Swiss over locked builds decides the London field.

Online

03

Final

Fifty seats, filled in finishing order, compete in person on 12 September 2026 at Encode Club, London.

London

04 · Criteria

What matters in competition.
01
Agent design
Turn board states into effective decisions.

02
Match performance
Compete directly against other agents. Ranking is by Elo.

03
Stable execution
Legal moves, time discipline, and reliable deployment all count.

05 · Prizes

Play for the pot.
Paid at the London final. Terms in the competition rules.

Prize pool

£1,750

01 · Winner
£1,000
02 · Runner-up
£500
03 · Third
£250
06 · Our sponsor

Our sponsor
07 · FAQ

Questions
Anything this misses, email us and we answer it here.


01
Who can register?


02
What is the format?


03
What do I have to build?


04
Can I enter with a team?


05
Do I have to share my CV with Optiver?


06
Where are the rules and privacy notice?

08 · Enter

Your move.
Register now
Read the docs
Qualification opens
4 September 2026
Final
12 September 2026
Entry
Free. One Python file.
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


What do I have to build?
One Python file, agent.py, exposing get_move(fen, time_left_ms). A model is not required, a classical search is a full entry. Training data is unrestricted, including positions annotated by an existing engine, and the ban on third party engines covers only what ships inside the submission. The full contract is on the docs page.


