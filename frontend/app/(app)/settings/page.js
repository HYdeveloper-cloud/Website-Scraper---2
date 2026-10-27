"use client";
import { useEffect, useState } from "react";
import { api, applyTheme, when } from "../../../lib/api";

const DEFAULT_THEME = { maroon: "#330908", gold: "#C0A559", ivory: "#F7F3E8", ink: "#2A2220" };
const TABS = [["general", "General"], ["appearance", "Appearance"], ["markets", "Markets"], ["services", "Service Catalog"], ["scoring", "Lead Scoring"], ["voice", "Voice Agent"],
  ["calling", "Calling Rules"], ["leads", "Leads"], ["acq", "Acquisition"], ["integrations", "Integrations"], ["compliance", "Compliance"], ["account", "Account and Security"]];
const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function Note({ n }) { return n.text ? <p className={`msg ${n.kind}`} role="status">{n.text}</p> : null; }

/* One reusable form for the simple settings areas. */
function Form({ area, s, reload, title, intro, fields, children }) {
  const init = () => Object.fromEntries(fields.map((f) => [f.key, f.type === "lines" ? (s[area][f.key] || []).join("\n") : s[area][f.key]]));
  const [v, setV] = useState(init); const [n, setN] = useState({});
  async function save(e) {
    e.preventDefault();
    const body = Object.fromEntries(fields.map((f) => [f.key, f.type === "lines" ? String(v[f.key]).split("\n") : f.type === "number" ? Number(v[f.key]) : v[f.key]]));
    try { await api(`/api/settings/${area}`, { method: "PUT", body: { ...s[area], ...body } }); setN({ kind: "ok", text: "Saved." }); reload(); } catch (x) { setN({ kind: "err", text: x.message }); }
  }
  return (
    <form className="panel" onSubmit={save} style={{ maxWidth: 720 }}>
      <h2>{title}</h2>{intro && <p>{intro}</p>}<Note n={n} />
      {fields.map((f) => (
        <div className="field" key={f.key}>
          {f.type === "checkbox"
            ? <label><input type="checkbox" checked={!!v[f.key]} onChange={(e) => setV({ ...v, [f.key]: e.target.checked })} style={{ width: "auto", marginRight: 8 }} />{f.label}</label>
            : <><label htmlFor={`f-${f.key}`}>{f.label}</label>
              {f.type === "select" ? <select id={`f-${f.key}`} value={v[f.key]} onChange={(e) => setV({ ...v, [f.key]: e.target.value })}>{f.options.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select>
                : f.type === "textarea" || f.type === "lines" ? <textarea id={`f-${f.key}`} value={v[f.key]} onChange={(e) => setV({ ...v, [f.key]: e.target.value })} style={{ minHeight: f.rows || 90, fontFamily: "inherit" }} />
                : <input id={`f-${f.key}`} type={f.type === "number" ? "number" : "text"} step={f.step} min={f.min} max={f.max} value={v[f.key]} onChange={(e) => setV({ ...v, [f.key]: e.target.value })} />}</>}
          {f.hint && <span className="hint">{f.hint}</span>}
        </div>))}
      <button className="btn">Save changes</button>
      {children}
    </form>
  );
}

function Appearance({ s }) {
  const [t, setT] = useState(s.theme || DEFAULT_THEME); const [n, setN] = useState({});
  const labels = { maroon: "Main headings, navigation and table headers", gold: "Accents, highlights and shaded visuals", ivory: "Page background", ink: "Body text" };
  const change = (k, val) => { const nt = { ...t, [k]: val }; setT(nt); if (/^#[0-9A-Fa-f]{6}$/.test(val)) applyTheme(nt); };
  async function save() { try { const d = await api("/api/settings/theme", { method: "PUT", body: t }); setT(d); applyTheme(d); setN({ kind: "ok", text: "Colors saved." }); } catch (x) { setN({ kind: "err", text: x.message }); } }
  return (
    <section className="panel" style={{ maxWidth: 680 }}><h2>Appearance</h2><Note n={n} />
      {Object.keys(DEFAULT_THEME).map((k) => (
        <div className="field" key={k}><label htmlFor={`c-${k}`}>{labels[k]}</label>
          <div className="swatch"><input type="color" aria-label={`${k} color picker`} value={t[k]} onChange={(e) => change(k, e.target.value.toUpperCase())} />
            <input id={`c-${k}`} value={t[k]} maxLength={7} onChange={(e) => change(k, e.target.value)} style={{ maxWidth: 140 }} /></div></div>))}
      <div className="preview" aria-hidden="true"><div className="pt">Preview heading</div><div className="pb">Body text on the page background.</div></div>
      <div className="row" style={{ margin: "14px 0" }}><button className="btn" onClick={save}>Save colors</button>
        <button className="btn line" onClick={() => { setT(DEFAULT_THEME); applyTheme(DEFAULT_THEME); setN({ kind: "", text: "Defaults restored. Save colors to keep them." }); }}>Restore maroon and gold</button></div>
      <h3>Logo, banners and headers</h3>
      <p>Edit or replace the logo, login banner, dashboard header, report header and agent picture on a canvas. Move, resize and recolor elements, swap images, and keep older versions.</p>
      <a className="btn gold" href="/visuals" style={{ textDecoration: "none", display: "inline-block" }}>Edit visuals</a>
    </section>
  );
}

function MarketRow({ m, say, reload }) {
  const [v, setV] = useState({ timezone: m.timezone, call_start: m.call_start, call_end: m.call_end, weekend_days: m.weekend_days, active: m.active });
  const off = (d) => v.weekend_days.includes(d);
  async function save() { try { await api(`/api/markets/${m.code}`, { method: "PUT", body: v }); say({ kind: "ok", text: `${m.name} saved.` }); reload(); } catch (x) { say({ kind: "err", text: x.message }); } }
  return (
    <section className="panel"><h3>{m.name} ({m.priority === "main" ? "main market" : "secondary"})</h3>
      <div className="row">
        <div className="field" style={{ flex: "1 1 200px" }}><label htmlFor={`tz${m.code}`}>Time zone</label><input id={`tz${m.code}`} value={v.timezone} onChange={(e) => setV({ ...v, timezone: e.target.value })} /></div>
        <div className="field"><label htmlFor={`s${m.code}`}>Calls start</label><input id={`s${m.code}`} type="time" value={v.call_start} onChange={(e) => setV({ ...v, call_start: e.target.value })} /></div>
        <div className="field"><label htmlFor={`e${m.code}`}>Calls end</label><input id={`e${m.code}`} type="time" value={v.call_end} onChange={(e) => setV({ ...v, call_end: e.target.value })} /></div>
      </div>
      <div className="field"><label>Never call on</label><div>{DAYS.map((d) => <label key={d} style={{ marginRight: 14 }}><input type="checkbox" checked={off(d)} style={{ width: "auto", marginRight: 4 }}
        onChange={() => setV({ ...v, weekend_days: off(d) ? v.weekend_days.filter((x) => x !== d) : [...v.weekend_days, d] })} />{d}</label>)}</div></div>
      <div className="row"><label><input type="checkbox" checked={v.active} onChange={(e) => setV({ ...v, active: e.target.checked })} style={{ width: "auto", marginRight: 6 }} />Calling switched on for this market</label>
        <button className="btn" onClick={save}>Save {m.name}</button></div>
    </section>
  );
}

function Markets() {
  const [m, setM] = useState([]); const [n, setN] = useState({});
  const load = () => api("/api/markets").then(setM).catch(() => {});
  useEffect(() => { load(); }, []);
  return (<><section className="panel"><h2>Markets</h2><p>Calling hours and days are checked in each market's own time zone. The starting values are guesses. Confirm the legal calling hours and rules for each country before live calls. The United States and Australia span several time zones, so use hours that are safe in all of them.</p><Note n={n} /></section>
    {m.map((x) => <MarketRow key={x.code + x.timezone + x.call_start + x.call_end + x.active} m={x} say={setN} reload={load} />)}</>);
}

function ServiceCard({ svc, reload, say }) {
  const [v, setV] = useState({ name: svc.name, pitch: svc.pitch, pain: svc.pain_points.join("\n"), sig: svc.signals.join("\n") });
  const body = () => ({ name: v.name, pitch: v.pitch, pain_points: v.pain.split("\n"), signals: v.sig.split("\n") });
  async function save() { try { await api(`/api/services/${svc.id}`, { method: "PUT", body: body() }); say({ kind: "ok", text: `${v.name} saved.` }); reload(); } catch (x) { say({ kind: "err", text: x.message }); } }
  async function del() { if (!window.confirm(`Delete ${svc.name}?`)) return; try { await api(`/api/services/${svc.id}`, { method: "DELETE" }); reload(); } catch (x) { say({ kind: "err", text: x.message }); } }
  return (
    <section className="panel">
      <div className="field"><label htmlFor={`n${svc.id}`}>Service name</label><input id={`n${svc.id}`} value={v.name} onChange={(e) => setV({ ...v, name: e.target.value })} /></div>
      <div className="field"><label htmlFor={`p${svc.id}`}>Short pitch</label><input id={`p${svc.id}`} value={v.pitch} onChange={(e) => setV({ ...v, pitch: e.target.value })} /></div>
      <div className="row">
        <div className="field" style={{ flex: "1 1 260px" }}><label htmlFor={`d${svc.id}`}>Problems it solves (one per line)</label><textarea id={`d${svc.id}`} value={v.pain} onChange={(e) => setV({ ...v, pain: e.target.value })} /></div>
        <div className="field" style={{ flex: "1 1 260px" }}><label htmlFor={`s${svc.id}`}>Signals we look for (one per line)</label><textarea id={`s${svc.id}`} value={v.sig} onChange={(e) => setV({ ...v, sig: e.target.value })} /></div>
      </div>
      <div className="row"><button className="btn" onClick={save}>Save service</button><button className="btn line" onClick={del}>Delete service</button></div>
    </section>
  );
}

function Services() {
  const [s, setS] = useState([]); const [n, setN] = useState({}); const [name, setName] = useState("");
  const load = () => api("/api/services").then(setS).catch(() => {});
  useEffect(() => { load(); }, []);
  async function add(e) { e.preventDefault(); try { await api("/api/services", { method: "POST", body: { name } }); setName(""); setN({ kind: "ok", text: "Service added. Fill in its problems and signals below." }); load(); } catch (x) { setN({ kind: "err", text: x.message }); } }
  return (<><section className="panel"><h2>Service Catalog</h2>
    <p>The services the pain-point engine matches against. The calling agent also reads this catalog, so rebuild the voice agent after changing it. The first service is used for businesses with no website.</p><Note n={n} />
    <form className="row" onSubmit={add}><div className="field" style={{ flex: "1 1 280px", margin: 0 }}><label htmlFor="ns">New service name</label><input id="ns" value={name} onChange={(e) => setName(e.target.value)} required minLength={2} /></div><button className="btn gold">Add service</button></form></section>
    {s.map((x) => <ServiceCard key={x.id + x.name} svc={x} reload={load} say={setN} />)}</>);
}

const SC_DEFAULT = {
  icp: { target_industries: [], avoid_industries: [], target_markets: ["AE", "SA", "GB", "US", "AU"] },
  weights: { pain: 50, fit: 25, evidence: 15, buying: 5, business: 5 },
  rules: { unverified_cap: 49, inferred_penalty: 5, avoid_cap: 39, high_from: 80, medium_from: 60, verified_min_pain: 3, verified_min_evidence: 3 },
  gap_points: { low: 6, medium: 12, high: 20, hypothesis_factor: 0.5 },
  pain_steps: [6, 12, 20, 32],
  buying: { one: 3, two_or_more: 5 },
  business: { both: 5, type_only: 3, market_only: 2, neither: 1, no_types_market_ok: 3, no_types_other: 1 },
};
const FACTORS = [["pain", "Pain point and impact"], ["fit", "HY service fit"], ["evidence", "Evidence quality"], ["buying", "Buying signals"], ["business", "Business fit"]];

function Num({ label, hint, value, onChange, step, min, max, id }) {
  return (<div className="field" style={{ flex: "1 1 200px" }}><label htmlFor={id}>{label}</label>
    <input id={id} type="number" step={step} min={min} max={max} value={value} onChange={(e) => onChange(e.target.value === "" ? "" : Number(e.target.value))} />{hint && <span className="hint">{hint}</span>}</div>);
}

function ScoringTab({ s, reload }) {
  const [v, setV] = useState(() => structuredClone(s.scoring));
  const [markets, setMarkets] = useState([]);
  const [n, setN] = useState({});
  const [busy, setBusy] = useState(false);
  const [t, setT] = useState({ pain: 3, fit: 4, evidence: 4, buying: 0, business: 3, verified: true, inferred: false, avoid: false });
  useEffect(() => { api("/api/markets").then(setMarkets).catch(() => {}); }, []);
  const set = (path, val) => setV((o) => { const c = structuredClone(o); let x = c; path.slice(0, -1).forEach((k) => (x = x[k])); x[path[path.length - 1]] = val; return c; });
  const total = Object.values(v.weights).reduce((a, b) => a + Number(b || 0), 0);
  const lines = (arr) => arr.join("\n");
  const R = v.rules;

  async function save(rescore) {
    setBusy(true); setN({});
    try {
      await api("/api/settings/scoring", { method: "PUT", body: v });
      let text = "Saved. New and re-analyzed leads use these choices.";
      if (rescore) { const r = await api("/api/scoring/rescore", { method: "POST" }); text = `Saved and re-scored ${r.rescored} leads. No new website reading was needed.`; }
      setN({ kind: "ok", text }); reload();
    } catch (x) { setN({ kind: "err", text: x.message }); }
    setBusy(false);
  }

  const pts = Object.fromEntries(FACTORS.map(([k]) => [k, (t[k] / 5) * v.weights[k]]));
  const raw = Math.round(Object.values(pts).reduce((a, b) => a + b, 0));
  let score = raw; const notes = [];
  if (t.inferred) { score = Math.max(0, score - R.inferred_penalty); notes.push(`Key pain only inferred: minus ${R.inferred_penalty}`); }
  if (!t.verified && score > R.unverified_cap) { notes.push(`No verified pain: capped at ${R.unverified_cap}`); score = R.unverified_cap; }
  if (t.avoid && score > R.avoid_cap) { notes.push(`Business type you avoid: capped at ${R.avoid_cap}`); score = R.avoid_cap; }
  const band = score >= R.high_from ? "High priority" : score >= R.medium_from ? "Medium priority" : "Low priority";

  return (<>
    <section className="panel" style={{ maxWidth: 820 }}><h2>How a lead gets its score</h2>
      <p>Every lead gets <b>five ratings from 0 to 5</b>: how serious its proven problems are, how well they match what HY Developer sells, how strong the evidence is, whether it shows buying signs, and whether it is your kind of customer.</p>
      <p>Each rating becomes points: <b>rating ÷ 5 × weight</b>. The weight is the most points that factor can give, and the five weights add up to 100. With your numbers now, a perfect Pain rating (5) gives {v.weights.pain} points, and a Business fit of 3 gives {Math.round(3 / 5 * v.weights.business * 10) / 10}.</p>
      <p>Two safety rules can then lower the score: with <b>no verified pain</b> it cannot go above {R.unverified_cap}, and if the <b>key pain is only guessed</b> it loses {R.inferred_penalty} points. The result is a <b>priority</b>: {R.high_from} or more is High, {R.medium_from} to {R.high_from - 1} is Medium, below {R.medium_from} is Low. It is a ranking for who to work on first, <b>not the chance that they will buy</b>.</p>
      <Note n={n} />
      <div className="row"><button className="btn" disabled={busy || total !== 100} onClick={() => save(false)}>Save</button>
        <button className="btn gold" disabled={busy || total !== 100} onClick={() => save(true)}>Save and re-score all my leads</button>
        <button className="btn line" onClick={() => { setV(structuredClone(SC_DEFAULT)); setN({ kind: "", text: "Original values are back on screen. Press Save to keep them." }); }}>Reset to the original values</button></div>
      {total !== 100 && <p className="msg err" style={{ marginTop: 12 }}>The five weights add up to {total}. They must add up to exactly 100 before you can save.</p>}
    </section>

    <section className="panel" style={{ maxWidth: 820 }}><h2>Your ideal customer (ICP)</h2>
      <p>This drives the <b>Business fit</b> rating and a safety rule. Business types are matched by words, so "clinic" also matches "dental clinic".</p>
      <div className="row">
        <div className="field" style={{ flex: "1 1 300px" }}><label htmlFor="tgt">Business types you want (one per line)</label><textarea id="tgt" value={lines(v.icp.target_industries)} onChange={(e) => set(["icp", "target_industries"], e.target.value.split("\n"))} placeholder={"dental clinic\nreal estate agency\nprivate school"} /></div>
        <div className="field" style={{ flex: "1 1 300px" }}><label htmlFor="avd">Business types you avoid (one per line)</label><textarea id="avd" value={lines(v.icp.avoid_industries)} onChange={(e) => set(["icp", "avoid_industries"], e.target.value.split("\n"))} placeholder={"government\nbank"} />
          <span className="hint">A lead of these types gets Business fit 0 and its score is capped at {R.avoid_cap}.</span></div>
      </div>
      <div className="field"><label>Markets you want</label><div>{markets.map((m) => <label key={m.code} style={{ marginRight: 16 }}><input type="checkbox" style={{ width: "auto", marginRight: 4 }} checked={v.icp.target_markets.includes(m.code)}
        onChange={(e) => set(["icp", "target_markets"], e.target.checked ? [...v.icp.target_markets, m.code] : v.icp.target_markets.filter((x) => x !== m.code))} />{m.name}</label>)}</div></div>
    </section>

    <section className="panel" style={{ maxWidth: 820 }}><h2>Weights: how much each factor is worth</h2>
      <div className="row">{FACTORS.map(([k, name]) => <Num key={k} id={`w-${k}`} label={`${name}`} min={0} max={100} value={v.weights[k]} onChange={(x) => set(["weights", k], x)} />)}</div>
      <p style={{ margin: 0 }}><b>Total: {total}</b> {total === 100 ? "(correct)" : "(must be 100)"}. Make a factor matter more by giving it more points and another one fewer.</p>
    </section>

    <section className="panel" style={{ maxWidth: 820 }}><h2>Safety rules and priority bands</h2>
      <div className="row">
        <Num id="r1" label="Score limit when no pain is verified" min={0} max={100} value={R.unverified_cap} onChange={(x) => set(["rules", "unverified_cap"], x)} hint="Your document says 49." />
        <Num id="r2" label="Points lost when the key pain is only inferred" min={0} max={50} value={R.inferred_penalty} onChange={(x) => set(["rules", "inferred_penalty"], x)} hint="Your document says 5." />
        <Num id="r3" label="Score limit for a business type you avoid" min={0} max={100} value={R.avoid_cap} onChange={(x) => set(["rules", "avoid_cap"], x)} />
      </div>
      <div className="row">
        <Num id="r4" label="High priority from" min={1} max={100} value={R.high_from} onChange={(x) => set(["rules", "high_from"], x)} />
        <Num id="r5" label="Medium priority from" min={1} max={100} value={R.medium_from} onChange={(x) => set(["rules", "medium_from"], x)} />
        <Num id="r6" label="Pain counts as verified from rating (1 to 5)" min={1} max={5} value={R.verified_min_pain} onChange={(x) => set(["rules", "verified_min_pain"], x)} hint="Rating of the proven problems alone." />
        <Num id="r7" label="and evidence rating of at least" min={1} max={5} value={R.verified_min_evidence} onChange={(x) => set(["rules", "verified_min_evidence"], x)} />
      </div>
    </section>

    <section className="panel" style={{ maxWidth: 820 }}><h2>Advanced values</h2>
      <details><summary>Show the detailed numbers behind each rating</summary>
        <h3>How many points a problem is worth</h3>
        <div className="row">
          <Num id="g1" label="Low problem" min={1} max={100} value={v.gap_points.low} onChange={(x) => set(["gap_points", "low"], x)} />
          <Num id="g2" label="Medium problem" min={1} max={100} value={v.gap_points.medium} onChange={(x) => set(["gap_points", "medium"], x)} />
          <Num id="g3" label="High problem" min={1} max={100} value={v.gap_points.high} onChange={(x) => set(["gap_points", "high"], x)} hint="High means it costs them customers now." />
          <Num id="g4" label="Share counted for a suspected problem" step="0.1" min={0} max={1} value={v.gap_points.hypothesis_factor} onChange={(x) => set(["gap_points", "hypothesis_factor"], x)} hint="0.5 means half." />
        </div>
        <h3>Pain rating steps</h3>
        <p className="hint">Add up the problem points of a lead. Below the first number the Pain rating is 1. At each number it rises by one, up to 5.</p>
        <div className="row">{[0, 1, 2, 3].map((i) => <Num key={i} id={`ps${i}`} label={`Rating ${i + 2} from`} min={1} value={v.pain_steps[i]} onChange={(x) => set(["pain_steps", i], x)} />)}</div>
        <h3>Buying signals rating</h3>
        <div className="row"><Num id="b1" label="One signal found" min={0} max={5} value={v.buying.one} onChange={(x) => set(["buying", "one"], x)} />
          <Num id="b2" label="Two or more, or an explicit request" min={0} max={5} value={v.buying.two_or_more} onChange={(x) => set(["buying", "two_or_more"], x)} /></div>
        <h3>Business fit rating</h3>
        <div className="row">
          <Num id="z1" label="Right type and market" min={0} max={5} value={v.business.both} onChange={(x) => set(["business", "both"], x)} />
          <Num id="z2" label="Right type, other market" min={0} max={5} value={v.business.type_only} onChange={(x) => set(["business", "type_only"], x)} />
          <Num id="z3" label="Right market, other type" min={0} max={5} value={v.business.market_only} onChange={(x) => set(["business", "market_only"], x)} />
          <Num id="z4" label="Neither" min={0} max={5} value={v.business.neither} onChange={(x) => set(["business", "neither"], x)} />
          <Num id="z5" label="No types set, right market" min={0} max={5} value={v.business.no_types_market_ok} onChange={(x) => set(["business", "no_types_market_ok"], x)} />
          <Num id="z6" label="No types set, other market" min={0} max={5} value={v.business.no_types_other} onChange={(x) => set(["business", "no_types_other"], x)} />
        </div>
      </details>
    </section>

    <section className="panel" style={{ maxWidth: 820 }}><h2>Try it: see how the numbers work</h2>
      <p>Move the ratings to see the score with your current settings. Nothing here changes any lead.</p>
      {FACTORS.map(([k, name]) => (<div className="field" key={k}><label htmlFor={`t-${k}`}>{name}: rating {t[k]} of 5, worth {Math.round(pts[k] * 10) / 10} of {v.weights[k]} points</label>
        <input id={`t-${k}`} type="range" min={0} max={5} step={1} value={t[k]} onChange={(e) => setT({ ...t, [k]: Number(e.target.value) })} /></div>))}
      <div className="row">
        <label><input type="checkbox" style={{ width: "auto", marginRight: 6 }} checked={t.verified} onChange={(e) => setT({ ...t, verified: e.target.checked })} />Pain is verified</label>
        <label><input type="checkbox" style={{ width: "auto", marginRight: 6 }} checked={t.inferred} onChange={(e) => setT({ ...t, inferred: e.target.checked })} />Key pain is only inferred</label>
        <label><input type="checkbox" style={{ width: "auto", marginRight: 6 }} checked={t.avoid} onChange={(e) => setT({ ...t, avoid: e.target.checked })} />Business type is on my avoid list</label>
      </div>
      <p style={{ fontSize: 18, marginBottom: 4 }}>Points added up: <b>{raw}</b>{notes.length > 0 && <> then {notes.join("; ")}</>}. <b>Final score: {score} out of 100, {band}.</b></p>
    </section>
  </>);
}

function Voice({ s, reload }) {
  const v0 = s.voice;
  const [v, setV] = useState({ ...v0, voicesText: Object.entries(v0.voices).map(([k, x]) => `${k} = ${x}`).join("\n") });
  const [markets, setMarkets] = useState([]); const [n, setN] = useState({}); const [report, setReport] = useState([]); const [busy, setBusy] = useState(false); const [st, setSt] = useState(null);
  useEffect(() => { api("/api/markets").then(setMarkets).catch(() => {}); api("/api/calling/status").then(setSt).catch(() => {}); }, []);
  const set = (k) => (e) => setV({ ...v, [k]: e.target.value });
  function body() {
    const voices = {}; v.voicesText.split("\n").forEach((l) => { const [k, ...r] = l.split("="); if (k && k.trim() && r.join("=").trim()) voices[k.trim()] = r.join("=").trim(); });
    const { voicesText, ...rest } = v;
    return { ...rest, voices, speed: Number(v.speed), max_call_minutes: Number(v.max_call_minutes) };
  }
  async function save(e) { e.preventDefault(); try { await api("/api/settings/voice", { method: "PUT", body: body() }); setN({ kind: "ok", text: "Saved. Press Build agent to send these settings to Retell." }); reload(); return true; } catch (x) { setN({ kind: "err", text: x.message }); return false; } }
  async function build() {
    setBusy(true); setReport([]);
    if (!(await save({ preventDefault() {} }))) { setBusy(false); return; }
    try { const r = await api("/api/voice/build", { method: "POST" }); setReport(r.report); setN({ kind: "ok", text: "The voice agent is built and ready." }); api("/api/calling/status").then(setSt); } catch (x) { setN({ kind: "err", text: x.message }); }
    setBusy(false);
  }
  return (
    <form className="panel" onSubmit={save} style={{ maxWidth: 760 }}>
      <h2>Voice Agent</h2>
      <p>How the calling agent sounds and what it says. Save, then press Build agent. Build again after changing the Service Catalog or anything here.</p>
      <Note n={n} />
      {st && <p><span className={`chip ${st.agents.length ? "on" : "off"}`}>Built agents: {st.agents.join(", ") || "none yet"}</span></p>}
      <div className="row">
        <div className="field" style={{ flex: "2 1 260px" }}><label htmlFor="an">Agent name</label><input id="an" value={v.agent_name} onChange={set("agent_name")} /></div>
        <div className="field" style={{ flex: "1 1 120px" }}><label htmlFor="sp">Speaking speed</label><input id="sp" type="number" step="0.05" min="0.6" max="1.4" value={v.speed} onChange={set("speed")} /></div>
        <div className="field" style={{ flex: "1 1 140px" }}><label htmlFor="mm">Longest call (minutes)</label><input id="mm" type="number" min="1" max="15" value={v.max_call_minutes} onChange={set("max_call_minutes")} /></div>
      </div>
      <div className="field"><label htmlFor="tone">Tone</label><input id="tone" value={v.tone} onChange={set("tone")} /><span className="hint">For example: formal and respectful, friendly and relaxed, direct and confident.</span></div>
      <div className="field"><label htmlFor="op">Opening line</label><textarea id="op" value={v.opening} onChange={set("opening")} style={{ minHeight: 80, fontFamily: "inherit" }} />
        <span className="hint">Must say it is an AI assistant. You can use {"{{business_name}}"}, {"{{lead_name}}"} and {"{{company_name}}"}.</span></div>
      <div className="field"><label htmlFor="vo">Retell voice for each language (one per line, like en-US = voice ID)</label><textarea id="vo" value={v.voicesText} onChange={set("voicesText")} style={{ minHeight: 70 }} />
        <span className="hint">Copy voice IDs from your Retell dashboard. Add an Arabic line only after checking that Retell supports Arabic for your voice, and use the language code Retell lists.</span></div>
      <div className="field"><label>Language for each market</label>
        <div className="row">{markets.map((m) => <div key={m.code} style={{ flex: "1 1 150px" }}><label htmlFor={`l${m.code}`} style={{ fontWeight: 400 }}>{m.name}</label>
          <input id={`l${m.code}`} value={v.call_language_by_market[m.code] || "en-US"} onChange={(e) => setV({ ...v, call_language_by_market: { ...v.call_language_by_market, [m.code]: e.target.value } })} /></div>)}</div>
        <span className="hint">If no voice is set for a language, calls use English instead.</span></div>
      <div className="field"><label htmlFor="cs">Your company website (the agent reads it)</label><input id="cs" value={v.company_site} onChange={set("company_site")} /></div>
      <div className="field"><label htmlFor="cf">Facts the agent may state</label><textarea id="cf" value={v.company_facts} onChange={set("company_facts")} /><span className="hint">Real proof only: past projects you can name, years of experience, locations. The agent is told never to invent anything else.</span></div>
      <div className="field"><label htmlFor="sn">Extra instructions for the call</label><textarea id="sn" value={v.script_notes} onChange={set("script_notes")} /></div>
      <div className="field"><label htmlFor="ob">Your answers to common objections</label><textarea id="ob" value={v.objection_notes} onChange={set("objection_notes")} /></div>
      <div className="row"><button className="btn line" type="submit">Save</button><button type="button" className="btn gold" disabled={busy} onClick={build}>{busy ? "Building" : "Save and build agent"}</button></div>
      {report.length > 0 && <ul>{report.map((r, i) => <li key={i}>{r}</li>)}</ul>}
    </form>
  );
}

function KeyRow({ id, label, where, info, svc, extra, value, setValue, note, onTest, onClear }) {
  return (
    <div className="field" style={{ borderTop: "1px solid var(--rule)", paddingTop: 12 }}>
      <label htmlFor={id}>{label} {info?.set ? <span className="chip on">saved {info.hint}</span> : <span className="chip off">not set</span>}</label>
      <input id={id} type="password" autoComplete="off" placeholder={info?.set ? "Saved. Type a new key to replace it." : "Paste your key"} value={value} onChange={(e) => setValue(e.target.value)} />
      <span className="hint">{where}</span>
      {extra}
      <div className="row" style={{ marginTop: 6 }}>
        <button type="button" className="btn line" disabled={!info?.set} onClick={() => onTest(svc)}>Test this key</button>
        {info?.set && <button type="button" className="btn line" onClick={() => onClear(id)}>Remove key</button>}
        {note[svc] && <span className={note[svc].ok ? "chip on" : "chip off"}>{note[svc].text}</span>}
      </div>
    </div>
  );
}

function Integrations({ s, reload }) {
  const [k, setK] = useState(null);
  const [v, setV] = useState({ LLM_API_KEY: "", GOOGLE_PLACES_API_KEY: "", RETELL_API_KEY: "", LLM_BASE_URL: "", LLM_MODEL: "" });
  const [tests, setTests] = useState({}); const [n, setN] = useState({});
  const [nums, setNums] = useState((s.integrations?.phone_numbers || []).join("\n")); const [pn, setPn] = useState({});
  const load = () => api("/api/keys").then((d) => { setK(d); setV((o) => ({ ...o, LLM_BASE_URL: d.llm_base_url, LLM_MODEL: d.llm_model })); }).catch(() => {});
  useEffect(() => { load(); }, []);
  const set = (key) => (val) => setV({ ...v, [key]: val });
  async function save() {
    try { await api("/api/keys", { method: "PUT", body: v }); setV((o) => ({ ...o, LLM_API_KEY: "", GOOGLE_PLACES_API_KEY: "", RETELL_API_KEY: "" })); setN({ kind: "ok", text: "Saved. Use Test this key to check each one." }); load(); }
    catch (x) { setN({ kind: "err", text: x.message }); }
  }
  async function clear(key) { if (!window.confirm("Remove this key?")) return; try { await api("/api/keys", { method: "PUT", body: { clear: [key] } }); load(); } catch (x) { setN({ kind: "err", text: x.message }); } }
  async function test(svc) {
    setTests((t) => ({ ...t, [svc]: { ok: true, text: "Testing" } }));
    try { await api(`/api/keys/test/${svc}`, { method: "POST" }); setTests((t) => ({ ...t, [svc]: { ok: true, text: "Works" } })); }
    catch (x) { setTests((t) => ({ ...t, [svc]: { ok: false, text: x.message.slice(0, 160) } })); }
  }
  async function savePhones() { try { const d = await api("/api/settings/integrations", { method: "PUT", body: { phone_numbers: nums.split("\n") } }); setNums(d.phone_numbers.join("\n")); setPn({ kind: "ok", text: "Phone numbers saved." }); reload(); } catch (x) { setPn({ kind: "err", text: x.message }); } }
  const ks = k?.keys || {};
  return (<>
    <section className="panel" style={{ maxWidth: 720 }}><h2>API keys</h2>
      <p>Keys are saved encrypted on this computer and are never shown again. Leave a box empty to keep what is saved.</p><Note n={n} />
      <KeyRow id="LLM_API_KEY" svc="llm" label="Language model key" info={ks.LLM_API_KEY} value={v.LLM_API_KEY} setValue={set("LLM_API_KEY")} note={tests} onTest={test} onClear={clear}
        where="Reads and scores businesses and sorts call results. A free Google Gemini key from aistudio.google.com works."
        extra={<div className="row"><div style={{ flex: "2 1 280px" }}><label htmlFor="lb" style={{ fontWeight: 400 }}>Provider address</label><input id="lb" value={v.LLM_BASE_URL} onChange={(e) => setV({ ...v, LLM_BASE_URL: e.target.value })} /></div>
          <div style={{ flex: "1 1 160px" }}><label htmlFor="lm" style={{ fontWeight: 400 }}>Model</label><input id="lm" value={v.LLM_MODEL} onChange={(e) => setV({ ...v, LLM_MODEL: e.target.value })} /></div></div>} />
      <KeyRow id="GOOGLE_PLACES_API_KEY" svc="places" label="Google Places key" info={ks.GOOGLE_PLACES_API_KEY} value={v.GOOGLE_PLACES_API_KEY} setValue={set("GOOGLE_PLACES_API_KEY")} note={tests} onTest={test} onClear={clear}
        where="Finds businesses automatically. In Google Cloud, turn on Places API (New) and enable billing. Set a budget alert first." />
      <KeyRow id="RETELL_API_KEY" svc="retell" label="Retell key" info={ks.RETELL_API_KEY} value={v.RETELL_API_KEY} setValue={set("RETELL_API_KEY")} note={tests} onTest={test} onClear={clear}
        where="Makes the voice agent and places the calls. Copy it from your Retell dashboard." />
      <button className="btn" onClick={save}>Save keys</button></section>
    <section className="panel" style={{ maxWidth: 720 }}><h2>Your calling phone numbers</h2><Note n={pn} />
      <div className="field"><label htmlFor="nums">One number per line, with country code</label><textarea id="nums" placeholder={"+971500000000\n+966500000000"} value={nums} onChange={(e) => setNums(e.target.value)} />
        <span className="hint">These must be numbers your Retell account owns or has imported. Retell numbers can only call some countries, so check that yours can reach the UAE, Saudi Arabia, the UK, Australia and the USA.</span></div>
      <button className="btn" onClick={savePhones}>Save phone numbers</button></section></>);
}

function Compliance({ s, reload }) {
  const [dnc, setDnc] = useState([]); const [ph, setPh] = useState(""); const [log, setLog] = useState(null); const [bk, setBk] = useState([]); const [n, setN] = useState({});
  const loadD = () => api("/api/dnc").then(setDnc).catch(() => {});
  useEffect(() => { loadD(); api("/api/backups").then(setBk).catch(() => {}); }, []);
  const run = async (fn, ok) => { try { await fn(); if (ok) setN({ kind: "ok", text: ok }); } catch (x) { setN({ kind: "err", text: x.message }); } };
  return (<>
    <Form area="compliance" s={s} reload={reload} title="Compliance" intro="Every call opens by telling the person they are speaking with an AI assistant. That is set in Voice Agent and cannot be left out."
      fields={[{ key: "recording_notice_enabled", label: "Add a recording notice to the opening line", type: "checkbox" }, { key: "recording_notice", label: "Recording notice wording", type: "text", hint: "Build the voice agent again after changing this." }]} />
    <section className="panel" style={{ maxWidth: 720 }}><h2>Do Not Call list</h2><Note n={n} />
      <p>Numbers here are never called. Anyone who asks on a call to be removed is added automatically.</p>
      <form className="row" onSubmit={(e) => { e.preventDefault(); run(async () => { await api("/api/dnc", { method: "POST", body: { phone: ph, reason: "Added by owner" } }); setPh(""); loadD(); }, "Number added."); }}>
        <div className="field" style={{ margin: 0, flex: "1 1 240px" }}><label htmlFor="dn">Add a number</label><input id="dn" placeholder="+971500000000" value={ph} onChange={(e) => setPh(e.target.value)} required /></div><button className="btn">Add</button></form>
      {dnc.length > 0 && <div className="scroll" style={{ marginTop: 12 }}><table className="tbl"><thead><tr><th>Number</th><th>Reason</th><th>Added</th><th></th></tr></thead>
        <tbody>{dnc.map((d) => <tr key={d.id}><td>{d.phone}</td><td>{d.reason}</td><td>{when(d.added_at)}</td><td><button className="btn line" onClick={() => run(async () => { await api(`/api/dnc/${d.id}`, { method: "DELETE" }); loadD(); })}>Remove</button></td></tr>)}</tbody></table></div>}</section>
    <section className="panel" style={{ maxWidth: 720 }}><h2>Backup</h2>
      <p>Saves a copy of your database in backend/data/backups. A copy is also made once a day while the program is running. Copy that folder to another drive now and then.</p>
      <button className="btn" onClick={() => run(async () => { const r = await api("/api/backup", { method: "POST" }); setBk([r.file, ...bk]); }, "Backup saved.")}>Back up now</button>
      {bk.length > 0 && <p className="hint">Latest: {bk.slice(0, 3).join(", ")}</p>}</section>
    <section className="panel" style={{ maxWidth: 720 }}><h2>Activity log</h2>
      {!log ? <button className="btn line" onClick={() => api("/api/audit").then(setLog)}>Show recent activity</button>
        : <div className="scroll"><table className="tbl"><thead><tr><th>When</th><th>What</th><th>Detail</th></tr></thead><tbody>{log.map((a, i) => <tr key={i}><td>{when(a.at)}</td><td>{a.action}</td><td>{a.detail}</td></tr>)}</tbody></table></div>}</section></>);
}

function Account() {
  const [v, setV] = useState({ current_password: "", new_password: "" }); const [n, setN] = useState({});
  async function save(e) { e.preventDefault(); try { await api("/api/auth/change-password", { method: "POST", body: v }); setV({ current_password: "", new_password: "" }); setN({ kind: "ok", text: "Password changed." }); } catch (x) { setN({ kind: "err", text: x.message }); } }
  return (<form className="panel" onSubmit={save} style={{ maxWidth: 560 }}><h2>Account and Security</h2><Note n={n} />
    <div className="field"><label htmlFor="cp">Current password</label><input id="cp" type="password" autoComplete="current-password" value={v.current_password} onChange={(e) => setV({ ...v, current_password: e.target.value })} required /></div>
    <div className="field"><label htmlFor="np">New password</label><input id="np" type="password" autoComplete="new-password" minLength={10} value={v.new_password} onChange={(e) => setV({ ...v, new_password: e.target.value })} required /><span className="hint">At least 10 characters</span></div>
    <button className="btn">Change password</button></form>);
}

export default function Settings() {
  const [tab, setTab] = useState("general");
  const [s, setS] = useState(null);
  const [markets, setMarkets] = useState([]);
  const load = () => api("/api/settings").then(setS).catch(() => {});
  useEffect(() => { load(); api("/api/markets").then(setMarkets).catch(() => {}); }, []);
  const common = { s, reload: load };
  return (
    <>
      <header className="top"><h1>Settings</h1></header>
      <div className="page">
        <div className="tabs" role="tablist">{TABS.map(([id, label]) => <button key={id} role="tab" aria-selected={tab === id} className={tab === id ? "on" : ""} onClick={() => setTab(id)}>{label}</button>)}</div>
        {!s ? "Loading" : tab === "general" ? <Form {...common} area="general" title="General" fields={[
            { key: "company_name", label: "Company name", type: "text" }, { key: "timezone", label: "Your time zone", type: "text", hint: "Example: Asia/Karachi. Scheduled start times and daily limits use this." },
            { key: "currency", label: "Currency for revenue", type: "text", hint: "Three letters, for example USD or AED" }]} />
          : tab === "appearance" ? <Appearance s={s} />
          : tab === "scoring" ? <ScoringTab s={s} reload={load} />
          : tab === "markets" ? <Markets /> : tab === "services" ? <Services /> : tab === "voice" ? <Voice {...common} />
          : tab === "calling" ? <Form {...common} area="calling" title="Calling Rules" intro="These rules apply to every call. Follow-ups stop on any real engagement." fields={[
            { key: "short_call_seconds", label: "A call shorter than this many seconds counts as a short call", type: "number", min: 5, max: 60 },
            { key: "followup_count", label: "Follow-up calls after a short or unanswered call", type: "number", min: 0, max: 5 },
            { key: "followup_gap_hours", label: "Hours between follow-ups", type: "number", min: 1, max: 168 },
            { key: "callback_default_hours", label: "Hours until a callback when the person gave no time", type: "number", min: 1, max: 168 },
            { key: "max_concurrent", label: "Calls at the same time", type: "number", min: 1, max: 10, hint: "Also limited by your Retell plan." },
            { key: "daily_call_limit", label: "Most calls per day", type: "number", min: 1, max: 1000 },
            { key: "daily_minutes_cap", label: "Most call minutes per day", type: "number", min: 10, max: 5000, hint: "A spending guard. Calling pauses for the day when reached." },
            { key: "cost_per_minute", label: "Your estimated cost per call minute", type: "number", step: "0.01", min: 0, max: 5, hint: "Used only for the cost estimates in Dashboard and Reports. Check your Retell and phone charges." }]} />
          : tab === "leads" ? <Form {...common} area="leads" title="Leads" fields={[
            { key: "default_market", label: "Market for imported leads when the file does not say", type: "select", options: [["", "Work it out from the phone number"], ...markets.map((m) => [m.code, m.name])] },
            { key: "analyze_uploads", label: "Analyze websites after every import by default", type: "checkbox" }]} />
          : tab === "acq" ? <Form {...common} area="acquisition" title="Acquisition" intro="The last two stages must stay Won and Lost." fields={[
            { key: "stages", label: "Pipeline stages, in order (one per line)", type: "lines", rows: 180 },
            { key: "monthly_target", label: "Monthly revenue target", type: "number", min: 0, hint: "Zero turns the target off." }]} />
          : tab === "integrations" ? <Integrations {...common} /> : tab === "compliance" ? <Compliance {...common} /> : <Account />}
      </div>
    </>
  );
}
