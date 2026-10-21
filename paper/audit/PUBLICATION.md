# What ships, and what does not

The repository published alongside this paper carries the research artefact.
It does not carry the workspace that produced it: planning documents, review
records and process notes belong to the making of the work rather than to the
work. This file is the classification, and `build/scan_vocabulary.py` reads it
rather than trusting anyone to remember.

Every file under `audit/` must appear in exactly one list below. A file that
appears in neither fails the publication check, so a new note cannot slip into
the repository unclassified.

## Ships

| File | Why |
|---|---|
| `evidence_freeze.csv` | Reproducibility infrastructure. Records the research commit every reported figure came from and a SHA-256 digest of each analysis output, so a reader can confirm that a number in the paper corresponds to the state of the code that produced it. Without it the manuscript's provenance claims are unverifiable. |
| `PUBLICATION.md` | This file. The exclusions below are visible rather than silent. |

## Does not ship

| File | Why |
|---|---|
| `outline.md` | Planning document: section budgets, float plans and drafting instructions. Superseded by the manuscript itself. |
| `peer_review.md` | Internal review record and its revision log. The revisions are in the paper; the review is process. |
| `prehumanization_audit.md` | Internal consistency audit of the finished draft. |
| `humanization_pass.md` | Internal record of the prose audit. |
| `open_finding_period_end.md` | Working note recording how the period-end comparison was found and what was checked before it was used. The finding itself is in Section 6 and Appendix A. |

## A note on why the distinction is drawn here and not by taste

Two of the excluded files mention the tooling used to produce the work, which
is precisely why the vocabulary check must know they are excluded rather than
simply passing over `audit/` wholesale. Passing over the directory would also
pass over `evidence_freeze.csv`, which does ship. The classification is
per-file for that reason.
