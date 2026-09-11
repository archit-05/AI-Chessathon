"""Independent finite-node Stockfish triage; scores are estimates, not game-theoretic truth."""
import json
from pathlib import Path
import chess
import chess.engine
import chess.pgn

OUT = Path(__file__).resolve().parent
engine = chess.engine.SimpleEngine.popen_uci('/opt/homebrew/bin/stockfish')
engine.configure({'Threads': 1, 'Hash': 128})
rows = []
try:
    for round_no in (94, 98, 99, 100):
        path = next(p for p in Path.home().joinpath('Downloads').glob(f'aichessathon-round-{round_no}-*.pgn') if '(' not in p.name)
        game = chess.pgn.read_game(path.open())
        board = game.board()
        for move in game.mainline_moves():
            if board.turn == chess.WHITE:
                engine.configure({'Clear Hash': None})
                best = engine.analyse(board, chess.engine.Limit(nodes=150000))
                engine.configure({'Clear Hash': None})
                played = engine.analyse(board, chess.engine.Limit(nodes=150000), root_moves=[move])
                a = best['score'].white().score(mate_score=32000)
                b = played['score'].white().score(mate_score=32000)
                row = dict(round=round_no, move=board.fullmove_number, san=board.san(move), uci=move.uci(), fen=board.fen(), best=best['pv'][0].uci(), best_cp=a, played_cp=b, loss_cp=a-b, depth=best.get('depth'))
                rows.append(row)
            board.push(move)
        OUT.joinpath('stockfish_triage.json').write_text(json.dumps({'engine':engine.id,'nodes_per_search':150000,'rows':rows}, indent=2))
        print('Round',round_no,'largest estimated losses', sorted([r for r in rows if r['round']==round_no and abs(r['best_cp'])<2000],key=lambda r:r['loss_cp'],reverse=True)[:5],flush=True)
finally:
    engine.quit()
