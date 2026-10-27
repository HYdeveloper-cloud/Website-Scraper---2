"use client";
import { useCallback, useEffect, useState } from "react";
import { api } from "../../../lib/api";

const RUN_CLASS = { done: "st-won", running: "st-contacted", error: "st-lost", interrupted: "st-lost" };
const RUN_LABEL = { done: "Finished", running: "Running", error: "Failed", interrupted: "Interrupted" };

function describe(r) {
  const p = r.params || {};
  if (r.mode === "link") { try { return `Link: ${new URL(p.url).host}`; } catch { return "Link"; } }
  if (r.mode === "analyze") return `Re-analysis: ${p.business || "lead"}`;
  return `Auto-find: ${p.niche} in ${p.city} (${p.market_code}), up to ${p.limit}`;
}

export default function Discovery() {
  const [markets, setMarkets] = useState([]);
  const [st, setSt] = useState(null);
  const [runs, setRuns] = useState([]);
  const [link, setLink] = useState({ url: "", market_code: "" });
  const [auto, setAuto] = useState({ niche: "", city: "", market_code: "", limit: 20, min_rating: 0, min_fit: 0, require_website: false });
  const [note, setNote] = useState({ kind: "", text: "" });

  const loadRuns = useCallback(() => api("/api/discovery/runs").then(setRuns).catch(() => {}), []);
  useEffect(() => { api("/api/markets").then(setMarkets).catch(() => {}); api("/api/status").then(setSt).catch(() => {}); loadRuns(); }, [loadRuns]);
  const running = runs.some((r) => r.status === "running");
  useEffect(() => { if (!running) return; const t = setInterval(loadRuns, 2000); return () => clearInterval(t); }, [running, loadRuns]);

  async function start(path, body, resetFn) {
    setNote({ kind: "", text: "" });
    try {
      await api(path, { method: "POST", body });
      setNote({ kind: "ok", text: "Started. Progress appears under Discovery runs below." });
      resetFn && resetFn(); loadRuns();
    } catch (e) { setNote({ kind: "err", text: e.message }); }
  }

  const chip = (ok, label) => <span className={`chip ${ok ? "on" : "off"}`}>{label}: {ok ? "ready" : "not set"}</span>;
  const mkOpts = markets.map((m) => <option key={m.code} value={m.code}>{m.name}</option>);

  return (
    <>
      <header className="top"><h1>Lead Discovery</h1></header>
      <div className="page">
        {st && <p>{chip(st.llm_configured, "Language model key")}{chip(st.places_configured, "Google Places key")}
          {(!st.llm_configured || !st.places_configured) && <span className="hint"> Add the missing keys in Settings, Integrations.</span>}</p>}
        {note.text && <p className={`msg ${note.kind}`} role="status">{note.text}</p>}

        <div className="grid2" style={{ gridTemplateColumns: "1fr 1fr" }}>
          <form className="panel" onSubmit={(e) => { e.preventDefault(); start("/api/discovery/link", link, () => setLink({ ...link, url: "" })); }}>
            <h2>Find by link</h2>
            <p>Paste one business website. The system reads its pages, checks the site, and works out which problems HY Developer can solve.</p>
            <div className="field"><label htmlFor="lu">Website address</label><input id="lu" placeholder="example.com" value={link.url} onChange={(e) => setLink({ ...link, url: e.target.value })} required /></div>
            <div className="field"><label htmlFor="lm">Market (optional)</label>
              <select id="lm" value={link.market_code} onChange={(e) => setLink({ ...link, market_code: e.target.value })}><option value="">Not set</option>{mkOpts}</select></div>
            <button className="btn" disabled={!st?.llm_configured}>Analyze website</button>
          </form>

          <form className="panel" onSubmit={(e) => { e.preventDefault(); start("/api/discovery/auto", { ...auto, limit: +auto.limit, min_rating: +auto.min_rating, min_fit: +auto.min_fit }); }}>
            <h2>Auto-find businesses</h2>
            <p>Search Google for a type of business in a city. Each result is checked and scored.</p>
            <div className="row">
              <div className="field" style={{ flex: "1 1 160px" }}><label htmlFor="an">Type of business</label><input id="an" placeholder="dental clinics" value={auto.niche} onChange={(e) => setAuto({ ...auto, niche: e.target.value })} required minLength={2} /></div>
              <div className="field" style={{ flex: "1 1 120px" }}><label htmlFor="ac">City</label><input id="ac" placeholder="Dubai" value={auto.city} onChange={(e) => setAuto({ ...auto, city: e.target.value })} required minLength={2} /></div>
              <div className="field" style={{ flex: "1 1 160px" }}><label htmlFor="am">Market</label>
                <select id="am" value={auto.market_code} onChange={(e) => setAuto({ ...auto, market_code: e.target.value })} required><option value="">Choose</option>{mkOpts}</select></div>
            </div>
            <div className="row">
              <div className="field" style={{ flex: "1 1 110px" }}><label htmlFor="al">How many (1 to 60)</label><input id="al" type="number" min={1} max={60} value={auto.limit} onChange={(e) => setAuto({ ...auto, limit: e.target.value })} /></div>
              <div className="field" style={{ flex: "1 1 130px" }}><label htmlFor="ar">Minimum Google rating</label>
                <select id="ar" value={auto.min_rating} onChange={(e) => setAuto({ ...auto, min_rating: e.target.value })}><option value={0}>Any</option><option value={3.5}>3.5</option><option value={4}>4.0</option><option value={4.5}>4.5</option></select></div>
              <div className="field" style={{ flex: "1 1 130px" }}><label htmlFor="af">Keep only fit score of</label><input id="af" type="number" min={0} max={100} value={auto.min_fit} onChange={(e) => setAuto({ ...auto, min_fit: e.target.value })} /></div>
            </div>
            <div className="field"><label><input type="checkbox" checked={auto.require_website} onChange={(e) => setAuto({ ...auto, require_website: e.target.checked })} style={{ width: "auto", marginRight: 8 }} />Only businesses that have a website</label>
              <span className="hint">Leave this off to also find businesses with no website. They score high because that is a clear gap.</span></div>
            <button className="btn" disabled={!st?.llm_configured || !st?.places_configured}>Find businesses</button>
            <p className="hint" style={{ marginBottom: 0 }}>Google bills searches that return phone numbers and websites, and each lead uses one language model call. Start with 10 to 20 to see the cost.</p>
          </form>
        </div>

        <section className="panel">
          <h2>Discovery runs</h2>
          {runs.length === 0 ? <p className="msg">No runs yet. Start one above, then review the results in Leads.</p> : (
            <div className="scroll"><table className="tbl runs">
              <thead><tr><th>Started</th><th>What</th><th>Status</th><th className="num">Found</th><th className="num">Added</th><th className="num">Updated</th><th className="num">Skipped</th><th className="num">Filtered</th><th className="num">Failed</th><th>Progress</th></tr></thead>
              <tbody>{runs.map((r) => (
                <tr key={r.id}>
                  <td>{new Date(r.created_at + "Z").toLocaleString()}</td><td>{describe(r)}</td>
                  <td><span className={`tag ${RUN_CLASS[r.status]}`}>{RUN_LABEL[r.status]}</span></td>
                  <td className="num">{r.found}</td><td className="num">{r.added}</td><td className="num">{r.updated}</td>
                  <td className="num">{r.skipped}</td><td className="num">{r.filtered}</td><td className="num">{r.failed}</td>
                  <td>{r.note}{r.errors.length > 0 && <details><summary>{r.errors.length} problem{r.errors.length > 1 ? "s" : ""}</summary><ul>{r.errors.map((e, i) => <li key={i}>{e}</li>)}</ul></details>}</td>
                </tr>))}</tbody>
            </table></div>
          )}
          <p className="hint">Skipped means the business was already in Leads. Filtered means it did not meet your rating, website or fit score limits.</p>
        </section>
      </div>
    </>
  );
}
