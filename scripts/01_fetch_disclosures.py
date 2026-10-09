#!/usr/bin/env python3
"""Pull Goldman's 10-K market risk disclosures into structured CSVs.

Run this first. Everything downstream compares against what it writes.

Full filings land in data/raw/filings/ and are not committed: ten years of
inline XBRL is about 95 MB and reproducing it is one command. What does get
committed is the Market Risk Management section of each filing, verbatim, under
references/sec_filings/, so the numbers in data/processed/ can be checked
against the source text without a network round trip.

Four years of the sample need a word of warning, and the script prints it:
the daily net revenue distribution only appears as a table from the FY2019
filing onwards. Before that Goldman published the same information as a bar
chart, and there is no table to read.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gsvar import config, edgar, item7a  # noqa: E402

CONFIG = config.load()
ROOT = CONFIG.paths.root
RAW = CONFIG.paths.raw / "filings"
PROCESSED = CONFIG.paths.processed
SECTIONS = CONFIG.paths.references / "sec_filings"

FIRST_FISCAL_YEAR = CONFIG["sample"]["first_year"]


def main() -> int:
    for directory in (RAW, PROCESSED, SECTIONS):
        directory.mkdir(parents=True, exist_ok=True)

    filings = edgar.list_annual_reports(min_fiscal_year=FIRST_FISCAL_YEAR)
    print(f"{len(filings)} annual reports from FY{FIRST_FISCAL_YEAR} onwards")

    average, period_end, high_low, distribution, exceptions, manifest = [], [], [], [], [], []

    for filing in filings:
        path = edgar.download(filing, RAW)
        document = path.read_bytes()
        text = item7a.filing_text(document)
        year = filing.fiscal_year

        section = item7a.market_risk_section(text)
        (SECTIONS / f"GS_10K_FY{year}_market_risk.txt").write_text(section, encoding="utf-8")

        frame = item7a.average_daily_var(document).reset_index()
        frame["source_fiscal_year"] = year
        average.append(frame)

        frame = item7a.period_end_var(document).reset_index()
        frame["source_fiscal_year"] = year
        period_end.append(frame)

        frame = item7a.high_low_var(document)
        frame["source_fiscal_year"] = year
        high_low.append(frame)

        try:
            frame = item7a.net_revenue_distribution(document)
            frame["source_fiscal_year"] = year
            distribution.append(frame)
        except LookupError:
            print(f"  FY{year}: net revenue distribution published as a chart, not a table")

        for confidence in ("95", "99"):
            for record in item7a.var_exceptions(text, confidence):
                exceptions.append(
                    {
                        "year": record.year,
                        "exceptions": record.exceptions,
                        "confidence_pct": int(record.confidence),
                        "source_fiscal_year": year,
                    }
                )

        manifest.append(
            {
                "fiscal_year": year,
                "accession": filing.accession,
                "filed": filing.filed,
                "period_end": filing.period_end,
                "primary_document": filing.document,
                "url": filing.url,
                "bytes": path.stat().st_size,
            }
        )
        print(f"  FY{year}: parsed ({path.stat().st_size / 1e6:.1f} MB)")

    write(PROCESSED / "gs_var_average_daily.csv", pd.concat(average))
    write(PROCESSED / "gs_var_period_end.csv", pd.concat(period_end))
    write(PROCESSED / "gs_var_high_low.csv", pd.concat(high_low))
    write(PROCESSED / "gs_net_revenue_distribution.csv", pd.concat(distribution))
    write(PROCESSED / "gs_var_exceptions.csv", pd.DataFrame(exceptions))
    write(PROCESSED / "gs_filing_manifest.csv", pd.DataFrame(manifest))

    report_restatements(pd.concat(average))
    return 0


def write(path: Path, frame: pd.DataFrame) -> None:
    frame.to_csv(path, index=False)
    print(f"wrote {path.relative_to(ROOT)}  ({len(frame)} rows)")


def report_restatements(average: pd.DataFrame) -> None:
    """Flag years whose figures differ between the filings that report them.

    Each 10-K restates the prior year, so most years appear twice and should
    agree. Where they do not, Goldman has changed what sits inside VaR and
    conformed the comparative. That happened once in this sample, in the first
    quarter of 2023, and the difference is small but real.
    """
    measures = [
        "interest_rates",
        "equity_prices",
        "currency_rates",
        "commodity_prices",
        "diversification_effect",
        "total",
    ]
    disagreements = average.groupby("year")[measures].nunique().max(axis=1)
    restated = disagreements[disagreements > 1].index.tolist()
    if restated:
        print(f"\nrestated between filings: {restated}")
        print("  first-reported figures are used downstream; both are kept in the CSV")


if __name__ == "__main__":
    raise SystemExit(main())
