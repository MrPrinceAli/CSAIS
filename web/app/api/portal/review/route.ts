import { queryOne } from "@/lib/db";
import { signDecision } from "@/lib/attestation";
import { institutionFromSession, KEY_COOKIE_NAME, keyFromSession, REASONS, REVIEW_FIELDS, REVIEW_STATUSES, SESSION_COOKIE_NAME, type ReviewStatus } from "@/lib/portal";
import { AUDIENCE_KEYS, tipText, TOPIC_KEYS } from "@/lib/prevention";
import { CORRECTION_MAX, saveReview, surveyConfigured } from "@/lib/survey";

/**
 * Simpan keputusan lembaga untuk satu kartu inti D1. Lembaga diambil dari
 * cookie sesi (bukan dari isi permintaan), kartu diperiksa ke flow_outputs, dan
 * keputusan ditandatangani (EIP-712) dengan kunci lembaga dari cookie kunci.
 * Kolom yang ditandai salah boleh membawa nilai yang benar, dan lembaga boleh
 * memilih langkah pencegahan, sasaran literasi, dan materi literasi sendiri;
 * semuanya ikut ditandatangani (``fields``).
 */
const MAX_STEPS = 12;
export const dynamic = "force-dynamic";

function bad(error: string, status = 400) {
  return Response.json({ ok: false, error }, { status });
}

function cookieValue(request: Request, name: string): string | undefined {
  const header = request.headers.get("cookie") ?? "";
  for (const part of header.split(";")) {
    const [key, ...rest] = part.trim().split("=");
    if (key === name) return rest.join("=");
  }
  return undefined;
}

export async function POST(request: Request) {
  const session = cookieValue(request, SESSION_COOKIE_NAME);
  const inst = institutionFromSession(session);
  const privateKey = keyFromSession(session, cookieValue(request, KEY_COOKIE_NAME));
  if (!inst || !privateKey) return bad("not-signed-in", 401);
  if (!surveyConfigured()) return bad("storage-unavailable", 503);

  let body: Record<string, unknown>;
  try {
    body = (await request.json()) as Record<string, unknown>;
  } catch {
    return bad("invalid-json");
  }
  const incidentId = typeof body.incident_id === "string" && /^[A-Za-z0-9_-]{1,64}$/.test(body.incident_id) ? body.incident_id : null;
  const outputId = Number.isInteger(body.output_id) ? (body.output_id as number) : null;
  const status = REVIEW_STATUSES.includes(body.status as ReviewStatus) ? (body.status as ReviewStatus) : null;
  if (!incidentId || outputId === null || !status) return bad("invalid-review");
  const reason = typeof body.reason === "string" && REASONS[status].includes(body.reason) ? body.reason : null;
  if (!reason) return bad("reason-required");

  const rawFields = body.fields && typeof body.fields === "object" ? (body.fields as Record<string, unknown>) : {};
  const fieldStatus: Record<string, string> = {};
  for (const field of REVIEW_FIELDS) {
    if (rawFields[field] === "benar") fieldStatus[field] = "dikonfirmasi";
    if (rawFields[field] === "salah") fieldStatus[field] = "dibantah";
  }
  const rawCorrections = body.corrections && typeof body.corrections === "object" ? (body.corrections as Record<string, unknown>) : {};
  const corrections: Record<string, string> = {};
  for (const field of REVIEW_FIELDS) {
    const value = rawCorrections[field];
    if (fieldStatus[field] !== "dibantah" || typeof value !== "string") continue;
    const clean = value.replace(/\s+/g, " ").trim().slice(0, CORRECTION_MAX);
    if (clean) corrections[field] = clean;
  }
  const rawSteps = Array.isArray(body.prevention) ? body.prevention : [];
  const preventionKeys = [...new Set(rawSteps.filter((k): k is string => typeof k === "string" && tipText(k, "id") !== null))].slice(0, MAX_STEPS);
  const preventionText = typeof body.prevention_text === "string" ? body.prevention_text.trim().slice(0, 600) || null : null;
  const rawLiteracy = body.literacy && typeof body.literacy === "object" ? (body.literacy as Record<string, unknown>) : {};
  const pick = (value: unknown, allowed: string[]) =>
    [...new Set(Array.isArray(value) ? value.filter((k): k is string => typeof k === "string" && allowed.includes(k)) : [])].slice(0, MAX_STEPS);
  const literacy = { audience: pick(rawLiteracy.audience, AUDIENCE_KEYS), topics: pick(rawLiteracy.topics, TOPIC_KEYS) };
  const note = typeof body.note === "string" ? body.note.trim().slice(0, 600) || null : null;
  const source = typeof body.source_url === "string" && /^https?:\/\/\S{3,500}$/.test(body.source_url.trim()) ? body.source_url.trim() : null;
  const reviewer = typeof body.reviewer === "string" ? body.reviewer.trim().slice(0, 80) || null : null;

  const card = await queryOne<{ output_id: number; output_hash: string }>(
    `SELECT output_id, output_hash FROM flow_outputs WHERE output_id = ? AND incident_id = ? AND flow = 'D1'`,
    [outputId, incidentId],
  );
  if (!card) return bad("unknown-card", 404);

  try {
    const signed = await signDecision(privateKey, {
      incidentId,
      cardHash: `0x${card.output_hash}`,
      institution: inst,
      status,
      reason,
      fields: JSON.stringify({ status: fieldStatus, values: corrections, prevention: preventionKeys, prevention_text: preventionText ?? "", literacy }),
      note: note ?? "",
      source: source ?? "",
      issuedAt: Math.floor(Date.now() / 1000),
    });
    const reviewId = await saveReview({
      signed,
      incidentId,
      cardOutputId: outputId,
      institution: inst,
      status,
      reasonCode: reason,
      reasonText: note,
      fieldStatus,
      corrections,
      preventionKeys,
      preventionText,
      literacy,
      sourceUrl: source,
      reviewer,
    });
    return Response.json({ ok: true, review_id: reviewId });
  } catch (error) {
    console.error("portal: gagal menyimpan keputusan", error);
    return bad("save-failed", 500);
  }
}
