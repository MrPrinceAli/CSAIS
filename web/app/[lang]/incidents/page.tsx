import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getAttackTypeOptions, getCountryCounts, getDashboard, type DashboardFilters } from "@/lib/queries";
import { countryOf } from "@/lib/geo";
import { formatters } from "@/lib/format";
import { attackLabel, getDict, isLang, L } from "@/lib/i18n";
import { Globe, type GlobeMarker } from "@/components/globe";
import { Pagination } from "@/components/pagination";
import { SearchField } from "@/components/search-field";
import { DailyBars, IncidentTable, LabelBars, SectionTitle, Stat, TrustLegend } from "@/components/ui";

type Search = Record<string, string | string[] | undefined>;

export async function generateMetadata({ params }: { params: Promise<{ lang: string }> }): Promise<Metadata> {
  const { lang } = await params;
  return { title: getDict(isLang(lang) ? lang : "id").incidents.title };
}

function first(value: string | string[] | undefined): string {
  return Array.isArray(value) ? (value[0] ?? "") : (value ?? "");
}

function parseFilters(sp: Search): DashboardFilters {
  const min = Number.parseInt(first(sp.min), 10);
  const hari = Number.parseInt(first(sp.hari), 10);
  const page = Number.parseInt(first(sp.page), 10);
  return {
    q: first(sp.q).trim().slice(0, 80) || undefined,
    jenis: first(sp.jenis).trim().slice(0, 40) || undefined,
    bahasa: ["id", "en"].includes(first(sp.bahasa)) ? first(sp.bahasa) : undefined,
    negara: first(sp.negara).trim().slice(0, 40) || undefined,
    min: Number.isFinite(min) && min > 1 ? min : undefined,
    hari: [7, 30, 90, 365].includes(hari) ? hari : 30,
    page: Number.isFinite(page) && page > 0 ? page : 1,
  };
}

function params(f: DashboardFilters): Record<string, string | undefined> {
  return {
    q: f.q,
    jenis: f.jenis,
    bahasa: f.bahasa,
    negara: f.negara,
    min: f.min ? String(f.min) : undefined,
    hari: f.hari && f.hari !== 30 ? String(f.hari) : undefined,
  };
}

export default async function IncidentsPage({ params: p, searchParams }: { params: Promise<{ lang: string }>; searchParams: Promise<Search> }) {
  const { lang } = await p;
  if (!isLang(lang)) notFound();
  const t = getDict(lang);
  const f = formatters(lang);
  const filters = parseFilters(await searchParams);
  const base = L(lang, "/incidents");
  const hrefWith = (overrides: Record<string, string | undefined>) => {
    const sp = new URLSearchParams();
    for (const [k, v] of Object.entries({ ...params(filters), ...overrides })) if (v) sp.set(k, v);
    const s = sp.toString();
    return s ? `${base}?${s}` : base;
  };

  const [data, typeOptions, globeCountries] = await Promise.all([getDashboard(filters), getAttackTypeOptions(), getCountryCounts(filters.hari ?? 30)]);
  const active = [filters.q, filters.jenis, filters.bahasa, filters.negara, filters.min].filter(Boolean).length;
  const maxCountry = Math.max(...globeCountries.map((c) => Number(c.n)), 1);
  const markers: GlobeMarker[] = globeCountries
    .map((c) => {
      const geo = countryOf(c.location);
      return geo ? { location: [geo.lat, geo.lng] as [number, number], size: 0.03 + 0.12 * (Number(c.n) / maxCountry) } : null;
    })
    .filter((m): m is GlobeMarker => m !== null);
  const located = globeCountries.reduce((acc, c) => acc + Number(c.n), 0);
  const days = filters.hari ?? 30;

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex flex-col gap-1">
          <h1 className="text-[24px] font-semibold">{t.incidents.title}</h1>
          <span className="text-[13px] text-muted">{t.incidents.subtitle(f.num(data.total), days, active)}</span>
        </div>
        <div className="flex gap-1.5">
          {[7, 30, 90, 365].map((d) => (
            <Link key={d} href={hrefWith({ hari: d === 30 ? undefined : String(d), page: undefined })} className={`chip no-underline ${days === d ? "chip-accent" : ""}`}>
              {t.common.days(d)}
            </Link>
          ))}
        </div>
      </div>

      <section className="grid gap-4 lg:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)]">
        <div className="card grid gap-4 p-4 sm:p-5 md:grid-cols-[minmax(0,1fr)_200px]">
          <div className="flex flex-col gap-3">
            <SectionTitle aside={t.incidents.globeNote(days)}>{t.incidents.globeTitle}</SectionTitle>
            <div className="relative mx-auto aspect-square w-full max-w-[380px]">
              <Globe markers={markers} label={t.incidents.located(f.num(located), globeCountries.length)} />
              <div className="radar" aria-hidden="true" />
              <div className="radar-ring" aria-hidden="true" />
            </div>
            <div className="flex items-center justify-between font-mono text-[11px] text-muted">
              <span>{t.incidents.located(f.num(located), globeCountries.length)}</span>
              <span>{t.incidents.globeHint}</span>
            </div>
          </div>
          <div className="flex flex-col gap-2 border-t border-line pt-4 md:border-l md:border-t-0 md:pl-4 md:pt-0">
            <span className="label">{t.common.country}</span>
            <LabelBars
              data={globeCountries.slice(0, 9).map((c) => ({
                label: countryOf(c.location)?.label ?? c.location,
                n: Number(c.n),
                text: f.num(Number(c.n)),
                href: hrefWith({ negara: c.location, page: undefined }),
              }))}
            />
          </div>
        </div>

        <div className="flex flex-col gap-4">
          <div className="grid grid-cols-2 gap-3">
            <Stat label={t.incidents.kpi.total} value={f.num(data.kpi.total)} note={t.common.lastDays(days)} tone="accent" live />
            <Stat
              label={t.incidents.kpi.multi}
              value={f.num(data.kpi.multi)}
              note={data.kpi.total ? t.incidents.kpiNotes.multi(Math.round((100 * Number(data.kpi.multi)) / Number(data.kpi.total))) : ""}
              tone="good"
            />
            <Stat label={t.incidents.kpi.target} value={f.num(data.kpi.target_known)} note={t.incidents.kpiNotes.target} />
            <Stat label={t.incidents.kpi.indonesia} value={f.num(data.kpi.indonesia)} note={t.incidents.kpiNotes.indonesia} tone="high" />
          </div>
          <div className="card p-4">
            <SectionTitle aside={t.incidents.clickToFilter}>{t.incidents.typesTitle}</SectionTitle>
            <LabelBars
              data={data.types.map((x) => ({
                label: attackLabel(x.t, lang),
                n: Number(x.n),
                text: f.num(Number(x.n)),
                href: hrefWith({ jenis: x.t, page: undefined }),
              }))}
            />
          </div>
        </div>
      </section>

      <div className="card p-4">
        <SectionTitle aside={t.incidents.dailyNote}>{t.incidents.dailyTitle}</SectionTitle>
        <DailyBars data={data.daily} lang={lang} height={96} />
      </div>

      <form method="get" action={base} className="card flex flex-wrap items-end gap-3 p-3.5">
        {days !== 30 ? <input type="hidden" name="hari" value={days} /> : null}
        <label className="flex min-w-[220px] flex-1 flex-col gap-1 text-[12px] text-muted">
          {t.incidents.filters.search}
          <SearchField id="q" name="q" defaultValue={filters.q ?? ""} placeholder={t.incidents.filters.searchPlaceholder} examples={t.incidents.filters.searchExamples} className="field" />
        </label>
        <label className="flex flex-col gap-1 text-[12px] text-muted">
          {t.incidents.filters.type}
          <select id="jenis" name="jenis" defaultValue={filters.jenis ?? ""} className="field">
            <option value="">{t.common.all}</option>
            {typeOptions.map((x) => (
              <option key={x.t} value={x.t}>
                {attackLabel(x.t, lang)}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-[12px] text-muted">
          {t.incidents.filters.language}
          <select id="bahasa" name="bahasa" defaultValue={filters.bahasa ?? ""} className="field">
            <option value="">{t.common.all}</option>
            <option value="id">{lang === "en" ? "Indonesian" : "Indonesia"}</option>
            <option value="en">{lang === "en" ? "English" : "Inggris"}</option>
          </select>
        </label>
        <label className="flex flex-col gap-1 text-[12px] text-muted">
          {t.incidents.filters.country}
          <select id="negara" name="negara" defaultValue={filters.negara ?? ""} className="field">
            <option value="">{t.common.all}</option>
            {globeCountries.map((c) => (
              <option key={c.location} value={c.location}>
                {countryOf(c.location)?.label ?? c.location}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-[12px] text-muted">
          {t.incidents.filters.minSources}
          <select id="min" name="min" defaultValue={String(filters.min ?? 1)} className="field">
            {[1, 2, 3, 5, 10].map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </label>
        <button type="submit" className="btn btn-primary">
          {t.common.apply}
        </button>
        {active ? (
          <Link href={base} className="text-[13px] no-underline">
            {t.common.reset}
          </Link>
        ) : null}
      </form>

      <IncidentTable rows={data.rows} lang={lang} />
      <div id="confidence" className="scroll-mt-20">
        <TrustLegend lang={lang} />
      </div>

      <Pagination
        lang={lang}
        page={data.page}
        pages={data.pages}
        total={data.total}
        pageSize={data.pageSize}
        label={t.common.incidents}
        hrefFor={(n) => hrefWith({ page: n > 1 ? String(n) : undefined })}
        action={base}
        hidden={params(filters)}
      />
    </div>
  );
}
