"""Book candidate wrapper: (1) skip the book when a legal en-passant capture exists (the key ignores
en passant), (2) never consult the book beyond fullmove 20 (the published opening window), (3) log the
search budget each book move saved and one 'bookexit' line with hits, saved ms, exit fullmove and FEN.
Search, budget and everything else untouched.  usage: patch_guards.py <build_dir>"""
import sys
from pathlib import Path
p = Path(sys.argv[1]) / 'agent.py'; s = p.read_text()
def rep(old, new):
    global s
    assert s.count(old) == 1, old[:70]
    s = s.replace(old, new)
rep('''def _book_key(board: chess.Board) -> str:
    return f"{board.board_fen()} {'w' if board.turn else 'b'} {board.castling_xfen()}"
''', '''def _book_key(board: chess.Board) -> str:
    return f"{board.board_fen()} {'w' if board.turn else 'b'} {board.castling_xfen()}"


def _has_ep_capture(board: chess.Board) -> bool:
    """The book key carries no en-passant state, so a position where an en-passant capture is
    legal is never answered from the book."""
    return board.ep_square is not None and any(board.is_en_passant(m) for m in board.legal_moves)


_book_stats = {"hits": 0, "saved_ms": 0, "exited": False}
''')
rep('''    if _BOOK and _state.move_number < 12:
        entry = _BOOK.get(_book_key(board))
        if entry:
            bm = entry.get("move", "")
            if bm and chess.Move.from_uci(bm) in board.legal_moves:
                print(f"{VERSION} m{_state.move_number + 1} book {bm} d{entry.get('depth', 0)} {entry.get('score', 0)}cp left {time_left_ms}ms", file=sys.stderr, flush=True)
                _state.record_reply(board, bm)
                return bm
''', '''    # book only inside the published opening window (fullmove <= 20; our own move count is not the
    # PGN move number) and never where an en-passant capture is legal (the key does not encode it)
    if _BOOK and _state.move_number < 12 and board.fullmove_number <= 20 and not _has_ep_capture(board):
        entry = _BOOK.get(_book_key(board))
        if entry:
            bm = entry.get("move", "")
            if bm and chess.Move.from_uci(bm) in board.legal_moves:
                _book_stats["hits"] += 1
                _book_stats["saved_ms"] += int(soft)
                print(f"{VERSION} m{_state.move_number + 1} book {bm} d{entry.get('depth', 0)} {entry.get('score', 0)}cp left {time_left_ms}ms soft{int(soft)}ms", file=sys.stderr, flush=True)
                _state.record_reply(board, bm)
                return bm
    if _book_stats["hits"] and not _book_stats["exited"]:
        _book_stats["exited"] = True
        print(f"{VERSION} bookexit m{_state.move_number + 1} hits={_book_stats['hits']} saved={_book_stats['saved_ms']}ms fullmove={board.fullmove_number} left={time_left_ms}ms fen={board.fen()}", file=sys.stderr, flush=True)
''')
p.write_text(s); print('guards + book instrumentation applied to', p)
