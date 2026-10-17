from datetime import date

import pytest

from app.sources.expenditure import (
    CAPITAL_EXPENDITURE_INDICATOR_ID,
    TOTAL_EXPENDITURE_INDICATOR_ID,
    ExpenditureSourceError,
    parse_budget_at_a_glance_text,
)


REPORT_TEXT = """
Budget at a Glance 2026-2027
In Revised Estimates (RE) 2025-26, the total expenditure is estimated at ₹49,64,842 crore.
The total capital expenditure is estimated at ₹10,95,755 crore in RE 2025-26.
The total expenditure in Budget Estimates (BE) 2026-27 is estimated at ₹53,47,315 crore
of which total capital expenditure is ₹12,21,821 crore and effective capital expenditure is ₹17,14,523 crore.
"""


def test_parse_budget_at_a_glance_text_reads_total_and_capital_expenditure() -> None:
    points = parse_budget_at_a_glance_text(REPORT_TEXT, date(2026, 2, 1))

    total, capital = points
    assert total.indicator_id == TOTAL_EXPENDITURE_INDICATOR_ID
    assert total.period_label == "BE FY 2026-27"
    assert total.observation_date == date(2026, 2, 1)
    assert total.value_lakh_crore == pytest.approx(53.47315)
    assert total.comparison_value_lakh_crore == pytest.approx(49.64842)
    assert total.comparison_period_label == "RE FY 2025-26"
    assert capital.indicator_id == CAPITAL_EXPENDITURE_INDICATOR_ID
    assert capital.value_lakh_crore == pytest.approx(12.21821)
    assert capital.comparison_value_lakh_crore == pytest.approx(10.95755)


def test_parse_budget_at_a_glance_text_rejects_missing_figures() -> None:
    with pytest.raises(ExpenditureSourceError, match="missing the expected expenditure figures"):
        parse_budget_at_a_glance_text("Budget at a Glance 2026-2027", date(2026, 2, 1))
