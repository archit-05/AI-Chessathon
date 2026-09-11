#!/bin/bash
# Build a reviewable archive from a candidate tree and check it against the frozen baseline.
# Building an archive is NOT uploading; nothing here contacts the platform.
set -euo pipefail
SRC="${1:?usage: package_astra.sh <candidate-dir> <out.zip>}"
OUT="${2:?usage: package_astra.sh <candidate-dir> <out.zip>}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/$SRC"
rm -f "$ROOT/$OUT"
zip -q -X "$ROOT/$OUT" agent.py bini_*.py nnue.safetensors book.json
cd "$ROOT"
python3 - "$OUT" <<'PY'
import hashlib, sys, zipfile
out = sys.argv[1]
BASE = "submission_v8_0910_0313.zip"
z = zipfile.ZipFile(out)
names = sorted(z.namelist())
total = sum(i.file_size for i in z.infolist())
assert "agent.py" in names, "agent.py must sit at the zip root"
assert all("/" not in n for n in names), "no folders in the zip"
assert total < 50_000_000, f"{total} bytes unzipped exceeds the 50 MB limit"
base = zipfile.ZipFile(BASE)
bnames = sorted(base.namelist())
assert names == bnames, f"file list differs from the shipped baseline:\n new {names}\n old {bnames}"
raw = open(out, "rb").read()
print(f"{out}: {len(raw):,} bytes packed, {total:,} unzipped, {len(names)} files")
print("  sha256", hashlib.sha256(raw).hexdigest())
print("  md5   ", hashlib.md5(raw).hexdigest())
print("  per-file md5 (candidate vs frozen V8):")
for n in names:
    a = hashlib.md5(z.read(n)).hexdigest()
    b = hashlib.md5(base.read(n)).hexdigest()
    print(f"    {n:<20} {a}  {'SAME' if a == b else 'CHANGED'}")
PY
