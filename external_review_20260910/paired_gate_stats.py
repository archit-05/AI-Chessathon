"""Recompute completed-gate uncertainty, clustered by start FEN.

Usage: python paired_gate_stats.py completed.pgn --agent bini_candidate --expected-games 400
Requires full, named-player PGNs. Rejects missing pairs, voids and infrastructure failures.
Repeated games on the same FEN stay in one cluster. This is an approximate cluster-normal
interval over sampled openings, not a cure for unrepresentative opening selection.
"""
import argparse, collections, json, math, statistics
import chess.pgn

def elo(p):
    return 400*math.log10(p/(1-p)) if 0 < p < 1 else (-math.inf if p<=0 else math.inf)

def main():
    p=argparse.ArgumentParser()
    p.add_argument('pgn'); p.add_argument('--agent',required=True)
    p.add_argument('--expected-games',type=int,required=True)
    a=p.parse_args(); groups=collections.defaultdict(list); scores=[]; wdl=collections.Counter()
    with open(a.pgn) as f:
        while (g:=chess.pgn.read_game(f)) is not None:
            result=g.headers.get('Result'); term=g.headers.get('Termination','').lower()
            if result not in ('1-0','0-1','1/2-1/2') or term in ('crash','illegal','flag','init','both_failed'):
                raise SystemExit('Invalid gate: unfinished/void/infrastructure game; audit both arms first')
            names=[g.headers.get('White'),g.headers.get('Black')]
            if names.count(a.agent)!=1:raise SystemExit(f'Agent must match exactly one player: {names}')
            white=names[0]==a.agent
            s=.5 if result=='1/2-1/2' else float((result=='1-0')==white)
            scores.append(s); wdl[str(s)]+=1
            groups[g.board().fen()].append((white,s))
    if len(scores)!=a.expected_games:raise SystemExit(f'Incomplete gate: {len(scores)} != {a.expected_games}')
    for fen,rows in groups.items():
        if sum(w for w,s in rows)*2 != len(rows):raise SystemExit('Unbalanced colour cluster: '+fen)
    n=len(scores); k=len(groups); mean=statistics.mean(scores)
    if k<2:raise SystemExit('At least two opening clusters required')
    # Cluster sandwich for the overall per-game mean; allows unequal cluster sizes.
    se=math.sqrt(k/(k-1)*sum(sum(s-mean for _,s in rows)**2 for rows in groups.values()))/n
    low,high=mean-1.96*se,mean+1.96*se
    print(json.dumps(dict(games=n,opening_clusters=k,wdl=wdl,score=mean,score_ci95=[low,high],elo=elo(mean),elo_ci95=[elo(low),elo(high)],note='Approximate interval; complete gate only. Full logs must independently establish zero fallback and NNUE-on for both arms.'),indent=2))

if __name__=='__main__':main()
