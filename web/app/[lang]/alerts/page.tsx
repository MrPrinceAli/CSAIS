import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { EARLY_DAYS, getAlerts, hasTable, type AlertRow } from "@/lib/queries";
import { formatters, incidentTitle } from "@/lib/format";
import { getDict, groupLabel, isLang, L, type Lang } from "@/lib/i18n";
import prevention from "@/lib/prevention.json";
import { PreventionPanel } from "@/components/prevention-panel";
import { RiskOverview } from "@/components/risk-overview";
import { SectionTitle, TypeChip } from "@/components/ui";

type Params = { lang: string };
type Search = { kelompok?: string };

export async function generateMetadata({ params }: { params: Promise<Params> }): Promise<Metadata> {
  const { lang } = await params;
  return { title: getDict(isLang(lang) ? lang : "id").alerts.title };
}

const GROUPS = Object.keys(prevention.by_group);
const SECTIONS = ["hoax", "official", "public", "early"] as const;

function AlertCard({ row, lang }: { row: AlertRow; lang: Lang }) {
  const t = getDict(lang);
  const f = formatters(lang);
  return (
    <li className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2 text-[12.5px] text-muted">
        <TypeChip attackType={row.attack_type} lang={lang} />
        <span>{f.date(row.anchor_published_date)}</span>
        <span>
          · {f.num(Number(row.document_count))} {t.common.articles}
        </span>
        {row.target_group ? <span>· {row.target_group.split(",").map((g) => groupLabel(g.trim(), lang)).join(", ")}</span> : null}
      </div>
      <Link href={L(lang, `/incidents/${row.incident_id}`)} className="text-[15px] font-semibold leading-snug text-fg no-underline hover:text-accent">
        {incidentTitle(row.title)}
      </Link>
      <PreventionPanel tier={row} lang={lang} compact />
    </li>
  );
}

/** Keluaran preventif untuk publik: status peringatan terkini dan langkah pencegahan per incident. */
export default async function AlertsPage({ params, searchParams }: { params: Promise<Params>; searchParams: Promise<Search> }) {
  const { lang } = await params;
  if (!isLang(lang)) notFound();
  const t = getDict(lang);
  const a = t.alerts;
  const { kelompok } = await searchParams;
  const group = kelompok && GROUPS.includes(kelompok) ? kelompok : undefined;
  const available = await hasTable("incident_tiers");
  const alerts = available ? await getAlerts(group) : null;
  const base = L(lang, "/alerts");

  return (
    <div className="flex flex-col gap-6 py-8">
      <header className="flex max-w-[78ch] flex-col gap-2">
        <h1 className="text-balance text-[28px] font-semibold leading-tight">{a.title}</h1>
        <p className="text-[14px] leading-relaxed text-soft">{a.lead}</p>
      </header>

      <RiskOverview lang={lang} />

      <div className="flex flex-col gap-1 border-t border-line pt-6">
        <h2 className="text-[20px] font-semibold">{a.perIncident}</h2>
        <p className="max-w-[78ch] text-[13.5px] text-muted">{a.perIncidentNote}</p>
      </div>

      <nav className="flex flex-wrap items-center gap-1.5" aria-label={a.group}>
        <span className="label mr-1">{a.group}</span>
        {[undefined, ...GROUPS].map((g) => (
          <Link
            key={g ?? "all"}
            href={g ? `${base}?kelompok=${g}` : base}
            className={`chip no-underline ${group === g ? "chip-accent" : ""}`}
            aria-current={group === g ? "page" : undefined}
          >
            {g ? groupLabel(g, lang) : a.allGroups}
          </Link>
        ))}
      </nav>

      {!alerts ? (
        <p className="card p-5 text-[14px] text-soft">{a.unavailable}</p>
      ) : (
        SECTIONS.map((key) => {
          const rows = alerts[key];
          const section = a.sections[key];
          const note = typeof section.note === "function" ? section.note(EARLY_DAYS) : section.note;
          return (
            <section key={key} className="flex flex-col gap-3">
              <SectionTitle aside={note}>{section.title}</SectionTitle>
              {rows.length ? (
                <ol className="grid gap-5 lg:grid-cols-2">
                  {rows.map((row) => (
                    <AlertCard key={row.incident_id} row={row} lang={lang} />
                  ))}
                </ol>
              ) : (
                <p className="text-[13px] text-muted">{a.empty}</p>
              )}
            </section>
          );
        })
      )}
    </div>
  );
}
