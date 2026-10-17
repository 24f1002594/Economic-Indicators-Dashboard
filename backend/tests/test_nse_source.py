from datetime import date

import pytest

from app.sources.nse import NseSourceError, parse_all_indices_payload


def nse_payload() -> dict[str, object]:
    return {
        "timestamp": "16-Oct-2026 15:30:00",
        "data": [
            {
                "index": "NIFTY 50",
                "last": "25,000.50",
                "variation": "125.25",
                "percentChange": "0.50",
                "timeVal": "16-Oct-2026 15:30:00",
            },
            {
                "index": "NIFTY BANK",
                "last": "55,000.00",
                "variation": "-100.00",
                "percentChange": "-0.18",
                "timeVal": "16-Oct-2026 15:30:00",
            },
            {
                "index": "NIFTY IT",
                "last": "37,842.15",
                "variation": "412.30",
                "percentChange": "1.10",
                "timeVal": "16-Oct-2026 15:30:00",
            },
        ]
    }


def test_parse_all_indices_payload_returns_tracked_quotes() -> None:
    quotes = parse_all_indices_payload(nse_payload())

    assert len(quotes) == 3
    assert quotes[0].indicator_id == "nifty_50"
    assert quotes[0].last_price == 25000.5
    assert quotes[1].change == -100
    assert quotes[1].as_of_date == date(2026, 10, 16)
    assert quotes[2].indicator_id == "nifty_it"
    assert quotes[2].last_price == 37842.15


def test_parse_all_indices_payload_rejects_missing_tracked_index() -> None:
    payload = nse_payload()
    payload["data"] = payload["data"][:1]

    with pytest.raises(NseSourceError, match="NIFTY BANK"):
        parse_all_indices_payload(payload)


def test_parse_all_indices_payload_rejects_invalid_timestamp() -> None:
    payload = nse_payload()
    payload["timestamp"] = "not a timestamp"
    payload["data"][0]["timeVal"] = "not a timestamp"
    payload["data"][1]["timeVal"] = "not a timestamp"
    payload["data"][2]["timeVal"] = "not a timestamp"

    with pytest.raises(NseSourceError, match="source timestamp"):
        parse_all_indices_payload(payload)
