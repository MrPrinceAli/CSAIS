import { queryOne } from "@/lib/db";
import { institutionFromSession, REASONS, REVIEW_FIELDS, REVIEW_STATUSES, SESSION_COOKIE_NAME, type ReviewStatus } from "@/lib/portal";
import { saveReview, surveyConfigured } from "@/lib/survey";

/**
 * Simpan keputusan lembaga untuk satu kartu inti D1. Lembaga diambil dari
 * cookie sesi (bukan dari isi permintaan), kartu diperiksa ke flow_outputs.
 */
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
  const inst = institutionFromSession(cookieValue(request, SESSION_COOKIE_NAME));
  if (!inst) return bad("not-signed-in", 401);
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
  const note = typeof body.note === "string" ? body.note.trim().slice(0, 600) || null : null;
  const source = typeof body.source_url === "string" && /^https?:\/\/\S{3,500}$/.test(body.source_url.trim()) ? body.source_url.trim() : null;
  const reviewer = typeof body.reviewer === "string" ? body.reviewer.trim().slice(0, 80) || null : null;

  const card = await queryOne<{ output_id: number }>(
    `SELECT output_id FROM flow_outputs WHERE output_id = ? AND incident_id = ? AND flow = 'D1'`,
    [outputId, incidentId],
  );
  if (!card) return bad("unknown-card", 404);

  try {
    const reviewId = await saveReview({
      incidentId,
      cardOutputId: outputId,
      institution: inst,
      status,
      reasonCode: reason,
      reasonText: note,
      fieldStatus,
      sourceUrl: source,
      reviewer,
    });
    return Response.json({ ok: true, review_id: reviewId });
  } catch (error) {
    console.error("portal: gagal menyimpan keputusan", error);
    return bad("save-failed", 500);
  }
}
