/**
 * Alur lima langkah AI + blockchain: garis mengalir dengan titik bergerak (SMIL),
 * simpul AI sian dan blockchain ungu, kartu langkah di bawahnya.
 */
export type FlowStep = { tag: string; title: string; text: string };

const AI = "var(--accent)";
const CHAIN = "var(--chain)";

export function PipelineFlow({ steps, aiTag }: { steps: FlowStep[]; aiTag: string }) {
  const n = steps.length;
  const w = 1000;
  const y = 40;
  const xs = steps.map((_, i) => 80 + (i * (w - 160)) / Math.max(1, n - 1));
  const color = (s: FlowStep) => (s.tag === aiTag ? AI : CHAIN);
  return (
    <div className="flex flex-col gap-3">
      <svg viewBox={`0 0 ${w} 80`} className="hidden w-full md:block" aria-hidden="true">
        {xs.slice(0, -1).map((x, i) => (
          <g key={i}>
            <line x1={x + 22} x2={xs[i + 1] - 22} y1={y} y2={y} stroke="var(--line-2)" strokeWidth="2" />
            <line x1={x + 22} x2={xs[i + 1] - 22} y1={y} y2={y} stroke={color(steps[i + 1])} strokeWidth="2" className="flow-line" opacity="0.8" />
            {[0, 1].map((k) => (
              <circle key={k} r="3.5" fill={color(steps[i + 1])} className="flow-dot">
                <animateMotion dur="2.4s" begin={`${k * 1.2 + i * 0.3}s`} repeatCount="indefinite" path={`M${x + 22},${y} L${xs[i + 1] - 22},${y}`} />
              </circle>
            ))}
          </g>
        ))}
        {xs.map((x, i) => (
          <g key={i}>
            <circle cx={x} cy={y} r="22" fill="var(--surface)" stroke={color(steps[i])} strokeWidth="2" />
            <circle cx={x} cy={y} r="30" fill="none" stroke={color(steps[i])} strokeWidth="1" opacity="0.25" />
            <text x={x} y={y} dy="0.36em" textAnchor="middle" fontSize="15" fontWeight="600" fill="var(--fg)" fontFamily="var(--font-jet), monospace">
              {i + 1}
            </text>
          </g>
        ))}
      </svg>
      <ol className="grid gap-3 md:grid-cols-5">
        {steps.map((s, i) => {
          const ai = s.tag === aiTag;
          return (
            <li key={s.title} className="card lift flex min-h-[170px] flex-col gap-2.5 p-4" style={{ borderTopColor: color(s), borderTopWidth: 2 }}>
              <div className="flex items-center justify-between">
                <span className="font-mono text-[11px] text-muted md:hidden">0{i + 1}</span>
                <span className={`chip ${ai ? "chip-accent" : "chip-chain"}`}>{s.tag}</span>
              </div>
              <span className="text-[14.5px] font-semibold">{s.title}</span>
              <span className="text-[12.5px] leading-relaxed text-soft">{s.text}</span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
