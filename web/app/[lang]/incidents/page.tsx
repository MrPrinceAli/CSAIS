import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getAttackTypeOptions, getDashboard, type DashboardFilters } from "@/lib/queries";
import { COUNTRY, countryOf } from "@/lib/geo";
import { formatters, incidentTitle } from "@/lib/format";
import { attackLabel, getDict, isLang, L, languageLabel } from "@/lib/i18n";
import { CommandGlobe, type GlobeArc, type GlobePoint } from "@/components/command-globe";
import { EscapeClose } from "@/components/escape-close";
import { Pagination } from "@/components/pagination";
import { SearchField } from "@/components/search-field";
import { DailyBars, IncidentCard, TrustLegend } from "@/components/ui";

type Search = Record<string, string | string[] | undefined>;

export async function generateMetadata({ params }: { params: Promise<{ lang: string }> }): Promise<Metadata> {
  const { lang } = await params;
  return { title: getDict(isLang(lang) ? lang : "id").incidents.title };
}

function first(value: string | string[] | undefined): string {
  return Array.isArray(value) ? (value[0] ?? "") : (value ?? "");
}

function parseFilters(sp: Search): DashboardFilters & { daftar: boolean } {
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
    daftar: first(sp.daftar) === "1",
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

/** Kunci penanda globe yang aman sebagai nama anchor CSS. */
const markerId = (name: string) => `c-${name.replace(/[^a-z0-9]+/g, "-")}`;

export default async function IncidentsPage({ params: p, searchParams }: { params: Promise<{ lang: string }>; searchParams: Promise<Search> }) {
  const { lang } = await p;
  if (!isLang(lang)) notFound();
  const t = getDict(lang);
  const c = t.incidents.cc;
  const f = formatters(lang);
  const filters = parseFilters(await searchParams);
  const base = L(lang, "/incidents");
  const hrefWith = (overrides: Record<string, string | undefined>) => {
    const sp = new URLSearchParams();
    for (const [k, v] of Object.entries({ ...params(filters), ...overrides })) if (v) sp.set(k, v);
    const s = sp.toString();
    return s ? `${base}?${s}` : base;
  };

  const [data, typeOptions] = await Promise.all([getDashboard(filters), getAttackTypeOptions()]);
  const days = filters.hari ?? 30;
  const active = [filters.q, filters.jenis, filters.bahasa, filters.negara, filters.min].filter(Boolean).length;
  const total = Number(data.kpi.total);

  // Penanda globe: jumlah incident per negara pada filter aktif (lokasi majemuk dihitung per negara)
  const perCountry = new Map<string, number>();
  for (const row of data.allCountries) {
    for (const name of row.location.split(",").map((x) => x.trim()).filter(Boolean)) {
      if (COUNTRY[name]) perCountry.set(name, (perCountry.get(name) ?? 0) + Number(row.n));
    }
  }
  const ranked = [...perCountry.entries()].sort((a, b) => b[1] - a[1]);
  const points: GlobePoint[] = ranked.map(([name, n]) => ({
    id: markerId(name),
    lat: COUNTRY[name].lat,
    lng: COUNTRY[name].lng,
    n,
    label: COUNTRY[name].label,
    href: hrefWith({ negara: name, page: undefined }),
  }));
  const arcs: GlobeArc[] = data.pairs
    .filter((x) => COUNTRY[x.a] && COUNTRY[x.b])
    .slice(0, 16)
    .map((x) => ({ from: [COUNTRY[x.a].lat, COUNTRY[x.a].lng], to: [COUNTRY[x.b].lat, COUNTRY[x.b].lng], n: x.n }));
  const focusCountry = filters.negara ? countryOf(filters.negara) : null;
  const located = ranked.reduce((acc, [, n]) => acc + n, 0);

  // Jenis serangan: hitungan pada filter aktif; "tidak teridentifikasi" tidak ditawarkan sebagai filter
  const typeCount = new Map(data.types.map((x) => [x.t, Number(x.n)]));
  const primary = (x: string) => x.split(",")[0].trim();
  const typeList = [...new Set([...data.types.map((x) => primary(x.t)), ...typeOptions.map((x) => primary(x.t))])].filter((x) => x && x !== "unknown").slice(0, 14);
  const maxCountry = Math.max(1, ...ranked.slice(0, 8).map(([, n]) => n));
  const feed = data.rows.slice(0, 4);

  const chips: { label: string; href: string }[] = [];
  if (filters.q) chips.push({ label: `“${filters.q}”`, href: hrefWith({ q: undefined, page: undefined }) });
  if (filters.jenis) chips.push({ label: attackLabel(filters.jenis, lang), href: hrefWith({ jenis: undefined, page: undefined }) });
  if (filters.negara) chips.push({ label: countryOf(filters.negara)?.label ?? filters.negara, href: hrefWith({ negara: undefined, page: undefined }) });
  if (filters.bahasa) chips.push({ label: languageLabel(filters.bahasa, lang), href: hrefWith({ bahasa: undefined, page: undefined }) });
  if (filters.min) chips.push({ label: `≥ ${filters.min} ${t.common.sources}`, href: hrefWith({ min: undefined, page: undefined }) });

  const listHref = (page?: number) => hrefWith({ daftar: "1", page: page && page > 1 ? String(page) : undefined });
  const closeHref = hrefWith({ page: undefined });

  return (
    <>
      <div className="cc bleed -mt-6 lg:-mb-6">
        <div className="mx-auto grid h-full max-w-[1680px] gap-4 px-4 py-4 sm:px-6 lg:grid-cols-[290px_minmax(0,1fr)_290px]">
          {/* Kiri: filter */}
          <aside className="cc-panel cc-scroll order-3 lg:order-1" aria-label={c.filters}>
            <form method="get" action={base} className="flex flex-col gap-2">
              <span className="cc-h">{c.search}</span>
              {Object.entries({ ...params(filters), q: undefined }).map(([k, v]) => (v ? <input key={k} type="hidden" name={k} value={v} /> : null))}
              <SearchField id="q" name="q" defaultValue={filters.q ?? ""} placeholder={t.incidents.filters.searchPlaceholder} examples={t.incidents.filters.searchExamples} className="field w-full" />
            </form>

            <div className="flex flex-col gap-1.5">
              <span className="cc-h">{c.period}</span>
              <nav className="cc-seg" aria-label={c.period}>
                {[7, 30, 90, 365].map((d) => (
                  <Link key={d} href={hrefWith({ hari: d === 30 ? undefined : String(d), page: undefined })} aria-current={days === d ? "true" : undefined}>
                    {t.common.days(d)}
                  </Link>
                ))}
              </nav>
            </div>

            <div className="flex flex-col gap-1">
              <span className="cc-h">{t.incidents.filters.type}</span>
              <Link href={hrefWith({ jenis: undefined, page: undefined })} className="cc-opt" aria-current={!filters.jenis ? "true" : undefined}>
                <span>{c.all}</span>
                <span className="n">{f.num(total)}</span>
              </Link>
              {typeList.map((type) => (
                <Link key={type} href={hrefWith({ jenis: type, page: undefined })} className="cc-opt" aria-current={filters.jenis?.toLowerCase() === type ? "true" : undefined}>
                  <span className="truncate">{attackLabel(type, lang)}</span>
                  <span className="n">{typeCount.has(type) ? f.num(typeCount.get(type)) : "·"}</span>
                </Link>
              ))}
            </div>

            <div className="flex flex-col gap-1.5">
              <span className="cc-h">{t.incidents.filters.language}</span>
              <nav className="cc-seg">
                {[undefined, "id", "en"].map((code) => (
                  <Link key={code ?? "all"} href={hrefWith({ bahasa: code, page: undefined })} aria-current={filters.bahasa === code ? "true" : undefined}>
                    {code ? languageLabel(code, lang) : c.all}
                  </Link>
                ))}
              </nav>
            </div>

            <div className="flex flex-col gap-1.5">
              <span className="cc-h">{t.incidents.filters.minSources}</span>
              <nav className="cc-seg">
                {[1, 2, 3, 5, 10].map((n) => (
                  <Link key={n} href={hrefWith({ min: n > 1 ? String(n) : undefined, page: undefined })} aria-current={(filters.min ?? 1) === n ? "true" : undefined}>
                    {n === 1 ? c.all : `≥ ${n}`}
                  </Link>
                ))}
              </nav>
            </div>

            {chips.length ? (
              <div className="flex flex-col gap-1.5 border-t border-line pt-3">
                <span className="cc-h">
                  {c.active}
                  <Link href={base} className="text-[11px] font-normal normal-case tracking-normal no-underline">
                    {c.clear}
                  </Link>
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {chips.map((chip) => (
                    <Link key={chip.label} href={chip.href} className="chip chip-accent no-underline">
                      {chip.label} ×
                    </Link>
                  ))}
                </div>
              </div>
            ) : null}
          </aside>

          {/* Tengah: judul, globe, garis waktu */}
          <section className="order-1 flex min-h-0 flex-col gap-3 lg:order-2">
            <div className="flex flex-wrap items-end justify-between gap-3">
              <div className="flex flex-col gap-1">
                <h1 className="text-[24px] font-semibold leading-tight">{t.incidents.title}</h1>
                <span className="text-[13px] text-soft">{t.incidents.subtitle(f.num(total), days, active)}</span>
              </div>
              <Link href={listHref()} scroll={false} className="btn btn-primary">
                {c.open}
                <span className="rounded bg-[rgba(15,23,32,0.2)] px-1.5 py-0.5 font-mono text-[12px]">{f.num(total)}</span>
              </Link>
            </div>
            <div className="relative flex min-h-0 flex-1 items-center justify-center">
              <CommandGlobe
                points={points}
                arcs={arcs}
                focus={focusCountry ? { lat: focusCountry.lat, lng: focusCountry.lng } : null}
                labels={10}
                ariaLabel={t.incidents.located(f.num(located), ranked.length)}
                readoutLabel={c.rotation}
              />
            </div>
            <div className="cc-panel gap-2 py-3">
              <span className="cc-h">
                {t.incidents.dailyTitle}
                <span className="font-normal normal-case tracking-normal">{t.incidents.located(f.num(located), ranked.length)} · {c.arcsNote}</span>
              </span>
              <DailyBars data={data.daily} lang={lang} height={48} />
            </div>
          </section>

          {/* Kanan: ringkasan */}
          <aside className="cc-panel cc-scroll order-2 lg:order-3" aria-label={c.summary}>
            <span className="cc-h">{c.summary}</span>
            <div className="cc-metric">
              <span className="text-[13px] text-soft">{t.incidents.kpi.total}</span>
              <span className="v">{f.num(total)}</span>
            </div>
            <div className="cc-metric">
              <span className="text-[13px] text-soft">{t.incidents.kpi.multi}</span>
              <span className="v">{f.num(data.kpi.multi)}</span>
              <span className="cc-bar">
                <i style={{ width: `${total ? (100 * Number(data.kpi.multi)) / total : 0}%` }} />
              </span>
            </div>
            <div className="cc-metric">
              <span className="text-[13px] text-soft">{t.incidents.kpi.target}</span>
              <span className="v">{f.num(data.kpi.target_known)}</span>
              <span className="cc-bar">
                <i style={{ width: `${total ? (100 * Number(data.kpi.target_known)) / total : 0}%` }} />
              </span>
            </div>

            <div className="flex flex-col gap-1 border-t border-line pt-3">
              <span className="cc-h">{c.countries}</span>
              {ranked.slice(0, 8).map(([name, n]) => (
                <Link key={name} href={hrefWith({ negara: name, page: undefined })} className="cc-opt" aria-current={filters.negara === name ? "true" : undefined}>
                  <span className="flex min-w-0 flex-col gap-1">
                    <span className="truncate">{COUNTRY[name].label}</span>
                    <span className="block h-[3px] overflow-hidden rounded-sm bg-line">
                      <span className="bar-fill block h-full bg-accent" style={{ width: `${(100 * n) / maxCountry}%` }} />
                    </span>
                  </span>
                  <span className="n">{f.num(n)}</span>
                </Link>
              ))}
            </div>

            <div className="flex flex-col gap-2 border-t border-line pt-3">
              <span className="cc-h">{c.feed}</span>
              {feed.map((row) => (
                <Link key={row.incident_id} href={L(lang, `/incidents/${row.incident_id}`)} className="row-link flex flex-col gap-1 rounded-md border border-line bg-[rgba(7,12,18,0.6)] p-2.5 hover:border-accent">
                  <span className="line-clamp-2 text-[13px] font-semibold leading-snug">{incidentTitle(row.title)}</span>
                  <span className="text-[12px] text-muted">
                    {attackLabel(row.attack_type, lang)} · {f.num(row.document_count)} {t.common.articles}
                  </span>
                </Link>
              ))}
            </div>
          </aside>
        </div>
      </div>

      {/* Daftar incident sebagai panel pop-up */}
      {filters.daftar ? (
        <>
          <EscapeClose href={closeHref} />
          <Link href={closeHref} scroll={false} className="cc-backdrop" aria-label={c.close} />
          <aside className="cc-drawer" role="dialog" aria-modal="true" aria-label={c.listTitle}>
            <header className="flex items-center justify-between gap-3 border-b border-line px-5 py-4">
              <div className="flex flex-col gap-0.5">
                <span className="text-[18px] font-semibold">{c.listTitle}</span>
                <span className="text-[12.5px] text-muted">
                  {t.incidents.subtitle(f.num(data.total), days, active)} · {t.incidents.sortNote}
                </span>
              </div>
              <Link href={closeHref} scroll={false} className="btn btn-ghost px-3 py-1.5 text-[13px]" title={c.escHint}>
                {c.close} ✕
              </Link>
            </header>
            <div className="cc-scroll flex flex-1 flex-col gap-2 px-5 py-4">
              {data.rows.length ? (
                data.rows.map((row, i) => <IncidentCard key={row.incident_id} row={row} lang={lang} index={Math.min(i, 12)} />)
              ) : (
                <p className="py-10 text-center text-[13.5px] text-muted">{t.incidents.empty}</p>
              )}
              <div className="pt-2">
                <TrustLegend lang={lang} />
              </div>
            </div>
            <footer className="border-t border-line px-5 py-3">
              <Pagination
                lang={lang}
                page={data.page}
                pages={data.pages}
                total={data.total}
                pageSize={data.pageSize}
                label={t.common.incidents}
                hrefFor={(n) => listHref(n)}
                action={base}
                hidden={{ ...params(filters), daftar: "1" }}
              />
            </footer>
          </aside>
        </>
      ) : null}
    </>
  );
}
