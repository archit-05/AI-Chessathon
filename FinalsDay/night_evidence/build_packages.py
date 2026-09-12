"""Build upload-ready zips (deterministic timestamps) from build dirs. usage: build_packages.py build:name.zip ..."""
import sys, zipfile, hashlib
from pathlib import Path
out = Path.home() / "chess" / "packages"; out.mkdir(exist_ok=True); man = []
for arg in sys.argv[1:]:
    build, name = arg.split(":"); b = Path.home() / "chess" / build; zp = out / name
    files = ["agent.py"] + sorted(p.name for p in b.glob("bini_*.py")) + ["nnue.safetensors", "book.json"]
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            zi = zipfile.ZipInfo(f, date_time=(2026, 9, 12, 6, 0, 0)); zi.compress_type = zipfile.ZIP_DEFLATED; z.writestr(zi, (b / f).read_bytes())
    total = sum(i.file_size for i in zipfile.ZipFile(zp).infolist())
    man.append(f"{name}  sha256 {hashlib.sha256(zp.read_bytes()).hexdigest()}  zip {zp.stat().st_size:,} B  unzipped {total:,} B  from ~/chess/{build}")
    for f in files: man.append(f"    {hashlib.sha256((b / f).read_bytes()).hexdigest()[:16]}  {f}")
(out / "MANIFEST.txt").write_text("\n".join(man) + "\n"); print("\n".join(man))
