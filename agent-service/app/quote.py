"""Deterministic quote engine. Integer minor units only; the model never prices."""
from . import config

PARTS = {
    "brake_pad_set": ("Brake pad set", 6200),
    "rotor_pair": ("Rotor pair", 14000),
    "oil_filter_kit": ("Oil and filter kit", 3500),
    "led_headlight_kit": ("LED headlight kit", 9500),
    "dashcam_kit": ("Dashcam and hardwire kit", 7500),
}


def _vat(subtotal: int) -> int:
    return (subtotal * config.VAT_PERCENT + 50) // 100


def build_quote(parts: list[str], labour_hours_x10: int, label: str) -> dict:
    """labour_hours_x10 avoids floats: 15 == 1.5h."""
    lines = [{"item": PARTS[p][0], "cents": PARTS[p][1]} for p in parts]
    labour = (config.LABOUR_RATE_CENTS * labour_hours_x10) // 10
    lines.append({"item": f"Labour {labour_hours_x10 / 10:g}h", "cents": labour})
    subtotal = sum(line["cents"] for line in lines)
    vat = _vat(subtotal)
    return {"label": label, "lines": lines, "subtotal_cents": subtotal,
            "vat_cents": vat, "total_cents": subtotal + vat, "currency": config.CURRENCY}


def brake_inspection_quote() -> dict:
    """Inspection-first: a range, because rotors depend on measured thickness."""
    low = build_quote(["brake_pad_set"], 10, "Pads only")
    high = build_quote(["brake_pad_set", "rotor_pair"], 15, "Pads and rotors")
    return {"type": "range", "low": low, "high": high, "currency": config.CURRENCY,
            "note": "Final scope confirmed by a technician after measuring rotor thickness."}


def fixed_quote(label: str, parts: list[str], labour_hours_x10: int) -> dict:
    return {"type": "fixed", "quote": build_quote(parts, labour_hours_x10, label),
            "currency": config.CURRENCY}
