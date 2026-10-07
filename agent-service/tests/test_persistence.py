"""Restart-survival test against a real Postgres. Skipped unless TEST_DATABASE_URL is set.

  TEST_DATABASE_URL=postgresql://user:pw@localhost/db pytest tests/test_persistence.py
"""
import os

import pytest

os.environ["AUTH_DISABLED"] = "1"
URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="TEST_DATABASE_URL not set")


def _fresh_service(monkeypatch):
    """Simulates a restart: brand-new connection pool and graph, same database."""
    from psycopg.rows import dict_row
    from psycopg_pool import ConnectionPool
    from langgraph.checkpoint.postgres import PostgresSaver

    from app import main
    from app.graph import build_graph
    pool = ConnectionPool(conninfo=URL, min_size=1, max_size=2, open=True,
                          kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row})
    saver = PostgresSaver(pool)
    saver.setup()
    monkeypatch.setattr(main, "graph", build_graph(checkpointer=saver))
    from fastapi.testclient import TestClient
    return TestClient(main.app), pool


def test_runs_and_ownership_survive_restarts(monkeypatch):
    body = {"text": "Brakes squeal when stopping", "vehicle": {"id": 1, "name": "Toyota Corolla 2018", "kind": "ice"}, "history": []}
    cust, tech, other = {"X-Dev-Role": "customer"}, {"X-Dev-Role": "technician"}, {"X-Dev-Role": "customer", "X-Dev-Other": "1"}

    c1, p1 = _fresh_service(monkeypatch)
    rid = c1.post("/requests", json=body, headers=cust).json()["request_id"]
    assert c1.get(f"/requests/{rid}", headers=cust).json()["status"] == "needs_clarification"
    p1.close()                                                       # --- service stops ---

    c2, p2 = _fresh_service(monkeypatch)                             # --- service starts again ---
    assert c2.get(f"/requests/{rid}", headers=cust).json()["status"] == "needs_clarification"
    r = c2.post(f"/requests/{rid}/clarify", headers=cust,
                json={"answers": {"sound": "squeal", "pedal": "normal", "warning": "no"}}).json()
    assert r["status"] == "pending_technician" and r["quote"]["range"]["highCents"] == 28652
    p2.close()                                                       # --- stops again, now waiting for the technician ---

    c3, p3 = _fresh_service(monkeypatch)
    assert c3.get(f"/requests/{rid}", headers=cust).json()["status"] == "pending_technician"
    assert c3.post(f"/requests/{rid}/resume", headers=cust, json={"action": "approve"}).status_code == 403
    r = c3.post(f"/requests/{rid}/resume", headers=tech, json={"action": "approve", "note": "ok"}).json()
    assert r["status"] == "approved"
    assert [t["name"] for t in r["trace"]][-1] == "Technician Review" and len(r["trace"]) == 9  # includes the Clarification step
    assert c3.get("/requests/doesnotexist1", headers=tech).status_code == 404
    p3.close()
