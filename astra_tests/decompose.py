"""Separate the layers of a score for one position, so a wrong number can be attributed.

    raw        nnue_eval           the network's own output, side-to-move relative
    calib      + bini_calib        the calibration table (I_CALIB, off by default)
    scaled     + endgame_scale     the pawnless heuristic divide-by-8
    corrected  + corrected()       correction history (empty here unless --poison)
    qsearch    qsearch(-INF, INF)  the quiescence value at this node
    search d   search(depth)       the full search, cold table

Every layer is measured on the same position with the same engine, so the difference between
two adjacent rows is exactly what that layer did.
"""
import os, sys, json, argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness import Probe, S, B, N, V, chess, np


def layers(p, fen, depths=(1, 6, 10, 14, 18), poison=False):
    e = p.e
    p.setup(fen, budget=900.0)
    p.clear_tt(); p.clear_corr()
    if poison:
        p.poison_corr()
    side = int(e.st[B.S_SIDE])
    raw = int(N.nnue_eval(e.bb, e.st, e.acc, e.w2, e.b2))
    calib = int(V.calibrate(e.bb, side, raw)) if int(e.info[S.I_CALIB]) != 0 else raw
    scaled = int(V.endgame_scale(e.bb, calib))
    evaluated = int(S.evaluate(e.bb, e.st, e.pcs, e.acc, e.info, e.w2, e.b2))
    corr = int(S.corrected(e.scores, e.bb, side, evaluated, e.info[S.I_CORR]))
    p.clear_tt()
    qs = p.qsearch()
    row = dict(fen=fen, side='w' if side == 0 else 'b', raw=raw, calib=calib,
               scaled=scaled, evaluate=evaluated, corrected=corr, qsearch=qs)
    for d in depths:
        p.setup(fen, budget=900.0); p.clear_tt(); p.clear_corr()
        if poison:
            p.poison_corr()
        e.info[S.I_ROOT_MOVE] = 0
        sc = p.search(d)
        row[f'search_d{d}'] = sc
        row[f'move_d{d}'] = B.move_to_uci(int(e.info[S.I_ROOT_MOVE]))
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('positions', nargs='+', help='FEN[:label] entries')
    ap.add_argument('--depths', default='1,6,10,14,18')
    ap.add_argument('--poison', action='store_true')
    ap.add_argument('--out')
    a = ap.parse_args()
    depths = tuple(int(x) for x in a.depths.split(','))
    p = Probe()
    rows = []
    print(f"build: {os.environ.get('BINI_DIR')}")
    hdr = f"{'label':<10} {'stm':>3} {'raw':>7} {'scaled':>7} {'eval':>7} {'corr':>7} {'qs':>7}" + \
          ''.join(f" {'d'+str(d):>7}" for d in depths)
    print(hdr)
    for spec in a.positions:
        fen, _, label = spec.partition('|')
        r = layers(p, fen.strip(), depths, a.poison)
        r['label'] = label or fen[:12]
        rows.append(r)
        print(f"{r['label']:<10} {r['side']:>3} {r['raw']:>7} {r['scaled']:>7} {r['evaluate']:>7} "
              f"{r['corrected']:>7} {r['qsearch']:>7}" + ''.join(f" {r['search_d'+str(d)]:>7}" for d in depths))
    if a.out:
        Path(a.out).write_text(json.dumps(rows, indent=1))
        print('written', a.out)


if __name__ == '__main__':
    main()
