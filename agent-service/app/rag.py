"""Retriever interface. Keyword scoring now; swap in a QdrantRetriever in Phase 2."""
import re
from typing import Protocol

KB = [
    {"id": "brake-4.2-3", "source": "Brake Service Manual 4.2", "section": "3.1 Noise diagnosis", "system": "brakes",
     "text": "A high-pitched squeal on light braking often indicates pad wear indicators. Grinding indicates pad material is exhausted; inspect rotors immediately."},
    {"id": "brake-4.2-5", "source": "Brake Service Manual 4.2", "section": "5.2 Rotor limits", "system": "brakes",
     "text": "Replace rotors when thickness is below the minimum stamped on the hub, or when scoring or heat spots are present."},
    {"id": "batt-2.1-1", "source": "Electrical Guide 2.1", "section": "1.4 Charging tests", "system": "battery",
     "text": "Test resting voltage, cranking voltage and alternator output. Parasitic drain above the limit points to a faulty module or an aftermarket accessory."},
    {"id": "ac-1.3-2", "source": "HVAC Handbook 1.3", "section": "2.2 Cooling loss", "system": "ac",
     "text": "Weak cooling is commonly low refrigerant from a slow leak, or a failed compressor clutch. Leak test before recharging."},
    {"id": "svc-1.0-1", "source": "Routine Service Schedule", "section": "1.0 Oil service", "system": "service",
     "text": "Replace engine oil and filter at the manufacturer interval; inspect fluids, belts and tyres during service."},
    {"id": "upg-1.0-1", "source": "Accessory Fitting Guide", "section": "1.0 LED and dashcam", "system": "upgrade_electrical",
     "text": "Fit LED headlights with the correct beam pattern and CANbus compatibility. Use fused hardwiring for dashcams."},
]


class Retriever(Protocol):
    def search(self, query: str, categories: list[str], k: int = 3) -> list[dict]: ...


def _tokens(s: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", s.lower()))


class KeywordRetriever:
    def search(self, query: str, categories: list[str], k: int = 3) -> list[dict]:
        q = _tokens(query)
        scored = []
        for doc in KB:
            overlap = len(q & _tokens(doc["text"] + " " + doc["section"]))
            bonus = 3 if doc["system"] in categories else 0
            score = overlap + bonus
            if score > 0:
                scored.append({**doc, "score": round(score / 10, 2)})
        return sorted(scored, key=lambda d: d["score"], reverse=True)[:k]
