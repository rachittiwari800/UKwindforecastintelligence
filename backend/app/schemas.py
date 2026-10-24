from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ForecastDatum(BaseModel):
    dataset: str
    publish_time: str
    start_time: str
    generation: Optional[float] = None


class ActualDatum(BaseModel):
    dataset: str
    start_time: str
    generation: Optional[float] = None
    fuel_type: Optional[str] = None


class TimeSeriesRecord(BaseModel):
    delivery_time: str
    forecast_mw: Optional[float] = None
    forecast_publication_time: Optional[str] = None
    actual_mw: Optional[float] = None
    signed_error_mw: Optional[float] = None
    absolute_error_mw: Optional[float] = None
    status: str
    missing_forecast: bool = False
    missing_actual: bool = False
    warning: Optional[str] = None


class OverviewResponse(BaseModel):
    delivery_date: str
    timezone: str
    cutoff_local: str
    cutoff_utc: str
    forecast_selection_policy: str
    total_expected_periods: int
    available_actual_periods: int
    eligible_forecast_periods: int
    matched_periods: int
    missing_periods: int
    coverage_percentage: float
    mae_mw: Optional[float] = None
    rmse_mw: Optional[float] = None
    signed_bias_mw: Optional[float] = None
    periods: List[TimeSeriesRecord]
    data_quality_warnings: List[str] = Field(default_factory=list)
    data_source_status: str
    source: str


class ForecastHistoryRecord(BaseModel):
    delivery_time: str
    publish_time: str
    generation_mw: float
    eligible_at_cutoff: bool
    is_selected: bool


class ForecastHistoryResponse(BaseModel):
    delivery_date: str
    cutoff_local: str
    cutoff_utc: str
    records: List[ForecastHistoryRecord]
