from __future__ import annotations

import csv
import io
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.analytics.forecast_selection import as_utc, build_cutoff_utc, parse_iso_datetime
from app.analytics.metrics import calculate_metrics
from app.config import settings
from app.services.elexon_client import ElexonAPIError, client

router = APIRouter(prefix="/api")


def filter_records_for_delivery_date(records: list[dict], dataset: str, delivery_date: date) -> list[dict]:
    filtered: list[dict] = []
    for row in records or []:
        if not isinstance(row, dict):
            continue
        if row.get("dataset") != dataset:
            continue
        if dataset == "FUELHH" and row.get("fuelType") != "WIND":
            continue
        start_time = parse_iso_datetime(row.get("startTime"))
        if start_time is None:
            continue
        if start_time.date() != delivery_date:
            continue
        generation = row.get("generation")
        if generation is None:
            continue
        try:
            numeric_generation = float(generation)
        except (TypeError, ValueError):
            continue
        cleaned = dict(row)
        cleaned["generation"] = numeric_generation
        cleaned["_start_dt"] = start_time
        filtered.append(cleaned)
    return filtered


def get_forecast_and_actual_data(delivery_date: date, cutoff: str) -> tuple[list[dict], list[dict], bool, str, list[str]]:
    warnings: list[str] = []
    cutoff_utc = build_cutoff_utc(delivery_date, cutoff)
    try:
        raw_forecasts = client.fetch_windfor(delivery_date, cutoff_utc)
        raw_actuals = client.fetch_fuelhh(delivery_date)
    except ElexonAPIError as exc:
        return [], [], False, "error", [f"Live Elexon request failed: {exc}"]

    forecast_rows = filter_records_for_delivery_date(raw_forecasts, "WINDFOR", delivery_date)
    actual_rows = filter_records_for_delivery_date(raw_actuals, "FUELHH", delivery_date)

    if not forecast_rows:
        warnings.append("No WINDFOR records were returned for the selected delivery date from the public Elexon stream.")
    if not actual_rows:
        warnings.append("No FUELHH WIND actuals were returned for the selected delivery date from the public Elexon stream.")

    return forecast_rows, actual_rows, False, "live", warnings


def build_modeled_periods(delivery_date: date, cutoff: str) -> dict:
    cutoff_utc = build_cutoff_utc(delivery_date, cutoff)
    forecast_rows, actual_rows, _, status, source_warnings = get_forecast_and_actual_data(delivery_date, cutoff)
    warnings: List[str] = list(source_warnings)

    actual_candidates_by_period: Dict[str, List[dict]] = {}
    for row in actual_rows:
        start_time = parse_iso_datetime(row.get("startTime"))
        if start_time is None:
            continue
        key = as_utc(start_time).isoformat()
        publish_time = parse_iso_datetime(row.get("publishTime"))
        actual_candidates_by_period.setdefault(key, []).append({
            "generation": float(row["generation"]),
            "publish_time": row.get("publishTime"),
            "_publish_dt": publish_time,
        })

    actuals_by_period: Dict[str, Optional[float]] = {}
    actual_publications_by_period: Dict[str, Optional[str]] = {}
    for period_key, values in actual_candidates_by_period.items():
        generations = {record["generation"] for record in values}
        if len(generations) > 1:
            warnings.append(f"Conflicting duplicate FUELHH WIND records for {period_key}; actual left unavailable.")
            actuals_by_period[period_key] = None
            actual_publications_by_period[period_key] = None
        else:
            selected_actual = max(
                values,
                key=lambda record: record["_publish_dt"] or datetime.min.replace(tzinfo=ZoneInfo("Europe/London")),
            )
            actuals_by_period[period_key] = selected_actual["generation"]
            actual_publications_by_period[period_key] = selected_actual["publish_time"]

    forecast_by_period: Dict[str, List[dict]] = {}
    for row in forecast_rows:
        start_time = parse_iso_datetime(row.get("startTime"))
        publish_time = parse_iso_datetime(row.get("publishTime"))
        if start_time is None or publish_time is None:
            continue
        delivery_key = as_utc(start_time).isoformat()
        forecast_by_period.setdefault(delivery_key, []).append({**row, "_publish_dt": publish_time})

    periods: List[dict] = []
    matched_forecasts: List[float] = []
    matched_actuals: List[float] = []
    available_actuals = 0
    eligible_forecasts = 0
    matched_periods = 0
    missing_periods = 0
    missing_forecasts = 0
    missing_actuals = 0

    for offset in range(48):
        delivery_dt = datetime.combine(delivery_date, datetime.min.time()).replace(tzinfo=ZoneInfo("Europe/London")) + timedelta(minutes=30 * offset)
        delivery_key = as_utc(delivery_dt).isoformat()
        actual_value = actuals_by_period.get(delivery_key)
        actual_publish = actual_publications_by_period.get(delivery_key)
        forecast_candidates = forecast_by_period.get(delivery_key, [])
        selected = None
        selected_generation = None
        selected_publish = None

        if actual_value is not None:
            available_actuals += 1

        eligible = [candidate for candidate in forecast_candidates if as_utc(candidate["_publish_dt"]) <= cutoff_utc]
        if eligible:
            selected_time = max(candidate["_publish_dt"] for candidate in eligible)
            latest = [candidate for candidate in eligible if candidate["_publish_dt"] == selected_time]
            generations = {float(candidate["generation"]) for candidate in latest if candidate.get("generation") is not None}
            if len(generations) > 1:
                warnings.append(f"Conflicting duplicate WINDFOR forecasts for {delivery_key} at {selected_time.isoformat()}; forecast left unavailable.")
            elif generations:
                selected = latest[0]
                selected_generation = generations.pop()
                selected_publish = selected.get("publishTime")
                eligible_forecasts += 1

        if selected is not None and actual_value is not None:
            matched_periods += 1
            matched_forecasts.append(selected_generation)
            matched_actuals.append(actual_value)

        is_missing_forecast = selected_generation is None
        is_missing_actual = actual_value is None
        if is_missing_forecast:
            missing_forecasts += 1
        if is_missing_actual:
            missing_actuals += 1
        if is_missing_forecast or is_missing_actual:
            missing_periods += 1

        periods.append({
            "delivery_time": delivery_key,
            "selected_forecast_mw": selected_generation,
            "forecast_publication_time": selected_publish,
            "actual_mw": actual_value,
            "actual_publication_time": actual_publish,
            "signed_error_mw": (selected_generation - actual_value) if selected_generation is not None and actual_value is not None else None,
            "absolute_error_mw": abs((selected_generation - actual_value)) if selected_generation is not None and actual_value is not None else None,
            "status": "matched" if not is_missing_forecast and not is_missing_actual else ("missing-both" if is_missing_forecast and is_missing_actual else ("missing-forecast" if is_missing_forecast else "missing-actual")),
            "warning": "Missing forecast at decision cutoff." if selected_generation is None and actual_value is not None else None,
        })

    metrics = calculate_metrics(matched_forecasts, matched_actuals)
    coverage = (matched_periods / 48) * 100 if 48 else 0.0
    if matched_periods == 0:
        warnings.append("No matched periods were available for this delivery date and cutoff. Historical coverage is zero.")
    if not forecast_rows:
        warnings.append("Forecast history is unavailable for the selected delivery date from the live Elexon stream.")
    if missing_forecasts and forecast_rows:
        warnings.append(f"No eligible WINDFOR forecast was available for {missing_forecasts} of 48 delivery periods at the configured cutoff.")
    if missing_actuals and actual_rows:
        warnings.append(f"No FUELHH WIND actual was available for {missing_actuals} of 48 delivery periods.")

    return {
        "delivery_date": delivery_date.isoformat(),
        "timezone": "Europe/London",
        "cutoff_local": cutoff,
        "cutoff_utc": cutoff_utc.isoformat(),
        "forecast_selection_policy": "Assumption: latest WINDFOR record with publishTime <= configured local cutoff (Europe/London) is selected as the decision-time forecast; this is not a confirmed official client rule.",
        "total_expected_periods": 48,
        "available_actual_periods": available_actuals,
        "eligible_forecast_periods": eligible_forecasts,
        "matched_periods": matched_periods,
        "missing_forecast_periods": missing_forecasts,
        "missing_actual_periods": missing_actuals,
        "missing_periods": missing_periods,
        "coverage_percentage": round(coverage, 2),
        "coverage_denominator": 48,
        "coverage_definition": "matched periods divided by 48 expected half-hour delivery periods",
        "mae_mw": metrics.get("mae_mw"),
        "rmse_mw": metrics.get("rmse_mw"),
        "signed_bias_mw": metrics.get("signed_bias_mw"),
        "periods": periods,
        "data_quality_warnings": warnings,
        "data_source_status": status,
        "source": "Elexon data stream",
    }


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "service": settings.app_name}


@router.get("/overview")
def overview(delivery_date_str: str = Query(..., alias="date", description="Delivery date in ISO format, e.g. 2026-01-15"), cutoff: str = Query(default=settings.default_cutoff, description="Local UK time cutoff (HH:MM)")) -> dict:
    try:
        delivery_date = date.fromisoformat(delivery_date_str)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="date must be a valid ISO date (YYYY-MM-DD).") from exc
    if delivery_date.year != 2026 or delivery_date.month != 1:
        raise HTTPException(status_code=400, detail="This dashboard is restricted to January 2026 data.")
    try:
        datetime.strptime(cutoff, "%H:%M")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="cutoff must be in HH:MM format.") from exc
    return build_modeled_periods(delivery_date, cutoff)


@router.get("/forecast-history")
def forecast_history(delivery_date_str: str = Query(..., alias="date", description="Delivery date in ISO format"), cutoff: str = Query(default=settings.default_cutoff, description="Local UK time cutoff (HH:MM)")) -> dict:
    try:
        delivery_date = date.fromisoformat(delivery_date_str)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="date must be a valid ISO date (YYYY-MM-DD).") from exc
    if delivery_date.year != 2026 or delivery_date.month != 1:
        raise HTTPException(status_code=400, detail="This dashboard is restricted to January 2026 data.")
    try:
        datetime.strptime(cutoff, "%H:%M")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="cutoff must be in HH:MM format.") from exc
    forecast_rows, _, _, status, source_warnings = get_forecast_and_actual_data(delivery_date, cutoff)
    cutoff_utc = build_cutoff_utc(delivery_date, cutoff)
    records: List[dict] = []
    for row in forecast_rows:
        publish_dt = parse_iso_datetime(row.get("publishTime"))
        start_time = row.get("startTime")
        if publish_dt is None or not start_time:
            continue
        is_eligible = as_utc(publish_dt) <= cutoff_utc
        records.append({
            "delivery_time": start_time,
            "publish_time": row.get("publishTime"),
            "generation_mw": float(row["generation"]),
            "eligible_at_cutoff": is_eligible,
            "is_selected": False,
        })
    records.sort(key=lambda record: (record["publish_time"], record["delivery_time"]))
    return {
        "delivery_date": delivery_date.isoformat(),
        "cutoff_local": cutoff,
        "cutoff_utc": cutoff_utc.isoformat(),
        "records": records,
        "source": status,
        "data_quality_warnings": source_warnings,
    }


@router.get("/export")
def export_csv(delivery_date_str: str = Query(..., alias="date"), cutoff: str = Query(default=settings.default_cutoff)) -> StreamingResponse:
    overview_data = overview(delivery_date_str=delivery_date_str, cutoff=cutoff)
    output = io.StringIO()
    fieldnames = ["delivery_time", "selected_forecast_mw", "forecast_publication_time", "actual_mw", "actual_publication_time", "signed_error_mw", "absolute_error_mw", "status"]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for period in overview_data["periods"]:
        writer.writerow({key: period.get(key) for key in fieldnames})
    response = StreamingResponse(iter([output.getvalue()]), media_type="text/csv")
    response.headers["Content-Disposition"] = f'attachment; filename="wind-forecast-{delivery_date_str}.csv"'
    return response
