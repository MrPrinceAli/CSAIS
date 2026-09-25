import Image from "next/image";
import Link from "next/link";
import type { ReactNode } from "react";
import type { IncidentRow } from "@/lib/queries";
import { attackCode, attackLabel, fmtDate, fmtNum, fmtScore, incidentTitle, languageLabel, severity, SEVERITY_LABEL, type Severity } from "@/lib/format";
import { trustFromRow, TRUST_COLOR, type Trust } from "@/lib/trust";

export function Stat({ label, value, note, tone = "muted" }: { label: string; value: ReactNode; note?: ReactNode; tone?: "muted" | "good" | "high" | "chain" | "accent" }) {
  const toneClass = { muted: "text-muted", good: "text-good", high: "text-high", chain: "text-chain", accent: "text-accent" }[tone];
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
    <div className="mb-2.5 flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
      <h2 className="label text-[12px]">{children}</h2>
      {aside ? <span className="text-[12px] text-muted">{aside}</span> : null}
    </div>
  );
}

const SEV_COLOR: Record<Severity, string> = { crit: "bg-crit", high: "bg-high", med: "bg-med" };
const SEV_TEXT: Record<Severity, string> = { crit: "text-crit", high: "text-high", med: "text-med" };

export function SeverityBar({ level, className = "" }: { level: Severity; className?: string }) {
  return <span className={`inline-block w-1 rounded-sm ${SEV_COLOR[level]} ${className}`} aria-label={SEVERITY_LABEL[level]} title={SEVERITY_LABEL[level]} />;
}

export function SeverityText({ level }: { level: Severity }) {
  return <span className={`text-[12px] font-semibold ${SEV_TEXT[level]}`}>{SEVERITY_LABEL[level]}</span>;
}

/** Cincin skor kepercayaan: SVG berskala, warna sesuai tingkat. */
export function TrustRing({ trust, size = 44, showLabel = false }: { trust: Trust; size?: number; showLabel?: boolean }) {
  const r = (size - 6) / 2;
  const c = 2 * Math.PI * r;
  const pct = Math.round(trust.score * 100);
  return (
    <span className="inline-flex items-center gap-2" title={`Skor kepercayaan sementara ${pct} dari 100 (${trust.level})`}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label={`Skor kepercayaan ${pct} dari 100`}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--line)" strokeWidth="4" />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={TRUST_COLOR[trust.level]}
          strokeWidth="4"
          strokeLinecap="round"
          strokeDasharray={`${c * trust.score} ${c}`}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
        />
        <text x="50%" y="50%" dy="0.36em" textAnchor="middle" fontSize={size >= 60 ? 16 : 11} fontWeight="700" fill="var(--fg)" fontFamily="var(--font-jet), monospace">
          {pct}
        </text>
      </svg>
      {showLabel ? <span className="text-[12px] capitalize" style={{ color: TRUST_COLOR[trust.level] }}>{trust.level}</span> : null}
    </span>
  );
}

export function IncidentCard({ row }: { row: IncidentRow }) {
  const level = severity(row);
  const trust = trustFromRow(row);
  return (
    <Link href={`/incident/${row.incident_id}`} className="row-link grid grid-cols-[4px_minmax(0,1fr)_auto] items-center gap-3 rounded-md border border-line bg-bg px-3.5 py-3">
      <SeverityBar level={level} className="h-11" />
      <span className="flex min-w-0 flex-col gap-1">
        <span className="truncate text-[14.5px] font-semibold">{incidentTitle(row.title)}</span>
        <span className="truncate font-mono text-[11.5px] text-muted">
          {attackCode(row.attack_type).split(",")[0]} · {fmtNum(row.document_count)} artikel · {fmtNum(Number(row.domains ?? 0))} domain
          {row.target ? ` · ${row.target}` : ""}
        </span>
      </span>
      <TrustRing trust={trust} size={40} />
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
        <table className="w-full min-w-[920px] border-collapse text-[13px]">
          <thead>
            <tr className="label border-b border-line text-left">
              <th className="w-2 px-3 py-2.5" aria-label="Keparahan" />
              <th className="px-2 py-2.5 font-medium">Incident</th>
              <th className="px-2 py-2.5 font-medium">Jenis</th>
              <th className="px-2 py-2.5 font-medium">Sumber</th>
              <th className="px-2 py-2.5 font-medium">Kepercayaan</th>
              <th className="px-2 py-2.5 font-medium">Bahasa</th>
              <th className="px-3 py-2.5 font-medium">Terbaru</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const level = severity(row);
              const trust = trustFromRow(row);
              return (
                <tr key={row.incident_id} className="border-b border-line last:border-b-0 hover:bg-accent/5">
                  <td className="px-3 py-2.5">
                    <SeverityBar level={level} className="h-9" />
                  </td>
                  <td className="max-w-[460px] px-2 py-2.5">
                    <Link href={`/incident/${row.incident_id}`} className="row-link block truncate font-semibold">
                      {incidentTitle(row.title)}
                    </Link>
                    <span className="flex flex-wrap gap-1.5 pt-1">
                      {row.target ? <span className="chip">{row.target}</span> : <span className="chip text-muted">target belum dikenali</span>}
                      {row.threat_actor ? <span className="chip chip-accent">{row.threat_actor.split(",")[0]}</span> : null}
                      {row.location ? <span className="chip">{row.location.split(",")[0]}</span> : null}
                    </span>
                  </td>
                  <td className="px-2 py-2.5 font-mono text-[11.5px]">{attackCode(row.attack_type).split(",")[0]}</td>
                  <td className="px-2 py-2.5">
                    <span className="tnum font-mono text-[13px]">{fmtNum(row.document_count)}</span>
                    <span className="block font-mono text-[11px] text-muted">{fmtNum(Number(row.domains ?? 0))} domain</span>
                  </td>
                  <td className="px-2 py-2.5">
                    <TrustRing trust={trust} size={40} />
                  </td>
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

/** Grafik batang harian sebagai SVG berskala. */
export function DailyBars({ data, height = 120, accent = "var(--accent)" }: { data: { d: string; n: number }[]; height?: number; accent?: string }) {
  if (!data.length) return <p className="text-[13px] text-muted">Belum ada data pada rentang ini.</p>;
  const max = Math.max(...data.map((x) => Number(x.n)), 1);
  const w = 720;
  const pad = 4;
  const bw = (w - pad * 2) / data.length;
  return (
    <div className="flex flex-col gap-2">
      <svg viewBox={`0 0 ${w} ${height}`} className="w-full" style={{ height }} role="img" aria-label="Jumlah per hari">
        <line x1={pad} x2={w - pad} y1={height - 1} y2={height - 1} stroke="var(--line)" />
        {data.map((x, i) => {
          const n = Number(x.n);
          const bh = Math.max(2, ((height - 8) * n) / max);
          const last = i === data.length - 1;
          return (
            <rect key={x.d} x={pad + i * bw + 1} y={height - 2 - bh} width={Math.max(2, bw - 2)} height={bh} rx={1.5} fill={accent} opacity={last ? 1 : 0.55}>
              <title>{`${x.d}: ${n}`}</title>
            </rect>
          );
        })}
      </svg>
      <div className="flex justify-between font-mono text-[10.5px] text-muted">
        <span>{fmtDate(data[0].d)}</span>
        <span>puncak {fmtNum(max)} per hari</span>
        <span>
          {fmtDate(data[data.length - 1].d)} · {fmtNum(Number(data[data.length - 1].n))}
        </span>
      </div>
    </div>
  );
}

export function TypeBars({ data, hrefFor }: { data: { t: string; n: number }[]; hrefFor?: (t: string) => string }) {
  if (!data.length) return <p className="text-[13px] text-muted">Belum ada data.</p>;
  const max = Math.max(...data.map((x) => Number(x.n)), 1);
  return (
    <div className="flex flex-col gap-2">
      {data.map((x) => {
        const label = attackLabel(x.t);
        const inner = (
          <>
            <span className="truncate">{label}</span>
            <span className="block h-2 overflow-hidden rounded-sm bg-line">
              <span className="block h-full bg-accent" style={{ width: `${(100 * Number(x.n)) / max}%` }} />
            </span>
            <span className="tnum text-right font-mono">{fmtNum(Number(x.n))}</span>
          </>
        );
        const cls = "grid grid-cols-[130px_minmax(0,1fr)_44px] items-center gap-2 text-[12.5px]";
        return hrefFor ? (
          <Link key={x.t} href={hrefFor(x.t)} className={`${cls} text-fg no-underline hover:text-accent`}>
            {inner}
          </Link>
        ) : (
          <div key={x.t} className={cls}>
            {inner}
          </div>
        );
      })}
    </div>
  );
}

export function LabelBars({ data, max }: { data: { label: string; n: number; href?: string }[]; max?: number }) {
  const top = max ?? Math.max(...data.map((x) => x.n), 1);
  return (
    <div className="flex flex-col gap-2">
      {data.map((x) => {
        const inner = (
          <>
            <span className="truncate">{x.label}</span>
            <span className="block h-2 overflow-hidden rounded-sm bg-line">
              <span className="block h-full bg-accent" style={{ width: `${(100 * x.n) / top}%` }} />
            </span>
            <span className="tnum text-right font-mono">{fmtNum(x.n)}</span>
          </>
        );
        const cls = "grid grid-cols-[130px_minmax(0,1fr)_44px] items-center gap-2 text-[12.5px]";
        return x.href ? (
          <Link key={x.label} href={x.href} className={`${cls} text-fg no-underline hover:text-accent`}>
            {inner}
          </Link>
        ) : (
          <div key={x.label} className={cls}>
            {inner}
          </div>
        );
      })}
    </div>
  );
}

/** Sparkline kecil dari deret angka. */
export function Sparkline({ values, width = 120, height = 32, color = "var(--accent)" }: { values: number[]; width?: number; height?: number; color?: string }) {
  if (!values.length) return null;
  const max = Math.max(...values, 1);
  const step = values.length > 1 ? width / (values.length - 1) : width;
  const points = values.map((v, i) => `${(i * step).toFixed(1)},${(height - 2 - ((height - 4) * v) / max).toFixed(1)}`);
  const path = `M${points.join(" L")}`;
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`Tren: ${values.join(", ")}`}>
      <path d={`${path} L${width},${height} L0,${height} Z`} fill={color} opacity="0.12" />
      <path d={path} fill="none" stroke={color} strokeWidth="1.5" />
      <circle cx={(values.length - 1) * step} cy={height - 2 - ((height - 4) * values[values.length - 1]) / max} r="2.5" fill={color} />
    </svg>
  );
}

/** Sidik jari hash: 64 heksadesimal menjadi kisi 8x8 berwarna; hash beda, pola beda. */
export function HashGrid({ hex, size = 96, label }: { hex: string | null | undefined; size?: number; label?: string }) {
  const clean = (hex ?? "").toLowerCase().replace(/[^0-9a-f]/g, "");
  const cells = Array.from({ length: 64 }, (_, i) => Number.parseInt(clean[i % Math.max(1, clean.length)] ?? "0", 16));
  const cell = size / 8;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label={label ?? "Sidik jari hash"} className="rounded-md">
      <rect width={size} height={size} fill="var(--nav)" />
      {cells.map((v, i) => (
        <rect
          key={i}
          x={(i % 8) * cell}
          y={Math.floor(i / 8) * cell}
          width={cell}
          height={cell}
          fill={v >= 12 ? "var(--accent)" : v >= 8 ? "var(--chain)" : v >= 4 ? "var(--line-2)" : "transparent"}
          opacity={clean ? 0.35 + (v / 15) * 0.65 : 0.2}
        />
      ))}
    </svg>
  );
}

/** Logo domain dari layanan favicon; fallback inisial bila gagal dimuat. */
export function SourceLogo({ domain, size = 24 }: { domain: string; size?: number }) {
  return (
    <span className="inline-flex flex-none items-center justify-center overflow-hidden rounded-md border border-line bg-nav" style={{ width: size + 8, height: size + 8 }}>
      <Image
        src={`https://www.google.com/s2/favicons?domain=${encodeURIComponent(domain)}&sz=64`}
        alt=""
        width={size}
        height={size}
        unoptimized
        loading="lazy"
      />
    </span>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="card px-4 py-6 text-[13.5px] text-muted">{children}</div>;
}

export function ScoreLegend() {
  return (
    <p className="text-[12px] text-muted">
      Skor kepercayaan sementara: dikuatkan domain berbeda, sumber independen (bukan salinan), nama korban jelas, isi
      artikel tersedia, dan keyakinan pengelompokan. Trust score resmi (Step 3) akan menambahkan riwayat sumber dan
      atestasi lembaga.
    </p>
  );
}

export { fmtScore };
