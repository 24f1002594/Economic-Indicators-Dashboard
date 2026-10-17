from datetime import date

import pytest

from app.sources.trade import (
    MonthlyTradePoint,
    TradeSourceError,
    _build_point,
    _drop_anomalous_points,
    _extract_csrf_token,
    _form_field_names,
    _recent_fiscal_years,
    _sum_selected_year_column,
)


def test_extract_csrf_token_reads_name_then_value_order() -> None:
    assert _extract_csrf_token('<input name="_token" value="abc123">') == "abc123"


def test_extract_csrf_token_reads_value_then_name_order() -> None:
    assert _extract_csrf_token('<input value="xyz789" name="_token">') == "xyz789"


def test_extract_csrf_token_missing_raises() -> None:
    with pytest.raises(TradeSourceError, match="CSRF token"):
        _extract_csrf_token("<html></html>")


def test_form_field_names_matches_by_keyword() -> None:
    page = (
        '<select name="eidbYearChwe"></select>'
        '<select name="eidbReportChwe"></select>'
        '<select name="eidbChapterEx"></select>'
    )
    assert _form_field_names(page) == ("eidbYearChwe", "eidbReportChwe", "eidbChapterEx")


def test_form_field_names_missing_raises() -> None:
    with pytest.raises(TradeSourceError, match="form fields"):
        _form_field_names("<select name=\"somethingElse\"></select>")


def _chapter_row(hs: str, year1: str, year2: str) -> str:
    return (
        f"<tr><td>{hs}</td><td>{hs}</td><td>Commodity {hs}</td>"
        f"<td>{year1}</td><td>0.01</td><td>{year2}</td><td>0.01</td><td>1.0</td></tr>"
    )


def test_sum_selected_year_column_sums_the_second_value_column() -> None:
    rows = "".join(_chapter_row(f"{i:02d}", "100.00", "200.00") for i in range(1, 51))
    report_html = f"<table><thead><tr><th>...</th></tr></thead><tbody>{rows}</tbody></table>"

    assert _sum_selected_year_column(report_html) == pytest.approx(50 * 200.00)


def test_sum_selected_year_column_rejects_too_few_rows() -> None:
    rows = "".join(_chapter_row(f"{i:02d}", "100.00", "200.00") for i in range(1, 5))
    report_html = f"<table><tbody>{rows}</tbody></table>"

    with pytest.raises(TradeSourceError, match="too few"):
        _sum_selected_year_column(report_html)


def test_sum_selected_year_column_rejects_empty_report() -> None:
    with pytest.raises(TradeSourceError, match="no HS-chapter rows"):
        _sum_selected_year_column("<table><tbody></tbody></table>")


def test_build_point_computes_fiscal_year_label_and_balance() -> None:
    point = _build_point(2024, exports=437_704.55, imports=721_200.25)

    assert point.period_label == "FY2024-25"
    assert point.observation_date == date(2025, 3, 31)
    assert point.source_as_of_date == date(2025, 3, 31)
    assert point.exports_usd_millions == 437_704.55
    assert point.imports_usd_millions == 721_200.25
    assert point.reported_trade_balance_usd_millions == pytest.approx(437_704.55 - 721_200.25)


def _point(fiscal_year: int, exports: float, imports: float) -> MonthlyTradePoint:
    return _build_point(fiscal_year, exports, imports)


def test_drop_anomalous_points_removes_a_spike_versus_both_neighbours() -> None:
    points = [
        _point(2022, 451_069.97, 700_000.0),
        _point(2023, 874_144.08, 700_000.0),  # live, confirmed anomalous figure
        _point(2024, 437_704.55, 700_000.0),
    ]

    kept = _drop_anomalous_points(points)

    assert [point.period_label for point in kept] == ["FY2022-23", "FY2024-25"]


def test_drop_anomalous_points_keeps_a_genuine_gradual_trend() -> None:
    points = [
        _point(2020, 291_808.52, 400_000.0),
        _point(2021, 422_004.40, 450_000.0),
        _point(2022, 451_069.97, 480_000.0),
    ]

    kept = _drop_anomalous_points(points)

    assert len(kept) == 3


def test_drop_anomalous_points_keeps_an_edge_point_with_only_one_neighbour() -> None:
    points = [
        _point(2024, 437_704.55, 700_000.0),
        _point(2025, 441_452.19, 775_713.16),
    ]

    kept = _drop_anomalous_points(points)

    assert len(kept) == 2


def test_recent_fiscal_years_uses_april_boundary() -> None:
    today = date.today()
    current_fiscal_year = today.year if today.month >= 4 else today.year - 1

    assert _recent_fiscal_years(3) == [
        current_fiscal_year,
        current_fiscal_year - 1,
        current_fiscal_year - 2,
    ]
