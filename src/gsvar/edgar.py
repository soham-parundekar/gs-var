"""Retrieval of Goldman Sachs annual reports from EDGAR.

The firm files under CIK 0000886982. Everything this project needs sits in the
main 10-K document itself (the market risk tables live inside Management's
Discussion and Analysis, not in a separate exhibit), so there is no need to walk
the filing index beyond finding the primary document name.

SEC asks automated clients to identify themselves and to stay under ten requests
per second. Both are handled here rather than left to the caller.
"""

from __future__ import annotations

import gzip
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

GS_CIK = "0000886982"

# SEC rejects requests that do not carry a contact address in the User-Agent,
# and asks that it be the address of whoever is actually making the request.
# There is deliberately no default: a committed one would mean every fork
# fetching EDGAR under someone else's name.
CONTACT_VARIABLE = "SEC_CONTACT"

_SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik}.json"
_ARCHIVE = "https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession}/{document}"

# SEC's published ceiling is 10 requests/second. A tenth of a second between
# calls keeps us under it without needing a token bucket.
_MIN_INTERVAL_SECONDS = 0.15
_last_request_at = 0.0


@dataclass(frozen=True)
class Filing:
    """One annual report, identified well enough to fetch and to cite."""

    form: str
    filed: str
    period_end: str
    accession: str
    document: str

    @property
    def fiscal_year(self) -> int:
        return int(self.period_end[:4])

    @property
    def url(self) -> str:
        return _ARCHIVE.format(
            cik_int=int(GS_CIK),
            accession=self.accession.replace("-", ""),
            document=self.document,
        )


def _contact() -> str:
    contact = os.environ.get(CONTACT_VARIABLE, "").strip()
    if not contact:
        raise RuntimeError(
            f"set {CONTACT_VARIABLE} to your name and email before fetching from EDGAR, "
            f'for example: export {CONTACT_VARIABLE}="Jane Smith jane@example.com". '
            "SEC requires automated clients to identify themselves."
        )
    if "@" not in contact:
        raise RuntimeError(f"{CONTACT_VARIABLE} must include an email address; got {contact!r}")
    return contact


def _fetch(url: str, timeout: int = 120) -> bytes:
    """GET with SEC's required identification and a courtesy delay."""
    global _last_request_at

    wait = _MIN_INTERVAL_SECONDS - (time.monotonic() - _last_request_at)
    if wait > 0:
        time.sleep(wait)

    request = urllib.request.Request(
        url,
        headers={"User-Agent": _contact(), "Accept-Encoding": "gzip, deflate"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read()
            if response.headers.get("Content-Encoding") == "gzip":
                payload = gzip.decompress(payload)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"EDGAR returned {exc.code} for {url}") from exc
    finally:
        _last_request_at = time.monotonic()

    return payload


def list_annual_reports(min_fiscal_year: int = 2016) -> list[Filing]:
    """Every 10-K with a period ending in or after `min_fiscal_year`.

    EDGAR splits a long filing history across several JSON files: the newest
    filings sit in the main submissions document and the rest in numbered
    chunks. Goldman has filed since the 1999 IPO, so the chunks have to be read
    as well or the search stops at the most recent report.
    """
    index = json.loads(_fetch(_SUBMISSIONS.format(cik=GS_CIK)))
    blocks = [index["filings"]["recent"]]

    for extra in index["filings"].get("files", []):
        blocks.append(json.loads(_fetch(f"https://data.sec.gov/submissions/{extra['name']}")))

    filings: dict[str, Filing] = {}
    for block in blocks:
        rows = zip(
            block["form"],
            block["filingDate"],
            block["reportDate"],
            block["accessionNumber"],
            block["primaryDocument"],
        )
        for form, filed, period_end, accession, document in rows:
            if form != "10-K" or not period_end:
                continue
            if int(period_end[:4]) < min_fiscal_year:
                continue
            filings[accession] = Filing(form, filed, period_end, accession, document)

    return sorted(filings.values(), key=lambda f: f.period_end)


def download(filing: Filing, directory: Path) -> Path:
    """Save a filing under a name that says which year it reports on.

    EDGAR's own document names are opaque (`d192225d10k.htm`), and the reference
    register has to point at something a reader can identify.
    """
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / f"GS_10K_FY{filing.fiscal_year}.htm"

    # Filings are immutable once accepted, so a non-trivial local copy is final.
    if destination.exists() and destination.stat().st_size > 100_000:
        return destination

    destination.write_bytes(_fetch(filing.url))
    return destination
