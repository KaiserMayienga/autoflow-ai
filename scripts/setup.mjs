// Creates the schema and seeds demo data. Safe to re-run; use --reset to wipe first.
import { readFileSync } from "node:fs";
import { neon } from "@neondatabase/serverless";
import bcrypt from "bcryptjs";

if (!process.env.DATABASE_URL) throw new Error("DATABASE_URL missing (run `neon env pull` or check .env.local)");
const sql = neon(process.env.DATABASE_URL);
const run = (t, p = []) => sql.query(t, p);

if (process.argv.includes("--reset")) {
  for (const t of ["audit_logs", "notifications", "reviews", "appointments", "tickets", "parts", "service_history", "vehicles", "users"])
    await run(`drop table if exists ${t} cascade`);
  console.log("Dropped existing tables");
}

for (const stmt of readFileSync(new URL("../db/schema.sql", import.meta.url), "utf8").split(";").map((s) => s.trim()).filter(Boolean)) await run(stmt);
console.log("Schema ready");

const users = [
  ["customer", "customer123", "customer", "Amina K."],
  ["tech", "tech123", "tech", "Technician Omar"],
];
for (const [u, p, role, name] of users)
  await run("insert into users (username, password_hash, role, name) values ($1,$2,$3,$4) on conflict (username) do nothing", [u, bcrypt.hashSync(p, 10), role, name]);

const [{ id: cid }] = await run("select id from users where username='customer'");
const [{ n }] = await run("select count(*)::int as n from vehicles");
if (n === 0) {
  const vehicles = [
    ["Toyota Corolla 2018", "ice", [["Oil change", "2026-03-10"], ["Front brake pads", "2025-08-22"]]],
    ["Nissan Leaf 2020 (EV)", "ev", [["Battery health check", "2026-01-14"]]],
    ["Honda CB125 2021", "ice", [["Chain service", "2026-05-02"]]],
  ];
  for (const [name, kind, hist] of vehicles) {
    const [{ id }] = await run("insert into vehicles (user_id, name, kind) values ($1,$2,$3) returning id", [cid, name, kind]);
    for (const [note, d] of hist) await run("insert into service_history (vehicle_id, note, serviced_on) values ($1,$2,$3)", [id, note, d]);
  }
}

const parts = [
  ["BRK-PAD", "Brake pad set", 6200, 14], ["BRK-ROT", "Rotor pair", 14000, 6], ["OIL-5L", "Engine oil 5L", 3800, 40], ["OIL-FLT", "Oil filter", 900, 60],
  ["BAT-12V", "12V battery", 9500, 8], ["EV-SEAL", "Charge port seal kit", 7000, 5], ["AC-REF", "AC refrigerant", 4500, 20],
  ["LED-KIT", "LED headlight kit", 8500, 10], ["DASHCAM", "Dashcam 2K", 11000, 7], ["ALIGN-SHIM", "Alignment shim kit", 1500, 25],
];
for (const [sku, name, cents, stock] of parts)
  await run("insert into parts (sku, name, price_cents, stock) values ($1,$2,$3,$4) on conflict (sku) do nothing", [sku, name, cents, stock]);

console.log("Seed complete. Demo logins: customer/customer123, tech/tech123");
