"""Workshop knowledge base. Ported from lib/kb.ts so the agent and the web app agree.

Matching copies the TypeScript `norm` + `has` helpers exactly (word-boundary keywords)."""
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class KbEntry:
    id: str
    title: str
    keywords: tuple[str, ...]
    risk: str            # low | med | high
    hours_x10: int       # labour hours x10 (15 == 1.5h) so money maths stays in integers
    skus: tuple[str, ...]
    doc: str
    # Inspection-first pricing: (skus, hours_x10, low_label, high_label)
    low_scope: tuple[tuple[str, ...], int, str, str] | None = None


KB: tuple[KbEntry, ...] = (
    KbEntry("brakes", "Brake pad and rotor inspection", ("brake", "brakes", "braking", "squeal", "squeals", "pedal"), "high", 15,
            ("BRK-PAD", "BRK-ROT"), "Brake Service Manual 4.2", low_scope=(("BRK-PAD",), 10, "Pads only", "Pads and rotors")),
    KbEntry("oil", "Oil and filter service", ("oil", "oil change"), "low", 7, ("OIL-5L", "OIL-FLT"), "Routine Maintenance Guide"),
    KbEntry("battery", "12V battery test and replacement", ("battery", "starting", "wont start", "dead battery", "12v"), "low", 5, ("BAT-12V",), "Electrical Procedures 2.1"),
    KbEntry("charging", "Charging port and HV safety inspection", ("charge", "charging", "charge port", "high voltage"), "high", 12, ("EV-SEAL",), "EV Safety Procedures 1.0"),
    KbEntry("ac", "AC recharge and leak test", ("ac", "air conditioning", "not cold", "cooling"), "low", 12, ("AC-REF",), "HVAC Guide 3.3"),
    KbEntry("led", "LED headlight upgrade", ("led", "headlight", "headlights", "lights"), "low", 10, ("LED-KIT",), "Upgrade Guide: Lighting"),
    KbEntry("dashcam", "Dashcam installation", ("dashcam", "dash cam", "camera"), "low", 10, ("DASHCAM",), "Upgrade Guide: Electronics"),
    KbEntry("alignment", "Wheel alignment and tyre rotation", ("alignment", "tyre", "tyres", "tire", "tires", "vibration", "vibrates", "pulling"), "low", 10, ("ALIGN-SHIM",), "Chassis Manual 5.4"),
    KbEntry("obd", "OBD-II diagnostic scan", ("check engine", "engine light", "warning light", "diagnostic", "obd"), "med", 8, (), "Diagnostics Guide 6.1"),
    KbEntry("urgent", "Urgent safety inspection", ("smoke", "overheat", "overheating", "fuel leak", "burning", "steering", "airbag",
                                  "wheel nuts", "wheel nut", "loose wheel", "tyre bulge", "tire bulge", "bulge", "sidewall", "blowout", "abs", "petrol smell", "fuel smell", "smell petrol", "smell fuel", "smell of petrol", "smell of fuel", "gas smell", "coolant leak", "steam"), "high", 15, (), "Safety Procedures 0.1"),
)
BY_ID = {e.id: e for e in KB}

# Same prices as scripts/setup.mjs. The web app sends live prices from Neon; this is the dev default.
DEFAULT_PRICES: dict[str, dict] = {
    "BRK-PAD": {"name": "Brake pad set", "cents": 6200}, "BRK-ROT": {"name": "Rotor pair", "cents": 14000},
    "OIL-5L": {"name": "Engine oil 5L", "cents": 3800}, "OIL-FLT": {"name": "Oil filter", "cents": 900},
    "BAT-12V": {"name": "12V battery", "cents": 9500}, "EV-SEAL": {"name": "Charge port seal kit", "cents": 7000},
    "AC-REF": {"name": "AC refrigerant", "cents": 4500}, "LED-KIT": {"name": "LED headlight kit", "cents": 8500},
    "DASHCAM": {"name": "Dashcam 2K", "cents": 11000}, "ALIGN-SHIM": {"name": "Alignment shim kit", "cents": 1500},
}


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s-]", " ", s.lower())).strip()


def _has(text: str, kw: str) -> bool:
    return re.search(rf"(^| ){re.escape(kw)}( |$)", text) is not None


def match(normalised_text: str) -> list[KbEntry]:
    return [e for e in KB if any(_has(normalised_text, k) for k in e.keywords)]
