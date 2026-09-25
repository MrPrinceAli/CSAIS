import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getSampleEvidence, verify } from "@/lib/queries";
import { formatters } from "@/lib/format";
import { evidenceRole, getDict, isLang, L } from "@/lib/i18n";
import { HashGrid } from "@/components/ui";

type Search = Record<string, string | string[] | undefined>;

export async function generateMetadata({ params }: { params: Promise<{ lang: string }> }): Promise<Metadata> {
  const { lang } = await params;
  return { title: getDict(isLang(lang) ? lang : "id").verify.title };
}

export default async function VerifyPage({ params, searchParams }: { params: Promise<{ lang: string }>; searchParams: Promise<Search> }) {
  const { lang } = await params;
  if (!isLang(lang)) notFound();
  const t = getDict(lang);
  const f = formatters(lang);
  const sp = await searchParams;
  const raw = Array.isArray(sp.q) ? sp.q[0] : sp.q;
  const input = (raw ?? "").trim().slice(0, 600);
  const [result, samples] = await Promise.all([input ? verify(input) : Promise.resolve(null), getSampleEvidence()]);
  const base = L(lang, "/verify");

  return (
    <div className="flex flex-col gap-6">
      <section className="grid gap-6 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,0.8fr)]">
        <div className="flex flex-col gap-3">
          <h1 className="text-balance text-[26px] font-semibold leading-tight">{t.verify.title}</h1>
          <p className="max-w-[70ch] text-[14.5px] leading-relaxed text-soft">{t.verify.lead}</p>
          <form method="get" action={base} className="flex w-full flex-col gap-2 sm:flex-row">
            <label htmlFor="q" className="sr-only">
              {t.verify.placeholder}
            </label>
            <input id="q" name="q" type="text" defaultValue={input} placeholder={t.verify.placeholder} className="field flex-1 py-2.5 font-mono text-[12.5px]" />
            <button type="submit" className="btn btn-primary justify-center">
              {t.verify.button}
            </button>
          </form>
          {!input && samples.length ? (
            <div className="flex flex-wrap items-center gap-2 text-[12.5px] text-muted">
              <span>{t.verify.sampleLabel}:</span>
              {samples.map((s) => (
                <Link key={s.evidence_uid} href={`${base}?q=${s.evidence_uid}`} className="chip chip-accent no-underline">
                  {s.evidence_uid}
                </Link>
              ))}
            </div>
          ) : null}
        </div>
        <div className="card grid grid-cols-[auto_minmax(0,1fr)] items-center gap-4 p-4">
          <HashGrid hex={result?.article?.content_sha256 ?? samples[0]?.content_sha256 ?? null} size={112} label={t.verify.fingerprintTitle} />
          <div className="flex flex-col gap-1 text-[12.5px] text-soft">
            <span className="label">{t.verify.fingerprintTitle}</span>
            <span className="leading-relaxed">{t.verify.fingerprintText}</span>
          </div>
        </div>
      </section>

      {result ? (
        result.article ? (
          <section className="card flex flex-col gap-4 p-5">
            <div className="flex items-start gap-3">
              <span className="mt-0.5 inline-flex h-8 w-8 flex-none items-center justify-center rounded-full bg-good" aria-hidden="true">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#0f1720" strokeWidth="3">
                  <path d="M5 12l5 5L20 7" />
                </svg>
              </span>
              <div className="flex flex-col">
                <span className="text-[16px] font-semibold">{t.verify.found}</span>
                <span className="text-[12.5px] text-muted">
                  {t.verify.matchedBy[result.kind === "hash" ? "hash" : result.kind === "url" ? "url" : "uid"]}{" "}
                  {result.article.content_fetched_at ? t.verify.fetchedAt(f.dateTime(result.article.content_fetched_at)) : t.verify.noContent}
                </span>
              </div>
            </div>
            <div className="grid gap-4 md:grid-cols-[auto_minmax(0,1fr)]">
              <HashGrid hex={result.article.content_sha256 ?? result.evidence[0]?.content_fingerprint} size={128} label={t.verify.fingerprintTitle} />
              <dl className="grid grid-cols-[130px_minmax(0,1fr)] gap-x-4 gap-y-2 text-[13px]">
                <dt className="text-muted">{t.verify.fields.article}</dt>
                <dd>
                  <a href={result.article.resolved_url ?? result.article.article_url ?? "#"} target="_blank" rel="noreferrer" className="no-underline">
                    {result.article.title ?? "—"}
                  </a>
                </dd>
                <dt className="text-muted">{t.verify.fields.published}</dt>
                <dd>{f.dateTime(result.article.published_date)}</dd>
                <dt className="text-muted">{t.verify.fields.uid}</dt>
                <dd className="break-all font-mono">{result.article.article_uid ?? "—"}</dd>
                <dt className="text-muted">{t.verify.fields.sha}</dt>
                <dd className="break-all font-mono">{result.article.content_sha256 ?? t.verify.noSha}</dd>
                {result.evidence.map((e) => (
                  <div key={e.evidence_uid} className="contents">
                    <dt className="text-muted">{t.verify.fields.evidence}</dt>
                    <dd className="flex flex-wrap items-center gap-2">
                      <span className="font-mono">{e.evidence_uid}</span>
                      <span className="chip">{evidenceRole(e.evidence_type, lang)}</span>
                      <Link href={L(lang, `/incidents/${e.incident_id}`)} className="no-underline">
                        {t.verify.openIncident}
                      </Link>
                    </dd>
                  </div>
                ))}
                <dt className="text-muted">{t.verify.fields.chain}</dt>
                <dd>
                  <span className="chip chip-chain">{t.verify.notAnchored}</span>
                </dd>
              </dl>
            </div>
          </section>
        ) : (
          <section className="card flex flex-col gap-2 p-5">
            <span className="text-[16px] font-semibold">{t.verify.notFound}</span>
            <p className="text-[13.5px] text-soft">{result.kind === "kosong" ? t.verify.notFoundEmpty : t.verify.notFoundText}</p>
          </section>
        )
      ) : null}

      <section className="grid gap-3 sm:grid-cols-3">
        {t.verify.steps.map((s, i) => (
          <div key={s.title} className="card flex flex-col gap-1.5 p-4">
            <span className={`label ${i === 2 ? "text-chain" : "text-accent"}`}>
              {t.verify.step} {i + 1}
            </span>
            <span className="text-[14px] font-semibold">{s.title}</span>
            <span className="text-[12.5px] leading-relaxed text-soft">{s.text}</span>
          </div>
        ))}
      </section>
    </div>
  );
}
