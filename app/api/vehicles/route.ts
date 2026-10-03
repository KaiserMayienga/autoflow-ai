import { q } from "@/lib/db";
import { requireRole } from "@/lib/auth";

export async function GET() {
  const s = await requireRole("customer");
  if (s instanceof Response) return s;
  const vehicles = await q(
    `select v.id, v.name, v.kind, coalesce(json_agg(h.note || ' (' || h.serviced_on || ')' order by h.serviced_on desc) filter (where h.id is not null), '[]') as history
     from vehicles v left join service_history h on h.vehicle_id = v.id where v.user_id = $1 group by v.id order by v.id`, [s.uid]);
  return Response.json({ vehicles });
}
