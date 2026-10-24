import asyncio
import csv
import io
from datetime import date

from app.api import routes


def test_overview_uses_latest_forecast_at_cutoff_and_matches_delivery_timestamp(monkeypatch):
    start_time = "2026-01-15T00:00:00Z"
    monkeypatch.setattr(
        routes.client,
        "fetch_windfor",
        lambda _delivery_date, _cutoff: [
            {
                "dataset": "WINDFOR",
                "startTime": start_time,
                "publishTime": "2026-01-14T10:30:00Z",
                "generation": 100,
            },
            {
                "dataset": "WINDFOR",
                "startTime": start_time,
                "publishTime": "2026-01-14T11:30:00Z",
                "generation": 200,
            },
        ],
    )
    monkeypatch.setattr(
        routes.client,
        "fetch_fuelhh",
        lambda _delivery_date: [
            {
                "dataset": "FUELHH",
                "fuelType": "WIND",
                "startTime": start_time,
                "generation": 90,
            }
        ],
    )

    result = routes.build_modeled_periods(date(2026, 1, 15), "11:00")
    first_period = result["periods"][0]

    assert result["cutoff_utc"] == "2026-01-14T11:00:00+00:00"
    assert result["matched_periods"] == 1
    assert first_period["selected_forecast_mw"] == 100
    assert first_period["forecast_publication_time"] == "2026-01-14T10:30:00Z"
    assert first_period["actual_mw"] == 90
    assert first_period["signed_error_mw"] == 10
    assert result["mae_mw"] == 10


def test_overview_reports_missing_data_when_upstream_fails(monkeypatch):
    def fail(*_args, **_kwargs):
        raise routes.ElexonAPIError("upstream unavailable")

    monkeypatch.setattr(routes.client, "fetch_windfor", fail)
    monkeypatch.setattr(routes.client, "fetch_fuelhh", lambda *_args: [])

    result = routes.build_modeled_periods(date(2026, 1, 15), "11:00")

    assert result["matched_periods"] == 0
    assert result["mae_mw"] is None
    assert any("Live Elexon request failed" in warning for warning in result["data_quality_warnings"])


def test_conflicting_duplicate_forecasts_are_not_silently_selected(monkeypatch):
    start_time = "2026-01-15T00:00:00Z"
    monkeypatch.setattr(
        routes.client,
        "fetch_windfor",
        lambda *_args: [
            {
                "dataset": "WINDFOR",
                "startTime": start_time,
                "publishTime": "2026-01-14T10:30:00Z",
                "generation": 100,
            },
            {
                "dataset": "WINDFOR",
                "startTime": start_time,
                "publishTime": "2026-01-14T10:30:00Z",
                "generation": 120,
            },
        ],
    )
    monkeypatch.setattr(
        routes.client,
        "fetch_fuelhh",
        lambda *_args: [
            {
                "dataset": "FUELHH",
                "fuelType": "WIND",
                "startTime": start_time,
                "generation": 90,
            }
        ],
    )

    result = routes.build_modeled_periods(date(2026, 1, 15), "11:00")

    assert result["periods"][0]["selected_forecast_mw"] is None
    assert result["periods"][0]["actual_mw"] == 90
    assert any("Conflicting duplicate WINDFOR" in warning for warning in result["data_quality_warnings"])


def test_zero_actual_is_valid_and_missing_counts_are_separate(monkeypatch):
    monkeypatch.setattr(
        routes.client,
        "fetch_windfor",
        lambda *_args: [
            {
                "dataset": "WINDFOR",
                "startTime": "2026-01-15T00:00:00Z",
                "publishTime": "2026-01-14T10:30:00Z",
                "generation": 0,
            }
        ],
    )
    monkeypatch.setattr(
        routes.client,
        "fetch_fuelhh",
        lambda *_args: [
            {
                "dataset": "FUELHH",
                "fuelType": "WIND",
                "startTime": "2026-01-15T00:00:00Z",
                "publishTime": "2026-01-15T00:30:00Z",
                "generation": 0,
            }
        ],
    )

    result = routes.build_modeled_periods(date(2026, 1, 15), "11:00")

    assert result["periods"][0]["actual_mw"] == 0
    assert result["periods"][0]["actual_publication_time"] == "2026-01-15T00:30:00Z"
    assert result["matched_periods"] == 1
    assert result["missing_forecast_periods"] == 47
    assert result["missing_actual_periods"] == 47
    assert result["missing_periods"] == 47
    assert result["coverage_denominator"] == 48
    assert result["coverage_percentage"] == 2.08


def test_csv_export_contains_same_period_selection_as_overview(monkeypatch):
    start_time = "2026-01-15T00:00:00Z"
    monkeypatch.setattr(
        routes.client,
        "fetch_windfor",
        lambda *_args: [{
            "dataset": "WINDFOR",
            "startTime": start_time,
            "publishTime": "2026-01-14T10:30:00Z",
            "generation": 110,
        }],
    )
    monkeypatch.setattr(
        routes.client,
        "fetch_fuelhh",
        lambda *_args: [{
            "dataset": "FUELHH",
            "fuelType": "WIND",
            "startTime": start_time,
            "publishTime": "2026-01-15T00:30:00Z",
            "generation": 100,
        }],
    )

    response = routes.export_csv("2026-01-15", "11:00")

    async def read_body():
        chunks = [chunk async for chunk in response.body_iterator]
        return b"".join(chunk if isinstance(chunk, bytes) else chunk.encode() for chunk in chunks)

    rows = list(csv.DictReader(io.StringIO(asyncio.run(read_body()).decode())))

    assert len(rows) == 48
    assert rows[0]["selected_forecast_mw"] == "110.0"
    assert rows[0]["forecast_publication_time"] == "2026-01-14T10:30:00Z"
    assert rows[0]["actual_mw"] == "100.0"
    assert rows[0]["status"] == "matched"
