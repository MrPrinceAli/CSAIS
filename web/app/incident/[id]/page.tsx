import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getIncident, type DocumentRow } from "@/lib/queries";
import { attackCode, domainOf, EVIDENCE_LABEL, fmtDate, fmtDateTime, fmtNum, fmtScore, incidentTitle, languageLabel, RELATION_LABEL, severity } from "@/lib/format";
import { trustScore, TRUST_COLOR } from "@/lib/trust";
import { HashGrid, IncidentCard, SectionTitle, SeverityText, SourceLogo, TrustRing } from "@/components/ui";

type Params = { id: string };

export async function generateMetadata({ params }: { params: Promise<Params> }): Promise<Metadata> {
  const { id } = await params;
  const data = await getIncident(id);
  return { title: data ? incidentTitle(data.incident.title) : "Incident tidak ditemukan" };
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

function bestClaims(docs: DocumentRow[]) {
  const fields = [
    { key: "target", label: "Target" },
    { key: "threat_actor", label: "Pelaku" },
    { key: "attack_type", label: "Jenis serangan" },
    { key: "attack_date", label: "Tanggal kejadian" },
  ] as const;
  return fields.map((f) => {
    let best: { value: string; confidence: number } | null = null;
    const values = new Set<string>();
    for (const d of docs) {
      const value = d[f.key];
      if (!value || value === "UNKNOWN") continue;
      values.add(value);
      const confidence = parseConfidence(d.field_confidence)[f.key] ?? 0;
      if (!best || confidence > best.confidence) best = { value, confidence };
    }
    return { ...f, best, variants: values.size };
  });
}

export default async function IncidentDetail({ params }: { params: Promise<Params> }) {
  const { id } = await params;
  const data = await getIncident(id);
  if (!data) notFound();
  const { incident, docs, relations, related } = data;
  const level = severity(incident);
  const claims = bestClaims(docs);
  const domains = new Set(docs.map((d) => d.source_domain || domainOf(d.resolved_url) || d.source_name || "").filter(Boolean));
  const syndicated = docs.filter((d) => d.syndicated_of).length;
  const withContent = docs.filter((d) => d.content_status === "ok").length;
  const targetClaim = claims.find((c) => c.key === "target");
  const trust = trustScore({
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
      <nav className="flex items-center gap-2 text-[13px] text-muted" aria-label="Jejak">
        <Link href="/incident" className="no-underline">
          Incident
        </Link>
        <span className="text-line-2">/</span>
        <span className="font-mono">{incident.incident_id}</span>
      </nav>

      <header className="grid gap-4 border-b border-line pb-5 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="flex flex-col gap-2.5">
          <div className="flex flex-wrap items-center gap-3">
            <SeverityText level={level} />
            <span className="font-mono text-[12px] text-muted">
              {attackCode(incident.attack_type)}
              {incident.location ? ` · ${incident.location}` : ""}
              {incident.language ? ` · artikel jangkar ${languageLabel(incident.language)}` : ""}
            </span>
          </div>
          <h1 className="text-balance text-[26px] font-bold leading-tight">{incidentTitle(incident.title)}</h1>
          <div className="flex flex-wrap gap-x-5 gap-y-1 text-[13px] text-soft">
            <span>
              Pertama terlihat <b className="text-fg">{fmtDateTime(incident.anchor_published_date)}</b>
            </span>
            <span>
              Terbaru <b className="text-fg">{fmtDate(incident.last_published_date)}</b>
            </span>
            <span>
              <b className="text-fg">{fmtNum(docs.length)}</b> artikel · <b className="text-fg">{fmtNum(domains.size)}</b> domain · <b className="text-fg">{fmtNum(syndicated)}</b> sindikasi
            </span>
          </div>
          <div className="flex flex-wrap gap-2 pt-1">
            {incident.target ? <span className="chip">target {incident.target}</span> : null}
            {incident.threat_actor ? <span className="chip chip-accent">pelaku {incident.threat_actor}</span> : null}
            <Link href={`/verifikasi?q=${encodeURIComponent(firstUid)}`} className="chip chip-chain no-underline">
              verifikasi bukti
            </Link>
          </div>
        </div>
        <div className="card flex items-center gap-4 p-4">
          <TrustRing trust={trust} size={84} />
          <div className="flex min-w-0 flex-1 flex-col gap-1.5">
            <span className="label">Skor kepercayaan (sementara)</span>
            <span className="text-[15px] font-semibold capitalize" style={{ color: TRUST_COLOR[trust.level] }}>
              {trust.level}
            </span>
            {trust.parts.map((p) => (
              <div key={p.key} className="grid grid-cols-[minmax(0,1fr)_60px] items-center gap-2 text-[11.5px] text-soft">
                <span className="truncate">{p.label}</span>
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
            <SectionTitle>Klaim terekstrak</SectionTitle>
            <div className="card flex flex-col gap-3.5 p-3.5">
              {claims.map((c) => (
                <div key={c.key} className="flex flex-col gap-1">
                  <div className="flex justify-between text-[12px] text-muted">
                    <span>{c.label}</span>
                    <span className="font-mono">{c.best ? `keyakinan ${fmtScore(c.best.confidence)}` : "tidak ditemukan"}</span>
                  </div>
                  <span className="text-[14.5px] font-semibold">{c.best ? c.best.value : <span className="font-normal text-muted">belum dikenali</span>}</span>
                  <span className="block h-1 overflow-hidden rounded-sm bg-line">
                    <span
                      className={`block h-full ${c.best && c.best.confidence >= 0.8 ? "bg-good" : c.best && c.best.confidence >= 0.5 ? "bg-med" : "bg-high"}`}
                      style={{ width: `${Math.round(100 * (c.best?.confidence ?? 0))}%` }}
                    />
                  </span>
                  {c.variants > 1 ? <span className="text-[12px] text-high">{c.variants} nilai berbeda antar artikel; perlu ditinjau.</span> : null}
                </div>
              ))}
            </div>
          </div>
          <div>
            <SectionTitle>Incident lain, target sama</SectionTitle>
            {related.length ? (
              <div className="flex flex-col gap-2">
                {related.map((row) => (
                  <IncidentCard key={row.incident_id} row={row} />
                ))}
              </div>
            ) : (
              <div className="card p-3.5 text-[13px] text-muted">Tidak ada incident lain dengan target yang sama.</div>
            )}
          </div>
        </section>

        <section className="flex min-w-0 flex-col gap-4">
          <div>
            <SectionTitle aside={`${fmtNum(docs.length)} artikel, urut waktu terbit`}>Garis waktu sumber</SectionTitle>
            <ol className="card relative flex flex-col p-3.5">
              {docs.map((d, i) => {
                const href = d.resolved_url || d.article_url || "#";
                const domain = d.source_domain || domainOf(d.resolved_url) || d.source_name || "";
                const role = i === 0 ? "Pertama" : d.syndicated_of ? "Sindikasi" : EVIDENCE_LABEL[d.evidence_type ?? ""] ?? "";
                const dot = i === 0 ? "bg-accent" : role === "Independen" ? "bg-good" : role === "Sindikasi" || role === "Duplikat" ? "bg-line-2" : "bg-med";
                const hours = d.published_date && firstTs ? Math.round((new Date(d.published_date).getTime() - firstTs) / 3600000) : null;
                return (
                  <li key={d.article_id} className="grid grid-cols-[18px_minmax(0,1fr)] gap-3 border-b border-line py-3 last:border-b-0">
                    <span className="relative flex justify-center">
                      <span className="absolute top-3 bottom-[-14px] w-px bg-line" aria-hidden="true" />
                      <span className={`relative mt-1.5 h-2.5 w-2.5 rounded-full ${dot}`} aria-hidden="true" />
                    </span>
                    <div className="flex min-w-0 flex-col gap-1">
                      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 font-mono text-[11px] text-muted">
                        <span>{fmtDateTime(d.published_date)}</span>
                        {hours !== null && i > 0 ? <span>+{hours} jam</span> : null}
                        <span className={role === "Pertama" ? "text-accent" : role === "Independen" ? "text-good" : ""}>{role}</span>
                        {d.content_status === "ok" ? <span className="text-chain">isi penuh ter-hash</span> : null}
                      </div>
                      <a href={href} target="_blank" rel="noreferrer" className="flex items-start gap-2 text-[13.5px] font-semibold text-fg no-underline hover:text-accent">
                        {domain ? <SourceLogo domain={domain} size={16} /> : null}
                        <span className="min-w-0">
                          {d.title ?? "(tanpa judul)"}
                          <span className="block font-mono text-[11px] font-normal text-muted">{domain || "-"}</span>
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
            <span className="text-[12px] text-muted">Hubungan antar sumber (V0.6)</span>
            {relations.length ? (
              <div className="flex flex-wrap gap-2">
                {relations.map((r) => (
                  <span key={r.relation_type} className="chip">
                    {fmtNum(Number(r.n))} pasangan {RELATION_LABEL[r.relation_type] ?? r.relation_type.toLowerCase()}
                  </span>
                ))}
              </div>
            ) : (
              <span className="text-[13px] text-soft">Satu sumber saja; belum ada pasangan artikel untuk dibandingkan.</span>
            )}
          </div>
        </section>

        <section className="flex flex-col gap-4">
          <div>
            <SectionTitle>Bukti</SectionTitle>
            <div className="card flex flex-col gap-3 p-3.5 text-[12.5px]">
              <div className="flex items-center gap-3">
                <HashGrid hex={firstHash} size={72} label="Sidik jari hash artikel pertama" />
                <div className="flex flex-col gap-1">
                  <span className="text-muted">Hash disiapkan</span>
                  <span className="tnum font-mono text-[15px] font-bold">{fmtNum(docs.filter((d) => d.evidence_uid).length)}</span>
                  <span className="text-muted">isi penuh ter-hash {fmtNum(docs.filter((d) => d.content_sha256).length)}</span>
                </div>
              </div>
              {firstUid ? (
                <div className="flex flex-col gap-1 border-t border-line pt-2">
                  <span className="text-muted">evidence_uid pertama</span>
                  <span className="break-all font-mono text-[11.5px]">{firstUid}</span>
                </div>
              ) : null}
              <span className="chip chip-chain self-start">Penjangkaran ke rantai: tahap berikutnya</span>
            </div>
          </div>
          <div>
            <SectionTitle>Atestasi lembaga</SectionTitle>
            <div className="card p-3.5 text-[13px] text-soft">Belum ada. Portal atestasi dibuka setelah kontrak terpasang.</div>
          </div>
        </section>
      </div>
    </div>
  );
}
