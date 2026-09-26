/**
 * Jalur bukti Merkle: daun -> simpul antara -> akar, digambar sebagai rantai kotak
 * dengan garis yang menggambar dirinya. Ukuran mengikuti jumlah hash saudara.
 */
export function MerkleMini({ siblings, leafLabel, rootLabel, valid, anchored }: { siblings: number; leafLabel: string; rootLabel: string; valid: boolean; anchored: boolean }) {
  const steps = Math.min(siblings, 10);
  const nodes = steps + 2; // daun, simpul antara, akar
  const w = 640;
  const gap = (w - 80) / Math.max(1, nodes - 1);
  const y = 34;
  const okColor = valid ? "var(--accent)" : "var(--crit)";
  return (
    <svg viewBox={`0 0 ${w} 70`} className="w-full" role="img" aria-label={`${leafLabel} → ${rootLabel}`}>
      {Array.from({ length: nodes - 1 }, (_, i) => (
        <line key={i} x1={40 + i * gap + 9} x2={40 + (i + 1) * gap - 9} y1={y} y2={y} stroke={okColor} strokeWidth="1.5" pathLength={1} className="draw" style={{ "--i": i } as React.CSSProperties} opacity="0.9" />
      ))}
      {Array.from({ length: nodes }, (_, i) => {
        const x = 40 + i * gap;
        const isLeaf = i === 0;
        const isRoot = i === nodes - 1;
        const fill = isRoot ? "var(--chain)" : isLeaf ? okColor : "var(--surface)";
        return (
          <g key={i} className="fade-up" style={{ "--i": i * 2 } as React.CSSProperties}>
            {isRoot && anchored ? <circle cx={x} cy={y} r="15" fill="none" stroke="var(--chain)" strokeWidth="1" opacity="0.5" /> : null}
            <rect x={x - 8} y={y - 8} width="16" height="16" rx="3" fill={fill} stroke={isRoot ? "var(--chain)" : okColor} strokeWidth="1.5" />
          </g>
        );
      })}
      <text x={40} y={y + 24} textAnchor="middle" fontSize="10.5" fill="var(--muted)" fontFamily="var(--font-jet), monospace" className="draw-fill">
        {leafLabel}
      </text>
      <text x={40 + (nodes - 1) * gap} y={y + 24} textAnchor="middle" fontSize="10.5" fill="var(--chain)" fontFamily="var(--font-jet), monospace" className="draw-fill">
        {rootLabel}
      </text>
    </svg>
  );
}
