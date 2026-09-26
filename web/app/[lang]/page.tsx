import { createHash } from "node:crypto";
import Link from "next/link";
import { notFound } from "next/navigation";
import {
  getCoverageDocs,
  getPublisherDomains,
  getCountryCounts,
  getEvidenceLeaf,
  getFeaturedIncidentId,
  getIncident,
  getLanguageCounts,
  getLastRun,
  getLatestIncidents,
  getLedgerStats,
  getNewsFeed,
  getOverview,
  getRiskGroups,
  getScannerFeed,
  getShowcaseIncidentId,
  type CoverageDoc,
  type DocumentRow,
  type GroupStat,
  type IncidentRow,
} from "@/lib/queries";
import { countryOf } from "@/lib/geo";
import { domainOf, formatters, incidentTitle, publisherOf, severity } from "@/lib/format";
import { attackLabel, getDict, groupLabel, isLang, L, languageLabel, type Lang } from "@/lib/i18n";
import { trustFromRow, trustFromStored, trustScore } from "@/lib/trust";
import { CountUp, Reveal } from "@/components/reveal";
import { IntelScanner, type ScanItem } from "@/components/intel-scanner";
import { NewsSlider, type NewsItem } from "@/components/news-slider";
import { OrgLogo, ORGS } from "@/components/org-logo";
import { ScrollScenes } from "@/components/scroll-scenes";
import {
  SceneCluster,
  SceneEvidence,
  ScenePackage,
  SceneRisk,
  SceneTrust,
  type ClusterData,
  type EvidenceData,
  type PackageData,
  type RiskData,
  type TrustData,
} from "@/components/process-scenes";
import { CoverageFeature, CoverageRow, type CoverageItem } from "@/components/coverage";
import { LabelBars, SectionTitle, Stat } from "@/components/ui";

export const revalidate = 3600;

/** Domain media asli sebuah artikel (URL media, lalu domain bukti); kosong bila hanya tautan Google News. */
function docDomain(d: DocumentRow): string {
  for (const domain of [domainOf(d.resolved_url), d.source_domain ?? ""]) {
    if (domain && !domain.includes("google.")) return domain;
  }
  return "";
}

/** Nama sumber untuk ditampilkan: domain asli, atau penerbit dari akhiran judul. */
function docSource(d: DocumentRow): string {
  return docDomain(d) || publisherOf(d.title) || "news";
}

function isoWeek(date: Date): number {
  const t = new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate()));
  const day = t.getUTCDay() || 7;
  t.setUTCDate(t.getUTCDate() + 4 - day);
  const start = new Date(Date.UTC(t.getUTCFullYear(), 0, 1));
  return Math.ceil(((t.getTime() - start.getTime()) / 86400000 + 1) / 7);
}

/** Tingkat kelompok berisiko, aturan yang sama dengan halaman temuan. */
function riskLevel(g: GroupStat): "high" | "medium" | "low" {
  if (g.now >= 20 || (g.now >= 8 && g.now > g.prev * 1.5)) return "high";
  if (g.now >= 5) return "medium";
  return "low";
}

const LEVEL_COLOR = { high: "var(--crit)", medium: "var(--high)", low: "var(--med)" } as const;

/** "Korban" dari v05 tersimpan huruf kecil; tampilkan dengan huruf besar di awal kata. */
function titleCase(value: string | null): string | null {
  return value ? value.replace(/(^|[\s./-])(\p{L})/gu, (_, sep: string, ch: string) => sep + ch.toUpperCase()) : null;
}

/** Data bagian liputan terluas: artikel per hari, penerbit dari akhiran judul, gambar bila ada. */
function coverageItems(lang: Lang, rows: IncidentRow[], docs: CoverageDoc[], publisherDomains: Record<string, string>): CoverageItem[] {
  const f = formatters(lang);
  const DAY = 86400000;
  return rows.map((row, idx) => {
    const list = docs.filter((d) => d.incident_id === row.incident_id);
    const keys = list.map((d) => (d.published_date ?? "").slice(0, 10)).filter(Boolean);
    const first = keys[0] ?? "";
    const last = keys[keys.length - 1] ?? first;
    const start = Date.parse(`${first}T00:00:00Z`);
    const spanDays = first ? Math.round((Date.parse(`${last}T00:00:00Z`) - start) / DAY) + 1 : 1;
    const bucket = Math.max(1, Math.ceil(spanDays / 24));
    const buckets = Math.max(1, Math.ceil(spanDays / bucket));
    const days = Array.from({ length: buckets }, () => 0);
    const ticks: number[] = [];
    for (const key of keys) {
      const b = Math.min(buckets - 1, Math.floor(Math.round((Date.parse(`${key}T00:00:00Z`) - start) / DAY) / bucket));
      days[b] += 1;
      ticks.push(buckets > 1 ? b / (buckets - 1) : 0);
    }
    const publishers = new Map<string, { name: string; domain: string | null }>();
    for (const d of list) {
      const name = publisherOf(d.title);
      if (!name) continue;
      const key = name.toLowerCase();
      const own = domainOf(d.resolved_url);
      const domain = own && !own.includes("google.") ? own : (publisherDomains[key] ?? null);
      const known = publishers.get(key);
      if (!known) publishers.set(key, { name, domain });
      else if (!known.domain && domain) known.domain = domain;
    }
    const all = [...publishers.values()].sort((a, b) => Number(Boolean(b.domain)) - Number(Boolean(a.domain)));
    const withImage = list.find((d) => d.image_url);
    const resolved = list.find((d) => d.resolved_url && !d.resolved_url.includes("google."));
    return {
      id: row.incident_id,
      href: `/${lang}/incidents/${row.incident_id}`,
      rank: idx + 1,
      title: incidentTitle(row.title),
      target: titleCase(row.target),
      type: attackLabel(row.attack_type, lang),
      severity: severity(row),
      articles: Number(row.document_count),
      publishers: Math.max(publishers.size, 1),
      trust: trustFromRow(row),
      image: withImage?.image_url ?? (resolved ? `/api/og/${resolved.article_id}` : null),
      days,
      ticks,
      firstDate: f.date(first || null),
      lastDate: f.date(last || null),
      logos: all.slice(0, 8),
      morePublishers: Math.max(0, all.length - 8),
    };
  });
}

/** Panjang gulir relatif tiap adegan "Cara kerja" (rel bukti paling panjang). */
const SCENE_WEIGHTS = [1, 1.4, 1.2, 1, 1.2];

async function processData(lang: Lang, featuredId: string | null, riskGroups: GroupStat[], batches: number) {
  const t = getDict(lang);
  const f = formatters(lang);
  const sc = t.home.scenes;
  const featured = featuredId ? await getIncident(featuredId) : null;
  const docs = featured?.docs ?? [];
  const inc = featured?.incident ?? null;

  // 01 ekstraksi: artikel incident dengan liputan terluas, satu per domain dulu
  const seen = new Set<string>();
  const picked: DocumentRow[] = [];
  for (const d of docs) {
    const publisher = docSource(d).toLowerCase();
    if (!seen.has(publisher)) {
      seen.add(publisher);
      picked.push(d);
    }
  }
  for (const d of docs) if (picked.length < 8 && !picked.includes(d)) picked.push(d);
  const domains = new Set(docs.map((d) => docSource(d).toLowerCase()));
  const cluster: ClusterData = {
    docs: picked.slice(0, 8).map((d) => ({ title: incidentTitle(d.title), domain: docSource(d) })),
    fields: [
      { label: sc.fields.target, value: inc?.target || t.common.unknown },
      { label: sc.fields.type, value: attackLabel(inc?.attack_type ?? null, lang) },
      { label: sc.fields.actor, value: inc?.threat_actor?.split(",")[0] || t.common.unknown },
      { label: sc.fields.sources, value: f.num(domains.size) },
    ],
    summary: sc.summary(f.num(docs.length), f.num(domains.size)),
  };

  // 02 bukti: artikel yang teksnya ter-hash, beserta posisinya di batch Merkle bila sudah ada
  const ev = docs.find((d) => d.content_sha256) ?? docs.find((d) => d.content_fingerprint) ?? docs[0] ?? null;
  const leaf = ev ? await getEvidenceLeaf(ev.evidence_uid, ev.content_sha256) : null;
  const evidence: EvidenceData = {
    title: incidentTitle(ev?.title ?? t.home.processTitle),
    domain: ev ? docSource(ev) : "news",
    url: (ev?.resolved_url || ev?.article_url || "").replace(/^https?:\/\//, ""),
    fetched: f.dateTime(ev?.content_fetched_at ?? ev?.published_date),
    hash: ev?.content_sha256 ?? ev?.content_fingerprint ?? "",
    leaf: leaf ? { index: f.num(leaf.leaf_index + 1), count: f.num(leaf.leaf_count), batch: leaf.batch_id } : null,
    root: leaf?.merkle_root ?? null,
  };

  // 03 kepercayaan: skor incident yang sama (pipeline V0.7 bila sudah terbit)
  const bestTarget = Math.max(
    0,
    ...docs.map((d) => {
      if (!d.target || d.target === "UNKNOWN" || !d.field_confidence) return 0;
      try {
        return Number((JSON.parse(d.field_confidence) as Record<string, number>).target ?? 0);
      } catch {
        return 0;
      }
    }),
  );
  const detailDomains = new Set(docs.map((d) => d.source_domain || domainOf(d.resolved_url) || d.source_name || "").filter(Boolean));
  const trust =
    (inc && trustFromStored(inc)) ??
    trustScore({
      independence: inc?.independence ?? null,
      domains: detailDomains.size,
      docs: docs.length,
      targetConfidence: bestTarget,
      contentShare: docs.length ? docs.filter((d) => d.content_status === "ok").length / docs.length : 0,
      clustering: Number(inc?.incident_confidence ?? 0),
    });
  const trustData: TrustData = {
    score: Math.round(trust.score * 100),
    level: t.levels[trust.level],
    parts: trust.parts.map((p) => ({
      label: t.trust.parts[p.key],
      weight: p.weight,
      value: p.value,
      weightText: f.score(p.weight),
      valueText: f.score(p.value),
      plus: `+${Math.round(p.weight * p.value * 100)}`,
    })),
  };

  // 04 temuan: kelompok sasaran × jenis serangan, 30 hari
  const top = riskGroups.filter((g) => g.now > 0).slice(0, 6);
  const typeTotals = new Map<string, number>();
  for (const g of top) for (const [type, n] of Object.entries(g.typesAll)) if (type !== "unknown") typeTotals.set(type, (typeTotals.get(type) ?? 0) + n);
  const types = [...typeTotals.entries()].sort((a, b) => b[1] - a[1]).slice(0, 5).map(([type]) => type);
  const rows = top.map((g) => {
    const level = riskLevel(g);
    const pct = g.prev ? Math.round((100 * (g.now - g.prev)) / g.prev) : null;
    return {
      label: groupLabel(g.group, lang),
      counts: types.map((type) => g.typesAll[type] ?? 0),
      now: f.num(g.now),
      change: pct === null ? t.findings.change.new : pct > 0 ? t.findings.change.up(pct) : pct < 0 ? t.findings.change.down(Math.abs(pct)) : t.findings.change.same,
      changeColor: pct !== null && pct < 0 ? "var(--good)" : "var(--high)",
      levelColor: LEVEL_COLOR[level],
      levelLabel: t.findings.levels[level],
    };
  });
  const risk: RiskData = { types: types.map((type) => attackLabel(type, lang)), rows, max: Math.max(1, ...rows.flatMap((r) => r.counts)) };

  // 05 paket: pratinjau paket mingguan dari temuan di atas, tertaut ke batch bukti terakhir
  const week = isoWeek(new Date());
  const findings = top.slice(0, 3).map((g) => `${groupLabel(g.group, lang)} · ${attackLabel(g.types[0]?.t ?? "unknown", lang)}`);
  const batchChips = batches > 0 ? [batches - 2, batches - 1, batches].filter((n) => n > 0).map((n) => sc.batch(n)) : ["batch …"];
  const pkg: PackageData = {
    week: sc.week(week),
    findings,
    batches: batchChips,
    hash: createHash("sha256").update(JSON.stringify({ week, findings, batches: batchChips })).digest("hex"),
  };
  return { cluster, evidence, trust: trustData, risk, pkg };
}

export default async function Home({ params }: { params: Promise<{ lang: string }> }) {
  const { lang } = await params;
  if (!isLang(lang)) notFound();
  const t = getDict(lang);
  const f = formatters(lang);
  const locale = lang === "en" ? "en-GB" : "id-ID";

  const [overview, latest, countries, news, languages, feed, lastRun, featuredId, riskGroups, ledgerStats] = await Promise.all([
    getOverview(),
    getLatestIncidents(5),
    getCountryCounts(90),
    getNewsFeed(36),
    getLanguageCounts(),
    getScannerFeed(8),
    getLastRun(),
    getShowcaseIncidentId(),
    getRiskGroups(),
    getLedgerStats(),
  ]);
  const [coverageDocs, publisherDomains] = await Promise.all([getCoverageDocs(latest.map((r) => r.incident_id)), getPublisherDomains()]);
  const coverage = coverageItems(lang, latest, coverageDocs, publisherDomains);
  const scenes = await processData(lang, featuredId ?? (await getFeaturedIncidentId()) ?? latest[0]?.incident_id ?? null, riskGroups, ledgerStats?.batches ?? 0);
  const steps = t.home.steps;
  const common = { total: steps.length, aiTag: "AI", labels: t.home.scenes };
  const newsItems: NewsItem[] = news.map((r) => ({
    id: Number(r.article_id),
    title: incidentTitle(r.title),
    domain: r.source_domain,
    date: f.date(r.published_date),
    type: attackLabel((r.attack_type ?? "").split(",")[0].trim(), lang),
    language: languageLabel(r.language, lang),
    href: L(lang, `/incidents/${r.incident_id}`),
    image: r.image_url ?? `/api/og/${r.article_id}`,
  }));
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
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <span className="label inline-flex items-center gap-2 text-accent">
              <span className="led led-accent" aria-hidden="true" />
              {t.brand}
            </span>
            <span className="text-[13.5px] font-medium text-soft">{t.tagline}</span>
          </div>
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
          <span className="label pt-1 text-muted">{t.home.eyebrow}</span>
        </Reveal>
        <div className="flex flex-col gap-2">
          <IntelScanner items={scanItems} labels={t.home.scanner} stamp={version ? `pipeline ${version}` : ""} />
          <span className="text-[11.5px] text-muted">{t.home.scanner.note}</span>
        </div>
      </section>
      <div className="hairline -mt-6" aria-hidden="true" />

      {/* Instrumen: empat angka dan volume harian */}
      <Reveal>
        <section className="flex flex-col gap-3">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Stat label={t.home.metrics.incidents} value={<CountUp value={Number(overview.incident)} locale={locale} />} note={t.home.metricNotes.incidents(f.num(overview.incident_30))} tone="accent" live />
            <Stat label={t.home.metrics.articles} value={<CountUp value={Number(overview.artikel)} locale={locale} />} note={t.home.metricNotes.articles(f.num(overview.sumber))} />
            <Stat label={t.home.metrics.corroborated} value={<CountUp value={Number(overview.multi_all)} locale={locale} />} note={t.home.metricNotes.corroborated} tone="good" />
            <Stat label={t.home.metrics.evidence} value={<CountUp value={Number(overview.bukti)} locale={locale} />} note={t.home.metricNotes.evidence} tone="chain" />
          </div>
          <div className="flex flex-col gap-3 pt-2">
            <SectionTitle aside={t.home.newsNote}>{t.home.newsTitle}</SectionTitle>
            <NewsSlider items={newsItems} prevLabel={t.common.prev} nextLabel={t.common.next} />
          </div>
        </section>
      </Reveal>

      {/* Liputan terluas: kartu sorotan (#1) dan baris peringkat */}
      <Reveal>
        <section className="flex flex-col gap-4">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="text-[22px] font-semibold">{t.home.coverageTitle}</h2>
            <span className="text-[13px] text-muted">{t.home.coverageNote}</span>
          </div>
          {coverage.length ? (
            <div className="grid gap-4 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)]">
              <CoverageFeature item={coverage[0]} labels={t.home.coverage} lang={lang} locale={locale} />
              <div className="flex flex-col gap-3">
                {coverage.slice(1).map((item, i) => (
                  <CoverageRow key={item.id} item={item} labels={t.home.coverage} lang={lang} index={i} />
                ))}
                <Link href={L(lang, "/incidents")} className="self-end pt-1 text-[13px] no-underline">
                  {t.home.coverage.all} →
                </Link>
              </div>
            </div>
          ) : null}
        </section>
      </Reveal>

      {/* Sebaran bahasa dan negara */}
      <Reveal>
        <section className="grid gap-4 lg:grid-cols-2">
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
        </section>
      </Reveal>

      {/* Cara kerja: lima adegan scroll-driven, teknik berbeda per langkah (tanpa Reveal: tinggi adegan melebihi layar) */}
      <section id="process" className="flex scroll-mt-20 flex-col gap-4">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="text-[22px] font-semibold">{t.home.processTitle}</h2>
          <span className="text-[13px] text-muted">{t.home.processNote}</span>
        </div>
        <ScrollScenes weights={SCENE_WEIGHTS}>
          <SceneCluster {...common} step={steps[0]} index={0} data={scenes.cluster} />
          <SceneEvidence {...common} step={steps[1]} index={1} data={scenes.evidence} />
          <SceneTrust {...common} step={steps[2]} index={2} data={scenes.trust} />
          <SceneRisk {...common} step={steps[3]} index={3} data={scenes.risk} />
          <ScenePackage {...common} step={steps[4]} index={4} data={scenes.pkg} />
        </ScrollScenes>
      </section>

      {/* Lembaga dan program literasi */}
      <Reveal>
        <section className="grid gap-4 lg:grid-cols-2">
          <div className="card lift flex flex-col gap-3 p-5" style={{ borderTopColor: "var(--chain)", borderTopWidth: 2 }}>
            <div className="flex items-center justify-between gap-3">
              <h2 className="text-[18px] font-semibold">{t.home.institutionsTitle}</h2>
              <div className="hidden gap-2 sm:flex">
                {ORGS.map((org, i) => (
                  <span key={org} className="fade-up" style={{ "--i": i * 2 } as React.CSSProperties}>
                    <OrgLogo org={org} size={40} />
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
