"""Check the repository for vocabulary that should not reach publication.

The project's standing rule is that the published repository carries the
research artefact and not the apparatus used to produce it. One section is a
deliberate exception: the declaration of generative AI use, which exists
precisely to say what the author used, keeps the wording and position it had in
the author's previous paper. Listing it here makes the exception auditable
rather than a matter of someone remembering it.

The set scanned is whatever git would publish: tracked files plus untracked
files that no ignore rule covers. Defining it that way rather than by a list
of directories means the check follows the repository instead of trailing it,
and a file added tomorrow is scanned without anyone editing this script. It
also means the check has to run from a working copy; asked to run anywhere
else, it fails rather than reporting on a set it cannot establish.

Exit status is 1 if anything is found outside the exception, so this can gate a
checkpoint.

Usage:
    python paper/build/scan_vocabulary.py
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

PAPER_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = PAPER_ROOT.parent

#: Text the scan can read. The compiled PDF is excluded as a build product of
#: files that are themselves scanned, and binary sources under references/ are
#: preserved documents by outside authors rather than project-authored text.
SUFFIXES = {".tex", ".py", ".bib", ".csv", ".md", ".yaml", ".yml", ".toml",
            ".txt", ".cfg", ".ini"}

#: Directories holding preserved third-party documents: filing text, papers
#: and official reports, stored verbatim. Their wording is not the project's
#: to control. The registers that describe them are project-authored and are
#: scanned, so the exclusion is by subdirectory rather than by
#: ``references/`` wholesale.
PRESERVED = (
    Path("references/sec_filings"),
    Path("references/papers"),
    Path("references/official_reports"),
)

#: The one file permitted to contain the terms below, and the heading that
#: has to be present in it for the exception to apply.
EXCEPTION = Path("paper/sections/declarations.tex")
EXCEPTION_HEADING = r"\section*{Declaration of generative AI use}"

#: This file states the terms it looks for, so it matches itself. Excluded by
#: identity rather than by pattern, so that a second scanner copied from it
#: would still be scanned.
SELF = Path(__file__).resolve().relative_to(REPO_ROOT)

#: Files under the manuscript's audit directory are classified ship-or-exclude
#: in this manifest. An unclassified file fails the check rather than being
#: quietly scanned or quietly skipped.
AUDIT_DIR = Path("paper/audit")
MANIFEST = AUDIT_DIR / "PUBLICATION.md"


class NoRepository(RuntimeError):
    """Raised when git cannot say what would be published.

    This check gates a publication checkpoint, so being unable to determine
    the published set is a failure rather than something to work around: a
    guess would report "clean" without having looked at the right files.
    """


def _candidates() -> list[Path]:
    """Every file git would publish: tracked, plus untracked and not ignored."""
    try:
        listing = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "ls-files", "--cached", "--others",
             "--exclude-standard"],
            capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError) as why:
        raise NoRepository(
            f"cannot list the published files from {REPO_ROOT}: {why}. Run "
            f"this from a working copy of the repository; a copy of the "
            f"manuscript on its own is not enough to tell what would ship."
        ) from why
    return sorted(Path(line) for line in listing.splitlines() if line)


def _unpublished() -> set[Path]:
    """Audit files the manifest marks as not shipping."""
    text = (REPO_ROOT / MANIFEST).read_text(encoding="utf-8")
    _, _, tail = text.partition("## Does not ship")
    # Stop at the next heading: prose after the table mentions files that do
    # ship, and reading past it would exclude them from the scan.
    tail = tail.split("\n## ", 1)[0]
    return {AUDIT_DIR / m for m in re.findall(r"`([^`/]+\.\w+)`", tail)}


def _classified() -> set[Path]:
    text = (REPO_ROOT / MANIFEST).read_text(encoding="utf-8")
    return {AUDIT_DIR / m for m in re.findall(r"`([^`/]+\.\w+)`", text)}

TERMS = re.compile(
    r"\b(claude|anthropic|openai|chatgpt|gpt-\d|copilot|gemini|llm|"
    r"large language model|language model|artificial intelligence|"
    r"ai[- ](?:generated|assisted|written|created)|ai|agentic|"
    r"prompt engineering|system prompt)\b",
    re.IGNORECASE,
)


def main() -> int:
    findings: list[tuple[Path, int, str]] = []

    try:
        candidates = _candidates()
    except NoRepository as why:
        print(why, file=sys.stderr)
        return 1

    skip = _unpublished()
    classified = _classified()
    present = {p.relative_to(REPO_ROOT) for p in (REPO_ROOT / AUDIT_DIR).glob("*")
               if p.is_file() and p.suffix in SUFFIXES}
    unclassified = sorted(present - classified)
    if unclassified:
        print(f"files absent from {MANIFEST}:", file=sys.stderr)
        for u in unclassified:
            print(f"  {u}", file=sys.stderr)
        print("Classify each as shipping or not before publishing.", file=sys.stderr)
        return 1

    scanned = 0
    for relative in candidates:
        if relative.suffix not in SUFFIXES:
            continue
        if relative in (EXCEPTION, SELF) or relative in skip:
            continue
        if any(d in relative.parents for d in PRESERVED):
            continue
        path = REPO_ROOT / relative
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        scanned += 1
        for number, line in enumerate(text.splitlines(), start=1):
            match = TERMS.search(line)
            if match:
                findings.append((relative, number, match.group(0)))

    # The exception only holds while the file is actually the declaration it
    # claims to be. A renamed or gutted file should not keep a free pass.
    exception_path = REPO_ROOT / EXCEPTION
    if not exception_path.exists():
        print(f"{EXCEPTION} is missing; the exception no longer applies.",
              file=sys.stderr)
        return 1
    if EXCEPTION_HEADING not in exception_path.read_text(encoding="utf-8"):
        print(f"{EXCEPTION} no longer contains {EXCEPTION_HEADING!r}. "
              f"Either restore it or remove the exception from this script.",
              file=sys.stderr)
        return 1

    if findings:
        print(f"{len(findings)} occurrence(s) outside the documented exception:",
              file=sys.stderr)
        for path, number, term in findings:
            print(f"  {path}:{number}: {term}", file=sys.stderr)
        return 1

    print(f"clean: {scanned} file(s) scanned, no occurrences outside "
          f"{EXCEPTION}, which carries the declaration of generative AI use "
          f"by design")
    print(f"       {len(skip)} working note(s) excluded from publication by "
          f"{MANIFEST}, and not scanned")
    print("       preserved third-party documents under "
          + ", ".join(f"{d}/" for d in PRESERVED)
          + " are not scanned; the registers describing them are")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
