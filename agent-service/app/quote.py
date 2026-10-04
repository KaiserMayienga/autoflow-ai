"""Deterministic quote engine, identical in behaviour to lib/quote.ts. Integer cents only.

hours are passed as hours_x10 (15 == 1.5h) to avoid floats. The model never prices."""
from . import config
from .kb import BY_ID, DEFAULT_PRICES, KbEntry


def build_quote(skus: list[str], hours_x10: int, prices: dict) -> dict:
    parts = []
    for sku in skus:
        p = prices.get(sku)
        if p:  # unknown SKUs are skipped, as in the TypeScript pipeline
            parts.append({"sku": sku, "name": p["name"], "qty": 1, "unitCents": p["cents"], "totalCents": p["cents"]})
    parts_cents = sum(p["totalCents"] for p in parts)
    labour = (config.LABOUR_RATE_CENTS * hours_x10 + 5) // 10
    subtotal = parts_cents + labour
    vat = (subtotal * config.VAT_PERCENT + 50) // 100
    return {"parts": parts, "partsCents": parts_cents, "hours": hours_x10 / 10, "labourCents": labour,
            "subtotalCents": subtotal, "vatCents": vat, "totalCents": subtotal + vat}


DIAGNOSTIC_HOURS_X10 = 8  # no knowledge-base match: quote a diagnostic inspection, never $0


def quote_for_hits(hit_ids: list[str], prices: dict | None) -> dict:
    """Full-scope quote, plus a low/high range when a topic is priced inspection-first."""
    prices = prices or DEFAULT_PRICES
    hits: list[KbEntry] = [BY_ID[i] for i in hit_ids]
    if not hits:
        return build_quote([], DIAGNOSTIC_HOURS_X10, prices)
    high_skus = [s for h in hits for s in h.skus]
    high_h = sum(h.hours_x10 for h in hits)
    quote = build_quote(high_skus, high_h, prices)

    scoped = [h for h in hits if h.low_scope]
    if scoped:
        low_skus = [s for h in hits for s in (h.low_scope[0] if h.low_scope else h.skus)]
        low_h = sum((h.low_scope[1] if h.low_scope else h.hours_x10) for h in hits)
        low = build_quote(low_skus, low_h, prices)
        if low["totalCents"] != quote["totalCents"]:
            quote["range"] = {"lowCents": low["totalCents"], "highCents": quote["totalCents"],
                              "lowLabel": scoped[0].low_scope[2], "highLabel": scoped[0].low_scope[3],
                              "note": "Final scope is confirmed by a technician after inspection."}
    return quote
