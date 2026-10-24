from datetime import date, datetime

import httpx
import pytest

from app.services.elexon_client import ElexonAPIError, ElexonClient


def test_elexon_api_error_is_raised_for_http_500(monkeypatch):
    def fake_get(*args, **kwargs):
        class FakeResponse:
            status_code = 500

            def json(self):
                return {}

        return FakeResponse()

    monkeypatch.setattr(httpx, "get", fake_get)

    client = ElexonClient(base_url="https://example.com")
    with pytest.raises(ElexonAPIError):
        client.fetch_windfor(
            date(2026, 1, 15),
            datetime.fromisoformat("2026-01-14T11:00:00+00:00"),
        )


def test_elexon_api_error_is_raised_for_network_failure(monkeypatch):
    def fake_get(*args, **kwargs):
        raise httpx.ConnectError("network unavailable")

    monkeypatch.setattr(httpx, "get", fake_get)

    client = ElexonClient(base_url="https://example.com")
    with pytest.raises(ElexonAPIError, match="request failed"):
        client.fetch_fuelhh(date(2026, 1, 15))
