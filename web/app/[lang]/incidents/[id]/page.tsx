import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getIncident, type DocumentRow } from "@/lib/queries";
import { domainOf, formatters, incidentTitle, severity } from "@/lib/format";
import { attackLabel, evidenceRole, getDict, isLang, L, languageLabel } from "@/lib/i18n";
import { trustFromStored, trustScore, TRUST_COLOR } from "@/lib/trust";
import { HashGrid, IncidentCard, SectionTitle, SeverityText, SourceLogo, TrustRing } from "@/components/ui";

type Params = { lang: string; id: string };

export async function generateMetadata({ params }: { params: Promise<Params> }): Promise<Metadata> {
  const { lang, id } = await params;
  const data = await getIncident(id);
  return { title: data ? incidentTitle(data.incident.title) : getDict(isLang(lang) ? lang : "id").notFound.title };
}

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

export default async function IncidentDetail({ params }: { params: Promise<Params> }) {
  const { lang, id } = await params;
  if (!isLang(lang)) notFound();
  const t = getDict(lang);
  const f = formatters(lang);
  const data = await getIncident(id);
  if (!data) notFound();
  const { incident, docs, relations, related, ledgerCount } = data;
  const level = severity(incident);
  const claims = bestClaims(docs);
  const domains = new Set(docs.map((d) => d.source_domain || domainOf(d.resolved_url) || d.source_name || "").filter(Boolean));
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

  return (
    <div className="flex flex-col gap-5">
      <nav className="flex items-center gap-2 text-[13px] text-muted" aria-label="Breadcrumb">
        <Link href={L(lang, "/incidents")} className="no-underline">
          {t.detail.breadcrumb}
        </Link>
        <span className="text-line-2">/</span>
        <span className="font-mono">{incident.incident_id}</span>
      </nav>

      <header className="grid gap-4 border-b border-line pb-5 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="flex flex-col gap-2.5">
          <div className="flex flex-wrap items-center gap-3">
            <SeverityText level={level} lang={lang} />
            <span className="text-[12.5px] text-muted">
              {attackLabel(incident.attack_type, lang)}
              {incident.location ? ` · ${countryLabel(incident.location)}` : ""}
              {incident.language ? ` · ${t.detail.anchorLanguage}: ${languageLabel(incident.language, lang)}` : ""}
            </span>
          </div>
          <h1 className="text-balance text-[26px] font-semibold leading-tight">{incidentTitle(incident.title)}</h1>
          <div className="flex flex-wrap gap-x-5 gap-y-1 text-[13px] text-soft">
            <span>
              {t.detail.firstSeen} <b className="font-medium text-fg">{f.dateTime(incident.anchor_published_date)}</b>
            </span>
            <span>
              {t.detail.latest} <b className="font-medium text-fg">{f.date(incident.last_published_date)}</b>
            </span>
            <span>
              <b className="font-medium text-fg">{f.num(docs.length)}</b> {t.common.articles} · <b className="font-medium text-fg">{f.num(domains.size)}</b> {t.common.domains} ·{" "}
              <b className="font-medium text-fg">{f.num(syndicated)}</b> {t.roles.syndicated.toLowerCase()}
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
              {t.trust.title} · {t.trust.preliminary}
            </span>
            <span className="text-[11px] text-muted">{t.trust.computedBy[trust.source]}</span>
            <span className="text-[15px] font-semibold capitalize" style={{ color: TRUST_COLOR[trust.level] }}>
              {t.levels[trust.level]}
            </span>
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

      <div className="grid gap-4 lg:grid-cols-[300px_minmax(0,1fr)_300px]">
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
          <div>
            <SectionTitle>{t.detail.relatedTitle}</SectionTitle>
            {related.length ? (
              <div className="flex flex-col gap-2">
                {related.map((row) => (
                  <IncidentCard key={row.incident_id} row={row} lang={lang} />
                ))}
              </div>
            ) : (
              <div className="card p-3.5 text-[13px] text-muted">{t.detail.relatedEmpty}</div>
            )}
          </div>
        </section>

        <section className="flex min-w-0 flex-col gap-4">
          <div>
            <SectionTitle aside={t.detail.chronologyNote(f.num(docs.length))}>{t.detail.chronologyTitle}</SectionTitle>
            <ol className="card flex flex-col p-3.5">
              {docs.map((d, i) => {
                const href = d.resolved_url || d.article_url || "#";
                const domain = d.source_domain || domainOf(d.resolved_url) || d.source_name || "";
                const role = i === 0 ? t.roles.first : d.syndicated_of ? t.roles.syndicated : evidenceRole(d.evidence_type, lang);
                const dot = i === 0 ? "bg-accent" : role === t.roles.independent ? "bg-good" : role === t.roles.syndicated || role === t.roles.duplicate ? "bg-line-2" : "bg-med";
                const hours = d.published_date && firstTs ? Math.round((new Date(d.published_date).getTime() - firstTs) / 3600000) : null;
                return (
                  <li key={d.article_id} className="fade-up grid grid-cols-[18px_minmax(0,1fr)] gap-3 border-b border-line py-3 last:border-b-0" style={{ "--i": Math.min(i, 24) } as React.CSSProperties}>
                    <span className="relative flex justify-center">
                      <span className="tl-line absolute top-3 bottom-[-14px] w-px bg-line-2" aria-hidden="true" style={{ "--i": Math.min(i, 24) } as React.CSSProperties} />
                      <span className={`tl-dot relative mt-1.5 h-2.5 w-2.5 rounded-full ${dot}`} aria-hidden="true" style={{ "--i": Math.min(i, 24) } as React.CSSProperties} />
                    </span>
                    <div className="flex min-w-0 flex-col gap-1">
                      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 font-mono text-[11px] text-muted">
                        <span>{f.dateTime(d.published_date)}</span>
                        {hours !== null && i > 0 ? <span>{t.detail.hoursAfter(hours)}</span> : null}
                        <span className={i === 0 ? "text-accent" : role === t.roles.independent ? "text-good" : ""}>{role}</span>
                        {d.content_status === "ok" ? <span className="text-chain">{t.detail.fullText}</span> : null}
                      </div>
                      <a href={href} target="_blank" rel="noreferrer" className="flex items-start gap-2 text-[13.5px] font-semibold text-fg no-underline hover:text-accent">
                        {domain ? <SourceLogo domain={domain} size={16} /> : null}
                        <span className="min-w-0">
                          {d.title ?? "—"}
                          <span className="block font-mono text-[11px] font-normal text-muted">{domain || "—"}</span>
                        </span>
                      </a>
                      {(d.target && d.target !== "UNKNOWN") || (d.threat_actor && d.threat_actor !== "UNKNOWN") ? (
                        <div className="flex flex-wrap gap-1.5">
                          {d.target && d.target !== "UNKNOWN" ? <span className="chip">{d.target}</span> : null}
                          {d.threat_actor && d.threat_actor !== "UNKNOWN" ? <span className="chip chip-accent">{d.threat_actor}</span> : null}
                        </div>
                      ) : null}
                    </div>
                  </li>
                );
              })}
            </ol>
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

        <section className="flex flex-col gap-4">
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
              <span className="chip chip-chain self-start">{t.detail.anchoring}</span>
            </div>
          </div>
          <div>
            <SectionTitle>{t.detail.attestTitle}</SectionTitle>
            <div className="card p-3.5 text-[13px] text-soft">{t.detail.attestEmpty}</div>
          </div>
        </section>
      </div>
    </div>
  );

  function countryLabel(location: string): string {
    const first = location.split(",")[0].trim();
    return first.charAt(0).toUpperCase() + first.slice(1);
  }
}
