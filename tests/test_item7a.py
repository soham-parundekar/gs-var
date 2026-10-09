"""Disclosure parsing, against the table and sentence shapes Goldman has used.

The fixtures below are cut down from real filings and keep the three cell
layouts that appear between FY2016 and FY2025: the dollar sign sharing a cell
with the figure or sitting in its own, and a negative written either as one
token or split across two. A parser that only handles the layout in front of
it works until the next annual report.
"""

import pytest

from gsvar import item7a

# FY2016 style: three year columns, "$ 45" in one cell, "(45" and ")" split.
OLD_LAYOUT = """
<table>
 <tr><td>$ in millions</td><td>Year Ended December</td></tr>
 <tr><td>2016</td><td>2015</td><td>2014</td></tr>
 <tr><td>Risk Categories</td></tr>
 <tr><td>Interest rates</td><td>$ 45</td><td>$ 47</td><td>$ 51</td></tr>
 <tr><td>Equity prices</td><td>25</td><td>26</td><td>26</td></tr>
 <tr><td>Currency rates</td><td>21</td><td>30</td><td>19</td></tr>
 <tr><td>Commodity prices</td><td>17</td><td>20</td><td>21</td></tr>
 <tr><td>Diversification effect</td><td>(45</td><td>)</td><td>(47</td><td>)</td><td>(45</td><td>)</td></tr>
 <tr><td>Total</td><td>$ 63</td><td>$ 76</td><td>$ 72</td></tr>
</table>
"""

# FY2025 style: dollar signs in their own cells, negatives in one token.
NEW_LAYOUT = """
<table>
 <tr><td>Year Ended December</td></tr>
 <tr><td>$ in millions</td><td>2025</td><td>2024</td></tr>
 <tr><td>Categories</td></tr>
 <tr><td>Interest rates</td><td>$</td><td>70</td><td>$</td><td>81</td></tr>
 <tr><td>Equity prices</td><td>47</td><td>37</td></tr>
 <tr><td>Currency rates</td><td>24</td><td>26</td></tr>
 <tr><td>Commodity prices</td><td>17</td><td>19</td></tr>
 <tr><td>Diversification effect</td><td>(68)</td><td>(71)</td></tr>
 <tr><td>Total</td><td>$</td><td>90</td><td>$</td><td>92</td></tr>
</table>
"""

PERIOD_END = NEW_LAYOUT.replace("Year Ended December", "As of December")

HIGH_LOW = """
<table>
 <tr><td>Year Ended December</td></tr>
 <tr><td>2022</td><td>2021</td></tr>
 <tr><td>$ in millions</td><td>High</td><td>Low</td><td>High</td><td>Low</td></tr>
 <tr><td>Categories</td></tr>
 <tr><td>Interest rates</td><td>$</td><td>139</td><td>$</td><td>57</td><td>$</td><td>74</td><td>$</td><td>49</td></tr>
 <tr><td>Equity prices</td><td>48</td><td>25</td><td>71</td><td>30</td></tr>
 <tr><td>Currency rates</td><td>55</td><td>16</td><td>20</td><td>8</td></tr>
 <tr><td>Commodity prices</td><td>82</td><td>18</td><td>45</td><td>14</td></tr>
 <tr><td>Firmwide</td></tr>
 <tr><td>VaR</td><td>$</td><td>158</td><td>$</td><td>76</td><td>$</td><td>105</td><td>$</td><td>69</td></tr>
</table>
"""

# A dash is how an empty bucket is written, and it means zero days.
DISTRIBUTION = """
<table>
 <tr><td>Year Ended December</td></tr>
 <tr><td>$ in millions</td><td>2019</td><td>2018</td></tr>
 <tr><td>&gt;$100</td><td>16</td><td>12</td></tr>
 <tr><td>$75 - $100</td><td>17</td><td>22</td></tr>
 <tr><td>$(75) - $(50)</td><td>&#8211;</td><td>1</td></tr>
 <tr><td>Total</td><td>252</td><td>251</td></tr>
</table>
"""


def test_old_layout_parses_three_years_with_split_negatives():
    frame = item7a.average_daily_var(OLD_LAYOUT)
    assert list(frame.index) == [2014, 2015, 2016]
    assert frame.loc[2016, "interest_rates"] == 45
    assert frame.loc[2016, "diversification_effect"] == -45
    assert frame.loc[2014, "total"] == 72


def test_new_layout_parses_separated_dollar_signs():
    frame = item7a.average_daily_var(NEW_LAYOUT)
    assert frame.loc[2025, "interest_rates"] == 70
    assert frame.loc[2024, "interest_rates"] == 81
    assert frame.loc[2025, "diversification_effect"] == -68


@pytest.mark.parametrize("document", [OLD_LAYOUT, NEW_LAYOUT])
def test_the_disclosed_figures_reconcile(document):
    """Categories plus the diversification effect must equal the total.

    Goldman defines the effect as exactly that difference, so this is an
    identity in the filing. If parsing breaks, it breaks here first.
    """
    frame = item7a.average_daily_var(document)
    categories = ["interest_rates", "equity_prices", "currency_rates", "commodity_prices"]
    reconciled = frame[categories].sum(axis=1) + frame["diversification_effect"]
    assert reconciled.equals(frame["total"])


def test_period_end_and_average_tables_are_told_apart():
    assert item7a.average_daily_var(NEW_LAYOUT).loc[2025, "total"] == 90
    assert item7a.period_end_var(PERIOD_END).loc[2025, "total"] == 90
    with pytest.raises(LookupError):
        item7a.period_end_var(NEW_LAYOUT)


def test_high_low_reads_the_firmwide_row_split_across_two_lines():
    frame = item7a.high_low_var(HIGH_LOW)
    firmwide = frame[(frame.measure == "firmwide") & (frame.year == 2022)].iloc[0]
    assert firmwide.high == 158 and firmwide.low == 76
    rates = frame[(frame.measure == "interest_rates") & (frame.year == 2021)].iloc[0]
    assert rates.high == 74 and rates.low == 49
    assert (frame.low <= frame.high).all()


def test_a_dash_in_the_distribution_is_zero_days_not_a_missing_row():
    frame = item7a.net_revenue_distribution(DISTRIBUTION)
    empty = frame[(frame.bucket == "$(75) - $(50)") & (frame.year == 2019)]
    assert len(empty) == 1
    assert empty.iloc[0].days == 0


@pytest.mark.parametrize(
    "sentence,expected",
    [
        (
            "Net losses incurred on a single day for such positions exceeded our 95% one-day "
            "VaR (i.e., a VaR exception) on two occasions during 2022 and on one occasion "
            "during 2021.",
            {2022: 2, 2021: 1},
        ),
        (
            "... exceeded our 95% one-day VaR (i.e., a VaR exception) on two occasions during "
            "2018 and did not exceed our 95% one-day VaR during 2017.",
            {2018: 2, 2017: 0},
        ),
        (
            "Net losses incurred on a single day for such positions did not exceed our 95% "
            "one-day VaR (i.e., a VaR exception) during 2025. There were two VaR exceptions "
            "during 2024.",
            {2025: 0, 2024: 2},
        ),
        (
            "Trading losses incurred on a single day did not exceed our 95% one-day VaR during "
            "2016 and 2015 (i.e., a VaR exception) and exceeded our 95% one-day VaR on one "
            "occasion during 2014.",
            {2016: 0, 2015: 0, 2014: 1},
        ),
    ],
)
def test_every_exception_sentence_shape_goldman_has_used(sentence, expected):
    parsed = {record.year: record.exceptions for record in item7a.var_exceptions(sentence, "95")}
    assert parsed == expected


def test_regulatory_and_risk_management_counts_are_not_confused():
    text = (
        "... exceeded our 95% one-day VaR (i.e., a VaR exception) on two occasions during 2018 "
        "and did not exceed our 95% one-day VaR during 2017. The firm's positional losses "
        "observed on a single day exceeded its 99% one-day regulatory VaR on two occasions "
        "during 2018 and did not exceed its 99% one-day regulatory VaR during 2017."
    )
    risk = {r.year: r.exceptions for r in item7a.var_exceptions(text, "95")}
    regulatory = {r.year: r.exceptions for r in item7a.var_exceptions(text, "99")}
    assert risk == {2018: 2, 2017: 0}
    assert regulatory == {2018: 2, 2017: 0}


def test_a_filing_with_no_var_table_raises_rather_than_returning_nothing():
    with pytest.raises(LookupError):
        item7a.average_daily_var("<table><tr><td>nothing here</td></tr></table>")
