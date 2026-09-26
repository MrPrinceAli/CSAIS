import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getRiskGroups, type GroupStat } from "@/lib/queries";
import { formatters, incidentTitle } from "@/lib/format";
import { attackLabel, getDict, groupLabel, isLang, L } from "@/lib/i18n";
import { SectionTitle, Sparkline } from "@/components/ui";

export const revalidate = 3600;

export async function generateMetadata({ params }: { params: Promise<{ lang: string }> }): Promise<Metadata> {
  const { lang } = await params;
  return { title: getDict(isLang(lang) ? lang : "id").findings.title };
}

type Level = "high" | "medium" | "low";
const LEVEL_COLOR: Record<Level, string> = { high: "var(--crit)", medium: "var(--high)", low: "var(--med)" };

function levelOf(now: number, prev: number): Level {
  if (now >= 20 || (now >= 8 && now > prev * 1.5)) return "high";
  if (now >= 5) return "medium";
  return "low";
}

export default async function FindingsPage({ params }: { params: Promise<{ lang: string }> }) {
  const { lang } = await params;
  if (!isLang(lang)) notFound();
  const t = getDict(lang);
  const f = formatters(lang);
  const groups = await getRiskGroups();
  const totalNow = groups.reduce((acc, g) => acc + g.now, 0);
  const rising = groups.filter((g) => g.now > g.prev).length;
  const maxNow = Math.max(...groups.map((g) => g.now), 1);

  // Heatmap: kelompok teratas × jenis serangan teratas
  const typeTotals = new Map<string, number>();
  for (const g of groups) for (const [type, n] of Object.entries(g.typesAll)) typeTotals.set(type, (typeTotals.get(type) ?? 0) + n);
  const topTypes = [...typeTotals.entries()]
    .filter(([type]) => type !== "unknown")
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6)
    .map(([type]) => type);
  const heatGroups = groups.slice(0, 8);
  const heatMax = Math.max(1, ...heatGroups.flatMap((g) => topTypes.map((type) => g.typesAll[type] ?? 0)));

  function changeText(g: GroupStat): { text: string; color: string } {
    if (g.prev === 0) return { text: g.now ? t.findings.change.new : "—", color: "var(--muted)" };
    const pct = Math.round((100 * (g.now - g.prev)) / g.prev);
    if (pct > 0) return { text: t.findings.change.up(pct), color: "var(--high)" };
    if (pct < 0) return { text: t.findings.change.down(Math.abs(pct)), color: "var(--good)" };
    return { text: t.findings.change.same, color: "var(--muted)" };
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-[24px] font-semibold">{t.findings.title}</h1>
        <p className="max-w-[90ch] text-[13.5px] text-muted">{t.findings.subtitle(f.num(totalNow), f.num(rising), f.num(groups.length))}</p>
      </div>

      <section>
        <SectionTitle aside={t.findings.boardNote}>{t.findings.boardTitle}</SectionTitle>
        {groups.length ? (
          <div className="card overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[860px] border-collapse text-[13px]">
                <thead>
                  <tr className="label border-b border-line text-left">
                    <th className="px-4 py-2.5 font-medium">{t.findings.columns.group}</th>
                    <th className="px-2 py-2.5 font-medium">{t.findings.columns.level}</th>
                    <th className="px-2 py-2.5 font-medium">{t.findings.columns.count}</th>
                    <th className="px-2 py-2.5 font-medium">{t.findings.columns.change}</th>
                    <th className="px-2 py-2.5 font-medium">{t.findings.columns.trend}</th>
                    <th className="px-4 py-2.5 font-medium">{t.findings.columns.types}</th>
                  </tr>
                </thead>
                <tbody>
                  {groups.map((g, i) => {
                    const level = levelOf(g.now, g.prev);
                    const change = changeText(g);
                    return (
                      <tr key={g.group} className="scan-row row-in border-b border-line align-middle last:border-b-0" style={{ animationDelay: `${Math.min(i, 20) * 45}ms` }}>
                        <td className="px-4 py-3">
                          <span className="block font-semibold">{groupLabel(g.group, lang)}</span>
                          {g.samples[0] ? (
                            <Link href={L(lang, `/incidents/${g.samples[0].incident_id}`)} className="block max-w-[320px] truncate text-[12px] text-muted no-underline hover:text-accent">
                              {incidentTitle(g.samples[0].title)}
                            </Link>
                          ) : null}
                        </td>
                        <td className="px-2 py-3">
                          <span className="inline-flex items-center gap-2 text-[12.5px] font-semibold" style={{ color: LEVEL_COLOR[level] }}>
                            <span className={level === "high" ? "led led-crit" : "inline-block h-2 w-2 rounded-full"} style={{ background: LEVEL_COLOR[level] }} aria-hidden="true" />
                            {t.findings.levels[level]}
                          </span>
                        </td>
                        <td className="px-2 py-3">
                          <div className="grid grid-cols-[36px_minmax(0,1fr)] items-center gap-2">
                            <span className="tnum font-mono">{f.num(g.now)}</span>
                            <span className="block h-1.5 w-full max-w-[140px] overflow-hidden rounded-sm bg-line">
                              <span className="bar-fill block h-full" style={{ width: `${Math.max(2, (100 * g.now) / maxNow)}%`, background: LEVEL_COLOR[level], "--i": i } as React.CSSProperties} />
                            </span>
                          </div>
                        </td>
                        <td className="px-2 py-3 font-mono text-[12.5px]" style={{ color: change.color }}>
                          {change.text}
                        </td>
                        <td className="px-2 py-3">
                          <Sparkline values={g.weeks} width={110} height={30} color={LEVEL_COLOR[level]} />
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex flex-wrap gap-1.5">
                            {g.types.map((x) => (
                              <Link key={x.t} href={`${L(lang, "/incidents")}?jenis=${encodeURIComponent(x.t)}`} className="chip no-underline">
                                {attackLabel(x.t, lang)} <span className="font-mono text-muted">{f.num(x.n)}</span>
                              </Link>
                            ))}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        ) : (
          <div className="card p-4 text-[13.5px] text-muted">{t.findings.empty}</div>
        )}
        <p className="mt-2 text-[12px] text-muted">{t.findings.rule}</p>
      </section>

      {heatGroups.length && topTypes.length ? (
        <section>
          <SectionTitle aside={t.findings.heatmapNote}>{t.findings.heatmapTitle}</SectionTitle>
          <div className="card overflow-x-auto p-4">
            <div className="grid min-w-[720px] gap-px" style={{ gridTemplateColumns: `180px repeat(${topTypes.length}, minmax(0, 1fr))` }}>
              <span />
              {topTypes.map((type) => (
                <span key={type} className="label truncate px-2 pb-2 text-[10.5px]" title={attackLabel(type, lang)}>
                  {attackLabel(type, lang)}
                </span>
              ))}
              {heatGroups.map((g, gi) => (
                <div key={g.group} className="contents">
                  <span className="truncate pr-3 text-[12.5px] leading-[38px]">{groupLabel(g.group, lang)}</span>
                  {topTypes.map((type, ti) => {
                    const n = g.typesAll[type] ?? 0;
                    const alpha = n ? 0.15 + 0.75 * (n / heatMax) : 0;
                    return (
                      <Link
                        key={type}
                        href={`${L(lang, "/incidents")}?jenis=${encodeURIComponent(type)}`}
                        className="heat-cell flex h-[38px] items-center justify-center rounded-sm border border-line font-mono text-[12px] no-underline"
                        style={{ background: `rgba(242, 85, 90, ${alpha})`, color: n ? "var(--fg)" : "var(--muted)", "--i": gi * topTypes.length + ti } as React.CSSProperties}
                        title={`${groupLabel(g.group, lang)} · ${attackLabel(type, lang)}: ${n}`}
                      >
                        {n || "·"}
                      </Link>
                    );
                  })}
                </div>
              ))}
            </div>
          </div>
        </section>
      ) : null}

      <section className="grid gap-3 lg:grid-cols-2">
        <div className="card lift flex flex-col gap-2 p-4">
          <span className="label">{t.findings.nextTitle}</span>
          <span className="text-[15px] font-semibold">{t.findings.next4.title}</span>
          <p className="text-[13.5px] leading-relaxed text-soft">{t.findings.next4.text}</p>
        </div>
        <div className="card lift flex flex-col gap-2 p-4" style={{ borderColor: "color-mix(in srgb, var(--chain) 60%, transparent)" }}>
          <span className="label text-chain">{t.findings.nextTitle}</span>
          <span className="text-[15px] font-semibold">{t.findings.next5.title}</span>
          <p className="text-[13.5px] leading-relaxed text-soft">{t.findings.next5.text}</p>
        </div>
      </section>
    </div>
  );
}
