import { getRiskGroups } from "@/lib/queries";
import { formatters } from "@/lib/format";
import { attackLabel, getDict, groupLabel, type Lang } from "@/lib/i18n";
import { GroupArt } from "@/components/group-art";
import { SectionTitle } from "@/components/ui";
import { preventionFor } from "@/lib/prevention";

type Level = "high" | "medium" | "low";
const LEVEL_COLOR: Record<Level, string> = { high: "var(--crit)", medium: "var(--high)", low: "var(--med)" };

function levelOf(now: number, prev: number): Level {
  if (now >= 20 || (now >= 8 && now > prev * 1.5)) return "high";
  if (now >= 5) return "medium";
  return "low";
}

/**
 * Kelompok sasaran berisiko (dulu halaman Temuan): langkah pencegahan per
 * kelompok, diurutkan dari kelompok dengan incident terbanyak 30 hari terakhir;
 * nomor peringkatnya ada di pojok kartu. Dipakai di bagian atas halaman Peringatan.
 */
export async function RiskOverview({ lang }: { lang: Lang }) {
  const t = getDict(lang);
  const f = formatters(lang);
  const groups = await getRiskGroups();
  const totalNow = groups.reduce((acc, g) => acc + g.now, 0);
  const rising = groups.filter((g) => g.now > g.prev).length;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h2 className="text-[20px] font-semibold">{t.alerts.riskTitle}</h2>
        <p className="max-w-[90ch] text-[13.5px] text-muted">{t.findings.subtitle(f.num(totalNow), f.num(rising), f.num(groups.length))}</p>
      </div>

      {groups.some((g) => g.now > 0) ? (
        <section>
          <SectionTitle aside={t.findings.prevention.note}>{t.findings.prevention.title}</SectionTitle>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {groups
              .filter((g) => g.now > 0)
              .slice(0, 6)
              .map((g, i) => {
                const level = levelOf(g.now, g.prev);
                const modes = g.types.filter((x) => x.t !== "unknown");
                const plan = preventionFor(g.group, modes.map((x) => x.t), lang);
                return (
                  <article key={g.group} className="card lift fade-up relative isolate flex flex-col gap-3 overflow-hidden p-4" style={{ "--i": i, borderTopColor: LEVEL_COLOR[level], borderTopWidth: 2 } as React.CSSProperties}>
                    <GroupArt group={g.group} color={LEVEL_COLOR[level]} />
                    <span
                      className="tnum absolute right-3 top-3 flex h-8 min-w-8 items-center justify-center rounded-md border px-1.5 font-mono text-[14px] font-semibold"
                      style={{ color: LEVEL_COLOR[level], borderColor: LEVEL_COLOR[level], background: `color-mix(in srgb, ${LEVEL_COLOR[level]} 10%, transparent)` }}
                      title={t.findings.prevention.rank(i + 1)}
                      aria-label={t.findings.prevention.rank(i + 1)}
                    >
                      #{i + 1}
                    </span>
                    <header className="flex flex-col gap-1 pr-12">
                      <h3 className="text-[16px] font-semibold leading-tight">{groupLabel(g.group, lang)}</h3>
                      <span className="flex items-center gap-1.5 text-[12.5px] font-semibold" style={{ color: LEVEL_COLOR[level] }}>
                        <span className="inline-block h-2 w-2 rounded-full" style={{ background: LEVEL_COLOR[level] }} aria-hidden="true" />
                        {t.findings.levels[level]} · {t.findings.prevention.incidents(f.num(g.now))}
                      </span>
                      <span className="text-[12.5px] text-muted">
                        {t.findings.prevention.modes}: {modes.slice(0, 2).map((x) => `${attackLabel(x.t, lang)} ${f.num(x.n)}`).join(" · ") || t.common.unknown}
                      </span>
                    </header>
                    <ol className="flex flex-col gap-2 border-t border-line pt-3">
                      {plan.steps.map((step, k) => (
                        <li key={step} className="grid grid-cols-[26px_minmax(0,1fr)] gap-2 text-[13.5px] leading-relaxed text-soft">
                          <span className="font-mono text-[12px] font-semibold" style={{ color: LEVEL_COLOR[level] }}>
                            0{k + 1}
                          </span>
                          <span>{step}</span>
                        </li>
                      ))}
                    </ol>
                    <div className="mt-auto flex flex-wrap items-center gap-1.5 border-t border-line pt-3 text-[12.5px] text-muted">
                      <span>{t.findings.prevention.report}</span>
                      {plan.channels.map((c) => (
                        <a key={c.url} href={c.url} target="_blank" rel="noreferrer" className="chip chip-good no-underline">
                          {c.name} ↗
                        </a>
                      ))}
                    </div>
                  </article>
                );
              })}
          </div>
          <p className="mt-2 text-[12px] text-muted">{t.findings.rule}</p>
        </section>
      ) : (
        <div className="card p-4 text-[13.5px] text-muted">{t.findings.empty}</div>
      )}
    </div>
  );
}
