import { neon } from "@neondatabase/serverless";

let client: ReturnType<typeof neon> | null = null;

/** Run a parameterised query. Retries once or twice to ride out Neon cold starts. */
export async function q<T = Record<string, any>>(text: string, params: unknown[] = []): Promise<T[]> {
  const url = process.env.DATABASE_URL;
  if (!url) throw new Error("DATABASE_URL is not set");
  client ??= neon(url);
  let last: unknown;
  for (let i = 0; i < 3; i++) {
    try {
      return (await client.query(text, params)) as T[];
    } catch (e) {
      last = e;
      await new Promise((r) => setTimeout(r, 400 * (i + 1)));
    }
  }
  throw last;
}

export async function audit(actor: string, event: string, ticketId: number | null, detail = "") {
  await q("insert into audit_logs (actor, event, ticket_id, detail) values ($1,$2,$3,$4)", [actor, event, ticketId, detail]);
}
