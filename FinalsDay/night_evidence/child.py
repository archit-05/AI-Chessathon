"""Engine's own view of named root moves: search each child at equal nodes (cold, full history), negate.
usage: child.py <build> <pgn> <fullmove> <uci,uci,...> <nodes> <out.json>"""
import os, sys, io, json, time
from pathlib import Path
ROOT = Path('/Users/architbhardwaj/Desktop/AI Chessathon')
build, pgn_path, target, ucis, nodes, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2]), int(sys.argv[3]), sys.argv[4].split(','), int(sys.argv[5]), Path(sys.argv[6])
os.environ['BINI_DIR'] = str(build); os.environ.setdefault('BINI_TT_BITS', '24')
sys.path.insert(0, str(ROOT / 'astra_tests'))
from harness import Probe, S, N, chess
import chess.pgn
g = chess.pgn.read_game(io.StringIO(pgn_path.read_text()))
ours = chess.WHITE if g.headers['White'] == 'Opus Carlsen' else chess.BLACK
b = g.board(); start = b.fen(); hist = []; own = 0
for mv in g.mainline_moves():
    if b.turn == ours:
        own += 1
        if b.fullmove_number == target: break
    hist.append(mv.uci()); b.push(mv)
fen = b.fen(); p = Probe(); rows = []
for u in ucis:
    p.setup(start, hist + [u], budget=3600); p.e.move_number = own; p.e.prev_score_valid = False
    raw = int(N.nnue_eval(p.e.bb, p.e.st, p.e.acc, p.e.w2, p.e.b2))
    got, sc, d = p.e.think(1e9, 1e9, max_nodes=nodes, log=False)
    rows.append(dict(move=u, san=chess.Board(fen).san(chess.Move.from_uci(u)), score_for_us=-int(sc), depth=int(d), reply=got, static_after_for_us=-raw, pv=p.e.pv_line(12)))
    print(json.dumps(rows[-1]), flush=True)
out.write_text(json.dumps(dict(build=str(build), fen=fen, nodes=nodes, rows=rows), indent=1)); print('done')
