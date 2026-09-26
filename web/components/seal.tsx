/**
 * Segel lembaga: cincin putus-putus berputar pelan, inisial di tengah, dan
 * garis tanda tangan yang menggambar dirinya (lambang atestasi EIP-712).
 */
export function Seal({ org, size = 84 }: { org: string; size?: number }) {
  const c = size / 2;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label={org}>
      <circle cx={c} cy={c} r={c - 3} fill="none" stroke="var(--chain)" strokeWidth="1.5" strokeDasharray="4 5" className="seal-ring" opacity="0.8" />
      <circle cx={c} cy={c} r={c - 12} fill="var(--nav)" stroke="var(--line-2)" strokeWidth="1" />
      <text x={c} y={c} dy="0.36em" textAnchor="middle" fontSize={org.length > 4 ? 13 : 15} fontWeight="700" fill="var(--fg)" fontFamily="var(--font-jet), monospace" letterSpacing="0.06em">
        {org}
      </text>
    </svg>
  );
}

export function Signature({ width = 220 }: { width?: number }) {
  const h = 34;
  return (
    <svg width={width} height={h} viewBox={`0 0 220 ${h}`} aria-hidden="true" className="max-w-full">
      <path d="M4 26 C 20 6, 34 6, 44 22 S 70 30, 84 12 S 110 4, 118 22 S 150 30, 166 10 S 196 12, 216 24" fill="none" stroke="var(--chain)" strokeWidth="1.6" strokeLinecap="round" pathLength={1} className="draw" />
      <line x1="4" x2="216" y1="31" y2="31" stroke="var(--line-2)" strokeWidth="1" />
    </svg>
  );
}
