"use client";
import { useCallback, useEffect, useState } from "react";

type Me = { name: string; role: "customer" | "tech" };
type Ticket = any;
const money = (c: number) => `$${(c / 100).toFixed(2)}`;
const api = async (url: string, body?: unknown) => {
  const r = await fetch(url, body === undefined ? undefined : { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || "Request failed");
  return j;
};

function TicketCard({ t, children }: { t: Ticket; children?: React.ReactNode }) {
  const risk = t.risk, rc = risk === "high" ? "hi" : risk === "med" ? "md" : "lo";
  const hits = t.analysis?.hits ?? [], q = t.quote;
  return (
    <div className="card">
      <h2>Ticket #{t.id}{t.vehicle ? `: ${t.vehicle}` : ""}</h2>
      {t.text && <div className="mut">“{t.text}”</div>}
      <p><b>Preliminary assessment:</b> {hits.length ? hits.map((h: any) => h.title).join("; ") : "No confident match in workshop knowledge"}<br />
        <span className={rc}>Risk: {risk}</span> · Confidence: {Math.round(t.confidence * 100)}%{hits.length ? ` · Sources: ${hits.map((h: any) => h.doc).join(", ")}` : ""}</p>
      <div className="sc"><table><tbody>
        {q.parts.map((p: any) => <tr key={p.sku}><td>{p.name}</td><td>{money(p.totalCents)}</td></tr>)}
        <tr><td>Labour {q.hours.toFixed(1)}h</td><td>{money(q.labourCents)}</td></tr>
        <tr><td>VAT 16%</td><td>{money(q.vatCents)}</td></tr>
        <tr><td><b>Estimated total (deterministic quote engine)</b></td><td><b>{money(q.totalCents)}</b></td></tr>
      </tbody></table></div>
      <p><span className="tag">{t.status}</span> {t.appointment ? `Appointment: ${t.appointment}` : (t.escalate_reason ?? t.reason) ? `Escalated: ${t.escalate_reason ?? t.reason}` : ""}</p>
      {children}
    </div>
  );
}

export default function Home() {
  const [me, setMe] = useState<Me | null | undefined>(undefined);
  useEffect(() => { api("/api/me").then(setMe).catch(() => setMe(null)); }, []);
  if (me === undefined) return <div className="wrap mut">Loading…</div>;
  if (!me) return <Login onDone={setMe} />;
  return <Shell me={me} onOut={() => { api("/api/logout", {}); setMe(null); }} />;
}

function Login({ onDone }: { onDone: (m: Me) => void }) {
  const [u, setU] = useState(""), [p, setP] = useState(""), [err, setErr] = useState(""), [busy, setBusy] = useState(false);
  const go = async () => { setBusy(true); setErr(""); try { onDone(await api("/api/login", { username: u, password: p })); } catch (e: any) { setErr(e.message); } setBusy(false); };
  return (
    <div className="wrap">
      <header><h1>🔧 AutoFlow AI</h1></header>
      <div className="card"><h2>Sign in</h2><div className="mut">AI workflow automation for automotive repair and upgrade workshops</div>
        <label>Username</label><input value={u} onChange={(e) => setU(e.target.value)} autoComplete="off" />
        <label>Password</label><input type="password" value={p} onChange={(e) => setP(e.target.value)} onKeyDown={(e) => e.key === "Enter" && go()} />
        <div className="row" style={{ marginTop: 12 }}><button onClick={go} disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button><span className="mut hi">{err}</span></div>
        <div className="cred"><b>Demo credentials</b><br />Customer: <code>customer</code> / <code>customer123</code><br />Technician: <code>tech</code> / <code>tech123</code></div>
      </div>
    </div>
  );
}

function Shell({ me, onOut }: { me: Me; onOut: () => void }) {
  const cust = me.role === "customer";
  const tabs: [string, string][] = cust ? [["new", "New request"], ["mine", "My requests"]] : [["queue", "Review queue"], ["all", "All work orders"]];
  const [view, setView] = useState(tabs[0][0]);
  const [data, setData] = useState<{ tickets: Ticket[]; notifications: any[] }>({ tickets: [], notifications: [] });
  const [auditData, setAudit] = useState<{ logs: any[]; stats: any } | null>(null);
  const load = useCallback(async () => {
    setData(await api("/api/tickets"));
    if (!cust) setAudit(await api("/api/audit"));
  }, [cust]);
  useEffect(() => { load().catch(() => {}); }, [load]);
  return (
    <div className="wrap">
      <header><h1>🔧 AutoFlow AI <span className="tag">{cust ? "Customer" : "Technician"}</span></h1>
        <div className="row"><span className="mut">{me.name}</span><button className="g" onClick={onOut}>Sign out</button></div></header>
      <div className="tabs">{tabs.map(([k, l]) => <button key={k} className={view === k ? "" : "g"} onClick={() => { setView(k); load(); }}>{l}</button>)}</div>
      {view === "new" && <NewRequest onDone={load} />}
      {view === "mine" && <>
        {data.notifications.length > 0 && <div className="card"><h2>Notifications</h2>{data.notifications.map((n, i) => <div key={i} className="mut">• {n.message}</div>)}</div>}
        {data.tickets.map((t) => <TicketCard key={t.id} t={t} />)}
        {!data.tickets.length && <div className="card mut">No requests yet.</div>}
      </>}
      {view === "queue" && <Queue tickets={data.tickets} reload={load} />}
      {view === "all" && <div className="card sc"><h2>Work orders</h2><table><thead><tr><th>#</th><th>Vehicle</th><th>Status</th><th>Appointment</th><th>Total</th></tr></thead><tbody>
        {data.tickets.map((t) => <tr key={t.id}><td>{t.id}</td><td>{t.vehicle}</td><td>{t.status}</td><td>{t.appointment ?? "-"}</td><td>{money(t.quote.totalCents)}</td></tr>)}</tbody></table></div>}
      {!cust && auditData && <div className="card"><h2>Governance</h2>
        <div className="mut">{auditData.stats.total} tickets · {auditData.stats.escalated} escalated to a technician</div>
        <div className="log">{auditData.logs.map((l, i) => <div key={i}>{new Date(l.ts).toLocaleTimeString()} {l.actor} {l.event}{l.ticket_id ? ` #${l.ticket_id}` : ""} {l.detail}</div>)}</div></div>}
    </div>
  );
}

function NewRequest({ onDone }: { onDone: () => void }) {
  const [vehicles, setVehicles] = useState<any[]>([]), [vid, setVid] = useState(0), [text, setText] = useState("");
  const [busy, setBusy] = useState(false), [err, setErr] = useState(""), [shown, setShown] = useState(0), [res, setRes] = useState<any>(null);
  useEffect(() => { api("/api/vehicles").then((j) => { setVehicles(j.vehicles); setVid(j.vehicles[0]?.id ?? 0); }).catch((e) => setErr(e.message)); }, []);
  const run = async () => {
    setBusy(true); setErr(""); setRes(null); setShown(0);
    try {
      const r = await api("/api/tickets", { vehicleId: vid, text });
      for (let i = 1; i <= r.trace.length; i++) { await new Promise((z) => setTimeout(z, 300)); setShown(i); }
      setRes(r); onDone();
    } catch (e: any) { setErr(e.message); }
    setBusy(false);
  };
  const ex = ["Brakes squeal when stopping", "Oil change and AC not cold", "Install LED headlights and a dashcam", "Battery drains fast and charging seems slow", "Strange noise, not sure what"];
  return (<>
    <div className="card"><h2>Describe the problem or upgrade</h2>
      <label>Vehicle</label><select value={vid} onChange={(e) => setVid(Number(e.target.value))}>{vehicles.map((v) => <option key={v.id} value={v.id}>{v.name}</option>)}</select>
      <label>Problem or upgrade goal</label><textarea rows={3} maxLength={500} value={text} onChange={(e) => setText(e.target.value)} placeholder="e.g. My brakes squeal when stopping, and I want LED headlights" />
      <div className="row" style={{ marginTop: 6 }}>{ex.map((x) => <button key={x} className="g" onClick={() => setText(x)}>{x}</button>)}</div>
      <div className="row" style={{ marginTop: 12 }}><button onClick={run} disabled={busy || !vid || text.trim().length < 5}>{busy ? "Analyzing…" : "Analyze with AutoFlow AI"}</button><span className="hi">{err}</span></div>
    </div>
    {(busy || res) && <div className="card steps"><h2>AI orchestration pipeline</h2>
      {(res?.trace ?? Array.from({ length: 7 }, (_, i) => ({ step: i + 1, name: "…", detail: "" }))).map((s: any, i: number) => <div key={i} className={i < shown ? "on" : ""}>{s.step}. {i < shown ? `${s.name}: ${s.detail}` : s.name}</div>)}</div>}
    {res && <TicketCard t={{ ...res, vehicle: vehicles.find((v) => v.id === vid)?.name, text, analysis: { hits: res.hits }, quote: res.quote, escalate_reason: res.reason }} />}
  </>);
}

function Queue({ tickets, reload }: { tickets: Ticket[]; reload: () => void }) {
  const pending = tickets.filter((t) => t.status === "Pending technician review" || t.status === "More info requested");
  const act = async (id: number, decision: string) => { await api(`/api/tickets/${id}/review`, { decision }); reload(); };
  if (!pending.length) return <div className="card mut">Queue is empty. Submit a brake or EV charging request as the customer to see an escalation.</div>;
  return <>{pending.map((t) => <TicketCard key={t.id} t={t}>
    <div className="row"><button className="ok" onClick={() => act(t.id, "approve")}>Approve</button><button className="er" onClick={() => act(t.id, "reject")}>Reject</button><button className="g" onClick={() => act(t.id, "more_info")}>Request more information</button></div>
  </TicketCard>)}</>;
}
