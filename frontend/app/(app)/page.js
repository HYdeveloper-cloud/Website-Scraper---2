"use client";
import { useContext, useEffect, useState } from "react";
import { api, visualSrc } from "../../lib/api";
import { VisualsContext } from "../../lib/visuals";
import { Bars, HBars } from "../../components/charts";

const num = (n) => (n ?? 0).toLocaleString("en-US");

export default function Dashboard() {
  const vis = useContext(VisualsContext);
  const [days, setDays] = useState(30);
  const [d, setD] = useState(null);
  const [cur, setCur] = useState("USD");
  const [err, setErr] = useState("");

  useEffect(() => { api(`/api/dashboard?days=${days}`).then(setD).catch((e) => setErr(e.message)); }, [days]);
  useEffect(() => { api("/api/settings").then((s) => s.general && setCur(s.general.currency)).catch(() => {}); }, []);

  const money = (n) => new Intl.NumberFormat("en-US", { style: "currency", currency: cur, maximumFractionDigits: 0 }).format(n || 0);
  if (err) return <div className="page"><p className="msg err">{err}</p></div>;
  if (!d) return <div className="page">Loading</div>;
  const k = d.kpis;
  const tiles = [["Businesses discovered", num(k.discovered), "/leads"], ["Calls made", num(k.calls), "/call-logs"], ["Calls connected", num(k.connected), "/call-logs"],
    ["Meetings booked", num(k.meetings), "/leads?status=Meeting%20Booked"], ["Deals won", num(k.won), "/acquisition"], ["Revenue", money(k.revenue), "/acquisition"]];

  return (
    <>
      {vis.dashboard_header && <img className="hero-img" src={visualSrc("dashboard_header", vis.dashboard_header)} alt="" />}
      <header className="top"><h1>Dashboard</h1>
        <div className="pills" style={{ margin: 0 }} role="group" aria-label="Date range">
          {[[1, "Today"], [7, "7 days"], [30, "30 days"], [90, "90 days"]].map(([n, l]) => <button key={n} className={days === n ? "on" : ""} onClick={() => setDays(n)}>{l}</button>)}
        </div>
      </header>
      <div className="page">
        {d.empty && <p className="msg">Nothing to show yet. Find businesses in Lead Discovery or import a list in Leads. These numbers fill in as calls are made.</p>}
        <section className="tiles" aria-label="Key figures">
          {tiles.map(([l, n, href]) => <a className="tile" href={href} key={l}><div className="n">{n}</div><div className="l">{l}</div></a>)}
        </section>

        <div className="grid2">
          <section className="panel"><h2>Calls per day, last 14 days</h2><Bars data={d.calls_per_day} labels={d.calls_per_day.map((_, i) => (i === 13 ? "today" : i + 1))} label="Calls per day over the last 14 days" /></section>
          <section className="panel"><h2>Call outcomes</h2><HBars rows={d.outcomes} />
            <p className="hint" style={{ marginBottom: 0 }}>{d.short_calls} calls were under the short-call limit. Average connected call: {d.avg_duration} seconds.</p></section>
        </div>

        <div className="grid3">
          <section className="panel"><h2>Success and denial</h2>
            <div className="bigpair"><div className="good"><div className="n">{d.success_rate}%</div>Success rate</div><div className="bad"><div className="n">{d.denial_rate}%</div>Denial rate</div></div>
            <p className="hint" style={{ marginBottom: 0 }}>Of connected calls. Success means interested, meeting booked or callback requested.</p></section>
          <section className="panel"><h2>Follow-ups</h2>
            <HBars gold rows={[["Scheduled", d.followups.scheduled], ["Completed", d.followups.completed], ["Pending now", d.followups.pending], ["Led to a result", d.followups.converted]]} /></section>
          <section className="panel"><h2>Top pain points found</h2><HBars gold rows={d.top_pains} /></section>
        </div>

        <div className="grid2">
          <section className="panel"><h2>By market</h2>
            <div className="scroll"><table className="tbl"><thead><tr><th>Market</th><th className="num">New leads</th><th className="num">Calls</th><th className="num">Meetings</th></tr></thead>
              <tbody>{d.by_market.map(([m, a, b, c]) => <tr key={m}><td>{m}</td><td className="num">{a}</td><td className="num">{b}</td><td className="num">{c}</td></tr>)}</tbody></table></div></section>
          <section className="panel"><h2>Pipeline</h2><HBars rows={d.pipeline} />
            <p className="hint" style={{ marginBottom: 0 }}>Call time in this period: {d.minutes} minutes, about {money(d.cost_estimate)} at your rate in Calling Rules.</p></section>
        </div>

        <section className="panel"><h2>Results by priority band</h2>
          <div className="scroll"><table className="tbl"><thead><tr><th>Band</th><th className="num">Leads</th><th className="num">Called</th><th className="num">Connected</th><th className="num">Positive</th><th className="num">Meetings</th><th className="num">Won</th></tr></thead>
            <tbody>{d.by_band.map((b) => <tr key={b.band}><td><b>{b.band}</b></td><td className="num">{b.leads}</td><td className="num">{b.called}</td><td className="num">{b.connected}</td><td className="num">{b.positive}</td><td className="num">{b.meetings}</td><td className="num">{b.won}</td></tr>)}</tbody></table></div>
          <p className="hint" style={{ marginBottom: 0 }}>{d.by_band.reduce((n, b) => n + b.called, 0) < 30 ? "Too few called leads to judge the scoring yet. Wait for at least 30 before changing it. " : ""}If High priority leads do not get more positive replies and meetings than Low priority ones over time, the scoring needs adjusting.</p></section>

      </div>
    </>
  );
}
