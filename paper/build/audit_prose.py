"""Score the project's prose against the patterns that read as machine-written.

This is a reader-facing audit, not a detector. Statistical classifiers score
token-level fingerprints that none of these checks touch; what this catches is
the vocabulary and the sentence shapes that make a person who knows the
patterns stop trusting the page.

Counts, per file: banned lexicon, clustered second-tier lexicon, the
constructions that give the game away (negative parallelism, rule of three,
rhetorical question-and-answer, copula dodges, participial tails, hedge
stacks, vague authority), em dashes, and sentence-length spread.

Usage:
    python build/audit_prose.py [path ...]      # defaults to both repositories
"""

from __future__ import annotations

import re
import statistics
import sys
from pathlib import Path

PAPER_ROOT = Path(__file__).resolve().parent.parent

BANNED = [
    "delve", "leverage", "underscore", "harness", "foster", "utilize",
    "facilitate", "streamline", "bolster", "illuminate", "showcase", "embark",
    "elevate", "empower", "unleash", "garner", "resonate", "revolutionize",
    "shed light on", "synthesize", "elucidate", "transcend", "reimagine",
    "intertwine", "grapple with", "exemplify", "underpin", "tapestry",
    "realm", "paradigm", "synergy", "testament", "beacon", "interplay",
    "intricacies", "myriad", "plethora", "advancements", "pivotal", "crucial",
    "seamless", "vibrant", "intricate", "meticulous", "nuanced",
    "cutting-edge", "transformative", "game-changing", "groundbreaking",
    "unparalleled", "invaluable", "multifaceted", "commendable", "poignant",
    "relentless", "tireless", "unwavering", "timeless", "ever-evolving",
    "fast-paced", "it is worth noting", "it's important to note",
    "plays a pivotal role", "stands as a testament", "in conclusion",
    "in summary", "at its core", "a key takeaway", "paving the way",
    "valuable insights", "deeper understanding", "when it comes to",
    "not only", "let's explore", "furthermore", "moreover",
]

SECOND_TIER = [
    "comprehensive", "significant", "essential", "critical", "dynamic",
    "innovative", "powerful", "notable", "vital", "vast", "explore",
    "enhance", "ensure", "highlight", "reveal", "engage", "embrace",
    "insights", "perspective", "framework", "approach", "strategy",
    "challenges", "opportunities", "potential", "impactful", "genuinely",
    "truly", "remarkably", "arguably", "thought-provoking", "robust",
]

CONSTRUCTIONS = {
    "negative parallelism": r"\b(?:it(?:'s| is) not\s+\w+[^.]{0,40}?\bit(?:'s| is)\b|not just\s+\w+[^.]{0,30}?\bbut\b)",
    "rule of three": r"\b\w+,\s+\w+,\s+and\s+\w+\b",
    "rhetorical Q&A": r"\?\s+(?:Because|The answer|Yes|No)\b",
    "copula dodge": r"\b(?:serves as|stands as|functions as|represents a|boasts)\b",
    "participial tail": r",\s+(?:highlighting|underscoring|showcasing|emphasising|emphasizing|demonstrating)\b",
    "hedge stack": r"\b(?:it is important to note|while\s+\w+[^.]{0,30},\s+consider)\b",
    "vague authority": r"\b(?:experts (?:argue|say)|studies show|observers note|research suggests)\b",
    "false suspense": r"\b(?:here(?:'s| is) the (?:kicker|thing)|the best part)\b",
}


def strip_markup(text: str, suffix: str) -> str:
    """Reduce a source file to the prose a reader actually meets."""
    if suffix == ".tex":
        text = re.sub(r"(?m)^%.*$", "", text)
        text = re.sub(r"\\(?:label|ref|eqref|cite[tp]?|input|includegraphics)\{[^}]*\}", " ", text)
        text = re.sub(r"\\begin\{(?:table|figure|tabular|equation)\*?\}.*?\\end\{(?:table|figure|tabular|equation)\*?\}",
                      " ", text, flags=re.S)
        text = re.sub(r"\\[a-zA-Z]+\*?", " ", text)
        text = re.sub(r"[{}$\\]", " ", text)
    elif suffix == ".py":
        # Only the prose: docstrings and comments, not identifiers.
        parts = re.findall(r'"""(.*?)"""', text, flags=re.S) + re.findall(r"(?m)^\s*#\s?(.*)$", text)
        text = "\n".join(parts)
        # A run of dashes ruling off a comment block is a separator, not the
        # mid-sentence em dash the audit is looking for.
        text = re.sub(r"-{3,}", " ", text)
    elif suffix == ".md":
        text = re.sub(r"```.*?```", " ", text, flags=re.S)
        text = re.sub(r"\|[^\n]*\|", " ", text)
        text = re.sub(r"[`*#\[\]()]", " ", text)
    return re.sub(r"\s+", " ", text)


def audit(path: Path) -> dict:
    prose = strip_markup(path.read_text(encoding="utf-8"), path.suffix)
    low = prose.lower()

    banned = [w for w in BANNED if re.search(rf"\b{re.escape(w)}", low)]
    tier2 = [w for w in SECOND_TIER if re.search(rf"\b{re.escape(w)}", low)]
    found = {name: len(re.findall(pat, prose, re.I))
             for name, pat in CONSTRUCTIONS.items()}
    found = {k: v for k, v in found.items() if v}

    sentences = [s for s in re.split(r"(?<=[.!?])\s+", prose) if len(s.split()) > 2]
    lengths = [len(s.split()) for s in sentences]

    return {
        "words": len(prose.split()),
        "banned": banned,
        "tier2": tier2,
        "constructions": found,
        # In LaTeX "---" is the em dash; a longer run is a rule, already
        # stripped above for Python and never used in the .tex sources.
        "em_dashes": len(re.findall(r"---(?!-)", prose)) + prose.count("\u2014"),
        "sentences": len(lengths),
        "mean_len": statistics.mean(lengths) if lengths else 0,
        "stdev_len": statistics.pstdev(lengths) if len(lengths) > 1 else 0,
        "shortest": min(lengths) if lengths else 0,
        "longest": max(lengths) if lengths else 0,
    }


def main(argv: list[str]) -> int:
    targets = [Path(a) for a in argv[1:]] or [
        PAPER_ROOT / "sections", PAPER_ROOT / "build",
        PAPER_ROOT.parent / "src" / "gsvar", PAPER_ROOT.parent / "scripts",
        PAPER_ROOT.parent / "README.md", PAPER_ROOT.parent / "data" / "README.md",
        PAPER_ROOT.parent / "reports" / "report.md",
    ]

    files: list[Path] = []
    for t in targets:
        if t.is_dir():
            files += [p for p in sorted(t.rglob("*")) if p.suffix in {".tex", ".py", ".md"}]
        elif t.exists():
            files.append(t)

    total_banned = total_constructions = 0
    print(f"{'file':<46}{'words':>7}{'banned':>8}{'constr':>8}{'em—':>6}{'len sd':>8}{'range':>10}")
    for f in files:
        r = audit(f)
        if r["words"] < 40:
            continue
        total_banned += len(r["banned"])
        total_constructions += sum(r["constructions"].values())
        name = str(f).replace(str(PAPER_ROOT.parent) + "/", "")
        print(f"{name[-45:]:<46}{r['words']:>7}{len(r['banned']):>8}"
              f"{sum(r['constructions'].values()):>8}{r['em_dashes']:>6}"
              f"{r['stdev_len']:>8.1f}{r['shortest']:>5}-{r['longest']:<4}")
        if r["banned"]:
            print(f"{'':<46}  banned: {', '.join(r['banned'])}")
        if len(r["tier2"]) >= 5:
            print(f"{'':<46}  tier-2 cluster ({len(r['tier2'])}): {', '.join(r['tier2'][:8])}")
        for k, v in r["constructions"].items():
            print(f"{'':<46}  {k}: {v}")

    print(f"\ntotals: {total_banned} banned-lexicon hits, "
          f"{total_constructions} flagged constructions")
    return 1 if total_banned else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
