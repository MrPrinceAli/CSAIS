/**
 * Penyimpanan jawaban survei publik (alur D2) di database Turso terpisah.
 * Hanya dipakai di server (route /api/survey); tokennya boleh menulis, tetapi
 * hanya ke database survei, bukan ke database utama pipeline. Skema tabel sama
 * dengan SURVEY_SCHEMA di csais/survey.py, yang membaca jawaban ini setiap hari.
 *
 *   SURVEY_DATABASE_URL  libsql://csais-survey-nama.turso.io, atau file:/path.db
 *   SURVEY_AUTH_TOKEN    token tulis (tidak perlu untuk file:)
 *   SURVEY_SALT          garam untuk hash alamat IP
 */
import { createHash } from "node:crypto";
import { createClient } from "@libsql/client";

export const SURVEY_FIELDS = ["attack_type", "target", "threat_actor", "attack_date", "location"] as const;
export type SurveyField = (typeof SURVEY_FIELDS)[number];
export const SURVEY_ANSWERS = ["sesuai", "tidak_sesuai", "tidak_tahu"] as const;
export type SurveyAnswer = (typeof SURVEY_ANSWERS)[number];

const SCHEMA = `
  CREATE TABLE IF NOT EXISTS survey_responses (
    response_id INTEGER PRIMARY KEY AUTOINCREMENT,
    submission_id TEXT NOT NULL,
    incident_id TEXT NOT NULL,
    card_output_id INTEGER NOT NULL,
    field TEXT NOT NULL,
    shown_value TEXT,
    answer TEXT NOT NULL CHECK (answer IN ('sesuai', 'tidak_sesuai', 'tidak_tahu')),
    respondent TEXT,
    ip_hash TEXT,
    lang TEXT,
    created_at TEXT NOT NULL
  )`;

const url = (process.env.SURVEY_DATABASE_URL ?? "").replace(/^libsql:\/\//, "https://");
const authToken = process.env.SURVEY_AUTH_TOKEN;
const isLocalFile = url.startsWith("file:");

let client: ReturnType<typeof createClient> | null = null;
let ready: Promise<unknown> | null = null;

export function surveyConfigured(): boolean {
  return Boolean(url && (authToken || isLocalFile));
}

function getClient() {
  if (!client) {
    if (!surveyConfigured()) throw new Error("SURVEY_DATABASE_URL dan SURVEY_AUTH_TOKEN belum diisi.");
    client = isLocalFile ? createClient({ url }) : createClient({ url, authToken });
    ready = client.execute(SCHEMA).catch((error: unknown) => {
      client = null; // coba lagi pada permintaan berikutnya
      throw error;
    });
  }
  return client;
}

/** Hash alamat IP bergaram; alamatnya sendiri tidak disimpan. */
export function hashIp(ip: string): string | null {
  if (!ip) return null;
  return createHash("sha256")
    .update(`${process.env.SURVEY_SALT ?? ""}|${ip}`)
    .digest("hex")
    .slice(0, 24);
}

export type SurveySubmission = {
  incidentId: string;
  cardOutputId: number;
  answers: { field: SurveyField; shownValue: string | null; answer: SurveyAnswer }[];
  respondent: string | null;
  ipHash: string | null;
  lang: string;
};

/** Simpan satu kiriman (beberapa kolom) dalam satu transaksi. */
export async function saveSubmission(s: SurveySubmission): Promise<string> {
  const db = getClient();
  await ready;
  const submissionId = crypto.randomUUID();
  const createdAt = new Date().toISOString();
  await db.batch(
    s.answers.map((a) => ({
      sql: `INSERT INTO survey_responses (submission_id, incident_id, card_output_id, field, shown_value, answer, respondent, ip_hash, lang, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      args: [submissionId, s.incidentId, s.cardOutputId, a.field, a.shownValue, a.answer, s.respondent, s.ipHash, s.lang, createdAt],
    })),
    "write",
  );
  return submissionId;
}

/** Jumlah kiriman per incident untuk daftar id; kosong bila survei belum dikonfigurasi atau gagal dibaca. */
export async function submissionCounts(ids: string[]): Promise<Map<string, number>> {
  const counts = new Map<string, number>();
  if (!ids.length || !surveyConfigured()) return counts;
  try {
    const db = getClient();
    await ready;
    const result = await db.execute({
      sql: `SELECT incident_id, COUNT(DISTINCT submission_id) AS n FROM survey_responses
            WHERE incident_id IN (${ids.map(() => "?").join(", ")}) GROUP BY incident_id`,
      args: ids,
    });
    for (const row of result.rows) counts.set(String(row.incident_id), Number(row.n));
  } catch (error) {
    console.error("survey: gagal membaca jumlah jawaban", error);
  }
  return counts;
}

// --- Keputusan lembaga (alur D3, portal) ---
// Skema sama dengan REVIEWS_SCHEMA di csais/official.py, yang membacanya setiap hari.
const REVIEWS_SCHEMA = `
  CREATE TABLE IF NOT EXISTS official_reviews (
    review_id INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_id TEXT NOT NULL,
    card_output_id INTEGER NOT NULL,
    institution TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('dikonfirmasi', 'dibantah', 'sebagian')),
    reason_code TEXT NOT NULL,
    reason_text TEXT,
    field_status TEXT,
    source_url TEXT,
    reviewer TEXT,
    created_at TEXT NOT NULL,
    signer TEXT,
    signature TEXT,
    signed TEXT
  )`;
// Kolom tanda tangan ditambahkan setelah tabel pertama dibuat
const REVIEWS_COLUMNS = ["signer TEXT", "signature TEXT", "signed TEXT"];

let reviewsReady: Promise<unknown> | null = null;

async function reviewsClient() {
  const db = getClient();
  await ready;
  if (!reviewsReady) {
    reviewsReady = db
      .execute(REVIEWS_SCHEMA)
      .then(async () => {
        const info = await db.execute("PRAGMA table_info(official_reviews)");
        const have = new Set(info.rows.map((r) => String(r.name)));
        for (const column of REVIEWS_COLUMNS) {
          if (!have.has(column.split(" ")[0])) await db.execute(`ALTER TABLE official_reviews ADD COLUMN ${column}`);
        }
      })
      .catch((error: unknown) => {
      reviewsReady = null;
      throw error;
    });
  }
  await reviewsReady;
  return db;
}

export type OfficialReview = {
  signed: import("./attestation").SignedDecision;
  incidentId: string;
  cardOutputId: number;
  institution: string;
  status: string;
  reasonCode: string;
  reasonText: string | null;
  fieldStatus: Record<string, string>;
  sourceUrl: string | null;
  reviewer: string | null;
};

export async function saveReview(r: OfficialReview): Promise<number> {
  const db = await reviewsClient();
  const result = await db.execute({
    sql: `INSERT INTO official_reviews (incident_id, card_output_id, institution, status, reason_code, reason_text, field_status, source_url, reviewer, created_at, signer, signature, signed)
          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
    args: [
      r.incidentId, r.cardOutputId, r.institution, r.status, r.reasonCode, r.reasonText, JSON.stringify(r.fieldStatus), r.sourceUrl, r.reviewer,
      new Date().toISOString(), r.signed.signer, r.signed.signature, JSON.stringify(r.signed),
    ],
  });
  return Number(result.lastInsertRowid ?? 0);
}

/** Keputusan terakhir satu lembaga per incident: incident_id -> {status, created_at}. */
export async function reviewsBy(institution: string): Promise<Map<string, { status: string; created_at: string }>> {
  const out = new Map<string, { status: string; created_at: string }>();
  if (!surveyConfigured()) return out;
  try {
    const db = await reviewsClient();
    const result = await db.execute({
      sql: `SELECT incident_id, status, created_at FROM official_reviews WHERE institution = ? ORDER BY review_id`,
      args: [institution],
    });
    for (const row of result.rows) out.set(String(row.incident_id), { status: String(row.status), created_at: String(row.created_at) });
  } catch (error) {
    console.error("portal: gagal membaca keputusan", error);
  }
  return out;
}
