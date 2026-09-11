import sys,json,re,urllib.request,concurrent.futures
from pathlib import Path
import chess,chess.pgn
sys.path.insert(0,str(Path('intel').resolve()));import scrape
out=Path('FinalsDay');dl=Path.home()/'Downloads'
def fetch(u):
 with urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'}),timeout=20) as r:return r.read().decode()
def game(rd):
 p=next(p for p in dl.glob(f'aichessathon-round-{rd}-*.pgn') if '(' not in p.name)
 g=chess.pgn.read_game(p.open());s=p.with_suffix('.log').read_text();gid=re.search(r'Match ID\s+(\S+)',s)[1];b=g.board();ours=g.headers['White']=='Opus Carlsen';moves=[]
 for m in g.mainline():
  if b.turn==ours:moves.append({'number':b.fullmove_number,'san':b.san(m.move),'uci':m.move.uci(),'fen':b.fen(),'clock':m.clock()})
  b.push(m.move)
 try:pub=scrape.parse_game(fetch(scrape.BASE+'/game/'+gid),gid)
 except Exception as e:pub={'error':str(e)}
 telemetry=[{'index':int(a),'depth':int(d),'uci':u,'cp':int(c),'nodes':int(n),'ms':int(t),'left_ms':int(l)} for a,d,u,c,n,t,l in re.findall(r'bini-[\d.]+ m(\d+) d(\d+) (\w+) (-?\d+)cp (\d+)n (\d+)ms left (\d+)ms',s)]
 return {'round':rd,'headers':dict(g.headers),'init':float(re.search(r'Ready in\s+([\d.]+)',s)[1]),'telemetry':telemetry,'moves':moves,'public':pub,'log':str(p.with_suffix('.log'))}
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:games=list(pool.map(game,range(110,123)))
for stage in ['knockout','swiss']:
 try:(out/f'{stage}_page.html').write_text(fetch(scrape.BASE+'/leaderboard?stage='+stage))
 except Exception as e:print(stage,e)
(out/'swiss_games.json').write_text(json.dumps(games,indent=2))
for x in games:
 p=x['public'];h=x['headers'];t=x['telemetry'];print(json.dumps({'round':x['round'],'white':h['White'],'black':h['Black'],'result':h['Result'],'init':x['init'],'own_moves':len(x['moves']),'lastclock':x['moves'][-1]['clock'],'cp_range': [min([z['cp'] for z in t],default=0),max([z['cp'] for z in t],default=0)],'review':p.get('review')}))
