"use client";
import { useContext, useEffect, useState } from "react";
import { api, download, visualSrc } from "../../../lib/api";
import { VisualsContext } from "../../../lib/visuals";

export default function Reports() {
  const vis = useContext(VisualsContext);
  const [days, setDays] = useState(30);
  const [d, setD] = useState(null);
  const [a, setA] = useState(null);
  const [company, setCompany] = useState("HY Developer");
  const [cur, setCur] = useState("USD");
  const [err, setErr] = useState("");

  useEffect(() => { api(`/api/dashboard?days=${days}`).then(setD).catch((e) => setErr(e.message)); }, [days]);
  useEffect(() => {
    api("/api/acquisition").then(setA).catch(() => {});
    api("/api/settings").then((s) => { setCompany(s.general.company_name); setCur(s.general.currency); }).catch(() => {});
  }, []);
  const money = (n) => new Intl.NumberFormat("en-US", { style: "currency", currency: cur, maximumFractionDigits: 0 }).format(n || 0);
  const dl = (path, name) => download(path, name).catch((e) => setErr(e.message));

  return (
    <>
      <header className="top"><h1>Reports</h1></header>
      <div className="page">
        {err && <p className="msg err">{err}</p>}
        <section className="panel no-print"><h2>Download your data</h2>
          <p>Plain CSV files that open in Excel or Google Sheets.</p>
          <div className="row"><button className="btn" onClick={() => dl("/api/reports/leads.csv", "leads.csv")}>Leads</button>
            <button className="btn" onClick={() => dl("/api/reports/calls.csv", "calls.csv")}>Calls</button>
            <button className="btn" onClick={() => dl("/api/reports/deals.csv", "deals.csv")}>Deals</button></div></section>

        <div className="pills no-print" role="group" aria-label="Period">{[[7, "7 days"], [30, "30 days"], [90, "90 days"]].map(([n, l]) => <button key={n} className={days === n ? "on" : ""} onClick={() => setDays(n)}>{l}</button>)}
          <button style={{ marginLeft: 16, borderRightWidth: 2 }} onClick={() => window.print()}>Print or save as PDF</button></div>

        <section className="panel">
          {vis.report_header && <img src={visualSrc("report_header", vis.report_header)} alt="" style={{ width: "100%", marginBottom: 12 }} />}
          <h2>{company} acquisition report</h2>
          <p>Period: last {days} days. Created {new Date().toLocaleDateString()}.</p>
          {d && a && <>
            <div className="scroll"><table className="tbl"><thead><tr><th>Measure</th><th className="num">Value</th></tr></thead><tbody>
              {[["Businesses discovered", d.kpis.discovered], ["Calls made", d.kpis.calls], ["Calls connected", d.kpis.connected], ["Meetings booked", d.kpis.meetings],
                ["Success rate of connected calls", `${d.success_rate}%`], ["Denial rate of connected calls", `${d.denial_rate}%`], ["Follow-ups scheduled", d.followups.scheduled],
                ["Estimated call cost", money(d.cost_estimate)], ["Deals won (all time)", a.metrics.deals_won], ["Revenue (all time)", money(a.metrics.revenue)],
                ["Proposals submitted (all time)", a.metrics.proposals], ["Win rate", `${a.metrics.win_rate}%`]].map(([k, v]) => <tr key={k}><td>{k}</td><td className="num">{v}</td></tr>)}</tbody></table></div>
            <h3>Call outcomes</h3>
            <div className="scroll"><table className="tbl"><tbody>{d.outcomes.map(([k, v]) => <tr key={k}><td>{k}</td><td className="num">{v}</td></tr>)}{d.outcomes.length === 0 && <tr><td>No calls in this period.</td></tr>}</tbody></table></div>
            <h3>Results by priority band</h3>
            <div className="scroll"><table className="tbl"><thead><tr><th>Band</th><th className="num">Leads</th><th className="num">Called</th><th className="num">Positive</th><th className="num">Meetings</th><th className="num">Won</th></tr></thead>
              <tbody>{d.by_band.map((b) => <tr key={b.band}><td>{b.band}</td><td className="num">{b.leads}</td><td className="num">{b.called}</td><td className="num">{b.positive}</td><td className="num">{b.meetings}</td><td className="num">{b.won}</td></tr>)}</tbody></table></div>
            <h3>Revenue by month</h3>
            <div className="scroll"><table className="tbl"><tbody>{a.revenue_by_month.map(([m, v]) => <tr key={m}><td>{m}</td><td className="num">{money(v)}</td></tr>)}</tbody></table></div>
          </>}
        </section>
      </div>
    </>
  );
}
