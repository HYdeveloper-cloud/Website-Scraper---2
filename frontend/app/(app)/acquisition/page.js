"use client";
import { useEffect, useState } from "react";
import { api } from "../../../lib/api";
import { Bars, HBars } from "../../../components/charts";

export default function Acquisition() {
  const [a, setA] = useState(null);
  const [leads, setLeads] = useState([]);
  const [cur, setCur] = useState("USD");
  const [nd, setNd] = useState({ lead_id: "", value: "" });
  const [note, setNote] = useState({ kind: "", text: "" });

  const load = () => api("/api/acquisition").then(setA).catch((e) => setNote({ kind: "err", text: e.message }));
  useEffect(() => {
    load();
    api("/api/leads").then((d) => setLeads(d.leads.filter((l) => l.source !== "demo"))).catch(() => {});
    api("/api/settings").then((s) => s.general && setCur(s.general.currency)).catch(() => {});
  }, []);
  const money = (n) => new Intl.NumberFormat("en-US", { style: "currency", currency: cur, maximumFractionDigits: 0 }).format(n || 0);

  async function call(fn, ok) { setNote({ kind: "", text: "" }); try { await fn(); if (ok) setNote({ kind: "ok", text: ok }); load(); } catch (e) { setNote({ kind: "err", text: e.message }); } }
  const add = (e) => { e.preventDefault(); call(async () => { await api("/api/deals", { method: "POST", body: { lead_id: +nd.lead_id, value: +nd.value || 0 } }); setNd({ lead_id: "", value: "" }); }, "Deal added."); };
  function move(d, stage) {
    const body = { stage };
    if (stage === "Won") { const v = window.prompt(`Final value of the deal with ${d.business} (${cur})`, d.value || ""); if (!v) return; body.final_value = +v; }
    if (stage === "Lost") { const r = window.prompt(`Why was the deal with ${d.business} lost?`); if (!r) return; body.lost_reason = r; }
    call(() => api(`/api/deals/${d.id}`, { method: "PUT", body }));
  }
  function editValue(d) { const v = window.prompt(`Expected value for ${d.business} (${cur})`, d.value || 0); if (v !== null && v !== "") call(() => api(`/api/deals/${d.id}`, { method: "PUT", body: { value: +v } })); }

  if (!a) return <div className="page">{note.text ? <p className="msg err">{note.text}</p> : "Loading"}</div>;
  const m = a.metrics, open = new Set(a.deals.filter((d) => d.stage !== "Won" && d.stage !== "Lost").map((d) => d.lead_id));
  const tiles = [["Revenue", money(m.revenue)], ["This month", money(m.revenue_this_month)], ["Deals won", m.deals_won], ["Win rate", `${m.win_rate}%`],
    ["Proposals submitted", m.proposals], ["Average deal", money(m.avg_deal)], ["Days to close", m.avg_cycle_days], ["Call cost per client", m.cost_per_client == null ? "Not yet" : money(m.cost_per_client)]];

  return (
    <>
      <header className="top"><h1>Client Acquisition</h1></header>
      <div className="page">
        {note.text && <p className={`msg ${note.kind}`} role="status">{note.text}</p>}
        <section className="tiles" style={{ gridTemplateColumns: "repeat(4,1fr)" }}>{tiles.map(([l, n]) => <div className="tile" key={l}><div className="n" style={{ fontSize: 28 }}>{n}</div><div className="l">{l}</div></div>)}</section>
        {a.target > 0 && <p className="msg">Monthly target: {money(a.target)}. This month so far: {money(m.revenue_this_month)} ({m.target_progress}%).</p>}

        <form className="panel" onSubmit={add}><h2>New deal</h2>
          <div className="row">
            <div className="field" style={{ flex: "2 1 260px", margin: 0 }}><label htmlFor="dl">Lead</label>
              <select id="dl" value={nd.lead_id} onChange={(e) => setNd({ ...nd, lead_id: e.target.value })} required><option value="">Choose a lead</option>
                {leads.filter((l) => !open.has(l.id)).map((l) => <option key={l.id} value={l.id}>{l.business_name}{l.city ? `, ${l.city}` : ""}</option>)}</select></div>
            <div className="field" style={{ flex: "1 1 160px", margin: 0 }}><label htmlFor="dv">Expected value ({cur})</label><input id="dv" type="number" min={0} value={nd.value} onChange={(e) => setNd({ ...nd, value: e.target.value })} /></div>
            <button className="btn">Add deal</button>
          </div>
          <p className="hint" style={{ marginBottom: 0 }}>A deal is added automatically when a call ends in a booked meeting.</p>
        </form>

        <section className="panel"><h2>Pipeline</h2>
          <div className="board">{a.stages.map((st) => {
            const cards = a.deals.filter((d) => d.stage === st);
            return (<div className="col" key={st}><h3>{st} ({cards.length})</h3>
              {cards.map((d) => (<div className="card" key={d.id}><b>{d.business}</b><br />{d.service || "No service set"}<br />{money(d.final_value ?? d.value)}
                {d.lost_reason && <><br /><span style={{ color: "var(--bad)" }}>{d.lost_reason}</span></>}
                {st !== "Won" && st !== "Lost" && <button className="linklike" style={{ display: "block", marginTop: 4 }} onClick={() => editValue(d)}>Edit value</button>}
                <select aria-label={`Move ${d.business}`} value={st} onChange={(e) => move(d, e.target.value)}>{a.stages.map((x) => <option key={x}>{x}</option>)}</select></div>))}</div>);
          })}</div>
        </section>

        <div className="grid2">
          <section className="panel"><h2>Revenue by month</h2><Bars data={a.revenue_by_month.map((x) => x[1])} labels={a.revenue_by_month.map((x) => x[0].slice(2))} label="Revenue by month" fmt={(v) => (v >= 1000 ? `${Math.round(v / 100) / 10}k` : v)} /></section>
          <section className="panel"><h2>Why deals were lost</h2><HBars rows={a.lost_reasons} /></section>
        </div>
        <div className="grid2">
          <section className="panel"><h2>Revenue by service</h2><HBars gold rows={a.by_service} fmt={money} /></section>
          <section className="panel"><h2>Revenue by lead source</h2><HBars gold rows={a.by_source} fmt={money} /></section>
        </div>
      </div>
    </>
  );
}
