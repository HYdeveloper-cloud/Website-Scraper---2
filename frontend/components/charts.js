"use client";

const num = (n) => (n ?? 0).toLocaleString("en-US");

export function HBars({ rows, gold, fmt = num }) {
  if (!rows.length) return <p style={{ color: "var(--mute)" }}>Nothing yet.</p>;
  const max = Math.max(1, ...rows.map((r) => r[1]));
  return rows.map(([l, v]) => (
    <div className={`hbar ${gold ? "gold" : ""}`} key={l}><span>{l}</span><span><i style={{ width: `${(v / max) * 100}%` }} /></span><b>{fmt(v)}</b></div>
  ));
}

export function Bars({ data, labels, label, fmt = num }) {
  const max = Math.max(1, ...data), w = 560, h = 170, pad = 20, bw = (w - pad * 2) / data.length;
  return (
    <svg className="chart" viewBox={`0 0 ${w} ${h + 26}`} role="img" aria-label={label}>
      {data.map((v, i) => {
        const bh = (v / max) * (h - 26), x = pad + i * bw + 4;
        return (<g key={i}><rect x={x} y={h - bh} width={bw - 8} height={bh} fill="var(--gold)" />
          <text x={x + (bw - 8) / 2} y={h - bh - 5} textAnchor="middle" className="bar-val">{fmt(v)}</text>
          <text x={x + (bw - 8) / 2} y={h + 17} textAnchor="middle" className="bar-lab">{labels[i]}</text></g>);
      })}
      <line x1={pad} x2={w - pad} y1={h} y2={h} stroke="var(--maroon)" strokeWidth="3" />
    </svg>
  );
}
