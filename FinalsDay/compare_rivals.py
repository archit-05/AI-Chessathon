import json,sys,re,io,statistics,urllib.request,concurrent.futures
from pathlib import Path
import chess,chess.pgn
sys.path.insert(0,str(Path('intel').resolve()));import scrape
D=Path('FinalsDay');base=scrape.BASE
ids={'BINI':'f0286356-626d-4dd2-86ab-fd6d779063cb','Mite':'8c22f2a5-3bce-4b66-b93a-8f4ab4318b0f','PSL':'10021bb5-71a5-4b10-bde5-14e1f667501a'}
def fetch(u):
 with urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'}),timeout=20) as r:return r.read().decode()
teams={}
for name,uid in ids.items():
 p=fetch(base+'/team/'+uid);t=scrape.parse_team(scrape.resolve_streamed(p),uid);teams[name]=t
 print(name,[(g['round'],g['verdict']) for g in t['games'] if g['kind']=='Final'],flush=True)
gids=set(g['game'] for t in teams.values() for g in t['games'] if g['kind']=='Final')
# Include complete own Swiss corpus and cached missing team rows where available.
for z in json.load(open(D/'swiss_games.json')):gids.add(z['public']['game'])
def get(gid):
 p=Path('intel/raw/cache/games')/(gid+'.json')
 if p.exists():
  x=json.load(p.open())
  if x.get('evals'):return gid,x
 try:return gid,scrape.parse_game(fetch(base+'/game/'+gid),gid)
 except Exception as e:return gid,{'error':str(e)}
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:games=dict(pool.map(get,gids))
res={'fetched_at':scrape.now(),'teams':teams,'games':games};(D/'rival_comparison_raw.json').write_text(json.dumps(res,indent=2))
summary={}
for name,uid in ids.items():
 allm=[];gs=[]
 for gid,x in games.items():
  if not x or not x.get('pgn') or uid not in [x.get('white_uuid'),x.get('black_uuid')]:continue
  g=chess.pgn.read_game(io.StringIO(x['pgn']));b=g.board();col=x['white_uuid']==uid;prev=120.;own=0;mm=[];ev=x.get('evals');r=g.headers['Result'];score=.5 if r=='1/2-1/2' else float((r=='1-0')==col)
  for i,n in enumerate(g.mainline()):
   if b.turn==col:
    own+=1;c=n.clock();tm=None if c is None else prev+.5-c
    m={'round':g.headers['Round'],'number':b.fullmove_number,'own':own,'san':b.san(n.move),'seconds':None if tm is None else max(0,tm),'clock_before':prev,'clock_after':c,'legal_count':b.legal_moves.count(),'pieces':len(b.piece_map())}
    if ev and i+1<len(ev['cp']):
     a=ev['cp'][i]*(1 if col else -1);z=ev['cp'][i+1]*(1 if col else -1);m.update(before=a,after=z,cpl=max(0,a-z) if abs(a)<800 and abs(z)<800 else None)
    mm.append(m);prev=c if c is not None else prev
   b.push(n.move)
  allm+=mm;si=0 if col else 1;sides=x.get('review',{}).get('sides',[])
  gs.append({'round':g.headers['Round'],'score':score,'moves':len(mm),'final_clock':prev,'accuracy':sides[si].get('accuracy') if len(sides)>si else None,'site_acpl':sides[si].get('acpl') if len(sides)>si else None,'termination':g.headers.get('Termination'),'max_cp':max([m['before'] for m in mm if 'before'in m],default=None),'losses_100':sum(m.get('cpl',0)>=100 for m in mm if m.get('cpl')is not None)})
 def avg(a):return round(statistics.mean(a),3) if a else None
 times=[m['seconds'] for m in allm if m['seconds']is not None];early=[m for m in allm if m['own']<=6 and m['seconds']is not None];q=[m['cpl'] for m in allm if m.get('cpl')is not None]
 s={'games':gs,'n_games':len(gs),'moves':len(allm),'timing_mean':avg(times),'timing_median':statistics.median(times),'first6_instant':sum(m['seconds']<.05 for m in early),'first6_count':len(early),'mean_endclock':avg([g['final_clock'] for g in gs]),'games_end_under10':sum(g['final_clock']<10 for g in gs),'q_n':len(q),'mean_clipped_cpl':avg(q),'errors100':sum(v>=100 for v in q),'errors200':sum(v>=200 for v in q),'mean_game_acpl':avg([g['site_acpl'] for g in gs if g['site_acpl']is not None]),'moves_data':allm}
 summary[name]=s;print(name,json.dumps({k:v for k,v in s.items() if k not in ['moves_data','games']}),flush=True)
(D/'rival_comparison_metrics.json').write_text(json.dumps(summary,indent=2))
