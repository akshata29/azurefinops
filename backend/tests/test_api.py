"""Backend API tests (mock mode)."""
from __future__ import annotations

import os

os.environ["USE_MOCK"] = "true"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)
BASE = "/api/v1"


def test_health() -> None:
    r = client.get(f"{BASE}/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["mode"] == "mock"


def test_summary_shape() -> None:
    r = client.get(f"{BASE}/summary")
    assert r.status_code == 200
    body = r.json()
    assert body["affiliate_count"] > 0
    assert body["total_commitment"] >= body["total_remaining"]
    assert 0 <= body["percent_consumed"] <= 100


def test_affiliates_list() -> None:
    r = client.get(f"{BASE}/affiliates")
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 10
    assert {"affiliate_id", "name", "agreement_type", "status"} <= set(data[0].keys())


def test_macc_balances_and_detail() -> None:
    r = client.get(f"{BASE}/macc/balances")
    assert r.status_code == 200
    balances = r.json()
    assert len(balances) > 0
    first = balances[0]["affiliate_id"]

    d = client.get(f"{BASE}/macc/{first}")
    assert d.status_code == 200
    detail = d.json()
    assert detail["balance"]["affiliate_id"] == first
    assert len(detail["trend"]) == 12
    assert len(detail["events"]) == 12


def test_macc_detail_404() -> None:
    assert client.get(f"{BASE}/macc/does-not-exist").status_code == 404


def test_costs_summary() -> None:
    r = client.get(f"{BASE}/costs")
    assert r.status_code == 200
    body = r.json()
    assert len(body["trend"]) == 12
    assert len(body["by_service"]) > 0


def test_licenses() -> None:
    r = client.get(f"{BASE}/licenses")
    assert r.status_code == 200
    assert len(r.json()) > 0


def test_affiliate_breakdown_hierarchy() -> None:
    aff = client.get(f"{BASE}/affiliates").json()[0]["affiliate_id"]
    r = client.get(f"{BASE}/affiliates/{aff}/breakdown")
    assert r.status_code == 200
    body = r.json()
    assert body["affiliate_id"] == aff
    assert body["resource_count"] > 0
    assert len(body["breakdown"]) > 0
    # 4 levels: category -> service -> resourceType -> resource
    cat = body["breakdown"][0]
    assert cat["level"] == 1
    svc = cat["children"][0]
    assert svc["level"] == 2
    rt = svc["children"][0]
    assert rt["level"] == 3
    res = rt["children"][0]
    assert res["level"] == 4
    assert len(body["top_resources"]) > 0


def test_affiliate_breakdown_404() -> None:
    assert client.get(f"{BASE}/affiliates/nope/breakdown").status_code == 404


def test_affiliate_resources() -> None:
    aff = client.get(f"{BASE}/affiliates").json()[0]["affiliate_id"]
    r = client.get(f"{BASE}/affiliates/{aff}/resources")
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) > 0
    assert {"service_category", "service_name", "resource_type", "resource_name", "cost"} <= set(rows[0].keys())


def test_rate_optimization() -> None:
    r = client.get(f"{BASE}/rate-optimization")
    assert r.status_code == 200
    body = r.json()
    assert body["potential_reservation_savings"] >= 0
    assert len(body["by_service"]) > 0
    assert len(body["recommendations"]) > 0


def test_prepayment_and_offer_mix() -> None:
    p = client.get(f"{BASE}/prepayment")
    assert p.status_code == 200
    assert p.json()["macc_total_balance"] >= p.json()["macc_utilized"]
    o = client.get(f"{BASE}/offer-mix")
    assert o.status_code == 200
    assert len(o.json()) > 0


def test_hierarchy() -> None:
    aff = client.get(f"{BASE}/affiliates").json()[0]["affiliate_id"]
    r = client.get(f"{BASE}/affiliates/{aff}/hierarchy")
    assert r.status_code == 200
    root = r.json()["root"]
    assert root["node_type"] == "billingProfile"
    assert len(root["children"]) > 0
    assert client.get(f"{BASE}/affiliates/nope/hierarchy").status_code == 404


def test_ai_consumption() -> None:
    r = client.get(f"{BASE}/ai-consumption")
    assert r.status_code == 200
    body = r.json()
    assert body["total_ai_cost"] > 0
    assert body["copilot_seats"] > 0
    assert len(body["by_source"]) > 0
    assert len(body["trend"]) == 12
    sources = {s["source"] for s in body["by_source"]}
    assert "GitHub Copilot" in sources


def test_tco() -> None:
    r = client.get(f"{BASE}/tco")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= body["azure_cost"]
    assert len(body["by_source"]) == 3
    assert len(body["trend"]) == 12
