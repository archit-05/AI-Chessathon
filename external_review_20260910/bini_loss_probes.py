"""Diagnostic ablations only. Not timed strength tests or faithful warm-state replay."""
import os,sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['BINI_DIR']=str(ROOT/'bini_v8_ship')
os.environ['BINI_TT_BITS']='24'
sys.path.insert(0,str(ROOT/'astra_tests'))
from harness import Probe,B,N,S,chess
import chess.pgn
p=Probe();rows=[]
targets={104:{60,78,81},100:{29},103:{31},105:{33}}
arms={'baseline':{},'quiet_checks':{S.I_QS_CHECKS:1},'no_correction':{S.I_CORR:0},'no_see_pruning':{S.I_SEEP:0},'no_null':{S.I_NMP_OFF:1}}
baseinfo=p.e.info.copy()
for rd,nums in targets.items():
 path=next(q for q in Path.home().joinpath('Downloads').glob(f'aichessathon-round-{rd}-*.pgn') if '(' not in q.name and '-vs-' not in q.name)
 g=chess.pgn.read_game(path.open());b=g.board();initial=b.fen();past=[];own=0
 side=g.headers['White']=='Opus Carlsen'
 for m in g.mainline_moves():
  if b.turn==side:
   own+=1
   if b.fullmove_number in nums:
    for arm,settings in arms.items():
     p.e.info[:]=baseinfo
     p.setup(initial,past,budget=300)
     p.e.move_number=own-1
     for k,v in settings.items():p.e.info[k]=v
     raw=int(N.nnue_eval(p.e.bb,p.e.st,p.e.acc,p.e.w2,p.e.b2))
     got,score,depth=p.e.think(300000,300000,max_nodes=1000000,log=False)
     row=dict(round=rd,number=b.fullmove_number,arm=arm,raw=raw,got=got,score=score,depth=depth,nodes=int(p.e.info[S.I_NODES]),played=m.uci(),pv=p.e.pv_line(12))
     rows.append(row);(ROOT/'external_review_20260910/loss_audit/bini_probes.json').write_text(json.dumps(rows,indent=2));print(json.dumps(row),flush=True)
  b.push(m);past.append(m.uci())
