from datetime import date

import pytest

from app.sources.inflation import (
    InflationSourceError,
    parse_cpi_report_text,
    parse_mospi_cpi_release_history,
    parse_mospi_cpi_releases,
)


def release_payload() -> dict[str, object]:
    return {
        "data": [
            {
                "title": "Press release of CPI for the month of August 2026",
                "published_year": "2026-09-14",
                "file_one": {"path": "uploads/latestReleases/august-cpi.pdf"},
            },
            {
                "title": "Press release of CPI for the month of September 2026",
                "published_year": "2026-10-12",
                "file_one": {"path": "uploads/latestReleases/september-cpi.pdf"},
            },
        ]
    }


def test_parse_mospi_cpi_releases_selects_latest_publication() -> None:
    release = parse_mospi_cpi_releases(release_payload(), "https://www.mospi.gov.in")

    assert release.reference_period == date(2026, 9, 1)
    assert release.release_date == date(2026, 10, 12)
    assert release.pdf_url == "https://www.mospi.gov.in/uploads/latestReleases/september-cpi.pdf"


def test_parse_mospi_cpi_release_history_returns_newest_first() -> None:
    releases = parse_mospi_cpi_release_history(release_payload(), "https://www.mospi.gov.in")

    assert [release.reference_period.month for release in releases] == [9, 8]


def test_parse_cpi_report_text_reads_all_india_combined_rate() -> None:
    release = parse_mospi_cpi_releases(release_payload(), "https://www.mospi.gov.in")
    point = parse_cpi_report_text(
        """
        Year-on-year inflation rate based on All India Consumer Price Index (CPI) with base year 2024
        for the month of September, 2026 over September, 2025 is 5.54%(Provisional).
        """,
        release,
    )

    assert point.period_label == "Sep 2026"
    assert point.observation_date == date(2026, 9, 30)
    assert point.source_as_of_date == date(2026, 10, 12)
    assert point.inflation_percent == pytest.approx(5.54)
    assert point.raw_payload["rbi_target_percent"] == 4.0


def test_parse_cpi_report_text_rejects_missing_headline_rate() -> None:
    release = parse_mospi_cpi_releases(release_payload(), "https://www.mospi.gov.in")

    with pytest.raises(InflationSourceError, match="missing the all-India"):
        parse_cpi_report_text("Consumer Food Price Index was published.", release)
