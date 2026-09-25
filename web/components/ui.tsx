import Link from "next/link";
import type { ReactNode } from "react";
import type { IncidentRow } from "@/lib/queries";
import {
  attackCode,
  attackLabel,
  fmtDate,
  fmtNum,
  fmtScore,
  incidentTitle,
  languageLabel,
  severity,
  SEVERITY_LABEL,
  type Severity,
} from "@/lib/format";

export function Stat({
  label,
  value,
  note,
  tone = "muted",
}: {
  label: string;
  value: string;
  note?: string;
  tone?: "muted" | "good" | "high" | "chain";
}) {
  const toneClass = { muted: "text-muted", good: "text-good", high: "text-high", chain: "text-chain" }[tone];
  return (
    <div className="card flex flex-col gap-1 px-4 py-3.5">
      <span className="label">{label}</span>
      <span className="tnum text-[26px] font-bold leading-tight">{value}</span>
      {note ? <span className={`font-mono text-[11.5px] ${toneClass}`}>{note}</span> : null}
    </div>
  );
}

export function SectionTitle({ children, aside }: { children: ReactNode; aside?: ReactNode }) {
  return (
    <div className="mb-2.5 flex items-baseline justify-between gap-3">
      <h2 className="label text-[12px]">{children}</h2>
      {aside ? <span className="text-[12px] text-muted">{aside}</span> : null}
    </div>
  );
}

const SEV_COLOR: Record<Severity, string> = { crit: "bg-crit", high: "bg-high", med: "bg-med" };
const SEV_TEXT: Record<Severity, string> = { crit: "text-crit", high: "text-high", med: "text-med" };

export function SeverityBar({ level, className = "" }: { level: Severity; className?: string }) {
  return (
    <span
      className={`inline-block w-1 rounded-sm ${SEV_COLOR[level]} ${className}`}
      aria-label={SEVERITY_LABEL[level]}
      title={SEVERITY_LABEL[level]}
    />
  );
}

export function SeverityText({ level }: { level: Severity }) {
  return <span className={`text-[12px] font-semibold ${SEV_TEXT[level]}`}>{SEVERITY_LABEL[level]}</span>;
}

/** Baris incident ringkas (beranda) dan penuh (tabel dashboard). */
export function IncidentCard({ row }: { row: IncidentRow }) {
  const level = severity(row);
  return (
    <Link
      href={`/incident/${row.incident_id}`}
      className="row-link grid grid-cols-[4px_minmax(0,1fr)_auto] items-center gap-3 rounded-md border border-line bg-bg px-3.5 py-3"
    >
      <SeverityBar level={level} className="h-11" />
      <span className="flex min-w-0 flex-col gap-1">
        <span className="truncate text-[14.5px] font-semibold">{incidentTitle(row.title)}</span>
        <span className="truncate font-mono text-[11.5px] text-muted">
          {attackCode(row.attack_type)} · {fmtNum(row.document_count)} sumber · keyakinan {fmtScore(row.incident_confidence)}
          {row.target ? ` · ${row.target}` : ""}
        </span>
      </span>
      <span className="chip">{fmtDate(row.last_published_date)}</span>
    </Link>
  );
}

export function IncidentTable({ rows }: { rows: IncidentRow[] }) {
  if (!rows.length) {
    return <div className="card px-4 py-8 text-center text-[13.5px] text-muted">Tidak ada incident yang cocok dengan saringan ini.</div>;
  }
  return (
    <div className="card overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[880px] border-collapse text-[13px]">
          <thead>
            <tr className="label border-b border-line text-left">
              <th className="w-2 px-3 py-2.5" aria-label="Keparahan" />
              <th className="px-2 py-2.5 font-medium">Incident</th>
              <th className="px-2 py-2.5 font-medium">Jenis</th>
              <th className="px-2 py-2.5 font-medium">Target</th>
              <th className="px-2 py-2.5 text-right font-medium">Sumber</th>
              <th className="px-2 py-2.5 text-right font-medium">Keyakinan</th>
              <th className="px-2 py-2.5 font-medium">Bahasa</th>
              <th className="px-3 py-2.5 font-medium">Terbaru</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const level = severity(row);
              return (
                <tr key={row.incident_id} className="border-b border-line last:border-b-0 hover:bg-accent/5">
                  <td className="px-3 py-2.5">
                    <SeverityBar level={level} className="h-7" />
                  </td>
                  <td className="max-w-[420px] px-2 py-2.5">
                    <Link href={`/incident/${row.incident_id}`} className="row-link block truncate font-semibold">
                      {incidentTitle(row.title)}
                    </Link>
                    {row.threat_actor ? (
                      <span className="font-mono text-[11px] text-muted">pelaku: {row.threat_actor}</span>
                    ) : null}
                  </td>
                  <td className="px-2 py-2.5 font-mono text-[11.5px]">{attackCode(row.attack_type).split(",")[0]}</td>
                  <td className="max-w-[200px] truncate px-2 py-2.5">
                    {row.target || <span className="text-muted">belum dikenali</span>}
                  </td>
                  <td className="tnum px-2 py-2.5 text-right font-mono">{fmtNum(row.document_count)}</td>
                  <td className="tnum px-2 py-2.5 text-right font-mono">{fmtScore(row.incident_confidence)}</td>
                  <td className="px-2 py-2.5 text-[12px] text-soft">{languageLabel(row.language)}</td>
                  <td className="px-3 py-2.5 font-mono text-[11.5px] text-muted">{fmtDate(row.last_published_date)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/** Grafik batang harian sebagai SVG berskala; label sumbu dari data nyata. */
export function DailyBars({ data }: { data: { d: string; n: number }[] }) {
  if (!data.length) return <p className="text-[13px] text-muted">Belum ada data pada rentang ini.</p>;
  const max = Math.max(...data.map((x) => Number(x.n)), 1);
  const w = 720;
  const h = 120;
  const pad = 4;
  const bw = (w - pad * 2) / data.length;
  return (
    <div className="flex flex-col gap-2">
      <svg viewBox={`0 0 ${w} ${h}`} className="h-[120px] w-full" role="img" aria-label="Incident baru per hari">
        <line x1={pad} x2={w - pad} y1={h - 1} y2={h - 1} stroke="var(--line)" />
        {data.map((x, i) => {
          const n = Number(x.n);
          const bh = Math.max(2, ((h - 8) * n) / max);
          const last = i === data.length - 1;
          return (
            <rect
              key={x.d}
              x={pad + i * bw + 1}
              y={h - 2 - bh}
              width={Math.max(2, bw - 2)}
              height={bh}
              rx={1.5}
              fill="var(--accent)"
              opacity={last ? 1 : 0.55}
            >
              <title>{`${x.d}: ${n} incident`}</title>
            </rect>
          );
        })}
      </svg>
      <div className="flex justify-between font-mono text-[10.5px] text-muted">
        <span>{fmtDate(data[0].d)}</span>
        <span>puncak {fmtNum(max)} per hari</span>
        <span>
          {fmtDate(data[data.length - 1].d)} · {fmtNum(Number(data[data.length - 1].n))} incident
        </span>
      </div>
    </div>
  );
}

export function TypeBars({ data }: { data: { t: string; n: number }[] }) {
  if (!data.length) return <p className="text-[13px] text-muted">Belum ada data.</p>;
  const max = Math.max(...data.map((x) => Number(x.n)), 1);
  return (
    <div className="flex flex-col gap-2">
      {data.map((x) => (
        <div key={x.t} className="grid grid-cols-[130px_minmax(0,1fr)_44px] items-center gap-2 text-[12.5px]">
          <span className="truncate">{attackLabel(x.t)}</span>
          <span className="block h-2 overflow-hidden rounded-sm bg-line">
            <span className="block h-full bg-accent" style={{ width: `${(100 * Number(x.n)) / max}%` }} />
          </span>
          <span className="tnum text-right font-mono">{fmtNum(Number(x.n))}</span>
        </div>
      ))}
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="card px-4 py-6 text-[13.5px] text-muted">{children}</div>;
}
