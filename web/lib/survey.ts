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
