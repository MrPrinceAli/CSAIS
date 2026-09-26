import { SourceLogo } from "@/components/ui";

/** Dua baris logo sumber yang bergeser berlawanan arah; berhenti saat disorot. */
export function LogoMarquee({ domains, note }: { domains: string[]; note: string }) {
  if (domains.length < 6) return null;
  const half = Math.ceil(domains.length / 2);
  const rows = [domains.slice(0, half), domains.slice(half)];
  return (
    <div className="ticker-wrap flex flex-col gap-3 overflow-hidden py-1 fade-x" aria-label={note}>
      {rows.map((row, r) => (
        <div key={r} className={`ticker ${r === 1 ? "ticker-rev" : ""}`}>
          {[...row, ...row].map((d, i) => (
            <span key={`${d}-${i}`} className="flex items-center gap-2 rounded-md border border-line bg-surface px-2.5 py-1.5 font-mono text-[11px] text-soft" aria-hidden={i >= row.length}>
              <SourceLogo domain={d} size={16} />
              {d}
            </span>
          ))}
        </div>
      ))}
    </div>
  );
}
