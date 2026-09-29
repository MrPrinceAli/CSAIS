import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getSurveyCandidates, getSurveyCard } from "@/lib/queries";
import { formatters, incidentTitle } from "@/lib/format";
import { attackLabel, getDict, isLang, L } from "@/lib/i18n";
import { submissionCounts, SURVEY_FIELDS } from "@/lib/survey";
import { SurveyForm, type SurveyFieldView } from "@/components/survey-form";

type Params = { lang: string };
type Search = { id?: string };

export async function generateMetadata({ params }: { params: Promise<Params> }): Promise<Metadata> {
  const { lang } = await params;
  return { title: getDict(isLang(lang) ? lang : "id").survey.title };
}

function display(field: string, value: string | null, lang: "id" | "en"): string | null {
  if (!value) return null;
  if (field === "attack_type") return [...new Set(value.split(",").map((v) => attackLabel(v, lang)))].join(", ");
  if (field === "location") return value.split(",").map((v) => v.trim().replace(/^./, (c) => c.toUpperCase())).join(", ");
  return value;
}

const LEAST_POOL = 30;

/** Kartu yang paling sedikit dinilai didahulukan: acak di antara 30 calon dengan jawaban tersedikit. */
async function pickCandidate(): Promise<string> {
  const ids = await getSurveyCandidates();
  const counts = await submissionCounts(ids);
  const pool = [...ids].sort((a, b) => (counts.get(a) ?? 0) - (counts.get(b) ?? 0)).slice(0, LEAST_POOL);
  return pool[Math.floor(Math.random() * pool.length)] ?? "";
}

/** Survei publik (alur D2): satu kartu inti D1 per halaman, dinilai terhadap beritanya. */
export default async function SurveyPage({ params, searchParams }: { params: Promise<Params>; searchParams: Promise<Search> }) {
  const { lang } = await params;
  if (!isLang(lang)) notFound();
  const { id } = await searchParams;
  const t = getDict(lang);
  const f = formatters(lang);
  const requested = typeof id === "string" && /^[A-Za-z0-9_-]{1,64}$/.test(id) ? id : null;
  const data = await getSurveyCard(requested ?? (await pickCandidate()));

  const fields: SurveyFieldView[] = data
    ? SURVEY_FIELDS.map((key) => ({ key, label: t.flows.rows[key], value: display(key, data.card[key], lang) }))
    : [];

  return (
    <div className="mx-auto flex w-full max-w-[860px] flex-col gap-5 py-8">
      <header className="flex flex-col gap-2">
        <span className="label text-med">D2 · {t.survey.title}</span>
        <h1 className="text-balance text-[26px] font-semibold leading-tight">{data ? incidentTitle(data.title) : t.survey.title}</h1>
        <p className="max-w-[68ch] text-[14px] leading-relaxed text-soft">{t.survey.lead}</p>
      </header>

      {data ? (
        <>
          <section className="card flex flex-col gap-2 p-4">
            <span className="label">{t.survey.read}</span>
            <ol className="flex flex-col gap-1.5 text-[14px]">
              {data.articles.map((a, i) => (
                <li key={`${a.url}-${i}`} className="flex flex-wrap items-baseline gap-x-2">
                  <span className="font-mono text-[12px] text-muted">{f.date(a.published_date)}</span>
                  {a.url ? (
                    <a href={a.url} target="_blank" rel="noreferrer">
                      {incidentTitle(a.title)}
                    </a>
                  ) : (
                    <span>{incidentTitle(a.title)}</span>
                  )}
                </li>
              ))}
            </ol>
            {data.documentCount > data.articles.length ? <span className="text-[12px] text-muted">{t.survey.more(f.num(data.documentCount - data.articles.length))}</span> : null}
          </section>

          <section className="flex flex-col gap-2">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h2 className="label">{t.survey.card}</h2>
              <Link href={L(lang, `/incidents/${data.incidentId}`)} className="text-[12.5px]">
                {t.survey.openIncident}
              </Link>
            </div>
            <SurveyForm
              key={data.card.output_id}
              lang={lang}
              incidentId={data.incidentId}
              outputId={data.card.output_id}
              fields={fields}
              nextHref={L(lang, "/survey")}
              strings={{
                answers: t.survey.answers,
                submit: t.survey.submit,
                sending: t.survey.sending,
                chooseOne: t.survey.chooseOne,
                thanks: t.survey.thanks,
                next: t.survey.next,
                failed: t.survey.failed,
                unknown: t.common.unknown,
              }}
            />
            <p className="text-[12px] text-muted">{t.survey.rule}</p>
            <p className="text-[12px] text-muted">{t.survey.privacy}</p>
          </section>
        </>
      ) : (
        <p className="card p-5 text-[14px] text-soft">{t.survey.unavailable}</p>
      )}
    </div>
  );
}
