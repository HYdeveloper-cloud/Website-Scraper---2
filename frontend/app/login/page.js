"use client";
import { useEffect, useState } from "react";
import { api, applyTheme, visualSrc } from "../../lib/api";

export default function Login() {
  const [company, setCompany] = useState("HY Developer");
  const [banner, setBanner] = useState(null);
  const [setup, setSetup] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [again, setAgain] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api("/api/public/theme").then((d) => { applyTheme(d.theme); setCompany(d.company_name); }).catch(() => {});
    api("/api/public/visuals").then((v) => setBanner(v.login_banner || null)).catch(() => {});
    api("/api/auth/setup-status").then((d) => setSetup(d.needs_setup)).catch(() => {});
  }, []);

  async function submit(e) {
    e.preventDefault();
    setError("");
    if (setup && password !== again) { setError("The two passwords are not the same."); return; }
    setBusy(true);
    try {
      const d = await api(setup ? "/api/auth/setup" : "/api/auth/login", { method: "POST", body: { email, password } });
      localStorage.setItem("hy_token", d.token);
      window.location.href = "/";
    } catch (err) { setError(err.message); }
    setBusy(false);
  }

  return (
    <main className="login">
      <section className="left" style={banner ? { backgroundImage: `url(${visualSrc("login_banner", banner)})`, backgroundSize: "cover", backgroundPosition: "center" } : undefined}>
        {!banner && <><h1>{company} Sales Engine</h1><p>Find the businesses that need you, call them, and track every deal to the close.</p></>}
      </section>
      <section className="right">
        <form onSubmit={submit}>
          <h2 style={{ marginBottom: 6 }}>{company}</h2>
          <p style={{ marginTop: 0, color: "var(--mute)" }}>{setup ? "Welcome. Create your owner account. Only you will use this program." : "Owner sign in"}</p>
          {error && <p className="msg err" role="alert">{error}</p>}
          <div className="field"><label htmlFor="e">Email</label>
            <input id="e" type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required /></div>
          <div className="field"><label htmlFor="p">Password</label>
            <input id="p" type="password" autoComplete={setup ? "new-password" : "current-password"} minLength={setup ? 10 : undefined} value={password} onChange={(e) => setPassword(e.target.value)} required />
            {setup && <span className="hint">At least 10 characters. There is no password reset, so keep it safe.</span>}</div>
          {setup && <div className="field"><label htmlFor="p2">Type the password again</label>
            <input id="p2" type="password" autoComplete="new-password" value={again} onChange={(e) => setAgain(e.target.value)} required /></div>}
          <button className="btn" disabled={busy}>{busy ? "Please wait" : setup ? "Create account" : "Sign in"}</button>
        </form>
      </section>
    </main>
  );
}
