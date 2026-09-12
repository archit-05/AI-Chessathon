"""End-to-end robustness battery through the PACKAGE interface (agent.get_move), fresh interpreter, no BINI_* env.
Odd but legal inputs the live harness could hand us: en-passant squares, no castling rights, promotions, halfmove 99,
bare-bones endings, checks, mate-in-one, black to move, book-boundary positions, Chess960-like castling layouts,
plus the 300 ms and 5 s budgets. Every answer must be legal and on time.  usage: (cd <package_dir> && python fen_battery.py)"""
import time, sys, chess
t0 = time.perf_counter(); import agent; t_import = time.perf_counter() - t0
FENS = [
 ("start", "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"),
 ("ep square set (book must skip)", "rnbqkbnr/pp2pppp/8/2ppP3/8/8/PPPP1PPP/RNBQKBNR w KQkq d6 0 3"),
 ("ep capture legal", "rnbqkbnr/ppp1p1pp/8/3pPp2/8/8/PPPP1PPP/RNBQKBNR w KQkq f6 0 3"),
 ("no castling rights", "r3k2r/pppq1ppp/2n2n2/3pp3/3PP3/2N2N2/PPPQ1PPP/R3K2R w - - 4 9"),
 ("promotion available", "8/P6k/8/8/8/8/8/K7 w - - 0 1"),
 ("black promotes with check", "k7/8/8/8/8/8/p6K/8 b - - 0 1"),
 ("halfmove 99", "8/8/8/3k4/8/8/4K3/R7 w - - 99 120"),
 ("KRvKR dead draw", "8/6rk/8/2K5/8/R7/8/8 w - - 40 163"),
 ("in check", "rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3"),
 ("mate in one", "6k1/5ppp/8/8/8/8/5PPP/3R2K1 w - - 0 1"),
 ("only pawns", "4k3/pppppppp/8/8/8/8/PPPPPPPP/4K3 w - - 0 1"),
 ("black to move, book range", "rnbqkb1r/pppp1ppp/4pn2/8/2PP4/8/PP2PPPP/RNBQKBNR b KQkq - 0 3"),
 ("fullmove 20 boundary", "r2q1rk1/1b2bppp/p2p1n2/1p2p3/4P3/1BN2N2/PP3PPP/R2QR1K1 w - - 0 20"),
 ("fullmove 21 (book must be off)", "r2q1rk1/1b2bppp/p2p1n2/1p2p3/4P3/1BN2N2/PP3PPP/R2QR1K1 w - - 0 21"),
 ("960-like layout, standard castling letters", "nrbqkbrn/pppppppp/8/8/8/8/PPPPPPPP/NRBQKBRN w KQkq - 0 1"),
 ("960-like layout, no castling", "bbqnnrkr/pppppppp/8/8/8/8/PPPPPPPP/BBQNNRKR w - - 0 1"),
 ("many queens", "QQQQk3/8/8/8/8/8/8/K7 w - - 0 1"),
 ("stalemate trap avoid", "7k/5Q2/6K1/8/8/8/8/8 w - - 0 1"),
]
bad = 0
for budget in (5000, 300):
    for name, fen in FENS:
        b = chess.Board(fen)
        if not b.is_valid(): print(f"  skip invalid fen: {name}"); continue
        if b.is_game_over(): continue
        t = time.perf_counter()
        try:
            mv = agent.get_move(fen, budget); dt = (time.perf_counter() - t) * 1000
            legal = chess.Move.from_uci(mv) in b.legal_moves
            ok = legal and dt <= budget * 1.15 + 150
        except Exception as e:
            mv, dt, legal, ok = f"EXC {type(e).__name__}: {e}", (time.perf_counter() - t) * 1000, False, False
        bad += 0 if ok else 1
        print(f"{'OK ' if ok else 'BAD'} budget {budget:5d}ms  {dt:7.0f}ms  {str(mv):10s} legal={legal}  {name}", flush=True)
print(f"import {t_import:.1f}s; BATTERY {'PASS' if bad == 0 else 'FAIL'} ({bad} bad)")
