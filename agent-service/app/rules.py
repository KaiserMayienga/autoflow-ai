"""Deterministic risk and escalation. The model may never override these.

Mirrors lib/pipeline.ts (risk, confidence, escalation reasons) and adds symptom handling,
clarifying questions and human-readable reasons."""
import re
from dataclasses import dataclass

SYMPTOM_KEYWORDS = {
    "squeal": ["squeal", "squeak", "screech"],
    "grind": ["grind", "grinding", "scrape"],
    "vibration": ["judder", "vibrat", "shake", "shaking"],
    "soft_pedal": ["soft pedal", "spongy", "pedal sinks", "pedal goes"],
    "warning_light": ["warning light", "dashboard light", "check engine"],
    "pull": ["pulls", "pull to"],
}
SEVERE_SYMPTOMS = {"grind", "soft_pedal", "warning_light", "pull"}
SEVERE_ANSWERS = {"grinding", "soft", "yes"}

CLARIFYING_QUESTIONS = {
    "brakes": [
        {"key": "sound", "q": "Is the noise a squeal/squeak or a grinding sound?", "options": ["squeal", "grinding", "not sure"]},
        {"key": "pedal", "q": "Does the brake pedal feel soft or sink?", "options": ["normal", "soft"]},
        {"key": "warning", "q": "Is any brake or ABS warning light on?", "options": ["no", "yes"]},
    ],
}


def _has(text: str, kw: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(kw)}(?![a-z0-9])", text) is not None


def find_symptoms(text: str) -> list[str]:
    t = text.lower()
    return [s for s, kws in SYMPTOM_KEYWORDS.items() if any(_has(t, k) for k in kws)]


def questions_for(hit_ids: list[str], symptoms: list[str]) -> list[dict]:
    """Ask only when a safety-critical topic has no symptom detail beyond a squeal."""
    for c in hit_ids:
        if c in CLARIFYING_QUESTIONS and not (set(symptoms) - {"squeal"}):
            return CLARIFYING_QUESTIONS[c]
    return []


@dataclass
class Risk:
    level: str          # low | med | high
    confidence: int     # percent
    escalate: bool
    reason: str         # same strings the web app already shows
    reasons: list[str]  # explanation for the UI / audit trail
    severe: bool


def assess_risk(hits: list[dict], symptoms: list[str], answers: dict | None, vehicle_kind: str | None, norm_text: str) -> Risk:
    answers = answers or {}
    reasons: list[str] = []
    level = "high" if any(h["risk"] == "high" for h in hits) else "med" if any(h["risk"] == "med" for h in hits) else "low"
    confidence = min(95, 55 + 20 * len(hits)) if hits else 20
    high_titles = [h["title"] for h in hits if h["risk"] == "high"]

    if high_titles:
        reasons.append(f"Rule: {', '.join(high_titles)} is safety-critical -> mandatory technician sign-off")
    if not hits:
        reasons.append("No recognised component in the knowledge base -> low confidence -> technician review")
    ev_hv = vehicle_kind == "ev" and re.search(r"(battery|charg)", norm_text) is not None
    if ev_hv:
        reasons.append("Rule: battery or charging work on an EV involves the high-voltage system -> technician review")

    if hits and symptoms:
        confidence = min(95, confidence + 10)
        reasons.append(f"Symptom detail captured: {', '.join(symptoms)}")
    if hits and answers:
        confidence = min(95, confidence + 10)
        reasons.append("Customer answered clarifying questions")
    severe = bool(SEVERE_SYMPTOMS & set(symptoms) or SEVERE_ANSWERS & set(answers.values()))
    if severe:
        reasons.append("Severe symptom indicated -> advise not driving until inspected")
    if not reasons:
        reasons.append("Routine maintenance; no safety rule fired")

    reason = ""
    if level == "high":
        reason = "Safety-critical topic"
    elif confidence < 60:
        reason = "Low confidence match"
    elif ev_hv:
        reason = "High-voltage EV system"
    return Risk(level, confidence, reason != "", reason, reasons, severe)
