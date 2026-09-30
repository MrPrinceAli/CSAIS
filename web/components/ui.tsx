import Image from "next/image";
import Link from "next/link";
import type { ReactNode } from "react";
import type { IncidentRow } from "@/lib/queries";
import { glyphFor, IncidentThumb } from "@/components/incident-thumb";
import { attackCode, formatters, incidentTitle, severity, type Severity } from "@/lib/format";
import { attackLabel, getDict, L, type Lang } from "@/lib/i18n";
import { trustFromRow, TRUST_COLOR, type Trust } from "@/lib/trust";

export function Stat({ label, value, note, tone = "muted", live = false }: { label: string; value: ReactNode; note?: ReactNode; tone?: "muted" | "good" | "high" | "chain" | "accent"; live?: boolean }) {
  const toneClass = { muted: "text-muted", good: "text-good", high: "text-high", chain: "text-chain", accent: "text-accent" }[tone];
  const topColor = { muted: "var(--line-2)", good: "var(--good)", high: "var(--high)", chain: "var(--chain)", accent: "var(--accent)" }[tone];
  return (
    <div className="card lift flex flex-col gap-1 px-4 py-3.5" style={{ borderTopColor: topColor, borderTopWidth: 2 }}>
      <span className="label inline-flex items-center gap-2">
        {live ? <span className="led led-accent" aria-hidden="true" /> : null}
        {label}
      </span>
      <span className="tnum text-[26px] font-semibold leading-tight tracking-tight">{value}</span>
      {note ? <span className={`text-[12.5px] ${toneClass}`}>{note}</span> : null}
    </div>
  );
}

export function SectionTitle({ children, aside }: { children: ReactNode; aside?: ReactNode }) {
  return (
    <div className="mb-3 flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
      <h2 className="label">{children}</h2>
      {aside ? <span className="text-[12px] text-muted">{aside}</span> : null}
    </div>
  );
}

const SEV_COLOR: Record<Severity, string> = { crit: "bg-crit", high: "bg-high", med: "bg-med" };
const SEV_TEXT: Record<Severity, string> = { crit: "text-crit", high: "text-high", med: "text-med" };

export function SeverityBar({ level, lang, className = "" }: { level: Severity; lang: Lang; className?: string }) {
  const label = getDict(lang).severity[level];
  return <span className={`inline-block w-1 rounded-sm ${SEV_COLOR[level]} ${className}`} aria-label={label} title={label} />;
}

export function SeverityText({ level, lang }: { level: Severity; lang: Lang }) {
  return <span className={`text-[12px] font-semibold ${SEV_TEXT[level]}`}>{getDict(lang).severity[level]}</span>;
}

/** Cincin indeks kepercayaan: SVG berskala, warna sesuai tingkat. */
export function TrustRing({ trust, lang, size = 44, showLabel = false }: { trust: Trust; lang: Lang; size?: number; showLabel?: boolean }) {
  const t = getDict(lang);
  const r = (size - 6) / 2;
  const c = 2 * Math.PI * r;
  const pct = Math.round(trust.score * 100);
  const level = t.levels[trust.level];
  return (
    <span className="inline-flex items-center gap-2" title={`${t.trust.title} ${pct}/100 (${level})`}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label={`${t.trust.title} ${pct}/100`}>
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
          className="ring-arc"
        />
        <text x="50%" y="50%" dy="0.36em" textAnchor="middle" fontSize={size >= 60 ? 16 : 11} fontWeight="600" fill="var(--fg)" fontFamily="var(--font-jet), monospace">
          {pct}
        </text>
      </svg>
      {showLabel ? (
        <span className="text-[12px] capitalize" style={{ color: TRUST_COLOR[trust.level] }}>
          {level}
        </span>
      ) : null}
    </span>
  );
}

/** Tumpukan logo domain sumber (maksimal empat) dengan sisa sebagai angka. */
export function LogoStack({ domains, max = 4, size = 16 }: { domains: string[]; max?: number; size?: number }) {
  const shown = domains.slice(0, max);
  const rest = domains.length - shown.length;
  if (!shown.length) return null;
  return (
    <span className="inline-flex items-center">
      {shown.map((d, i) => (
        <span key={d} className={i ? "-ml-2" : ""} style={{ zIndex: max - i }}>
          <SourceLogo domain={d} size={size} />
        </span>
      ))}
      {rest > 0 ? <span className="ml-1 font-mono text-[11px] text-muted">+{rest}</span> : null}
    </span>
  );
}

export function IncidentCard({ row, lang, index = 0, thumb = false }: { row: IncidentRow; lang: Lang; index?: number; thumb?: boolean }) {
  const f = formatters(lang);
  const t = getDict(lang);
  const level = severity(row);
  const trust = trustFromRow(row);
  const domains = (row.domain_list ?? "").split(",").map((d) => d.trim()).filter(Boolean);
  return (
    <Link
      href={L(lang, `/incidents/${row.incident_id}`)}
      scroll={thumb ? false : undefined}
      className={`row-link lift fade-up grid items-center gap-3 rounded-md border border-line bg-bg px-3.5 py-3 ${
        thumb ? "grid-cols-[4px_76px_minmax(0,1fr)_auto] sm:grid-cols-[4px_104px_minmax(0,1fr)_auto]" : "grid-cols-[4px_minmax(0,1fr)_auto]"
      }`}
      style={{ "--i": index } as React.CSSProperties}
    >
      <SeverityBar level={level} lang={lang} className={thumb ? "h-14" : "h-11"} />
      {thumb ? <IncidentThumb id={row.incident_id} attackType={row.attack_type} className="aspect-[4/3] w-full" /> : null}
      <span className="flex min-w-0 flex-col gap-1.5">
        <span className={`text-[14px] font-semibold ${thumb ? "line-clamp-2 leading-snug" : "truncate"}`}>{incidentTitle(row.title)}</span>
        <span className="flex min-w-0 items-center gap-2">
          <LogoStack domains={domains} />
          <TierBadge tier={row.alert_tier} lang={lang} institution={row.alert_institution} demo={Boolean(row.alert_demo)} quiet />
          <TypeChip attackType={row.attack_type} lang={lang} />
          <span className="truncate text-[12.5px] text-muted">
            {f.num(row.document_count)} {t.common.articles} · {f.num(Number(row.domains ?? 0))} {t.common.domains}
            {row.target ? ` · ${row.target}` : ""}
          </span>
        </span>
      </span>
      <TrustRing trust={trust} lang={lang} size={40} />
    </Link>
  );
}

/**
 * Grafik batang harian sebagai SVG berskala. Dengan `hrefFor`, tiap batang
 * menjadi tautan filter per tanggal; `selected` menandai tanggal yang aktif.
 */
const TIER_TONE: Record<string, string> = {
  peringatan_dini: "var(--accent)",
  waspada: "var(--med)",
  rekomendasi_resmi: "var(--good)",
  peringatan_hoaks: "var(--high)",
};

/** Lencana status peringatan terkini; `quiet` menyembunyikan peringatan dini (tingkat bawaan semua incident). */
/** Penanda data uji (scripts demo); tampil di mana pun data itu muncul. */
export function DemoChip({ lang }: { lang: Lang }) {
  return (
    <span className="inline-flex items-center rounded border border-dashed px-1.5 py-0.5 font-mono text-[10.5px] font-semibold tracking-wide" style={{ borderColor: "var(--muted)", color: "var(--muted)" }} title={getDict(lang).demo.hint}>
      {getDict(lang).demo.label}
    </span>
  );
}

export function TierBadge({ tier, lang, institution, quiet = false, demo = false, className = "" }: { tier: string | null; lang: Lang; institution?: string | null; quiet?: boolean; demo?: boolean; className?: string }) {
  if (!tier || (quiet && tier === "peringatan_dini")) return null;
  const t = getDict(lang);
  const tone = TIER_TONE[tier] ?? "var(--muted)";
  return (
    <span
      className={`inline-flex flex-none items-center gap-1.5 whitespace-nowrap rounded-full border px-2 py-0.5 text-[11.5px] font-semibold ${className}`}
      style={{ borderColor: tone, color: tone, background: `color-mix(in srgb, ${tone} 12%, transparent)` }}
    >
      <span className="h-1.5 w-1.5 rounded-full" style={{ background: tone }} aria-hidden="true" />
      {t.flows.tiers[tier] ?? tier}
      {institution ? <span className="font-normal">· {institution}</span> : null}
      {demo ? <span className="font-mono text-[10px] font-normal opacity-80">· {t.demo.label}</span> : null}
    </span>
  );
}

/** Label jenis serangan berwarna; nada sama dengan ikon jenis serangan. */
export function TypeChip({ attackType, lang, className = "" }: { attackType: string | null; lang: Lang; className?: string }) {
  return (
    <span className={`type-chip ${className}`} style={{ "--tone": glyphFor(attackType).tone } as React.CSSProperties}>
      {attackLabel(attackType, lang)}
    </span>
  );
}

export function DailyBars({
  data,
  lang,
  height = 120,
  accent = "var(--accent)",
  selected,
  hrefFor,
}: {
  data: { d: string; n: number }[];
  lang: Lang;
  height?: number;
  accent?: string;
  selected?: string;
  hrefFor?: Record<string, string>;
}) {
  const f = formatters(lang);
  if (!data.length) return <p className="text-[13px] text-muted">{getDict(lang).common.notAvailable}</p>;
  const max = Math.max(...data.map((x) => Number(x.n)), 1);
  const w = 720;
  const pad = 4;
  const bw = (w - pad * 2) / data.length;
  const last = data[data.length - 1];
  const picked = selected ? data.find((x) => x.d === selected) : undefined;
  return (
    <div className="flex flex-col gap-2">
      <svg viewBox={`0 0 ${w} ${height}`} className={`w-full${hrefFor ? " day-bars" : ""}`} style={{ height }} role="img" aria-label={`${f.num(max)} max`}>
        <line x1={pad} x2={w - pad} y1={height - 1} y2={height - 1} stroke="var(--line)" />
        {data.map((x, i) => {
          const n = Number(x.n);
          const bh = Math.max(2, ((height - 8) * n) / max);
          const on = selected ? x.d === selected : i === data.length - 1;
          const bar = (
            <rect x={pad + i * bw + 1} y={height - 2 - bh} width={Math.max(2, bw - 2)} height={bh} rx={1} fill={accent} opacity={on ? 1 : selected ? 0.28 : 0.5} className="bar-rise" style={{ "--i": i } as React.CSSProperties}>
              <title>{`${f.date(x.d)}: ${n}`}</title>
            </rect>
          );
          const href = hrefFor?.[x.d];
          if (!href) return <g key={x.d}>{bar}</g>;
          return (
            <Link key={x.d} href={href} scroll={false} aria-label={`${f.date(x.d)}: ${n}`} aria-current={x.d === selected ? "true" : undefined}>
              <rect x={pad + i * bw} y={0} width={bw} height={height} fill="transparent" className="day-hit" />
              {bar}
            </Link>
          );
        })}
      </svg>
      <div className="flex justify-between font-mono text-[11px] text-muted">
        <span>{f.date(data[0].d)}</span>
        <span>max {f.num(max)}</span>
        <span>{picked ? <b className="font-medium text-accent">{f.date(picked.d)} · {f.num(Number(picked.n))}</b> : `${f.date(last.d)} · ${f.num(Number(last.n))}`}</span>
      </div>
    </div>
  );
}

export function LabelBars({ data, max }: { data: { label: string; n: number; text: string; href?: string }[]; max?: number }) {
  const top = max ?? Math.max(...data.map((x) => x.n), 1);
  return (
    <div className="flex flex-col gap-2">
      {data.map((x, i) => {
        const inner = (
          <>
            <span className="truncate">{x.label}</span>
            <span className="block h-1.5 overflow-hidden rounded-sm bg-line">
              <span className="bar-fill block h-full bg-accent" style={{ width: `${Math.max(1, (100 * x.n) / top)}%`, "--i": i } as React.CSSProperties} />
            </span>
            <span className="tnum text-right font-mono">{x.text}</span>
          </>
        );
        const cls = "grid grid-cols-[130px_minmax(0,1fr)_52px] items-center gap-2 text-[12.5px]";
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
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label={values.join(", ")}>
      <path d={`${path} L${width},${height} L0,${height} Z`} fill={color} opacity="0.12" className="draw-fill" />
      <path d={path} fill="none" stroke={color} strokeWidth="1.5" pathLength={1} className="draw" />
      <circle cx={(values.length - 1) * step} cy={height - 2 - ((height - 4) * values[values.length - 1]) / max} r="2.5" fill={color} className="draw-fill" />
    </svg>
  );
}

/** Sidik jari hash: 64 heksadesimal menjadi kisi 8×8. */
export function HashGrid({ hex, size = 96, label }: { hex: string | null | undefined; size?: number; label: string }) {
  const clean = (hex ?? "").toLowerCase().replace(/[^0-9a-f]/g, "");
  const cells = Array.from({ length: 64 }, (_, i) => Number.parseInt(clean[i % Math.max(1, clean.length)] ?? "0", 16));
  const cell = size / 8;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label={label} className="rounded-md">
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
          className="hash-cell"
          style={{ "--i": i } as React.CSSProperties}
        />
      ))}
    </svg>
  );
}

/** Logo domain dari layanan favicon. */
export function SourceLogo({ domain, size = 24 }: { domain: string; size?: number }) {
  return (
    <span className="inline-flex flex-none items-center justify-center overflow-hidden rounded-md border border-line bg-nav" style={{ width: size + 8, height: size + 8 }}>
      <Image src={`https://www.google.com/s2/favicons?domain=${encodeURIComponent(domain)}&sz=64`} alt="" width={size} height={size} unoptimized loading="lazy" />
    </span>
  );
}

export function TrustLegend({ lang }: { lang: Lang }) {
  return <p className="max-w-[100ch] text-[12px] leading-relaxed text-muted">{getDict(lang).trust.legend}</p>;
}

export { attackCode };
