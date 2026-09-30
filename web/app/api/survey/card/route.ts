import { getSurveyCard } from "@/lib/queries";
import { formatters, incidentTitle } from "@/lib/format";
import { getDict, isLang } from "@/lib/i18n";
import { SURVEY_FIELDS } from "@/lib/survey";
import { pickSurveyIncident, surveyDisplay } from "@/lib/survey-pick";

/**
 * Satu kartu survei untuk pop-up: GET /api/survey/card?lang=id&exclude=ID1,ID2
 * Kartu dipilih seperti halaman /survey (jawaban tersedikit lebih dulu);
 * ``exclude`` untuk tombol "ganti berita lain".
 */
export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const params = new URL(request.url).searchParams;
  const lang = isLang(params.get("lang") ?? "") ? (params.get("lang") as "id" | "en") : "id";
  const exclude = (params.get("exclude") ?? "").split(",").filter((id) => /^[A-Za-z0-9_-]{1,64}$/.test(id)).slice(0, 50);
  const t = getDict(lang);
  const f = formatters(lang);
  const data = await getSurveyCard(await pickSurveyIncident(exclude));
  if (!data) return Response.json({ ok: false }, { status: 404, headers: { "Cache-Control": "no-store" } });
  return Response.json(
    {
      ok: true,
      incidentId: data.incidentId,
      outputId: Number(data.card.output_id),
      title: incidentTitle(data.title),
      documentCount: data.documentCount,
      articles: data.articles.slice(0, 2).map((a) => ({ title: incidentTitle(a.title), url: a.url, date: f.date(a.published_date) })),
      fields: SURVEY_FIELDS.map((key) => ({ key, label: t.flows.rows[key], value: surveyDisplay(key, data.card[key], lang) })),
    },
    { headers: { "Cache-Control": "no-store" } },
  );
}
