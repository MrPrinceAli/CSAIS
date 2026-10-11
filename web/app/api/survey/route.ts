import { queryOne } from "@/lib/db";
import { CORRECTION_MAX, hashIp, saveSubmission, SURVEY_ANSWERS, SURVEY_FIELDS, surveyConfigured, VERDICT_FIELD, type SurveyAnswer, type SurveyField } from "@/lib/survey";

/**
 * Terima jawaban survei publik (alur D2) untuk satu kartu inti D1. Nilai kolom
 * yang dinilai diambil dari flow_outputs di server, bukan dari klien, sehingga
 * jawaban selalu tertaut ke kartu yang benar-benar ditampilkan. Kolom yang
 * dijawab tidak sesuai boleh membawa koreksi (nilai yang benar menurut berita),
 * dan ada satu pertanyaan kesimpulan ("benar terjadi?"). Untuk sementara
 * satu orang boleh menjawab berkali-kali; hanya ada batas laju kasar per IP.
 */
export const dynamic = "force-dynamic";

const WINDOW_MS = 60_000;
const MAX_PER_WINDOW = 20;
const hits = new Map<string, number[]>();

function limited(key: string): boolean {
  const now = Date.now();
  const recent = (hits.get(key) ?? []).filter((t) => now - t < WINDOW_MS);
  recent.push(now);
  hits.set(key, recent);
  if (hits.size > 5000) hits.clear();
  return recent.length > MAX_PER_WINDOW;
}

type Card = Record<SurveyField, string | null> & { output_id: number };

function bad(message: string, status = 400) {
  return Response.json({ ok: false, error: message }, { status });
}

export async function POST(request: Request) {
  if (!surveyConfigured()) return bad("survey-unavailable", 503);
  const ip = (request.headers.get("x-forwarded-for") ?? "").split(",")[0].trim();
  if (limited(ip || "unknown")) return bad("too-many-requests", 429);

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return bad("invalid-json");
  }
  const input = (body ?? {}) as { incident_id?: unknown; output_id?: unknown; answers?: unknown; corrections?: unknown; respondent?: unknown; lang?: unknown };
  const incidentId = typeof input.incident_id === "string" && /^[A-Za-z0-9_-]{1,64}$/.test(input.incident_id) ? input.incident_id : null;
  const outputId = Number.isInteger(input.output_id) ? (input.output_id as number) : null;
  const respondent = typeof input.respondent === "string" && /^[A-Za-z0-9-]{8,64}$/.test(input.respondent) ? input.respondent : null;
  const lang = input.lang === "en" ? "en" : "id";
  if (!incidentId || outputId === null) return bad("invalid-card");

  const raw = input.answers && typeof input.answers === "object" ? (input.answers as Record<string, unknown>) : {};
  const chosen = SURVEY_FIELDS.filter((f) => SURVEY_ANSWERS.includes(raw[f] as SurveyAnswer));
  const verdict = SURVEY_ANSWERS.includes(raw[VERDICT_FIELD] as SurveyAnswer) ? (raw[VERDICT_FIELD] as SurveyAnswer) : null;
  if (!chosen.length && !verdict) return bad("no-answers");
  const rawCorrections = input.corrections && typeof input.corrections === "object" ? (input.corrections as Record<string, unknown>) : {};
  const correctionOf = (field: SurveyField): string | null => {
    const value = rawCorrections[field];
    if (raw[field] !== "tidak_sesuai" || typeof value !== "string") return null;
    return value.replace(/\s+/g, " ").trim().slice(0, CORRECTION_MAX) || null;
  };

  const card = await queryOne<Card>(
    `SELECT output_id, attack_type, target, threat_actor, attack_date, location
     FROM flow_outputs WHERE output_id = ? AND incident_id = ? AND flow = 'D1'`,
    [outputId, incidentId],
  );
  if (!card) return bad("unknown-card", 404);

  try {
    const submission = await saveSubmission({
      incidentId,
      cardOutputId: outputId,
      answers: [
        ...chosen.map((field) => ({ field, shownValue: card[field] ?? null, answer: raw[field] as SurveyAnswer, correctedValue: correctionOf(field) })),
        ...(verdict ? [{ field: VERDICT_FIELD, shownValue: null, answer: verdict, correctedValue: null }] : []),
      ],
      respondent,
      ipHash: hashIp(ip),
      lang,
    });
    return Response.json({ ok: true, submission, saved: chosen.length + (verdict ? 1 : 0) });
  } catch (error) {
    console.error("survey: gagal menyimpan", error);
    return bad("save-failed", 500);
  }
}
