import { z } from "zod";
import { q, audit } from "@/lib/db";
import { requireRole } from "@/lib/auth";
import { runPipeline } from "@/lib/pipeline";
import { slotFor } from "@/lib/slots";
import { AgentError, agentEnabled, agentStart } from "@/lib/agent";
import { saveAgentTicket } from "@/lib/agent-ticket";

const Body = z.object({ vehicleId: z.number().int().positive(), text: z.string().trim().min(5).max(500) });

export async function GET() {
  const s = await requireRole();
  if (s instanceof Response) return s;
  const cols = `t.id, t.text, t.status, t.risk, t.confidence, t.escalate_reason, t.analysis, t.quote, t.created_at, v.name as vehicle,
    (select slot from appointments a where a.ticket_id = t.id order by a.id desc limit 1) as appointment`;
  const tickets = s.role === "tech"
    ? await q(`select ${cols} from tickets t join vehicles v on v.id = t.vehicle_id order by t.id desc limit 100`)
    : await q(`select ${cols} from tickets t join vehicles v on v.id = t.vehicle_id where t.user_id = $1 order by t.id desc limit 100`, [s.uid]);
  const notifications = s.role === "customer"
    ? await q("select message, created_at from notifications where user_id = $1 order by id desc limit 20", [s.uid]) : [];
  return Response.json({ tickets, notifications });
}

export async function POST(req: Request) {
  const s = await requireRole("customer");
  if (s instanceof Response) return s;
  const body = Body.safeParse(await req.json().catch(() => null));
  if (!body.success) return Response.json({ error: "Describe the problem in 5 to 500 characters" }, { status: 400 });

  const [veh] = await q<{ id: number; name: string; kind: string }>("select id, name, kind from vehicles where id = $1 and user_id = $2", [body.data.vehicleId, s.uid]);
  if (!veh) return Response.json({ error: "Vehicle not found" }, { status: 404 });
  const history = (await q<{ note: string }>("select note from service_history where vehicle_id = $1", [veh.id])).map((h) => h.note);
  const prices = Object.fromEntries((await q<{ sku: string; name: string; price_cents: number }>("select sku, name, price_cents from parts"))
    .map((p) => [p.sku, { name: p.name, cents: p.price_cents }]));

  // AI agent service (FastAPI + LangGraph). If it is switched off or unreachable, fall back to the
  // in-process pipeline below so customers are never blocked.
  if (agentEnabled()) {
    try {
      const v = await agentStart(s, body.data.text, veh, history, prices);
      if (v.status === "needs_clarification" && v.awaiting?.type === "clarification")
        return Response.json({ needsClarification: true, requestId: v.request_id, questions: v.awaiting.questions });
      return Response.json(await saveAgentTicket(s, v, veh));
    } catch (e) {
      if (!(e instanceof AgentError)) throw e;
      await audit("system", "agent_unavailable", null, `fell back to built-in pipeline: ${e.message}`.slice(0, 200));
    }
  }

  const result = runPipeline({ text: body.data.text, vehicle: veh, history, prices });
  const status = result.escalate ? "Pending technician review" : "Booked";
  const [t] = await q<{ id: number }>(
    `insert into tickets (user_id, vehicle_id, text, status, risk, confidence, escalate_reason, analysis, quote)
     values ($1,$2,$3,$4,$5,$6,$7,$8,$9) returning id`,
    [s.uid, veh.id, body.data.text, status, result.risk, result.confidence, result.reason, JSON.stringify({ trace: result.trace, hits: result.hits }), JSON.stringify(result.quote)]);
  await audit(s.username, "ticket_created", t.id, `${veh.name}: risk ${result.risk}, confidence ${result.confidence.toFixed(2)}`);

  let appointment: string | null = null;
  if (result.escalate) {
    await audit("system", "escalated", t.id, result.reason);
    await q("insert into notifications (user_id, ticket_id, message) values ($1,$2,$3)", [s.uid, t.id, `#${t.id}: sent to a technician for review (${result.reason})`]);
  } else {
    const [{ n }] = await q<{ n: number }>("select count(*)::int as n from appointments");
    appointment = slotFor(n);
    await q("insert into appointments (ticket_id, slot) values ($1,$2)", [t.id, appointment]);
    await q("insert into notifications (user_id, ticket_id, message) values ($1,$2,$3)", [s.uid, t.id, `#${t.id}: appointment confirmed for ${appointment}`]);
    await audit("system", "booked", t.id, appointment);
  }
  return Response.json({ id: t.id, status, appointment, ...result });
}
