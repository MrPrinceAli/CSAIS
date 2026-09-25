import Link from "next/link";
import { notFound } from "next/navigation";
import { getCountryCounts, getDailyArticles, getLanguageCounts, getLatestIncidents, getOverview } from "@/lib/queries";
import { countryOf } from "@/lib/geo";
import { formatters } from "@/lib/format";
import { getDict, isLang, L, languageLabel } from "@/lib/i18n";
import { CountUp, Reveal } from "@/components/reveal";
import { DailyBars, IncidentCard, LabelBars, SectionTitle, Stat } from "@/components/ui";

export const revalidate = 3600;

export default async function Home({ params }: { params: Promise<{ lang: string }> }) {
  const { lang } = await params;
  if (!isLang(lang)) notFound();
  const t = getDict(lang);
  const f = formatters(lang);
  const locale = lang === "en" ? "en-GB" : "id-ID";

  const [overview, latest, countries, daily, languages] = await Promise.all([
    getOverview(),
    getLatestIncidents(5),
    getCountryCounts(90),
    getDailyArticles(60),
    getLanguageCounts(),
  ]);
  const totalLang = languages.reduce((acc, l) => acc + Number(l.n), 0) || 1;

  return (
    <div className="flex flex-col gap-14">
      <section className="grid items-start gap-8 pt-4 lg:grid-cols-[minmax(0,1.05fr)_minmax(0,1fr)] lg:pt-8">
        <div className="flex flex-col gap-5">
          <span className="label text-accent">{t.home.eyebrow}</span>
          <h1 className="max-w-[22ch] text-balance text-[34px] font-semibold leading-[1.12] sm:text-[42px]">{t.home.title}</h1>
          <p className="max-w-[58ch] text-[15.5px] leading-relaxed text-soft">{t.home.lead}</p>
          <div className="flex flex-wrap gap-3">
            <Link href={L(lang, "/incidents")} className="btn btn-primary">
              {t.home.ctaPrimary}
            </Link>
            <Link href={L(lang, "/verify")} className="btn btn-ghost">
              {t.home.ctaSecondary}
            </Link>
          </div>
        </div>
        <div className="card flex flex-col gap-4 p-4 sm:p-5">
          <SectionTitle aside={t.home.volumeNote}>{t.home.volumeTitle}</SectionTitle>
          <DailyBars data={daily} lang={lang} height={140} />
          <div className="grid grid-cols-3 gap-3 border-t border-line pt-4">
            <div className="flex flex-col">
              <CountUp value={Number(overview.incident)} locale={locale} className="text-[24px] font-semibold leading-tight" />
              <span className="label">{t.home.metrics.incidents}</span>
            </div>
            <div className="flex flex-col">
              <CountUp value={Number(overview.artikel)} locale={locale} className="text-[24px] font-semibold leading-tight" />
              <span className="label">{t.home.metrics.articles}</span>
            </div>
            <div className="flex flex-col">
              <CountUp value={Number(overview.bukti)} locale={locale} className="text-[24px] font-semibold leading-tight text-chain" />
              <span className="label">{t.home.metrics.evidence}</span>
            </div>
          </div>
        </div>
      </section>
      <div className="hairline -mt-8" aria-hidden="true" />

      <Reveal>
        <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Stat label={t.home.metrics.incidents} value={f.num(overview.incident)} note={t.home.metricNotes.incidents(f.num(overview.incident_30))} />
          <Stat label={t.home.metrics.articles} value={f.num(overview.artikel)} note={t.home.metricNotes.articles(f.num(overview.sumber))} />
          <Stat label={t.home.metrics.corroborated} value={f.num(overview.multi_all)} note={t.home.metricNotes.corroborated} tone="good" />
          <Stat label={t.home.metrics.evidence} value={f.num(overview.bukti)} note={t.home.metricNotes.evidence} tone="chain" />
        </section>
      </Reveal>

      <Reveal>
        <section className="grid gap-4 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
          <div className="card flex flex-col gap-2.5 p-4 sm:p-5">
            <SectionTitle aside={t.home.coverageNote}>{t.home.coverageTitle}</SectionTitle>
            {latest.map((row) => (
              <IncidentCard key={row.incident_id} row={row} lang={lang} />
            ))}
            <Link href={L(lang, "/incidents")} className="self-end text-[13px] no-underline">
              {t.nav.incidents} →
            </Link>
          </div>
          <div className="flex flex-col gap-4">
            <div className="card p-4 sm:p-5">
              <SectionTitle>{t.home.languagesTitle}</SectionTitle>
              <LabelBars
                data={languages.map((l) => ({
                  label: languageLabel(l.language, lang),
                  n: Number(l.n),
                  text: `${Math.round((100 * Number(l.n)) / totalLang)}%`,
                }))}
              />
            </div>
            <div className="card p-4 sm:p-5">
              <SectionTitle aside={t.home.countriesNote}>{t.home.countriesTitle}</SectionTitle>
              <LabelBars
                data={countries.slice(0, 6).map((c) => ({
                  label: countryOf(c.location)?.label ?? c.location,
                  n: Number(c.n),
                  text: f.num(Number(c.n)),
                  href: `${L(lang, "/incidents")}?negara=${encodeURIComponent(c.location)}&hari=90`,
                }))}
              />
            </div>
          </div>
        </section>
      </Reveal>

      <Reveal>
        <section id="process" className="flex flex-col gap-4 scroll-mt-20">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="text-[22px] font-semibold">{t.home.processTitle}</h2>
            <span className="text-[13px] text-muted">{t.home.processNote}</span>
          </div>
          <ol className="grid gap-px overflow-hidden rounded-lg border border-line bg-line md:grid-cols-5">
            {t.home.steps.map((step, i) => (
              <li key={step.title} className="flex min-h-[170px] flex-col gap-2.5 bg-surface p-4">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-[11px] text-muted">0{i + 1}</span>
                  <span className={`chip ${step.tag === "AI" ? "chip-accent" : "chip-chain"}`}>{step.tag}</span>
                </div>
                <span className="text-[14.5px] font-semibold">{step.title}</span>
                <span className="text-[12.5px] leading-relaxed text-soft">{step.text}</span>
              </li>
            ))}
          </ol>
        </section>
      </Reveal>

      <Reveal>
        <section className="grid gap-4 lg:grid-cols-2">
          <div className="card flex flex-col gap-3 p-5">
            <h2 className="text-[18px] font-semibold">{t.home.institutionsTitle}</h2>
            <p className="text-[14px] leading-relaxed text-soft">{t.home.institutionsText}</p>
            <div className="flex flex-wrap gap-2">
              {["BSSN", "OJK", "Polri", "Komdigi"].map((org) => (
                <span key={org} className="chip">
                  {org}
                </span>
              ))}
            </div>
            <Link href={L(lang, "/institutions")} className="btn btn-ghost self-start">
              {t.home.institutionsCta}
            </Link>
          </div>
          <div className="card flex flex-col gap-3 p-5">
            <h2 className="text-[18px] font-semibold">{t.home.publicTitle}</h2>
            <p className="text-[14px] leading-relaxed text-soft">{t.home.publicText}</p>
            <Link href={L(lang, "/findings")} className="btn btn-primary self-start">
              {t.home.publicCta}
            </Link>
          </div>
        </section>
      </Reveal>
    </div>
  );
}
