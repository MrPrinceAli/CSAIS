import { query } from "@/lib/db";
import { getPublisherDomains, getSurveyCard } from "@/lib/queries";
import { domainOf, formatters, incidentTitle, publisherOf } from "@/lib/format";
import { getDict, isLang } from "@/lib/i18n";
import { SURVEY_FIELDS } from "@/lib/survey";
import { pickSurveyIncident, surveyDisplay } from "@/lib/survey-pick";

/**
 * Satu kartu survei untuk pop-up: GET /api/survey/card?lang=id&exclude=ID1,ID2
 * Kartu dipilih seperti halaman /survey (jawaban tersedikit lebih dulu);
 * ``exclude`` untuk tombol "ganti berita lain".
 */
export const dynamic = "force-dynamic";

/** Domain media untuk logo (paling sering lebih dulu) dan jumlah penerbit berbeda satu incident. */
async function mediaOf(incidentId: string): Promise<{ logos: string[]; publishers: number }> {
  const [rows, publisherDomains] = await Promise.all([
    query<{ title: string | null; resolved_url: string | null }>(
      `SELECT a.title, a.resolved_url FROM v05_incident_documents d JOIN articles a ON a.article_id = d.article_id
       WHERE d.incident_id = ? LIMIT 80`,
      [incidentId],
    ),
    getPublisherDomains(),
  ]);
  const counts = new Map<string, number>();
  const names = new Set<string>();
  for (const row of rows) {
    const resolved = domainOf(row.resolved_url);
    const publisher = publisherOf(row.title);
    const domain = resolved && !resolved.includes("google.") ? resolved : publisherDomains[publisher.toLowerCase()] ?? "";
    names.add((publisher || domain).toLowerCase());
    if (domain) counts.set(domain, (counts.get(domain) ?? 0) + 1);
  }
  names.delete("");
  const logos = [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 3).map(([d]) => d);
  return { logos, publishers: names.size };
}

export async function GET(request: Request) {
  const params = new URL(request.url).searchParams;
  const lang = isLang(params.get("lang") ?? "") ? (params.get("lang") as "id" | "en") : "id";
  const exclude = (params.get("exclude") ?? "").split(",").filter((id) => /^[A-Za-z0-9_-]{1,64}$/.test(id)).slice(0, 50);
  const t = getDict(lang);
  const f = formatters(lang);
  const data = await getSurveyCard(await pickSurveyIncident(exclude));
  if (!data) return Response.json({ ok: false }, { status: 404, headers: { "Cache-Control": "no-store" } });
  const { logos, publishers } = await mediaOf(data.incidentId);
  return Response.json(
    {
      ok: true,
      incidentId: data.incidentId,
      outputId: Number(data.card.output_id),
      title: incidentTitle(data.title),
      documentCount: data.documentCount,
      articles: data.articles.slice(0, 2).map((a) => ({ title: incidentTitle(a.title), url: a.url, date: f.date(a.published_date) })),
      logos,
      publishers,
      fields: SURVEY_FIELDS.map((key) => ({ key, label: t.flows.rows[key], value: surveyDisplay(key, data.card[key], lang) })),
    },
    { headers: { "Cache-Control": "no-store" } },
  );
}
