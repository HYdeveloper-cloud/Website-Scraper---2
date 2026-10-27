"use client";
import { useEffect, useState } from "react";
import { API, api, getToken } from "../../../../lib/api";

const FIELDS = [["business_name", "Business name (required)"], ["phone", "Phone"], ["website", "Website"], ["contact_name", "Contact person"],
  ["email", "Email"], ["city", "City"], ["market", "Country or market"], ["industry", "Industry"], ["notes", "Notes"]];

export default function ImportLeads() {
  const [markets, setMarkets] = useState([]);
  const [pv, setPv] = useState(null);
  const [map, setMap] = useState({});
  const [dm, setDm] = useState("");
  const [analyze, setAnalyze] = useState(false);
  const [res, setRes] = useState(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api("/api/markets").then(setMarkets).catch(() => {});
    api("/api/settings").then((s) => { setDm(s.leads?.default_market || ""); setAnalyze(!!s.leads?.analyze_uploads); }).catch(() => {});
  }, []);

  async function choose(e) {
    const file = e.target.files[0];
    if (!file) return;
    setErr(""); setRes(null); setBusy(true);
    const fd = new FormData(); fd.append("file", file);
    try {
      const r = await fetch(`${API}/api/leads/upload/preview`, { method: "POST", headers: { Authorization: `Bearer ${getToken()}` }, body: fd });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || "That file could not be read.");
      setPv(d); setMap(d.suggested);
    } catch (x) { setErr(x.message); setPv(null); }
    setBusy(false);
  }

  async function doImport() {
    setErr(""); setBusy(true);
    try { setRes(await api("/api/leads/upload/import", { method: "POST", body: { upload_id: pv.upload_id, mapping: map, default_market: dm, analyze } })); setPv(null); }
    catch (x) { setErr(x.message); }
    setBusy(false);
  }

  return (
    <>
      <header className="top"><h1>Import leads</h1><a className="btn line" href="/leads" style={{ textDecoration: "none" }}>Back to Leads</a></header>
      <div className="page">
        {err && <p className="msg err" role="alert">{err}</p>}

        {!res && (
          <section className="panel"><h2>1. Choose your file</h2>
            <p>A CSV or Excel (.xlsx) file with one lead per row and a header row on top. Up to 5,000 rows and 5 MB.</p>
            <div className="field"><label htmlFor="f">File</label><input id="f" type="file" accept=".csv,.txt,.xlsx" onChange={choose} disabled={busy} /></div>
          </section>
        )}

        {pv && !res && (
          <>
            <section className="panel"><h2>2. Match your columns</h2>
              <p>{pv.total} rows found. Check that each field points at the right column. Numbers without a country code are read using the lead's market.</p>
              <div className="row">{FIELDS.map(([k, label]) => (
                <div className="field" key={k} style={{ flex: "1 1 220px" }}><label htmlFor={`m-${k}`}>{label}</label>
                  <select id={`m-${k}`} value={map[k] || ""} onChange={(e) => setMap({ ...map, [k]: e.target.value })}><option value="">Not in my file</option>{pv.columns.map((c) => <option key={c}>{c}</option>)}</select></div>))}</div>
              <div className="row">
                <div className="field" style={{ flex: "1 1 260px" }}><label htmlFor="dm">Market when the file does not say</label>
                  <select id="dm" value={dm} onChange={(e) => setDm(e.target.value)}><option value="">Work it out from the phone number</option>{markets.map((m) => <option key={m.code} value={m.code}>{m.name}</option>)}</select></div>
                <div className="field" style={{ flex: "1 1 260px" }}><label><input type="checkbox" checked={analyze} onChange={(e) => setAnalyze(e.target.checked)} style={{ width: "auto", marginRight: 8 }} />Analyze websites after import (up to 100)</label>
                  <span className="hint">Finds the problems HY Developer can solve. Uses your language model key.</span></div>
              </div>
              <h3>First rows of your file</h3>
              <div className="scroll"><table className="tbl"><thead><tr>{pv.columns.map((c) => <th key={c}>{c}</th>)}</tr></thead>
                <tbody>{pv.rows.map((r, i) => <tr key={i}>{pv.columns.map((c) => <td key={c}>{r[c]}</td>)}</tr>)}</tbody></table></div>
              <p><button className="btn" onClick={doImport} disabled={busy || !map.business_name}>{busy ? "Importing" : `Import ${pv.total} rows`}</button></p>
            </section>
          </>
        )}

        {res && (
          <section className="panel"><h2>3. Import finished</h2>
            <div className="tiles" style={{ gridTemplateColumns: "repeat(4,1fr)" }}>
              {[["Added", res.added], ["Duplicates skipped", res.duplicates], ["Invalid rows", res.invalid], ["On Do Not Call", res.do_not_call]].map(([l, n]) => <div className="tile" key={l}><div className="n">{n}</div><div className="l">{l}</div></div>)}
            </div>
            {res.analysis_note && <p className="msg">{res.analysis_note}</p>}
            {res.analysis_run && <p className="msg ok">Website analysis is running. Follow it in Lead Discovery.</p>}
            {res.problems.length > 0 && <><h3>Rows that were not added</h3>
              <div className="scroll"><table className="tbl"><thead><tr><th>Row</th><th>Business</th><th>Why</th></tr></thead>
                <tbody>{res.problems.map((p, i) => <tr key={i}><td>{p.row}</td><td>{p.business}</td><td>{p.reason}</td></tr>)}</tbody></table></div></>}
            <p><a className="btn" href="/leads" style={{ textDecoration: "none" }}>See your leads</a> <button className="btn line" onClick={() => { setRes(null); setPv(null); }}>Import another file</button></p>
          </section>
        )}
      </div>
    </>
  );
}
