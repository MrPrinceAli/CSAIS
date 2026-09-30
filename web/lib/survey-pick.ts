/**
 * Pemilihan dan tampilan kartu survei (alur D2), dipakai halaman /survey dan
 * pop-up survei. Hanya untuk server.
 */
import { attackLabel, type Lang } from "./i18n";
import { getSurveyCandidates } from "./queries";
import { submissionCounts } from "./survey";

const LEAST_POOL = 30;

/** Teks tampilan satu kolom kartu. */
export function surveyDisplay(field: string, value: string | null, lang: Lang): string | null {
  if (!value) return null;
  if (field === "attack_type") return [...new Set(value.split(",").map((v) => attackLabel(v, lang)))].join(", ");
  if (field === "location") return value.split(",").map((v) => v.trim().replace(/^./, (c) => c.toUpperCase())).join(", ");
  return value;
}

/** Kartu yang paling sedikit dinilai didahulukan: acak di antara 30 calon dengan jawaban tersedikit. */
export async function pickSurveyIncident(exclude: string[] = []): Promise<string> {
  const skip = new Set(exclude);
  const ids = (await getSurveyCandidates()).filter((id) => !skip.has(id));
  const counts = await submissionCounts(ids);
  const pool = [...ids].sort((a, b) => (counts.get(a) ?? 0) - (counts.get(b) ?? 0)).slice(0, LEAST_POOL);
  return pool[Math.floor(Math.random() * pool.length)] ?? "";
}
