#!/bin/bash
# Build submission.zip with agent.py at the root: every root .py plus the NNUE weights.
# Usage: bash tools/package.sh   (from the bini/ directory)
set -euo pipefail
cd "$(dirname "$0")/.."
rm -f submission.zip
zip -q -X submission.zip agent.py bini_*.py nnue.safetensors
echo "submission.zip:"; unzip -l submission.zip
python3 - <<'PY'
import zipfile
z = zipfile.ZipFile("submission.zip")
total = sum(i.file_size for i in z.infolist())
names = z.namelist()
assert "agent.py" in names, "agent.py must sit at the zip root"
assert all("/" not in n for n in names), "no folders in the zip"
assert total < 50_000_000, f"{total} bytes unzipped exceeds 50 MB"
print(f"{total:,} bytes unzipped, {len(names)} files: ok")
PY
