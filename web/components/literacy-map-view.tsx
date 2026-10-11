"use client";

/*
 * Bagian interaktif Peta Literasi: warna provinsi mengikuti jumlah incident
 * (atau incident yang membutuhkan satu sasaran/materi bila disaring), sorot
 * dengan tooltip, klik untuk panel rincian, dan tabel ringkas untuk pembaca
 * layar dan perencanaan program.
 */
import Link from "next/link";
import type { AiAdvice } from "@/lib/queries";
import { useEffect, useMemo, useRef, useState } from "react";

export type Item = { label: string; n: number };
export type ProvinceStat = {
  code: string;
  name: string;
  d: string;
  c: [number, number];
  n: number;
  byAudience: Record<string, number>;
  byTopic: Record<string, number>;
  audiences: Item[];
  topics: Item[];
  types: Item[];
  cities: Item[];
  samples: { id: string; title: string; date: string; tier: string | null }[];
  traits: { label: string; reason: string; example: { id: string; title: string; place: string } | null }[];
  ai: { audience: string; message: string; flows: string[]; model: string } | null;
  recAudiences: string[];
  recTopics: string[];
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
  cols: {
    province: string;
    incidents: string;
    audience: string;
    topic: string;
  };
  tiers: Record<string, string>;
  empty: string;
  detail: string;
  recommend: string;
  noLocal: string;
  profile: string;
  example: string;
  zoomIn: string;
  zoomOut: string;
  zoomReset: string;
  zoomHint: string;
  ai: { badge: string; region: string; targets: string; topics: string; steps: string; key: string; age: string; note: string };
  listTitle: string;
  listHint: string;
  close: string;
  loading: string;
  compareTitle: string;
  flowNames: Record<string, string>;
  noFlow: Record<string, string>;
  ruleBased: string;
  localCases: string;
  recommendation: string;
};

const FLOWS = ["D1", "D2", "D3", "D4"] as const;
const FLOW_TONE: Record<string, string> = { D1: "var(--accent)", D2: "var(--med)", D3: "var(--chain)", D4: "var(--good)" };

type FlowAdvice = { flow: string; model: string; advice: AiAdvice };

/** Pop-up satu provinsi: profil wilayah dan rekomendasi AI D1 - D4 berdampingan (dimuat dari /api/literacy/[kode]). */
function ProvinceModal({ stat, onClose, strings, incidentHref }: { stat: ProvinceStat; onClose: () => void; strings: Strings; incidentHref: string }) {
  const [flows, setFlows] = useState<FlowAdvice[] | null>(null);
  useEffect(() => {
    let alive = true;
    fetch(`/api/literacy/${stat.code}`)
      .then((r) => r.json())
      .then((data: { flows?: FlowAdvice[] }) => alive && setFlows(data.flows ?? []))
      .catch(() => alive && setFlows([]));
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => {
      alive = false;
      window.removeEventListener("keydown", onKey);
    };
  }, [stat.code, onClose]);
  const byFlow = Object.fromEntries((flows ?? []).map((f) => [f.flow, f.advice]));
  const model = flows?.[0]?.model;

  const advice = (a: AiAdvice) => (
    <div className="flex flex-col gap-2 text-[12.5px]">
      {a.ringkasan ? <p className="leading-snug text-soft">{a.ringkasan}</p> : null}
      <span className="label">{strings.ai.targets}</span>
      <ul className="flex flex-col gap-1">
        {a.sasaran.map((t) => (
          <li key={t.kelompok} className="rounded-md border border-line px-2 py-1">
            <span className="block font-semibold leading-snug text-fg">{t.kelompok}</span>
            {t.usia || t.wilayah ? <span className="block text-[11px] text-accent">{[t.usia && `${strings.ai.age} ${t.usia}`, t.wilayah].filter(Boolean).join(" · ")}</span> : null}
          </li>
        ))}
      </ul>
      <span className="label">{strings.ai.topics}</span>
      <ol className="flex list-decimal flex-col gap-0.5 pl-4 text-soft">
        {a.materi.map((m) => (
          <li key={m}>{m}</li>
        ))}
      </ol>
      <span className="label">{strings.ai.steps}</span>
      <ul className="flex list-disc flex-col gap-0.5 pl-4 text-soft">
        {a.langkah.map((m) => (
          <li key={m}>{m}</li>
        ))}
      </ul>
      {a.pesan_kunci ? <p className="border-l-2 border-chain pl-2 font-semibold leading-snug text-fg">“{a.pesan_kunci}”</p> : null}
    </div>
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-3 backdrop-blur-sm" role="dialog" aria-modal="true" aria-label={stat.name} onClick={onClose}>
      <div
        className="flex max-h-[92svh] w-full max-w-[1280px] flex-col overflow-hidden rounded-2xl border border-line bg-[var(--surface)] shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex flex-wrap items-start justify-between gap-3 border-b border-line px-5 py-3.5">
          <div className="flex min-w-0 flex-col gap-1">
            <span className="label text-accent">{strings.compareTitle}</span>
            <h3 className="text-[22px] font-semibold leading-tight">{stat.name}</h3>
            <span className="text-[12px] text-muted">
              {Math.max(1, stat.ai?.flows.length ?? 0)} {strings.recommendation}
              {stat.n > 0 ? ` · ${stat.n} ${strings.incidents}` : ""} · {stat.traits.map((t) => t.label).join(" · ")}
            </span>
          </div>
          <button type="button" onClick={onClose} className="btn btn-ghost text-[13px]" aria-label={strings.close}>
            ✕ {strings.close}
          </button>
        </header>
        <div className="flex min-h-0 flex-col gap-4 overflow-y-auto px-5 py-4">
          {flows === null ? (
            <p className="text-[13px] text-muted">{strings.loading}</p>
          ) : (
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              {FLOWS.map((flow) => (
                <section key={flow} className="flex flex-col gap-2 rounded-xl border border-line p-3" style={{ borderTop: `2px solid ${FLOW_TONE[flow]}` }}>
                  <span className="font-mono text-[12px] font-semibold" style={{ color: FLOW_TONE[flow] }}>
                    {flow} · <span className="font-sans text-fg">{strings.flowNames[flow]}</span>
                  </span>
                  {byFlow[flow] ? (
                    advice(byFlow[flow])
                  ) : flow === "D1" ? (
                    <div className="flex flex-col gap-1.5 text-[12.5px]">
                      <span className="text-[11.5px] text-muted">{strings.ruleBased}</span>
                      <span className="text-soft">{stat.recAudiences.join(", ")}</span>
                      <ol className="flex list-decimal flex-col gap-0.5 pl-4 text-soft">
                        {stat.recTopics.map((t) => (
                          <li key={t}>{t}</li>
                        ))}
                      </ol>
                    </div>
                  ) : (
                    <p className="text-[12px] leading-snug text-muted">{strings.noFlow[flow]}</p>
                  )}
                </section>
              ))}
            </div>
          )}
          <div className="grid gap-4 border-t border-line pt-3 md:grid-cols-2">
            <div className="flex flex-col gap-2">
              <span className="label">{strings.profile}</span>
              {stat.traits.map((trait) => (
                <p key={trait.label} className="text-[12px] leading-snug text-soft">
                  <span className="font-semibold text-fg">{trait.label}.</span> {trait.reason}
                  {trait.example ? (
                    <>
                      {" "}
                      <span className="text-muted">
                        {strings.example} ({trait.example.place}):{" "}
                      </span>
                      <Link href={`${incidentHref}${trait.example.id}`} className="text-accent no-underline hover:underline">
                        {trait.example.title}
                      </Link>
                    </>
                  ) : null}
                </p>
              ))}
            </div>
            <div className="flex flex-col gap-2">
              <span className="label">{strings.localCases}</span>
              {stat.samples.length ? (
                <ul className="flex flex-col gap-1.5">
                  {stat.samples.map((s) => (
                    <li key={s.id} className="text-[12px]">
                      <Link href={`${incidentHref}${s.id}`} className="font-semibold text-fg no-underline hover:text-accent">
                        {s.title}
                      </Link>{" "}
                      <span className="text-muted">{s.date}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-[12px] text-muted">{strings.noLocal}</p>
              )}
              {stat.cities.length ? <p className="text-[11.5px] text-muted">{stat.cities.map((c) => `${c.label.replace(/^(Kabupaten|Kota) /, "")} (${c.n})`).join(", ")}</p> : null}
            </div>
          </div>
          {model ? <p className="text-[11px] text-muted">✦ {strings.ai.note.replace("{model}", model)}</p> : null}
        </div>
      </div>
    </div>
  );
}

type View = { k: number; x: number; y: number };
const HOME: View = { k: 1, x: 0, y: 0 };
const MAX_ZOOM = 8;

// Gradasi biru satu warna, gelap = sedikit, terang = banyak (lolos validasi kontras tema gelap)
const RAMP = ["#184f95", "#256abf", "#3987e5", "#6da7ec", "#b7d3f6"];
const NO_DATA = "#1c2836";
const LABELS = 5; // provinsi teratas yang diberi label nama dan angka

/** Batas kelas: 5 kelas dari 1 sampai nilai terbesar, tanpa batas ganda. */
function breaksFor(max: number): number[] {
  if (max <= 5) return Array.from({ length: Math.max(max, 1) }, (_, i) => i + 1);
  const raw = [1, max * 0.15, max * 0.35, max * 0.6, max * 0.85].map((v) => Math.max(1, Math.round(v)));
  return [...new Set(raw)];
}

type Placed = {
  s: ProvinceStat;
  x: number;
  y: number;
  w: number;
  above: boolean;
};

/**
 * Letak label provinsi teratas: bergantian di atas dan di bawah titik pusatnya,
 * lalu digeser ke kanan dalam barisnya agar tidak saling menimpa.
 */
function placeLabels(items: { s: ProvinceStat; text: string }[], width: number, height: number): Placed[] {
  const sorted = [...items].sort((a, b) => a.s.c[0] - b.s.c[0]);
  const rows: Record<"above" | "below", number> = {
    above: -Infinity,
    below: -Infinity,
  };
  return sorted.map(({ s, text }, i) => {
    const above = i % 2 === 0;
    const w = text.length * 7.4 + 22;
    const key = above ? "above" : "below";
    let x = Math.min(Math.max(s.c[0] - w / 2, 4), width - w - 4);
    x = Math.max(x, rows[key] + 6);
    rows[key] = x + w;
    const y = above ? Math.max(s.c[1] - 58, 4) : Math.min(s.c[1] + 34, height - 26);
    return { s, x, y, w, above };
  });
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
  listOrder,
}: {
  width: number;
  height: number;
  stats: ProvinceStat[];
  audienceOptions: Option[];
  topicOptions: Option[];
  incidentHref: string;
  strings: Strings;
  listOrder: string[]; // urutan acak daftar provinsi, diacak di server per permintaan
}) {
  const [audience, setAudience] = useState("");
  const [topic, setTopic] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const [hover, setHover] = useState<{ code: string; x: number; y: number; w: number } | null>(null);
  const [view, setView] = useState<View>(HOME);
  const svgRef = useRef<SVGSVGElement>(null);
  const drag = useRef<{ x: number; y: number; view: View; moved: boolean } | null>(null);

  /** Titik layar -> koordinat viewBox SVG. */
  const toSvg = (clientX: number, clientY: number) => {
    const svg = svgRef.current;
    const matrix = svg?.getScreenCTM();
    if (!svg || !matrix) return { x: width / 2, y: height / 2 };
    const point = new DOMPoint(clientX, clientY).matrixTransform(matrix.inverse());
    return { x: point.x, y: point.y };
  };
  /** Zoom dengan faktor ``factor`` di titik viewBox ``at`` (default tengah peta). */
  const zoomBy = (factor: number, at = { x: width / 2, y: height / 2 }) =>
    setView((v) => {
      const k = Math.min(MAX_ZOOM, Math.max(1, v.k * factor));
      if (k === 1) return HOME;
      const r = k / v.k;
      return { k, x: at.x - (at.x - v.x) * r, y: at.y - (at.y - v.y) * r };
    });

  // Ctrl/⌘ + gulir (dan cubit di trackpad) untuk zoom; gulir biasa tetap menggulir halaman
  useEffect(() => {
    const svg = svgRef.current;
    if (!svg) return;
    const onWheel = (e: WheelEvent) => {
      if (!e.ctrlKey && !e.metaKey) return;
      e.preventDefault();
      const matrix = svg.getScreenCTM();
      const at = matrix ? new DOMPoint(e.clientX, e.clientY).matrixTransform(matrix.inverse()) : { x: width / 2, y: height / 2 };
      zoomBy(Math.exp(-e.deltaY * 0.004), { x: at.x, y: at.y });
    };
    svg.addEventListener("wheel", onWheel, { passive: false });
    return () => svg.removeEventListener("wheel", onWheel);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [width, height]);

  const valueOf = useMemo(() => (s: ProvinceStat) => (audience ? (s.byAudience[audience] ?? 0) : topic ? (s.byTopic[topic] ?? 0) : s.n), [audience, topic]);
  const max = Math.max(0, ...stats.map(valueOf));
  const breaks = breaksFor(max);
  const ramp = RAMP.slice(RAMP.length - breaks.length);
  const fill = (s: ProvinceStat) => {
    const c = classOf(valueOf(s), breaks);
    return c < 0 ? NO_DATA : ramp[c];
  };
  const ranked = [...stats].filter((s) => valueOf(s) > 0).sort((a, b) => valueOf(b) - valueOf(a) || a.name.localeCompare(b.name));
  const current = selected ? (stats.find((s) => s.code === selected) ?? null) : null;
  const labelled = ranked.slice(0, LABELS);
  const glowing = new Set(stats.filter((s) => classOf(valueOf(s), breaks) >= breaks.length - 2 && valueOf(s) > 0).map((s) => s.code));
  const hovered = hover ? stats.find((s) => s.code === hover.code) : null;

  const select = (id: string, label: string, value: string, onChange: (v: string) => void, options: Option[]) => (
    <label htmlFor={id} className="flex min-w-0 items-center gap-2 text-[12px] text-muted">
      <span className="whitespace-nowrap">{label}</span>
      <select id={id} value={value} onChange={(e) => onChange(e.target.value)} className="field max-w-[260px] py-1 text-[12.5px]">
        <option value="">{strings.all}</option>
        {options.map((o) => (
          <option key={o.key} value={o.key}>
            {o.label} ({o.n})
          </option>
        ))}
      </select>
    </label>
  );

  const legend = (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-muted">
      <span>{strings.legend}</span>
      <span className="flex items-center gap-1.5">
        <span className="inline-block h-2.5 w-3.5 rounded-sm border border-line" style={{ background: NO_DATA }} aria-hidden="true" />
        {strings.none}
      </span>
      {breaks.map((b, i) => (
        <span key={b} className="flex items-center gap-1.5">
          <span className="inline-block h-2.5 w-3.5 rounded-sm" style={{ background: ramp[i] }} aria-hidden="true" />
          <span className="tnum font-mono">
            {b}
            {i === breaks.length - 1 ? "+" : breaks[i + 1] - 1 > b ? `–${breaks[i + 1] - 1}` : ""}
          </span>
        </span>
      ))}
    </div>
  );

  const order = listOrder;
  const byCode = Object.fromEntries(stats.map((s) => [s.code, s]));
  const toggle = (code: string) => setSelected((prev) => (prev === code ? null : code));
  // indikator per provinsi = jumlah rekomendasi (alur D1 - D4 yang punya saran; minimal 1 dari profil wilayah)
  const recCount = (s: ProvinceStat) => Math.max(1, s.ai?.flows.length ?? 0);
  const countLabel = (s: ProvinceStat) => `${recCount(s)} ${strings.recommendation}`;

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-2" id="peta-literasi">
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
        <div className="flex flex-wrap items-center gap-3">
          {select(
            "lm-audience",
            strings.audience,
            audience,
            (v) => {
              setAudience(v);
              setTopic("");
            },
            audienceOptions,
          )}
          {select(
            "lm-topic",
            strings.topic,
            topic,
            (v) => {
              setTopic(v);
              setAudience("");
            },
            topicOptions,
          )}
        </div>
        {legend}
      </div>

      <div className="grid min-h-0 flex-1 gap-3 lg:grid-cols-[minmax(0,1fr)_330px]">
        <div className="relative min-h-0">
          <svg
            ref={svgRef}
            viewBox={`0 0 ${width} ${height}`}
            preserveAspectRatio="xMidYMid meet"
            className={`block h-auto w-full touch-none select-none lg:h-full ${view.k > 1 ? "cursor-grab active:cursor-grabbing" : ""}`}
            role="img"
            aria-label={strings.table}
            onPointerDown={(e) => {
              drag.current = { x: e.clientX, y: e.clientY, view, moved: false };
            }}
            onPointerMove={(e) => {
              const d = drag.current;
              if (!d || view.k === 1) return;
              const a = toSvg(d.x, d.y);
              const b = toSvg(e.clientX, e.clientY);
              if (Math.abs(e.clientX - d.x) + Math.abs(e.clientY - d.y) > 4) d.moved = true;
              if (d.moved) setView({ ...d.view, x: d.view.x + b.x - a.x, y: d.view.y + b.y - a.y });
            }}
            onPointerUp={() => {
              setTimeout(() => (drag.current = null), 0);
            }}
            onDoubleClick={(e) => zoomBy(2, toSvg(e.clientX, e.clientY))}
          >
            <defs>
              <filter id="lm-glow" x="-20%" y="-20%" width="140%" height="140%">
                <feGaussianBlur stdDeviation="7" result="blur" />
                <feMerge>
                  <feMergeNode in="blur" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
            </defs>
            <g transform={`translate(${view.x} ${view.y}) scale(${view.k})`}>
              {stats.map((s) => (
                <path
                  vectorEffect="non-scaling-stroke"
                  key={s.code}
                  d={s.d}
                  fill={fill(s)}
                  stroke={s.code === current?.code ? "var(--fg)" : "var(--bg)"}
                  strokeWidth={s.code === current?.code ? 1.8 : 0.6}
                  filter={glowing.has(s.code) ? "url(#lm-glow)" : undefined}
                  className="cursor-pointer outline-none transition-[fill] focus-visible:stroke-[var(--accent)]"
                  tabIndex={0}
                  aria-label={`${s.name}: ${countLabel(s)}`}
                  onMouseMove={(e) => {
                    const box = (e.currentTarget.ownerSVGElement as SVGSVGElement).getBoundingClientRect();
                    setHover({ code: s.code, x: e.clientX - box.left, y: e.clientY - box.top, w: box.width });
                  }}
                  onMouseLeave={() => setHover(null)}
                  onClick={() => {
                    if (drag.current?.moved) return; // akhir geser peta, bukan klik
                    toggle(s.code); // klik provinsi yang sama lagi = lepas pilihan
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      toggle(s.code);
                    }
                  }}
                />
              ))}
            </g>
            {placeLabels(
              labelled
                .map((s) => ({ s: { ...s, c: [s.c[0] * view.k + view.x, s.c[1] * view.k + view.y] as [number, number] }, text: `${s.name} ${valueOf(s)}` }))
                .filter(({ s }) => s.c[0] > 0 && s.c[0] < width && s.c[1] > 0 && s.c[1] < height),
              width,
              height,
            ).map(({ s, x, y, w, above }) => (
              <g key={s.code} className="pointer-events-none" aria-hidden="true">
                <line x1={s.c[0]} y1={s.c[1]} x2={x + w / 2} y2={above ? y + 24 : y} stroke="var(--fg)" strokeOpacity={0.5} strokeWidth={1} />
                <circle cx={s.c[0]} cy={s.c[1]} r={3.2} fill="var(--fg)" />
                <rect x={x} y={y} width={w} height={24} rx={12} fill="rgba(11,18,25,0.86)" stroke="var(--line-2)" />
                <text x={x + w / 2} y={y + 16} textAnchor="middle" fontSize={12.5} fontWeight={600} fill="var(--fg)">
                  {s.name} <tspan fill="var(--accent)">{valueOf(s)}</tspan>
                </text>
              </g>
            ))}
          </svg>
          <div className="absolute left-2 top-2 flex flex-col overflow-hidden rounded-lg border border-line bg-[color-mix(in_srgb,var(--bg)_75%,transparent)] backdrop-blur-sm">
            {[
              { label: "+", title: strings.zoomIn, action: () => zoomBy(1.6) },
              { label: "−", title: strings.zoomOut, action: () => zoomBy(1 / 1.6) },
              { label: "⟲", title: strings.zoomReset, action: () => setView(HOME) },
            ].map((b) => (
              <button
                key={b.title}
                type="button"
                title={b.title}
                aria-label={b.title}
                onClick={b.action}
                className="h-8 w-8 border-b border-line text-[16px] leading-none text-soft last:border-0 hover:bg-[color-mix(in_srgb,var(--accent)_15%,transparent)] hover:text-fg"
              >
                {b.label}
              </button>
            ))}
          </div>
          <span className="pointer-events-none absolute bottom-1 left-2 text-[10.5px] text-muted">{strings.zoomHint}</span>
          {hovered && hover ? (
            <div
              className="pointer-events-none absolute z-10 rounded-md border border-line bg-[var(--nav)] px-2.5 py-1.5 text-[12px] shadow-lg"
              style={hover.x > hover.w * 0.6 ? { right: `calc(100% - ${hover.x - 14}px)`, top: hover.y + 14 } : { left: hover.x + 14, top: hover.y + 14 }}
            >
              <span className="block font-semibold text-fg">{hovered.name}</span>
              <span className="text-soft">
                {countLabel(hovered)}
                {hovered.n > 0 ? ` · ${hovered.n} ${strings.incidents}` : ""}
              </span>
              {hovered.audiences[0] ? <span className="block text-muted">{hovered.audiences[0].label}</span> : null}
            </div>
          ) : null}
        </div>

        <aside className="flex min-h-0 flex-col overflow-hidden rounded-xl border border-line bg-[color-mix(in_srgb,var(--bg)_62%,transparent)] backdrop-blur-sm">
          <div className="border-b border-line px-4 py-2.5">
            <span className="label text-accent">{strings.listTitle}</span>
            <p className="text-[11.5px] text-muted">{strings.listHint}</p>
          </div>
          <ul className="flex min-h-0 flex-1 flex-col overflow-y-auto">
            {order.map((code) => {
              const s = byCode[code];
              return (
                <li key={code}>
                  <button
                    type="button"
                    onClick={() => toggle(code)}
                    className={`flex w-full flex-col gap-1 border-b border-line px-4 py-2.5 text-left transition-colors hover:bg-[color-mix(in_srgb,var(--accent)_8%,transparent)] ${selected === code ? "bg-[color-mix(in_srgb,var(--accent)_12%,transparent)]" : ""}`}
                  >
                    <span className="flex items-baseline justify-between gap-2">
                      <span className="flex items-baseline gap-2">
                        <span className="text-[13.5px] font-semibold text-fg">{s.name}</span>
                        <span className="font-mono text-[11px] text-muted">{countLabel(s)}</span>
                      </span>
                      <span className="flex gap-1">
                        {(s.ai?.flows ?? []).map((flow) => (
                          <span key={flow} className="rounded px-1 font-mono text-[10px] font-semibold" style={{ color: FLOW_TONE[flow], border: `1px solid ${FLOW_TONE[flow]}` }}>
                            {flow}
                          </span>
                        ))}
                      </span>
                    </span>
                    <span className="line-clamp-2 text-[12px] leading-snug text-soft">{s.ai?.audience || s.recAudiences.slice(0, 2).join(", ")}</span>
                    {s.ai?.message ? <span className="line-clamp-1 text-[11.5px] italic text-muted">“{s.ai.message}”</span> : null}
                  </button>
                </li>
              );
            })}
          </ul>
        </aside>
      </div>
      {current ? <ProvinceModal key={current.code} stat={current} onClose={() => setSelected(null)} strings={strings} incidentHref={incidentHref} /> : null}
    </div>
  );
}
