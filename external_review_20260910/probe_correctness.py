"""Run against the frozen V8 sources; no engine files are edited."""
import os
os.environ['BINI_TT_BITS'] = '16'
import sys, json, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'bini_v8_ship'))
import chess
import bini_board as B
import bini_engine as E
import bini_search as S
import bini_nnue as N
eng=E.Engine()
rows=[]
def setup(fen):
    eng.new_game(); eng.set_position(fen,[])
    eng.info[S.I_ABORT]=0; eng.info[S.I_NODES]=0
    eng.tlim[0]=time.perf_counter()+10
def qs():
    return int(S.qsearch(eng.bb,eng.st,eng.pcs,eng.mv,eng.ub,eng.ui,eng.acc,eng.tt_key,eng.tt_data,eng.scores,eng.info,eng.tlim,eng.w1,eng.b1,eng.w2,eng.b2,-S.INF,S.INF,1,0))
def search(depth):
    return int(S.search(eng.bb,eng.st,eng.pcs,eng.mv,eng.ub,eng.ui,eng.acc,eng.tt_key,eng.tt_data,eng.killers,eng.history,eng.counters,eng.scores,eng.info,eng.tlim,eng.hist,eng.w1,eng.b1,eng.w2,eng.b2,depth,-S.INF,S.INF,1))
fen='k7/8/1QK5/8/8/8/8/8 b - - 0 1'
setup(fen)
rows.append(dict(test='qsearch_stalemate',fen=fen,oracle=chess.Board(fen).is_stalemate(),score=qs()))
fen='7k/6Q1/5K2/8/8/8/8/8 b - - 100 1'
setup(fen); eng.st[B.S_PLY]=1
N.nnue_refresh(eng.bb,eng.st,eng.pcs,eng.acc,eng.w1,eng.b1)
rows.append(dict(test='mate_at_halfmove_100_nonroot',fen=fen,oracle=chess.Board(fen).is_checkmate(),score=search(1)))
# Four reversible knight plies; root is halfway through the cycle.
board=chess.Board(); keys=[]
for uci in ('g1f3','g8f6'):
    B.set_fen(eng.bb,eng.st,eng.pcs,board.fen()); keys.append(int(eng.bb[15])); board.push_uci(uci)
eng.set_position(board.fen(),keys)
for uci in ('f3g1','f6g8'):
    m=B.uci_to_move(eng.bb,eng.st,eng.pcs,uci)
    assert B.make(eng.bb,eng.st,eng.pcs,m,eng.ub,eng.ui)
rows.append(dict(test='repetition_at_even_ply_history_boundary',expected=True,actual=bool(S.is_repetition(eng.bb,eng.st,eng.ub,eng.hist,eng.info[S.I_HIST_N])),halfmove=int(eng.st[B.S_HALF]),ply=int(eng.st[B.S_PLY])))
# Same material is not the same as a dead position: legal checkmate with B versus N.
fen='kn6/1B6/1K6/8/8/8/8/8 b - - 0 1'
b=chess.Board(fen)
rows.append(dict(test='bishop_vs_knight_can_mate',fen=fen,valid=b.is_valid(),checkmate=b.is_checkmate(),insufficient=b.is_insufficient_material()))
fen='7k/8/8/8/8/8/2B5/K7 w - - 0 1'
setup(fen)
for which in (0,1):eng.scores[S.corr_index(eng.bb,eng.st[B.S_SIDE],which)]=S.CORR_LIMIT
rows.append(dict(test='correction_can_change_zero',corrected=int(S.corrected(eng.scores,eng.bb,eng.st[B.S_SIDE],0,1))))
rows.append(dict(test='network_metadata',hidden=N.HIDDEN,buckets=N.NO,acc_dtype=str(N.ACC_DTYPE),bound=N.ACC_BOUND))
print(json.dumps(rows,indent=2))
ROOT.joinpath('external_review_20260910/correctness_results.json').write_text(json.dumps(rows,indent=2))
