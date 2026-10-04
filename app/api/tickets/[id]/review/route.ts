import { z } from "zod";
import { q, audit } from "@/lib/db";
import { requireRole } from "@/lib/auth";
import { slotFor } from "@/lib/slots";
import { AgentError, agentDecide, agentEnabled } from "@/lib/agent";

const Body = z.object({ decision: z.enum(["approve", "reject", "more_info"]), note: z.string().max(300).optional() });
const STATUS = { approve: "Booked", reject: "Rejected", more_info: "More info requested" } as const;

export async function POST(req: Request, ctx: { params: Promise<{ id: string }> }) {
  const s = await requireRole("tech");
  if (s instanceof Response) return s;
  const id = Number((await ctx.params).id);
  const body = Body.safeParse(await req.json().catch(() => null));
  if (!Number.isInteger(id) || !body.success) return Response.json({ error: "Invalid input" }, { status: 400 });

  const [t] = await q<{ id: number; user_id: number; status: string; agent_request_id: string | null }>(
    "select id, user_id, status, agent_request_id from tickets where id = $1", [id]);
  if (!t) return Response.json({ error: "Not found" }, { status: 404 });
  if (!["Pending technician review", "More info requested"].includes(t.status))
    return Response.json({ error: "Ticket is not awaiting review" }, { status: 409 });

  const { decision, note } = body.data;

  // Resume the paused LangGraph run so the agent's trace records the human decision.
  if (t.agent_request_id && agentEnabled()) {
    try {
      await agentDecide(s, t.agent_request_id, decision, note ?? "");
    } catch (e) {
      if (!(e instanceof AgentError)) throw e;
      if (e.status === 404 || e.status === 409) {
        // The agent lost this run (for example after a restart). The technician can still decide;
        // record that the agent trace is incomplete.
        await audit("system", "agent_state_missing", id, `agent ${t.agent_request_id}: ${e.message}`.slice(0, 200));
      } else {
        return Response.json({ error: "The AI agent service is unavailable. Please try again shortly." }, { status: 502 });
      }
    }
  }

  let msg = `#${id}: ${STATUS[decision]}${note ? ` (${note})` : ""}`;
  if (decision === "approve") {
    const [{ n }] = await q<{ n: number }>("select count(*)::int as n from appointments");
    const slot = slotFor(n);
    await q("insert into appointments (ticket_id, slot) values ($1,$2)", [id, slot]);
    msg = `#${id}: technician approved, appointment ${slot}`;
  }
  await q("update tickets set status = $1 where id = $2", [STATUS[decision], id]);
  await q("insert into reviews (ticket_id, tech_id, decision, note) values ($1,$2,$3,$4)", [id, s.uid, decision, note ?? ""]);
  await q("insert into notifications (user_id, ticket_id, message) values ($1,$2,$3)", [t.user_id, id, msg]);
  await audit(s.username, `review_${decision}`, id, note ?? "");
  return Response.json({ ok: true, status: STATUS[decision] });
}
