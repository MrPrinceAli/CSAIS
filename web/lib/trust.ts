/**
 * Indeks kepercayaan awal (0..1) dari sinyal yang sudah ada di pipeline.
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
export type Trust = { score: number; level: TrustLevel; parts: TrustPart[] };

const W: Record<TrustPartKey, number> = { corroboration: 0.3, independence: 0.3, claim: 0.2, content: 0.1, clustering: 0.1 };

export function trustScore(t: TrustInput): Trust {
  const independence = t.docs >= 2 ? Math.min(1, Math.max(0, t.independence ?? 0)) : 0.35;
  const corroboration = Math.min(1, Math.max(0, (t.domains - 1) / 4));
  const claim = Math.min(1, Math.max(0, t.targetConfidence));
  const content = Math.min(1, Math.max(0, t.contentShare));
  const clustering = Math.min(1, Math.max(0, t.clustering));
  const parts: TrustPart[] = [
    { key: "corroboration", value: corroboration, weight: W.corroboration },
    { key: "independence", value: independence, weight: W.independence },
    { key: "claim", value: claim, weight: W.claim },
    { key: "content", value: content, weight: W.content },
    { key: "clustering", value: clustering, weight: W.clustering },
  ];
  const score = parts.reduce((acc, p) => acc + p.value * p.weight, 0);
  const level: TrustLevel = score >= 0.72 ? "tinggi" : score >= 0.45 ? "sedang" : "rendah";
  return { score, level, parts };
}

/** Versi ringkas untuk baris tabel (tanpa daftar dokumen). */
export function trustFromRow(row: {
  independence: number | null;
  domains: number | bigint | null;
  document_count: number | bigint;
  incident_confidence: number;
  target: string | null;
}): Trust {
  return trustScore({
    independence: row.independence,
    domains: Number(row.domains ?? 0),
    docs: Number(row.document_count),
    targetConfidence: row.target ? 0.8 : 0,
    contentShare: 0.5,
    clustering: Number(row.incident_confidence),
  });
}

export const TRUST_COLOR: Record<TrustLevel, string> = {
  tinggi: "var(--good)",
  sedang: "var(--med)",
  rendah: "var(--high)",
};
