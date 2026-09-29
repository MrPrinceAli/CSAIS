import type { Metadata } from "next";
import { cookies } from "next/headers";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getPortalCardsById, getPortalQueue, type PortalCard } from "@/lib/queries";
import { formatters, incidentTitle } from "@/lib/format";
import { attackLabel, getDict, isLang, L, type Lang } from "@/lib/i18n";
import { INSTITUTION_LOGO, INSTITUTION_NAME, INSTITUTIONS, institutionFromSession, MANDATE, portalConfigured, REASONS, REVIEW_FIELDS, SESSION_COOKIE_NAME } from "@/lib/portal";
import { reviewsBy } from "@/lib/survey";
import { OrgLogo } from "@/components/org-logo";
import { PortalLogin, PortalLogout } from "@/components/portal-login";
import { ReviewCard } from "@/components/review-card";
import { TypeChip } from "@/components/ui";

type Params = { lang: string };
type Search = { tab?: string; page?: string };

export async function generateMetadata({ params }: { params: Promise<Params> }): Promise<Metadata> {
  const { lang } = await params;
  return { title: getDict(isLang(lang) ? lang : "id").portal.title, robots: { index: false } };
}

const PAGE = 20;
const POOL = 60;

function display(field: string, value: string | null, lang: Lang): string | null {
  if (!value) return null;
  if (field === "attack_type") return [...new Set(value.split(",").map((v) => attackLabel(v, lang)))].join(", ");
  if (field === "location") return value.split(",").map((v) => v.trim().replace(/^./, (c) => c.toUpperCase())).join(", ");
  return value;
}

/** Portal lembaga (alur D3): antrean incident sesuai mandat dan tombol keputusan. */
export default async function PortalPage({ params, searchParams }: { params: Promise<Params>; searchParams: Promise<Search> }) {
  const { lang } = await params;
  if (!isLang(lang)) notFound();
  const t = getDict(lang);
  const p = t.portal;
  const f = formatters(lang);
  const sp = await searchParams;
  const store = await cookies();
  const inst = institutionFromSession(store.get(SESSION_COOKIE_NAME)?.value);

  const header = (
    <header className="flex max-w-[78ch] flex-col gap-2">
      <span className="label text-chain">D3 · {p.title}</span>
      <h1 className="text-balance text-[26px] font-semibold leading-tight">{inst ? p.signedIn(INSTITUTION_NAME[inst]) : p.title}</h1>
      <p className="text-[14px] leading-relaxed text-soft">{p.lead}</p>
    </header>
  );

  if (!portalConfigured()) {
    return (
      <div className="flex flex-col gap-5 py-8">
        {header}
        <p className="card p-5 text-[14px] text-soft">{p.unavailable}</p>
      </div>
    );
  }
  if (!inst) {
    return (
      <div className="flex flex-col gap-5 py-8">
        {header}
        <PortalLogin
          strings={p.login}
          institutions={INSTITUTIONS.map((code) => ({ code, name: INSTITUTION_NAME[code], logo: `/logos/${INSTITUTION_LOGO[code].toLowerCase()}.png` }))}
        />
      </div>
    );
  }

  const tab = sp.tab === "done" ? "done" : "queue";
  const page = Math.max(0, Number.parseInt(sp.page ?? "0", 10) || 0);
  const reviewed = await reviewsBy(inst);
  let cards: PortalCard[];
  if (tab === "done") {
    cards = await getPortalCardsById([...reviewed.keys()].slice(-100).reverse());
  } else {
    const pool = await getPortalQueue(MANDATE[inst], POOL, page * POOL);
    cards = pool.filter((c) => !reviewed.has(c.incident_id)).slice(0, PAGE);
  }
  const base = L(lang, "/portal");
  const reviewStrings = {
    decision: p.decision,
    reason: p.reason,
    fieldsTitle: p.fieldsTitle,
    fieldsHint: p.fieldsHint,
    fieldValues: p.fieldValues,
    note: p.note,
    source: p.source,
    submit: p.submit,
    sending: p.sending,
    saved: p.saved,
    again: p.again,
    failed: p.failed,
    chooseReason: p.chooseReason,
    statuses: p.statuses,
    reasons: p.reasons,
    unknown: t.common.unknown,
  };

  return (
    <div className="flex flex-col gap-5 py-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-start gap-4">
          <OrgLogo org={INSTITUTION_LOGO[inst]} size={52} />
          {header}
        </div>
        <PortalLogout label={p.logout} />
      </div>

      <nav className="flex gap-2 border-b border-line" aria-label={p.title}>
        {(["queue", "done"] as const).map((key) => (
          <Link
            key={key}
            href={key === "queue" ? base : `${base}?tab=done`}
            className={`-mb-px border-b-2 px-3 py-2 text-[13.5px] no-underline ${tab === key ? "border-accent text-fg" : "border-transparent text-muted"}`}
          >
            {p.tabs[key]}
            {key === "done" ? <span className="ml-1.5 font-mono text-[12px] text-muted">{f.num(reviewed.size)}</span> : null}
          </Link>
        ))}
      </nav>

      {!cards.length ? <p className="card p-5 text-[14px] text-soft">{p.empty}</p> : null}

      <ol className="flex flex-col gap-3">
        {cards.map((c) => {
          const done = reviewed.get(c.incident_id);
          return (
            <li key={c.incident_id} className="card flex flex-col gap-3 p-4">
              <div className="flex flex-wrap items-center gap-2 text-[12.5px] text-muted">
                <TypeChip attackType={c.card.attack_type} lang={lang} />
                {c.indonesia ? <span className="chip chip-accent">{p.indonesia}</span> : null}
                <span>{f.date(c.anchor_published_date)}</span>
                <span>· {p.articles(f.num(c.document_count))}</span>
                {c.trust_level ? <span>· {t.flows.status[c.trust_level] ?? c.trust_level}</span> : null}
              </div>
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <h2 className="text-[16px] font-semibold leading-snug">{incidentTitle(c.title)}</h2>
                <Link href={L(lang, `/incidents/${c.incident_id}`)} className="text-[12.5px]">
                  {p.open}
                </Link>
              </div>
              <dl className="grid grid-cols-[120px_minmax(0,1fr)] gap-x-3 gap-y-1 text-[13px] sm:grid-cols-[120px_minmax(0,1fr)_120px_minmax(0,1fr)]">
                {REVIEW_FIELDS.map((field) => (
                  <div key={field} className="contents">
                    <dt className="text-muted">{t.flows.rows[field]}</dt>
                    <dd>{display(field, c.card[field], lang) ?? <span className="text-muted">{t.common.unknown}</span>}</dd>
                  </div>
                ))}
              </dl>
              {done ? <p className="text-[12.5px] text-good">{p.reviewed(p.statuses[done.status] ?? done.status, f.dateTime(done.created_at))}</p> : null}
              <ReviewCard
                incidentId={c.incident_id}
                outputId={Number(c.card.output_id)}
                fields={REVIEW_FIELDS.map((field) => ({ key: field, label: t.flows.rows[field], value: display(field, c.card[field], lang) }))}
                reasonsByStatus={REASONS}
                strings={reviewStrings}
              />
            </li>
          );
        })}
      </ol>

      {tab === "queue" && cards.length === PAGE ? (
        <Link href={`${base}?page=${page + 1}`} className="btn btn-ghost self-start">
          {p.more}
        </Link>
      ) : null}
    </div>
  );
}
