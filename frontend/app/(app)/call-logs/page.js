"use client";
import { Fragment, useEffect, useState } from "react";
import { api, download, when } from "../../../lib/api";

const OUT = [["", "All outcomes"], ["meeting_booked", "Meeting booked"], ["interested", "Interested"], ["callback_requested", "Callback requested"], ["not_interested", "Not interested"],
  ["do_not_call", "Do Not Call"], ["wrong_number", "Wrong number"], ["connected", "Connected, no clear result"], ["short_call", "Short call"], ["no_answer", "No answer"], ["voicemail", "Voicemail"]];

function Detail({ id, reload }) {
  const [d, setD] = useState(null);
  const [o, setO] = useState("");
  const [msg, setMsg] = useState("");
  useEffect(() => { api(`/api/calls/${id}`).then((x) => { setD(x); setO(x.outcome || ""); }).catch((e) => setMsg(e.message)); }, [id]);
  async function save() { try { await api(`/api/calls/${id}/outcome`, { method: "PUT", body: { outcome: o } }); setMsg("Outcome changed. The lead's status and follow-ups were updated to match."); reload(); } catch (e) { setMsg(e.message); } }
  if (!d) return <p>{msg || "Loading"}</p>;
  return (
    <div>
      {msg && <p className="msg">{msg}</p>}
      <div className="kv2"><b>Number</b><span>{d.to_number}</span><b>Language</b><span>{d.language}</span><b>Ended because</b><span>{d.reason || "Not reported"}</span>
        <b>Summary</b><span>{d.summary || "None yet"}{d.meeting_when && ` Meeting: ${d.meeting_when}.`}</span>
        <b>Recording</b><span>{d.recording_url ? <a href={d.recording_url} target="_blank" rel="noreferrer">Open the recording</a> : "None"}</span></div>
      <h3>Transcript</h3><div className="transcript">{d.transcript || "No transcript."}</div>
      <div className="row" style={{ marginTop: 12 }}>
        <div className="field" style={{ margin: 0 }}><label htmlFor="oc">If the result was read wrongly, set it yourself</label>
          <select id="oc" value={o} onChange={(e) => setO(e.target.value)}>{OUT.filter(([k]) => k).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></div>
        <button className="btn" onClick={save} disabled={!o || o === d.outcome}>Change outcome</button>
      </div>
    </div>
  );
}

export default function CallLogs() {
  const [rows, setRows] = useState([]);
  const [out, setOut] = useState("");
  const [open, setOpen] = useState(null);
  const load = () => api(`/api/calls?outcome=${out}`).then(setRows).catch(() => {});
  useEffect(() => { load(); const t = setInterval(load, 15000); return () => clearInterval(t); }, [out]);
  return (
    <>
      <header className="top"><h1>Call Logs</h1>
        <button className="btn line" onClick={() => download("/api/reports/calls.csv", "calls.csv")}>Export CSV</button></header>
      <div className="page">
        <div className="field" style={{ maxWidth: 280 }}><label htmlFor="fo">Outcome</label>
          <select id="fo" value={out} onChange={(e) => setOut(e.target.value)}>{OUT.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></div>
        <section className="panel">
          {rows.length === 0 ? <p className="msg">No calls yet. Plan calls in Campaigns and Calling.</p> : (
            <div className="scroll"><table className="tbl"><thead><tr><th>When</th><th>Business</th><th>Type</th><th className="num">Seconds</th><th>Outcome</th></tr></thead>
              <tbody>{rows.map((c) => (
                <Fragment key={c.id}>
                  <tr><td>{when(c.created_at)}</td><td><button className="linklike" aria-expanded={open === c.id} onClick={() => setOpen(open === c.id ? null : c.id)}>{c.business}</button><br /><span style={{ color: "var(--mute)" }}>{c.to_number}</span></td>
                    <td>{c.kind}{c.attempt ? ` ${c.attempt}` : ""}</td><td className="num">{c.duration_s}</td><td>{c.status === "ended" || c.status === "error" ? (c.outcome_label || "Not classified") : <em>{c.status}</em>}</td></tr>
                  {open === c.id && <tr className="detail"><td colSpan={5}><Detail id={c.id} reload={load} /></td></tr>}
                </Fragment>))}</tbody></table></div>
          )}
        </section>
      </div>
    </>
  );
}
