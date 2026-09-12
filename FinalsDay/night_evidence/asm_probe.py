"""Is the NNUE code vectorised? Compile the real kernels in situ and count SIMD register/instruction use.
usage: asm_probe.py <build_dir>"""
import os, sys, re
from pathlib import Path
ROOT = Path('/Users/architbhardwaj/Desktop/AI Chessathon')
if not ROOT.exists(): ROOT = Path.home() / 'chess'
build = Path(sys.argv[1]).resolve(); os.environ['BINI_DIR'] = str(build); os.environ.setdefault('BINI_TT_BITS', '16'); os.environ.setdefault('BINI_EVAL_VARIANT', '1')
sys.path.insert(0, str(ROOT / 'astra_tests'))
from harness import Probe, B, N, S
p = Probe(); p.setup("r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4", [], budget=60); p.push("d2d3")
e = p.e
fns = {'nnue_eval_v0': N.nnue_eval_v0, 'nnue_after_make': N.nnue_after_make, 'nnue_refresh_persp': N.nnue_refresh_persp}
for name in ('nnue_eval_v1', 'nnue_eval_v2', '_sq_dot64', '_sq_dot32'):
    if hasattr(N, name): fns[name] = getattr(N, name)
# make sure every variant is compiled
for name in ('nnue_eval_v0', 'nnue_eval_v1', 'nnue_eval_v2'):
    if name in fns: fns[name](e.bb, e.st, e.acc, e.w2, e.b2)
if '_sq_dot64' in fns: fns['_sq_dot64'](e.acc[0, 0], e.w2[0, :N.HIDDEN])
if '_sq_dot32' in fns: fns['_sq_dot32'](e.acc[0, 0], e.w2[0, :N.HIDDEN])
import platform; print('machine', platform.machine(), 'variant', os.environ['BINI_EVAL_VARIANT'])
for name, f in fns.items():
    asms = f.inspect_asm()
    for sig, asm in asms.items():
        lines = asm.count('\n'); z = len(re.findall(r'\bzmm\d+', asm)); y = len(re.findall(r'\bymm\d+', asm)); x = len(re.findall(r'\bxmm\d+', asm)); v = len(re.findall(r'\bv\d+\.(?:4s|8h|16b|2d)\b', asm))
        ins = {k: len(re.findall(r'\b' + k + r'\b', asm)) for k in ('vpmuldq', 'vpmullq', 'vpmulld', 'vpmullw', 'vpmaddwd', 'vpaddq', 'vpaddd', 'vpmovsxwd', 'vpmaxsd', 'vpminsd', 'imul', 'smull', 'smlal', 'mul', 'sqadd', 'add')}
        ins = {k: c for k, c in ins.items() if c}
        print(f"{name:20s} lines={lines:5d} zmm={z:4d} ymm={y:4d} xmm={x:4d} neon_v={v:4d} {ins}", flush=True)
