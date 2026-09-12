"""Cold reproduction of R113 move 39 (White, Rc2 played; reference prefers Qe8+).
Runs the deployed V8.5 engine (bini_astra_v5_noc2b) from the real start FEN with full game
history, fixed-node budgets, cold TT.  Diagnostic only."""
import os, sys, io, json, time
from pathlib import Path
ROOT = Path('/Users/architbhardwaj/Desktop/AI Chessathon')
OUT = Path(sys.argv[1])
os.environ['BINI_DIR'] = str(ROOT / 'bini_astra_v5_noc2b')
os.environ['BINI_TT_BITS'] = '24'
sys.path.insert(0, str(ROOT / 'astra_tests'))
from harness import Probe, B, N, S, chess, build_hashes
import chess.pgn

g = chess.pgn.read_game(io.StringIO((ROOT / 'Swiss Round 13/aichessathon-round-113-omi.pgn').read_text()))
b = g.board(); start = b.fen(); hist = []; own = 0
for mv in g.mainline_moves():
    if b.turn == chess.WHITE:
        own += 1
        if b.fullmove_number == 39:
            break
    hist.append(mv.uci()); b.push(mv)
fen = b.fen()
assert fen.startswith('6k1/4Qpp1/p3p2p/qrNb4/7P/1PR2PP1/4P1K1/8 w'), fen
TARGET_OWN = own
GAME_NODES = 2646016
p = Probe(); base = p.e.info.copy(); rows = []
def log(row):
    rows.append(row); print(json.dumps(row), flush=True)
    (OUT / 'r113_probe.json').write_text(json.dumps(dict(fen=fen, start=start, history_plies=len(hist), target_own_move=TARGET_OWN, game_nodes=GAME_NODES, hashes=build_hashes(), rows=rows), indent=1))

def think_at(nodes, settings=None, history=True, extra=()):
    p.e.info[:] = base
    if history:
        p.setup(start, list(hist) + list(extra), budget=3600)
    else:
        bb = chess.Board(fen)
        for u in extra: bb.push_uci(u)
        p.setup(bb.fen(), [], budget=3600)
    p.e.move_number = TARGET_OWN - 1
    p.e.prev_score_valid = False
    for k, v in (settings or {}).items(): p.e.info[k] = v
    raw = int(N.nnue_eval(p.e.bb, p.e.st, p.e.acc, p.e.w2, p.e.b2))
    stat = p.evaluate()
    t0 = time.perf_counter()
    got, score, depth = p.e.think(1e9, 1e9, max_nodes=int(nodes), log=False)
    dt = time.perf_counter() - t0
    return dict(move=got, score=int(score), depth=int(depth), nodes=int(p.e.info[S.I_NODES]), seldepth=int(p.e.info[S.I_SELDEPTH]), secs=round(dt, 2), raw_nnue=raw, static=stat, pv=p.e.pv_line(14))

log(dict(section='env', target_fen=fen, history_plies=len(hist), own_move=TARGET_OWN))
# 1. node sweep, cold, full history
for n in [500_000, 1_000_000, GAME_NODES, 5_000_000, 10_000_000, 20_000_000, 40_000_000]:
    log(dict(section='sweep', arm='default', **think_at(n)))
# 2. history-free control
log(dict(section='history', arm='no_history', **think_at(GAME_NODES, history=False)))
# 3. ablations at the game's node count
for name, st in [('seep_off', {S.I_SEEP: 0}), ('cont_off', {S.I_CONT: 0}), ('corr_off', {S.I_CORR: 0}), ('qs_checks_on', {S.I_QS_CHECKS: 1}), ('nmp_off', {S.I_NMP_OFF: 1}), ('improving_on', {S.I_IMPROVING: 1}), ('probcut_on', {S.I_PROBCUT: 1}), ('contempt_0', {S.I_CONTEMPT: 0})]:
    log(dict(section='ablation', arm=name, **think_at(GAME_NODES, st)))
    if name == 'qs_checks_on':
        log(dict(section='ablation', arm=name + '_10M', **think_at(10_000_000, st)))
# 4. root ranking: every legal move searched from the child at equal nodes, negated
rank = []
for m in chess.Board(fen).legal_moves:
    r = think_at(600_000, extra=[m.uci()])
    rank.append(dict(move=m.uci(), san=chess.Board(fen).san(m), score_white=-r['score'], depth=r['depth'], reply=r['move'], pv=r['pv'][:8]))
rank.sort(key=lambda x: -x['score_white'])
log(dict(section='ranking', nodes_per_child=600_000, ranking=rank))
# 5. trace the reference line Qe8+ Kh7 Nd7
for extra in (['e7e8'], ['e7e8', 'g8h7'], ['e7e8', 'g8h7', 'c5d7'], ['e7e8', 'g8h7', 'c5d7', 'b5b8'], ['e7e8', 'g8h7', 'c5d7', 'b5b8', 'e8b8']):
    r = think_at(1_000_000, extra=extra)
    log(dict(section='trace', line=extra, side_to_move='black' if len(extra) % 2 else 'white', **r))
log(dict(section='done'))
