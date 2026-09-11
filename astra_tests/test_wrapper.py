"""Wrapper and reliability tests: agent.get_move exactly as the platform calls it.

Runs in a cold process with the production COMPILE_JOIN_S (no BINI_JOIN_S override), so the
init measurement is comparable to the 90 s platform budget.  argv[1] selects the mode.
"""
import os, sys, io, json, time, contextlib, threading, platform
from pathlib import Path

MODE = sys.argv[2] if len(sys.argv) > 2 else 'normal'
BINI_DIR = Path(sys.argv[1]).resolve()
os.environ.pop('BINI_JOIN_S', None)
if MODE == 'fallback':
    os.environ['BINI_FORCE_FALLBACK'] = '1'
if MODE == 'nobook':
    os.environ['BINI_BOOK'] = '0'
sys.path.insert(0, str(BINI_DIR))

import chess

rows = []
def add(tid, title, status, **kw):
    rows.append(dict(id=tid, title=title, status=status, **kw))
    extra = ' '.join(f'{k}={v}' for k, v in kw.items() if k != 'detail')
    print(f'[{status:4}] {tid:<30} {title}   {extra}', flush=True)

# ---- cold import, production join ---------------------------------------------------------
_t0 = time.perf_counter()
_out = io.StringIO()
with contextlib.redirect_stdout(_out):
    import agent
IMPORT_S = time.perf_counter() - _t0
add('W1.cold_init', 'import + compile inside the 90 s platform init budget',
    'PASS' if IMPORT_S < 90 and agent._ready.is_set() else 'FAIL',
    seconds=round(IMPORT_S, 1), ready=agent._ready.is_set(),
    join_s=agent.COMPILE_JOIN_S, build_error=agent._build_error)
add('W1b.nnue_on', 'the compiled engine is using the network, not the handcrafted fallback',
    'PASS' if (MODE == 'fallback') or (agent._engine is not None and agent._engine.use_nnue) else 'FAIL',
    mode=MODE, engine=agent._engine is not None,
    use_nnue=bool(agent._engine and agent._engine.use_nnue))
add('W2.import_stdout_clean', 'import writes nothing to stdout',
    'PASS' if _out.getvalue() == '' else 'FAIL', captured=repr(_out.getvalue()[:120]))

def call(fen, ms):
    """One platform-style call; returns (uci, wall_ms, stdout_text)."""
    buf = io.StringIO()
    t = time.perf_counter()
    with contextlib.redirect_stdout(buf):
        u = agent.get_move(fen, ms)
    return u, (time.perf_counter() - t) * 1000.0, buf.getvalue()

# ---- a full self-played game through the real entry point ---------------------------------
agent._state = agent.GameState()
board = chess.Board()
# a compressed clock: 80 plies at 120 s each would take seven minutes, and the low-clock
# regime is where budget breaches actually happen
clock = {True: 20000, False: 20000}
illegal, dirty, over_hard, plies = [], [], [], 0
t_start = time.perf_counter()
while not board.is_game_over(claim_draw=True) and plies < 80:
    side = board.turn
    u, ms, so = call(board.fen(), clock[side])
    if so:
        dirty.append((plies, so[:80]))
    try:
        mv = chess.Move.from_uci(u)
    except Exception:
        mv = None
    if mv is None or mv not in board.legal_moves:
        illegal.append((plies, board.fen(), u))
        break
    soft, hard = agent._budget(clock[side], agent._state.move_number)
    if ms > hard + 400:
        over_hard.append((plies, round(ms), round(hard)))
    clock[side] = int(clock[side] - ms + 500)
    board.push(mv)
    plies += 1
game_s = time.perf_counter() - t_start
add('W3.selfplay_all_legal', 'every move of a self-played game is legal',
    'PASS' if not illegal else 'FAIL', plies=plies, detail=illegal,
    result=board.result(claim_draw=True), seconds=round(game_s, 1))
add('W4.stdout_clean_in_play', 'get_move writes nothing to stdout during play',
    'PASS' if not dirty else 'FAIL', detail=dirty[:3])
add('W5.clock_respected', 'no move exceeds its own hard budget by more than 400 ms',
    'PASS' if not over_hard else 'FAIL', breaches=len(over_hard), detail=over_hard[:5],
    min_clock_left=min(clock.values()))

# ---- forced move, no legal move, low budget, repeated calls -------------------------------
agent._state = agent.GameState()
FORCED = '7k/8/8/8/8/8/6q1/7K w - - 0 1'
u, ms, _ = call(FORCED, 120000)
lm = [m.uci() for m in chess.Board(FORCED).legal_moves]
add('W6.forced_move', 'a position with one legal move returns it immediately',
    'PASS' if u in lm and len(lm) == 1 and ms < 200 else 'FAIL', move=u, ms=round(ms), legal=lm)

agent._state = agent.GameState()
MATED = '7k/6Q1/5K2/8/8/8/8/8 b - - 0 1'
u, ms, _ = call(MATED, 120000)
add('W7.no_legal_move', 'a finished position returns the null move',
    'PASS' if u == '0000' else 'FAIL', move=u)

agent._state = agent.GameState()
LOWCLK = 'r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3'
low = []
for ms_left in (2000, 800, 300, 120, 40):
    agent._state = agent.GameState()
    agent._state.move_number = 30
    u, ms, _ = call(LOWCLK, ms_left)
    ok = chess.Move.from_uci(u) in chess.Board(LOWCLK).legal_moves
    low.append((ms_left, u, round(ms), ok))
add('W8.low_clock_legal', 'a legal move comes back at every low clock value',
    'PASS' if all(r[3] for r in low) else 'FAIL', detail=low)

# ---- book ---------------------------------------------------------------------------------
agent._state = agent.GameState()
u, ms, _ = call(chess.STARTING_FEN, 120000)
in_book = agent._book_key(chess.Board()) in agent._BOOK
add('W9.book_move', 'the start position is answered from the book with a legal move',
    'PASS' if chess.Move.from_uci(u) in chess.Board().legal_moves else 'FAIL',
    move=u, start_in_book=in_book, book_entries=len(agent._BOOK), ms=round(ms))

# ---- history reconstruction from FENs alone -----------------------------------------------
agent._state = agent.GameState()
b = chess.Board()
seq = ['g1f3', 'g8f6', 'f3g1', 'f6g8', 'g1f3', 'g8f6', 'f3g1', 'f6g8']
keys_seen = []
for i in range(0, len(seq), 2):
    u, _, _ = call(b.fen(), 120000)   # we are White; our reply is recorded
    # force the scripted continuation so the position really repeats
    agent._state.board = b.copy()
    agent._state.board.push_uci(seq[i])
    agent._state._pending_key = agent._state._key(agent._state.board)
    b.push_uci(seq[i]); b.push_uci(seq[i + 1])
    keys_seen.append(len(agent._state.keys))
add('W10.history_grows', 'GameState accumulates a key for every earlier position',
    'PASS' if keys_seen == sorted(keys_seen) and keys_seen[-1] >= 4 else 'FAIL',
    key_counts=keys_seen)

# ---- failure injection --------------------------------------------------------------------
inj = []
if agent._engine is not None:
    class Boom:
        def __getattr__(self, k):
            raise RuntimeError('injected engine failure')
    real = agent._engine
    agent._state = agent.GameState(); agent._state.move_number = 20
    agent._engine = Boom()
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        u, ms, so = call(LOWCLK, 30000)
    inj.append(('exception', u, chess.Move.from_uci(u) in chess.Board(LOWCLK).legal_moves,
                'engine error' in err.getvalue(), so == ''))
    agent._engine = real

    class Illegal:
        def __init__(self, e): self._e = e
        def __getattr__(self, k): return getattr(self._e, k)
        def think(self, *a, **k): return 'a1a8', 0, 1
    agent._state = agent.GameState(); agent._state.move_number = 20
    agent._engine = Illegal(real)
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        u, ms, so = call(LOWCLK, 30000)
    inj.append(('illegal_candidate', u, chess.Move.from_uci(u) in chess.Board(LOWCLK).legal_moves,
                'ILLEGAL candidate' in err.getvalue(), so == ''))
    agent._engine = real
add('W11.failure_recovery', 'engine exception and illegal candidate both recover to a legal move',
    'PASS' if inj and all(r[2] and r[3] and r[4] for r in inj) else ('SKIP' if not inj else 'FAIL'),
    detail=inj)

# ---- background work ----------------------------------------------------------------------
alive = [t.name for t in threading.enumerate() if t is not threading.current_thread() and t.is_alive()]
add('W12.no_background_work', 'no worker thread is still running between moves',
    'PASS' if not alive else 'FAIL', threads=alive,
    note='the platform suspends the process between moves; anything still running is wasted')

summary = dict(mode=MODE, build=str(BINI_DIR), total=len(rows),
               passed=sum(1 for r in rows if r['status'] == 'PASS'),
               failed=sum(1 for r in rows if r['status'] == 'FAIL'),
               import_seconds=round(IMPORT_S, 1))
print(json.dumps(summary), flush=True)
out = Path(__file__).resolve().parents[1] / 'astra_reports' / f"wrapper_{os.environ.get('LABEL','run')}_{MODE}.json"
out.write_text(json.dumps(dict(summary=summary, rows=rows,
    environment=dict(python=sys.version.split()[0], platform=platform.platform())), indent=2, default=str))
print('written', out)
