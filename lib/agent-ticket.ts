import { audit, q } from "@/lib/db";
import type { Session } from "@/lib/auth";
import type { AgentView } from "@/lib/agent";
import { slotFor } from "@/lib/slots";

export type Veh = { id: number; name: string; kind: string };

/**
 * Persist a finished agent pass as a ticket and run the same booking / escalation side effects
 * as the original in-process pipeline, so the rest of the app is unchanged.
 */
export async function saveAgentTicket(s: Session, v: AgentView, veh: Veh) {
  const risk = v.risk!;
  const quote = v.quote!;
  const status = risk.escalate ? "Pending technician review" : "Booked";
  const confidence = risk.confidence / 100;
  const passages = (v.retrieval ?? []).map(({ id, source, section, text, score }) => ({ id, source, section, text, score }));
  const analysis = { trace: v.trace, hits: v.hits ?? [], reasons: risk.reasons, passages, recommendation: v.recommendation };

  const [t] = await q<{ id: number }>(
    `insert into tickets (user_id, vehicle_id, text, status, risk, confidence, escalate_reason, analysis, quote, agent_request_id)
     values ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10) returning id`,
    [s.uid, veh.id, v.text, status, risk.level, confidence, risk.reason, JSON.stringify(analysis), JSON.stringify(quote), v.request_id]);
  await audit(s.username, "ticket_created", t.id, `${veh.name}: risk ${risk.level}, confidence ${confidence.toFixed(2)} (agent ${v.request_id})`);

  let appointment: string | null = null;
  if (risk.escalate) {
    const safety = v.recommendation?.advise_not_to_drive ? " Please avoid driving until it has been inspected." : "";
    await audit("system", "escalated", t.id, risk.reason);
    await q("insert into notifications (user_id, ticket_id, message) values ($1,$2,$3)",
      [s.uid, t.id, `#${t.id}: sent to a technician for review (${risk.reason}).${safety}`]);
  } else {
    const [{ n }] = await q<{ n: number }>("select count(*)::int as n from appointments");
    appointment = slotFor(n);
    await q("insert into appointments (ticket_id, slot) values ($1,$2)", [t.id, appointment]);
    await q("insert into notifications (user_id, ticket_id, message) values ($1,$2,$3)", [s.uid, t.id, `#${t.id}: appointment confirmed for ${appointment}`]);
    await audit("system", "booked", t.id, appointment);
  }
  return {
    id: t.id, status, appointment, trace: v.trace, hits: v.hits ?? [], risk: risk.level, confidence,
    escalate: risk.escalate, reason: risk.reason, quote, reasons: risk.reasons, passages, recommendation: v.recommendation,
  };
}
