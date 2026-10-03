import { SignJWT, jwtVerify } from "jose";
import { cookies } from "next/headers";

export type Session = { uid: number; role: "customer" | "tech"; name: string; username: string };
const COOKIE = "af_session";

function key() {
  const s = process.env.AUTH_SECRET;
  if (!s || s.length < 32) throw new Error("AUTH_SECRET must be set (32+ chars)");
  return new TextEncoder().encode(s);
}

export async function createSession(s: Session) {
  const jwt = await new SignJWT({ ...s }).setProtectedHeader({ alg: "HS256" }).setIssuedAt().setExpirationTime("8h").sign(key());
  (await cookies()).set(COOKIE, jwt, { httpOnly: true, sameSite: "lax", secure: process.env.NODE_ENV === "production", path: "/", maxAge: 8 * 3600 });
}

export async function clearSession() {
  (await cookies()).delete(COOKIE);
}

export async function getSession(): Promise<Session | null> {
  const t = (await cookies()).get(COOKIE)?.value;
  if (!t) return null;
  try {
    const { payload } = await jwtVerify(t, key());
    return payload as unknown as Session;
  } catch {
    return null;
  }
}

/** Returns the session, or a Response (401/403) the route should return as-is. */
export async function requireRole(role?: Session["role"]): Promise<Session | Response> {
  const s = await getSession();
  if (!s) return Response.json({ error: "Not signed in" }, { status: 401 });
  if (role && s.role !== role) return Response.json({ error: "Forbidden" }, { status: 403 });
  return s;
}
