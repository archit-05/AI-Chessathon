"""Which jitted functions compile more than one specialisation (each costs compile time)? Run in the package dir."""
import os, sys, time; sys.path.insert(0, os.getcwd())
t = time.perf_counter(); import agent; agent._ready.wait(150)
import bini_board, bini_eval, bini_nnue, bini_search
rows = []
for modname, mod in (("board", bini_board), ("eval", bini_eval), ("nnue", bini_nnue), ("search", bini_search)):
    for name, obj in vars(mod).items():
        if hasattr(obj, "signatures") and hasattr(obj, "py_func"):
            n = len(obj.signatures)
            if n: rows.append((n, modname, name, len(obj.py_func.__code__.co_code)))
rows.sort(reverse=True)
print(f"compile {agent._compile_seconds:.1f}s; {len(rows)} compiled dispatchers, {sum(r[0] for r in rows)} specialisations")
for n, m, f, size in rows[:14]: print(f"  {n} sig  {m:6s} {f:28s} bytecode {size:6d}")
