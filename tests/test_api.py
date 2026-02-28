import pytest
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("ok", "stale")
    assert isinstance(data["last_update"], str)
    assert isinstance(data["days_stale"], int)


def test_summary_daily():
    response = client.get("/summary/daily?days=30")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    if data:
        record = data[0]
        assert "sale_date" in record
        assert "revenue" in record
        assert "gross_margin" in record
        assert "transactions" in record
        assert "margin_pct" in record


def test_margins_by_product():
    response = client.get("/margins/by-product")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) <= 20
    if data:
        record = data[0]
        assert "product_name" in record
        assert "revenue" in record
        assert "gross_margin" in record
        assert "transactions" in record
        assert "margin_pct" in record
