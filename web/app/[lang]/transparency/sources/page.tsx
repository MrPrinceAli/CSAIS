import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getSources, getTopSourceDomains, type SourceFilters } from "@/lib/queries";
import { LogoMarquee } from "@/components/logo-marquee";
import { SearchField } from "@/components/search-field";
import { isoLabel } from "@/lib/geo";
import { formatters } from "@/lib/format";
import { getDict, isLang, L } from "@/lib/i18n";
import { Pagination } from "@/components/pagination";
import { LabelBars, SectionTitle, SourceLogo, Stat } from "@/components/ui";

type Search = Record<string, string | string[] | undefined>;

export async function generateMetadata({ params }: { params: Promise<{ lang: string }> }): Promise<Metadata> {
  const { lang } = await params;
  return { title: getDict(isLang(lang) ? lang : "id").sources.title };
}

function first(value: string | string[] | undefined): string {
  return Array.isArray(value) ? (value[0] ?? "") : (value ?? "");
}

function parse(sp: Search): SourceFilters {
  const page = Number.parseInt(first(sp.page), 10);
  return {
    q: first(sp.q).trim().slice(0, 60) || undefined,
    tipe: ["media", "official", "blog"].includes(first(sp.tipe).toLowerCase()) ? first(sp.tipe).toLowerCase() : undefined,
    negara: first(sp.negara).trim().slice(0, 8) || undefined,
    urut: ["artikel", "terbaru", "nama"].includes(first(sp.urut)) ? first(sp.urut) : undefined,
    page: Number.isFinite(page) && page > 0 ? page : 1,
  };
}

function params(f: SourceFilters): Record<string, string | undefined> {
  return { q: f.q, tipe: f.tipe, negara: f.negara, urut: f.urut };
}

export default async function SourcesPage({ params: p, searchParams }: { params: Promise<{ lang: string }>; searchParams: Promise<Search> }) {
  const { lang } = await p;
  if (!isLang(lang)) notFound();
  const t = getDict(lang);
  const f = formatters(lang);
  const filters = parse(await searchParams);
  const base = L(lang, "/transparency/sources");
  const hrefWith = (overrides: Record<string, string | undefined>) => {
    const sp = new URLSearchParams();
    for (const [k, v] of Object.entries({ ...params(filters), ...overrides })) if (v) sp.set(k, v);
    const s = sp.toString();
    return s ? `${base}?${s}` : base;
  };
  const [data, topDomains] = await Promise.all([getSources(filters), getTopSourceDomains(28)]);
  const totalArticles = data.byType.reduce((acc, x) => acc + Number(x.artikel), 0);
  const typeLabel = (type: string) => t.sources.types[type.toLowerCase() as keyof typeof t.sources.types] ?? type.toLowerCase();

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-col gap-1">
        <h1 className="text-[24px] font-semibold">{t.sources.title}</h1>
        <p className="max-w-[84ch] text-[13.5px] text-muted">{t.sources.lead}</p>
      </div>

      <LogoMarquee domains={topDomains} note={t.sources.marqueeNote} />

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label={t.sources.stats.domains} value={f.num(data.byType.reduce((acc, x) => acc + Number(x.n), 0))} note={t.sources.statNotes.domains(f.num(totalArticles))} />
        <Stat label={t.sources.stats.media} value={f.num(Number(data.byType.find((x) => x.source_type === "MEDIA")?.n ?? 0))} note={t.sources.statNotes.media} />
        <Stat label={t.sources.stats.official} value={f.num(Number(data.byType.find((x) => x.source_type === "OFFICIAL")?.n ?? 0))} note={t.sources.statNotes.official} tone="high" />
        <Stat label={t.sources.stats.countries} value={f.num(data.byCountry.filter((c) => c.country !== "unknown").length)} note={t.sources.statNotes.countries} />
      </div>

      <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
        <div className="card p-4">
          <SectionTitle aside={t.incidents.clickToFilter}>{t.sources.countriesTitle}</SectionTitle>
          <LabelBars
            data={data.byCountry.map((c) => ({
              label: isoLabel(c.country),
              n: Number(c.n),
              text: f.num(Number(c.n)),
              href: hrefWith({ negara: c.country, page: undefined }),
            }))}
          />
        </div>
        <form method="get" action={base} className="card flex flex-wrap content-start items-end gap-3 p-3.5">
          <label className="flex min-w-[200px] flex-1 flex-col gap-1 text-[12px] text-muted">
            {t.sources.filters.search}
            <SearchField id="q" name="q" defaultValue={filters.q ?? ""} placeholder={t.sources.filters.searchPlaceholder} examples={["detik", "bleepingcomputer", "kompas", "bssn"]} className="field" />
          </label>
          <label className="flex flex-col gap-1 text-[12px] text-muted">
            {t.sources.filters.type}
            <select id="tipe" name="tipe" defaultValue={filters.tipe ?? ""} className="field">
              <option value="">{t.common.all}</option>
              <option value="media">{t.sources.types.media}</option>
              <option value="official">{t.sources.types.official}</option>
              <option value="blog">{t.sources.types.blog}</option>
            </select>
          </label>
          <label className="flex flex-col gap-1 text-[12px] text-muted">
            {t.sources.filters.country}
            <select id="negara" name="negara" defaultValue={filters.negara ?? ""} className="field">
              <option value="">{t.common.all}</option>
              {data.byCountry.map((c) => (
                <option key={c.country} value={c.country}>
                  {isoLabel(c.country)}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-[12px] text-muted">
            {t.sources.filters.sort}
            <select id="urut" name="urut" defaultValue={filters.urut ?? "artikel"} className="field">
              <option value="artikel">{t.sources.sorts.artikel}</option>
              <option value="terbaru">{t.sources.sorts.terbaru}</option>
              <option value="nama">{t.sources.sorts.nama}</option>
            </select>
          </label>
          <button type="submit" className="btn btn-primary">
            {t.common.apply}
          </button>
          {filters.q || filters.tipe || filters.negara || filters.urut ? (
            <Link href={base} className="text-[13px] no-underline">
              {t.common.reset}
            </Link>
          ) : null}
        </form>
      </div>

      {data.rows.length ? (
        <div className="grid gap-2.5 sm:grid-cols-2 xl:grid-cols-3">
          {data.rows.map((s, i) => (
            <div key={s.domain} className="card lift fade-up flex items-center gap-3 p-3" style={{ "--i": Math.min(i, 24) } as React.CSSProperties}>
              <SourceLogo domain={s.domain} size={28} />
              <div className="flex min-w-0 flex-1 flex-col gap-1">
                <div className="flex items-center justify-between gap-2">
                  <a href={`https://${s.domain}`} target="_blank" rel="noreferrer" className="truncate font-mono text-[12.5px] text-fg no-underline hover:text-accent">
                    {s.domain}
                  </a>
                  <span className={`chip ${s.source_type === "OFFICIAL" ? "chip-good" : ""}`}>{typeLabel(s.source_type)}</span>
                </div>
                <span className="truncate text-[12px] text-soft">
                  {s.publisher_name || t.sources.unknownPublisher} · {isoLabel(s.country)}
                </span>
                <div className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-2">
                  <span className="block h-1.5 overflow-hidden rounded-sm bg-line">
                    <span className="bar-fill block h-full bg-accent" style={{ width: `${Math.max(3, (100 * Number(s.article_count)) / data.max)}%`, "--i": Math.min(i, 24) } as React.CSSProperties} />
                  </span>
                  <span className="tnum font-mono text-[12px] text-muted">
                    {f.num(s.article_count)} · {f.date(s.last_seen)}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="card px-4 py-8 text-center text-[13.5px] text-muted">{t.sources.empty}</div>
      )}

      <Pagination
        lang={lang}
        page={data.page}
        pages={data.pages}
        total={data.total}
        pageSize={data.pageSize}
        label={t.sources.label}
        hrefFor={(n) => hrefWith({ page: n > 1 ? String(n) : undefined })}
        action={base}
        hidden={params(filters)}
      />
    </div>
  );
}
