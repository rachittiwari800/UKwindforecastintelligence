from datetime import date, datetime

import httpx

from app.services.elexon_client import ElexonClient


def test_windfor_uses_documented_publication_time_parameters(monkeypatch):
    captured = {}

    class FakeResponse:
        status_code = 200

        def json(self):
            return []

    def fake_get(url, params, **kwargs):
        captured.update(url=url, params=params)
        return FakeResponse()

    monkeypatch.setattr(httpx, "get", fake_get)

    client = ElexonClient(base_url="https://example.com")
    client.fetch_windfor(
        date(2026, 1, 15),
        datetime.fromisoformat("2026-01-14T11:00:00+00:00"),
    )

    assert captured["url"] == "https://example.com/datasets/WINDFOR/stream"
    assert captured["params"] == {
        "publishDateTimeFrom": "2026-01-01T00:00:00Z",
        "publishDateTimeTo": "2026-01-17T00:00:00Z",
    }


def test_fuelhh_uses_documented_settlement_date_and_fuel_type_parameters(monkeypatch):
    captured = {}

    class FakeResponse:
        status_code = 200

        def json(self):
            return []

    def fake_get(url, params, **kwargs):
        captured.update(url=url, params=params)
        return FakeResponse()

    monkeypatch.setattr(httpx, "get", fake_get)

    client = ElexonClient(base_url="https://example.com")
    client.fetch_fuelhh(date(2026, 1, 15))

    assert captured["url"] == "https://example.com/datasets/FUELHH/stream"
    assert captured["params"] == {
        "settlementDateFrom": "2026-01-15",
        "settlementDateTo": "2026-01-15",
        "fuelType": "WIND",
    }
