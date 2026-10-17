from datetime import date

import pytest

from app.sources.gst import (
    GstSourceError,
    parse_gst_news_payload,
    parse_gst_news_releases,
    parse_gst_report_text,
)


def gst_news_payload() -> dict[str, object]:
    return {
        "data": [
            {
                "title": "Gross and Net GST revenue collections for the month of August, 2026",
                "content": '<a href="https://tutorial.gst.gov.in/august.pdf">report</a>',
                "date": "01/09/2026",
            },
            {
                "title": "Gross and Net GST revenue collections for the month of September, 2026",
                "content": '<a href="https://tutorial.gst.gov.in/september.pdf">report</a>',
                "date": "01/10/2026",
            },
        ]
    }


def test_parse_gst_news_payload_selects_latest_monthly_release() -> None:
    release = parse_gst_news_payload(gst_news_payload(), "https://www.gst.gov.in")

    assert release.period_month == 9
    assert release.period_year == 2026
    assert release.published_date == date(2026, 10, 1)
    assert release.pdf_url == "https://tutorial.gst.gov.in/september.pdf"


def test_parse_gst_news_releases_returns_newest_first_for_history_hydration() -> None:
    releases = parse_gst_news_releases(gst_news_payload(), "https://www.gst.gov.in")

    assert [release.period_month for release in releases] == [9, 8]


def test_parse_gst_report_text_converts_crore_to_lakh_crore() -> None:
    release = parse_gst_news_payload(gst_news_payload(), "https://www.gst.gov.in")
    point = parse_gst_report_text(
        "Total Gross GST Revenue 1,77,365 2,03,521 14.7% 11,17,088 12,46,278 11.6%",
        release,
    )

    assert point.period_label == "Sep 2026"
    assert point.observation_date == date(2026, 9, 30)
    assert point.gross_collection_lakh_crore == pytest.approx(2.03521)
    assert point.previous_year_collection_lakh_crore == pytest.approx(1.77365)
    assert point.comparison_period_label == "Sep 2025"


def test_parse_gst_report_text_rejects_missing_total() -> None:
    release = parse_gst_news_payload(gst_news_payload(), "https://www.gst.gov.in")

    with pytest.raises(GstSourceError, match="missing Total Gross"):
        parse_gst_report_text("Gross Domestic Revenue 1,25,334 1,37,996", release)
