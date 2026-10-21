"""Build the Overleaf upload: a manuscript that compiles with nothing else.

Overleaf gets a self-contained tree. Generated tables and figures are included
as built artefacts, because Overleaf has no access to the research repository
and could not rebuild them; the generators travel too, so the provenance of
every number is visible to anyone who opens the archive.

What does not travel: the working notes under audit/ that
audit/PUBLICATION.md marks as not shipping, LaTeX build products, and the
caches. The exclusions come from the manifest rather than from a list kept
here, so there is one place to change and one place to audit.

Preserved source documents do not travel either. They are stored once, in the
repository's own references/ directory, and the register that does travel
names the path of each. Overleaf compiles LaTeX, so a copy of a cited PDF
would add weight without adding anything a reader of the archive can use.

Refuses to build if the vocabulary check fails or if the manuscript has not
been compiled, since an archive whose PDF does not match its sources is worse
than no archive.

Usage:
    python build/package_overleaf.py [-o OUT.zip]
"""

from __future__ import annotations

import re
import subprocess
import sys
import zipfile
from pathlib import Path

PAPER_ROOT = Path(__file__).resolve().parent.parent
MANIFEST = PAPER_ROOT / "audit" / "PUBLICATION.md"

#: Everything Overleaf needs, in the order a reader would meet it.
INCLUDE_DIRS = ["sections", "tables", "figures", "references", "build", "audit"]
INCLUDE_FILES = ["main.tex"]

#: Build products and caches. main.pdf is added separately and deliberately.
SKIP_SUFFIXES = {".aux", ".log", ".out", ".fls", ".fdb_latexmk", ".blg",
                 ".synctex.gz", ".toc", ".pyc"}
SKIP_NAMES = {"__pycache__", ".DS_Store"}


def unpublished() -> set[Path]:
    text = MANIFEST.read_text(encoding="utf-8")
    _, _, tail = text.partition("## Does not ship")
    tail = tail.split("\n## ", 1)[0]
    return {Path("audit") / m for m in re.findall(r"`([^`/]+\.\w+)`", tail)}


def main(argv: list[str]) -> int:
    out = Path(argv[argv.index("-o") + 1]) if "-o" in argv else (
        PAPER_ROOT / "overleaf-gs-var.zip")

    check = subprocess.run([sys.executable, str(PAPER_ROOT / "build" / "scan_vocabulary.py")],
                           capture_output=True, text=True)
    if check.returncode != 0:
        print("vocabulary check failed; not packaging:\n" + check.stderr, file=sys.stderr)
        return 1

    pdf = PAPER_ROOT / "main.pdf"
    if not pdf.exists():
        print("main.pdf is missing. Compile before packaging so the archive "
              "carries a PDF that matches its sources.", file=sys.stderr)
        return 1

    skip = unpublished()
    members: list[Path] = [PAPER_ROOT / f for f in INCLUDE_FILES]
    for folder in INCLUDE_DIRS:
        for path in sorted((PAPER_ROOT / folder).rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(PAPER_ROOT)
            if relative in skip:
                continue
            if path.suffix in SKIP_SUFFIXES or any(p in SKIP_NAMES for p in relative.parts):
                continue
            members.append(path)
    members.append(pdf)

    out.unlink(missing_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in members:
            archive.write(path, path.relative_to(PAPER_ROOT).as_posix())

    size = out.stat().st_size
    print(f"wrote {out.name}: {len(members)} files, {size/1_048_576:.1f} MB")
    print(f"excluded {len(skip)} working note(s) per audit/PUBLICATION.md")
    print("Overleaf: upload the zip, set main.tex as the root document, and "
          "compile with pdfLaTeX. apacite needs two bibtex passes, which "
          "Overleaf runs automatically.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
