/**
 * Ilustrasi kecil tiap langkah "Cara kerja" (SVG 200x110, berskala):
 *   0 ekstraksi dan pengelompokan  1 pencatatan bukti  2 indeks kepercayaan
 *   3 temuan dan risiko            4 paket rekomendasi
 * Gerak memakai kelas global (.draw, .bar-rise, .ring-arc, .heat-cell, .led)
 * dan titik SMIL; semuanya diam pada prefers-reduced-motion.
 */
const AI = "var(--accent)";
const CHAIN = "var(--chain)";
const LINE = "var(--line-2)";
const MUTED = "var(--muted)";
const MONO = "var(--font-jet), monospace";

function Doc({ x, y, marks = [] as number[], w = 46, h = 34 }: { x: number; y: number; marks?: number[]; w?: number; h?: number }) {
  const rows = [8, 14, 20, 26];
  return (
    <g>
      <rect x={x} y={y} width={w} height={h} rx="3" fill="var(--bg)" stroke={LINE} />
      {rows.map((r, i) => (
        <rect key={i} x={x + 6} y={y + r} width={i % 2 ? w - 18 : w - 12} height="2.5" rx="1" fill={marks.includes(i) ? "rgba(245,230,99,0.75)" : LINE} />
      ))}
    </g>
  );
}

function Extraction() {
  return (
    <svg viewBox="0 0 200 110" className="w-full" aria-hidden="true">
      <Doc x={10} y={8} marks={[1]} />
      <Doc x={10} y={38} marks={[0, 2]} />
      <Doc x={10} y={68} marks={[1]} />
      {[25, 55, 85].map((y, i) => (
        <g key={y}>
          <path d={`M58 ${y} C 95 ${y}, 95 55, 128 55`} fill="none" stroke={AI} strokeWidth="1.2" opacity="0.6" pathLength={1} className="draw" style={{ "--i": i } as React.CSSProperties} />
          <circle r="2.2" fill={AI} className="flow-dot">
            <animateMotion dur="2.2s" begin={`${i * 0.5}s`} repeatCount="indefinite" path={`M58 ${y} C 95 ${y}, 95 55, 128 55`} />
          </circle>
        </g>
      ))}
      <circle cx="152" cy="55" r="26" fill="var(--bg)" stroke={AI} strokeWidth="1.5" />
      <circle cx="152" cy="55" r="33" fill="none" stroke={AI} strokeWidth="1" opacity="0.25" />
      <Doc x={137} y={41} w={30} h={24} marks={[0]} />
      <Doc x={141} y={45} w={30} h={24} marks={[1]} />
      <text x="152" y="95" textAnchor="middle" fontSize="8" fill={MUTED} fontFamily={MONO}>
        incident
      </text>
    </svg>
  );
}

function Evidence() {
  const cells = Array.from({ length: 16 }, (_, i) => i);
  const leaves = [24, 44, 64, 84];
  return (
    <svg viewBox="0 0 200 110" className="w-full" aria-hidden="true">
      {cells.map((i) => (
        <rect key={i} x={8 + (i % 4) * 9} y={30 + Math.floor(i / 4) * 9} width="8" height="8" rx="1" fill={[0, 3, 5, 6, 9, 10, 12, 15].includes(i) ? AI : [1, 7, 8, 14].includes(i) ? CHAIN : LINE} opacity={0.5 + ((i * 7) % 5) / 8} className="hash-cell" style={{ "--i": i } as React.CSSProperties} />
      ))}
      <text x="26" y="78" textAnchor="middle" fontSize="7.5" fill={MUTED} fontFamily={MONO}>
        sha-256
      </text>
      {leaves.map((y, i) => (
        <g key={y}>
          <rect x="60" y={y - 4} width="8" height="8" rx="1.5" fill={AI} opacity="0.85" />
          <path d={`M68 ${y} L 96 ${i < 2 ? 34 : 74}`} fill="none" stroke={LINE} strokeWidth="1.2" pathLength={1} className="draw" style={{ "--i": i } as React.CSSProperties} />
        </g>
      ))}
      {[34, 74].map((y, i) => (
        <g key={y}>
          <rect x="96" y={y - 4} width="8" height="8" rx="1.5" fill="var(--bg)" stroke={AI} />
          <path d={`M104 ${y} L 132 54`} fill="none" stroke={LINE} strokeWidth="1.2" pathLength={1} className="draw" style={{ "--i": 4 + i } as React.CSSProperties} />
        </g>
      ))}
      <rect x="132" y="49" width="10" height="10" rx="2" fill={CHAIN} />
      <path d="M142 54 L 162 54" fill="none" stroke={CHAIN} strokeWidth="1.4" strokeDasharray="3 3" className="flow-line" />
      <g transform="translate(162 40)">
        <rect width="30" height="28" rx="3" fill="var(--bg)" stroke={CHAIN} strokeWidth="1.5" />
        <rect x="6" y="8" width="18" height="3" rx="1" fill={CHAIN} opacity="0.8" />
        <rect x="6" y="14" width="12" height="3" rx="1" fill={CHAIN} opacity="0.5" />
        <rect x="6" y="20" width="16" height="3" rx="1" fill={CHAIN} opacity="0.35" />
      </g>
      <text x="177" y="82" textAnchor="middle" fontSize="7.5" fill={CHAIN} fontFamily={MONO}>
        root
      </text>
    </svg>
  );
}

function Confidence() {
  const r = 30;
  const c = 2 * Math.PI * r;
  const score = 0.78;
  const bars = [0.9, 0.7, 0.55, 0.85, 0.4];
  return (
    <svg viewBox="0 0 200 110" className="w-full" aria-hidden="true">
      <circle cx="58" cy="55" r={r} fill="none" stroke="var(--line)" strokeWidth="6" />
      <circle cx="58" cy="55" r={r} fill="none" stroke="var(--good)" strokeWidth="6" strokeLinecap="round" strokeDasharray={`${c * score} ${c}`} transform="rotate(-90 58 55)" className="ring-arc" />
      <text x="58" y="55" dy="0.36em" textAnchor="middle" fontSize="17" fontWeight="600" fill="var(--fg)" fontFamily={MONO}>
        {Math.round(score * 100)}
      </text>
      {bars.map((v, i) => (
        <g key={i}>
          <rect x={112 + i * 16} y={78 - 46 * v} width="9" height={46 * v} rx="1.5" fill={i % 2 ? AI : "var(--good)"} opacity="0.85" className="bar-rise" style={{ "--i": i * 6 } as React.CSSProperties} />
          <rect x={112 + i * 16} y="32" width="9" height="46" rx="1.5" fill="none" stroke="var(--line)" />
        </g>
      ))}
      <line x1="108" x2="192" y1="80" y2="80" stroke={LINE} />
      <text x="150" y="94" textAnchor="middle" fontSize="7.5" fill={MUTED} fontFamily={MONO}>
        sinyal · signals
      </text>
    </svg>
  );
}

function Findings() {
  const heat = [0.9, 0.5, 0.2, 0.6, 0.3, 0.8, 0.1, 0.4, 0.7, 0.2, 0.5, 0.9];
  return (
    <svg viewBox="0 0 200 110" className="w-full" aria-hidden="true">
      {heat.map((v, i) => (
        <rect key={i} x={12 + (i % 4) * 20} y={22 + Math.floor(i / 4) * 20} width="18" height="18" rx="2" fill={`rgba(242, 85, 90, ${0.12 + v * 0.7})`} stroke="var(--line)" className="heat-cell" style={{ "--i": i } as React.CSSProperties} />
      ))}
      <path d="M96 52 L 122 52" fill="none" stroke="var(--crit)" strokeWidth="1.4" strokeDasharray="3 3" className="flow-line" />
      <path d="M118 47 L 124 52 L 118 57" fill="none" stroke="var(--crit)" strokeWidth="1.4" />
      {[0, 1, 2].map((i) => (
        <g key={i} transform={`translate(${134 + i * 20} 40)`}>
          <g className="fade-up" style={{ "--i": i * 3 } as React.CSSProperties}>
            <circle cx="8" cy="6" r="5" fill="var(--bg)" stroke={i === 1 ? "var(--crit)" : LINE} strokeWidth="1.5" />
            <path d="M0 24 C 0 14, 16 14, 16 24 Z" fill="var(--bg)" stroke={i === 1 ? "var(--crit)" : LINE} strokeWidth="1.5" />
          </g>
        </g>
      ))}
      <path d="M146 70 l 8 -4 l 8 4 v 8 c 0 6 -4 9 -8 11 c -4 -2 -8 -5 -8 -11 z" fill="var(--bg)" stroke="var(--good)" strokeWidth="1.5" />
      <path d="M150 78 l 3 3 l 6 -6" fill="none" stroke="var(--good)" strokeWidth="1.5" />
      <text x="160" y="100" textAnchor="middle" fontSize="7.5" fill={MUTED} fontFamily={MONO}>
        risiko · risk
      </text>
    </svg>
  );
}

function Package() {
  return (
    <svg viewBox="0 0 200 110" className="w-full" aria-hidden="true">
      <rect x="22" y="14" width="70" height="84" rx="4" fill="var(--bg)" stroke={LINE} />
      {[26, 34, 42].map((y, i) => (
        <rect key={y} x="32" y={y} width={i === 1 ? 38 : 50} height="3" rx="1" fill={LINE} />
      ))}
      <path d="M32 74 C 40 60, 46 60, 50 72 S 62 82, 70 66 S 80 64, 84 74" fill="none" stroke={CHAIN} strokeWidth="1.5" strokeLinecap="round" pathLength={1} className="draw" />
      <line x1="32" x2="84" y1="80" y2="80" stroke={LINE} />
      <circle cx="74" cy="34" r="11" fill="none" stroke={CHAIN} strokeWidth="1" strokeDasharray="2 2.5" className="seal-ring" />
      <circle cx="74" cy="34" r="6" fill={CHAIN} opacity="0.85" />
      <path d="M92 56 L 126 56" fill="none" stroke={CHAIN} strokeWidth="1.4" strokeDasharray="3 3" className="flow-line" />
      {[0, 1, 2].map((i) => (
        <g key={i} transform={`translate(${128 + i * 22} 42)`}>
          <g className="fade-up" style={{ "--i": i * 3 } as React.CSSProperties}>
            <rect width="18" height="28" rx="3" fill="var(--bg)" stroke={CHAIN} strokeWidth="1.5" />
            <rect x="5" y="8" width="8" height="3" rx="1" fill={CHAIN} opacity="0.7" />
            <rect x="5" y="14" width="8" height="3" rx="1" fill={CHAIN} opacity="0.4" />
            {i < 2 ? <path d="M18 14 L 22 14" stroke={CHAIN} strokeWidth="1.5" /> : null}
          </g>
        </g>
      ))}
      <text x="160" y="86" textAnchor="middle" fontSize="7.5" fill={CHAIN} fontFamily={MONO}>
        hash · ttd
      </text>
    </svg>
  );
}

const ART = [Extraction, Evidence, Confidence, Findings, Package];

export function ProcessArt({ step }: { step: number }) {
  const Art = ART[step] ?? Extraction;
  return (
    <div className="rounded-md border border-line bg-nav/60 grid-bg">
      <Art />
    </div>
  );
}
