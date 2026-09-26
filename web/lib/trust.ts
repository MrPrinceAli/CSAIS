/**
 * Indeks kepercayaan awal (0..1) dari sinyal yang sudah ada di pipeline.
 * Sejak V0.7 skor dihitung di pipeline dan disimpan di tabel v07_trust
 * (csais/v07_trust_score.py); rumus di sini harus tetap sama dan hanya
 * dipakai sebagai cadangan bila tabel itu belum diterbitkan.
 * Bukan indeks Step 3 (yang akan memakai riwayat sumber dan atestasi
 * lembaga); dipakai agar incident yang dikuatkan banyak sumber dapat
 * dibedakan dari yang hanya satu artikel.
 */
export type TrustInput = {
  independence: number | null; // rata-rata evidence_independence_score (V0.6)
  domains: number; // jumlah domain sumber berbeda
  docs: number; // jumlah artikel
  targetConfidence: number; // keyakinan field target (V0.3), 0 bila tidak ada
  contentShare: number; // porsi artikel dengan teks penuh
  clustering: number; // incident_confidence (V0.5)
};

export type TrustPartKey = "corroboration" | "independence" | "claim" | "content" | "clustering";
export type TrustPart = { key: TrustPartKey; value: number; weight: number };
export type TrustLevel = "tinggi" | "sedang" | "rendah";
export type TrustSource = "pipeline" | "web";
export type Trust = { score: number; level: TrustLevel; parts: TrustPart[]; source: TrustSource };

const W: Record<TrustPartKey, number> = { corroboration: 0.3, independence: 0.3, claim: 0.2, content: 0.1, clustering: 0.1 };
const KEYS: TrustPartKey[] = ["corroboration", "independence", "claim", "content", "clustering"];

function levelOf(score: number): TrustLevel {
  return score >= 0.72 ? "tinggi" : score >= 0.45 ? "sedang" : "rendah";
}

export function trustScore(t: TrustInput): Trust {
  const independence = t.docs >= 2 ? Math.min(1, Math.max(0, t.independence ?? 0)) : 0.35;
  const corroboration = Math.min(1, Math.max(0, (t.domains - 1) / 4));
  const claim = Math.min(1, Math.max(0, t.targetConfidence));
  const content = Math.min(1, Math.max(0, t.contentShare));
  const clustering = Math.min(1, Math.max(0, t.clustering));
  const values: Record<TrustPartKey, number> = { corroboration, independence, claim, content, clustering };
  const parts: TrustPart[] = KEYS.map((key) => ({ key, value: values[key], weight: W[key] }));
  const score = parts.reduce((acc, p) => acc + p.value * p.weight, 0);
  return { score, level: levelOf(score), parts, source: "web" };
}

/** Kolom v07_trust yang ikut di baris incident (null bila tabel belum ada). */
export type StoredTrust = {
  trust_score: number | null;
  trust_level: string | null;
  trust_corroboration: number | null;
  trust_independence: number | null;
  trust_claim: number | null;
  trust_content: number | null;
  trust_clustering: number | null;
};

/** Skor hasil pipeline bila tersimpan; null bila incident belum dinilai V0.7. */
export function trustFromStored(row: Partial<StoredTrust>): Trust | null {
  if (row.trust_score === null || row.trust_score === undefined) return null;
  const score = Number(row.trust_score);
  const values: Record<TrustPartKey, number> = {
    corroboration: Number(row.trust_corroboration ?? 0),
    independence: Number(row.trust_independence ?? 0),
    claim: Number(row.trust_claim ?? 0),
    content: Number(row.trust_content ?? 0),
    clustering: Number(row.trust_clustering ?? 0),
  };
  const level = (row.trust_level as TrustLevel | null) ?? levelOf(score);
  return { score, level, parts: KEYS.map((key) => ({ key, value: values[key], weight: W[key] })), source: "pipeline" };
}

/** Versi ringkas untuk baris tabel: skor pipeline bila ada, selain itu perkiraan dari kolom baris. */
export function trustFromRow(
  row: {
    independence: number | null;
    domains: number | bigint | null;
    document_count: number | bigint;
    incident_confidence: number;
    target: string | null;
  } & Partial<StoredTrust>,
): Trust {
  return (
    trustFromStored(row) ??
    trustScore({
      independence: row.independence,
      domains: Number(row.domains ?? 0),
      docs: Number(row.document_count),
      targetConfidence: row.target ? 0.8 : 0,
      contentShare: 0.5,
      clustering: Number(row.incident_confidence),
    })
  );
}

export const TRUST_COLOR: Record<TrustLevel, string> = {
  tinggi: "var(--good)",
  sedang: "var(--med)",
  rendah: "var(--high)",
};
