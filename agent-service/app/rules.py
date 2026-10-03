"""Deterministic rule layer: categories, risk, escalation.

The model may never override these. Matching uses word boundaries so a short
keyword like "ac" can never match inside "back".
"""
import re
from dataclasses import dataclass

SAFETY_CRITICAL = {"brakes", "steering", "airbag", "fuel", "smoke", "high_voltage"}

CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "brakes": ["brake", "brakes", "braking", "rotor", "rotors", "pads", "pedal"],
    "steering": ["steering", "wheel pulls", "pulls to"],
    "airbag": ["airbag", "air bag", "srs"],
    "fuel": ["fuel leak", "petrol smell", "fuel smell", "gas smell"],
    "smoke": ["smoke", "burning smell", "overheating"],
    "high_voltage": ["ev battery", "hybrid battery", "high voltage", "charging port", "ev charging"],
    "battery": ["battery", "charging", "alternator", "drains"],
    "ac": ["ac", "a/c", "air conditioning", "not cold"],
    "service": ["oil change", "oil", "service", "filter"],
    "upgrade_electrical": ["led", "headlights", "dashcam", "dash cam", "stereo"],
    "noise_unknown": ["strange noise", "weird noise", "noise", "rattle"],
}

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


def _has(text: str, kw: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(kw)}(?![a-z0-9])", text) is not None


def find_categories(text: str) -> list[str]:
    t = text.lower()
    return [c for c, kws in CATEGORY_KEYWORDS.items() if any(_has(t, k) for k in kws)]


def find_symptoms(text: str) -> list[str]:
    t = text.lower()
    return [s for s, kws in SYMPTOM_KEYWORDS.items() if any(_has(t, k) for k in kws)]


@dataclass
class Risk:
    level: str
    confidence: int
    escalate: bool
    reasons: list[str]


def assess_risk(categories: list[str], symptoms: list[str], answers: dict | None = None) -> Risk:
    answers = answers or {}
    reasons: list[str] = []
    critical = [c for c in categories if c in SAFETY_CRITICAL]

    if critical:
        reasons.append(f"Rule: {', '.join(critical)} is safety-critical -> mandatory technician sign-off")
        level, confidence = "high", 75
    elif not categories:
        return Risk("medium", 30, True, ["Rule: no recognised component -> low confidence -> technician review"])
    elif categories == ["noise_unknown"]:
        return Risk("medium", 40, True, ["Rule: unidentified noise -> low confidence -> technician review"])
    elif "upgrade_electrical" in categories:
        reasons.append("Rule: electrical upgrade -> routine; wiring scope verified at fitting")
        level, confidence = "low", 85
    else:
        reasons.append("Routine maintenance category; no safety rule fired")
        level, confidence = "low", 90

    if symptoms:
        confidence = min(95, confidence + 10)
        reasons.append(f"Symptom detail captured: {', '.join(symptoms)}")
    if answers:
        confidence = min(95, confidence + 10)
        reasons.append("Customer answered clarifying questions")
    if SEVERE_SYMPTOMS & set(symptoms) or SEVERE_ANSWERS & set(answers.values()):
        level = "high"
        reasons.append("Severe symptom indicated -> advise not driving until inspected")

    escalate = bool(critical) or confidence < 60
    return Risk(level, confidence, escalate, reasons)


CLARIFYING_QUESTIONS = {
    "brakes": [
        {"key": "sound", "q": "Is the noise a squeal/squeak or a grinding sound?", "options": ["squeal", "grinding", "not sure"]},
        {"key": "pedal", "q": "Does the brake pedal feel soft or sink?", "options": ["normal", "soft"]},
        {"key": "warning", "q": "Is any brake or ABS warning light on?", "options": ["no", "yes"]},
    ],
}


def questions_for(categories: list[str], symptoms: list[str]) -> list[dict]:
    """Ask only when a safety-critical category has no symptom detail beyond a squeal."""
    for c in categories:
        if c in CLARIFYING_QUESTIONS and not (set(symptoms) - {"squeal"}):
            return CLARIFYING_QUESTIONS[c]
    return []
