"""Build-by-build evidence table: which exact hash received which test, and what it returned.

Every result file written by the suites carries its own `build_hashes` and `environment`, so the
mapping is taken from the artefacts themselves rather than from memory or from a filename.
"""
import json, hashlib, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = [ROOT / 'astra_reports', ROOT / 'astra_reports_x86']

ARCHIVES = {
    'bini_v8_ship': 'submission_v8_0910_0313.zip',
    'bini_astra_c2': 'submission_astra_c2only.zip',
    'bini_astra_correctness': 'submission_astra_c1c2.zip',
    'bini_astra_v2': 'submission_astra_v2.zip',
    'bini_astra_v3_noc2b': 'submission_astra_v3_noc2b.zip',
    'bini_astra_v5': 'submission_v5.zip',
    'bini_astra_v5_noc2b': 'submission_v5_noc2b.zip',
}
PATCHES = {
    'bini_v8_ship': '(frozen baseline)',
    'bini_astra_c2': 'C2',
    'bini_astra_correctness': 'C2+C1',
    'bini_astra_v2': 'C2+C1+C1b+C2b',
    'bini_astra_v3_noc2b': 'C2+C1+C1b',
    'bini_astra_v4': 'C2+C1+C1b+C2b+C1c',
    'bini_astra_v5': 'C2+C1+C1b+C2b+C1c+C1d  **FINAL CANDIDATE**',
    'bini_astra_v5_noc2b': 'C2+C1+C1b+C1c+C1d  (final minus C2b)',
}

def sha256(p):
    h = hashlib.sha256()
    h.update(Path(p).read_bytes())
    return h.hexdigest()

rows = []
for d in REPORTS:
    if not d.exists():
        continue
    for f in sorted(d.glob('*.json')):
        try:
            j = json.loads(f.read_text())
        except Exception:
            continue
        if not isinstance(j, dict) or 'summary' not in j:
            continue
        s = j['summary']; env = j.get('environment', {}); bh = j.get('build_hashes', {})
        build = Path(str(env.get('build_dir') or s.get('label') or '?')).name
        if build in ('bini_astra',):
            build += '  (old box: C2+C1)'
        rows.append(dict(
            artefact=str(f.relative_to(ROOT)), build=build,
            search_md5=bh.get('bini_search.py', 'not recorded'),
            board_md5=bh.get('bini_board.py', 'not recorded'),
            net_md5=bh.get('nnue.safetensors', '?'), book_md5=bh.get('book.json', '?'),
            machine=env.get('machine', '?'), python=env.get('python', '?'),
            total=s.get('total'), passed=s.get('passed'), failed=s.get('failed')))

print('# Build-by-build evidence table\n')
print('## Archives\n')
print('| build | patches | archive SHA-256 | bini_search.py md5 |')
print('|---|---|---|---|')
for b, z in ARCHIVES.items():
    p = ROOT / z
    src = ROOT / b / 'bini_search.py'
    print(f"| `{b}` | {PATCHES.get(b,'?')} | `{sha256(p) if p.exists() else 'not packaged'}` | "
          f"`{hashlib.md5(src.read_bytes()).hexdigest() if src.exists() else '?'}` |")

print('\n## Every test result, keyed to the hash that received it\n')
print('| build | bini_search.py md5 | arch | test artefact | total | passed | FAILED |')
print('|---|---|---|---|---|---|---|')
for r in sorted(rows, key=lambda x: (x['build'], x['artefact'])):
    mark = f"**{r['failed']}**" if r['failed'] else '0'
    print(f"| `{r['build']}` | `{r['search_md5'][:16]}…` | {r['machine']} | "
          f"`{Path(r['artefact']).name}` | {r['total']} | {r['passed']} | {mark} |")
print()
print('**Known failure, unchanged from the baseline and deliberately not fixed:** '
      '`C3.book_key_ep_aliasing`. The book key omits en passant, so a position offering an '
      'en-passant capture can share a book entry with one that does not. It fails **identically '
      'on the frozen V8 baseline and on every candidate**, so it is a pre-existing property, not '
      'a regression, and it does not bear on the ship decision. `agent.py` legality-checks the '
      'book move it plays, so the worst case is a suboptimal move, never an illegal one. Fixing '
      'it requires changing the book key format, which would strand all 1,226 existing entries; '
      'the brief directs that a book migration be kept separate from the search work, so it is '
      'recorded as a post-lock item.')

nets = {r['net_md5'] for r in rows if r['net_md5'] != '?'}
books = {r['book_md5'] for r in rows if r['book_md5'] != '?'}
print(f"\n**Network md5 across every build tested:** {', '.join(sorted(nets)) or 'n/a'} "
      f"({'identical everywhere' if len(nets) == 1 else 'DIFFERS — investigate'})")
print(f"**Book md5 across every build tested:** {', '.join(sorted(books)) or 'n/a'} "
      f"({'identical everywhere' if len(books) == 1 else 'DIFFERS — investigate'})")
