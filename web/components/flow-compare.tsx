/* Perbandingan keluaran alur D1 - D4 satu incident: snapshot terakhir tiap alur berdampingan. */
import type { FlowOutput } from "@/lib/queries";
import { formatters } from "@/lib/format";
import { attackLabel, getDict, groupLabel, type Lang } from "@/lib/i18n";
import { channelOf, tipText } from "@/lib/prevention";
import { SectionTitle } from "@/components/ui";

const FLOWS = ["D1", "D2", "D3", "D4"] as const;
const FIELDS = ["attack_type", "target", "threat_actor", "attack_date", "location", "target_group"] as const;
type Field = (typeof FIELDS)[number];

const FLOW_TONE: Record<string, string> = { D1: "var(--accent)", D2: "var(--med)", D3: "var(--chain)", D4: "var(--good)" };
const TIER_CLASS: Record<string, string> = {
  peringatan_dini: "text-accent",
  waspada: "text-med",
  rekomendasi_resmi: "text-good",
  peringatan_hoaks: "text-high",
};
const STATUS_CLASS: Record<string, string> = {
  sesuai: "text-good",
  dikonfirmasi: "text-good",
  tidak_sesuai: "text-high",
  dibantah: "text-high",
  sebagian: "text-med",
};

function parse<T>(raw: string | null): T | null {
  if (!raw) return null;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

/** Nama host tautan sumber pernyataan; null bila bukan URL http(s). */
function hostOf(ref: string | null): string | null {
  if (!ref || !/^https?:\/\//.test(ref)) return null;
  try {
    return new URL(ref).hostname;
  } catch {
    return null;
  }
}

function valueLabel(field: Field, value: string | null, lang: Lang): string | null {
  if (!value) return null;
  if (field === "attack_type") return [...new Set(value.split(",").map((v) => attackLabel(v, lang)))].join(", ");
  if (field === "target_group") return groupLabel(value, lang);
  if (field === "location") return value.split(",").map((v) => v.trim().replace(/^./, (c) => c.toUpperCase())).join(", ");
  return value;
}

export function FlowCompare({ lang, outputs }: { lang: Lang; outputs: FlowOutput[] }) {
  const t = getDict(lang);
  const f = formatters(lang);
  const latest: Partial<Record<(typeof FLOWS)[number], FlowOutput>> = {};
  for (const o of outputs) if (o.status !== "dihapus") latest[o.flow] = o;
  const d1History = outputs.filter((o) => o.flow === "D1").length;
  if (!latest.D1) return null;

  const cell = "px-3 py-2.5 align-top";
  const empty = <span className="text-muted">–</span>;

  const fieldCell = (o: FlowOutput | undefined, field: Field) => {
    if (!o) return empty;
    const label = valueLabel(field, o[field], lang);
    const judged = parse<Record<string, string>>(o.field_status)?.[field];
    return (
      <div className="flex flex-col gap-0.5">
        <span className={label ? "text-fg" : "text-muted"}>{label ?? t.common.unknown}</span>
        {judged ? <span className={`text-[11.5px] ${STATUS_CLASS[judged] ?? "text-muted"}`}>{t.flows.status[judged] ?? judged}</span> : null}
      </div>
    );
  };

  const preventionCell = (o: FlowOutput | undefined) => {
    const plan = parse<{ steps?: string[]; channels?: string[]; text?: string }>(o?.prevention ?? null);
    if (!plan) return empty;
    const steps = (plan.steps ?? []).map((k) => tipText(k, lang)).filter((s): s is string => Boolean(s));
    const channels = (plan.channels ?? []).map(channelOf).filter((c) => c !== null);
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

  return (
    <div>
      <SectionTitle aside={`${t.flows.note} · ${t.flows.history(f.num(d1History))} · ${t.flows.since(f.date(outputs[0].recorded_at))}`}>{t.flows.title}</SectionTitle>
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
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {FIELDS.map((field) => (
              <tr key={field} className="border-b border-line">
                <th className={`${cell} label text-left font-medium`}>{t.flows.rows[field]}</th>
                {FLOWS.map((flow) => (
                  <td key={flow} className={cell}>
                    {fieldCell(latest[flow], field)}
                  </td>
                ))}
              </tr>
            ))}
            <tr className="border-b border-line">
              <th className={`${cell} label text-left font-medium`}>{t.flows.rows.status}</th>
              {FLOWS.map((flow) => {
                const o = latest[flow];
                return (
                  <td key={flow} className={cell}>
                    {o ? <span className={STATUS_CLASS[o.status] ?? "text-soft"}>{t.flows.status[o.status] ?? o.status}</span> : empty}
                  </td>
                );
              })}
            </tr>
            <tr className="border-b border-line">
              <th className={`${cell} label text-left font-medium`}>{t.flows.rows.tier}</th>
              {FLOWS.map((flow) => {
                const tier = latest[flow]?.tier;
                return (
                  <td key={flow} className={cell}>
                    {tier ? <span className={`font-semibold ${TIER_CLASS[tier] ?? ""}`}>{t.flows.tiers[tier] ?? tier}</span> : empty}
                  </td>
                );
              })}
            </tr>
            <tr className="border-b border-line">
              <th className={`${cell} label text-left font-medium`}>{t.flows.rows.prevention}</th>
              {FLOWS.map((flow) => (
                <td key={flow} className={cell}>
                  {preventionCell(latest[flow])}
                </td>
              ))}
            </tr>
            <tr>
              <th className={`${cell} label text-left font-medium`}>{t.flows.rows.reason}</th>
              {FLOWS.map((flow) => {
                const o = latest[flow];
                return (
                  <td key={flow} className={cell}>
                    {o?.reason ? (
                      <span className="flex flex-col gap-1">
                        <span className="text-soft">{o.reason}</span>
                        {hostOf(o.source_ref) ? (
                          <a href={o.source_ref ?? "#"} target="_blank" rel="noreferrer" className="text-[11.5px]">
                            {hostOf(o.source_ref)}
                          </a>
                        ) : null}
                      </span>
                    ) : (
                      empty
                    )}
                  </td>
                );
              })}
            </tr>
          </tbody>
        </table>
      </div>
      {!latest.D2 && !latest.D3 && !latest.D4 ? <p className="mt-2 text-[12px] text-muted">{t.flows.pending}</p> : null}
    </div>
  );
}
