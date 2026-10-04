"""Retriever interface. Keyword scoring now; swap in a QdrantRetriever in Phase 2.

`system` is a knowledge-base entry id (see kb.py)."""
import re
from typing import Protocol

PASSAGES = [
    {"id": "brake-4.2-3", "source": "Brake Service Manual 4.2", "section": "3.1 Noise diagnosis", "system": "brakes",
     "text": "A high-pitched squeal on light braking often indicates pad wear indicators. Grinding indicates pad material is exhausted; inspect rotors immediately."},
    {"id": "brake-4.2-5", "source": "Brake Service Manual 4.2", "section": "5.2 Rotor limits", "system": "brakes",
     "text": "Replace rotors when thickness is below the minimum stamped on the hub, or when scoring or heat spots are present."},
    {"id": "elec-2.1-4", "source": "Electrical Procedures 2.1", "section": "1.4 Charging tests", "system": "battery",
     "text": "Test resting voltage, cranking voltage and alternator output. Parasitic drain above the limit points to a faulty module or an aftermarket accessory."},
    {"id": "ev-1.0-2", "source": "EV Safety Procedures 1.0", "section": "2.1 High-voltage isolation", "system": "charging",
     "text": "Only certified technicians may work on high-voltage components. Isolate the pack and verify zero voltage before inspecting the charge port."},
    {"id": "hvac-3.3-2", "source": "HVAC Guide 3.3", "section": "2.2 Cooling loss", "system": "ac",
     "text": "Weak cooling is commonly low refrigerant from a slow leak, or a failed compressor clutch. Leak test before recharging."},
    {"id": "svc-1.0-1", "source": "Routine Maintenance Guide", "section": "1.0 Oil service", "system": "oil",
     "text": "Replace engine oil and filter at the manufacturer interval; inspect fluids, belts and tyres during service."},
    {"id": "upg-light-1", "source": "Upgrade Guide: Lighting", "section": "1.0 LED headlights", "system": "led",
     "text": "Fit LED headlights with the correct beam pattern and CANbus compatibility, and re-aim after fitting."},
    {"id": "upg-elec-1", "source": "Upgrade Guide: Electronics", "section": "1.0 Dashcam", "system": "dashcam",
     "text": "Use fused hardwiring for dashcams and route cables clear of airbag panels."},
    {"id": "safe-0.1-1", "source": "Safety Procedures 0.1", "section": "1.1 Urgent symptoms", "system": "urgent",
     "text": "Smoke, fuel leaks, overheating, or steering and airbag faults require the vehicle to be inspected before further driving."},
]


class Retriever(Protocol):
    def search(self, query: str, hit_ids: list[str], k: int = 3) -> list[dict]: ...


def _tokens(s: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", s.lower()))


class KeywordRetriever:
    def search(self, query: str, hit_ids: list[str], k: int = 3) -> list[dict]:
        q = _tokens(query)
        scored = []
        for doc in PASSAGES:
            overlap = len(q & _tokens(doc["text"] + " " + doc["section"]))
            bonus = 3 if doc["system"] in hit_ids else 0
            score = overlap + bonus
            if score > 0 and (bonus or overlap >= 2):
                scored.append({**doc, "score": round(score / 10, 2)})
        return sorted(scored, key=lambda d: d["score"], reverse=True)[:k]
