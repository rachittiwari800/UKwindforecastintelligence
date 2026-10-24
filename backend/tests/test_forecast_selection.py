from datetime import date, datetime

from app.analytics.forecast_selection import build_cutoff_utc, build_period_rows, parse_iso_datetime, select_latest_eligible_forecast


def test_selects_latest_eligible_forecast_before_cutoff():
    cutoff = build_cutoff_utc(date(2026, 1, 15), "11:00")
    forecasts = [
        {"publishTime": "2026-01-14T10:00:00Z", "generation": 100},
        {"publishTime": "2026-01-14T11:00:00Z", "generation": 120},
        {"publishTime": "2026-01-14T12:00:00Z", "generation": 140},
    ]
    selected, warnings, err = select_latest_eligible_forecast(forecasts, cutoff)
    assert selected["generation"] == 120
    assert warnings == []
    assert err is None


def test_excludes_after_cutoff_forecast():
    cutoff = build_cutoff_utc(date(2026, 1, 15), "11:00")
    forecasts = [
        {"publishTime": "2026-01-14T10:00:00Z", "generation": 100},
        {"publishTime": "2026-01-14T12:00:00Z", "generation": 140},
    ]
    selected, _, _ = select_latest_eligible_forecast(forecasts, cutoff)
    assert selected["generation"] == 100


def test_missing_eligible_forecast_is_reported():
    cutoff = build_cutoff_utc(date(2026, 1, 15), "11:00")
    forecasts = [{"publishTime": "2026-01-14T12:10:00Z", "generation": 140}]
    selected, warnings, err = select_latest_eligible_forecast(forecasts, cutoff)
    assert selected is None
    assert "No eligible forecast" in (err or "")


def test_duplicate_time_with_conflicting_generation_is_ambiguous():
    cutoff = build_cutoff_utc(date(2026, 1, 15), "11:00")
    forecasts = [
        {"publishTime": "2026-01-14T11:00:00Z", "generation": 100},
        {"publishTime": "2026-01-14T11:00:00Z", "generation": 140},
    ]
    selected, warnings, err = select_latest_eligible_forecast(forecasts, cutoff)
    assert selected is None
    assert any("Ambiguous" in warning for warning in warnings) or err is not None


def test_cutoff_converts_to_utc_for_bst():
    cutoff = build_cutoff_utc(date(2026, 7, 15), "11:00")
    assert cutoff.isoformat() == "2026-07-14T10:00:00+00:00"


def test_invalid_timestamp_is_ignored():
    assert parse_iso_datetime("not-a-timestamp") is None
    cutoff = build_cutoff_utc(date(2026, 1, 15), "11:00")
    selected, _, error = select_latest_eligible_forecast(
        [{"publishTime": "not-a-timestamp", "generation": 100}], cutoff
    )
    assert selected is None
    assert error == "No eligible forecast at the decision cutoff."


def test_missing_data_results_in_unmatched_periods():
    rows = build_period_rows([], [], date(2026, 1, 15), "11:00")
    assert len(rows["periods"]) == 48
    assert all(period["selected_forecast_mw"] is None for period in rows["periods"])
    assert all(period["actual_mw"] is None for period in rows["periods"])
