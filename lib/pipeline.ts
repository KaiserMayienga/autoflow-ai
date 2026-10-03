import { KB, type KbEntry } from "./kb";
import { buildQuote, type PartLine, type Quote } from "./quote";

export type TraceStep = { step: number; name: string; detail: string };
export type PipelineInput = { text: string; vehicle: { name: string; kind: string }; history: string[]; prices: Record<string, { name: string; cents: number }> };
export type PipelineResult = {
  trace: TraceStep[]; hits: Pick<KbEntry, "id" | "title" | "doc" | "risk">[]; risk: "low" | "med" | "high";
  confidence: number; escalate: boolean; reason: string; quote: Quote;
};

const norm = (s: string) => s.toLowerCase().replace(/[^a-z0-9\s-]/g, " ").replace(/\s+/g, " ").trim();
const has = (text: string, kw: string) => new RegExp(`(^| )${kw.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}( |$)`).test(text);

/**
 * The 7 orchestration steps from the architecture. Phase 1 runs them as plain functions.
 * Phase 2 turns each into a LangGraph node and lets the LLM handle steps 1, 5 and 7.
 */
export function runPipeline(inp: PipelineInput): PipelineResult {
  const trace: TraceStep[] = [];
  const t = norm(inp.text);
  trace.push({ step: 1, name: "Request Parser", detail: `Parsed ${t.split(" ").length} words` });
  trace.push({ step: 2, name: "Vehicle Context", detail: `${inp.vehicle.name}; ${inp.history.length} service history records loaded` });

  const hits = KB.filter((e) => e.keywords.some((k) => has(t, k)));
  const risk = hits.some((h) => h.risk === "high") ? "high" : hits.some((h) => h.risk === "med") ? "med" : "low";
  const confidence = hits.length ? Math.min(0.95, 0.55 + 0.2 * hits.length) : 0.2;
  const evHv = inp.vehicle.kind === "ev" && /(battery|charg)/.test(t);
  let reason = "";
  if (risk === "high") reason = "Safety-critical topic";
  else if (confidence < 0.6) reason = "Low confidence match";
  else if (evHv) reason = "High-voltage EV system";
  const escalate = reason !== "";
  trace.push({ step: 3, name: "Risk Assessment", detail: `Risk ${risk}, confidence ${Math.round(confidence * 100)}%${escalate ? `, escalation: ${reason}` : ""}` });
  trace.push({ step: 4, name: "Knowledge Retrieval", detail: hits.length ? `Matched: ${hits.map((h) => h.doc).join(", ")}` : "No relevant documents" });
  trace.push({ step: 5, name: "Agent Decision", detail: hits.length ? `Actions: ${hits.map((h) => h.id).join(", ")}` : "Route to technician" });

  const parts: PartLine[] = [];
  let hours = 0;
  for (const h of hits) {
    hours += h.hours;
    for (const sku of h.skus) {
      const p = inp.prices[sku];
      if (p) parts.push({ sku, name: p.name, qty: 1, unitCents: p.cents });
    }
  }
  const quote = buildQuote(parts, hours);
  trace.push({ step: 6, name: "Controlled Tool Execution", detail: `Parts lookup (${parts.length}), quotation engine run` });
  trace.push({ step: 7, name: "Recommendation Builder", detail: escalate ? "Prepared for technician review" : "Ready for booking" });

  return { trace, hits: hits.map(({ id, title, doc, risk }) => ({ id, title, doc, risk })), risk, confidence, escalate, reason, quote };
}
