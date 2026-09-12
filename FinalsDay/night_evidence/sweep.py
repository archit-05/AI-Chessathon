"""Cold full-history node sweep of one game position for one build.
usage: sweep.py <build_dir> <pgn> <fullmove> <nodes,nodes,...> <out.json> [ENV=VAL ...]"""
import os, sys, io, json, time
from pathlib import Path
ROOT = Path('/Users/architbhardwaj/Desktop/AI Chessathon')
build, pgn_path, target, nodes_list, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2]), int(sys.argv[3]), [int(x) for x in sys.argv[4].split(',')], Path(sys.argv[5])
for kv in sys.argv[6:]:
    k, v = kv.split('='); os.environ[k] = v
os.environ['BINI_DIR'] = str(build); os.environ.setdefault('BINI_TT_BITS', '24')
sys.path.insert(0, str(ROOT / 'astra_tests'))
from harness import Probe, B, N, S, chess, build_hashes
import chess.pgn
g = chess.pgn.read_game(io.StringIO(pgn_path.read_text()))
ours = chess.WHITE if g.headers['White'] == 'Opus Carlsen' else chess.BLACK
b = g.board(); start = b.fen(); hist = []; own = 0; played = None
for mv in g.mainline_moves():
    if b.turn == ours:
        own += 1
        if b.fullmove_number == target:
            played = mv.uci(); break
    hist.append(mv.uci()); b.push(mv)
fen = b.fen()
p = Probe(); rows = []
for n in nodes_list:
    p.setup(start, hist, budget=3600); p.e.move_number = own - 1; p.e.prev_score_valid = False
    t0 = time.perf_counter()
    got, sc, d = p.e.think(1e9, 1e9, max_nodes=n, log=False)
    rows.append(dict(nodes=int(p.e.info[S.I_NODES]), move=got, score=int(sc), depth=int(d), seldepth=int(p.e.info[S.I_SELDEPTH]), secs=round(time.perf_counter() - t0, 1), pv=p.e.pv_line(12)))
    print(json.dumps(rows[-1]), flush=True)
    out.write_text(json.dumps(dict(build=str(build), env={k: v for k, v in os.environ.items() if k.startswith('BINI_')}, pgn=str(pgn_path), fullmove=target, own_move=own, fen=fen, played=played, hashes=build_hashes(), rows=rows), indent=1))
print('done', out)
