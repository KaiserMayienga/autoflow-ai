// One-off migration: links each ticket to its run in the agent service. Safe to re-run.
import { neon } from "@neondatabase/serverless";

if (!process.env.DATABASE_URL) throw new Error("DATABASE_URL missing (run with: node --env-file=.env.local scripts/add-agent-column.mjs)");
const sql = neon(process.env.DATABASE_URL);
await sql.query("alter table tickets add column if not exists agent_request_id text");
await sql.query("create index if not exists tickets_agent_request_id_idx on tickets (agent_request_id)");
console.log("tickets.agent_request_id is ready");
