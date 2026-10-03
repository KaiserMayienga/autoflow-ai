import { z } from "zod";
import bcrypt from "bcryptjs";
import { q, audit } from "@/lib/db";
import { createSession } from "@/lib/auth";

const Body = z.object({ username: z.string().min(1).max(40), password: z.string().min(1).max(100) });

export async function POST(req: Request) {
  const body = Body.safeParse(await req.json().catch(() => null));
  if (!body.success) return Response.json({ error: "Invalid input" }, { status: 400 });
  const [u] = await q<{ id: number; username: string; password_hash: string; role: "customer" | "tech"; name: string }>(
    "select id, username, password_hash, role, name from users where username = $1", [body.data.username]);
  const ok = u ? await bcrypt.compare(body.data.password, u.password_hash) : false;
  if (!u || !ok) {
    await audit(body.data.username, "login_failed", null);
    return Response.json({ error: "Invalid credentials" }, { status: 401 });
  }
  await createSession({ uid: u.id, role: u.role, name: u.name, username: u.username });
  await audit(u.username, "login", null, u.role);
  return Response.json({ name: u.name, role: u.role });
}
