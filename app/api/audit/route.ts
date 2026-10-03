import { q } from "@/lib/db";
import { requireRole } from "@/lib/auth";

export async function GET() {
  const s = await requireRole("tech");
  if (s instanceof Response) return s;
  const logs = await q("select ts, actor, event, ticket_id, detail from audit_logs order by id desc limit 60");
  const [stats] = await q(`select count(*)::int as total, count(*) filter (where status like 'Pending%' or status in ('Rejected','More info requested') or escalate_reason <> '')::int as escalated from tickets`);
  return Response.json({ logs, stats });
}
