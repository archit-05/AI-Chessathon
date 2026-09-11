import json,chess,chess.pgn,chess.engine
from pathlib import Path
rows=[];targets={113:{39},114:{39,40,41},116:{29}}
with chess.engine.SimpleEngine.popen_uci('/opt/homebrew/bin/stockfish') as sf:
 sf.configure({'Threads':1,'Hash':64});identity=sf.id
 for rd,ns in targets.items():
  p=next(p for p in Path.home().joinpath('Downloads').glob(f'aichessathon-round-{rd}-*.pgn') if '(' not in p.name);g=chess.pgn.read_game(p.open());b=g.board();ours=g.headers['White']=='Opus Carlsen'
  for m in g.mainline_moves():
   if b.turn==ours and b.fullmove_number in ns:
    z={'round':rd,'move':b.fullmove_number,'san':b.san(m),'fen':b.fen()}
    for lab,kw in [('best',{}),('played',{'root_moves':[m]})]:
     sf.configure({'Clear Hash':None});a=sf.analyse(b,chess.engine.Limit(nodes=600000),**kw);z[lab]={'cp':a['score'].pov(ours).score(mate_score=30000),'depth':a['depth'],'pv':b.variation_san(a.get('pv',[]))}
    rows.append(z);Path('FinalsDay/swiss_reference_checks.json').write_text(json.dumps({'engine':identity,'nodes':600000,'history':'complete from PGN start FEN','rows':rows},indent=2));print(json.dumps(z),flush=True)
   b.push(m)
