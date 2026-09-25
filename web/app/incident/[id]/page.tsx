import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getIncident, type DocumentRow } from "@/lib/queries";
import {
  attackCode,
  domainOf,
  EVIDENCE_LABEL,
  fmtDate,
  fmtDateTime,
  fmtNum,
  fmtScore,
  incidentTitle,
  languageLabel,
  RELATION_LABEL,
  severity,
} from "@/lib/format";
import { IncidentCard, SectionTitle, SeverityText } from "@/components/ui";

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

/** Klaim terbaik per field dari semua artikel: nilai bukan UNKNOWN dengan keyakinan tertinggi. */
function bestClaims(docs: DocumentRow[]) {
  const fields = [
    { key: "target", label: "Target" },
    { key: "threat_actor", label: "Pelaku" },
    { key: "attack_type", label: "Jenis serangan" },
    { key: "attack_date", label: "Tanggal kejadian" },
  ] as const;
  return fields.map((f) => {
    let best: { value: string; confidence: number; article_id: number } | null = null;
    const values = new Set<string>();
    for (const d of docs) {
      const value = d[f.key];
      if (!value || value === "UNKNOWN") continue;
      values.add(value);
      const confidence = parseConfidence(d.field_confidence)[f.key] ?? 0;
      if (!best || confidence > best.confidence) best = { value, confidence, article_id: d.article_id };
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

  return (
    <div className="flex flex-col gap-5">
      <nav className="flex items-center gap-2 text-[13px] text-muted" aria-label="Jejak">
        <Link href="/incident" className="no-underline">
          Incident
        </Link>
        <span className="text-line-2">/</span>
        <span className="font-mono">{incident.incident_id}</span>
      </nav>

      <header className="flex flex-col gap-2.5 border-b border-line pb-4">
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
            Sumber{" "}
            <b className="text-fg">
              {fmtNum(docs.length)} artikel · {fmtNum(domains.size)} domain · {fmtNum(syndicated)} sindikasi
            </b>
          </span>
          <span>
            Keyakinan pengelompokan <b className="text-fg">{fmtScore(incident.incident_confidence)}</b>
          </span>
          <span>
            Isi artikel tersedia <b className="text-fg">{fmtNum(withContent)} dari {fmtNum(docs.length)}</b>
          </span>
        </div>
      </header>

      <div className="grid gap-4 lg:grid-cols-[320px_minmax(0,1fr)_320px]">
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
                  <span className="text-[14.5px] font-semibold">
                    {c.best ? c.best.value : <span className="font-normal text-muted">belum dikenali</span>}
                  </span>
                  <span className="block h-1 overflow-hidden rounded-sm bg-line">
                    <span
                      className={`block h-full ${c.best && c.best.confidence >= 0.8 ? "bg-good" : c.best && c.best.confidence >= 0.5 ? "bg-med" : "bg-high"}`}
                      style={{ width: `${Math.round(100 * (c.best?.confidence ?? 0))}%` }}
                    />
                  </span>
                  {c.variants > 1 ? (
                    <span className="text-[12px] text-high">{c.variants} nilai berbeda antar artikel; perlu ditinjau.</span>
                  ) : null}
                </div>
              ))}
            </div>
          </div>

          <div>
            <SectionTitle>Incident lain dengan target sama</SectionTitle>
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
            <div className="card overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full min-w-[640px] border-collapse text-[12.5px]">
                  <thead>
                    <tr className="label border-b border-line text-left">
                      <th className="px-3 py-2 font-medium">Waktu</th>
                      <th className="px-2 py-2 font-medium">Artikel</th>
                      <th className="px-2 py-2 font-medium">Domain</th>
                      <th className="px-3 py-2 font-medium">Peran</th>
                    </tr>
                  </thead>
                  <tbody>
                    {docs.map((d, i) => {
                      const href = d.resolved_url || d.article_url || "#";
                      const domain = d.source_domain || domainOf(d.resolved_url) || d.source_name || "";
                      const role = i === 0 ? "Pertama" : d.syndicated_of ? "Sindikasi" : EVIDENCE_LABEL[d.evidence_type ?? ""] ?? "";
                      const roleClass = role === "Pertama" ? "text-accent" : role === "Independen" ? "text-good" : "text-muted";
                      return (
                        <tr key={d.article_id} className="border-b border-line align-top last:border-b-0">
                          <td className="whitespace-nowrap px-3 py-2 font-mono text-[11.5px] text-muted">{fmtDateTime(d.published_date)}</td>
                          <td className="px-2 py-2">
                            <a href={href} target="_blank" rel="noreferrer" className="font-semibold text-fg no-underline hover:text-accent">
                              {d.title ?? "(tanpa judul)"}
                            </a>
                            <div className="font-mono text-[11px] text-muted">
                              {d.target && d.target !== "UNKNOWN" ? `target ${d.target}` : ""}
                              {d.threat_actor && d.threat_actor !== "UNKNOWN" ? ` · pelaku ${d.threat_actor}` : ""}
                              {d.content_status === "ok" ? " · isi penuh" : d.content_status ? ` · isi ${d.content_status}` : ""}
                            </div>
                          </td>
                          <td className="px-2 py-2 text-soft">{domain || "-"}</td>
                          <td className={`whitespace-nowrap px-3 py-2 text-[11.5px] ${roleClass}`}>{role || "-"}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
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
            <div className="card flex flex-col gap-2 p-3.5 text-[12.5px]">
              <div className="flex justify-between gap-3">
                <span className="text-muted">Bukti disiapkan</span>
                <span className="font-mono">{fmtNum(docs.filter((d) => d.evidence_uid).length)} hash</span>
              </div>
              <div className="flex justify-between gap-3">
                <span className="text-muted">Isi penuh ter-hash</span>
                <span className="font-mono">{fmtNum(docs.filter((d) => d.content_sha256).length)} artikel</span>
              </div>
              {docs.find((d) => d.evidence_uid) ? (
                <div className="flex flex-col gap-1 border-t border-line pt-2">
                  <span className="text-muted">Contoh evidence_uid</span>
                  <span className="break-all font-mono text-[11.5px]">{docs.find((d) => d.evidence_uid)?.evidence_uid}</span>
                </div>
              ) : null}
              <span className="chip chip-chain mt-1 self-start">Pencatatan ke rantai: tahap berikutnya</span>
              <Link href={`/verifikasi?q=${encodeURIComponent(docs.find((d) => d.evidence_uid)?.evidence_uid ?? "")}`} className="text-[12.5px] no-underline">
                Verifikasi bukti incident ini
              </Link>
            </div>
          </div>

          <div>
            <SectionTitle>Atestasi lembaga</SectionTitle>
            <div className="card p-3.5 text-[13px] text-soft">
              Belum ada. Portal atestasi untuk BSSN, OJK, Komdigi, dan Polri dibuka pada tahap berikutnya.
            </div>
          </div>

          <div className="card flex flex-col gap-1 p-3.5 text-[12.5px]">
            <span className="text-muted">Ringkasan angka</span>
            <span>
              Terbaru {fmtDate(incident.last_published_date)} · {fmtNum(incident.document_count)} dokumen menurut V0.5
            </span>
            <span className="font-mono text-[11.5px] text-muted">{incident.incident_id}</span>
          </div>
        </section>
      </div>
    </div>
  );
}
