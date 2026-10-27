"use client";
import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { api, applyTheme, getToken, visualSrc } from "../../lib/api";
import { NAV } from "../../lib/nav";
import { VisualsContext } from "../../lib/visuals";

export default function AppLayout({ children }) {
  const path = usePathname();
  const [me, setMe] = useState(null);
  const [company, setCompany] = useState("HY Developer");
  const [vis, setVis] = useState({});

  useEffect(() => {
    if (!getToken()) { window.location.href = "/login"; return; }
    api("/api/auth/me").then((d) => setMe(d.email)).catch(() => {});
    api("/api/settings").then((s) => { if (s.theme) applyTheme(s.theme); if (s.general) setCompany(s.general.company_name); }).catch(() => {});
    api("/api/public/visuals").then(setVis).catch(() => {});
  }, []);

  function logout() { localStorage.removeItem("hy_token"); window.location.href = "/login"; }
  if (!me) return <p style={{ padding: 32 }}>Loading</p>;

  return (
    <VisualsContext.Provider value={vis}>
      <div className="shell">
        <aside className="side">
          <div className="brand">
            {vis.logo ? <img className="sidelogo" src={visualSrc("logo", vis.logo)} alt={company} /> : <b>{company}</b>}
            <span>Sales Engine</span>
          </div>
          <nav className="nav" aria-label="Main">
            {NAV.map(([href, label]) => {
              const on = href === "/" ? path === "/" : path.startsWith(href);
              return <a key={href} href={href} className={on ? "on" : ""} aria-current={on ? "page" : undefined}>{label}</a>;
            })}
          </nav>
          <div className="who">{me}<br /><button onClick={logout}>Sign out</button></div>
        </aside>
        <div className="main">{children}</div>
      </div>
    </VisualsContext.Provider>
  );
}
