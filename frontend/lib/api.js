export const API = process.env.NEXT_PUBLIC_API_URL || "";

export function getToken() {
  return typeof window === "undefined" ? null : localStorage.getItem("hy_token");
}

export async function api(path, { method = "GET", body } = {}) {
  const token = getToken();
  const r = await fetch(API + path, {
    method,
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await r.json().catch(() => ({}));
  if (r.status === 401 && !path.startsWith("/api/auth/login")) {
    localStorage.removeItem("hy_token");
    window.location.href = "/login";
    throw new Error("Session expired. Sign in again.");
  }
  if (!r.ok) {
    const d = data.detail;
    throw new Error(typeof d === "string" ? d : "That did not work. Check the fields and try again.");
  }
  return data;
}

export function applyTheme(t) {
  const root = document.documentElement;
  const map = { "--maroon": t.maroon, "--gold": t.gold, "--ivory": t.ivory, "--ink": t.ink };
  Object.entries(map).forEach(([k, v]) => v && root.style.setProperty(k, v));
}

export async function download(path, filename) {
  const r = await fetch(API + path, { headers: { Authorization: `Bearer ${getToken()}` } });
  if (!r.ok) throw new Error("The download failed.");
  const a = document.createElement("a");
  a.href = URL.createObjectURL(await r.blob());
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}

export const visualSrc = (slot, v) => `${API}/api/public/visual/${slot}?v=${v}`;
export const when = (iso) => (iso ? new Date(iso + (iso.endsWith("Z") ? "" : "Z")).toLocaleString() : "");
