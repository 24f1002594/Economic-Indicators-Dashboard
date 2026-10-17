from datetime import date

import pytest

from app.sources.trade import (
    TradeSourceError,
    parse_monthly_trade_html,
    parse_trade_page_bootstrap,
)


def test_parse_trade_page_bootstrap_reads_livewire_values() -> None:
    bootstrap = parse_trade_page_bootstrap(
        '<script data-csrf="token-123" '
        'data-update-uri="/livewire-da76d7be/update"></script>'
        '<div wire:snapshot="{&quot;data&quot;:{&quot;MonthUs&quot;:null}}"></div>'
    )

    assert bootstrap.csrf_token == "token-123"
    assert bootstrap.update_path == "/livewire-da76d7be/update"
    assert bootstrap.snapshot == '{"data":{"MonthUs":null}}'


def test_parse_monthly_trade_html_uses_latest_fiscal_year_row() -> None:
    point = parse_monthly_trade_html(
        """
        <table>
          <tr><th>Report Dated: Thu, Oct 16, 2025</th></tr>
          <tr><td>1</td><td>2024-2025</td><td>30,000.00</td><td>180,000</td>
              <td>40,000.50</td><td>240,000</td><td>-10,000.50</td><td>-60,000</td></tr>
          <tr><td>2</td><td>2025-2026</td><td>42,000.25</td><td>210,000</td>
              <td>53,500.75</td><td>265,000</td><td>-11,500.50</td><td>-55,000</td></tr>
        </table>
        """,
        requested_month=9,
    )

    assert point.period_label == "Sep 2025"
    assert point.observation_date == date(2025, 9, 30)
    assert point.source_as_of_date == date(2025, 10, 16)
    assert point.exports_usd_millions == 42_000.25
    assert point.imports_usd_millions == 53_500.75
    assert point.reported_trade_balance_usd_millions == -11_500.5


def test_parse_monthly_trade_html_rejects_inconsistent_balance() -> None:
    with pytest.raises(TradeSourceError, match="does not match"):
        parse_monthly_trade_html(
            """
            <table><tr><th>Report Dated: Thu, Oct 16, 2025</th></tr>
            <tr><td>1</td><td>2025-2026</td><td>42,000</td><td>210,000</td>
            <td>53,500</td><td>265,000</td><td>-10,000</td><td>-55,000</td></tr></table>
            """,
            requested_month=9,
        )
