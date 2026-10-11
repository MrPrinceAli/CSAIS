/*
 * Sorotan global (halaman Peringatan): incident luar negeri yang paling ramai
 * diberitakan akhir-akhir ini, diterjemahkan menjadi rekomendasi literasi untuk
 * masyarakat Indonesia. Sasarannya platform yang juga dipakai di Indonesia
 * (web/lib/platforms.json, mis. "Pengguna Binance di Indonesia, usia 18-30"),
 * atau bila tidak ada, korban incident itu sendiri ("Pengguna dan pelanggan X
 * di Indonesia"), lalu sasaran dan materi literasi D1/D4.
 */
import Link from "next/link";
import { getAiTop, getGlobalSpotlight, type AiTopRow } from "@/lib/queries";
import { AiAdviceView, AiBadge } from "@/components/ai-advice";
import { formatters, incidentTitle } from "@/lib/format";
import { getDict, L, type Lang } from "@/lib/i18n";
import { COUNTRY } from "@/lib/geo";
import { audienceText, platformOf, serviceAudience, topicText } from "@/lib/prevention";
import { SectionTitle, TypeChip } from "@/components/ui";

const DAYS = 14;
// Korban berupa instansi atau tempat, bukan layanan yang punya "pelanggan"
const INSTITUTION_WORDS =
  /\b(pentagon|fbi|cia|nsa|cisa|army|navy|air force|military|police|polisi|court|pengadilan|ministry|kementerian|department|government|pemerintah|council|parliament|agency|city|county|state|district|school|sekolah|university|universitas|college|hospital|rumah sakit|clinic)\b/i;
const US_STATES =
  "alabama|alaska|arizona|arkansas|california|colorado|connecticut|delaware|florida|georgia|hawaii|idaho|illinois|indiana|iowa|kansas|kentucky|louisiana|maine|maryland|massachusetts|michigan|minnesota|mississippi|missouri|montana|nebraska|nevada|new hampshire|new jersey|new mexico|new york|north carolina|north dakota|ohio|oklahoma|oregon|pennsylvania|rhode island|south carolina|south dakota|tennessee|texas|utah|vermont|virginia|washington|west virginia|wisconsin|wyoming".split(
    "|",
  );
// Sektor korban -> instansi sejenis di Indonesia dan sasaran literasinya
const INSTITUTION_SECTORS: Record<string, string[]> = {
  GOVERNMENT: ["asn_layanan", "staf_ti"],
  EDUCATION: ["guru", "staf_ti"],
  HEALTHCARE: ["staf_ti", "pimpinan"],
  CRITICAL_INFRASTRUCTURE: ["staf_ti", "pimpinan"],
  ENERGY: ["staf_ti", "pimpinan"],
};

// Sektor V0.3 yang cukup tegas untuk menyebut korban sebagai institusi; "GOVERNMENT"
// terlalu sering ikut tertandai pada berita fintech/perangkat lunak, jadi instansi
// pemerintah hanya dikenali dari namanya.
const SECTOR_TRUSTED = new Set(["EDUCATION", "HEALTHCARE"]);

/** Sektor institusi korban, atau null bila korbannya layanan untuk konsumen. */
function institutionSector(target: string | null, sector: string | null): string | null {
  const name = (target ?? "").split(",")[0].trim().toLowerCase();
  const main = (sector ?? "").split(",")[0].trim();
  if (name && (INSTITUTION_WORDS.test(name) || COUNTRY[name] || US_STATES.includes(name))) return "GOVERNMENT";
  return SECTOR_TRUSTED.has(main) ? main : null;
}

function titleCase(value: string): string {
  return value === value.toLowerCase() ? value.replace(/\b\p{L}/gu, (c) => c.toUpperCase()) : value;
}

/** Korban yang layak disebut sebagai layanan: nama pendek, bukan "UNKNOWN" atau kata umum. */
function serviceName(target: string | null): string | null {
  const name = (target ?? "").split(",")[0].trim();
  if (!name || name === "UNKNOWN" || name.length < 3 || name.length > 40 || /^(warga|korban|pengguna|users?|customers?|people)$/i.test(name)) return null;
  return titleCase(name);
}

export async function GlobalSpotlight({ lang }: { lang: Lang }) {
  const t = getDict(lang);
  const g = t.globalSpotlight;
  const f = formatters(lang);
  // Setelah tahap AI berjalan: 10 incident terbesar (dalam dan luar negeri) dengan saran AI
  const top = await getAiTop();
  const rows: (Omit<AiTopRow, "rank" | "advice" | "model"> & Partial<Pick<AiTopRow, "advice" | "model">>)[] = top.length ? top : await getGlobalSpotlight(DAYS);
  if (!rows.length) return null;
  const withAi = top.some((r) => r.advice);

  return (
    <section className="flex flex-col gap-3">
      <div className="flex flex-col gap-1">
        <h2 className="flex flex-wrap items-center gap-2 text-[20px] font-semibold">
          {top.length ? t.ai.topTitle : g.title}
          {withAi ? <AiBadge lang={lang} model={top.find((r) => r.model)?.model} /> : null}
        </h2>
        <p className="max-w-[90ch] text-[13.5px] text-muted">{top.length ? t.ai.topLead(DAYS) : g.lead(DAYS)}</p>
      </div>
      <SectionTitle aside={g.note}>{g.subtitle}</SectionTitle>
      <ol className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {rows.map((row, i) => {
          let plan: { audience?: string[]; topics?: string[] } = {};
          try {
            plan = row.prevention ? JSON.parse(row.prevention) : {};
          } catch {}
          const platformKeys = (plan.audience ?? []).filter((k) => platformOf(k));
          const detected = (row.platforms ?? "")
            .split(",")
            .filter(Boolean)
            .map((k) => `platform:${k}`);
          const platforms = [...new Set([...platformKeys, ...detected])].slice(0, 2);
          const institution = platforms.length ? null : institutionSector(row.target, row.sector);
          const service = platforms.length || institution ? null : serviceName(row.target);
          const victim = serviceName(row.target);
          const audiences = [
            ...platforms.map((k) => audienceText(k, lang)),
            ...(service ? [serviceAudience(service, lang)] : []),
            ...(institution ? [g.institutions[institution], ...INSTITUTION_SECTORS[institution].map((k) => audienceText(k, lang))] : []),
            ...(plan.audience ?? []).filter((k) => !platformOf(k)).map((k) => audienceText(k, lang)),
          ]
            .filter((s, i, all): s is string => Boolean(s) && all.indexOf(s) === i)
            .slice(0, 3);
          const topics = (plan.topics ?? [])
            .map((k) => topicText(k, lang))
            .filter((s): s is string => Boolean(s))
            .slice(0, 3);
          const place = (row.location ?? "").split(",")[0].trim();
          const country = place ? (COUNTRY[place.toLowerCase()]?.label ?? titleCase(place)) : g.global;
          const names = platforms.map((k) => platformOf(k)?.name).filter(Boolean);
          return (
            <li key={row.incident_id} className="card lift relative flex flex-col gap-3 overflow-hidden p-4">
              <span
                aria-hidden="true"
                className="pointer-events-none absolute -right-2 -top-4 font-mono text-[64px] font-bold leading-none text-[color-mix(in_srgb,var(--accent)_12%,transparent)]"
              >
                {i + 1}
              </span>
              <div className="flex flex-wrap items-center gap-2 text-[12px] text-muted">
                <span className="chip chip-accent">{country}</span>
                <TypeChip attackType={row.attack_type} lang={lang} />
                <span>
                  {f.num(Number(row.document_count))} {t.common.articles}
                  {row.domains ? ` · ${g.sources(f.num(Number(row.domains)))}` : ""}
                </span>
              </div>
              <Link href={L(lang, `/incidents/${row.incident_id}`)} className="line-clamp-2 pr-8 text-[15px] font-semibold leading-snug text-fg no-underline hover:text-accent">
                {incidentTitle(row.title)}
              </Link>
              {row.advice ? (
                <AiAdviceView advice={row.advice} lang={lang} compact parts={["ringkasan", "sasaran", "materi", "pesan_kunci"]} />
              ) : (
                <>
                  <p className="text-[12.5px] text-soft">
                    <span className="text-muted">{g.why}: </span>
                    {names.length
                      ? g.usedHere(names.join(", "))
                      : institution
                        ? g.institutionHere(victim ?? g.global, g.institutions[institution])
                        : service
                          ? g.serviceHere(service)
                          : g.generic}
                  </p>
                  {audiences.length ? (
                    <div className="flex flex-col gap-1.5">
                      <span className="label">{g.audience}</span>
                      <span className="flex flex-wrap gap-1.5">
                        {audiences.map((a) => (
                          <span key={a} className="chip">
                            {a}
                          </span>
                        ))}
                      </span>
                    </div>
                  ) : null}
                  {topics.length ? (
                    <div className="mt-auto flex flex-col gap-1.5 border-t border-line pt-3">
                      <span className="label">{g.topics}</span>
                      <ol className="flex list-decimal flex-col gap-0.5 pl-5 text-[13px] text-soft">
                        {topics.map((topic) => (
                          <li key={topic}>{topic}</li>
                        ))}
                      </ol>
                    </div>
                  ) : null}
                </>
              )}
            </li>
          );
        })}
      </ol>
      <p className="text-[11.5px] text-muted">
        {withAi ? `${t.ai.note(top.find((r) => r.model)?.model ?? "AI")} ` : ""}
        {g.ageSource}
      </p>
    </section>
  );
}
