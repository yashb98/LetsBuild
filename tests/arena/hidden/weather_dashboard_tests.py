"""Hidden test suite for Weather Dashboard challenge — runs inside team sandbox."""

from __future__ import annotations


class TestWeatherDashboard:
    """Core functionality tests for Weather Dashboard."""

    def test_current_conditions(self) -> None:
        """Returns current temperature, humidity, wind for a location."""

    def test_hourly_forecast(self) -> None:
        """Returns hourly forecast for next 24 hours."""

    def test_daily_forecast(self) -> None:
        """Returns daily forecast for next 7 days."""

    def test_location_search(self) -> None:
        """Search by city name returns matching locations."""

    def test_coordinates_search(self) -> None:
        """Search by lat/lon returns weather data."""

    def test_multi_source_aggregation(self) -> None:
        """Data from at least 2 sources is aggregated."""

    def test_source_failure_graceful(self) -> None:
        """Dashboard works when one API source is down."""

    def test_caching(self) -> None:
        """Repeated requests hit cache, not APIs."""

    def test_invalid_location(self) -> None:
        """Invalid location returns appropriate error."""

    def test_historical_comparison(self) -> None:
        """Today vs same day last year data available."""
