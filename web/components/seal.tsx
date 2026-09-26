/** Garis tanda tangan yang menggambar dirinya (lambang atestasi EIP-712). */
export function Signature({ width = 220 }: { width?: number }) {
  const h = 34;
  return (
    <svg width={width} height={h} viewBox={`0 0 220 ${h}`} aria-hidden="true" className="max-w-full">
      <path d="M4 26 C 20 6, 34 6, 44 22 S 70 30, 84 12 S 110 4, 118 22 S 150 30, 166 10 S 196 12, 216 24" fill="none" stroke="var(--chain)" strokeWidth="1.6" strokeLinecap="round" pathLength={1} className="draw" />
      <line x1="4" x2="216" y1="31" y2="31" stroke="var(--line-2)" strokeWidth="1" />
    </svg>
  );
}
