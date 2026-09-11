"""C4 diagnostic: replay round 100 through the real wrapper and find what carries the blunder.

The platform passed a FEN and a clock; the engine logged its own choice and remaining time.
Arm 'full' feeds the exact sequence.  The other arms feed the same sequence but wipe one piece
of accumulated context immediately before the move under test, so the carrier can be named
rather than guessed.  Fixed-node arms remove the clock from the comparison entirely.
"""
import os, sys, io, json, re, time, contextlib
from pathlib import Path

BUILD = Path(sys.argv[1]).resolve()
ARM = sys.argv[2] if len(sys.argv) > 2 else 'full'
os.environ.pop('BINI_JOIN_S', None)
sys.path.insert(0, str(BUILD))
import chess
import agent
import bini_search as S
import bini_board as BB

DL = Path.home() / 'Downloads'
PGN = (DL / 'aichessathon-round-100-lightning-tree.pgn').read_text()
LOG = (DL / 'aichessathon-round-100-lightning-tree.log').read_text()

START = re.search(r'\[FEN "([^"]+)"\]', PGN).group(1)
SAN = re.sub(r'\{[^}]*\}', '', PGN.split(']\n\n')[-1])
SAN = re.sub(r'\d+\.(\.\.)?', ' ', SAN).replace('0-1', '').split()

# our own stderr from the real game: move index -> (uci, clock passed in, logged choice)
LOGGED = {}
for m in re.finditer(r'bini-5\.0 m(\d+) d(\d+) ([a-h][1-8][a-h][1-8][qrbn]?) (-?\d+)cp \d+n (\d+)ms left (\d+)ms', LOG):
    LOGGED[int(m.group(1))] = dict(depth=int(m.group(2)), uci=m.group(3), cp=int(m.group(4)),
                                   spent=int(m.group(5)), left=int(m.group(6)))
TARGET = 23                       # our move 23 = PGN move 29 = Rfa1, the 523 cp blunder

board = chess.Board(START)
agent._state = agent.GameState()
rows = []
our_move = 0
for san in SAN:
    mv = board.parse_san(san)
    if board.turn == chess.WHITE:
        our_move += 1
        info = LOGGED.get(our_move)
        left = info['left'] if info else 60000
        if our_move == TARGET and ARM != 'full':
            eng = agent._engine
            if ARM == 'clear_tt':
                eng.tt_key[:] = 0; eng.tt_data[:] = 0
            elif ARM == 'clear_corr':
                eng.scores[S.CORR_BASE:] = 0
            elif ARM == 'clear_hist':
                eng.history[:] = 0; eng.counters[:] = 0; eng.killers[:] = 0
            elif ARM == 'clear_gamekeys':
                agent._state.keys = []
            elif ARM == 'clear_all':
                eng.tt_key[:] = 0; eng.tt_data[:] = 0
                eng.scores[S.CORR_BASE:] = 0
                eng.history[:] = 0; eng.counters[:] = 0; eng.killers[:] = 0
                agent._state.keys = []
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            got = agent.get_move(board.fen(), left)
        line = err.getvalue().strip().splitlines()[-1] if err.getvalue().strip() else ''
        played = mv.uci()
        rows.append(dict(our_move=our_move, fen=board.fen(), clock_ms=left,
                         game_played=played, replay_played=got, agree=got == played,
                         logged=info, telemetry=line))
        if our_move == TARGET:
            print(f'>>> move {TARGET}: game played {played}, replay played {got}  ({line})', flush=True)
    board.push(mv)
    if our_move > TARGET + 1:
        break

agree = sum(1 for r in rows if r['agree'])
t = [r for r in rows if r['our_move'] == TARGET][0]
out = dict(arm=ARM, build=str(BUILD), target_move=TARGET,
           target_game_played=t['game_played'], target_replay_played=t['replay_played'],
           target_reproduced=t['replay_played'] == t['game_played'],
           moves_replayed=len(rows), moves_agreeing=agree, rows=rows)
print(json.dumps({k: v for k, v in out.items() if k != 'rows'}, indent=1), flush=True)
p = Path(__file__).resolve().parents[1] / 'astra_reports' / f'r100_{ARM}.json'
p.write_text(json.dumps(out, indent=1))
print('written', p)
