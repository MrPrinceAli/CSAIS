/**
 * Beranda, "incident dengan liputan terluas": kartu sorotan untuk peringkat 1
 * dan baris peringkat untuk sisanya. Komponen server; angka memakai CountUp.
 */
import Image from "next/image";
import Link from "next/link";
import type { Severity } from "@/lib/format";
import type { getDict, Lang } from "@/lib/i18n";
import type { Trust } from "@/lib/trust";
import { CountUp } from "@/components/reveal";
import { SeverityText, SourceLogo, TrustRing } from "@/components/ui";

type Labels = ReturnType<typeof getDict>["home"]["coverage"];
const sv = (o: Record<string, string | number>) => o as React.CSSProperties;

export type CoverageItem = {
  id: string;
  href: string;
  rank: number;
  title: string;
  target: string | null;
  type: string;
  severity: Severity;
  articles: number;
  publishers: number;
  trust: Trust;
  image: string | null;
  /** artikel per hari dari hari pertama sampai terakhir; setiap artikel dengan --t hari relatifnya */
  days: number[];
  ticks: number[];
  firstDate: string;
  lastDate: string;
  logos: { name: string; domain: string | null }[];
  morePublishers: number;
};

function Publishers({ item, labels, size = 18 }: { item: CoverageItem; labels: Labels; size?: number }) {
  return (
    <span className="flex flex-wrap items-center gap-1.5">
      {item.logos.map((p) =>
        p.domain ? (
          <span key={p.name} title={p.name}>
            <SourceLogo domain={p.domain} size={size} />
          </span>
        ) : (
          <span key={p.name} className="cov-mono" style={{ width: size + 8, height: size + 8 }} title={p.name}>
            {p.name.replace(/[^\p{L}\p{N}]/gu, "").slice(0, 2)}
          </span>
        ),
      )}
      {item.morePublishers > 0 ? <span className="font-mono text-[11px] text-muted">{labels.more(String(item.morePublishers))}</span> : null}
    </span>
  );
}

/**
 * Histogram titik: satu kolom per hari selebar kartu; di dalam kolom, titik
 * (satu per artikel) tersusun bertingkat dari bawah. Titik pertama = laporan pertama.
 */
function DotHistogram({ item }: { item: CoverageItem }) {
  const span = Math.max(1, item.days.length - 1);
  let index = 0;
  return (
    <span className="grid items-end gap-2" style={{ gridTemplateColumns: `repeat(${item.days.length}, minmax(0, 1fr))` }} aria-hidden="true">
      {item.days.map((n, d) => (
        <span key={d} className="flex flex-wrap-reverse content-start gap-[3px] border-b border-line/80 pb-1.5">
          {Array.from({ length: n }, (_, k) => {
            const i = index++;
            return <span key={k} className={`cov-dot cov-tone ${i === 0 ? "is-first" : ""}`} style={sv({ "--t": (d / span).toFixed(3), "--i": Math.min(i, 140) })} />;
          })}
        </span>
      ))}
    </span>
  );
}

export function CoverageFeature({ item, labels, lang, locale }: { item: CoverageItem; labels: Labels; lang: Lang; locale: string }) {
  return (
    <Link href={item.href} className="cov-feature card lift row-link flex min-h-[480px] flex-col justify-end p-5 sm:p-6">
      {item.image ? (
        <Image src={item.image} alt="" fill unoptimized sizes="(min-width: 1024px) 55vw, 100vw" className="cov-img -z-10 object-cover opacity-50" />
      ) : (
        <span className="cov-fallback absolute inset-0 -z-10" aria-hidden="true">
          <span className="cov-bgword">{item.type}</span>
        </span>
      )}
      <span className="cov-shade absolute inset-0 -z-10" aria-hidden="true" />

      <span className="flex flex-col gap-4">
        <span className="flex flex-wrap items-center gap-3">
          <span className="cov-rank text-[64px]">#{item.rank}</span>
          <span className="flex flex-col gap-1.5">
            <SeverityText level={item.severity} lang={lang} />
            <span className="chip">{item.type}</span>
          </span>
        </span>
        <span className="line-clamp-3 max-w-[32ch] text-balance text-[24px] font-semibold leading-tight sm:text-[28px]">{item.title}</span>
        {item.target ? (
          <span className="chip chip-accent self-start">
            <span className="text-muted">{labels.victim}</span> {item.target}
          </span>
        ) : null}

        <span className="grid grid-cols-3 gap-3 border-y border-line/80 py-3">
          <span className="flex flex-col">
            <CountUp value={item.articles} locale={locale} className="text-[28px] font-semibold leading-none" />
            <span className="label pt-1.5">{labels.articles}</span>
          </span>
          <span className="flex flex-col">
            <CountUp value={item.publishers} locale={locale} className="text-[28px] font-semibold leading-none" />
            <span className="label pt-1.5">{labels.publishers}</span>
          </span>
          <span className="flex items-center gap-2.5">
            <TrustRing trust={item.trust} lang={lang} size={46} />
            <span className="label hidden sm:inline">{labels.trust}</span>
          </span>
        </span>

        <span className="flex flex-col gap-2">
          <DotHistogram item={item} />
          <span className="flex flex-wrap items-center justify-between gap-2 font-mono text-[10.5px] text-muted">
            <span>{item.firstDate}</span>
            <span className="flex items-center gap-2">
              <span className="inline-block h-2 w-2 rounded-[2px] bg-white shadow-[0_0_0_2px_var(--accent)]" aria-hidden="true" />
              {labels.first}
              <span className="cov-legend ml-2 inline-block h-1.5 w-10 rounded-sm" aria-hidden="true" />
              {labels.early} → {labels.late}
            </span>
            <span>{item.lastDate}</span>
          </span>
          <span className="text-[11.5px] text-muted">{labels.dots}</span>
        </span>

        <Publishers item={item} labels={labels} />
      </span>
    </Link>
  );
}

export function CoverageRow({ item, labels, lang, index }: { item: CoverageItem; labels: Labels; lang: Lang; index: number }) {
  const shown = item.ticks.slice(0, 90);
  return (
    <Link href={item.href} className="card lift row-link fade-up grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-4 p-4" style={sv({ "--i": index * 2 })}>
      <span className="cov-rank w-[2.2ch] text-[40px]">{String(item.rank).padStart(2, "0")}</span>
      <span className="flex min-w-0 flex-col gap-2">
        <span className="line-clamp-2 text-[14.5px] font-semibold leading-snug">{item.title}</span>
        <span className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1 font-mono text-[11px] text-muted">
          <span>{item.type}</span>
          <span>·</span>
          <span>
            {item.publishers} {labels.publishers}
          </span>
          {item.target ? (
            <>
              <span>·</span>
              <span className="truncate text-accent">{item.target}</span>
            </>
          ) : null}
        </span>
        <span className="flex items-end gap-2">
          <span className="flex flex-wrap items-end gap-[2px]" aria-hidden="true">
            {shown.map((t, i) => (
              <i key={i} className="cov-tick cov-tone" style={sv({ "--t": t.toFixed(3), "--i": i, "--row": index })} />
            ))}
          </span>
          <span className="whitespace-nowrap font-mono text-[12px] text-fg">
            {item.articles}
            <span className="text-muted"> {labels.articles}</span>
          </span>
        </span>
      </span>
      <TrustRing trust={item.trust} lang={lang} size={40} />
    </Link>
  );
}
