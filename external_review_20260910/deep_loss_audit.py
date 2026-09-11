"""Independent deeper checks of specific choices, retaining complete game history."""
import json,sys
from pathlib import Path
import chess,chess.pgn,chess.engine
OUT=Path(__file__).parent/'loss_audit'
sf=chess.engine.SimpleEngine.popen_uci('/opt/homebrew/bin/stockfish')
sf.configure({'Threads':1,'Hash':128})
targets={104:{35,40,44,59,60,62,73,78,81,83},105:{30,31,32,33,34},103:{24,25,30,31,34,36},100:{28,29,30},98:{}}
rows=[]
try:
 for rd,moves in targets.items():
  p=next(p for p in Path.home().joinpath('Downloads').glob(f'aichessathon-round-{rd}-*.pgn') if '(' not in p.name and '-vs-' not in p.name)
  g=chess.pgn.read_game(p.open()); b=g.board();col=g.headers['White']=='Opus Carlsen'
  for m in g.mainline_moves():
   if b.turn==col and b.fullmove_number in moves:
    z=dict(round=rd,number=b.fullmove_number,fen=b.fen(),san=b.san(m),uci=m.uci())
    for label,kw in [('best',{}),('played',{'root_moves':[m]})]:
     sf.configure({'Clear Hash':None})
     a=sf.analyse(b,chess.engine.Limit(nodes=1000000),**kw);pv=a.get('pv',[])
     z[label]=dict(cp=a['score'].pov(b.turn).score(mate_score=30000),depth=a['depth'],nodes=a['nodes'],pv=[x.uci() for x in pv],san=b.variation_san(pv))
    rows.append(z);(OUT/'deep.json').write_text(json.dumps({'engine':sf.id,'rows':rows},indent=2))
    print(json.dumps(z),flush=True)
   b.push(m)
finally:sf.quit()
