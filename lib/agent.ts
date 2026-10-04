import { SignJWT } from "jose";
import type { Session } from "./auth";
import type { Quote } from "./quote";

/**
 * Server-side client for the FastAPI/LangGraph agent service.
 * The browser never talks to the service. Next.js validates the session first, then mints a
 * 2-minute service token (signed with AGENT_SERVICE_SECRET, NOT the session secret) for each call.
 */
const BASE = () => (process.env.AGENT_SERVICE_URL ?? "http://localhost:8000").replace(/\/$/, "");

export const agentEnabled = () => process.env.USE_AGENT_SERVICE === "1";

export type AgentQuestion = { key: string; q: string; options: string[] };
export type AgentQuote = Quote & {
  range?: { lowCents: number; highCents: number; lowLabel: string; highLabel: string; note: string };
};
export type AgentView = {
  request_id: string;
  status: "needs_clarification" | "pending_technician" | "ready_to_book" | "approved" | "rejected" | "needs_info";
  awaiting: { type: "clarification"; questions: AgentQuestion[] } | { type: "technician_review" } | null;
  text: string;
  vehicle: { id?: number | null; name?: string | null; kind?: string | null };
  hits: { id: string; title: string; doc: string; risk: "low" | "med" | "high" }[] | null;
  risk: { level: "low" | "med" | "high"; confidence: number; escalate: boolean; reason: string; reasons: string[]; severe: boolean } | null;
  retrieval: { id: string; source: string; section: string; system: string; text: string; score: number }[] | null;
  quote: AgentQuote | null;
  recommendation: { summary: string; customer_message: string; advise_not_to_drive: boolean; top_source: string | null } | null;
  technician_decision: { action: string; note?: string } | null;
  trace: { step: number; name: string; detail: string }[];
};

export class AgentError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

function key() {
  const s = process.env.AGENT_SERVICE_SECRET;
  if (!s || s.length < 32) throw new Error("AGENT_SERVICE_SECRET must be set (32+ chars)");
  return new TextEncoder().encode(s);
}

async function token(s: Session) {
  return new SignJWT({ role: s.role === "tech" ? "technician" : "customer" })
    .setProtectedHeader({ alg: "HS256" })
    .setSubject(String(s.uid))
    .setIssuedAt()
    .setExpirationTime("2m")
    .sign(key());
}

async function call<T>(s: Session, path: string, body?: unknown): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE()}${path}`, {
      method: body === undefined ? "GET" : "POST",
      headers: { authorization: `Bearer ${await token(s)}`, ...(body === undefined ? {} : { "content-type": "application/json" }) },
      body: body === undefined ? undefined : JSON.stringify(body),
      cache: "no-store",
      signal: AbortSignal.timeout(20_000),
    });
  } catch {
    throw new AgentError(503, "The AI agent service is unavailable");
  }
  if (!res.ok) {
    const j = await res.json().catch(() => null);
    throw new AgentError(res.status, typeof j?.detail === "string" ? j.detail : `Agent service error (${res.status})`);
  }
  return res.json() as Promise<T>;
}

export type AgentVehicle = { id: number; name: string; kind: string };
export type AgentPrices = Record<string, { name: string; cents: number }>;

export const agentStart = (s: Session, text: string, vehicle: AgentVehicle, history: string[], prices: AgentPrices) =>
  call<AgentView>(s, "/requests", { text, vehicle, history, prices });
export const agentClarify = (s: Session, id: string, answers: Record<string, string>) =>
  call<AgentView>(s, `/requests/${id}/clarify`, { answers });
export const agentDecide = (s: Session, id: string, action: "approve" | "reject" | "more_info", note = "") =>
  call<AgentView>(s, `/requests/${id}/resume`, { action, note });
export const agentGet = (s: Session, id: string) => call<AgentView>(s, `/requests/${id}`);
