"use client";
import { Fragment, useCallback, useEffect, useState } from "react";
import { api, download, when } from "../../../lib/api";

const blank = { business_name: "", contact_name: "", phone: "", email: "", website: "", city: "", market_code: "", industry: "" };
const cls = (s) => "st-" + s.replace(/[^a-z]/gi, "").toLowerCase();
const SEV = { 3: ["High", "st-lost"], 2: ["Medium", "st-contacted"], 1: ["Low", "st-new"] };
const BASIS = { measured: ["Measured by the program", "chip on"], verified: ["Exact quote found on the page", "chip on"], inferred: ["AI inference, please confirm", "chip off"] };
const BAND_CLASS = { High: "st-won", Medium: "st-contacted", Low: "st-new", Strong: "st-won", Good: "st-won", Moderate: "st-contacted", Weak: "st-new" };
const bandText = (b) => (["High", "Medium", "Low"].includes(b) ? `${b} priority` : `${b} (old method)`);
const PAIN_STATUS = { VERIFIED: ["Pain verified", "st-won"], HYPOTHESIS: ["Key pain is a hypothesis", "st-contacted"], UNVERIFIED: ["Pain not verified", "st-lost"] };

function Evidence({ g }) {
  return (<>
    {g.quote ? <em>{g.evidence}</em> : g.evidence}
    {g.url && <><br /><a href={g.url} target="_blank" rel="noreferrer">Open the page</a></>}
    {g.urls_checked?.length > 0 && <details><summary>Pages looked at ({g.urls_checked.length})</summary><ul>{g.urls_checked.map((u) => <li key={u}><a href={u} target="_blank" rel="noreferrer">{u}</a></li>)}</ul></details>}
  </>);
}

function GapTable({ gaps, empty }) {
  if (!gaps.length) return <p>{empty}</p>;
  return (<div className="scroll"><table className="tbl"><thead><tr><th>Problem</th><th>Evidence</th><th>How we know</th><th>HY service</th><th>Weight</th></tr></thead>
    <tbody>{gaps.map((g, i) => <tr key={i}><td><b>{g.pain}</b></td><td><Evidence g={g} /></td>
      <td><span className={BASIS[g.basis][1]} style={{ display: "inline-block", padding: "2px 8px", border: "2px solid", fontSize: 13 }}>{BASIS[g.basis][0]}</span></td>
      <td>{g.service}</td><td><span className={`tag ${SEV[g.severity][1]}`}>{SEV[g.severity][0]}</span></td></tr>)}</tbody></table></div>);
}

function evidencePack(d) {
  const r = d.analysis.report;
  const line = (g, i) => `${i + 1}. ${g.pain} [${BASIS[g.basis][0]}] ${g.evidence}${g.url ? ` (${g.url})` : ""}`;
  return [`Lead: ${d.business_name}${d.city ? `, ${d.city}` : ""}`, `Website: ${d.website || "none"}`, `Checked on: ${r.checked_at}`, `What the business does: ${d.analysis.summary}`, "",
    "VERIFIED OBSERVATIONS (a software agency could help: websites, mobile apps, CRM and ERP, cloud, automation):", ...(r.gaps.filter((g) => g.direct).map(line) || []), "",
    "HYPOTHESES TO CONFIRM:", ...r.gaps.filter((g) => !g.direct).map(line), "",
    "Already in place:", ...(r.already_has.length ? r.already_has.map((h) => `- ${h.item}${h.url ? ` (${h.url})` : ""}`) : ["- nothing recorded"]), "",
    "Our ratings (0 to 5): " + Object.values(r.ratings).map((x) => `${x.name} ${x.rating} (weight ${x.weight})`).join(", "),
    `Score: ${r.score} out of 100, ${r.priority}, pain ${r.pain_status.toLowerCase()}, confidence ${r.confidence}.`,
    "Question: using only this evidence, is the pain really verified, and is the priority fair? Which findings look weak?"].join("\n");
}

function FitReport({ d, say }) {
  const r = d.analysis.report, ps = PAIN_STATUS[r.pain_status];
  async function copy() { await navigator.clipboard.writeText(evidencePack(d)); say("Copied. Paste it into ChatGPT or Gemini for a second opinion."); }
  return (<>
    <div className="row" style={{ alignItems: "center", gap: 24 }}>
      <div style={{ textAlign: "center", minWidth: 130 }}><div style={{ fontSize: 60, fontFamily: "var(--serif)", fontWeight: 900, color: "var(--maroon)", lineHeight: 1 }}>{r.score}</div>
        <div style={{ color: "var(--mute)" }}>out of 100</div></div>
      <div style={{ flex: "1 1 360px" }}>
        <span className={`tag ${BAND_CLASS[r.band]}`}>{r.priority}</span> <span className={`tag ${ps[1]}`}>{ps[0]}</span> <span className={`tag ${r.confidence === "High" ? "st-won" : r.confidence === "Medium" ? "st-contacted" : "st-lost"}`}>Confidence: {r.confidence}</span>
        <p style={{ margin: "8px 0 2px" }}><b>{d.analysis.summary}</b></p>
        <p style={{ margin: 0 }}>{r.verdict} Best service: <b>{d.hy_solution || "none yet"}</b>. Checked on {r.checked_at}.</p>
      </div>
    </div>

    <h3>How the score is made</h3>
    <div className="scroll"><table className="tbl"><thead><tr><th>Factor</th><th>Rating (0 to 5)</th><th className="num">Weight</th><th className="num">Points</th><th>Why</th></tr></thead>
      <tbody>{Object.values(r.ratings).map((x) => <tr key={x.name}><td><b>{x.name}</b></td><td>{x.rating} {x.label}</td><td className="num">{x.weight}</td><td className="num">{x.points}</td><td>{x.why}</td></tr>)}
        {r.adjustments.map((a, i) => <tr key={i}><td colSpan={3}><b>Adjustment:</b> {a.label}</td><td className="num">{a.points}</td><td></td></tr>)}
        <tr><td colSpan={3}><b>Final score</b></td><td className="num"><b>{r.score}</b></td><td>Points = rating divided by 5, times the weight. A priority for outreach, not a chance to buy.</td></tr></tbody></table></div>

    <h3>Verified observations</h3>
    <GapTable gaps={r.gaps.filter((g) => g.direct)} empty="Nothing verified yet. Do not make a pain-based pitch." />
    <h3>Hypotheses to confirm</h3>
    <GapTable gaps={r.gaps.filter((g) => !g.direct)} empty="None." />
    {r.already_has.length > 0 && <><h3>Already in place</h3><ul>{r.already_has.map((h, i) => <li key={i}>{h.item}{h.url && <> <a href={h.url} target="_blank" rel="noreferrer">page</a></>}</li>)}</ul></>}
    {r.buying_signals.length > 0 && <><h3>Buying signals</h3><ul>{r.buying_signals.map((b, i) => <li key={i}>{b.signal}: <em>“{b.quote}”</em> <a href={b.url} target="_blank" rel="noreferrer">page</a></li>)}</ul></>}
    <h3>Recommended outreach angle</h3><p>{r.angle}</p>
    {d.analysis.talking_points?.length > 0 && <><h3>Talking points</h3><ul>{d.analysis.talking_points.map((t, i) => <li key={i}>{t}</li>)}</ul></>}
    {r.missing_information.length > 0 && <><h3>Missing information</h3><ul>{r.missing_information.map((m, i) => <li key={i}>{m}</li>)}</ul></>}
    {r.caveats.length > 0 && <><h3>Read this before you call</h3><ul>{r.caveats.map((c, i) => <li key={i}>{c}</li>)}</ul></>}
    <div className="msg" style={{ marginTop: 14 }}><b>Check it yourself.</b> Open the page link on a finding and look for the quoted words. "Measured" items come from the program's own tests.
      Hypotheses were not seen on a page, so confirm them first. For a second opinion, <button className="linklike" onClick={copy}>copy the evidence pack</button> and paste it into ChatGPT or Gemini.</div>
  </>);
}

function LeadDetail({ id }) {
  const [d, setD] = useState(null);
  const [msg, setMsg] = useState("");
  useEffect(() => { api(`/api/leads/${id}`).then(setD).catch((e) => setMsg(e.message)); }, [id]);
  async function again() {
    setMsg("");
    try { await api(`/api/leads/${id}/analyze`, { method: "POST" }); setMsg("Analysis started. Follow it in Lead Discovery, then reopen this lead."); } catch (e) { setMsg(e.message); }
  }
  async function callNow() {
    setMsg("");
    try {
      const r = await api("/api/campaigns", { method: "POST", body: { name: `Call ${d.business_name}`, lead_ids: [id] } });
      setMsg(r.queued ? "Queued. The call is placed within a minute if calling is ready and the market is in its calling hours. Watch Follow-up Queue and Call Logs." : `Not queued: ${Object.keys(r.skipped).join(", ")}`);
    } catch (e) { setMsg(e.message); }
  }
  if (!d) return <p>{msg || "Loading"}</p>;
  const a = d.analysis, c = a?.checks || {}, ct = a?.contact || {};
  const yn = (v, yes, no) => <span className={`chip ${v ? "on" : "off"}`}>{v ? yes : no}</span>;
  return (
    <div>
      {msg && <p className="msg">{msg}</p>}
      <div className="row" style={{ marginBottom: 8 }}>
        <button className="btn gold" onClick={callNow}>Call this lead now</button>
        {d.website && <button className="btn line" onClick={again}>{a ? "Run analysis again" : "Analyze website"}</button>}
      </div>
      {!a ? <p>This lead has not been analyzed yet.{!d.website && " Add a website to analyze it."}</p>
        : a.report ? <FitReport d={d} say={setMsg} />
        : <p className="msg">This lead was scored with the older method, which could not show its evidence. Press Run analysis again to get the new, checkable score.</p>}
      {a?.report && Object.keys(c).length > 0 && <><h3>What the program measured</h3><div>
        {yn(c.https, "Secure (HTTPS)", "Not secure")}{yn(c.mobile_viewport, "Mobile layout set", "No mobile layout")}{yn(c.contact_form, "Contact form found", "No contact form")}
        <span className="chip">{c.booking_found ? "Booking wording found" : "No booking wording found"}</span>
        <span className="chip">{c.chat_or_whatsapp ? "Chat or WhatsApp found" : "No chat or WhatsApp found"}</span>
        <span className="chip">{c.app_links ? "App store links found" : "No app store links"}</span>
        {c.cms && <span className="chip">Platform: {c.cms}</span>}
        {c.response_ms != null && <span className="chip">Home page: {(c.response_ms / 1000).toFixed(1)} s from this computer</span>}
        <span className="chip">{c.pages_read} pages read</span></div></>}
      {(ct.emails?.length > 0 || ct.phones?.length > 0) && <p><b>Found on the site:</b> {[...(ct.emails || []), ...(ct.phones || [])].join(", ")}</p>}
      <h3>Call history</h3>
      {d.calls?.length ? <div className="scroll"><table className="tbl"><thead><tr><th>When</th><th>Type</th><th className="num">Seconds</th><th>Outcome</th><th>Summary</th></tr></thead>
        <tbody>{d.calls.map((c) => <tr key={c.id}><td>{when(c.created_at)}</td><td>{c.kind}{c.attempt ? ` ${c.attempt}` : ""}</td><td className="num">{c.duration_s}</td><td>{c.outcome_label || c.status}</td><td>{c.summary}</td></tr>)}</tbody></table></div>
        : <p>No calls yet.</p>}
    </div>
  );
}

export default function Leads() {
  const [data, setData] = useState({ leads: [], statuses: [], total: 0, demo_count: 0 });
  const [markets, setMarkets] = useState([]);
  const [f, setF] = useState({ q: "", market: "", status: "" });
  const [form, setForm] = useState(blank);
  const [open, setOpen] = useState(false);
  const [openId, setOpenId] = useState(null);
  const [sel, setSel] = useState(new Set());
  const [bulk, setBulk] = useState({ status: "", tag: "" });
  const [note, setNote] = useState({ kind: "", text: "" });

  useEffect(() => { const p = new URLSearchParams(window.location.search); setF({ q: p.get("q") || "", market: p.get("market") || "", status: p.get("status") || "" }); }, []);
  const load = useCallback(() => {
    const qs = new URLSearchParams(Object.entries(f).filter(([, v]) => v)).toString();
    api(`/api/leads?${qs}`).then(setData).catch((e) => setNote({ kind: "err", text: e.message }));
  }, [f]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { api("/api/markets").then(setMarkets).catch(() => {}); }, []);

  async function run(fn, okText) {
    setNote({ kind: "", text: "" });
    try { await fn(); setNote({ kind: "ok", text: okText }); load(); } catch (e) { setNote({ kind: "err", text: e.message }); }
  }
  const ids = [...sel];
  const doBulk = (action, value, okText) => run(async () => { await api("/api/leads/bulk", { method: "POST", body: { ids, action, value } }); setSel(new Set()); }, okText);
  const toggle = (id) => { const n = new Set(sel); n.has(id) ? n.delete(id) : n.add(id); setSel(n); };
  const allOn = data.leads.length > 0 && data.leads.every((l) => sel.has(l.id));
  const add = (e) => { e.preventDefault(); run(async () => { await api("/api/leads", { method: "POST", body: form }); setForm(blank); setOpen(false); }, "Lead added."); };
  const mname = (c) => (markets.find((m) => m.code === c) || {}).name || c || "";
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  return (
    <>
      <header className="top">
        <h1>Leads</h1>
        <button className="btn gold" onClick={() => setOpen(!open)}>{open ? "Close form" : "Add lead"}</button>
        <a className="btn line" href="/leads/import" style={{ textDecoration: "none" }}>Import from CSV or Excel</a>
        <button className="btn line" onClick={() => download("/api/reports/leads.csv", "leads.csv").catch((e) => setNote({ kind: "err", text: e.message }))}>Export CSV</button>
        {data.demo_count === 0
          ? <button className="btn line" onClick={() => run(() => api("/api/leads/demo", { method: "POST" }), "Sample leads loaded.")}>Load sample leads</button>
          : <button className="btn line" onClick={() => run(() => api("/api/leads/demo", { method: "DELETE" }), "Sample leads removed.")}>Remove sample leads</button>}
      </header>
      <div className="page">
        {note.text && <p className={`msg ${note.kind}`} role="status">{note.text}</p>}
        {open && (
          <form className="panel" onSubmit={add}><h2>New lead</h2>
            <div className="row">
              <div className="field" style={{ flex: "2 1 240px" }}><label htmlFor="bn">Business name</label><input id="bn" value={form.business_name} onChange={set("business_name")} required /></div>
              <div className="field" style={{ flex: "1 1 180px" }}><label htmlFor="cn">Contact person</label><input id="cn" value={form.contact_name} onChange={set("contact_name")} /></div>
              <div className="field" style={{ flex: "1 1 180px" }}><label htmlFor="ph">Phone</label><input id="ph" placeholder="+971500000000" value={form.phone} onChange={set("phone")} /></div>
            </div>
            <div className="row">
              <div className="field" style={{ flex: "1 1 220px" }}><label htmlFor="wb">Website</label><input id="wb" value={form.website} onChange={set("website")} /></div>
              <div className="field" style={{ flex: "1 1 200px" }}><label htmlFor="em">Email</label><input id="em" type="email" value={form.email} onChange={set("email")} /></div>
              <div className="field" style={{ flex: "1 1 140px" }}><label htmlFor="ct">City</label><input id="ct" value={form.city} onChange={set("city")} /></div>
              <div className="field" style={{ flex: "1 1 200px" }}><label htmlFor="mk">Market</label>
                <select id="mk" value={form.market_code} onChange={set("market_code")}><option value="">Choose a market</option>{markets.map((m) => <option key={m.code} value={m.code}>{m.name}</option>)}</select></div>
              <div className="field" style={{ flex: "1 1 160px" }}><label htmlFor="in">Industry</label><input id="in" value={form.industry} onChange={set("industry")} /></div>
            </div>
            <button className="btn">Save lead</button>
          </form>
        )}

        <section className="panel">
          <div className="row" style={{ marginBottom: 14 }}>
            <div className="field" style={{ flex: "2 1 220px", margin: 0 }}><label htmlFor="q">Search</label><input id="q" placeholder="Business, phone or city" value={f.q} onChange={(e) => setF({ ...f, q: e.target.value })} /></div>
            <div className="field" style={{ flex: "1 1 200px", margin: 0 }}><label htmlFor="fm">Market</label>
              <select id="fm" value={f.market} onChange={(e) => setF({ ...f, market: e.target.value })}><option value="">All markets</option>{markets.map((m) => <option key={m.code} value={m.code}>{m.name}</option>)}</select></div>
            <div className="field" style={{ flex: "1 1 180px", margin: 0 }}><label htmlFor="fs">Status</label>
              <select id="fs" value={f.status} onChange={(e) => setF({ ...f, status: e.target.value })}><option value="">All statuses</option>{data.statuses.map((s) => <option key={s}>{s}</option>)}</select></div>
          </div>

          {ids.length > 0 && (
            <div className="bar-actions" role="region" aria-label="Bulk actions">
              <b>{ids.length} selected</b>
              <select aria-label="New status" value={bulk.status} onChange={(e) => setBulk({ ...bulk, status: e.target.value })}><option value="">Change status to</option>{data.statuses.map((s) => <option key={s}>{s}</option>)}</select>
              <button className="btn gold" disabled={!bulk.status} onClick={() => doBulk("status", bulk.status, "Status changed.")}>Apply</button>
              <input aria-label="Tag" placeholder="Add a tag" value={bulk.tag} onChange={(e) => setBulk({ ...bulk, tag: e.target.value })} style={{ width: 140 }} />
              <button className="btn gold" disabled={!bulk.tag} onClick={() => doBulk("tag", bulk.tag, "Tag added.")}>Tag</button>
              <button className="btn gold" onClick={() => doBulk("analyze", "", "Analysis started. Follow it in Lead Discovery.")}>Re-analyze</button>
              <button className="btn gold" onClick={() => { localStorage.setItem("campaignLeads", JSON.stringify(ids)); window.location.href = "/campaigns"; }}>Plan calls</button>
              <button className="btn" style={{ borderColor: "var(--gold)" }} onClick={() => window.confirm(`Delete ${ids.length} leads? This cannot be undone.`) && doBulk("delete", "", "Leads deleted.")}>Delete</button>
            </div>
          )}

          {data.leads.length === 0 ? (
            <p className="msg">{data.total === 0 ? "No leads yet. Add a lead, import a list, or use Lead Discovery to find businesses." : "No leads match these filters."}</p>
          ) : (
            <div className="scroll"><table className="tbl">
              <thead><tr><th><input type="checkbox" aria-label="Select all" checked={allOn} onChange={() => setSel(allOn ? new Set() : new Set(data.leads.map((l) => l.id)))} /></th><th>Business</th><th>Market</th><th>Pain point and solution</th><th className="num">Fit</th><th>Status</th><th>Source</th></tr></thead>
              <tbody>{data.leads.map((l) => (
                <Fragment key={l.id}>
                  <tr>
                    <td><input type="checkbox" aria-label={`Select ${l.business_name}`} checked={sel.has(l.id)} onChange={() => toggle(l.id)} /></td>
                    <td><button className="linklike" aria-expanded={openId === l.id} onClick={() => setOpenId(openId === l.id ? null : l.id)}>{l.business_name}</button>
                      <br /><span style={{ color: "var(--mute)" }}>{l.city}{l.phone ? `, ${l.phone}` : ""}</span>
                      {l.tags && <div>{l.tags.split(",").map((t) => <span className="chip" key={t}>{t}</span>)}</div>}</td>
                    <td>{mname(l.market_code)}</td>
                    <td>{l.pain_point || "Not analyzed yet"}{l.hy_solution && <><br /><span style={{ color: "var(--mute)" }}>{l.hy_solution}</span></>}</td>
                    <td className="num"><span className="score">{l.fit_score ?? "-"}</span>{l.fit_band && <div><span className={`tag ${BAND_CLASS[l.fit_band]}`}>{bandText(l.fit_band)}</span><div style={{ color: "var(--mute)", fontSize: 12 }}>{l.fit_conf} confidence</div></div>}</td>
                    <td><select aria-label={`Status for ${l.business_name}`} value={l.status} onChange={(e) => run(() => api(`/api/leads/${l.id}/status`, { method: "PUT", body: { status: e.target.value } }), "Status updated.")}>
                      {data.statuses.map((s) => <option key={s}>{s}</option>)}</select>
                      <div style={{ marginTop: 4 }}><span className={`tag ${cls(l.status)}`}>{l.status}</span></div></td>
                    <td>{l.source}</td>
                  </tr>
                  {openId === l.id && <tr className="detail"><td colSpan={7}><LeadDetail id={l.id} /></td></tr>}
                </Fragment>))}</tbody>
            </table></div>
          )}
        </section>
      </div>
    </>
  );
}
