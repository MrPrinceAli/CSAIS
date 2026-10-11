/*
 * Peta Literasi Indonesia (halaman Peringatan): per provinsi, berapa incident
 * yang diberitakan, siapa yang perlu diedukasi, dan materi apa yang dibawakan.
 * Data dari incident_regions (csais/regions.py) dan sasaran/materi literasi
 * terkini tiap incident (incident_tiers). Peta digambar di server (d3-geo);
 * interaksinya di LiteracyMapView.
 */
import Link from "next/link";
import { geoMercator, geoPath } from "d3-geo";
import type { FeatureCollection, MultiPolygon } from "geojson";
import { getLiteracyRows } from "@/lib/queries";
import { formatters, incidentTitle } from "@/lib/format";
import { attackLabel, getDict, L, type Lang } from "@/lib/i18n";
import { audienceText, topicText } from "@/lib/prevention";
import provinces from "@/lib/indonesia-provinces.json";
import { LiteracyMapView, type ProvinceStat } from "@/components/literacy-map-view";

const WIDTH = 1100;
const HEIGHT = 430;
export const PERIODS = [30, 90, 365, 0] as const;
export type Period = (typeof PERIODS)[number];

type Counted = Map<string, number>;
const bump = (map: Counted, key: string | null | undefined) => key && map.set(key, (map.get(key) ?? 0) + 1);
const top = (map: Counted, n = 5) => [...map.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])).slice(0, n);

export async function LiteracyMap({ lang, period, base }: { lang: Lang; period: Period; base: string }) {
  const t = getDict(lang);
  const m = t.literacyMap;
  const f = formatters(lang);
  const rows = await getLiteracyRows(period);

  // Agregasi per provinsi: satu incident dihitung sekali per provinsi
  type Acc = { name: string; ids: Set<string>; audiences: Counted; topics: Counted; types: Counted; cities: Counted; samples: ProvinceStat["samples"] };
  const acc = new Map<string, Acc>();
  const seen = new Set<string>();
  const nationalAudience: Counted = new Map();
  const nationalTopic: Counted = new Map();
  const counted = new Set<string>();
  for (const row of rows) {
    const p = acc.get(row.province_code) ?? { name: row.province, ids: new Set(), audiences: new Map(), topics: new Map(), types: new Map(), cities: new Map(), samples: [] as ProvinceStat["samples"] };
    acc.set(row.province_code, p);
    const cityKey = `${row.province_code}|${row.incident_id}|${row.kabkota}`;
    if (row.kabkota && !seen.has(cityKey)) {
      seen.add(cityKey);
      bump(p.cities, row.kabkota.replace(/^Kota Administrasi /, "").trim());
    }
    if (p.ids.has(row.incident_id)) continue;
    p.ids.add(row.incident_id);
    let plan: { audience?: string[]; topics?: string[] } = {};
    try {
      plan = row.prevention ? JSON.parse(row.prevention) : {};
    } catch {}
    for (const key of plan.audience ?? []) bump(p.audiences, key);
    for (const key of plan.topics ?? []) bump(p.topics, key);
    for (const type of new Set((row.attack_type ?? "").split(",").map((v) => v.trim()).filter((v) => v && v !== "unknown"))) bump(p.types, type);
    if (p.samples.length < 3) p.samples.push({ id: row.incident_id, title: incidentTitle(row.title), date: f.date(row.anchor_published_date), tier: row.tier });
    if (!counted.has(row.incident_id)) {
      counted.add(row.incident_id);
      for (const key of plan.audience ?? []) bump(nationalAudience, key);
      for (const key of plan.topics ?? []) bump(nationalTopic, key);
    }
  }

  const collection = provinces as unknown as FeatureCollection<MultiPolygon, { code: string; name: string }>;
  const projection = geoMercator().fitExtent(
    [
      [8, 8],
      [WIDTH - 8, HEIGHT - 8],
    ],
    collection,
  );
  const path = geoPath(projection);
  const stats: ProvinceStat[] = collection.features.map((feature) => {
    const code = feature.properties.code;
    const p = acc.get(code);
    return {
      code,
      name: feature.properties.name,
      d: path(feature) ?? "",
      c: path.centroid(feature).map((v) => Math.round(v)) as [number, number],
      n: p?.ids.size ?? 0,
      byAudience: Object.fromEntries(p?.audiences ?? []),
      byTopic: Object.fromEntries(p?.topics ?? []),
      audiences: top(p?.audiences ?? new Map()).map(([key, n]) => ({ label: audienceText(key, lang) ?? key, n })),
      topics: top(p?.topics ?? new Map()).map(([key, n]) => ({ label: topicText(key, lang) ?? key, n })),
      types: top(p?.types ?? new Map(), 3).map(([key, n]) => ({ label: attackLabel(key, lang), n })),
      cities: top(p?.cities ?? new Map(), 6).map(([label, n]) => ({ label, n })),
      samples: p?.samples ?? [],
    };
  });
  const options = (map: Counted, text: (key: string, lang: Lang) => string | null) =>
    top(map, 40).map(([key, n]) => ({ key, label: text(key, lang) ?? key, n }));

  const affected = stats.filter((s) => s.n > 0).length;
  const kpis = [
    { label: m.kpi.incidents, value: f.num(counted.size) },
    { label: m.kpi.provinces, value: `${f.num(affected)} / 38` },
    { label: m.kpi.audience, value: top(nationalAudience, 1).map(([k]) => audienceText(k, lang) ?? k)[0] ?? "–" },
    { label: m.kpi.topic, value: top(nationalTopic, 1).map(([k]) => topicText(k, lang) ?? k)[0] ?? "–" },
  ];

  return (
    <section className="lm-hero full-bleed -mt-14 border-b border-line lg:h-[calc(100svh-57px)] lg:min-h-[600px]" aria-labelledby="lm-title">
      <div className="mx-auto flex h-full w-full max-w-[1680px] flex-col gap-3 px-4 pb-3 pt-4 sm:px-8">
        <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-2">
          <div className="flex min-w-0 flex-col gap-0.5">
            <span className="label text-accent">{m.eyebrow}</span>
            <h2 id="lm-title" className="text-[26px] font-semibold leading-tight sm:text-[30px]">
              {m.title}
            </h2>
            <p className="max-w-[90ch] text-[13px] text-soft">
              {m.lead(f.num(counted.size))} <span className="text-muted">({m.note})</span>
            </p>
          </div>
          <nav className="flex flex-wrap items-center gap-1.5" aria-label={m.period}>
            <span className="label mr-1">{m.period}</span>
            {PERIODS.map((p) => (
              <Link key={p} href={`${base}${p === 90 ? "" : `?periode=${p}`}`} scroll={false} className={`chip no-underline ${period === p ? "chip-accent" : ""}`} aria-current={period === p ? "true" : undefined}>
                {m.periods[String(p)]}
              </Link>
            ))}
          </nav>
        </div>
        <dl className="grid grid-cols-2 gap-2 lg:grid-cols-4">
          {kpis.map((k) => (
            <div key={k.label} className="flex min-w-0 items-baseline gap-2 rounded-lg border border-line bg-[color-mix(in_srgb,var(--bg)_55%,transparent)] px-3 py-2 backdrop-blur-sm">
              <dt className="label shrink-0">{k.label}</dt>
              <dd className="truncate text-[15px] font-semibold text-fg" title={k.value}>
                {k.value}
              </dd>
            </div>
          ))}
        </dl>
        <LiteracyMapView
          width={WIDTH}
          height={HEIGHT}
          stats={stats}
          audienceOptions={options(nationalAudience, audienceText)}
          topicOptions={options(nationalTopic, topicText)}
          incidentHref={L(lang, "/incidents/")}
          strings={{
            audience: m.audience,
            topic: m.topic,
            all: m.all,
            incidents: m.incidents,
            legend: m.legend,
            none: m.none,
            pick: m.pick,
            topAudience: m.topAudience,
            topTopics: m.topTopics,
            topTypes: m.topTypes,
            cities: m.cities,
            samples: m.samples,
            table: m.table,
            cols: m.cols,
            tiers: t.flows.tiers,
            empty: m.empty,
            detail: m.detail,
          }}
        />
        <p className="text-[10.5px] leading-snug text-muted">{m.source}</p>
      </div>
    </section>
  );
}
