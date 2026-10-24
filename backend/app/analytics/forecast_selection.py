from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, Iterable, List, Optional, Tuple
from zoneinfo import ZoneInfo


TIMEZONE = ZoneInfo("Europe/London")
UTC = ZoneInfo("UTC")


def parse_iso_datetime(value: Optional[str | datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=TIMEZONE)
    return dt.astimezone(TIMEZONE)


def as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TIMEZONE)
    return dt.astimezone(UTC)


def build_cutoff_utc(delivery_date: date, cutoff_time: str = "11:00") -> datetime:
    try:
        cutoff_local = datetime.combine(delivery_date - timedelta(days=1), time.fromisoformat(cutoff_time)).replace(tzinfo=TIMEZONE)
    except ValueError as exc:
        raise ValueError("cutoff_time must be in HH:MM format.") from exc
    return as_utc(cutoff_local)


def normalise_record(record: Dict[str, Any]) -> Dict[str, Any]:
    updated = dict(record)
    for key in ("publishTime", "startTime"):
        if key in updated and updated[key] is not None:
            updated[key] = updated[key].replace("Z", "+00:00") if isinstance(updated[key], str) else updated[key]
    return updated


def select_latest_eligible_forecast(forecasts: Iterable[Dict[str, Any]], cutoff_utc: datetime) -> Tuple[Optional[Dict[str, Any]], List[str], Optional[str]]:
    prepared: List[Dict[str, Any]] = []
    warnings: List[str] = []
    for entry in forecasts:
        if not isinstance(entry, dict):
            continue
        normalized = normalise_record(entry)
        publish_time = parse_iso_datetime(normalized.get("publishTime"))
        if publish_time is None:
            continue
        normalized["_publish_dt"] = publish_time
        prepared.append(normalized)

    eligible = [entry for entry in prepared if as_utc(entry["_publish_dt"]) <= cutoff_utc]
    if not eligible:
        return None, warnings, "No eligible forecast at the decision cutoff."

    grouped: Dict[datetime, List[Dict[str, Any]]] = defaultdict(list)
    for entry in eligible:
        grouped[entry["_publish_dt"]].append(entry)

    selected_dt = max(grouped.keys())
    candidates = grouped[selected_dt]
    generation_values = {float(item.get("generation")) for item in candidates if item.get("generation") is not None}
    if len(generation_values) > 1:
        warnings.append(f"Ambiguous forecasts at {selected_dt.isoformat()} with multiple generation values.")
        return None, warnings, "Duplicate forecast timestamps conflict at the cutoff."

    selected = sorted(candidates, key=lambda item: item.get("publishTime") or "", reverse=True)[0]
    return selected, warnings, None


def build_period_rows(actual_rows: Iterable[Dict[str, Any]], forecast_rows: Iterable[Dict[str, Any]], delivery_date: date, cutoff_time: str = "11:00") -> Dict[str, Any]:
    cutoff_utc = build_cutoff_utc(delivery_date, cutoff_time)
    actuals_by_period: Dict[datetime, float] = {}
    for row in actual_rows:
        normalized = normalise_record(row)
        start_time = parse_iso_datetime(normalized.get("startTime"))
        if start_time is None:
            continue
        generation = normalized.get("generation")
        if generation is None:
            continue
        try:
            actuals_by_period[as_utc(start_time)] = float(generation)
        except (TypeError, ValueError):
            continue

    forecast_by_period: Dict[datetime, List[dict]] = defaultdict(list)
    for row in forecast_rows:
        normalized = normalise_record(row)
        start_time = parse_iso_datetime(normalized.get("startTime"))
        publish_time = parse_iso_datetime(normalized.get("publishTime"))
        if start_time is None or publish_time is None:
            continue
        forecast_by_period[as_utc(start_time)].append({**normalized, "_publish_dt": publish_time})

    periods = []
    warnings: List[str] = []
    current = datetime.combine(delivery_date, datetime.min.time())
    for period_index in range(48):
        period_start = as_utc(current + timedelta(minutes=30 * period_index))
        issue = None
        actual = actuals_by_period.get(period_start)
        candidates = forecast_by_period.get(period_start, [])
        eligible = [item for item in candidates if as_utc(item["_publish_dt"]) <= cutoff_utc]
        if not eligible:
            issue = "No eligible forecast at the decision cutoff."
        selected = None
        if eligible:
            selected_dt = max(item["_publish_dt"] for item in eligible)
            same_time = [item for item in eligible if item["_publish_dt"] == selected_dt]
            generation_values = {float(item.get("generation")) for item in same_time if item.get("generation") is not None}
            if len(generation_values) > 1:
                warnings.append(f"Ambiguous forecast revision for {period_start.isoformat()}.")
                selected = None
            else:
                selected = max(same_time, key=lambda item: item["_publish_dt"]) if same_time else None
        periods.append({
            "delivery_time": period_start.isoformat(),
            "actual_mw": actual,
            "selected_forecast_mw": float(selected.get("generation")) if selected and selected.get("generation") is not None else None,
            "selected_forecast_publication_time": selected["publishTime"] if selected else None,
            "warning": issue,
        })

    return {"cutoff_utc": cutoff_utc.isoformat(), "periods": periods, "warnings": warnings}
