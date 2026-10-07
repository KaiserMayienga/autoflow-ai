"""Scores the deterministic safety layer against labelled requests.

  python -m evals.run_eval            # prints a report, writes evals/results.json
Labels in cases.jsonl follow workshop policy (what SHOULD happen), not the system's output.
The number that matters most is escalation recall on safety-critical cases: it must be 100%."""
import json
import pathlib
import sys

from app import kb, rules

HERE = pathlib.Path(__file__).parent


def load_cases() -> list[dict]:
    return [json.loads(line) for line in (HERE / "cases.jsonl").read_text().splitlines() if line.strip()]


def predict(case: dict) -> dict:
    t = kb.norm(case["text"])
    hits = [{"id": e.id, "title": e.title, "doc": e.doc, "risk": e.risk} for e in kb.match(t)]
    r = rules.assess_risk(hits, [], None, case["kind"], t)
    return {"escalate": r.escalate, "risk": r.level, "components": [h["id"] for h in hits], "reason": r.reason}


def evaluate() -> dict:
    cases = load_cases()
    rows = []
    for c in cases:
        p = predict(c)
        rows.append({**c, "pred": p})
    safety = [r for r in rows if r["safety"]]
    routine = [r for r in rows if not r["escalate"]]
    missed = [r for r in safety if not r["pred"]["escalate"]]
    over = [r for r in routine if r["pred"]["escalate"]]
    tp = sum(len(set(r["components"]) & set(r["pred"]["components"])) for r in rows)
    fp = sum(len(set(r["pred"]["components"]) - set(r["components"])) for r in rows)
    fn = sum(len(set(r["components"]) - set(r["pred"]["components"])) for r in rows)
    prec = tp / (tp + fp) if tp + fp else 1.0
    rec = tp / (tp + fn) if tp + fn else 1.0
    return {
        "cases": len(rows), "safety_cases": len(safety),
        "escalation_recall_safety": round(1 - len(missed) / len(safety), 4),
        "over_escalation_rate": round(len(over) / len(routine), 4),
        "escalation_accuracy": round(sum(r["escalate"] == r["pred"]["escalate"] for r in rows) / len(rows), 4),
        "triage_accuracy": round(sum(r["risk"] == r["pred"]["risk"] for r in rows) / len(rows), 4),
        "component_precision": round(prec, 4), "component_recall": round(rec, 4),
        "missed_safety_cases": [{"text": r["text"], "kind": r["kind"], "got": r["pred"]} for r in missed],
        "over_escalated": [{"text": r["text"], "kind": r["kind"], "got": r["pred"]} for r in over],
    }


if __name__ == "__main__":
    res = evaluate()
    (HERE / "results.json").write_text(json.dumps(res, indent=2))
    print(f"cases: {res['cases']} ({res['safety_cases']} safety-critical)")
    print(f"escalation recall on safety-critical : {res['escalation_recall_safety']:.1%}   <- must be 100%")
    print(f"over-escalation of routine requests  : {res['over_escalation_rate']:.1%}")
    print(f"escalation accuracy (all cases)      : {res['escalation_accuracy']:.1%}")
    print(f"triage (risk level) accuracy         : {res['triage_accuracy']:.1%}")
    print(f"component detection precision/recall : {res['component_precision']:.1%} / {res['component_recall']:.1%}")
    for k, title in (("missed_safety_cases", "MISSED safety-critical"), ("over_escalated", "Over-escalated")):
        for m in res[k]:
            print(f"  {title}: {m['text']!r} ({m['kind']}) -> {m['got']['reason'] or 'no escalation'}")
    sys.exit(0 if res["escalation_recall_safety"] == 1.0 else 1)
