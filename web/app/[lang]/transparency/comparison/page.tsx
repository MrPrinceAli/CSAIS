import type { Metadata } from "next";
import { notFound } from "next/navigation";
import type { ReactNode } from "react";
import { getFlowMetrics, type FlowMetric } from "@/lib/queries";
import { formatters } from "@/lib/format";
import { getDict, isLang } from "@/lib/i18n";
import { SectionTitle } from "@/components/ui";

type Params = { lang: string };

// Metrik dihitung pipeline sekali sehari; tanpa ini halaman dirender statis saat build
export const revalidate = 3600;

export async function generateMetadata({ params }: { params: Promise<Params> }): Promise<Metadata> {
  const { lang } = await params;
  return { title: getDict(isLang(lang) ? lang : "id").comparison.title };
}

const FLOWS = ["D1", "D2", "D3", "D4"] as const;
const FIELDS = ["attack_type", "target", "threat_actor", "attack_date", "location"] as const;
const LEVELS = ["tinggi", "sedang", "rendah", "tanpa_skor"] as const;
const FLOW_TONE: Record<string, string> = { D1: "var(--accent)", D2: "var(--med)", D3: "var(--chain)", D4: "var(--good)" };

/** Ringkasan metrik perbandingan alur D1 - D4 untuk seluruh incident (tabel flow_metrics). */
export default async function ComparisonPage({ params }: { params: Promise<Params> }) {
  const { lang } = await params;
  if (!isLang(lang)) notFound();
  const t = getDict(lang);
  const c = t.comparison;
  const f = formatters(lang);
  const metrics = await getFlowMetrics();
  const find = (metric: string, flow: string, field = "") => metrics.find((m) => m.metric === metric && m.flow === flow && m.field === field);

  const ratio = (m?: FlowMetric) => (m && m.value !== null ? f.score(m.value) : "–");
  const count = (m?: FlowMetric) => (m && m.value !== null ? f.num(m.value) : "–");
  const pct = (m?: FlowMetric) => {
    if (!m || m.value === null) return "–";
    const digits = m.value > 0 && m.value < 0.01 ? 3 : 1;
    return `${(100 * m.value).toLocaleString(lang === "id" ? "id-ID" : "en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits })}%`;
  };
  const n = (m?: FlowMetric) => <span className="font-mono text-[11.5px] text-muted">n={m ? f.num(m.n) : 0}</span>;
  const th = "px-3 py-2 text-left font-medium";
  const td = "px-3 py-2 tnum";

  const table = (head: ReactNode[], rows: ReactNode[][]) => (
    <div className="card overflow-x-auto">
      <table className="w-full min-w-[560px] border-collapse text-[13px]">
        <thead>
          <tr className="label border-b border-line">
            {head.map((h, i) => (
              <th key={i} className={th}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="border-b border-line last:border-0">
              {row.map((cell, j) => (
                <td key={j} className={j === 0 ? "px-3 py-2" : td}>
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );

  const both = (m?: FlowMetric) => (
    <span className="flex items-baseline gap-2">
      <span>{ratio(m)}</span>
      {n(m)}
    </span>
  );

  return (
    <div className="flex flex-col gap-7 py-8">
      <header className="flex max-w-[76ch] flex-col gap-2">
        <h1 className="text-balance text-[28px] font-semibold leading-tight">{c.title}</h1>
        <p className="text-[14px] leading-relaxed text-soft">{c.lead}</p>
        {metrics.length ? <span className="text-[12px] text-muted">{c.computed(f.dateTime(metrics[0].computed_at))}</span> : null}
      </header>

      {!metrics.length ? (
        <p className="card p-5 text-[14px] text-soft">{c.empty}</p>
      ) : (
        <>
          <section>
            <SectionTitle>{c.sections.coverage}</SectionTitle>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
              {FLOWS.map((flow) => {
                const total = find("cakupan", flow);
                return (
                  <div key={flow} className="card flex flex-col gap-1 p-4" style={{ borderTop: `2px solid ${FLOW_TONE[flow]}` }}>
                    <span className="font-mono text-[12px] font-semibold" style={{ color: FLOW_TONE[flow] }}>
                      {flow} · {t.flows.names[flow]}
                    </span>
                    <span className="tnum text-[24px] font-semibold">{count(total)}</span>
                    <span className="text-[12px] text-muted">{flow === "D1" ? t.common.incidents : c.share(pct(find("cakupan_porsi", flow)))}</span>
                  </div>
                );
              })}
            </div>
          </section>

          <div className="grid gap-6 lg:grid-cols-2">
            <section className="min-w-0">
              <SectionTitle aside={c.sections.accuracyNote}>{c.sections.accuracy}</SectionTitle>
              {table(
                [c.cols.field, c.cols.precision, c.cols.recall, c.cols.f1, "n"],
                FIELDS.map((field) => [
                  t.flows.rows[field],
                  ratio(find("ketepatan_precision", "D1", field)),
                  ratio(find("ketepatan_recall", "D1", field)),
                  ratio(find("ketepatan_f1", "D1", field)),
                  n(find("ketepatan_f1", "D1", field)),
                ]),
              )}
            </section>
            <section className="min-w-0">
              <SectionTitle aside={c.sections.judgmentNote}>{c.sections.judgment}</SectionTitle>
              {table(
                [c.cols.field, `D2 · ${t.flows.names.D2}`, `D3 · ${t.flows.names.D3}`],
                FIELDS.map((field) => [t.flows.rows[field], both(find("penilaian_tepat", "D2", field)), both(find("penilaian_tepat", "D3", field))]),
              )}
            </section>
            <section className="min-w-0">
              <SectionTitle>{c.sections.agreement}</SectionTitle>
              {table(
                [c.cols.field, c.cols.agree, c.cols.kappa, "n"],
                FIELDS.map((field) => [
                  t.flows.rows[field],
                  pct(find("kesepakatan_d2_d3", "D2-D3", field)),
                  ratio(find("kappa_d2_d3", "D2-D3", field)),
                  n(find("kappa_d2_d3", "D2-D3", field)),
                ]),
              )}
            </section>
            <section className="min-w-0">
              <SectionTitle aside={c.sections.speedNote}>{c.sections.speed}</SectionTitle>
              {table(
                ["", c.cols.hours, "n"],
                FLOWS.map((flow) => {
                  const m = find("kecepatan_median_jam", flow);
                  return [`${flow} · ${t.flows.names[flow]}`, m && m.value !== null ? m.value.toFixed(1) : "–", n(m)];
                }),
              )}
            </section>
            <section className="min-w-0">
              <SectionTitle>{c.sections.hoax}</SectionTitle>
              {table(
                ["", "", "n"],
                [
                  [c.hoax.refuted, count(find("hoaks_dibantah_d4", "D4")), n(find("hoaks_dibantah_d4", "D4"))],
                  [c.hoax.machine, count(find("hoaks_lolos_mesin", "D1")), n(find("hoaks_lolos_mesin", "D1"))],
                  [c.hoax.public, count(find("hoaks_lolos_publik", "D2")), n(find("hoaks_lolos_publik", "D2"))],
                ],
              )}
            </section>
            <section className="min-w-0">
              <SectionTitle>{c.sections.prevention}</SectionTitle>
              {table(
                ["", "", "n"],
                [
                  [c.prevention.jaccard, ratio(find("preventif_jaccard_d1_d4", "D1-D4")), n(find("preventif_jaccard_d1_d4", "D1-D4"))],
                  [c.prevention.added, pct(find("preventif_d4_menambah", "D4")), n(find("preventif_d4_menambah", "D4"))],
                ],
              )}
            </section>
            <section className="min-w-0 lg:col-span-2">
              <SectionTitle aside={c.sections.biasNote}>{c.sections.bias}</SectionTitle>
              {table(
                ["", c.cols.all, c.cols.reached],
                LEVELS.map((level) => [t.flows.status[level] ?? level, pct(find("bias_trust_semua", "D1", level)), pct(find("bias_trust_sampai_d4", "D1", level))]),
              )}
            </section>
          </div>
          <p className="text-[12px] text-muted">
            {c.none} {c.detailLink}
          </p>
        </>
      )}
    </div>
  );
}

