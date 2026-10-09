"""Parsing of the market risk disclosures inside Goldman's 10-K.

Goldman reports firmwide Value-at-Risk at a 95% confidence level over a one-day
horizon, split into four risk categories, with a separate "diversification
effect" line that reconciles the four category figures to the firmwide number.
Four tables and one sentence carry everything this project compares against:

  * average daily VaR over the year, by category
  * period-end VaR, by category
  * the year's high and low VaR, by category and firmwide
  * the frequency distribution of daily net revenues
  * a sentence giving the count of days on which a loss exceeded the prior
    day's 95% VaR

None of it is tagged in XBRL, so the tables have to be recognised by content.
Their HTML changes shape every few years. Three layouts show up across
FY2016-FY2025: dollar signs sometimes share a cell with the figure and
sometimes sit in their own, negatives are sometimes written "(45)" and
sometimes split into "(45" and ")", and the number of year columns moves
between two and three. Rather than special-case each era, every row is
flattened to a single string and the signed numbers are read out of it. That
survives all three layouts and, more to the point, will survive the next one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import lxml.html
import pandas as pd

CATEGORIES = ("Interest rates", "Equity prices", "Currency rates", "Commodity prices")

# Goldman writes exception counts as words, never digits.
_WORD_COUNTS = {
    "no": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}

_NUMBER = re.compile(r"-?\d[\d,]*\.?\d*")
_YEAR = re.compile(r"\b(?:19|20)\d{2}\b")


def _squash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _row_cells(row) -> list[str]:
    return [_squash(" ".join(cell.itertext())) for cell in row.iter("td", "th")]


def _row_values(cells: list[str]) -> list[float]:
    """Signed numbers from one table row, whatever the era's cell layout.

    Accounting parentheses mark negatives and may straddle two cells, so the
    row is joined before the bracket is turned into a minus sign. Without the
    join, "(45" and ")" parse as a positive 45 and the diversification effect
    silently flips sign.
    """
    joined = " ".join(cells)
    joined = re.sub(r"\(\s*([\d,.]+)\s*\)", r"-\1", joined)
    return [float(match.group().replace(",", "")) for match in _NUMBER.finditer(joined)]


def _tables(document: bytes | str):
    tree = lxml.html.fromstring(document if isinstance(document, bytes) else document.encode())
    for table in tree.iter("table"):
        yield table, _squash(" ".join(table.itertext()))


def _years_in(rows: list[list[str]], minimum: int = 1) -> list[int]:
    """Column years, read from the first header row above the data.

    Most tables carry two or three year columns, but the high/low table in the
    FY2017 filing shows a single year, so one year is enough to accept.
    """
    for cells in rows:
        text = " ".join(cells)
        if "Interest rates" in text:
            break
        years = [int(y) for y in _YEAR.findall(text)]
        if len(years) >= minimum:
            return years
    return []


def _parse_var_table(table) -> pd.DataFrame | None:
    """Turn one category VaR table into years x (categories, diversification, total)."""
    rows = [cells for cells in (_row_cells(r) for r in table.iter("tr")) if any(cells)]
    years = _years_in(rows)
    if not years:
        return None

    record: dict[str, list[float]] = {}
    for cells in rows:
        label = cells[0].strip() if cells else ""
        for field in (*CATEGORIES, "Diversification effect", "Total"):
            if label == field or label.rstrip(":") == field:
                values = _row_values(cells[1:])
                if len(values) >= len(years):
                    record[field] = values[: len(years)]

    if not all(field in record for field in CATEGORIES):
        return None

    frame = pd.DataFrame(record, index=pd.Index(years, name="year"))
    frame.columns = [_slug(c) for c in frame.columns]
    return frame.sort_index()


def _slug(label: str) -> str:
    return {
        "Interest rates": "interest_rates",
        "Equity prices": "equity_prices",
        "Currency rates": "currency_rates",
        "Commodity prices": "commodity_prices",
        "Diversification effect": "diversification_effect",
        "Total": "total",
    }[label]


def average_daily_var(document: bytes | str) -> pd.DataFrame:
    """Average daily VaR by category, in $ millions, indexed by calendar year."""
    return _first_var_table(document, requires="Year Ended")


def period_end_var(document: bytes | str) -> pd.DataFrame:
    """VaR as of the last business day of the year, by category, $ millions."""
    return _first_var_table(document, requires="As of December")


def _first_var_table(document: bytes | str, requires: str) -> pd.DataFrame:
    for table, text in _tables(document):
        if "Diversification effect" not in text or "Interest rates" not in text:
            continue
        if requires not in text:
            continue
        parsed = _parse_var_table(table)
        if parsed is not None:
            return parsed
    raise LookupError(f"no VaR table matching {requires!r} in this filing")


def high_low_var(document: bytes | str) -> pd.DataFrame:
    """The year's highest and lowest daily VaR, by category and firmwide.

    Unlike the other tables this one nests two sub-columns under each year, so
    the values arrive interleaved as high, low, high, low across the years.
    """
    for table, text in _tables(document):
        if "High" not in text or "Low" not in text:
            continue
        if "Interest rates" not in text or "Commodity prices" not in text:
            continue
        if "Diversification effect" in text:
            continue

        rows = [cells for cells in (_row_cells(r) for r in table.iter("tr")) if any(cells)]
        years = _years_in(rows)
        if not years:
            continue

        records = []
        for cells in rows:
            label = cells[0].strip()
            field = None
            if label in CATEGORIES:
                field = _slug(label)
            elif label.lower().startswith("firmwide") or label == "VaR":
                # From FY2019 the firmwide row is laid out with "Firmwide" on
                # its own line and "VaR" starting the row that holds the
                # numbers, so a bare "VaR" label is the firmwide row.
                field = "firmwide"
            if field is None:
                continue

            values = _row_values(cells[1:])
            if len(values) < 2 * len(years):
                continue
            for position, year in enumerate(years):
                records.append(
                    {
                        "year": year,
                        "measure": field,
                        "high": values[2 * position],
                        "low": values[2 * position + 1],
                    }
                )

        if records:
            return pd.DataFrame(records).sort_values(["year", "measure"]).reset_index(drop=True)

    raise LookupError("no high/low VaR table in this filing")


def net_revenue_distribution(document: bytes | str) -> pd.DataFrame:
    """Daily net revenue buckets and the day count in each, by year.

    This is the closest public view of the loss distribution the exception
    count is drawn from. It is coarse (ten buckets, $25mm wide in the middle)
    but it pins down how many loss days Goldman had, which the exception count
    alone does not.

    Only available from the FY2019 filing onwards. Earlier reports present the
    same information as a bar chart with no underlying table, so FY2016-FY2018
    raise LookupError rather than returning a partial series.
    """
    for table, text in _tables(document):
        if "Total" not in text or ">$100" not in text.replace(" ", ""):
            continue

        rows = [cells for cells in (_row_cells(r) for r in table.iter("tr")) if any(cells)]
        years = _years_in(rows, minimum=2)
        if not years:
            continue

        records = []
        for cells in rows:
            label = _squash(cells[0])
            if not label or label.lower().startswith(("$ in", "year ended")):
                continue
            # A bucket label always carries a dollar sign or a comparison; the
            # "Total" row is kept too, as a check that the buckets add up.
            is_total = label.lower().startswith("total")
            if not is_total and not re.search(r"[<>$]", label):
                continue

            counts = _dash_as_zero(cells[1:])
            if len(counts) < len(years):
                continue
            for position, year in enumerate(years):
                records.append(
                    {
                        "year": year,
                        "bucket": "Total" if is_total else label,
                        "days": int(counts[position]),
                    }
                )

        if records:
            return pd.DataFrame(records)

    raise LookupError("no daily net revenue distribution table in this filing")


def _dash_as_zero(cells: list[str]) -> list[float]:
    """Row values where an empty bucket is written as a dash rather than a 0.

    A year with no days in the worst bucket shows "-" in the FY2019 filing. Read
    naively that row yields one number instead of two, the row gets dropped, and
    the tail of the loss distribution quietly disappears, which is the part of
    the distribution this project cares about most.
    """
    cleaned = ["0" if _squash(cell) in {"-", "–", "—"} else cell for cell in cells]
    return _row_values(cleaned)


@dataclass(frozen=True)
class ExceptionCount:
    year: int
    exceptions: int
    confidence: str  # "95" for risk-management VaR, "99" for regulatory VaR


def var_exceptions(text: str, confidence: str = "95") -> list[ExceptionCount]:
    """Exception counts for both years discussed in one filing's narrative.

    Goldman states these in prose, and the sentence is rebuilt every year. Three
    shapes appear between FY2016 and FY2025:

        "... exceeded our 95% one-day VaR (i.e., a VaR exception) on two
         occasions during 2022 and on one occasion during 2021."
        "... on two occasions during 2018 and did not exceed our 95% one-day
         VaR during 2017."
        "... did not exceed ... during 2019 and exceeded ... on two occasions
         during 2018."

    Rather than match whole sentences, this walks the paragraph and reads each
    "N occasions during YYYY" or "did not exceed ... during YYYY" fragment in
    the order it appears. A zero is as much a data point as a two: FY2017 and
    FY2019 both had a clean year, and dropping those years would bias the
    comparison against the model.
    """
    window = _exception_paragraph(text, confidence)
    if window is None:
        return []

    found: dict[int, int] = {}
    for match in _EXCEPTION_PATTERN.finditer(window):
        if match.group("occasions_year"):
            found.setdefault(int(match.group("occasions_year")), _count(match.group("occasions")))
        elif match.group("plain_year"):
            found.setdefault(int(match.group("plain_year")), _count(match.group("plain")))
        else:
            # "did not exceed ... during 2016 and 2015" covers two clean years.
            for group in ("clean_year", "clean_year_second"):
                if match.group(group):
                    found.setdefault(int(match.group(group)), 0)

    return [ExceptionCount(y, c, confidence) for y, c in sorted(found.items())]


def _count(word: str) -> int:
    word = word.strip().lower()
    return int(word) if word.isdigit() else _WORD_COUNTS[word]


_COUNT_WORD = "|".join(_WORD_COUNTS) + r"|\d+"

# Three sentence shapes carry the count across FY2016-FY2025, so all three are
# matched in one pass and taken in the order they appear. The "did not exceed"
# branch is last in the alternation: a year with no exceptions is only claimed
# once the two positive forms have had their chance at the same span.
_EXCEPTION_PATTERN = re.compile(
    r"(?:on\s+(?P<occasions>" + _COUNT_WORD + r")\s+occasions?\s+during\s+(?P<occasions_year>\d{4}))"
    r"|(?:there\s+(?:were|was)\s+(?P<plain>" + _COUNT_WORD + r")\s+VaR\s+exceptions?\s+"
    r"during\s+(?P<plain_year>\d{4}))"
    r"|(?:did\s+not\s+exceed.{0,160}?during\s+(?P<clean_year>\d{4})"
    r"(?:\s+and\s+(?P<clean_year_second>\d{4}))?)",
    re.IGNORECASE,
)


def _exception_paragraph(text: str, confidence: str) -> str | None:
    """The stretch of narrative that states the exception count.

    The 95% and 99% figures are discussed in different paragraphs, and the 99%
    one belongs to regulatory VaR, which is a different measure on a different
    scope. Anchoring on the right phrase keeps them apart.
    """
    if confidence == "95":
        anchor = re.search(r"a VaR exception\)", text)
        if anchor is None:
            return None
        # The count can precede or follow the parenthetical, so take both sides.
        return text[max(0, anchor.start() - 400) : anchor.end() + 400]

    anchor = re.search(r"99\s*%\s*one-day regulatory VaR", text)
    if anchor is None:
        return None
    return text[max(0, anchor.start() - 300) : anchor.end() + 400]


def filing_text(document: bytes) -> str:
    """Whole-filing plain text, used for the narrative searches above."""
    return _squash(" ".join(lxml.html.fromstring(document).itertext()))


def market_risk_section(text: str) -> str:
    """The Market Risk Management discussion, verbatim.

    A full 10-K runs to about ten megabytes of inline XBRL, most of it nothing
    to do with this project. The market risk discussion is a few tens of
    kilobytes and contains every figure used here, so that is what gets kept
    alongside the code as the preserved source. The filing it came from is
    identified by accession number in the reference register, which is how a
    reader gets back to the complete document.
    """
    start = None
    for match in re.finditer(r"Market Risk Management", text):
        # The phrase appears in the table of contents and in cross-references
        # long before the section itself. The real one is followed closely by
        # the VaR definition.
        if "Value-at-Risk" in text[match.start() : match.start() + 4000]:
            start = match.start()
            break
    if start is None:
        raise LookupError("could not locate the Market Risk Management section")

    end = text.find("Credit Risk Management", start + 1000)
    if end == -1:
        end = min(len(text), start + 60_000)
    return text[start:end].strip()
