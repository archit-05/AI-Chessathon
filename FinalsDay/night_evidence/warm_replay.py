"""Reconstructed-warm replay: the deployed engine is fed the real game, every own move searched
at the LOGGED node count (deterministic, machine-independent), the board always advanced with the
move actually played.  At the target move the warm state is snapshotted and searched at several
node multipliers.  This is a reconstruction, not the live process (its TT is lost)."""
import os, sys, io, json, re, time
from pathlib import Path
ROOT = Path('/Users/architbhardwaj/Desktop/AI Chessathon')
os.environ['BINI_DIR'] = str(ROOT / 'bini_astra_v5_noc2b'); os.environ['BINI_TT_BITS'] = '24'
sys.path.insert(0, str(ROOT / 'astra_tests'))
from harness import B, E, N, S, chess
import chess.pgn
pgn_path, log_path, target_fullmove, out = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3]), Path(sys.argv[4])
mults = [float(x) for x in (sys.argv[5].split(',') if len(sys.argv) > 5 else ['1', '3', '10'])]
LOG = log_path.read_text()
logged = {int(m[0]): dict(depth=int(m[1]), uci=m[2], cp=int(m[3]), nodes=int(m[4]), ms=int(m[5]), left=int(m[6])) for m in re.findall(r'bini-[\d.]+ m(\d+) d(\d+) (\w+) (-?\d+)cp (\d+)n (\d+)ms left (\d+)ms', LOG)}
books = {int(m[0]): m[1] for m in re.findall(r'bini-[\d.]+ m(\d+) book (\w+)', LOG)}
g = chess.pgn.read_game(io.StringIO(pgn_path.read_text()))
ours = chess.WHITE if g.headers['White'] == 'Opus Carlsen' else chess.BLACK
board = g.board()
eng = E.Engine(); E.warm_up(eng); eng.new_game()
scratch = B.new_position()
def key(bd):
    bb, st, pcs = scratch; B.set_fen(bb, st, pcs, bd.fen()); return int(bb[15])
keys = []; own = 0; rows = []; started = False; result = None
def snap():
    return (eng.tt_key.copy(), eng.tt_data.copy(), eng.history.copy(), eng.counters.copy(), eng.scores.copy(), eng.killers.copy(), eng.prev_score, eng.prev_score_valid, eng.age)
def restore(s):
    eng.tt_key[:] = s[0]; eng.tt_data[:] = s[1]; eng.history[:] = s[2]; eng.counters[:] = s[3]; eng.scores[:] = s[4]; eng.killers[:] = s[5]; eng.prev_score, eng.prev_score_valid, eng.age = s[6], s[7], s[8]
t0 = time.perf_counter()
for mv in g.mainline_moves():
    if board.turn == ours:
        own += 1; started = True
        info = logged.get(own)
        if own in books:
            rows.append(dict(own=own, fullmove=board.fullmove_number, book=books[own], game=mv.uci()))
        elif info is None:
            rows.append(dict(own=own, fullmove=board.fullmove_number, note='no telemetry', game=mv.uci()))
        else:
            eng.set_position(board.fen(), keys); eng.move_number = own - 1
            if board.fullmove_number == target_fullmove:
                s = snap(); res = {}
                for m in mults:
                    restore(s); eng.set_position(board.fen(), keys); eng.move_number = own - 1
                    got, sc, d = eng.think(1e9, 1e9, max_nodes=int(info['nodes'] * m), log=False)
                    res[str(m)] = dict(move=got, score=int(sc), depth=int(d), nodes=int(eng.info[S.I_NODES]), pv=eng.pv_line(12))
                    print(json.dumps(dict(target=True, mult=m, **res[str(m)])), flush=True)
                result = dict(own=own, fullmove=board.fullmove_number, fen=board.fen(), game=mv.uci(), logged=info, arms=res)
                rows.append(result); break
            got, sc, d = eng.think(1e9, 1e9, max_nodes=info['nodes'], log=False)
            rows.append(dict(own=own, fullmove=board.fullmove_number, game=mv.uci(), replay=got, agree=got == mv.uci(), score=int(sc), depth=int(d), logged_cp=info['cp'], logged_depth=info['depth'], nodes=info['nodes']))
            print(json.dumps(rows[-1]), flush=True)
    if started: keys.append(key(board))
    board.push(mv)
agree = sum(1 for r in rows if r.get('agree') is True); n = sum(1 for r in rows if 'agree' in r)
summary = dict(pgn=str(pgn_path), ours='white' if ours else 'black', target_fullmove=target_fullmove, moves_replayed=n, moves_agreeing=agree, secs=round(time.perf_counter() - t0, 1), target=result, rows=rows)
out.write_text(json.dumps(summary, indent=1)); print(json.dumps({k: v for k, v in summary.items() if k != 'rows'}, indent=1))
