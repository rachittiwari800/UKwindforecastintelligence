from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Dict, List

import httpx

from app.analytics.forecast_selection import as_utc
from app.config import settings


class ElexonAPIError(RuntimeError):
    pass


class ElexonClient:
    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or settings.elexon_base_url).rstrip("/")
        self._cache: Dict[tuple, tuple[float, List[Dict[str, Any]]]] = {}

    def _fetch_raw(self, dataset: str, params: dict[str, str]) -> List[Dict[str, Any]]:
        url = f"{self.base_url}/datasets/{dataset}/stream"
        try:
            response = httpx.get(url, params=params, timeout=45.0, follow_redirects=True)
        except httpx.RequestError as exc:
            raise ElexonAPIError(f"Elexon request failed for {dataset}: {exc}") from exc
        if response.status_code >= 400:
            raise ElexonAPIError(f"Elexon API returned {response.status_code} for {dataset}.")
        try:
            data = response.json()
        except ValueError as exc:
            raise ElexonAPIError(f"Malformed JSON from Elexon for {dataset}.") from exc
        if not isinstance(data, list) or any(not isinstance(item, dict) for item in data):
            raise ElexonAPIError(f"Unexpected payload structure for {dataset}: expected a list of records.")
        return data

    def _cached_fetch(self, dataset: str, params: dict[str, str]) -> List[Dict[str, Any]]:
        key = (dataset, tuple(sorted(params.items())))
        now = datetime.now(timezone.utc).timestamp()
        cached = self._cache.get(key)
        if cached and cached[0] > now:
            return cached[1]

        data = self._fetch_raw(dataset, params)
        self._cache[key] = (now + settings.cache_ttl_seconds, data)
        return data

    def fetch_windfor(self, delivery_date: date, cutoff_utc: datetime) -> List[Dict[str, Any]]:
        publication_start = datetime.combine(
            delivery_date - timedelta(days=14), time.min, tzinfo=timezone.utc
        )
        revision_history_end = datetime.combine(
            delivery_date + timedelta(days=2), time.min, tzinfo=timezone.utc
        )
        publication_end = max(as_utc(cutoff_utc), revision_history_end)
        params = {
            "publishDateTimeFrom": publication_start.isoformat().replace("+00:00", "Z"),
            "publishDateTimeTo": publication_end.isoformat().replace("+00:00", "Z"),
        }
        return self._cached_fetch("WINDFOR", params)

    def fetch_fuelhh(self, delivery_date: date) -> List[Dict[str, Any]]:
        params = {
            "settlementDateFrom": delivery_date.isoformat(),
            "settlementDateTo": delivery_date.isoformat(),
            "fuelType": "WIND",
        }
        return self._cached_fetch("FUELHH", params)

    def fetch_dataset(self, dataset: str, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        """Fetch a date-bounded stream using the dataset's documented query names."""
        if dataset == "WINDFOR":
            params = {
                "publishDateTimeFrom": datetime.combine(
                    start_date, time.min, tzinfo=timezone.utc
                ).isoformat().replace("+00:00", "Z"),
                "publishDateTimeTo": datetime.combine(
                    end_date, time.max, tzinfo=timezone.utc
                ).isoformat().replace("+00:00", "Z"),
            }
        elif dataset == "FUELHH":
            params = {
                "settlementDateFrom": start_date.isoformat(),
                "settlementDateTo": end_date.isoformat(),
                "fuelType": "WIND",
            }
        else:
            raise ValueError(f"Unsupported Elexon dataset: {dataset}")
        return self._cached_fetch(dataset, params)


def build_date_range(delivery_date: date) -> tuple[date, date]:
    return delivery_date, delivery_date


client = ElexonClient()
