"""Regression guard: the deterministic safety layer must never miss a safety-critical case."""
import os

os.environ["AUTH_DISABLED"] = "1"

from evals.run_eval import evaluate


def test_no_safety_critical_request_goes_unescalated():
    res = evaluate()
    assert res["missed_safety_cases"] == [], res["missed_safety_cases"]
    assert res["escalation_recall_safety"] == 1.0


def test_routine_requests_are_not_over_escalated():
    res = evaluate()
    assert res["over_escalation_rate"] <= 0.10, res["over_escalated"]
    assert res["escalation_accuracy"] >= 0.95
