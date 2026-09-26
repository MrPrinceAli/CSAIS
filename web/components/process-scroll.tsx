"use client";

import { useEffect, useRef, useState } from "react";

/**
 * "Cara kerja" yang mengikuti gulir. Panggung lengket di kiri berganti sesuai
 * langkah di tengah layar, dan di dalam satu langkah setiap unsur digerakkan
 * oleh --p (0 saat langkah masuk, 1 saat keluar) yang diatur JS tiap frame:
 *   1 kertas terang: paralaks lapisan, stabilo menyapu mengikuti gulir
 *   2 terminal: zoom masuk ke akar Merkle, baris hash muncul berurutan
 *   3 dial: jarum berayun mengikuti gulir, batang sinyal tumbuh
 *   4 radar: lengan berputar mengikuti gulir, titik merah menyala bertahap
 *   5 dokumen: cap turun di tengah langkah, blok rantai masuk dari kanan
 * Tanpa JS atau reduced motion, --p bernilai tetap 0,75.
 */
export type ProcessStep = { tag: string; title: string; text: string };

const MONO = "var(--font-jet), monospace";
/** Ekspresi CSS 0..1 yang mulai naik pada --p = from dengan kecepatan speed. */
const rise = (from: number, speed: number) => `clamp(0, (var(--p) - ${from}) * ${speed}, 1)`;
const css = (transform: string, extra: React.CSSProperties = {}): React.CSSProperties => ({ transform, ...extra });

function Blob({ className, style }: { className: string; style: React.CSSProperties }) {
  return <div className={`layer pointer-events-none absolute rounded-full blur-3xl ${className}`} style={style} aria-hidden="true" />;
}

function StageExtraction() {
  const lines = [62, 80, 98, 116, 134, 152, 170, 188, 206];
  const widths = [190, 220, 150, 210, 170, 226, 120, 200, 180];
  const marks = [
    { y: 76, x: 92, w: 78, c: "rgba(47,183,201,0.55)" },
    { y: 112, x: 60, w: 96, c: "rgba(245,230,99,0.75)" },
    { y: 166, x: 40, w: 60, c: "rgba(167,139,250,0.6)" },
  ];
  const chips = [
    { y: 74, label: "korban · victim", c: "var(--accent)" },
    { y: 118, label: "jenis · type", c: "#e0c93a" },
    { y: 162, label: "tanggal · date", c: "var(--chain)" },
  ];
  return (
    <>
      <Blob className="-left-16 -top-16 h-64 w-64 bg-accent/20" style={css("translate3d(0, calc(var(--p) * -50px), 0)")} />
      <Blob className="-bottom-20 right-10 h-56 w-56 bg-[rgba(245,230,99,0.16)]" style={css("translate3d(0, calc(var(--p) * 40px), 0)")} />
      <svg viewBox="0 0 480 300" className="relative h-full w-full" aria-hidden="true">
        <g style={css("translateY(calc(var(--p) * -14px)) scale(calc(0.96 + var(--p) * 0.06))", { transformOrigin: "150px 150px" })}>
          <rect x="28" y="30" width="250" height="236" rx="6" fill="#f3f5f7" />
          <rect x="44" y="42" width="110" height="9" rx="2" fill="#1f2a36" />
          {lines.map((y, i) => (
            <rect key={y} x="44" y={y} width={widths[i]} height="5" rx="2" fill="#aab4bf" />
          ))}
          {marks.map((m, i) => (
            <rect key={m.y} x={m.x} y={m.y - 6} width={m.w} height="16" rx="3" fill={m.c} style={css(`scaleX(${rise(0.08 + i * 0.16, 4)})`, { transformBox: "fill-box", transformOrigin: "left center" })} />
          ))}
          <g style={css("translateY(calc(var(--p) * 205px))", { opacity: "calc(1 - var(--p) * 1.1)" })}>
            <rect x="28" y="34" width="250" height="22" fill="url(#scanfade)" />
            <line x1="28" x2="278" y1="56" y2="56" stroke="var(--accent)" strokeWidth="1.5" />
          </g>
        </g>
        <defs>
          <linearGradient id="scanfade" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0" stopColor="rgba(47,183,201,0)" />
            <stop offset="1" stopColor="rgba(47,183,201,0.35)" />
          </linearGradient>
        </defs>
        {chips.map((c, i) => (
          <g key={c.label} style={css(`translateX(calc((1 - ${rise(0.2 + i * 0.16, 3)}) * 40px))`, { opacity: rise(0.2 + i * 0.16, 3) })}>
            <line x1={marks[i].x + marks[i].w} x2="318" y1={marks[i].y + 2} y2={c.y + 12} stroke={c.c} strokeWidth="1" strokeDasharray="3 3" opacity="0.8" />
            <rect x="318" y={c.y} width="132" height="26" rx="5" fill="var(--bg)" stroke={c.c} strokeWidth="1.2" />
            <text x="330" y={c.y + 17} fontSize="11" fill={c.c} fontFamily={MONO}>
              {c.label}
            </text>
          </g>
        ))}
        <g style={css(`scale(calc(0.9 + ${rise(0.7, 4)} * 0.1))`, { opacity: rise(0.7, 4), transformOrigin: "384px 235px" })}>
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
    </>
  );
}

function StageEvidence() {
  const rows = ["sha256(artikel#1) 3f9a1c…b7d0", "sha256(artikel#2) 91be44…0e2a", "sha256(artikel#3) c04d7e…ff13", "sha256(artikel#4) 7a2210…9c58"];
  const leaves = [70, 108, 146, 184];
  return (
    <>
      <div className="layer pointer-events-none absolute inset-0 opacity-60" style={css("translate3d(calc(var(--p) * -30px), calc(var(--p) * -20px), 0)", { backgroundImage: "radial-gradient(rgba(167,139,250,0.22) 1px, transparent 1.5px)", backgroundSize: "18px 18px" })} aria-hidden="true" />
      <svg viewBox="0 0 480 300" className="relative h-full w-full" aria-hidden="true" style={css("scale(calc(1 + var(--p) * 0.32))", { transformOrigin: "76% 42%" })}>
        <rect x="20" y="24" width="440" height="252" rx="6" fill="#05080c" stroke="var(--line)" />
        <circle cx="36" cy="38" r="3.5" fill="var(--crit)" />
        <circle cx="48" cy="38" r="3.5" fill="var(--high)" />
        <circle cx="60" cy="38" r="3.5" fill="var(--good)" />
        {rows.map((r, i) => (
          <text key={r} x="36" y={leaves[i] + 4} fontSize="10.5" fill="var(--accent)" fontFamily={MONO} style={{ opacity: rise(i * 0.08, 8) }}>
            {r}
          </text>
        ))}
        {leaves.map((y, i) => (
          <g key={y}>
            <rect x="248" y={y - 6} width="12" height="12" rx="2" fill="var(--accent)" style={{ opacity: rise(i * 0.08, 8) }} />
            <path d={`M260 ${y} L 300 ${i < 2 ? 89 : 165}`} fill="none" stroke="var(--line-2)" strokeWidth="1.5" pathLength={1} strokeDasharray="1" style={{ strokeDashoffset: `calc(1 - ${rise(0.3 + i * 0.05, 3)})` }} />
          </g>
        ))}
        {[89, 165].map((y, i) => (
          <g key={y}>
            <rect x="300" y={y - 6} width="12" height="12" rx="2" fill="var(--bg)" stroke="var(--accent)" strokeWidth="1.5" style={{ opacity: rise(0.4, 4) }} />
            <path d={`M312 ${y} L 350 127`} fill="none" stroke="var(--line-2)" strokeWidth="1.5" pathLength={1} strokeDasharray="1" style={{ strokeDashoffset: `calc(1 - ${rise(0.5 + i * 0.05, 3)})` }} />
          </g>
        ))}
        <rect x="350" y="119" width="16" height="16" rx="3" fill="var(--chain)" style={css(`scale(calc(0.6 + ${rise(0.55, 3)} * 0.6))`, { transformBox: "fill-box", transformOrigin: "center", opacity: rise(0.55, 3) })} />
        <text x="358" y="150" textAnchor="middle" fontSize="10" fill="var(--chain)" fontFamily={MONO} style={{ opacity: rise(0.6, 4) }}>
          root
        </text>
        <path d="M366 127 L 400 127" stroke="var(--chain)" strokeWidth="1.5" strokeDasharray="4 4" className="flow-line" style={{ opacity: rise(0.7, 4) }} />
        <g style={css(`translateX(calc((1 - ${rise(0.7, 4)}) * 24px))`, { opacity: rise(0.7, 4) })}>
          <g transform="translate(400 100)">
            <rect width="44" height="54" rx="5" fill="var(--bg)" stroke="var(--chain)" strokeWidth="1.5" />
            <rect x="9" y="12" width="26" height="4" rx="1" fill="var(--chain)" opacity="0.8" />
            <rect x="9" y="22" width="18" height="4" rx="1" fill="var(--chain)" opacity="0.5" />
            <rect x="9" y="32" width="22" height="4" rx="1" fill="var(--chain)" opacity="0.35" />
            <text x="22" y="70" textAnchor="middle" fontSize="9.5" fill="var(--muted)" fontFamily={MONO}>
              on-chain
            </text>
          </g>
        </g>
        <text x="36" y="232" fontSize="10.5" fill="var(--soft)" fontFamily={MONO} style={{ opacity: rise(0.45, 5) }}>
          merkle_root = 04b942…cfa4a
        </text>
        <text x="36" y="252" fontSize="10.5" fill="var(--chain)" fontFamily={MONO} style={{ opacity: rise(0.6, 5) }}>
          batch #51 · 607 daun · leaves
          <tspan className="caret" />
        </text>
      </svg>
    </>
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
  const bars = [
    { k: "domain", v: 0.9 }, { k: "independen", v: 0.75 }, { k: "korban", v: 0.9 }, { k: "teks", v: 0.4 }, { k: "klaster", v: 0.85 },
  ];
  return (
    <>
      <div className="layer pointer-events-none absolute -bottom-40 left-1/2 h-[520px] w-[520px] -translate-x-1/2 rounded-full border border-good/20" style={css("translate(-50%, 0) rotate(calc(var(--p) * 30deg)) scale(calc(0.9 + var(--p) * 0.2))", { borderStyle: "dashed" })} aria-hidden="true" />
      <Blob className="-right-16 top-10 h-56 w-56 bg-good/15" style={css("translate3d(0, calc(var(--p) * 40px), 0)")} />
      <svg viewBox="0 0 480 300" className="relative h-full w-full" aria-hidden="true">
        <path d={arc(180, 120)} fill="none" stroke="var(--crit)" strokeWidth="14" opacity="0.85" />
        <path d={arc(120, 60)} fill="none" stroke="var(--med)" strokeWidth="14" opacity="0.85" />
        <path d={arc(60, 0)} fill="none" stroke="var(--good)" strokeWidth="14" opacity="0.85" />
        {Array.from({ length: 11 }, (_, i) => {
          const a = 180 - i * 18;
          return <circle key={i} cx={cx + (r - 18) * Math.cos((Math.PI * a) / 180)} cy={cy - (r - 18) * Math.sin((Math.PI * a) / 180)} r="1.8" fill="var(--muted)" />;
        })}
        <polygon points={`${cx - 4},${cy} ${cx + 4},${cy} ${cx},${cy - 100}`} fill="var(--fg)" style={css(`rotate(calc(-90deg + ${rise(0, 1.25)} * 168deg))`, { transformOrigin: `${cx}px ${cy}px` })} />
        <circle cx={cx} cy={cy} r="9" fill="var(--surface)" stroke="var(--fg)" strokeWidth="2" />
        <text x={cx} y={cy + 40} textAnchor="middle" fontSize="30" fontWeight="600" fill="var(--fg)" fontFamily={MONO} style={css("scale(calc(0.9 + var(--p) * 0.15))", { transformOrigin: `${cx}px ${cy + 30}px` })}>
          78
        </text>
        <text x={cx} y={cy + 58} textAnchor="middle" fontSize="10.5" fill="var(--good)" fontFamily={MONO} style={{ opacity: rise(0.6, 4) }}>
          tinggi · high
        </text>
        {bars.map((b, i) => (
          <g key={b.k}>
            <rect x={330 + i * 26} y={210 - 130 * b.v} width="16" height={130 * b.v} rx="2" fill={b.v >= 0.7 ? "var(--good)" : "var(--med)"} style={css(`scaleY(${rise(0.1 + i * 0.1, 3)})`, { transformBox: "fill-box", transformOrigin: "center bottom" })} />
            <text x={338 + i * 26} y="228" textAnchor="middle" fontSize="8.5" fill="var(--muted)" fontFamily={MONO} transform={`rotate(-35 ${338 + i * 26} 228)`}>
              {b.k}
            </text>
          </g>
        ))}
        <line x1="326" x2="464" y1="211" y2="211" stroke="var(--line-2)" />
      </svg>
    </>
  );
}

function StageFindings() {
  const blips = [
    { x: 92, y: 118 }, { x: 150, y: 96 }, { x: 74, y: 178 }, { x: 160, y: 190 }, { x: 128, y: 148 },
  ];
  const groups = [
    { k: "individu", v: 0.95, d: "+31%" }, { k: "perusahaan", v: 0.6, d: "+20%" }, { k: "pelajar", v: 0.45, d: "+130%" }, { k: "nasabah", v: 0.25, d: "+200%" },
  ];
  return (
    <>
      <Blob className="-left-24 -bottom-24 h-80 w-80 bg-crit/20" style={css("scale(calc(0.8 + var(--p) * 0.5))")} />
      <svg viewBox="0 0 480 300" className="relative h-full w-full" aria-hidden="true">
        {[40, 80, 120].map((rr, i) => (
          <circle key={rr} cx="120" cy="150" r={rr} fill="none" stroke="rgba(242,85,90,0.35)" style={css(`scale(calc(0.85 + var(--p) * ${0.15 + i * 0.05}))`, { transformOrigin: "120px 150px" })} />
        ))}
        <line x1="0" x2="240" y1="150" y2="150" stroke="rgba(242,85,90,0.2)" />
        <line x1="120" x2="120" y1="30" y2="270" stroke="rgba(242,85,90,0.2)" />
        <path d="M120 150 L 240 150 A 120 120 0 0 0 204.9 65.1 Z" fill="rgba(242,85,90,0.22)" style={css("rotate(calc(var(--p) * 540deg))", { transformOrigin: "120px 150px" })} />
        {blips.map((b, i) => (
          <g key={i} style={{ opacity: rise(0.12 + i * 0.14, 6) }}>
            <circle cx={b.x} cy={b.y} r="4" fill="var(--crit)" />
            <circle cx={b.x} cy={b.y} r="4" fill="none" stroke="var(--crit)" strokeWidth="1.5" className="blip" style={{ "--i": i } as React.CSSProperties} />
          </g>
        ))}
        {groups.map((g, i) => (
          <g key={g.k} style={{ opacity: rise(0.1 + i * 0.12, 4) }}>
            <text x="268" y={74 + i * 46} fontSize="11" fill="var(--fg)" fontFamily={MONO}>
              {g.k}
            </text>
            <text x="456" y={74 + i * 46} textAnchor="end" fontSize="11" fill="var(--high)" fontFamily={MONO}>
              {g.d}
            </text>
            <rect x="268" y={82 + i * 46} width="188" height="8" rx="2" fill="var(--line)" />
            <rect x="268" y={82 + i * 46} width={188 * g.v} height="8" rx="2" fill="var(--crit)" style={css(`scaleX(${rise(0.15 + i * 0.12, 3)})`, { transformBox: "fill-box", transformOrigin: "left center" })} />
          </g>
        ))}
        <g style={css(`translateY(calc((1 - ${rise(0.72, 4)}) * 12px))`, { opacity: rise(0.72, 4) })}>
          <path d="M268 252 l 10 -5 l 10 5 v 10 c 0 7 -5 11 -10 13 c -5 -2 -10 -6 -10 -13 z" fill="var(--bg)" stroke="var(--good)" strokeWidth="1.5" />
          <path d="M273 262 l 4 4 l 7 -7" fill="none" stroke="var(--good)" strokeWidth="1.5" />
          <text x="296" y="266" fontSize="10.5" fill="var(--soft)" fontFamily={MONO}>
            pencegahan · prevention
          </text>
        </g>
      </svg>
    </>
  );
}

function StagePackage() {
  return (
    <>
      <div className="layer pointer-events-none absolute inset-0 opacity-70" style={css("translate3d(calc(var(--p) * -60px), 0, 0)", { backgroundImage: "repeating-linear-gradient(135deg, rgba(167,139,250,0.08) 0 2px, transparent 2px 26px)" })} aria-hidden="true" />
      <Blob className="-right-20 -top-20 h-72 w-72 bg-[rgba(224,201,58,0.14)]" style={css("translate3d(0, calc(var(--p) * 50px), 0)")} />
      <svg viewBox="0 0 480 300" className="relative h-full w-full" aria-hidden="true">
        <g style={css(`translateX(calc((1 - ${rise(0, 2)}) * -30px))`, { opacity: rise(0, 2) })}>
          <rect x="40" y="30" width="190" height="240" rx="6" fill="var(--bg)" stroke="var(--chain)" strokeWidth="1.5" />
          <rect x="58" y="50" width="100" height="8" rx="2" fill="var(--fg)" opacity="0.9" />
          {[74, 88, 102, 116, 130].map((y, i) => (
            <rect key={y} x="58" y={y} width={i % 2 ? 110 : 150} height="5" rx="2" fill="var(--line-2)" />
          ))}
          <path d="M58 200 C 74 176, 84 176, 92 198 S 118 214, 132 186 S 160 178, 168 200 S 190 212, 208 192" fill="none" stroke="var(--chain)" strokeWidth="2" strokeLinecap="round" pathLength={1} strokeDasharray="1" style={{ strokeDashoffset: `calc(1 - ${rise(0.15, 2)})` }} />
          <line x1="58" x2="212" y1="212" y2="212" stroke="var(--line-2)" />
          <text x="58" y="228" fontSize="9.5" fill="var(--muted)" fontFamily={MONO}>
            EIP-712 · relayer
          </text>
        </g>
        <g style={css(`scale(calc(2.4 - ${rise(0.4, 3)} * 1.4)) rotate(-10deg)`, { transformOrigin: "180px 120px", opacity: rise(0.4, 3) })}>
          <circle cx="180" cy="120" r="34" fill="none" stroke="#e0c93a" strokeWidth="2.5" />
          <circle cx="180" cy="120" r="27" fill="none" stroke="#e0c93a" strokeWidth="1" strokeDasharray="3 3" />
          <path d="M166 120 l 9 9 l 19 -19" fill="none" stroke="#e0c93a" strokeWidth="3.5" strokeLinecap="round" />
        </g>
        <path d="M230 150 L 268 150" stroke="var(--chain)" strokeWidth="1.5" strokeDasharray="4 4" className="flow-line" style={{ opacity: rise(0.55, 4) }} />
        {[0, 1, 2].map((i) => (
          <g key={i} transform={`translate(${268 + i * 64} 118)`}>
            <g style={css(`translateX(calc((1 - ${rise(0.55 + i * 0.1, 4)}) * 50px))`, { opacity: rise(0.55 + i * 0.1, 4) })}>
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
        <text x="356" y="214" textAnchor="middle" fontSize="10" fill="var(--soft)" fontFamily={MONO} style={{ opacity: rise(0.8, 5) }}>
          hash paket → tautan ke batch bukti
        </text>
      </svg>
    </>
  );
}

const STAGES = [StageExtraction, StageEvidence, StageConfidence, StageFindings, StagePackage];

function Stage({ step, className = "" }: { step: number; className?: string }) {
  const S = STAGES[step] ?? StageExtraction;
  return (
    <div key={step} className={`stage-swap stage-${step + 1} corners relative aspect-[480/300] overflow-hidden rounded-lg border border-line ${className}`}>
      <S />
    </div>
  );
}

export function ProcessScroll({ steps, aiTag, hint }: { steps: ProcessStep[]; aiTag: string; hint: string }) {
  const [active, setActive] = useState(0);
  const listRef = useRef<HTMLOListElement>(null);
  const stageHost = useRef<HTMLDivElement>(null);
  const itemRefs = useRef<(HTMLLIElement | null)[]>([]);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let raf = 0;
    const n = steps.length;
    const update = () => {
      raf = 0;
      const list = listRef.current;
      if (!list) return;
      const center = window.innerHeight * 0.5;
      const rect = list.getBoundingClientRect();
      const t = Math.min(n - 0.001, Math.max(0, ((center - rect.top) / rect.height) * n));
      const index = Math.floor(t);
      stageHost.current?.style.setProperty("--p", (t - index).toFixed(3));
      itemRefs.current.forEach((el) => {
        if (!el) return;
        const r = el.getBoundingClientRect();
        // panggung di layar sempit: selesai saat kartu mencapai tengah layar
        el.style.setProperty("--p", Math.min(1, Math.max(0, (center - r.top) / (r.height * 0.65))).toFixed(3));
      });
      setActive((prev) => (prev === index ? prev : index));
    };
    const schedule = () => {
      if (!raf) raf = requestAnimationFrame(update);
    };
    schedule();
    window.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", schedule);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("scroll", schedule);
      window.removeEventListener("resize", schedule);
    };
  }, [steps.length]);

  const color = (s: ProcessStep) => (s.tag === aiTag ? "var(--accent)" : "var(--chain)");

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1.05fr)_minmax(0,0.95fr)] lg:gap-10">
      {/* panggung lengket (layar lebar) */}
      <div className="hidden lg:block">
        <div ref={stageHost} className="p-host sticky top-24 flex flex-col gap-3">
          <Stage step={active} />
          <div className="flex items-center justify-between font-mono text-[11px] text-muted">
            <span>
              {String(active + 1).padStart(2, "0")} / {String(steps.length).padStart(2, "0")}
            </span>
            <span>{hint}</span>
          </div>
        </div>
      </div>

      {/* daftar langkah dengan rel kemajuan; di layar sempit panggung ikut di sini */}
      <ol ref={listRef} className="relative flex flex-col">
        <span className="absolute left-[9px] top-6 bottom-6 hidden w-px bg-line lg:block" aria-hidden="true" />
        {steps.map((s, i) => (
          <li
            key={s.title}
            ref={(el) => {
              itemRefs.current[i] = el;
            }}
            data-active={active === i}
            className="step-item p-host grid grid-cols-[20px_minmax(0,1fr)] gap-4 py-8 lg:min-h-[62vh] lg:py-10"
          >
            <span className="rail-dot relative mt-1.5 inline-block h-5 w-5 rounded-full border-2" data-active={active === i} style={{ borderColor: color(s), background: active === i ? color(s) : "var(--bg)" }} aria-hidden="true" />
            <div className="flex min-w-0 flex-col gap-3">
              <Stage step={i} className="lg:hidden" />
              <div className="flex items-center gap-3">
                <span className="font-mono text-[11px] text-muted">0{i + 1}</span>
                <span className={`chip ${s.tag === aiTag ? "chip-accent" : "chip-chain"}`}>{s.tag}</span>
              </div>
              <h3 className="text-[22px] font-semibold leading-tight" style={css("translateX(calc(var(--p) * 8px))")}>
                {s.title}
              </h3>
              <p className="max-w-[46ch] text-[14.5px] leading-relaxed text-soft">{s.text}</p>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
