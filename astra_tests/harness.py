"""Shared scaffolding for the Astra correctness suite.

Loads one engine build (chosen by BINI_DIR) into this process and exposes helpers that
drive the *real* search/qsearch entry points rather than duplicating their predicates.
"""
import os, sys, time, json, platform
from pathlib import Path

os.environ.setdefault('BINI_TT_BITS', '16')
BINI_DIR = Path(os.environ.get('BINI_DIR', 'bini_v8_ship')).resolve()
sys.path.insert(0, str(BINI_DIR))

import numpy as np
import chess
import bini_board as B
import bini_engine as E
import bini_search as S
import bini_nnue as N
import bini_eval as V


def environment():
    import numba, llvmlite
    return dict(
        build_dir=str(BINI_DIR),
        python=sys.version.split()[0],
        numpy=np.__version__, numba=numba.__version__, llvmlite=llvmlite.__version__,
        python_chess=chess.__version__,
        platform=platform.platform(), machine=platform.machine(),
        tt_bits=os.environ.get('BINI_TT_BITS'),
    )


def build_hashes():
    import hashlib
    out = {}
    for f in sorted(BINI_DIR.iterdir()):
        if f.suffix in ('.py', '.json', '.safetensors'):
            out[f.name] = hashlib.md5(f.read_bytes()).hexdigest()
    return out


class Probe:
    """One engine instance; every helper leaves board state exactly as it found it."""

    def __init__(self):
        self.e = E.Engine()

    # ---- state -------------------------------------------------------------------
    def setup(self, fen, history_ucis=(), budget=30.0):
        """Place the engine at `fen` after replaying `history_ucis` as pre-root game history."""
        e = self.e
        e.new_game()
        board = chess.Board(fen)
        keys = []
        for u in history_ucis:
            B.set_fen(e.bb, e.st, e.pcs, board.fen())
            keys.append(int(e.bb[15]))
            board.push_uci(u)
        e.set_position(board.fen(), keys)
        e.info[S.I_ABORT] = 0
        e.info[S.I_NODES] = 0
        e.tlim[0] = time.perf_counter() + budget
        if e.info[S.I_USE_NNUE] != 0:
            N.nnue_refresh(e.bb, e.st, e.pcs, e.acc, e.w1, e.b1)
        return board

    def snapshot(self):
        e = self.e
        return (e.bb.copy(), e.st.copy(), e.pcs.copy(), e.ub.copy(), e.ui.copy(), e.acc.copy())

    def diff_snapshot(self, snap):
        e = self.e
        names = ('bb', 'st', 'pcs', 'ub', 'ui', 'acc')
        cur = (e.bb, e.st, e.pcs, e.ub, e.ui, e.acc)
        return [n for n, a, b in zip(names, snap, cur) if not np.array_equal(a, b)]

    def push(self, uci):
        e = self.e
        m = B.uci_to_move(e.bb, e.st, e.pcs, uci)
        assert m != 0, f'no such move {uci}'
        ok = B.make(e.bb, e.st, e.pcs, m, e.ub, e.ui)
        assert ok, f'illegal {uci}'
        if e.info[S.I_USE_NNUE] != 0:
            N.nnue_after_make(e.bb, e.st, e.pcs, e.acc, e.ui, m, e.w1, e.b1)
        return m

    def pop(self):
        B.unmake(self.e.bb, self.e.st, self.e.pcs, self.e.ub, self.e.ui)

    # ---- search entry points ----------------------------------------------------
    def qsearch(self, alpha=None, beta=None, qdepth=0):
        e = self.e
        a = -S.INF if alpha is None else alpha
        b = S.INF if beta is None else beta
        return int(S.qsearch(e.bb, e.st, e.pcs, e.mv, e.ub, e.ui, e.acc, e.tt_key, e.tt_data,
                             e.scores, e.info, e.tlim, e.w1, e.b1, e.w2, e.b2, a, b, 1, qdepth))

    def search(self, depth, alpha=None, beta=None):
        e = self.e
        a = -S.INF if alpha is None else alpha
        b = S.INF if beta is None else beta
        return int(S.search(e.bb, e.st, e.pcs, e.mv, e.ub, e.ui, e.acc, e.tt_key, e.tt_data,
                            e.killers, e.history, e.counters, e.scores, e.info, e.tlim, e.hist,
                            e.w1, e.b1, e.w2, e.b2, depth, a, b, 1))

    def is_repetition(self):
        # the C2 candidate takes `ui` so it can stop at a null-move ancestor; the baseline
        # does not - probe both so one suite runs against either build
        e = self.e
        try:
            return bool(S.is_repetition(e.bb, e.st, e.ub, e.ui, e.hist, e.info[S.I_HIST_N]))
        except TypeError:
            return bool(S.is_repetition(e.bb, e.st, e.ub, e.hist, e.info[S.I_HIST_N]))

    def evaluate(self):
        e = self.e
        return int(S.evaluate(e.bb, e.st, e.pcs, e.acc, e.info, e.w2, e.b2))

    def clear_tt(self):
        self.e.tt_key[:] = 0
        self.e.tt_data[:] = 0

    def clear_corr(self):
        self.e.scores[S.CORR_BASE:] = 0

    def poison_corr(self, value=None):
        """Saturate both correction slots for the side to move."""
        e = self.e
        v = S.CORR_LIMIT if value is None else value
        for which in (0, 1):
            e.scores[S.corr_index(e.bb, e.st[B.S_SIDE], which)] = v


class Results:
    def __init__(self, label):
        self.label = label
        self.rows = []

    def add(self, tid, title, status, **kw):
        row = dict(id=tid, title=title, status=status)
        row.update(kw)
        self.rows.append(row)
        mark = {'PASS': 'PASS', 'FAIL': 'FAIL', 'INFO': 'info', 'SKIP': 'skip',
                'XFAIL': 'xfail'}.get(status, status)
        extra = ' '.join(f'{k}={v}' for k, v in kw.items() if k not in ('detail',))
        print(f'[{mark:4}] {tid:<34} {title}' + (f'   {extra}' if extra else ''), flush=True)
        return row

    def summary(self):
        n = len(self.rows)
        f = sum(1 for r in self.rows if r['status'] == 'FAIL')
        p = sum(1 for r in self.rows if r['status'] == 'PASS')
        return dict(label=self.label, total=n, passed=p, failed=f,
                    xfail=sum(1 for r in self.rows if r['status'] == 'XFAIL'),
                    info=sum(1 for r in self.rows if r['status'] == 'INFO'))

    def dump(self, path, extra=None):
        payload = dict(summary=self.summary(), environment=environment(),
                       build_hashes=build_hashes(), rows=self.rows)
        if extra:
            payload.update(extra)
        Path(path).write_text(json.dumps(payload, indent=2, default=str))
        print(json.dumps(self.summary()), flush=True)
