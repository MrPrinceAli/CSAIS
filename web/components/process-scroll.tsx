"use client";

import { useEffect, useRef, useState } from "react";

/**
 * "Cara kerja" scroll-driven: panggung lengket di kiri berganti sesuai langkah
 * yang sedang berada di tengah layar, dengan gaya berbeda tiap langkah:
 *   1 kertas terang disapu stabilo   2 terminal hash dan pohon Merkle
 *   3 dial instrumen dengan jarum    4 radar merah dan daftar kelompok
 *   5 dokumen dicap dan dirantai
 * Di layar sempit, panggung tampil di atas teks masing-masing langkah.
 */
export type ProcessStep = { tag: string; title: string; text: string };

const MONO = "var(--font-jet), monospace";

function StageExtraction() {
  const lines = [
    { y: 62, w: 190 }, { y: 80, w: 220 }, { y: 98, w: 150 }, { y: 116, w: 210 },
    { y: 134, w: 170 }, { y: 152, w: 226 }, { y: 170, w: 120 }, { y: 188, w: 200 }, { y: 206, w: 180 },
  ];
  const marks = [
    { y: 76, x: 92, w: 78, c: "rgba(47,183,201,0.55)", i: 0 },
    { y: 112, x: 60, w: 96, c: "rgba(245,230,99,0.75)", i: 1 },
    { y: 166, x: 40, w: 60, c: "rgba(167,139,250,0.6)", i: 2 },
  ];
  const chips = [
    { y: 74, label: "korban · victim", c: "var(--accent)" },
    { y: 118, label: "jenis · type", c: "#e0c93a" },
    { y: 162, label: "tanggal · date", c: "var(--chain)" },
  ];
  return (
    <svg viewBox="0 0 480 300" className="h-full w-full" aria-hidden="true">
      <rect x="28" y="30" width="250" height="236" rx="6" fill="#f3f5f7" />
      <rect x="44" y="42" width="110" height="9" rx="2" fill="#1f2a36" />
      {lines.map((l, i) => (
        <rect key={i} x="44" y={l.y} width={l.w} height="5" rx="2" fill="#aab4bf" />
      ))}
      {marks.map((m) => (
        <rect key={m.i} x={m.x} y={m.y - 6} width={m.w} height="16" rx="3" fill={m.c} className="sweep" style={{ "--i": m.i } as React.CSSProperties} />
      ))}
      <g className="scan-y">
        <rect x="28" y="34" width="250" height="22" fill="url(#scanfade)" />
        <line x1="28" x2="278" y1="56" y2="56" stroke="var(--accent)" strokeWidth="1.5" />
      </g>
      <defs>
        <linearGradient id="scanfade" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0" stopColor="rgba(47,183,201,0)" />
          <stop offset="1" stopColor="rgba(47,183,201,0.35)" />
        </linearGradient>
      </defs>
      {chips.map((c, i) => (
        <g key={c.label} className="slide-r" style={{ "--i": i } as React.CSSProperties}>
          <line x1={marks[i].x + marks[i].w} x2="318" y1={marks[i].y + 2} y2={c.y + 12} stroke={c.c} strokeWidth="1" strokeDasharray="3 3" opacity="0.8" />
          <rect x="318" y={c.y} width="132" height="26" rx="5" fill="var(--bg)" stroke={c.c} strokeWidth="1.2" />
          <text x="330" y={c.y + 17} fontSize="11" fill={c.c} fontFamily={MONO}>
            {c.label}
          </text>
        </g>
      ))}
      <g className="slide-r" style={{ "--i": 3 } as React.CSSProperties}>
        <rect x="318" y="214" width="132" height="42" rx="6" fill="var(--bg)" stroke="var(--accent)" strokeWidth="1.5" />
        <circle cx="336" cy="235" r="5" fill="var(--accent)" />
        <text x="348" y="231" fontSize="10.5" fill="var(--fg)" fontFamily={MONO}>
          incident
        </text>
        <text x="348" y="246" fontSize="10.5" fill="var(--muted)" fontFamily={MONO}>
          +1 sumber · source
        </text>
      </g>
    </svg>
  );
}

function StageEvidence() {
  const rows = ["sha256(artikel#1) 3f9a1c…b7d0", "sha256(artikel#2) 91be44…0e2a", "sha256(artikel#3) c04d7e…ff13", "sha256(artikel#4) 7a2210…9c58"];
  const leaves = [70, 108, 146, 184];
  return (
    <svg viewBox="0 0 480 300" className="h-full w-full" aria-hidden="true">
      <rect x="20" y="24" width="440" height="252" rx="6" fill="#05080c" stroke="var(--line)" />
      <circle cx="36" cy="38" r="3.5" fill="var(--crit)" />
      <circle cx="48" cy="38" r="3.5" fill="var(--high)" />
      <circle cx="60" cy="38" r="3.5" fill="var(--good)" />
      {rows.map((r, i) => (
        <text key={r} x="36" y={leaves[i] + 4} fontSize="10.5" fill="var(--accent)" fontFamily={MONO} className="type-line" style={{ "--i": i } as React.CSSProperties}>
          {r}
        </text>
      ))}
      {leaves.map((y, i) => (
        <g key={y}>
          <rect x="248" y={y - 6} width="12" height="12" rx="2" fill="var(--accent)" className="type-line" style={{ "--i": i } as React.CSSProperties} />
          <path d={`M260 ${y} L 300 ${i < 2 ? 89 : 165}`} fill="none" stroke="var(--line-2)" strokeWidth="1.5" pathLength={1} className="draw" style={{ "--i": i + 4 } as React.CSSProperties} />
        </g>
      ))}
      {[89, 165].map((y, i) => (
        <g key={y}>
          <rect x="300" y={y - 6} width="12" height="12" rx="2" fill="var(--bg)" stroke="var(--accent)" strokeWidth="1.5" />
          <path d={`M312 ${y} L 350 127`} fill="none" stroke="var(--line-2)" strokeWidth="1.5" pathLength={1} className="draw" style={{ "--i": 9 + i } as React.CSSProperties} />
        </g>
      ))}
      <rect x="350" y="119" width="16" height="16" rx="3" fill="var(--chain)" className="pulse-node" />
      <text x="358" y="150" textAnchor="middle" fontSize="10" fill="var(--chain)" fontFamily={MONO}>
        root
      </text>
      <path d="M366 127 L 400 127" stroke="var(--chain)" strokeWidth="1.5" strokeDasharray="4 4" className="flow-line" />
      <g transform="translate(400 100)">
        <rect width="44" height="54" rx="5" fill="var(--bg)" stroke="var(--chain)" strokeWidth="1.5" />
        <rect x="9" y="12" width="26" height="4" rx="1" fill="var(--chain)" opacity="0.8" />
        <rect x="9" y="22" width="18" height="4" rx="1" fill="var(--chain)" opacity="0.5" />
        <rect x="9" y="32" width="22" height="4" rx="1" fill="var(--chain)" opacity="0.35" />
        <text x="22" y="70" textAnchor="middle" fontSize="9.5" fill="var(--muted)" fontFamily={MONO}>
          on-chain
        </text>
      </g>
      <text x="36" y="232" fontSize="10.5" fill="var(--soft)" fontFamily={MONO} className="type-line" style={{ "--i": 5 } as React.CSSProperties}>
        merkle_root = 04b942…cfa4a
      </text>
      <text x="36" y="252" fontSize="10.5" fill="var(--chain)" fontFamily={MONO} className="type-line" style={{ "--i": 6 } as React.CSSProperties}>
        batch #51 · 607 daun · leaves
        <tspan className="caret" />
      </text>
    </svg>
  );
}

function StageConfidence() {
  const cx = 170;
  const cy = 190;
  const r = 118;
  const arc = (a0: number, a1: number) => {
    const p = (a: number) => [cx + r * Math.cos((Math.PI * a) / 180), cy - r * Math.sin((Math.PI * a) / 180)];
    const [x0, y0] = p(a0);
    const [x1, y1] = p(a1);
    return `M${x0.toFixed(1)} ${y0.toFixed(1)} A${r} ${r} 0 0 1 ${x1.toFixed(1)} ${y1.toFixed(1)}`;
  };
  const score = 78;
  const deg = -90 + (score / 100) * 180;
  const bars = [
    { k: "domain", v: 0.9 }, { k: "independen", v: 0.75 }, { k: "korban", v: 0.9 }, { k: "teks", v: 0.4 }, { k: "klaster", v: 0.85 },
  ];
  return (
    <svg viewBox="0 0 480 300" className="h-full w-full" aria-hidden="true">
      <path d={arc(180, 120)} fill="none" stroke="var(--crit)" strokeWidth="14" strokeLinecap="butt" opacity="0.85" />
      <path d={arc(120, 60)} fill="none" stroke="var(--med)" strokeWidth="14" opacity="0.85" />
      <path d={arc(60, 0)} fill="none" stroke="var(--good)" strokeWidth="14" opacity="0.85" />
      {Array.from({ length: 11 }, (_, i) => {
        const a = 180 - i * 18;
        const x = cx + (r - 18) * Math.cos((Math.PI * a) / 180);
        const y = cy - (r - 18) * Math.sin((Math.PI * a) / 180);
        return <circle key={i} cx={x} cy={y} r="1.8" fill="var(--muted)" />;
      })}
      <g className="needle" style={{ "--deg": `${deg}deg` } as React.CSSProperties}>
        <polygon points={`${cx - 4},${cy} ${cx + 4},${cy} ${cx},${cy - 100}`} fill="var(--fg)" />
      </g>
      <circle cx={cx} cy={cy} r="9" fill="var(--surface)" stroke="var(--fg)" strokeWidth="2" />
      <text x={cx} y={cy + 40} textAnchor="middle" fontSize="30" fontWeight="600" fill="var(--fg)" fontFamily={MONO}>
        {score}
      </text>
      <text x={cx} y={cy + 58} textAnchor="middle" fontSize="10.5" fill="var(--good)" fontFamily={MONO}>
        tinggi · high
      </text>
      {bars.map((b, i) => (
        <g key={b.k}>
          <rect x={330 + i * 26} y={210 - 130 * b.v} width="16" height={130 * b.v} rx="2" fill={b.v >= 0.7 ? "var(--good)" : "var(--med)"} className="bar-rise" style={{ "--i": i * 8 } as React.CSSProperties} />
          <text x={338 + i * 26} y="228" textAnchor="middle" fontSize="8.5" fill="var(--muted)" fontFamily={MONO} transform={`rotate(-35 ${338 + i * 26} 228)`}>
            {b.k}
          </text>
        </g>
      ))}
      <line x1="326" x2="464" y1="211" y2="211" stroke="var(--line-2)" />
    </svg>
  );
}

function StageFindings() {
  const blips = [
    { x: 92, y: 118, i: 0 }, { x: 150, y: 96, i: 1 }, { x: 74, y: 178, i: 2 }, { x: 160, y: 190, i: 3 }, { x: 128, y: 148, i: 4 },
  ];
  const groups = [
    { k: "individu", v: 0.95, d: "+31%" }, { k: "perusahaan", v: 0.6, d: "+20%" }, { k: "pelajar", v: 0.45, d: "+130%" }, { k: "nasabah", v: 0.25, d: "+200%" },
  ];
  return (
    <svg viewBox="0 0 480 300" className="h-full w-full" aria-hidden="true">
      {[40, 80, 120].map((rr) => (
        <circle key={rr} cx="120" cy="150" r={rr} fill="none" stroke="rgba(242,85,90,0.35)" />
      ))}
      <line x1="0" x2="240" y1="150" y2="150" stroke="rgba(242,85,90,0.2)" />
      <line x1="120" x2="120" y1="30" y2="270" stroke="rgba(242,85,90,0.2)" />
      <path d="M120 150 L 240 150 A 120 120 0 0 0 204.9 65.1 Z" fill="rgba(242,85,90,0.22)" className="sweep-arm" />
      {blips.map((b) => (
        <g key={b.i}>
          <circle cx={b.x} cy={b.y} r="4" fill="var(--crit)" />
          <circle cx={b.x} cy={b.y} r="4" fill="none" stroke="var(--crit)" strokeWidth="1.5" className="blip" style={{ "--i": b.i } as React.CSSProperties} />
        </g>
      ))}
      {groups.map((g, i) => (
        <g key={g.k}>
          <text x="268" y={74 + i * 46} fontSize="11" fill="var(--fg)" fontFamily={MONO}>
            {g.k}
          </text>
          <text x="456" y={74 + i * 46} textAnchor="end" fontSize="11" fill="var(--high)" fontFamily={MONO}>
            {g.d}
          </text>
          <rect x="268" y={82 + i * 46} width="188" height="8" rx="2" fill="var(--line)" />
          <rect x="268" y={82 + i * 46} width={188 * g.v} height="8" rx="2" fill="var(--crit)" className="bar-fill" style={{ "--i": i * 4 } as React.CSSProperties} />
        </g>
      ))}
      <path d="M268 252 l 10 -5 l 10 5 v 10 c 0 7 -5 11 -10 13 c -5 -2 -10 -6 -10 -13 z" fill="var(--bg)" stroke="var(--good)" strokeWidth="1.5" />
      <path d="M273 262 l 4 4 l 7 -7" fill="none" stroke="var(--good)" strokeWidth="1.5" />
      <text x="296" y="266" fontSize="10.5" fill="var(--soft)" fontFamily={MONO}>
        pencegahan · prevention
      </text>
    </svg>
  );
}

function StagePackage() {
  return (
    <svg viewBox="0 0 480 300" className="h-full w-full" aria-hidden="true">
      <rect x="40" y="30" width="190" height="240" rx="6" fill="var(--bg)" stroke="var(--chain)" strokeWidth="1.5" />
      <rect x="58" y="50" width="100" height="8" rx="2" fill="var(--fg)" opacity="0.9" />
      {[74, 88, 102, 116, 130].map((y, i) => (
        <rect key={y} x="58" y={y} width={i % 2 ? 110 : 150} height="5" rx="2" fill="var(--line-2)" />
      ))}
      <path d="M58 200 C 74 176, 84 176, 92 198 S 118 214, 132 186 S 160 178, 168 200 S 190 212, 208 192" fill="none" stroke="var(--chain)" strokeWidth="2" strokeLinecap="round" pathLength={1} className="draw" />
      <line x1="58" x2="212" y1="212" y2="212" stroke="var(--line-2)" />
      <text x="58" y="228" fontSize="9.5" fill="var(--muted)" fontFamily={MONO}>
        EIP-712 · relayer
      </text>
      <g className="stamp">
        <circle cx="180" cy="120" r="34" fill="none" stroke="#e0c93a" strokeWidth="2.5" />
        <circle cx="180" cy="120" r="27" fill="none" stroke="#e0c93a" strokeWidth="1" strokeDasharray="3 3" />
        <path d="M166 120 l 9 9 l 19 -19" fill="none" stroke="#e0c93a" strokeWidth="3.5" strokeLinecap="round" />
      </g>
      <path d="M230 150 L 268 150" stroke="var(--chain)" strokeWidth="1.5" strokeDasharray="4 4" className="flow-line" />
      {[0, 1, 2].map((i) => (
        <g key={i} transform={`translate(${268 + i * 64} 118)`}>
          <g className="fade-in" style={{ "--i": i * 5 + 2 } as React.CSSProperties}>
            <rect width="48" height="64" rx="6" fill="var(--bg)" stroke={i === 2 ? "#e0c93a" : "var(--chain)"} strokeWidth="1.5" />
            <rect x="10" y="14" width="28" height="4" rx="1" fill="var(--chain)" opacity="0.8" />
            <rect x="10" y="24" width="20" height="4" rx="1" fill="var(--chain)" opacity="0.5" />
            <rect x="10" y="34" width="24" height="4" rx="1" fill="var(--chain)" opacity="0.35" />
            <text x="24" y="54" textAnchor="middle" fontSize="8.5" fill="var(--muted)" fontFamily={MONO}>
              {i === 2 ? "paket" : "bukti"}
            </text>
            {i < 2 ? <path d="M48 32 L 64 32" stroke="var(--chain)" strokeWidth="1.5" /> : null}
          </g>
        </g>
      ))}
      <text x="356" y="214" textAnchor="middle" fontSize="10" fill="var(--soft)" fontFamily={MONO}>
        hash paket → tautan ke batch bukti
      </text>
    </svg>
  );
}

const STAGES = [StageExtraction, StageEvidence, StageConfidence, StageFindings, StagePackage];

function Stage({ step, className = "" }: { step: number; className?: string }) {
  const S = STAGES[step] ?? StageExtraction;
  return (
    <div key={step} className={`stage-enter stage-${step + 1} corners overflow-hidden rounded-lg border border-line ${className}`}>
      <S />
    </div>
  );
}

export function ProcessScroll({ steps, aiTag, hint }: { steps: ProcessStep[]; aiTag: string; hint: string }) {
  const [active, setActive] = useState(0);
  const refs = useRef<(HTMLLIElement | null)[]>([]);

  useEffect(() => {
    if (!("IntersectionObserver" in window)) return;
    const io = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) setActive(Number((entry.target as HTMLElement).dataset.step ?? 0));
        }
      },
      { rootMargin: "-42% 0px -42% 0px", threshold: 0 },
    );
    refs.current.forEach((el) => el && io.observe(el));
    return () => io.disconnect();
  }, []);

  const color = (s: ProcessStep) => (s.tag === aiTag ? "var(--accent)" : "var(--chain)");

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1.05fr)_minmax(0,0.95fr)] lg:gap-10">
      {/* panggung lengket (layar lebar) */}
      <div className="hidden lg:block">
        <div className="sticky top-24 flex flex-col gap-3">
          <Stage step={active} className="aspect-[480/300]" />
          <div className="flex items-center justify-between font-mono text-[11px] text-muted">
            <span>
              {String(active + 1).padStart(2, "0")} / {String(steps.length).padStart(2, "0")}
            </span>
            <span>{hint}</span>
          </div>
        </div>
      </div>

      {/* daftar langkah dengan rel kemajuan */}
      <ol className="relative flex flex-col">
        <span className="absolute left-[9px] top-6 bottom-6 hidden w-px bg-line lg:block" aria-hidden="true" />
        {steps.map((s, i) => (
          <li
            key={s.title}
            ref={(el) => {
              refs.current[i] = el;
            }}
            data-step={i}
            data-active={active === i}
            className="step-item grid grid-cols-[20px_minmax(0,1fr)] gap-4 py-8 lg:min-h-[62vh] lg:py-10"
          >
            <span className="rail-dot relative mt-1.5 inline-block h-5 w-5 rounded-full border-2 bg-bg" data-active={active === i} style={{ borderColor: color(s), background: active === i ? color(s) : "var(--bg)" }} aria-hidden="true" />
            <div className="flex min-w-0 flex-col gap-3">
              <Stage step={i} className="aspect-[480/300] lg:hidden" />
              <div className="flex items-center gap-3">
                <span className="font-mono text-[11px] text-muted">0{i + 1}</span>
                <span className={`chip ${s.tag === aiTag ? "chip-accent" : "chip-chain"}`}>{s.tag}</span>
              </div>
              <h3 className="text-[22px] font-semibold leading-tight">{s.title}</h3>
              <p className="max-w-[46ch] text-[14.5px] leading-relaxed text-soft">{s.text}</p>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
