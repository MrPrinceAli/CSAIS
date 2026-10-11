/*
 * Perbandingan keluaran preventif alur D1 - D4 satu incident: sasaran literasi,
 * materi literasi, langkah pencegahan, dan alasan lembaga berdampingan. Nilai
 * kolom kartu dan penilaiannya ada di bagian "Klaim terekstrak".
 */
import type { FlowOutput } from "@/lib/queries";
import { formatters } from "@/lib/format";
import Link from "next/link";
import { getDict, L, type Lang } from "@/lib/i18n";
import { FLOW_TONE, FLOWS, latestByFlow, parseJson, type PreventionPlan } from "@/lib/flow-view";
import { audienceText, channelOf, tipText, topicText } from "@/lib/prevention";
import { recordUid } from "@/lib/records";
import { DemoChip, SectionTitle } from "@/components/ui";

/** Nama host tautan sumber pernyataan; null bila bukan URL http(s). */
function hostOf(ref: string | null): string | null {
  if (!ref || !/^https?:\/\//.test(ref)) return null;
  try {
    return new URL(ref).hostname;
  } catch {
    return null;
  }
}

export function FlowCompare({ lang, incidentId, outputs }: { lang: Lang; incidentId: string; outputs: FlowOutput[] }) {
  const t = getDict(lang);
  const f = formatters(lang);
  const latest = latestByFlow(outputs);
  const d1History = outputs.filter((o) => o.flow === "D1").length;
  if (!latest.D1) return null;

  const cell = "px-3 py-2.5 align-top";
  const empty = <span className="text-muted">–</span>;
  const plans = Object.fromEntries(FLOWS.map((flow) => [flow, parseJson<PreventionPlan>(latest[flow]?.prevention)]));

  const chips = (keys: string[] | undefined, text: (key: string, lang: Lang) => string | null) => {
    const labels = (keys ?? []).map((k) => text(k, lang)).filter((s): s is string => Boolean(s));
    if (!labels.length) return empty;
    return (
      <span className="flex flex-wrap gap-1.5">
        {labels.map((label) => (
          <span key={label} className="chip">
            {label}
          </span>
        ))}
      </span>
    );
  };

  const topicsCell = (plan: PreventionPlan | null) => {
    const topics = (plan?.topics ?? []).map((k) => topicText(k, lang)).filter((s): s is string => Boolean(s));
    if (!topics.length) return empty;
    return (
      <ol className="flex flex-col gap-1 text-soft">
        {topics.map((topic, i) => (
          <li key={topic} className="grid grid-cols-[20px_minmax(0,1fr)] gap-1">
            <span className="font-mono text-[11.5px] text-muted">{i + 1}.</span>
            <span>{topic}</span>
          </li>
        ))}
      </ol>
    );
  };

  const stepsCell = (plan: PreventionPlan | null) => {
    if (!plan) return empty;
    const steps = (plan.steps ?? []).map((k) => tipText(k, lang)).filter((s): s is string => Boolean(s));
    const channels = (plan.channels ?? []).map(channelOf).filter((c) => c !== null);
    if (!steps.length && !plan.text && !channels.length) return empty;
    return (
      <div className="flex flex-col gap-1.5">
        {steps.length ? (
          <ul className="flex list-disc flex-col gap-1 pl-4 text-soft">
            {steps.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ul>
        ) : null}
        {plan.text ? <p className="text-soft">{plan.text}</p> : null}
        {channels.length ? (
          <span className="text-[11.5px] text-muted">
            {t.flows.report}{" "}
            {channels.map((c, i) => (
              <span key={c.url}>
                {i ? ", " : ""}
                <a href={c.url} target="_blank" rel="noreferrer">
                  {c.name}
                </a>
              </span>
            ))}
          </span>
        ) : null}
      </div>
    );
  };

  const row = (label: string, render: (flow: (typeof FLOWS)[number]) => React.ReactNode, last = false) => (
    <tr className={last ? "" : "border-b border-line"}>
      <th className={`${cell} label text-left font-medium`}>{label}</th>
      {FLOWS.map((flow) => (
        <td key={flow} className={cell}>
          {render(flow)}
        </td>
      ))}
    </tr>
  );

  return (
    <div>
      <SectionTitle aside={`${t.flows.outputNote} · ${t.flows.history(f.num(d1History))} · ${t.flows.since(f.date(outputs[0].recorded_at))}`}>{t.flows.title}</SectionTitle>
      <div className="card overflow-x-auto">
        <table className="w-full min-w-[760px] table-fixed border-collapse text-[13px]">
          <thead>
            <tr className="border-b border-line text-left">
              <th className="label w-[150px] px-3 py-2.5 font-medium" />
              {FLOWS.map((flow) => (
                <th key={flow} className="px-3 py-2.5 font-medium" style={{ borderTop: `2px solid ${FLOW_TONE[flow]}` }}>
                  <span className="flex flex-col gap-0.5">
                    <span className="font-mono text-[12px] font-semibold" style={{ color: FLOW_TONE[flow] }}>
                      {flow}
                    </span>
                    <span className="text-[13px] text-fg">{t.flows.names[flow]}</span>
                    <span className="text-[11.5px] font-normal text-muted">{latest[flow] ? f.date(latest[flow].recorded_at) : t.flows.empty}</span>
                    {parseJson<{ demo?: boolean }>(latest[flow]?.basis)?.demo ? <DemoChip lang={lang} /> : null}
                    {flow === "D2" ? (
                      <Link href={`${L(lang, "/survey")}?id=${encodeURIComponent(incidentId)}`} className="text-[11.5px] font-normal">
                        {t.flows.judge}
                      </Link>
                    ) : null}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {row(t.flows.audience, (flow) => chips(plans[flow]?.audience, audienceText))}
            {row(t.flows.topics, (flow) => topicsCell(plans[flow]))}
            {row(t.flows.rows.prevention, (flow) => stepsCell(plans[flow]))}
            {row(
              t.flows.rows.reason,
              (flow) => {
                const o = latest[flow];
                if (!o?.reason) return empty;
                return (
                  <span className="flex flex-col gap-1">
                    <span className="text-soft">{o.reason}</span>
                    {flow === "D4" ? (
                      <Link href={`${L(lang, "/verify")}?q=${recordUid(o.output_id, o.output_hash)}`} className="text-[11.5px]">
                        {t.flows.verifyRecord}
                      </Link>
                    ) : null}
                    {hostOf(o.source_ref) ? (
                      <a href={o.source_ref ?? "#"} target="_blank" rel="noreferrer" className="text-[11.5px]">
                        {hostOf(o.source_ref)}
                      </a>
                    ) : null}
                  </span>
                );
              },
              true,
            )}
          </tbody>
        </table>
      </div>
      <p className="mt-2 flex flex-wrap gap-x-3 text-[12px] text-muted">
        {!latest.D2 && !latest.D3 && !latest.D4 ? <span>{t.flows.pending}</span> : null}
        <Link href={L(lang, "/comparison")}>{t.flows.summary}</Link>
      </p>
    </div>
  );
}
