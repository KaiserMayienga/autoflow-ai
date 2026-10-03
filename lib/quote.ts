/** Deterministic quotation engine. The LLM never computes prices: all money is integer cents. */
export type PartLine = { sku: string; name: string; qty: number; unitCents: number };
export type Quote = { parts: (PartLine & { totalCents: number })[]; partsCents: number; hours: number; labourCents: number; subtotalCents: number; vatCents: number; totalCents: number };

export const LABOUR_RATE_CENTS = 3000; // $30/hour
export const VAT_RATE = 0.16;

export function buildQuote(parts: PartLine[], hours: number, rateCents = LABOUR_RATE_CENTS, vatRate = VAT_RATE): Quote {
  const lines = parts.map((p) => ({ ...p, totalCents: p.qty * p.unitCents }));
  const partsCents = lines.reduce((a, l) => a + l.totalCents, 0);
  const labourCents = Math.round(hours * rateCents);
  const subtotalCents = partsCents + labourCents;
  const vatCents = Math.round(subtotalCents * vatRate);
  return { parts: lines, partsCents, hours, labourCents, subtotalCents, vatCents, totalCents: subtotalCents + vatCents };
}
