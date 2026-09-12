"""External opponent for gates: Stockfish at a fixed UCI_Elo behind the platform's agent interface (get_move(fen, ms)).
Plain UCI over a pipe, no threads, so the runner process exits cleanly and Stockfish quits on stdin EOF."""
import os, subprocess, chess
ELO = int(os.environ.get("SF_ELO", "2400")); BIN = os.environ.get("SF_BIN", os.path.expanduser("~/chess/stockfish"))
_p = None
def _until(prefix):
    while True:
        line = _p.stdout.readline()
        if not line: raise RuntimeError("stockfish exited")
        if line.startswith(prefix): return line
def _proc():
    global _p
    if _p is None or _p.poll() is not None:
        _p = subprocess.Popen([BIN], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1)
        _p.stdin.write("uci\n"); _p.stdin.flush(); _until("uciok")
        _p.stdin.write(f"setoption name Threads value 1\nsetoption name Hash value 128\nsetoption name UCI_LimitStrength value true\nsetoption name UCI_Elo value {ELO}\nucinewgame\nisready\n"); _p.stdin.flush(); _until("readyok")
    return _p
def get_move(fen: str, time_left_ms: int) -> str:
    p = _proc(); think_ms = int(max(50, min(time_left_ms * 0.035 + 300, 5000)))  # ~3.5 % of the clock + the increment, capped at 5 s
    p.stdin.write(f"position fen {fen}\ngo movetime {think_ms}\n"); p.stdin.flush()
    mv = _until("bestmove").split()[1]
    if chess.Move.from_uci(mv) not in chess.Board(fen).legal_moves: raise RuntimeError(f"illegal from stockfish: {mv}")
    return mv
