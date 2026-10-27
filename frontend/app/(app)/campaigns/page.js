"use client";
import { useCallback, useEffect, useState } from "react";
import { api, when } from "../../../lib/api";

const CAMP_CLASS = { active: "st-won", paused: "st-contacted", cancelled: "st-lost", completed: "st-new" };

export default function Campaigns() {
  const [st, setSt] = useState(null);
  const [markets, setMarkets] = useState([]);
  const [statuses, setStatuses] = useState([]);
  const [camps, setCamps] = useState([]);
  const [picked, setPicked] = useState([]);
  const [f, setF] = useState({ name: "", market_code: "", status: "New", min_fit: 0, limit: 50, mode: "now", start_at: "" });
  const [test, setTest] = useState({ to_number: "", language: "en-US" });
  const [note, setNote] = useState({ kind: "", text: "" });

  const load = useCallback(() => {
    api("/api/calling/status").then(setSt).catch(() => {});
    api("/api/campaigns").then(setCamps).catch(() => {});
  }, []);
  useEffect(() => {
    load();
    api("/api/markets").then(setMarkets).catch(() => {});
    api("/api/leads?limit=1").then((d) => setStatuses(d.statuses)).catch(() => {});
    try { setPicked(JSON.parse(localStorage.getItem("campaignLeads") || "[]")); } catch { setPicked([]); }
    const t = setInterval(load, 10000);
    return () => clearInterval(t);
  }, [load]);

  const say = (kind, text) => setNote({ kind, text });
  async function create(e) {
    e.preventDefault(); say("", "");
    try {
      const body = { name: f.name, lead_ids: picked, market_code: f.market_code, status: f.status, min_fit: +f.min_fit, limit: +f.limit, start_at: f.mode === "later" ? f.start_at : "" };
      const r = await api("/api/campaigns", { method: "POST", body });
      const why = Object.entries(r.skipped).map(([k, v]) => `${v} skipped: ${k}`).join(". ");
      say(r.queued ? "ok" : "err", `${r.queued} calls planned. ${why}`);
      localStorage.removeItem("campaignLeads"); setPicked([]); load();
    } catch (x) { say("err", x.message); }
  }
  async function setStatus(id, status) { try { await api(`/api/campaigns/${id}/status`, { method: "PUT", body: { status } }); load(); } catch (x) { say("err", x.message); } }
  async function testCall(e) {
    e.preventDefault(); say("", "");
    try { await api("/api/voice/test-call", { method: "POST", body: test }); say("ok", "Calling your phone now. Answer it and talk to the agent. The result appears in Call Logs."); } catch (x) { say("err", x.message); }
  }

  const ready = st && !st.paused && st.agents.length > 0;
  return (
    <>
      <header className="top"><h1>Campaigns and Calling</h1></header>
      <div className="page">
        {st && (
          <section className="panel" aria-label="Calling status">
            <h2>Calling status</h2>
            {st.paused ? <p className="msg err">Calling is paused. {st.paused}</p> : ready ? <p className="msg ok">Ready. Planned calls are placed as soon as the lead's market is in its calling hours.</p>
              : <p className="msg">Waiting for setup. Build the voice agent in Settings, Voice Agent.</p>}
            {st.error && <p className="msg err">Last problem: {st.error}</p>}
            <span className={`chip ${st.retell_configured ? "on" : "off"}`}>Retell key: {st.retell_configured ? "ready" : "not set"}</span>
            <span className={`chip ${st.numbers ? "on" : "off"}`}>Calling numbers: {st.numbers}</span>
            <span className={`chip ${st.agents.length ? "on" : "off"}`}>Voice agents built: {st.agents.join(", ") || "none"}</span>
            <span className="chip">Calls today: {st.calls_today} of {st.daily_limit}</span>
            <span className="chip">Minutes today: {st.minutes_today}</span>
            <span className="chip">On a call now: {st.active_calls}</span>
          </section>
        )}
        {note.text && <p className={`msg ${note.kind}`} role="status">{note.text}</p>}

        <div className="grid2" style={{ gridTemplateColumns: "3fr 2fr" }}>
          <form className="panel" onSubmit={create}>
            <h2>Plan calls</h2>
            <div className="field"><label htmlFor="cn">Campaign name</label><input id="cn" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} required minLength={2} /></div>
            {picked.length > 0 ? (
              <p className="msg">{picked.length} leads selected from the Leads screen. <button type="button" className="linklike" onClick={() => { localStorage.removeItem("campaignLeads"); setPicked([]); }}>Use filters instead</button></p>
            ) : (
              <div className="row">
                <div className="field" style={{ flex: "1 1 180px" }}><label htmlFor="cm">Market</label><select id="cm" value={f.market_code} onChange={(e) => setF({ ...f, market_code: e.target.value })}><option value="">All markets</option>{markets.map((m) => <option key={m.code} value={m.code}>{m.name}</option>)}</select></div>
                <div className="field" style={{ flex: "1 1 160px" }}><label htmlFor="cs">Lead status</label><select id="cs" value={f.status} onChange={(e) => setF({ ...f, status: e.target.value })}><option value="">Any</option>{statuses.map((s) => <option key={s}>{s}</option>)}</select></div>
                <div className="field" style={{ flex: "1 1 120px" }}><label htmlFor="cf">Minimum fit</label><input id="cf" type="number" min={0} max={100} value={f.min_fit} onChange={(e) => setF({ ...f, min_fit: e.target.value })} /></div>
                <div className="field" style={{ flex: "1 1 120px" }}><label htmlFor="cl">Most leads (1 to 200)</label><input id="cl" type="number" min={1} max={200} value={f.limit} onChange={(e) => setF({ ...f, limit: e.target.value })} /></div>
              </div>
            )}
            <div className="field"><label>When should calling start?</label>
              <div className="row">
                <label><input type="radio" name="mode" checked={f.mode === "now"} onChange={() => setF({ ...f, mode: "now" })} style={{ width: "auto", marginRight: 6 }} />Start now</label>
                <label><input type="radio" name="mode" checked={f.mode === "later"} onChange={() => setF({ ...f, mode: "later" })} style={{ width: "auto", marginRight: 6 }} />Schedule</label>
                {f.mode === "later" && <input type="datetime-local" aria-label="Start date and time" value={f.start_at} onChange={(e) => setF({ ...f, start_at: e.target.value })} required style={{ width: "auto" }} />}
              </div>
              <span className="hint">Times use your time zone from Settings, General. Calls are only placed inside each market's calling hours, even after Start now.</span></div>
            <button className="btn">Plan calls</button>
          </form>

          <form className="panel" onSubmit={testCall}>
            <h2>Test call to your own phone</h2>
            <p>Always do this before calling any lead. Listen to the voice, the pace and the opening line.</p>
            <div className="field"><label htmlFor="tn">Your phone number</label><input id="tn" placeholder="+923001234567" value={test.to_number} onChange={(e) => setTest({ ...test, to_number: e.target.value })} required /></div>
            <div className="field"><label htmlFor="tl">Language</label><input id="tl" value={test.language} onChange={(e) => setTest({ ...test, language: e.target.value })} /></div>
            <button className="btn gold">Call me</button>
          </form>
        </div>

        <section className="panel"><h2>Campaigns</h2>
          {camps.length === 0 ? <p className="msg">No campaigns yet.</p> : (
            <div className="scroll"><table className="tbl"><thead><tr><th>Name</th><th>Status</th><th>Starts</th><th className="num">Waiting</th><th className="num">Calls</th><th className="num">Positive</th><th>Actions</th></tr></thead>
              <tbody>{camps.map((c) => (
                <tr key={c.id}><td><b>{c.name}</b></td><td><span className={`tag ${CAMP_CLASS[c.status]}`}>{c.status}</span></td><td>{c.start_at ? when(c.start_at) : "Immediately"}</td>
                  <td className="num">{c.pending}</td><td className="num">{c.calls}</td><td className="num">{c.positive}</td>
                  <td>{c.status === "active" && <button className="btn line" onClick={() => setStatus(c.id, "paused")}>Pause</button>}
                    {c.status === "paused" && <button className="btn line" onClick={() => setStatus(c.id, "active")}>Resume</button>}
                    {c.status !== "cancelled" && <button className="btn line" onClick={() => window.confirm("Cancel this campaign and its waiting calls?") && setStatus(c.id, "cancelled")}>Cancel</button>}</td></tr>))}</tbody></table></div>
          )}
        </section>
      </div>
    </>
  );
}
