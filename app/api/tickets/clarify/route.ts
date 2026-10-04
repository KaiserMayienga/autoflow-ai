import { z } from "zod";
import { q } from "@/lib/db";
import { requireRole } from "@/lib/auth";
import { AgentError, agentClarify, agentEnabled } from "@/lib/agent";
import { saveAgentTicket } from "@/lib/agent-ticket";

const Body = z.object({
  requestId: z.string().regex(/^[a-f0-9]{12}$/),
  answers: z.record(z.string().max(40), z.string().max(60)).refine((a) => Object.keys(a).length > 0 && Object.keys(a).length <= 10),
});

/** Second step of a request: the customer answers the agent's clarifying questions. */
export async function POST(req: Request) {
  const s = await requireRole("customer");
  if (s instanceof Response) return s;
  if (!agentEnabled()) return Response.json({ error: "Not available" }, { status: 404 });
  const body = Body.safeParse(await req.json().catch(() => null));
  if (!body.success) return Response.json({ error: "Please answer every question" }, { status: 400 });

  let v;
  try {
    v = await agentClarify(s, body.data.requestId, body.data.answers);
  } catch (e) {
    if (e instanceof AgentError) {
      const gone = e.status === 404 || e.status === 409;
      if (e.status === 403) return Response.json({ error: "Forbidden" }, { status: 403 });
      return Response.json({ error: gone ? "This request has expired. Please submit it again." : e.message }, { status: gone ? 410 : 502 });
    }
    throw e;
  }
  if (v.status === "needs_clarification" && v.awaiting?.type === "clarification")
    return Response.json({ needsClarification: true, requestId: v.request_id, questions: v.awaiting.questions });

  // Never trust the browser for which vehicle this is: take it from the agent's copy and re-check ownership.
  const [veh] = await q<{ id: number; name: string; kind: string }>("select id, name, kind from vehicles where id = $1 and user_id = $2", [v.vehicle?.id ?? 0, s.uid]);
  if (!veh) return Response.json({ error: "Vehicle not found" }, { status: 404 });
  return Response.json(await saveAgentTicket(s, v, veh));
}
