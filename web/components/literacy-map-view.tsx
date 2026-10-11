"use client";

/*
 * Bagian interaktif Peta Literasi: warna provinsi mengikuti jumlah incident
 * (atau incident yang membutuhkan satu sasaran/materi bila disaring), sorot
 * dengan tooltip, klik untuk panel rincian, dan tabel ringkas untuk pembaca
 * layar dan perencanaan program.
 */
import Link from "next/link";
import { useMemo, useState } from "react";

export type Item = { label: string; n: number };
export type ProvinceStat = {
  code: string;
  name: string;
  d: string;
  n: number;
  byAudience: Record<string, number>;
  byTopic: Record<string, number>;
  audiences: Item[];
  topics: Item[];
  types: Item[];
  cities: Item[];
  samples: { id: string; title: string; date: string; tier: string | null }[];
};
type Option = { key: string; label: string; n: number };
type Strings = {
  audience: string;
  topic: string;
  all: string;
  incidents: string; // label setelah angka, mis. "incident"
  legend: string;
  none: string;
  pick: string;
  topAudience: string;
  topTopics: string;
  topTypes: string;
  cities: string;
  samples: string;
  table: string;
  cols: { province: string; incidents: string; audience: string; topic: string };
  tiers: Record<string, string>;
  empty: string;
  showAll: string;
};

// Gradasi biru satu warna, gelap = sedikit, terang = banyak (lolos validasi kontras tema gelap)
const RAMP = ["#184f95", "#256abf", "#3987e5", "#6da7ec", "#b7d3f6"];
const NO_DATA = "#1c2836";
const TABLE_ROWS = 10;

/** Batas kelas: 5 kelas dari 1 sampai nilai terbesar, tanpa batas ganda. */
function breaksFor(max: number): number[] {
  if (max <= 5) return Array.from({ length: Math.max(max, 1) }, (_, i) => i + 1);
  const raw = [1, max * 0.15, max * 0.35, max * 0.6, max * 0.85].map((v) => Math.max(1, Math.round(v)));
  return [...new Set(raw)];
}

function classOf(value: number, breaks: number[]): number {
  let index = -1;
  breaks.forEach((b, i) => {
    if (value >= b) index = i;
  });
  return index;
}

export function LiteracyMapView({
  width,
  height,
  stats,
  audienceOptions,
  topicOptions,
  incidentHref,
  strings,
}: {
  width: number;
  height: number;
  stats: ProvinceStat[];
  audienceOptions: Option[];
  topicOptions: Option[];
  incidentHref: string;
  strings: Strings;
}) {
  const [audience, setAudience] = useState("");
  const [topic, setTopic] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const [hover, setHover] = useState<{ code: string; x: number; y: number } | null>(null);
  const [allRows, setAllRows] = useState(false);

  const valueOf = useMemo(
    () => (s: ProvinceStat) => (audience ? (s.byAudience[audience] ?? 0) : topic ? (s.byTopic[topic] ?? 0) : s.n),
    [audience, topic],
  );
  const max = Math.max(0, ...stats.map(valueOf));
  const breaks = breaksFor(max);
  const ramp = RAMP.slice(RAMP.length - breaks.length);
  const fill = (s: ProvinceStat) => {
    const c = classOf(valueOf(s), breaks);
    return c < 0 ? NO_DATA : ramp[c];
  };
  const ranked = [...stats].filter((s) => valueOf(s) > 0).sort((a, b) => valueOf(b) - valueOf(a) || a.name.localeCompare(b.name));
  const current = stats.find((s) => s.code === (selected ?? ranked[0]?.code)) ?? null;
  const hovered = hover ? stats.find((s) => s.code === hover.code) : null;

  const list = (title: string, items: Item[]) =>
    items.length ? (
      <div className="flex flex-col gap-1.5">
        <span className="label">{title}</span>
        <ul className="flex flex-col gap-1">
          {items.map((item) => (
            <li key={item.label} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-2 text-[13px]">
              <span className="text-soft">{item.label}</span>
              <span className="tnum font-mono text-[12px] text-muted">{item.n}</span>
            </li>
          ))}
        </ul>
      </div>
    ) : null;

  const select = (id: string, label: string, value: string, onChange: (v: string) => void, options: Option[]) => (
    <label htmlFor={id} className="flex min-w-0 flex-col gap-1 text-[12px] text-muted">
      {label}
      <select id={id} value={value} onChange={(e) => onChange(e.target.value)} className="field max-w-[340px] text-[13px]">
        <option value="">{strings.all}</option>
        {options.map((o) => (
          <option key={o.key} value={o.key}>
            {o.label} ({o.n})
          </option>
        ))}
      </select>
    </label>
  );

  return (
    <div className="flex flex-col gap-4" id="peta-literasi">
      <div className="flex flex-wrap items-end gap-3">
        {select("lm-audience", strings.audience, audience, (v) => {
          setAudience(v);
          setTopic("");
        }, audienceOptions)}
        {select("lm-topic", strings.topic, topic, (v) => {
          setTopic(v);
          setAudience("");
        }, topicOptions)}
      </div>

      <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="card relative p-2">
          <svg viewBox={`0 0 ${width} ${height}`} className="block h-auto w-full" role="img" aria-label={strings.table}>
            {stats.map((s) => (
              <path
                key={s.code}
                d={s.d}
                fill={fill(s)}
                stroke={s.code === current?.code ? "var(--fg)" : "var(--bg)"}
                strokeWidth={s.code === current?.code ? 1.6 : 0.6}
                className="cursor-pointer outline-none transition-[fill] focus-visible:stroke-[var(--accent)]"
                tabIndex={0}
                aria-label={`${s.name}: ${`${valueOf(s)} ${strings.incidents}`}`}
                onMouseMove={(e) => {
                  const box = (e.currentTarget.ownerSVGElement as SVGSVGElement).getBoundingClientRect();
                  setHover({ code: s.code, x: e.clientX - box.left, y: e.clientY - box.top });
                }}
                onMouseLeave={() => setHover(null)}
                onClick={() => setSelected(s.code)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    setSelected(s.code);
                  }
                }}
              />
            ))}
          </svg>
          {hovered && hover ? (
            <div
              className="pointer-events-none absolute z-10 rounded-md border border-line bg-[var(--nav)] px-2.5 py-1.5 text-[12px] shadow-lg"
              style={hover.x > 520 ? { right: `calc(100% - ${hover.x - 14}px)`, top: hover.y + 14 } : { left: hover.x + 14, top: hover.y + 14 }}
            >
              <span className="block font-semibold text-fg">{hovered.name}</span>
              <span className="text-soft">{`${valueOf(hovered)} ${strings.incidents}`}</span>
              {hovered.audiences[0] ? <span className="block text-muted">{hovered.audiences[0].label}</span> : null}
            </div>
          ) : null}
          <div className="flex flex-wrap items-center gap-3 px-2 pb-1 pt-2 text-[11.5px] text-muted">
            <span>{strings.legend}</span>
            <span className="flex items-center gap-1.5">
              <span className="inline-block h-3 w-4 rounded-sm border border-line" style={{ background: NO_DATA }} aria-hidden="true" />
              {strings.none}
            </span>
            {breaks.map((b, i) => (
              <span key={b} className="flex items-center gap-1.5">
                <span className="inline-block h-3 w-4 rounded-sm" style={{ background: ramp[i] }} aria-hidden="true" />
                <span className="tnum font-mono">
                  {b}
                  {i === breaks.length - 1 ? "+" : breaks[i + 1] - 1 > b ? `–${breaks[i + 1] - 1}` : ""}
                </span>
              </span>
            ))}
          </div>
        </div>

        <aside className="card flex flex-col gap-4 p-4">
          {current && valueOf(current) > 0 ? (
            <>
              <header className="flex flex-col gap-0.5">
                <h3 className="text-[17px] font-semibold">{current.name}</h3>
                <span className="text-[12.5px] text-muted">{current.n} {strings.incidents}</span>
              </header>
              {list(strings.topAudience, current.audiences)}
              {list(strings.topTopics, current.topics)}
              {list(strings.topTypes, current.types)}
              {current.cities.length ? (
                <div className="flex flex-col gap-1.5">
                  <span className="label">{strings.cities}</span>
                  <span className="flex flex-wrap gap-1.5">
                    {current.cities.map((c) => (
                      <span key={c.label} className="chip">
                        {c.label} <span className="font-mono text-muted">{c.n}</span>
                      </span>
                    ))}
                  </span>
                </div>
              ) : null}
              {current.samples.length ? (
                <div className="flex flex-col gap-1.5 border-t border-line pt-3">
                  <span className="label">{strings.samples}</span>
                  <ul className="flex flex-col gap-2">
                    {current.samples.map((s) => (
                      <li key={s.id} className="flex flex-col gap-0.5">
                        <Link href={`${incidentHref}${s.id}`} className="line-clamp-2 text-[13px] font-semibold leading-snug text-fg no-underline hover:text-accent">
                          {s.title}
                        </Link>
                        <span className="text-[11.5px] text-muted">
                          {s.date}
                          {s.tier ? ` · ${strings.tiers[s.tier] ?? s.tier}` : ""}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </>
          ) : (
            <p className="text-[13px] text-muted">{ranked.length ? strings.pick : strings.empty}</p>
          )}
        </aside>
      </div>

      {ranked.length ? (
        <div className="card overflow-x-auto">
          <table className="w-full min-w-[640px] border-collapse text-[13px]">
            <caption className="label px-3 pt-3 text-left">{strings.table}</caption>
            <thead>
              <tr className="label border-b border-line text-left">
                <th className="px-3 py-2 font-medium">{strings.cols.province}</th>
                <th className="px-3 py-2 font-medium">{strings.cols.incidents}</th>
                <th className="px-3 py-2 font-medium">{strings.cols.audience}</th>
                <th className="px-3 py-2 font-medium">{strings.cols.topic}</th>
              </tr>
            </thead>
            <tbody>
              {(allRows ? ranked : ranked.slice(0, TABLE_ROWS)).map((s) => (
                <tr key={s.code} className={`border-b border-line last:border-0 ${s.code === current?.code ? "bg-[color-mix(in_srgb,var(--accent)_8%,transparent)]" : ""}`}>
                  <td className="px-3 py-2">
                    <button type="button" className="text-left font-semibold text-fg hover:text-accent" onClick={() => setSelected(s.code)}>
                      {s.name}
                    </button>
                  </td>
                  <td className="tnum px-3 py-2 font-mono">{valueOf(s)}</td>
                  <td className="px-3 py-2 text-soft">{s.audiences.slice(0, 2).map((a) => a.label).join(", ") || "–"}</td>
                  <td className="px-3 py-2 text-soft">{s.topics.slice(0, 2).map((a) => a.label).join(", ") || "–"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!allRows && ranked.length > TABLE_ROWS ? (
            <button type="button" className="btn btn-ghost m-3 text-[13px]" onClick={() => setAllRows(true)}>
              {strings.showAll} ({ranked.length})
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
