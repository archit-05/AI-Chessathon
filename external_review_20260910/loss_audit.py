"""Read-only game analysis; finite Stockfish searches are estimates, not proofs."""
import json, re, time
from pathlib import Path
import chess, chess.pgn, chess.engine

OUT = Path(__file__).parent / 'loss_audit'
OUT.mkdir(exist_ok=True)
DL = Path.home() / 'Downloads'
sf = chess.engine.SimpleEngine.popen_uci('/opt/homebrew/bin/stockfish')
sf.configure({'Threads': 1, 'Hash': 128})

def analyse(b, move=None, nodes=80000):
    sf.configure({'Clear Hash': None})
    kw = {'root_moves': [move]} if move else {}
    z = sf.analyse(b, chess.engine.Limit(nodes=nodes), **kw)
    return dict(cp=z['score'].pov(b.turn).score(mate_score=30000),
                mate=z['score'].pov(b.turn).mate(), depth=z.get('depth'),
                nodes=z.get('nodes'), pv=[m.uci() for m in z.get('pv', [])])

try:
    for rd in [104,105,103,100,98,99,102,101,97,94,93,95,96,91,92]:
        files = sorted(p for p in DL.glob(f'aichessathon-round-{rd}-*.pgn') if '(' not in p.name and '-vs-' not in p.name)
        if not files: continue
        g = chess.pgn.read_game(files[0].open()); b = g.board()
        col = chess.WHITE if g.headers['White'] == 'Opus Carlsen' else chess.BLACK
        logs = sorted(p for p in DL.glob(f'aichessathon-round-{rd}-*.log') if '(' not in p.name)
        log = logs[0].read_text() if logs else ''
        entries = {}
        for mt in re.finditer(r'bini-[\d.]+ m(\d+) d(\d+) (\w+) (-?\d+)cp (\d+)n (\d+)ms left (\d+)ms', log):
            no,d,u,cp,n,ms,left = mt.groups()
            entries[int(no)] = dict(depth=int(d),uci=u,cp=int(cp),nodes=int(n),ms=int(ms),left=int(left))
        rows=[]; own=0
        for move in g.mainline_moves():
            if b.turn == col:
                own+=1
                best=analyse(b); played=best if best['pv'] and best['pv'][0]==move.uci() else analyse(b,move)
                rows.append(dict(round=rd,number=b.fullmove_number,decision=own,fen=b.fen(),
                                 san=b.san(move),uci=move.uci(),best=best,played=played,
                                 loss=best['cp']-played['cp'],live=entries.get(own)))
            b.push(move)
        data=dict(headers=dict(g.headers),source=str(files[0]),engine=sf.id,rows=rows)
        (OUT/f'r{rd}_screen.json').write_text(json.dumps(data,indent=2))
        suspects=[r for r in rows if r['best']['mate'] is None and -500<r['best']['cp']<1500]
        top=sorted(suspects,key=lambda r:r['loss'],reverse=True)[:8]
        print(json.dumps({'round':rd,'top':[{'move':r['number'],'san':r['san'],'best':r['best']['cp'],'played':r['played']['cp'],'loss':r['loss']} for r in top]}),flush=True)
finally:
    sf.quit()
