"""Hash every research output the manuscript quotes a number from.

The manuscript and the research repository are separate artefacts with
separate histories, which is the point: a figure in the paper has to be
traceable to a specific state of a specific file, not to whatever happens to
be on disk when someone rebuilds. This writes that record.

Refuses to run against a dirty working tree. A freeze taken over uncommitted
changes names a commit that does not contain the data it hashed, which is
worse than no freeze at all.

Usage:
    python build/freeze_evidence.py [--allow-dirty]
"""

from __future__ import annotations

import csv
import hashlib
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

PAPER_ROOT = Path(__file__).resolve().parent.parent
RESEARCH_ROOT = Path(
    os.environ.get("GSVAR_REPO_ROOT", PAPER_ROOT.parent)
).resolve()
OUTPUT = PAPER_ROOT / "audit" / "evidence_freeze.csv"

# What the manuscript is allowed to quote from. Anything outside this set has
# no business carrying a number into the paper.
FROZEN = [
    ("data/processed", "*.csv", "frozen analysis output"),
    ("reports/figures", "*.png", "frozen figure"),
    ("config", "params.yaml", "engine configuration"),
    # The manuscript quotes Goldman's own wording, so the text those quotes
    # were read from is evidence in the same sense a results table is.
    ("references/sec_filings", "*.txt", "preserved disclosure text"),
]


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(RESEARCH_ROOT), *args],
        capture_output=True, text=True, check=True,
    ).stdout.strip()


def main(argv: list[str]) -> int:
    if not (RESEARCH_ROOT / ".git").exists():
        raise SystemExit(
            f"{RESEARCH_ROOT} is not a git repository. Point GSVAR_REPO_ROOT "
            f"at the research repository."
        )

    dirty = _git("status", "--porcelain")
    if dirty and "--allow-dirty" not in argv:
        print("Working tree is not clean. Commit first, or pass "
              "--allow-dirty and accept that the recorded commit will not "
              "contain the hashed data.\n", file=sys.stderr)
        print(dirty, file=sys.stderr)
        return 1

    commit = _git("rev-parse", "HEAD")
    committed = _git("show", "-s", "--format=%ci", "HEAD")

    rows = []
    for folder, pattern, kind in FROZEN:
        for path in sorted((RESEARCH_ROOT / folder).glob(pattern)):
            payload = path.read_bytes()
            rows.append({
                "path": path.relative_to(RESEARCH_ROOT).as_posix(),
                "kind": kind,
                "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            })

    if not rows:
        raise SystemExit("nothing matched; check GSVAR_REPO_ROOT")

    OUTPUT.parent.mkdir(exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8", newline="") as handle:
        handle.write("# Evidence freeze for the GS VaR manuscript\n")
        handle.write(f"# Source repository commit: {commit}\n")
        handle.write(f"# Commit date: {committed}\n")
        handle.write(f"# Frozen on: {date.today().isoformat()}\n")
        handle.write(
            "# Working tree was clean at freeze time.\n" if not dirty
            else "# WARNING: frozen over a dirty working tree.\n"
        )
        handle.write("# Any later change to a listed file invalidates the "
                     "manuscript numbers that depend on it.\n")
        writer = csv.DictWriter(handle, fieldnames=["path", "kind", "bytes", "sha256"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"froze {len(rows)} files at {commit[:8]} -> "
          f"{OUTPUT.relative_to(PAPER_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
