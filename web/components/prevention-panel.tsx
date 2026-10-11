/* Status peringatan terkini dan langkah pencegahan satu incident (incident_tiers). */
import type { IncidentTier } from "@/lib/queries";
import { getDict, type Lang } from "@/lib/i18n";
import { audienceText, channelOf, tipText, topicText } from "@/lib/prevention";
import { DemoChip, TierBadge } from "@/components/ui";

const TONE: Record<string, string> = {
  peringatan_dini: "var(--accent)",
  waspada: "var(--med)",
  rekomendasi_resmi: "var(--good)",
  peringatan_hoaks: "var(--high)",
};

function parse(raw: string | null): { steps?: string[]; channels?: string[]; text?: string | null; audience?: string[]; topics?: string[] } {
  if (!raw) return {};
  try {
    return JSON.parse(raw);
  } catch {
    return {};
  }
}

export function PreventionPanel({ tier, lang, compact = false }: { tier: IncidentTier; lang: Lang; compact?: boolean }) {
  const t = getDict(lang);
  const p = t.prevention;
  const plan = parse(tier.prevention);
  const steps = (plan.steps ?? []).map((k) => tipText(k, lang)).filter((s): s is string => Boolean(s));
  const channels = (plan.channels ?? []).map(channelOf).filter((c) => c !== null);
  const audience = (plan.audience ?? []).map((k) => audienceText(k, lang)).filter((s): s is string => Boolean(s));
  const topics = (plan.topics ?? []).map((k) => topicText(k, lang)).filter((s): s is string => Boolean(s));
  const source =
    tier.source_flow === "D4" ? p.source.D4(tier.institution ?? "lembaga") : tier.source_flow === "D2" ? p.source.D2 : p.source.D1;
  return (
    <section className={`card flex flex-col gap-3 ${compact ? "p-3.5" : "p-4"}`} style={{ borderLeft: `3px solid ${TONE[tier.tier] ?? "var(--line)"}` }}>
      {!compact ? <span className="label">{p.title}</span> : null}
      <div className="flex flex-wrap items-center gap-2">
        <TierBadge tier={tier.tier} lang={lang} />
        <span className="text-[12.5px] text-soft">{source}</span>
        {tier.review_note ? <span className="chip">{p.underReview(tier.review_note)}</span> : null}
        {tier.demo ? <DemoChip lang={lang} /> : null}
      </div>
      {tier.reason ? (
        <p className="text-[13.5px] text-fg">
          <span className="text-muted">{p.reason}: </span>
          {tier.reason}
        </p>
      ) : null}
      {plan.text ? (
        <p className="text-[13.5px] text-fg">
          <span className="text-muted">{p.official}: </span>
          {plan.text}
        </p>
      ) : null}
      {steps.length ? (
        <div className="flex flex-col gap-1">
          {!compact ? <span className="text-[12px] text-muted">{p.steps}</span> : null}
          <ul className="flex list-disc flex-col gap-1 pl-5 text-[13.5px] text-soft">
            {steps.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {!compact && (audience.length || topics.length) ? (
        <div className="grid gap-3 border-t border-line pt-3 sm:grid-cols-2">
          {audience.length ? (
            <div className="flex flex-col gap-1.5">
              <span className="text-[12px] text-muted">{p.audience}</span>
              <span className="flex flex-wrap gap-1.5">
                {audience.map((a) => (
                  <span key={a} className="chip">
                    {a}
                  </span>
                ))}
              </span>
            </div>
          ) : null}
          {topics.length ? (
            <div className="flex flex-col gap-1.5">
              <span className="text-[12px] text-muted">{p.topics}</span>
              <ol className="flex list-decimal flex-col gap-0.5 pl-5 text-[13px] text-soft">
                {topics.map((topic) => (
                  <li key={topic}>{topic}</li>
                ))}
              </ol>
            </div>
          ) : null}
        </div>
      ) : null}
      {channels.length ? (
        <p className="flex flex-wrap gap-x-2 gap-y-1 text-[12.5px] text-muted">
          <span>{p.report}</span>
          {channels.map((c) => (
            <a key={c.url} href={c.url} target="_blank" rel="noreferrer">
              {c.name}
            </a>
          ))}
        </p>
      ) : null}
    </section>
  );
}
