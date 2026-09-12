"""Init-time patch for the 30 s init budget (finals-day constraint). Applies in place to a build dir:
  1. agent.py: COMPILE_JOIN_S default 75 -> 21 (the ready line is the import; a wall-clock join keeps it under 30 s anywhere)
  2. agent.py: before any numba import, stage the engine sources at a fixed path with a fixed mtime, pin the numba CPU
     target (Haswell-level: AVX2, no AVX-512, runs on every EPYC/Xeon), point NUMBA_CACHE_DIR at /tmp and copy the shipped
     compiled cache (nbcache/) there, so numba loads the compiled functions instead of compiling (~35-60 s -> a few s).
     Any failure in the staging falls back to the old in-place import + compile.
  3. bini_*.py: @njit(cache=False -> cache=True
usage: patch_cache.py <build_dir>"""
import re, sys
from pathlib import Path
b = Path(sys.argv[1])
n = 0
for p in sorted(b.glob("bini_*.py")):
    s = p.read_text(); c = s.count("@njit(cache=False")
    if c: p.write_text(s.replace("@njit(cache=False", "@njit(cache=True")); n += c
print(f"cache=True on {n} jitted functions")
a = b / "agent.py"; s = a.read_text()
assert 'COMPILE_JOIN_S = float(os.environ.get("BINI_JOIN_S", "75"))' in s
s = s.replace('COMPILE_JOIN_S = float(os.environ.get("BINI_JOIN_S", "75"))', 'COMPILE_JOIN_S = float(os.environ.get("BINI_JOIN_S", "21"))  # finals: init budget 30 s; the join is wall-clock')
old = 'os.environ.setdefault("NUMBA_CACHE_DIR", "/tmp/numba_cache")\n'
assert s.count(old) == 1
new = '''# ---- finals-day init budget (30 s): load numba's compiled cache instead of compiling -----------------------------
# The package directory is read-only on the platform and its path is unknown; /tmp is writable scratch. numba keys a
# cache entry on the source file's (mtime, size) and on (target triple, CPU name, CPU features), so: stage the engine
# sources at a fixed path with a fixed mtime, pin the CPU target, and copy the shipped cache tree next to them.
import shutil  # noqa: E402
_PKG_DIR = Path(__file__).resolve().parent
_STAGE_DIR, _CACHE_DIR, _SRC_STAMP = Path("/tmp/bini_pkg"), Path("/tmp/bini_cache"), 1757600000
os.environ["NUMBA_CPU_NAME"] = "haswell"
os.environ["NUMBA_CPU_FEATURES"] = ("+64bit,+avx,+avx2,+bmi,+bmi2,+cmov,+cx16,+cx8,+f16c,+fma,+fsgsbase,+fxsr,+lzcnt,+mmx,"
                                    "+movbe,+pclmul,+popcnt,+rdrnd,+sahf,+sse,+sse2,+sse3,+sse4.1,+sse4.2,+ssse3,+x87,+xsave,+xsaveopt")
os.environ.setdefault("BINI_NNUE", str(_PKG_DIR / "nnue.safetensors"))
try:
    _STAGE_DIR.mkdir(parents=True, exist_ok=True)
    for _src in sorted(_PKG_DIR.glob("bini_*.py")):
        _dst = _STAGE_DIR / _src.name
        if not _dst.exists() or _dst.stat().st_size != _src.stat().st_size or _dst.read_bytes() != _src.read_bytes():
            shutil.copyfile(_src, _dst)
        os.utime(_dst, (_SRC_STAMP, _SRC_STAMP))
    if (_PKG_DIR / "nbcache").is_dir():
        shutil.copytree(_PKG_DIR / "nbcache", _CACHE_DIR, dirs_exist_ok=True)
    os.environ["NUMBA_CACHE_DIR"] = str(_CACHE_DIR)
    sys.path.insert(0, str(_STAGE_DIR))
    _STAGED = True
except Exception as _exc:  # noqa: BLE001 - never let the fast path break the import
    print(f"bini-5.0 WARNING: cache staging failed ({_exc!r}); compiling in place", file=sys.stderr, flush=True)
    os.environ.setdefault("NUMBA_CACHE_DIR", "/tmp/numba_cache")
    _STAGED = False
'''
s = s.replace(old, new)
assert "import bini_board as B" in s and s.index("_STAGE_DIR") < s.index("import bini_board as B")
a.write_text(s); print(f"agent.py patched: join 21 s + cache staging ({b})")
