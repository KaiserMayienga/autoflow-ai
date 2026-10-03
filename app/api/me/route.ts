import { getSession } from "@/lib/auth";
export async function GET() {
  const s = await getSession();
  return s ? Response.json({ name: s.name, role: s.role }) : Response.json({ error: "Not signed in" }, { status: 401 });
}
