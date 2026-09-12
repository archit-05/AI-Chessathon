"""Smoke the EXACT zip that will be uploaded: extract into an empty dir, import agent in a fresh interpreter with the
production join (no BINI_* env), require nnue=on, one legal move from a real opening position and one from a position
outside the book, report init seconds and peak RSS. usage: smoke_zip.py <package.zip>"""
import os, sys, zipfile, hashlib, tempfile, subprocess, time
from pathlib import Path
zp = Path(sys.argv[1]).resolve()
names = sorted(zipfile.ZipFile(zp).namelist()); total = sum(i.file_size for i in zipfile.ZipFile(zp).infolist())
need = {'agent.py', 'nnue.safetensors', 'book.json'}
print(f"{zp.name}: sha256 {hashlib.sha256(zp.read_bytes()).hexdigest()} zip={zp.stat().st_size:,} B unzipped={total:,} B "
      f"({'OK' if total < 50_000_000 else 'TOO BIG'}) files={len(names)} {'layout OK' if need <= set(names) and all('/' not in n for n in names) else 'LAYOUT WRONG: ' + str(names)}", flush=True)
d = Path(tempfile.mkdtemp(prefix='smokezip_')); zipfile.ZipFile(zp).extractall(d)
env = {k: v for k, v in os.environ.items() if not k.startswith('BINI_')}
code = ("import time,sys,chess\nt0=time.perf_counter(); import agent; t1=time.perf_counter()-t0\n"
        "ok=agent._ready.is_set() and agent._engine is not None and bool(agent._engine.use_nnue)\n"
        "for fen in ['r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4','8/5pk1/6p1/3R3p/7P/6P1/5PK1/3r4 w - - 0 45']:\n"
        "    t2=time.perf_counter(); m=agent.get_move(fen,120000); dt=time.perf_counter()-t2\n"
        "    print(f'SMOKE init={t1:.1f}s nnue_ready={ok} move={m} legal={chess.Move.from_uci(m) in chess.Board(fen).legal_moves} move_secs={dt:.2f}', file=sys.stderr, flush=True)\n")
r = subprocess.run(['/usr/bin/time', '-v', sys.executable, '-c', code], cwd=d, env=env, capture_output=True, text=True, timeout=300)
for ln in r.stderr.splitlines():
    if 'SMOKE' in ln or 'ready:' in ln or 'Maximum resident' in ln or 'WARNING' in ln or 'FAILED' in ln or 'Traceback' in ln or 'Error' in ln: print('  ' + ln.strip(), flush=True)
print('exit', r.returncode)
