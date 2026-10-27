"use client";
import { useEffect, useRef, useState } from "react";
import { api, when } from "../../../lib/api";

const LABEL = { logo: "Logo (sidebar)", login_banner: "Login banner", dashboard_header: "Dashboard header", report_header: "Report header", agent_image: "Agent picture" };
const FONTS = ["Georgia", "Times New Roman", "Segoe UI", "Arial", "Verdana"];
let counter = 1;
const nid = () => `e${Date.now().toString(36)}${counter++}`;

function defaultLayout(w, h, company, theme) {
  return { bg: theme.maroon, elements: [
    { id: nid(), type: "rect", x: 0, y: h - Math.round(h * 0.12), w, h: Math.round(h * 0.12), rotation: 0, fill: theme.gold },
    { id: nid(), type: "text", x: Math.round(w * 0.06), y: Math.round(h * 0.3), w: Math.round(w * 0.88), text: company, fontSize: Math.max(16, Math.round(Math.min(w * 0.09, h * 0.28))), fontFamily: "Georgia", fill: "#FFFFFF", rotation: 0 }] };
}

export default function Visuals() {
  const holder = useRef(null);
  const S = useRef({});                      // Konva, stage, layer, transformer, size
  const model = useRef({ bg: "#330908", elements: [] });
  const hist = useRef([]);
  const fut = useRef([]);
  const selId = useRef(null);
  const meta = useRef({ company: "HY Developer", theme: { maroon: "#330908", gold: "#C0A559" } });
  const [slots, setSlots] = useState({});
  const [slot, setSlot] = useState("logo");
  const [ready, setReady] = useState(false);
  const [versions, setVersions] = useState([]);
  const [, bump] = useState(0);
  const [msg, setMsg] = useState({ kind: "", text: "" });
  const sel = () => model.current.elements.find((e) => e.id === selId.current) || null;
  const say = (kind, text) => setMsg({ kind, text });

  useEffect(() => {
    let off = false;
    import("konva").then((m) => { if (!off) { S.current.K = m.default; setReady(true); } });
    api("/api/visual-slots").then(setSlots).catch((e) => say("err", e.message));
    api("/api/settings").then((s) => { meta.current = { company: s.general.company_name, theme: s.theme }; }).catch(() => {});
    return () => { off = true; S.current.stage && S.current.stage.destroy(); };
  }, []);

  useEffect(() => { if (ready && slots[slot]) openSlot(slot); }, [ready, slot, slots]);

  async function openSlot(sl, version = 0) {
    const { width: w, height: h } = slots[sl];
    const d = await api(`/api/visuals/${sl}${version ? `?version=${version}` : ""}`).catch((e) => { say("err", e.message); return null; });
    if (!d) return;
    setVersions(d.versions);
    model.current = d.layout ? JSON.parse(JSON.stringify(d.layout)) : defaultLayout(w, h, meta.current.company, meta.current.theme);
    hist.current = [JSON.stringify(model.current)]; fut.current = []; selId.current = null;
    buildStage(w, h); bump((n) => n + 1);
  }

  function buildStage(w, h) {
    const K = S.current.K;
    if (S.current.stage) S.current.stage.destroy();
    const avail = Math.min((holder.current.parentElement.clientWidth || 900) - 8, 900), scale = Math.min(1, avail / w);
    const stage = new K.Stage({ container: holder.current, width: Math.round(w * scale), height: Math.round(h * scale) });
    stage.scale({ x: scale, y: scale });
    const layer = new K.Layer(); stage.add(layer);
    stage.on("click tap", (e) => { if (e.target === stage || e.target.name() === "bg") select(null); });
    S.current = { ...S.current, stage, layer, scale, w, h };
    render();
  }

  function render() {
    const { K, layer, w, h } = S.current;
    layer.destroyChildren();
    layer.add(new K.Rect({ x: 0, y: 0, width: w, height: h, fill: model.current.bg, name: "bg" }));
    model.current.elements.forEach((el) => {
      let node;
      if (el.type === "rect") node = new K.Rect({ width: el.w, height: el.h, fill: el.fill });
      else if (el.type === "text") node = new K.Text({ text: el.text, fontSize: el.fontSize, fontFamily: el.fontFamily, fill: el.fill, width: el.w, lineHeight: 1.15 });
      else { node = new K.Image({ width: el.w, height: el.h }); const im = new window.Image(); im.onload = () => { node.image(im); layer.batchDraw(); }; im.src = el.src; }
      node.setAttrs({ x: el.x, y: el.y, rotation: el.rotation || 0, draggable: true, id: el.id, name: "el" });
      node.on("click tap", () => select(el.id));
      node.on("dragend transformend", () => sync(node, el));
      layer.add(node);
    });
    const tr = new K.Transformer({ rotateEnabled: true, boundBoxFunc: (o, n) => (n.width < 10 || n.height < 10 ? o : n) });
    layer.add(tr); S.current.tr = tr;
    const node = selId.current && layer.findOne("#" + selId.current);
    tr.nodes(node ? [node] : []);
    layer.batchDraw();
  }

  function commit() {
    hist.current.push(JSON.stringify(model.current)); if (hist.current.length > 40) hist.current.shift();
    fut.current = []; bump((n) => n + 1);
  }
  function select(id) { selId.current = id; render(); bump((n) => n + 1); }
  function sync(node, el) {
    const sx = node.scaleX(), sy = node.scaleY();
    el.x = Math.round(node.x()); el.y = Math.round(node.y()); el.rotation = Math.round(node.rotation());
    if (el.type === "text") { el.w = Math.max(20, Math.round(node.width() * sx)); el.fontSize = Math.max(8, Math.round(el.fontSize * sy)); }
    else { el.w = Math.max(4, Math.round(node.width() * sx)); el.h = Math.max(4, Math.round(node.height() * sy)); }
    node.scale({ x: 1, y: 1 }); commit(); render();
  }
  function patch(p) { const el = sel(); if (!el) return; Object.assign(el, p); commit(); render(); }
  function add(el) { const full = { id: nid(), rotation: 0, ...el }; model.current.elements.push(full); selId.current = full.id; commit(); render(); }
  function restore(json) { model.current = JSON.parse(json); selId.current = null; render(); bump((n) => n + 1); }
  const undo = () => { if (hist.current.length > 1) { fut.current.push(hist.current.pop()); restore(hist.current[hist.current.length - 1]); } };
  const redo = () => { const j = fut.current.pop(); if (j) { hist.current.push(j); restore(j); } };
  function order(dir) {
    const a = model.current.elements, i = a.findIndex((e) => e.id === selId.current), j = i + dir;
    if (i < 0 || j < 0 || j >= a.length) return; [a[i], a[j]] = [a[j], a[i]]; commit(); render();
  }
  function remove() { model.current.elements = model.current.elements.filter((e) => e.id !== selId.current); selId.current = null; commit(); render(); }

  function addImage(file) {
    if (!file) return;
    const fr = new FileReader();
    fr.onload = () => {
      const img = new window.Image();
      img.onload = () => {
        const k = Math.min(1, 1000 / Math.max(img.width, img.height)), c = document.createElement("canvas");
        c.width = Math.round(img.width * k); c.height = Math.round(img.height * k); c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
        const { w, h } = S.current, fit = Math.min(1, (w * 0.5) / c.width, (h * 0.8) / c.height);
        add({ type: "image", x: 20, y: 20, w: Math.round(c.width * fit), h: Math.round(c.height * fit), src: c.toDataURL("image/png") });
      };
      img.src = fr.result;
    };
    fr.readAsDataURL(file);
  }

  async function save() {
    say("", "");
    try {
      selId.current = null; render();
      const png = S.current.stage.toDataURL({ pixelRatio: 1 / S.current.scale, mimeType: "image/png" });
      const r = await api(`/api/visuals/${slot}`, { method: "POST", body: { layout: model.current, png } });
      say("ok", `Saved as version ${r.version} and now in use.`);
      const d = await api(`/api/visuals/${slot}`); setVersions(d.versions);
    } catch (e) { say("err", e.message); }
  }
  async function activate(v) { try { await api(`/api/visuals/${slot}/activate/${v}`, { method: "POST" }); say("ok", `Version ${v} is now in use.`); setVersions((await api(`/api/visuals/${slot}`)).versions); } catch (e) { say("err", e.message); } }
  async function resetDefault() {
    if (!window.confirm("Go back to the standard look for this visual? Your saved versions are kept.")) return;
    try { await api(`/api/visuals/${slot}/active`, { method: "DELETE" }); say("ok", "The standard look is back in use."); openSlot(slot); } catch (e) { say("err", e.message); }
  }

  const el = sel();
  return (
    <>
      <header className="top"><h1>Edit visuals</h1><a className="btn line" href="/settings" style={{ textDecoration: "none" }}>Back to Settings</a></header>
      <div className="page">
        {msg.text && <p className={`msg ${msg.kind}`} role="status">{msg.text}</p>}
        <div className="pills" role="tablist" style={{ flexWrap: "wrap" }}>{Object.keys(slots).map((k) => <button key={k} role="tab" aria-selected={slot === k} className={slot === k ? "on" : ""} onClick={() => setSlot(k)}>{LABEL[k] || k}</button>)}</div>
        <p>{slots[slot] ? `${LABEL[slot]}: ${slots[slot].width} by ${slots[slot].height} pixels. ` : ""}Click an element to select it, drag to move, use the handles to resize or rotate. Save to use the result across the system.</p>

        <div className="grid2" style={{ gridTemplateColumns: "2fr 1fr" }}>
          <section className="panel" style={{ maxHeight: "none" }}>
            <div className="row no-print" style={{ marginBottom: 12 }}>
              <button className="btn gold" onClick={() => add({ type: "text", x: 20, y: 20, w: Math.round((S.current.w || 400) * 0.5), text: "New text", fontSize: Math.max(14, Math.round((S.current.h || 100) * 0.16)), fontFamily: "Georgia", fill: "#FFFFFF" })}>Add text</button>
              <button className="btn gold" onClick={() => add({ type: "rect", x: 20, y: 20, w: Math.round((S.current.w || 400) * 0.3), h: Math.round((S.current.h || 100) * 0.25), fill: meta.current.theme.gold })}>Add shape</button>
              <label className="btn gold" style={{ cursor: "pointer" }}>Add image<input type="file" accept="image/*" hidden onChange={(e) => { addImage(e.target.files[0]); e.target.value = ""; }} /></label>
              <button className="btn line" onClick={undo} disabled={hist.current.length < 2}>Undo</button>
              <button className="btn line" onClick={redo} disabled={!fut.current.length}>Redo</button>
            </div>
            <div className="canvaswrap"><div ref={holder} /></div>
            <div className="row" style={{ marginTop: 14 }}>
              <button className="btn" onClick={save}>Save and use</button>
              <button className="btn line" onClick={resetDefault}>Back to the standard look</button>
            </div>
          </section>

          <div>
            <section className="panel" style={{ maxHeight: "none" }}><h2>{el ? (el.type === "text" ? "Text" : el.type === "rect" ? "Shape" : "Image") : "Background"}</h2>
              {!el && <div className="field"><label htmlFor="bg">Background color</label><input id="bg" type="color" value={model.current.bg} onChange={(e) => { model.current.bg = e.target.value; commit(); render(); }} style={{ height: 44 }} /></div>}
              {el && el.type === "text" && <>
                <div className="field"><label htmlFor="tx">Text</label><textarea id="tx" value={el.text} onChange={(e) => patch({ text: e.target.value })} style={{ minHeight: 70, fontFamily: "inherit" }} /></div>
                <div className="row"><div className="field" style={{ flex: "1 1 90px" }}><label htmlFor="fs">Size</label><input id="fs" type="number" min={8} max={400} value={el.fontSize} onChange={(e) => patch({ fontSize: Math.max(8, +e.target.value || 8) })} /></div>
                  <div className="field" style={{ flex: "2 1 130px" }}><label htmlFor="ff">Font</label><select id="ff" value={el.fontFamily} onChange={(e) => patch({ fontFamily: e.target.value })}>{FONTS.map((f) => <option key={f}>{f}</option>)}</select></div></div></>}
              {el && el.type !== "image" && <div className="field"><label htmlFor="fl">Color</label><input id="fl" type="color" value={el.fill} onChange={(e) => patch({ fill: e.target.value })} style={{ height: 44 }} /></div>}
              {el && <div className="row"><button className="btn line" onClick={() => order(1)}>Bring forward</button><button className="btn line" onClick={() => order(-1)}>Send back</button><button className="btn line" onClick={remove}>Delete</button></div>}
              {!el && <p className="hint">Select an element on the canvas to change it.</p>}
            </section>
            <section className="panel" style={{ maxHeight: "none" }}><h2>Saved versions</h2>
              {versions.length === 0 ? <p>None yet. The standard look is in use.</p> : (
                <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>{versions.map((v) => (
                  <li key={v.version} style={{ padding: "6px 0", borderTop: "1px solid var(--rule)" }}><b>Version {v.version}</b>{v.active && <span className="chip on" style={{ marginLeft: 8 }}>In use</span>}<br />
                    <span style={{ color: "var(--mute)" }}>{when(v.created_at)}</span><br />
                    <button className="linklike" onClick={() => openSlot(slot, v.version)}>Open in editor</button>{!v.active && <> {" | "} <button className="linklike" onClick={() => activate(v.version)}>Use this version</button></>}</li>))}</ul>)}
            </section>
          </div>
        </div>
      </div>
    </>
  );
}
