import sys,json,urllib.request,concurrent.futures
from pathlib import Path
sys.path.insert(0,str(Path('intel').resolve()))
import scrape
out=Path('FinalsDay')
def fetch(url):
 with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=20) as r:return r.read().decode()
rows=scrape.parse_leaderboard(fetch(scrape.BASE+'/leaderboard?stage=qualifier'))
rows=sorted({r['uuid']:r for r in rows}.values(),key=lambda x:x['rank'])[:10]
def team(r):
 try:return scrape.parse_team(fetch(scrape.BASE+'/team/'+r['uuid']),r['uuid'])
 except Exception as e:return {'uuid':r['uuid'],'error':str(e)}
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:teams=list(pool.map(team,rows))
games=[]
for gid in ['ddedc6bd-6a61-42ac-924f-c79d31cfb16a','3ba1dabd-1b79-48cf-9661-9a1795900076','bb260f25-3c8f-4237-be7a-7c674023ee05']:
 try:games.append(scrape.parse_game(fetch(scrape.BASE+'/game/'+gid),gid))
 except Exception as e:games.append({'game':gid,'error':str(e)})
result={'fetched_at':scrape.now(),'leaderboard':rows,'teams':teams,'games':games}
(out/'public_snapshot.json').write_text(json.dumps(result,indent=2))
for r,t in zip(rows,teams):
 recent=[g for g in t.get('games',[]) if g['kind']=='Rated' and g['verdict'] in ['win','draw','loss']][:10]
 print(json.dumps({**r,'last10':{v:sum(g['verdict']==v for g in recent) for v in ['win','draw','loss']},'recent':recent[:3]}))
for g in games:
 print('GAME',json.dumps({k:v for k,v in (g or {}).items() if k not in ['pgn','evals','site_verdicts']}))
