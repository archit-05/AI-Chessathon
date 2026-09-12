"""Exact-package smoke: zip a build the way package_astra.sh does, extract into an empty dir, import
agent in a FRESH interpreter with the production join (no BINI_* env), require nnue=on, one legal
move, report init seconds and peak RSS.  usage: pkg_smoke.py <build_dir> <tag>"""
import os, sys, zipfile, hashlib, tempfile, subprocess, shutil, time
from pathlib import Path
build, tag = Path(sys.argv[1]).resolve(), sys.argv[2]
gates = Path.home() / 'chess' / 'gates'; gates.mkdir(exist_ok=True)
zp = gates / f'{tag}.zip'
files = ['agent.py'] + sorted(p.name for p in build.glob('bini_*.py')) + ['nnue.safetensors', 'book.json']
with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED) as z:
    for f in files: z.write(build / f, f)
total = sum(i.file_size for i in zipfile.ZipFile(zp).infolist())
print(f"{tag}: zip sha256 {hashlib.sha256(zp.read_bytes()).hexdigest()[:16]} files={len(files)} unzipped={total:,} bytes ({'OK' if total < 50_000_000 else 'TOO BIG'})", flush=True)
d = Path(tempfile.mkdtemp(prefix='smoke_'))
zipfile.ZipFile(zp).extractall(d)
env = {k: v for k, v in os.environ.items() if not k.startswith('BINI_')}
code = ("import time,sys\nt0=time.perf_counter(); import agent; t1=time.perf_counter()-t0\n"
        "ok=agent._ready.is_set() and agent._engine is not None and bool(agent._engine.use_nnue)\n"
        "import chess\nfen='r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4'\n"
        "t2=time.perf_counter(); m=agent.get_move(fen,120000); dt=time.perf_counter()-t2\n"
        "print(f'SMOKE init={t1:.1f}s nnue_ready={ok} move={m} legal={chess.Move.from_uci(m) in chess.Board(fen).legal_moves} move_secs={dt:.2f}', file=sys.stderr, flush=True)\n")
t0 = time.perf_counter()
r = subprocess.run(['/usr/bin/time', '-v', sys.executable, '-c', code], cwd=d, env=env, capture_output=True, text=True, timeout=300)
for ln in r.stderr.splitlines():
    if 'SMOKE' in ln or 'ready:' in ln or 'Maximum resident' in ln or 'WARNING' in ln or 'FAILED' in ln: print('  ' + ln.strip(), flush=True)
print(f"  wall={time.perf_counter()-t0:.1f}s rc={r.returncode}", flush=True)
shutil.rmtree(d, ignore_errors=True)
