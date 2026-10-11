/*
 * Ilustrasi garis per kelompok sasaran, dipakai sebagai latar memudar di kartu
 * "Langkah pencegahan per kelompok". Gaya ikon 24x24 dengan stroke, digambar
 * besar dan transparan di pojok kartu.
 */
const PATHS: Record<string, React.ReactNode> = {
  INDIVIDUALS: (
    <>
      <circle cx="12" cy="8" r="4" />
      <path d="M4 21v-1a6 6 0 0 1 6-6h4a6 6 0 0 1 6 6v1" />
    </>
  ),
  EMPLOYEES: (
    <>
      <rect x="3" y="7" width="18" height="13" rx="2" />
      <path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
      <path d="M3 13h18M11 13v2h2v-2" />
    </>
  ),
  STUDENTS: (
    <>
      <path d="M2 9l10-5 10 5-10 5z" />
      <path d="M6 11v5c0 1.7 2.7 3 6 3s6-1.3 6-3v-5" />
      <path d="M22 9v6" />
    </>
  ),
  CHILDREN: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M8.5 14.5a4 4 0 0 0 7 0" />
      <path d="M9 9.5h.01M15 9.5h.01" />
      <path d="M10 3.3c0 1.5 1 2.2 2 2.2" />
    </>
  ),
  JOB_SEEKERS: (
    <>
      <circle cx="10.5" cy="10.5" r="6.5" />
      <path d="M15.5 15.5L21 21" />
      <path d="M8 9.5h5M8 12h3" />
    </>
  ),
  BUSINESSES: (
    <>
      <rect x="4" y="3" width="16" height="18" rx="1" />
      <path d="M9.5 21v-4h5v4" />
      <path d="M8 7h2M14 7h2M8 11h2M14 11h2" />
    </>
  ),
  GOVERNMENT: (
    <>
      <path d="M3 21h18" />
      <path d="M5 21v-9M9.5 21v-9M14.5 21v-9M19 21v-9" />
      <path d="M2 10l10-6 10 6z" />
    </>
  ),
  BANK_CUSTOMERS: (
    <>
      <rect x="2" y="5" width="20" height="14" rx="2" />
      <path d="M2 10h20" />
      <path d="M6 15h4" />
    </>
  ),
  SMES: (
    <>
      <path d="M3 9l1.5-5h15L21 9" />
      <path d="M3 9a3 3 0 0 0 6 0 3 3 0 0 0 6 0 3 3 0 0 0 6 0" />
      <path d="M5 11.5V21h14v-9.5" />
      <path d="M10 21v-5h4v5" />
    </>
  ),
  CIVIL_SERVANTS: (
    <>
      <rect x="4" y="3" width="16" height="18" rx="2" />
      <circle cx="12" cy="10" r="3" />
      <path d="M8 17a4 4 0 0 1 8 0" />
      <path d="M10 3v2h4V3" />
    </>
  ),
  ELDERLY: (
    <>
      <circle cx="11" cy="4.5" r="2" />
      <path d="M11 7.5l-1 5.5 3 3v5" />
      <path d="M10 13l-3 8" />
      <path d="M10.5 9l4 3" />
      <path d="M17 12v9" />
    </>
  ),
};

const FALLBACK = <path d="M12 3l8 3v6c0 4.5-3.4 8.2-8 9-4.6-.8-8-4.5-8-9V6z" />;

/** Ilustrasi besar dan memudar di pojok kanan kartu; ``color`` mengikuti tingkat risiko. */
export function GroupArt({ group, color }: { group: string; color: string }) {
  return (
    <div aria-hidden="true" className="pointer-events-none absolute inset-0 overflow-hidden rounded-[inherit]">
      <div className="absolute inset-0" style={{ background: `radial-gradient(120% 90% at 100% 0%, color-mix(in srgb, ${color} 14%, transparent) 0%, transparent 60%)` }} />
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke={color}
        strokeWidth={1.1}
        strokeLinecap="round"
        strokeLinejoin="round"
        className="absolute -right-6 top-6 h-[180px] w-[180px]"
        style={{ opacity: 0.16, maskImage: "linear-gradient(to bottom left, black 25%, transparent 85%)", WebkitMaskImage: "linear-gradient(to bottom left, black 25%, transparent 85%)" }}
      >
        {PATHS[group] ?? FALLBACK}
      </svg>
    </div>
  );
}
