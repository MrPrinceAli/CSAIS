import Link from "next/link";
import { notFound } from "next/navigation";
import { getCountryCounts, getDailyArticles, getLanguageCounts, getLastRun, getLatestIncidents, getOverview, getScannerFeed } from "@/lib/queries";
import { countryOf } from "@/lib/geo";
import { formatters, incidentTitle } from "@/lib/format";
import { attackLabel, getDict, isLang, L, languageLabel } from "@/lib/i18n";
import { CountUp, Reveal } from "@/components/reveal";
import { IntelScanner, type ScanItem } from "@/components/intel-scanner";
import { PipelineFlow } from "@/components/pipeline-flow";
import { Seal } from "@/components/seal";
import { DailyBars, IncidentCard, LabelBars, SectionTitle, Stat } from "@/components/ui";

export const revalidate = 3600;

export default async function Home({ params }: { params: Promise<{ lang: string }> }) {
  const { lang } = await params;
  if (!isLang(lang)) notFound();
  const t = getDict(lang);
  const f = formatters(lang);
  const locale = lang === "en" ? "en-GB" : "id-ID";

  const [overview, latest, countries, daily, languages, feed, lastRun] = await Promise.all([
    getOverview(),
    getLatestIncidents(5),
    getCountryCounts(90),
    getDailyArticles(60),
    getLanguageCounts(),
    getScannerFeed(8),
    getLastRun(),
  ]);
  const totalLang = languages.reduce((acc, l) => acc + Number(l.n), 0) || 1;
  const scanItems: ScanItem[] = feed.map((r) => {
    const type = (r.attack_type ?? "").split(",")[0].trim();
    const label = attackLabel(type, lang);
    const docs = Number(r.document_count);
    return {
      title: incidentTitle(r.title),
      target: r.target,
      attackLabel: label,
      attackWords: [...label.toLowerCase().split(/\s+/), ...type.toLowerCase().split("_")].filter((w) => w.length >= 4),
      domain: r.source_domain ?? "",
      language: languageLabel(r.language, lang),
      date: f.date(r.published_date),
      docs,
      incident_id: r.incident_id,
      trust: r.trust_score !== null && r.trust_score !== undefined ? Number(r.trust_score) : Math.min(0.9, 0.3 + docs * 0.06),
      href: L(lang, `/incidents/${r.incident_id}`),
    };
  });
  const version = lastRun?.pipeline_version.split("+")[0] ?? "";

  return (
    <div className="flex flex-col gap-14">
      {/* Pembuka: judul berstabilo + panel pemindai artikel sungguhan */}
      <section className="grid items-start gap-8 pt-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,0.95fr)] lg:pt-8">
        <Reveal className="flex flex-col gap-5">
          <span className="label inline-flex items-center gap-2 text-accent">
            <span className="led led-accent" aria-hidden="true" />
            {t.home.eyebrow}
          </span>
          <h1 className="max-w-[22ch] text-balance text-[34px] font-semibold leading-[1.12] sm:text-[42px]">
            {t.home.title.before}
            <span className="mark">{t.home.title.mark}</span>
            {t.home.title.after}
          </h1>
          <p className="max-w-[58ch] text-[15.5px] leading-relaxed text-soft">{t.home.lead}</p>
          <div className="flex flex-wrap gap-3">
            <Link href={L(lang, "/incidents")} className="btn btn-primary">
              {t.home.ctaPrimary}
            </Link>
            <Link href={L(lang, "/verify")} className="btn btn-ghost">
              {t.home.ctaSecondary}
            </Link>
          </div>
          <dl className="grid grid-cols-3 gap-4 border-t border-line pt-4">
            {[
              { label: t.home.metrics.incidents, value: Number(overview.incident), cls: "" },
              { label: t.home.metrics.articles, value: Number(overview.artikel), cls: "" },
              { label: t.home.metrics.evidence, value: Number(overview.bukti), cls: "text-chain" },
            ].map((m) => (
              <div key={m.label} className="flex flex-col">
                <dd className="order-1">
                  <CountUp value={m.value} locale={locale} className={`text-[24px] font-semibold leading-tight ${m.cls}`} />
                </dd>
                <dt className="label order-2">{m.label}</dt>
              </div>
            ))}
          </dl>
        </Reveal>
        <div className="flex flex-col gap-2">
          <IntelScanner items={scanItems} labels={t.home.scanner} stamp={version ? `pipeline ${version}` : ""} />
          <span className="text-[11.5px] text-muted">{t.home.scanner.note}</span>
        </div>
      </section>
      <div className="hairline -mt-8" aria-hidden="true" />

      {/* Instrumen: empat angka dan volume harian */}
      <Reveal>
        <section className="flex flex-col gap-3">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Stat label={t.home.metrics.incidents} value={f.num(overview.incident)} note={t.home.metricNotes.incidents(f.num(overview.incident_30))} tone="accent" live />
            <Stat label={t.home.metrics.articles} value={f.num(overview.artikel)} note={t.home.metricNotes.articles(f.num(overview.sumber))} />
            <Stat label={t.home.metrics.corroborated} value={f.num(overview.multi_all)} note={t.home.metricNotes.corroborated} tone="good" />
            <Stat label={t.home.metrics.evidence} value={f.num(overview.bukti)} note={t.home.metricNotes.evidence} tone="chain" />
          </div>
          <div className="card p-4 sm:p-5">
            <SectionTitle aside={t.home.volumeNote}>{t.home.volumeTitle}</SectionTitle>
            <DailyBars data={daily} lang={lang} height={110} />
          </div>
        </section>
      </Reveal>

      {/* Liputan terluas: kartu dengan tumpukan logo sumber */}
      <Reveal>
        <section className="grid gap-4 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
          <div className="card flex flex-col gap-2.5 p-4 sm:p-5">
            <SectionTitle aside={t.home.coverageNote}>{t.home.coverageTitle}</SectionTitle>
            {latest.map((row, i) => (
              <IncidentCard key={row.incident_id} row={row} lang={lang} index={i} />
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

      {/* Cara kerja: alur dengan titik mengalir */}
      <Reveal>
        <section id="process" className="flex flex-col gap-4 scroll-mt-20">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="text-[22px] font-semibold">
              <span className="mark mark-accent">{t.home.processTitle}</span>
            </h2>
            <span className="text-[13px] text-muted">{t.home.processNote}</span>
          </div>
          <PipelineFlow steps={t.home.steps} aiTag="AI" />
        </section>
      </Reveal>

      {/* Lembaga dan program literasi */}
      <Reveal>
        <section className="grid gap-4 lg:grid-cols-2">
          <div className="card lift flex flex-col gap-3 p-5" style={{ borderTopColor: "var(--chain)", borderTopWidth: 2 }}>
            <div className="flex items-center justify-between gap-3">
              <h2 className="text-[18px] font-semibold">{t.home.institutionsTitle}</h2>
              <div className="hidden gap-1 sm:flex">
                {["BSSN", "OJK", "Polri", "Komdigi"].map((org, i) => (
                  <span key={org} className="fade-up" style={{ "--i": i * 2 } as React.CSSProperties}>
                    <Seal org={org} size={56} />
                  </span>
                ))}
              </div>
            </div>
            <p className="text-[14px] leading-relaxed text-soft">{t.home.institutionsText}</p>
            <Link href={L(lang, "/institutions")} className="btn btn-ghost self-start">
              {t.home.institutionsCta}
            </Link>
          </div>
          <div className="card lift flex flex-col gap-3 p-5" style={{ borderTopColor: "var(--good)", borderTopWidth: 2 }}>
            <h2 className="text-[18px] font-semibold">
              <span className="mark mark-good">{t.home.publicTitle}</span>
            </h2>
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
