/*
 * Latar budaya provinsi untuk kepala pop-up Peta Literasi: siluet bangunan atau
 * ikon khas (Rumah Gadang, Gedung Sate, Candi Bentar, Tongkonan, Honai, ...)
 * dan pola kain/ornamen khas (songket, mega mendung, kawung, poleng, ikat,
 * Dayak, Asmat, ...), memudar ke kiri agar teks tetap terbaca. Pola bergeser
 * pelan dan ada partikel melayang (mati bila pengguna memilih kurangi gerakan).
 * Data per provinsi di lib/province-culture.json. Ilustrasi sederhana, bukan
 * gambar resmi.
 */
import culture from "@/lib/province-culture.json";

type Culture = { landmark: string; pattern: string; accent: string; label: Record<"id" | "en", string> };
const PROVINCES = culture.provinces as Record<string, Culture>;

export function cultureOf(code: string): Culture | null {
  return PROVINCES[code] ?? null;
}

const W = 640;
const H = 170;
const G = 158; // garis tanah

/** Siluet ikon budaya di sisi kanan (koordinat viewBox 640 x 170). */
const LANDMARKS: Record<string, React.ReactNode> = {
  gadang: (
    <>
      <path d="M352 104 C374 78 384 50 398 22 C410 62 434 78 464 82 C494 78 518 62 530 22 C544 50 554 78 576 104 Z" />
      <path d="M418 70 C428 56 434 44 440 34 C446 48 452 58 464 64 C476 58 482 48 488 34 C494 44 500 56 510 70 Z" opacity="0.7" />
      <rect x="372" y="104" width="184" height="36" />
      <rect x="380" y="140" width="6" height="18" />
      <rect x="430" y="140" width="6" height="18" />
      <rect x="492" y="140" width="6" height="18" />
      <rect x="542" y="140" width="6" height="18" />
    </>
  ),
  bolon: (
    <>
      <path d="M380 96 C392 70 400 40 404 18 C430 44 470 56 496 56 C522 56 556 44 580 18 C584 40 592 70 604 96 Z" />
      <rect x="402" y="96" width="180" height="30" />
      {[410, 446, 482, 518, 554].map((x) => (
        <rect key={x} x={x} y="126" width="7" height="32" />
      ))}
    </>
  ),
  panggung: (
    <>
      <path d="M380 94 L478 34 L576 94 Z" />
      <path d="M470 34 L460 18 M486 34 L496 18" strokeWidth="4" />
      <rect x="396" y="94" width="164" height="38" />
      {[404, 444, 478, 512, 548].map((x) => (
        <rect key={x} x={x} y="132" width="6" height="26" />
      ))}
      <path d="M560 132 L596 158" strokeWidth="5" />
    </>
  ),
  limas: (
    <>
      <path d="M392 100 L428 72 L528 72 L564 100 Z" />
      <path d="M416 72 L446 46 L510 46 L540 72 Z" opacity="0.85" />
      <path d="M440 46 L478 18 L516 46 Z" opacity="0.7" />
      <rect x="404" y="100" width="148" height="36" />
      {[412, 452, 492, 532].map((x) => (
        <rect key={x} x={x} y="136" width="6" height="22" />
      ))}
    </>
  ),
  siger: (
    <>
      <path d="M380 150 L380 110 C380 100 392 94 404 96 L412 54 L426 92 L438 40 L452 90 L466 28 L478 88 L490 20 L502 88 L514 28 L528 90 L542 40 L554 92 L568 54 L576 96 C588 94 600 100 600 110 L600 150 Z" />
      <path d="M392 128 L588 128" strokeWidth="3" opacity="0.6" />
      {[420, 452, 490, 528, 560].map((x) => (
        <circle key={x} cx={x} cy="140" r="4" opacity="0.7" />
      ))}
    </>
  ),
  monas: (
    <>
      <path d="M470 34 C462 24 468 12 478 6 C476 16 486 18 484 28 C490 24 490 16 488 12 C496 20 494 32 486 36 Z" />
      <rect x="470" y="36" width="16" height="8" />
      <path d="M472 44 L484 44 L490 116 L466 116 Z" />
      <path d="M418 116 L538 116 L556 134 L400 134 Z" />
      <rect x="388" y="134" width="180" height="24" />
    </>
  ),
  sate: (
    <>
      <path d="M478 6 L478 40" strokeWidth="3" />
      {[12, 20, 28].map((y) => (
        <circle key={y} cx="478" cy={y} r="3.5" />
      ))}
      <path d="M456 66 L478 40 L500 66 Z" />
      <path d="M446 80 L478 58 L510 80 Z" opacity="0.85" />
      <rect x="452" y="80" width="52" height="30" />
      <rect x="372" y="104" width="212" height="54" />
      {[388, 412, 436, 520, 544, 568].map((x) => (
        <rect key={x} x={x - 6} y="118" width="10" height="26" fill="var(--bg)" opacity="0.5" />
      ))}
    </>
  ),
  stupa: (
    <>
      <path d="M478 8 L482 36 L474 36 Z" />
      <rect x="466" y="36" width="24" height="10" />
      <path d="M446 76 C446 54 462 46 478 46 C494 46 510 54 510 76 Z" />
      <path d="M398 112 C398 98 404 92 412 92 C420 92 426 98 426 112 Z" opacity="0.8" />
      <path d="M530 112 C530 98 536 92 544 92 C552 92 558 98 558 112 Z" opacity="0.8" />
      <rect x="430" y="76" width="96" height="12" />
      <rect x="400" y="112" width="156" height="14" />
      <rect x="380" y="126" width="196" height="14" />
      <rect x="360" y="140" width="236" height="18" />
    </>
  ),
  joglo: (
    <>
      <path d="M444 64 L462 22 L494 22 L512 64 Z" />
      <path d="M380 98 L428 64 L528 64 L576 98 Z" opacity="0.85" />
      <rect x="400" y="98" width="156" height="12" opacity="0.6" />
      {[408, 440, 470, 486, 516, 548].map((x) => (
        <rect key={x} x={x} y="110" width="6" height="40" />
      ))}
      <rect x="386" y="150" width="184" height="8" />
    </>
  ),
  mosque: (
    <>
      <path d="M418 70 L478 34 L538 70 Z" />
      <path d="M406 98 L478 58 L550 98 Z" opacity="0.85" />
      <path d="M394 124 L478 84 L562 124 Z" opacity="0.75" />
      <path d="M472 34 L478 20 L484 34" />
      <rect x="404" y="124" width="148" height="34" />
      <rect x="582" y="40" width="16" height="118" />
      <path d="M578 40 L590 22 L602 40 Z" />
    </>
  ),
  domes: (
    <>
      <path d="M440 82 C440 58 456 42 478 30 C500 42 516 58 516 82 Z" />
      <path d="M478 30 L478 14" strokeWidth="3" />
      <path d="M400 104 C400 90 408 82 420 76 C432 82 440 90 440 104 Z" opacity="0.85" />
      <path d="M516 104 C516 90 524 82 536 76 C548 82 556 90 556 104 Z" opacity="0.85" />
      <rect x="392" y="104" width="172" height="54" />
      <rect x="440" y="82" width="76" height="22" />
      <rect x="370" y="52" width="12" height="106" />
      <rect x="574" y="52" width="12" height="106" />
      <path d="M368 52 L376 34 L384 52 Z M572 52 L580 34 L588 52 Z" />
    </>
  ),
  bentar: (
    <>
      <path d="M404 158 L404 120 L412 120 L412 96 L420 96 L420 72 L428 72 L428 48 L436 48 L436 28 L452 28 L452 158 Z" />
      <path d="M552 158 L552 120 L544 120 L544 96 L536 96 L536 72 L528 72 L528 48 L520 48 L520 28 L504 28 L504 158 Z" />
      <path d="M452 158 L452 132 L504 132 L504 158" opacity="0.35" />
      <circle cx="478" cy="60" r="16" opacity="0.4" />
    </>
  ),
  lumbung: (
    <>
      <path d="M432 92 C432 48 452 18 478 18 C504 18 524 48 524 92 Z" />
      <rect x="440" y="92" width="76" height="26" />
      <path d="M408 118 L548 118 L536 128 L420 128 Z" opacity="0.8" />
      {[434, 470, 486, 518].map((x) => (
        <rect key={x} x={x} y="128" width="6" height="30" />
      ))}
    </>
  ),
  cone: (
    <>
      <path d="M478 10 L548 150 L408 150 Z" />
      <path d="M440 90 L516 90 M428 116 L528 116" strokeWidth="3" opacity="0.5" stroke="var(--bg)" />
      <rect x="400" y="150" width="156" height="8" />
      <path d="M476 10 L478 2 L480 10" />
    </>
  ),
  betang: (
    <>
      <path d="M340 98 L372 66 L588 66 L620 98 Z" />
      <rect x="350" y="98" width="260" height="30" />
      {[358, 392, 426, 460, 494, 528, 562, 596].map((x) => (
        <rect key={x} x={x} y="128" width="6" height="30" />
      ))}
      <path d="M340 140 L356 128 M340 148 L360 134" strokeWidth="3" />
    </>
  ),
  bubungan: (
    <>
      <path d="M452 92 L478 12 L504 92 Z" />
      <path d="M392 108 L440 82 L516 82 L564 108 Z" opacity="0.85" />
      <rect x="404" y="108" width="148" height="30" />
      {[412, 450, 500, 540].map((x) => (
        <rect key={x} x={x} y="138" width="6" height="20" />
      ))}
    </>
  ),
  tongkonan: (
    <>
      <path d="M352 52 C380 78 420 90 478 90 C536 90 576 78 604 52 C600 78 588 96 570 104 L386 104 C368 96 356 78 352 52 Z" />
      <rect x="410" y="104" width="136" height="28" />
      {[418, 452, 500, 534].map((x) => (
        <rect key={x} x={x} y="132" width="8" height="26" />
      ))}
      <rect x="470" y="60" width="16" height="30" opacity="0.6" />
    </>
  ),
  honai: (
    <>
      <path d="M410 116 C410 70 440 42 478 42 C516 42 546 70 546 116 Z" />
      <rect x="418" y="116" width="120" height="42" />
      <rect x="466" y="128" width="24" height="30" fill="var(--bg)" opacity="0.5" />
      <path d="M560 128 C560 106 572 96 588 96 C604 96 616 106 616 128 Z" opacity="0.7" />
      <rect x="564" y="128" width="48" height="30" opacity="0.7" />
    </>
  ),
};

/** Pola kain/ornamen khas (tile SVG). */
function patternTile(kind: string, color: string): React.ReactNode {
  const s = { stroke: color, fill: "none", strokeWidth: 1.2 } as const;
  switch (kind) {
    case "songket":
      return (
        <>
          <path d="M12 0 L24 12 L12 24 L0 12 Z" {...s} />
          <path d="M12 6 L18 12 L12 18 L6 12 Z" fill={color} opacity="0.5" />
        </>
      );
    case "ulos":
    case "ikat":
      return (
        <>
          <path d="M0 4 H24 M0 20 H24" {...s} />
          <path d="M4 12 L8 8 L12 12 L8 16 Z M16 12 L20 8 L24 12 L20 16 Z" {...s} />
        </>
      );
    case "kawung":
      return (
        <>
          <ellipse cx="12" cy="5" rx="4" ry="5" {...s} />
          <ellipse cx="12" cy="19" rx="4" ry="5" {...s} />
          <ellipse cx="5" cy="12" rx="5" ry="4" {...s} />
          <ellipse cx="19" cy="12" rx="5" ry="4" {...s} />
        </>
      );
    case "megamendung":
      return <path d="M0 18 C4 8 10 8 12 14 C14 6 22 6 24 16 M2 22 C6 14 10 14 12 18 C14 12 20 12 22 20" {...s} />;
    case "parang":
      return <path d="M-4 20 C2 14 6 14 8 8 C10 2 14 2 18 -4 M8 28 C14 22 18 22 20 16 C22 10 26 10 30 4" {...s} strokeWidth={1.6} />;
    case "poleng":
      return (
        <>
          <rect x="0" y="0" width="12" height="12" fill={color} opacity="0.55" />
          <rect x="12" y="12" width="12" height="12" fill={color} opacity="0.55" />
        </>
      );
    case "dayak":
      return <path d="M4 20 C4 10 14 10 14 16 C14 20 10 20 10 17 M14 4 C14 12 22 12 22 8" {...s} strokeWidth={1.5} />;
    case "sasirangan":
      return <path d="M0 6 L6 0 L12 6 L18 0 L24 6 M0 18 L6 12 L12 18 L18 12 L24 18" {...s} />;
    case "waves":
      return <path d="M0 8 C4 4 8 4 12 8 C16 12 20 12 24 8 M0 20 C4 16 8 16 12 20 C16 24 20 24 24 20" {...s} />;
    case "toraja":
      return (
        <>
          <rect x="4" y="4" width="16" height="16" {...s} />
          <path d="M4 4 L20 20 M20 4 L4 20" {...s} />
          <circle cx="12" cy="12" r="3" {...s} />
        </>
      );
    case "papua":
      return <path d="M0 24 L6 12 L12 24 L18 12 L24 24 M6 6 C6 2 12 2 12 6 C12 9 8 9 8 7" {...s} strokeWidth={1.5} />;
    default:
      return <circle cx="12" cy="12" r="2" fill={color} />;
  }
}

const PARTICLES = [
  { x: 360, y: 40, r: 2, d: 0 },
  { x: 420, y: 24, r: 1.5, d: 1.2 },
  { x: 520, y: 30, r: 2.2, d: 2.4 },
  { x: 600, y: 60, r: 1.6, d: 0.6 },
  { x: 300, y: 70, r: 1.4, d: 1.8 },
  { x: 560, y: 120, r: 1.8, d: 3 },
];

/** Latar kepala pop-up: pola bergeser + siluet budaya + partikel, memudar ke kiri. */
export function ProvinceCulture({ code }: { code: string }) {
  const c = PROVINCES[code];
  if (!c) return null;
  const id = `culture-${code}`;
  return (
    <svg aria-hidden="true" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMaxYMax slice" className="pointer-events-none absolute inset-0 h-full w-full">
      <defs>
        <pattern id={`${id}-p`} width="24" height="24" patternUnits="userSpaceOnUse">
          {patternTile(c.pattern, c.accent)}
        </pattern>
        <linearGradient id={`${id}-fade`} x1="0" x2="1" y1="0" y2="0">
          <stop offset="0" stopColor="white" stopOpacity="0" />
          <stop offset="0.38" stopColor="white" stopOpacity="0.15" />
          <stop offset="0.7" stopColor="white" stopOpacity="0.85" />
          <stop offset="1" stopColor="white" stopOpacity="1" />
        </linearGradient>
        <mask id={`${id}-m`}>
          <rect width={W} height={H} fill={`url(#${id}-fade)`} />
        </mask>
        <radialGradient id={`${id}-glow`} cx="0.78" cy="0.55" r="0.6">
          <stop offset="0" stopColor={c.accent} stopOpacity="0.32" />
          <stop offset="1" stopColor={c.accent} stopOpacity="0" />
        </radialGradient>
      </defs>
      <rect width={W} height={H} fill={`url(#${id}-glow)`} />
      <g mask={`url(#${id}-m)`}>
        <rect className="culture-drift" x={-48} y={-48} width={W + 96} height={H + 96} fill={`url(#${id}-p)`} opacity="0.35" />
        <g fill={c.accent} stroke={c.accent} strokeWidth="1" opacity="0.5" className="culture-rise">
          {LANDMARKS[c.landmark]}
          <rect x="300" y={G} width={W - 300} height="2" opacity="0.6" />
        </g>
        {PARTICLES.map((p) => (
          <circle key={`${p.x}-${p.y}`} cx={p.x} cy={p.y} r={p.r} fill={c.accent} className="culture-float" style={{ animationDelay: `${p.d}s` }} />
        ))}
      </g>
    </svg>
  );
}
