"""Checks on the EDGAR client that do not need the network.

The contact header is the one thing here worth testing. SEC rejects requests
without it, and a committed default would mean every fork of this repository
fetching filings under the original author's name.
"""

import pytest

from gsvar import edgar


def test_a_missing_contact_is_refused_with_instructions(monkeypatch):
    monkeypatch.delenv(edgar.CONTACT_VARIABLE, raising=False)
    with pytest.raises(RuntimeError, match=edgar.CONTACT_VARIABLE):
        edgar._contact()


def test_a_blank_contact_counts_as_missing(monkeypatch):
    monkeypatch.setenv(edgar.CONTACT_VARIABLE, "   ")
    with pytest.raises(RuntimeError):
        edgar._contact()


def test_a_contact_without_an_email_is_refused(monkeypatch):
    monkeypatch.setenv(edgar.CONTACT_VARIABLE, "Jane Smith")
    with pytest.raises(RuntimeError, match="email"):
        edgar._contact()


def test_a_usable_contact_is_passed_through(monkeypatch):
    monkeypatch.setenv(edgar.CONTACT_VARIABLE, "Jane Smith jane@example.com")
    assert edgar._contact() == "Jane Smith jane@example.com"


def test_the_archive_url_is_built_without_dashes_in_the_accession():
    """EDGAR's directory names strip the dashes; its filenames do not."""
    filing = edgar.Filing(
        form="10-K",
        filed="2023-02-24",
        period_end="2022-12-31",
        accession="0000886982-23-000003",
        document="gs-20221231.htm",
    )
    assert filing.fiscal_year == 2022
    assert filing.url == (
        "https://www.sec.gov/Archives/edgar/data/886982/"
        "000088698223000003/gs-20221231.htm"
    )
