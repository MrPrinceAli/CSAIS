/* Isi detail incident bersama untuk halaman penuh dan jendela pop-up. */
import Link from "next/link";
import { notFound } from "next/navigation";
import { getIncident, getIncidentTier, getPublisherDomains, type DocumentRow } from "@/lib/queries";
import { domainOf, formatters, incidentTitle, publisherOf, severity } from "@/lib/format";
import { attackLabel, evidenceRole, getDict, L, languageLabel, type Lang } from "@/lib/i18n";
import { trustFromStored, trustScore, TRUST_COLOR } from "@/lib/trust";
import { FlowCompare } from "@/components/flow-compare";
import { PreventionPanel } from "@/components/prevention-panel";
import { HashGrid, IncidentCard, SectionTitle, SeverityText, SourceLogo, TierBadge, TrustRing, TypeChip } from "@/components/ui";

/** Jumlah artikel kronologi yang langsung terlihat; sisanya di balik "Lihat semua". */
const VISIBLE = 10;

type FieldConfidence = Record<string, number>;

function parseConfidence(raw: string | null): FieldConfidence {
  if (!raw) return {};
  try {
    return JSON.parse(raw) as FieldConfidence;
  } catch {
    return {};
  }
}

const CLAIM_KEYS = ["target", "threat_actor", "attack_type", "attack_date"] as const;

function bestClaims(docs: DocumentRow[]) {
  return CLAIM_KEYS.map((key) => {
    let best: { value: string; confidence: number } | null = null;
    const values = new Set<string>();
    for (const d of docs) {
      const value = d[key];
      if (!value || value === "UNKNOWN") continue;
      values.add(value);
      const confidence = parseConfidence(d.field_confidence)[key] ?? 0;
      if (!best || confidence > best.confidence) best = { value, confidence };
    }
    return { key, best, variants: values.size };
  });
}

/** Sumber sebuah artikel: domain media asli bila ada, selain itu penerbit dari akhiran judul Google News. */
function sourceOf(d: DocumentRow, publisherDomains: Record<string, string>): { label: string; domain: string | null } {
  for (const domain of [domainOf(d.resolved_url), d.source_domain ?? ""]) {
    if (domain && !domain.includes("google.")) return { label: domain, domain };
  }
  const publisher = publisherOf(d.title);
  if (publisher) return { label: publisher, domain: publisherDomains[publisher.toLowerCase()] ?? null };
  return { label: d.source_name ?? "—", domain: null };
}

type Row = { d: DocumentRow; i: number };
type Day = { key: string; rows: Row[] };

function groupByDay(docs: DocumentRow[], dayKey: (v: string | null) => string): Day[] {
  const days: Day[] = [];
  docs.forEach((d, i) => {
    const key = dayKey(d.published_date);
    const last = days[days.length - 1];
    if (last && last.key === key) last.rows.push({ d, i });
    else days.push({ key, rows: [{ d, i }] });
  });
  return days;
}

/**
 * Isi halaman detail incident. Dipakai halaman penuh (/incidents/[id]) dan
 * jendela pop-up di atas dasbor incident (rute yang dicegat); varian "modal"
 * tanpa breadcrumb karena jendelanya sudah punya bilah judul sendiri.
 */
export async function IncidentDetailView({ lang, id, variant = "page" }: { lang: Lang; id: string; variant?: "page" | "modal" }) {
  const t = getDict(lang);
  const f = formatters(lang);
  const [data, publisherDomains, tier] = await Promise.all([getIncident(id), getPublisherDomains(), getIncidentTier(id)]);
  if (!data) notFound();
  const { incident, docs, relations, related, ledgerCount, flows } = data;
  const level = severity(incident);
  const claims = bestClaims(docs);
  const domains = new Set(docs.map((d) => d.source_domain || domainOf(d.resolved_url) || d.source_name || "").filter(Boolean));
  const publishers = new Set(docs.map((d) => sourceOf(d, publisherDomains).label.toLowerCase()));
  const syndicated = docs.filter((d) => d.syndicated_of).length;
  const withContent = docs.filter((d) => d.content_status === "ok").length;
  const targetClaim = claims.find((c) => c.key === "target");
  // Skor V0.7 dari pipeline bila sudah diterbitkan; perhitungan halaman hanya cadangan
  const trust =
    trustFromStored(incident) ??
    trustScore({
      independence: incident.independence,
      domains: domains.size,
      docs: docs.length,
      targetConfidence: targetClaim?.best?.confidence ?? 0,
      contentShare: docs.length ? withContent / docs.length : 0,
      clustering: incident.incident_confidence,
    });
  const firstHash = docs.find((d) => d.content_sha256)?.content_sha256 ?? docs.find((d) => d.content_fingerprint)?.content_fingerprint ?? null;
  const firstUid = docs.find((d) => d.evidence_uid)?.evidence_uid ?? "";
  const firstTs = docs[0]?.published_date ? new Date(docs[0].published_date).getTime() : 0;
  const days = groupByDay(docs, (v) => f.dayKey(v));
  // Tanggal dari artikel sendiri: artikel jangkar bisa terbit lebih lambat dari
  // artikel paling awal (incident lanjutan dirangkai ke incident lama).
  const dates = [incident.anchor_published_date, ...docs.map((d) => d.published_date)].filter((v): v is string => Boolean(v));
  const firstSeen = dates.reduce((a, b) => (new Date(b) < new Date(a) ? b : a), dates[0] ?? "");
  const lastDates = [incident.last_published_date, ...docs.map((d) => d.published_date)].filter((v): v is string => Boolean(v));
  const lastSeen = lastDates.reduce((a, b) => (new Date(b) > new Date(a) ? b : a), lastDates[0] ?? "");

  /** Satu artikel dalam kronologi; peran hanya ditulis bila bukan "independen". */
  const renderRow = ({ d, i }: Row) => {
    const src = sourceOf(d, publisherDomains);
    const href = d.resolved_url || d.article_url || "#";
    const role = i === 0 ? t.roles.first : d.syndicated_of ? t.roles.syndicated : evidenceRole(d.evidence_type, lang);
    const quiet = i > 0 && (role === t.roles.independent || role === t.roles.single);
    const dot = i === 0 ? "bg-accent" : quiet ? "bg-good" : role === t.roles.syndicated || role === t.roles.duplicate ? "bg-line-2" : "bg-med";
    const hours = d.published_date && firstTs ? Math.round((new Date(d.published_date).getTime() - firstTs) / 3600000) : null;
    return (
      <li key={d.article_id} className="grid grid-cols-[18px_minmax(0,1fr)] gap-3 py-2.5">
        <span className="relative flex justify-center">
          <span className={`relative mt-1.5 h-2.5 w-2.5 rounded-full ${dot}`} aria-hidden="true" />
        </span>
        <div className="flex min-w-0 flex-col gap-1">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[12px] text-muted">
            <span className="font-mono">{f.clock(d.published_date)}</span>
            {hours !== null && i > 0 ? <span>{t.detail.hoursAfter(hours)}</span> : null}
            {!quiet ? <span className={i === 0 ? "text-accent" : "text-soft"}>{role}</span> : null}
            {d.content_status === "ok" ? <span className="text-chain">{t.detail.fullText}</span> : null}
          </div>
          <a href={href} target="_blank" rel="noreferrer" className="text-[14px] font-semibold leading-snug text-fg no-underline hover:text-accent">
            {incidentTitle(d.title)}
          </a>
          <span className="flex min-w-0 flex-wrap items-center gap-2 text-[12px] text-soft">
            {src.domain ? (
              <SourceLogo domain={src.domain} size={12} />
            ) : (
              <span className="cov-mono" style={{ width: 20, height: 20 }} aria-hidden="true">
                {src.label.replace(/[^\p{L}\p{N}]/gu, "").slice(0, 2)}
              </span>
            )}
            <span className="truncate">{src.label}</span>
            {d.target && d.target !== "UNKNOWN" ? <span className="chip">{d.target}</span> : null}
            {d.threat_actor && d.threat_actor !== "UNKNOWN" ? <span className="chip chip-accent">{d.threat_actor}</span> : null}
          </span>
        </div>
      </li>
    );
  };

  /** Kelompok per hari; bila satu hari terpotong batas VISIBLE, lanjutannya diberi tanda. */
  const renderDays = (visible: boolean) =>
    days.map((day) => {
      const rows = day.rows.filter((r) => (visible ? r.i < VISIBLE : r.i >= VISIBLE));
      if (!rows.length) return null;
      const continued = !visible && day.rows[0].i < VISIBLE;
      return (
        <section key={`${day.key}-${visible}`} className="flex flex-col">
          <h3 className="flex items-baseline justify-between gap-3 border-b border-line pb-2 pt-3">
            <span className="text-[13px] font-semibold">
              {f.dateLong(day.rows[0].d.published_date)}
              {continued ? <span className="font-normal text-muted"> · {t.detail.continued}</span> : null}
            </span>
            <span className="text-[12px] text-muted">{t.detail.dayCount(f.num(day.rows.length))}</span>
          </h3>
          <ol className="flex flex-col">{rows.map(renderRow)}</ol>
        </section>
      );
    });

  return (
    <div className="flex flex-col gap-5">
      {variant === "page" ? (
        <nav className="flex items-center gap-2 text-[13px] text-muted" aria-label="Breadcrumb">
          <Link href={L(lang, "/incidents")} className="no-underline">
            {t.detail.breadcrumb}
          </Link>
          <span className="text-line-2">/</span>
          <span className="font-mono">{incident.incident_id}</span>
        </nav>
      ) : null}

      <header className="grid gap-4 border-b border-line pb-5 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="flex flex-col gap-2.5">
          <div className="flex flex-wrap items-center gap-3">
            {/* keparahan dari pemberitaan tidak relevan bila lembaga membantah kejadiannya */}
            {tier?.tier !== "peringatan_hoaks" ? <SeverityText level={level} lang={lang} /> : null}
            <TierBadge tier={tier?.tier ?? null} lang={lang} institution={tier?.source_flow === "D4" ? tier.institution : null} demo={Boolean(tier?.demo)} />
            <TypeChip attackType={incident.attack_type} lang={lang} />
            <span className="text-[12.5px] text-muted">
              {[incident.location ? countryLabel(incident.location) : "", incident.language ? languageLabel(incident.language, lang) : ""].filter(Boolean).join(" · ")}
            </span>
          </div>
          <h1 className="text-balance text-[26px] font-semibold leading-tight">{incidentTitle(incident.title)}</h1>
          <div className="flex flex-wrap gap-x-5 gap-y-1 text-[13px] text-soft">
            <span>
              {t.detail.firstSeen} <b className="font-medium text-fg">{f.dateTime(firstSeen || null)}</b>
            </span>
            <span>
              {t.detail.latest} <b className="font-medium text-fg">{f.date(lastSeen || null)}</b>
            </span>
            <span>
              <b className="font-medium text-fg">{f.num(docs.length)}</b> {t.common.articles} · <b className="font-medium text-fg">{f.num(publishers.size)}</b> {t.detail.publishers}
              {syndicated ? (
                <>
                  {" · "}
                  <b className="font-medium text-fg">{f.num(syndicated)}</b> {t.roles.syndicated.toLowerCase()}
                </>
              ) : null}
            </span>
          </div>
          <div className="flex flex-wrap gap-2 pt-1">
            {incident.target ? (
              <span className="chip">
                {t.incidents.table.target}: {incident.target}
              </span>
            ) : null}
            {incident.threat_actor ? (
              <span className="chip chip-accent">
                {t.incidents.table.actor}: {incident.threat_actor}
              </span>
            ) : null}
            <Link href={`${L(lang, "/verify")}?q=${encodeURIComponent(firstUid)}`} className="chip chip-chain no-underline">
              {t.detail.verifyEvidence}
            </Link>
          </div>
        </div>
        <div className="card lift flex items-center gap-4 p-4" style={{ borderTopColor: TRUST_COLOR[trust.level], borderTopWidth: 2 }}>
          <TrustRing trust={trust} lang={lang} size={84} />
          <div className="flex min-w-0 flex-1 flex-col gap-1.5">
            <span className="label">
              {t.trust.title} · {trust.verification ? t.trust.final : t.trust.preliminary}
            </span>
            <span className="text-[11px] text-muted">{t.trust.computedBy[trust.source]}</span>
            <span className="text-[15px] font-semibold capitalize" style={{ color: TRUST_COLOR[trust.level] }}>
              {t.levels[trust.level]}
            </span>
            {trust.verification ? (
              <div className="flex flex-col gap-1 rounded-md border border-line p-2 text-[11.5px]">
                <span className="font-semibold text-fg">{t.trust.verified[trust.verification.source]}</span>
                <span className="text-soft">
                  {t.trust.shift(f.score(trust.verification.machine), f.score(trust.score), Math.round(trust.verification.weight * 100))}
                </span>
              </div>
            ) : null}
            {trust.parts.map((p) => (
              <div key={p.key} className="grid grid-cols-[minmax(0,1fr)_64px] items-center gap-2 text-[11.5px] text-soft">
                <span className="truncate">{t.trust.parts[p.key]}</span>
                <span className="block h-1.5 overflow-hidden rounded-sm bg-line">
                  <span className="block h-full" style={{ width: `${Math.round(100 * p.value)}%`, background: TRUST_COLOR[trust.level] }} />
                </span>
              </div>
            ))}
          </div>
        </div>
      </header>

      {tier ? <PreventionPanel tier={tier} lang={lang} /> : null}

      <div className="grid items-start gap-4 lg:grid-cols-[280px_minmax(0,1fr)_280px]">
        <section className="flex flex-col gap-4">
          <div>
            <SectionTitle>{t.detail.claimsTitle}</SectionTitle>
            <div className="card flex flex-col gap-3.5 p-3.5">
              {claims.map((c, i) => (
                <div key={c.key} className="fade-up flex flex-col gap-1" style={{ "--i": i } as React.CSSProperties}>
                  <div className="flex justify-between text-[12px] text-muted">
                    <span>{t.detail.claims[c.key]}</span>
                    <span className="font-mono">{c.best ? t.detail.confidence(f.score(c.best.confidence)) : t.detail.notFound}</span>
                  </div>
                  <span className="text-[14px] font-semibold">
                    {c.best ? (c.key === "attack_type" ? attackLabel(c.best.value, lang) : c.best.value) : <span className="font-normal text-muted">{t.common.unknown}</span>}
                  </span>
                  <span className="block h-1 overflow-hidden rounded-sm bg-line">
                    <span
                      className={`bar-fill block h-full ${c.best && c.best.confidence >= 0.8 ? "bg-good" : c.best && c.best.confidence >= 0.5 ? "bg-med" : "bg-high"}`}
                      style={{ width: `${Math.round(100 * (c.best?.confidence ?? 0))}%`, "--i": i } as React.CSSProperties}
                    />
                  </span>
                  {c.variants > 1 ? <span className="text-[12px] text-high">{t.detail.variants(c.variants)}</span> : null}
                </div>
              ))}
            </div>
          </div>
          {related.length ? (
            <div>
              <SectionTitle>{t.detail.relatedTitle}</SectionTitle>
              <div className="flex flex-col gap-2">
                {related.map((row) => (
                  <IncidentCard key={row.incident_id} row={row} lang={lang} />
                ))}
              </div>
            </div>
          ) : null}
        </section>

        <section className="flex min-w-0 flex-col gap-4">
          <div>
            <SectionTitle aside={t.detail.chronologyNote(f.num(docs.length))}>{t.detail.chronologyTitle}</SectionTitle>
            <div className="card flex flex-col px-3.5 pb-2">
              {renderDays(true)}
              {docs.length > VISIBLE ? (
                <details className="chrono-more">
                  <summary className="btn btn-ghost my-3 flex w-full justify-center text-[13px]">
                    <span className="when-closed">{t.detail.showAll(f.num(docs.length))}</span>
                    <span className="when-open">{t.detail.showLess}</span>
                  </summary>
                  {renderDays(false)}
                </details>
              ) : null}
            </div>
          </div>
          <div className="card flex flex-col gap-1.5 p-3.5">
            <span className="label">{t.detail.relationsTitle}</span>
            {relations.length ? (
              <div className="flex flex-wrap gap-2 pt-1">
                {relations.map((r) => (
                  <span key={r.relation_type} className="chip">
                    {t.detail.pairs(f.num(Number(r.n)), t.relations[r.relation_type as keyof typeof t.relations] ?? r.relation_type.toLowerCase())}
                  </span>
                ))}
              </div>
            ) : (
              <span className="text-[13px] text-soft">{t.detail.relationsEmpty}</span>
            )}
          </div>
        </section>

        <section className={`flex flex-col gap-4 lg:sticky ${variant === "modal" ? "lg:top-0" : "lg:top-20"}`}>
          <div>
            <SectionTitle>{t.detail.evidenceTitle}</SectionTitle>
            <div className="card corners flex flex-col gap-3 p-3.5 text-[12.5px]" style={{ borderTopColor: "var(--chain)", borderTopWidth: 2 }}>
              <div className="flex items-center gap-3">
                <HashGrid hex={firstHash} size={72} label={t.detail.fingerprintFirst} />
                <div className="flex flex-col gap-1">
                  <span className="text-muted">{t.detail.hashesPrepared}</span>
                  <span className="tnum font-mono text-[15px] font-semibold">{f.num(docs.filter((d) => d.evidence_uid).length)}</span>
                  <span className="text-muted">{t.detail.fullHashed(f.num(docs.filter((d) => d.content_sha256).length))}</span>
                </div>
              </div>
              {firstUid ? (
                <div className="flex flex-col gap-1 border-t border-line pt-2">
                  <span className="text-muted">{t.detail.firstUid}</span>
                  <span className="break-all font-mono text-[11.5px]">{firstUid}</span>
                </div>
              ) : null}
              <span className="text-muted">{ledgerCount > 0 ? t.detail.ledgerCount(f.num(ledgerCount), f.num(docs.filter((d) => d.evidence_uid).length)) : t.detail.ledgerNone}</span>
            </div>
          </div>
        </section>
      </div>

      <FlowCompare lang={lang} incidentId={incident.incident_id} outputs={flows} />
    </div>
  );

  function countryLabel(location: string): string {
    const first = location.split(",")[0].trim();
    return first.charAt(0).toUpperCase() + first.slice(1);
  }
}
