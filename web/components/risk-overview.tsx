import { getRiskGroups } from "@/lib/queries";
import { formatters } from "@/lib/format";
import { attackLabel, getDict, groupLabel, type Lang } from "@/lib/i18n";
import { GROUP_PHOTOS, GroupPhoto } from "@/components/group-photo";
import { SectionTitle } from "@/components/ui";
import { preventionFor } from "@/lib/prevention";

type Level = "high" | "medium" | "low";
const LEVEL_COLOR: Record<Level, string> = { high: "var(--crit)", medium: "var(--high)", low: "var(--med)" };

// Peringkat 1-3 diberi rona emas, perak, perunggu yang lembut; sisanya abu-abu
const RANK_TONE = ["#e8c872", "#d3dae3", "#d9a07a"];

function levelOf(now: number, prev: number): Level {
  if (now >= 20 || (now >= 8 && now > prev * 1.5)) return "high";
  if (now >= 5) return "medium";
  return "low";
}

/**
 * Kelompok sasaran berisiko (dulu halaman Temuan): langkah pencegahan per
 * kelompok, diurutkan dari kelompok dengan incident terbanyak 30 hari terakhir;
 * nomor peringkatnya ada di pojok kartu dan latar atasnya foto kelompok itu.
 * Dipakai di bagian atas halaman Peringatan.
 */
export async function RiskOverview({ lang }: { lang: Lang }) {
  const t = getDict(lang);
  const f = formatters(lang);
  const groups = await getRiskGroups();
  const totalNow = groups.reduce((acc, g) => acc + g.now, 0);
  const rising = groups.filter((g) => g.now > g.prev).length;
  const shown = groups.filter((g) => g.now > 0).slice(0, 6);

  return (
    <div id="kelompok-berisiko" className="flex scroll-mt-16 flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h2 className="text-[20px] font-semibold">{t.alerts.riskTitle}</h2>
        <p className="max-w-[90ch] text-[13.5px] text-muted">{t.findings.subtitle(f.num(totalNow), f.num(rising), f.num(groups.length))}</p>
      </div>

      {shown.length ? (
        <section>
          <SectionTitle aside={t.findings.prevention.note}>{t.findings.prevention.title}</SectionTitle>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {shown.map((g, i) => {
                const level = levelOf(g.now, g.prev);
                const modes = g.types.filter((x) => x.t !== "unknown");
                const plan = preventionFor(g.group, modes.map((x) => x.t), lang);
                return (
                  <article key={g.group} className="card lift fade-up relative isolate flex flex-col gap-3 overflow-hidden p-4" style={{ "--i": i, borderTopColor: LEVEL_COLOR[level], borderTopWidth: 2 } as React.CSSProperties}>
                    <GroupPhoto group={g.group} color={LEVEL_COLOR[level]} />
                    <div
                      className="absolute right-4 top-3.5 flex flex-col items-end leading-none"
                      title={t.findings.prevention.rank(i + 1)}
                      aria-label={t.findings.prevention.rank(i + 1)}
                    >
                      <span className="text-[9px] font-semibold uppercase tracking-[0.22em] text-soft [text-shadow:0_1px_6px_rgba(0,0,0,0.95)]">{t.findings.prevention.rankLabel}</span>
                      <span
                        className="tnum mt-1 font-mono text-[30px] font-extralight tracking-tight [text-shadow:0_1px_10px_rgba(0,0,0,0.85)]"
                        style={{ color: RANK_TONE[i] ?? "var(--soft)" }}
                      >
                        {String(i + 1).padStart(2, "0")}
                      </span>
                      <span className="mt-1.5 h-[2px] w-5 rounded-full" style={{ background: RANK_TONE[i] ?? "var(--line-2)" }} aria-hidden="true" />
                    </div>
                    <header className="flex flex-col gap-1 pr-16 [text-shadow:0_1px_8px_rgba(0,0,0,0.7)]">
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
          <p className="mt-1 text-[11.5px] text-muted">
            {t.findings.photoCredit}{" "}
            {shown
              .filter((g) => GROUP_PHOTOS[g.group])
              .map((g, i) => {
                const credit = GROUP_PHOTOS[g.group];
                return (
                  <span key={g.group}>
                    {i ? " · " : ""}
                    {groupLabel(g.group, lang)}:{" "}
                    <a href={credit.url} target="_blank" rel="noreferrer" className="text-muted underline">
                      {credit.author}
                    </a>{" "}
                    ({credit.license})
                  </span>
                );
              })}
          </p>
        </section>
      ) : (
        <div className="card p-4 text-[13.5px] text-muted">{t.findings.empty}</div>
      )}
    </div>
  );
}
