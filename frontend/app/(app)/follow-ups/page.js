"use client";
import { useCallback, useEffect, useState } from "react";
import { api, when } from "../../../lib/api";

const TABS = [["pending", "Waiting"], ["blocked", "Blocked"], ["done", "Called"], ["cancelled", "Cancelled"]];

export default function FollowUps() {
  const [tab, setTab] = useState("pending");
  const [rows, setRows] = useState([]);
  const [n, setN] = useState(3);
  const [resched, setResched] = useState({});
  const [note, setNote] = useState({ kind: "", text: "" });

  const load = useCallback(() => api(`/api/tasks?status=${tab}`).then(setRows).catch((e) => setNote({ kind: "err", text: e.message })), [tab]);
  useEffect(() => { load(); const t = setInterval(load, 15000); return () => clearInterval(t); }, [load]);
  useEffect(() => { api("/api/settings").then((s) => setN(s.calling?.followup_count ?? 3)).catch(() => {}); }, []);

  async function act(id, what, body) {
    setNote({ kind: "", text: "" });
    try { await api(`/api/tasks/${id}/${what}`, { method: "POST", body }); setResched({}); load(); } catch (e) { setNote({ kind: "err", text: e.message }); }
  }
  const label = (t) => (t.kind === "first" ? "First call" : t.kind === "callback" ? "Callback" : `Follow-up ${t.attempt} of ${n}`);

  return (
    <>
      <header className="top"><h1>Follow-up Queue</h1></header>
      <div className="page">
        <p>Calls under the short-call limit, unanswered calls and voicemails get up to {n} follow-ups, one per gap set in Calling Rules (24 hours by default). Follow-ups stop as soon as the lead engages, declines or asks not to be called.</p>
        {note.text && <p className={`msg ${note.kind}`} role="alert">{note.text}</p>}
        <div className="pills" role="tablist">{TABS.map(([k, l]) => <button key={k} className={tab === k ? "on" : ""} onClick={() => setTab(k)}>{l}</button>)}</div>
        <section className="panel">
          {rows.length === 0 ? <p className="msg">Nothing here.</p> : (
            <div className="scroll"><table className="tbl"><thead><tr><th>Business</th><th>Market</th><th>Type</th><th>Due</th><th>Note</th><th>Actions</th></tr></thead>
              <tbody>{rows.map((t) => (
                <tr key={t.id}><td><b>{t.business}</b><br /><span style={{ color: "var(--mute)" }}>{t.phone}</span></td><td>{t.market}</td><td>{label(t)}</td><td>{when(t.due_at)}</td><td>{t.note}{t.campaign && <><br /><span style={{ color: "var(--mute)" }}>{t.campaign}</span></>}</td>
                  <td>{(tab === "pending" || tab === "blocked") && <>
                    <button className="btn gold" onClick={() => act(t.id, "now")}>Call now</button>{" "}
                    {resched.id === t.id ? <><input type="datetime-local" aria-label="New time" onChange={(e) => setResched({ id: t.id, at: e.target.value })} style={{ width: "auto" }} /> <button className="btn" disabled={!resched.at} onClick={() => act(t.id, "reschedule", { start_at: resched.at })}>Save</button></>
                      : <button className="btn line" onClick={() => setResched({ id: t.id })}>Reschedule</button>}{" "}
                    {tab === "pending" && <button className="btn line" onClick={() => act(t.id, "cancel")}>Cancel</button>}</>}</td></tr>))}</tbody></table></div>
          )}
        </section>
      </div>
    </>
  );
}
