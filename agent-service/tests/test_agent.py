import os
os.environ["AUTH_DISABLED"] = "1"

from fastapi.testclient import TestClient

from app import quote, rules
from app.main import app

c = TestClient(app)
COROLLA = {"make": "Toyota", "model": "Corolla", "year": 2018}


def test_quote_matches_existing_demo_total():
    q = quote.build_quote(["brake_pad_set", "rotor_pair"], 15, "x")
    assert (q["vat_cents"], q["total_cents"]) == (3952, 28652)


def test_word_boundary_bug_stays_fixed():
    assert "ac" not in rules.find_categories("noise from the back of the car")
    assert "ac" in rules.find_categories("ac not cold")


def test_brake_squeal_asks_questions_then_escalates():
    r = c.post("/requests", json={"text": "Brakes squeal when stopping", "vehicle": COROLLA}).json()
    assert r["status"] == "needs_clarification" and len(r["awaiting"]["questions"]) == 3
    rid = r["request_id"]
    r = c.post(f"/requests/{rid}/clarify", json={"answers": {"sound": "squeal", "pedal": "normal", "warning": "no"}}).json()
    assert r["status"] == "pending_technician"
    assert r["risk"]["level"] == "high" and r["risk"]["escalate"]
    assert r["quote"]["type"] == "range"
    assert r["quote"]["high"]["total_cents"] == 28652 and r["quote"]["low"]["total_cents"] < 28652
    assert r["retrieval"][0]["source"] == "Brake Service Manual 4.2"


def test_grinding_answer_advises_not_driving():
    rid = c.post("/requests", json={"text": "Brakes squeal when stopping", "vehicle": COROLLA}).json()["request_id"]
    r = c.post(f"/requests/{rid}/clarify", json={"answers": {"sound": "grinding", "pedal": "normal", "warning": "no"}}).json()
    assert r["recommendation"]["advise_not_to_drive"] is True


def test_technician_approval_resumes_graph_and_trace_is_complete():
    rid = c.post("/requests", json={"text": "Brakes grinding and warning light on", "vehicle": COROLLA}).json()["request_id"]
    assert c.get(f"/requests/{rid}").json()["status"] == "pending_technician"
    r = c.post(f"/requests/{rid}/resume", json={"action": "approve", "note": "Book inspection"}).json()
    assert r["status"] == "approved"
    names = [t["name"] for t in c.get(f"/requests/{rid}/trace").json()["trace"]]
    assert names == ["Request Parser", "Vehicle Context", "Risk Assessment", "Knowledge Retrieval",
                     "Agent Decision", "Controlled Tool Execution", "Recommendation Builder", "Technician Review"]


def test_routine_request_does_not_escalate():
    r = c.post("/requests", json={"text": "Oil change please", "vehicle": COROLLA}).json()
    assert r["status"] == "ready_to_book" and not r["risk"]["escalate"]


def test_unknown_noise_escalates_on_low_confidence():
    r = c.post("/requests", json={"text": "Strange noise, not sure what", "vehicle": COROLLA}).json()
    assert r["status"] == "pending_technician" and r["risk"]["confidence"] < 60


def test_customer_cannot_use_technician_endpoint_or_see_others():
    rid = c.post("/requests", json={"text": "Brakes grinding", "vehicle": COROLLA}, headers={"X-Dev-Role": "technician"}).json()["request_id"]
    assert c.post(f"/requests/{rid}/resume", json={"action": "approve"}, headers={"X-Dev-Role": "customer"}).status_code == 403
    assert c.get(f"/requests/{rid}", headers={"X-Dev-Role": "customer"}).status_code == 403


def test_resume_before_escalation_is_rejected():
    rid = c.post("/requests", json={"text": "Oil change please", "vehicle": COROLLA}).json()["request_id"]
    assert c.post(f"/requests/{rid}/resume", json={"action": "approve"}).status_code == 409
