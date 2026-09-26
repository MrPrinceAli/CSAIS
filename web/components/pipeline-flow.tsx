import { ProcessArt } from "@/components/process-art";

/**
 * Alur lima langkah AI + blockchain: garis tipis dengan titik mengalir (SMIL)
 * di atas kartu berilustrasi; nomor langkah kecil di dalam kartu.
 */
export type FlowStep = { tag: string; title: string; text: string };

const AI = "var(--accent)";
const CHAIN = "var(--chain)";

export function PipelineFlow({ steps, aiTag }: { steps: FlowStep[]; aiTag: string }) {
  const n = steps.length;
  const w = 1000;
  const y = 12;
  const xs = steps.map((_, i) => ((i + 0.5) * w) / n);
  const color = (s: FlowStep) => (s.tag === aiTag ? AI : CHAIN);
  return (
    <div className="flex flex-col gap-2">
      <svg viewBox={`0 0 ${w} 24`} className="hidden w-full md:block" aria-hidden="true">
        {xs.slice(0, -1).map((x, i) => (
          <g key={i}>
            <line x1={x + 8} x2={xs[i + 1] - 8} y1={y} y2={y} stroke="var(--line-2)" strokeWidth="1.5" />
            <line x1={x + 8} x2={xs[i + 1] - 8} y1={y} y2={y} stroke={color(steps[i + 1])} strokeWidth="1.5" className="flow-line" opacity="0.8" />
            <circle r="3" fill={color(steps[i + 1])} className="flow-dot">
              <animateMotion dur="2.4s" begin={`${i * 0.4}s`} repeatCount="indefinite" path={`M${x + 8},${y} L${xs[i + 1] - 8},${y}`} />
            </circle>
          </g>
        ))}
        {xs.map((x, i) => (
          <g key={i}>
            <circle cx={x} cy={y} r="6" fill="var(--surface)" stroke={color(steps[i])} strokeWidth="1.5" />
            <circle cx={x} cy={y} r="2.5" fill={color(steps[i])} />
          </g>
        ))}
      </svg>
      <ol className="grid gap-3 md:grid-cols-5">
        {steps.map((s, i) => {
          const ai = s.tag === aiTag;
          return (
            <li key={s.title} className="card lift flex flex-col gap-2.5 p-3.5" style={{ borderTopColor: color(s), borderTopWidth: 2 }}>
              <ProcessArt step={i} />
              <div className="flex items-center justify-between">
                <span className="font-mono text-[11px] text-muted">0{i + 1}</span>
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
