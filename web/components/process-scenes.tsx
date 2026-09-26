/**
 * Lima adegan "Cara kerja". Komponen server: hanya markup dan variabel CSS;
 * gerak dihitung CSS dari --p yang diisi ScrollScenes. Setiap adegan memakai
 * teknik berbeda (lihat blok "Cara kerja" di app/globals.css).
 */
import type { getDict } from "@/lib/i18n";
import { SourceLogo } from "@/components/ui";

type Labels = ReturnType<typeof getDict>["home"]["scenes"];
export type SceneStep = { tag: string; title: string; text: string };
type Common = { step: SceneStep; index: number; total: number; aiTag: string; labels: Labels };

const sv = (o: Record<string, string | number>) => o as React.CSSProperties;
const HEX = "0123456789abcdef";
const HEX3 = HEX.repeat(3);

function Meta({ index, total, tag, aiTag }: { index: number; total: number; tag: string; aiTag: string }) {
  const ai = tag === aiTag;
  return (
    <div className="flex items-center gap-3 font-mono text-[11px] text-muted">
      <span>
        {String(index + 1).padStart(2, "0")} / {String(total).padStart(2, "0")}
      </span>
      <span className={`chip ${ai ? "chip-accent" : "chip-chain"}`}>{tag}</span>
      <span className="flex gap-1" aria-hidden="true">
        {Array.from({ length: total }, (_, i) => (
          <i key={i} className={`block h-1 w-4 rounded-full ${i === index ? (ai ? "bg-accent" : "bg-chain") : "bg-line-2"}`} />
        ))}
      </span>
    </div>
  );
}

/* ------------------------------------------------------------------ 01 */
export type ClusterData = { docs: { title: string; domain: string }[]; fields: { label: string; value: string }[]; summary: string };

const SCATTER = [
  { x: -360, y: -170, z: -300, rx: 20, ry: -30, rz: -12, b: 3, f: 0.5 },
  { x: 330, y: -200, z: -150, rx: -15, ry: 25, rz: 10, b: 2, f: 0.3 },
  { x: -300, y: 170, z: -500, rx: 25, ry: 20, rz: 8, b: 4, f: 0.6 },
  { x: 360, y: 150, z: 120, rx: -20, ry: -25, rz: -9, b: 1, f: 0.1 },
  { x: 20, y: -270, z: -700, rx: 30, ry: 0, rz: 4, b: 5, f: 0.7 },
  { x: -130, y: 260, z: 200, rx: -25, ry: 15, rz: -6, b: 1.5, f: 0.1 },
  { x: 190, y: 40, z: -420, rx: 10, ry: -35, rz: 14, b: 3.5, f: 0.5 },
  { x: -210, y: -40, z: 260, rx: -12, ry: 30, rz: -15, b: 2, f: 0.2 },
];
const TAGS: [number, number][] = [
  [-250, -170],
  [250, -150],
  [-250, 170],
  [250, 160],
];

export function SceneCluster({ step, index, total, aiTag, data }: Common & { data: ClusterData }) {
  const words = step.text.split(/\s+/).filter(Boolean);
  return (
    <section data-scene className="scene scene-1 bleed s1">
      <div className="scene-pin">
        <div className="s1-floor" aria-hidden="true" />
        <div className="relative mx-auto grid h-full max-w-7xl grid-rows-[auto_minmax(0,1fr)] gap-4 px-4 py-6 sm:px-6 lg:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)] lg:grid-rows-1 lg:items-center lg:gap-10">
          <div className="relative z-10 flex flex-col gap-4">
            <Meta index={index} total={total} tag={step.tag} aiTag={aiTag} />
            <h3 className="text-[30px] font-semibold leading-[1.05] tracking-tight sm:text-[46px]">{step.title}</h3>
            <p className="max-w-[40ch] text-[15px] leading-relaxed sm:text-[17px]">
              {words.map((w, i) => (
                <span key={i} className="s1-word" style={sv({ "--t": ((i / words.length) * 0.45).toFixed(3) })}>
                  {w}
                  {i < words.length - 1 ? " " : ""}
                </span>
              ))}
            </p>
          </div>
          <div className="s1-stage h-full min-h-[260px]" aria-hidden="true">
            <div className="s1-ring" />
            {data.docs.map((d, i) => {
              const s = SCATTER[i % SCATTER.length];
              return (
                <div
                  key={i}
                  className="s1-card card flex flex-col gap-1.5 p-3"
                  style={sv({ "--i": i, "--x": `${s.x}px`, "--y": `${s.y}px`, "--z": `${s.z}px`, "--rx": `${s.rx}deg`, "--ry": `${s.ry}deg`, "--rz": `${s.rz}deg`, "--b": `${s.b}px`, "--f": s.f })}
                >
                  <span className="flex min-w-0 items-center gap-2 font-mono text-[10.5px] text-muted">
                    <SourceLogo domain={d.domain} size={12} />
                    <span className="truncate">{d.domain}</span>
                  </span>
                  <span className="line-clamp-2 text-[12.5px] font-semibold leading-snug">{d.title}</span>
                </div>
              );
            })}
            {data.fields.slice(0, 4).map((field, i) => (
              <span key={field.label} className="s1-tag chip chip-accent" style={sv({ "--tx": `${TAGS[i][0]}px`, "--ty": `${TAGS[i][1]}px` })}>
                <span className="text-muted">{field.label}</span> {field.value}
              </span>
            ))}
            <span className="s1-tag rounded-md px-2 py-1 font-mono text-[12px] text-accent" style={sv({ "--tx": "0px", "--ty": "236px" })}>
              {data.summary}
            </span>
          </div>
        </div>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ 02 */
export type EvidenceData = {
  title: string;
  domain: string;
  url: string;
  fetched: string;
  hash: string;
  leaf: { index: string; count: string; batch: number } | null;
  root: string | null;
};

const TREE_LEAVES = Array.from({ length: 8 }, (_, i) => 20 + i * 40);
const TREE_L1 = [0, 1, 2, 3].map((i) => (TREE_LEAVES[2 * i] + TREE_LEAVES[2 * i + 1]) / 2);
const TREE_L2 = [0, 1].map((i) => (TREE_L1[2 * i] + TREE_L1[2 * i + 1]) / 2);
const TREE_ROOT = (TREE_L2[0] + TREE_L2[1]) / 2;
const HL = 3; // daun artikel ini di ilustrasi pohon

function PanelHead({ n, label }: { n: number; label: string }) {
  return (
    <span className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-[0.12em] text-muted">
      <span className="text-accent">{String(n).padStart(2, "0")}</span>
      {label}
    </span>
  );
}

export function SceneEvidence({ step, index, total, aiTag, labels, data }: Common & { data: EvidenceData }) {
  const hash = (data.hash || "").toLowerCase().replace(/[^0-9a-f]/g, "").padEnd(64, "0").slice(0, 64);
  const n = 6;
  const pv = (k: number) => sv({ "--s": ((k - 0.75) / (n - 1)).toFixed(3), "--d": (0.6 / (n - 1)).toFixed(3) });
  const root = data.root ? data.root.match(/.{1,16}/g) ?? [] : [];
  const edge = (x1: number, y1: number, x2: number, y2: number, o: number, hl: boolean, key: string) => (
    <path key={key} d={`M${x1} ${y1} L${x2} ${y2}`} pathLength={1} className="s2-edge" fill="none" stroke={hl ? "var(--chain)" : "var(--line-2)"} strokeWidth={hl ? 2.2 : 1.4} style={sv({ "--o": o })} />
  );
  return (
    <section data-scene className="scene scene-2 bleed s2">
      <div className="scene-pin flex flex-col">
        <div className="relative z-10 mx-auto flex w-full max-w-7xl flex-col gap-3 px-4 pt-6 sm:px-6">
          <Meta index={index} total={total} tag={step.tag} aiTag={aiTag} />
          <h3 className="s2-title font-mono text-[24px] font-semibold leading-tight tracking-tight sm:text-[38px]">{step.title}</h3>
          <p className="max-w-[62ch] text-[14.5px] leading-relaxed text-soft">{step.text}</p>
        </div>

        <div className="relative flex min-h-0 flex-1 items-center py-4" aria-hidden="true">
          <span className="s2-bgword">sha-256 · merkle · root · block ·</span>
          <div className="s2-track">
            <div className="s2-panel" style={pv(0)}>
              <PanelHead n={1} label={labels.track[0]} />
              <div className="s2-rise overflow-hidden rounded-lg border border-line bg-surface">
                <div className="flex items-center gap-2 border-b border-line px-3 py-2 font-mono text-[10.5px] text-muted">
                  <SourceLogo domain={data.domain} size={12} />
                  <span className="truncate">{data.url}</span>
                </div>
                <div className="flex flex-col gap-2 p-3.5">
                  <span className="line-clamp-3 text-[15px] font-semibold leading-snug">{data.title}</span>
                  {[92, 100, 76, 88, 64].map((w, i) => (
                    <span key={i} className="block h-1.5 rounded-sm bg-line-2" style={{ width: `${w}%` }} />
                  ))}
                  <span className="pt-1 font-mono text-[10.5px] text-muted">
                    {labels.fetched} {data.fetched}
                  </span>
                </div>
              </div>
            </div>

            <div className="s2-panel" style={pv(1)}>
              <PanelHead n={2} label={labels.track[1]} />
              <div className="rounded-lg border border-line bg-[#070b10] p-4">
                <div className="grid gap-x-[0.45ch] gap-y-1 font-mono text-[15px] font-semibold text-accent sm:text-[17px]" style={{ gridTemplateColumns: "repeat(16, 1ch)" }}>
                  {hash.split("").map((ch, k) => (
                    <span key={k} className="s2-strip" style={sv({ "--g": HEX.indexOf(ch), "--k": k, "--r": 1 + ((k * 7) % 15) })}>
                      <span>{HEX3}</span>
                    </span>
                  ))}
                </div>
                <span className="mt-3 block font-mono text-[10.5px] text-muted">sha256(teks) · 256 bit</span>
              </div>
            </div>

            <div className="s2-panel" style={pv(2)}>
              <PanelHead n={3} label={labels.track[2]} />
              <div className="flex flex-col gap-4 rounded-lg border border-line bg-surface p-4">
                <div className="flex flex-wrap gap-2">
                  {Array.from({ length: 16 }, (_, i) => (
                    <span key={i} className={`s2-leaf ${i === 5 ? "is-hl" : ""}`} style={sv({ "--i": i })} />
                  ))}
                </div>
                <span className="font-mono text-[11px] text-soft">{data.leaf ? labels.leafOf(data.leaf.index, data.leaf.count) : labels.newLeaf}</span>
              </div>
            </div>

            <div className="s2-panel" style={pv(3)}>
              <PanelHead n={4} label={labels.track[3]} />
              <div className="rounded-lg border border-line bg-surface p-3">
                <svg viewBox="0 0 340 200" className="w-full">
                  {TREE_LEAVES.map((x, i) => edge(x, 180, TREE_L1[Math.floor(i / 2)], 124, 0, i === HL, `a${i}`))}
                  {TREE_L1.map((x, i) => edge(x, 124, TREE_L2[Math.floor(i / 2)], 70, 0.3, i === Math.floor(HL / 2), `b${i}`))}
                  {TREE_L2.map((x, i) => edge(x, 70, TREE_ROOT, 20, 0.6, i === Math.floor(HL / 4), `c${i}`))}
                  {TREE_LEAVES.map((x, i) => (
                    <rect key={`l${i}`} x={x - 7} y={173} width="14" height="14" rx="3" fill={i === HL ? "var(--accent)" : "var(--line-2)"} />
                  ))}
                  {TREE_L1.map((x, i) => (
                    <rect key={`m${i}`} className="s2-node" style={sv({ "--o": 0.3 })} x={x - 6} y={118} width="12" height="12" rx="3" fill="var(--bg)" stroke="var(--accent)" />
                  ))}
                  {TREE_L2.map((x, i) => (
                    <rect key={`n${i}`} className="s2-node" style={sv({ "--o": 0.6 })} x={x - 6} y={64} width="12" height="12" rx="3" fill="var(--bg)" stroke="var(--accent)" />
                  ))}
                  <rect className="s2-node" style={sv({ "--o": 0.85 })} x={TREE_ROOT - 9} y={11} width="18" height="18" rx="4" fill="var(--chain)" />
                </svg>
              </div>
            </div>

            <div className="s2-panel" style={pv(4)}>
              <PanelHead n={5} label={labels.track[4]} />
              <div className="s2-root flex flex-col gap-3 rounded-lg border bg-[#0b0916] p-4">
                <span className="label text-chain">{labels.root}</span>
                {root.length ? (
                  <div className="font-mono text-[13.5px] leading-6 text-chain">
                    {root.map((line) => (
                      <span key={line} className="block">
                        {line}
                      </span>
                    ))}
                  </div>
                ) : (
                  <span className="font-mono text-[13px] text-soft">{labels.notBatched}</span>
                )}
                <span className="font-mono text-[11px] text-muted">{data.leaf ? labels.batch(data.leaf.batch) : "—"}</span>
              </div>
            </div>

            <div className="s2-panel" style={pv(5)}>
              <PanelHead n={6} label={labels.track[5]} />
              <div className="flex items-center gap-2 rounded-lg border border-line bg-surface p-4">
                {[0, 1, 2].map((i) => (
                  <span key={i} className="flex h-16 w-14 flex-none flex-col justify-between rounded-md border border-line-2 bg-bg p-1.5 font-mono text-[9px] text-muted">
                    <span>{labels.block}</span>
                    <span className="block h-1 w-full rounded-sm bg-line-2" />
                    <span className="block h-1 w-2/3 rounded-sm bg-line-2" />
                  </span>
                ))}
                <span className="h-px w-4 flex-none bg-chain" />
                <span className="s2-newblock flex h-20 w-24 flex-none flex-col justify-between rounded-md border-2 border-chain bg-[#0b0916] p-2 font-mono text-[9.5px] text-chain">
                  <span>{labels.root}</span>
                  <span className="truncate">{data.root ? `${data.root.slice(0, 8)}…` : "…"}</span>
                  <span className="text-muted">{labels.pending}</span>
                </span>
              </div>
            </div>
          </div>
        </div>

        <div className="relative z-10 mx-auto w-full max-w-7xl px-4 pb-5 sm:px-6" aria-hidden="true">
          <div className="s2-rail">
            <span className="s2-rail-fill" />
          </div>
          <div className="mt-2 grid grid-cols-6 font-mono text-[10px] text-soft sm:text-[10.5px]">
            {labels.track.map((l, i) => (
              <span key={l} className="s2-tick truncate" style={sv({ "--s": (i / (n - 1) - 0.06).toFixed(3) })}>
                {l}
              </span>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ 03 */
export type TrustData = { score: number; level: string; parts: { label: string; weight: number; value: number; weightText: string; valueText: string; plus: string }[] };

const CARD_TONES = ["var(--accent)", "var(--good)", "var(--med)", "var(--chain)", "var(--high)"];

export function SceneTrust({ step, index, total, aiTag, labels, data }: Common & { data: TrustData }) {
  const vars: Record<string, string | number> = {};
  data.parts.forEach((part, i) => {
    vars[`--w${i}`] = part.weight;
    vars[`--v${i}`] = part.value.toFixed(3);
    vars[`--c${i}`] = `clamp(0, (var(--p) - ${(0.05 + i * 0.16).toFixed(2)}) / 0.16, 1)`;
  });
  return (
    <section data-scene className="scene scene-3 bleed s3" style={sv(vars)}>
      <div className="scene-pin">
        <div className="mx-auto grid h-full max-w-7xl content-center gap-6 px-4 py-6 sm:px-6 lg:grid-cols-2 lg:items-center lg:gap-14">
          <div className="flex flex-col gap-4">
            <Meta index={index} total={total} tag={step.tag} aiTag={aiTag} />
            <h3 className="text-[28px] font-semibold leading-tight tracking-tight sm:text-[40px]">{step.title}</h3>
            <p className="max-w-[46ch] text-[14.5px] leading-relaxed text-soft">{step.text}</p>
            <div className="flex items-center gap-5 pt-2">
              <div className="relative aspect-square w-[128px] flex-none sm:w-[210px]">
                <div className="s3-ticks absolute inset-0" aria-hidden="true" />
                <div className="s3-ring absolute inset-[10px]" aria-hidden="true" />
                <div className="absolute inset-0 flex flex-col items-center justify-center gap-1">
                  <span className="s3-num tnum font-mono text-[38px] font-semibold leading-none sm:text-[60px]" aria-hidden="true" />
                  <span className="sr-only">{data.score}</span>
                  <span className="s3-level font-mono text-[11px] uppercase tracking-[0.14em] text-good">{data.level}</span>
                </div>
              </div>
              <span className="max-w-[22ch] font-mono text-[11.5px] leading-relaxed text-muted">{labels.deckNote}</span>
            </div>
          </div>
          <div className="relative h-[230px] sm:h-[300px]" aria-hidden="true">
            {data.parts.map((part, i) => (
              <div
                key={part.label}
                className="s3-card card flex flex-col gap-2.5 p-4"
                style={sv({ "--c": `var(--c${i})`, "--bur": `clamp(0, (var(--p) - ${(0.21 + i * 0.16).toFixed(2)}) / 0.16, ${4 - i})`, borderTopColor: CARD_TONES[i], borderTopWidth: "3px" })}
              >
                <div className="flex items-center justify-between font-mono text-[11px] text-muted">
                  <span>0{i + 1}</span>
                  <span>
                    {labels.weight} {part.weightText}
                  </span>
                </div>
                <span className="text-[18px] font-semibold">{part.label}</span>
                <span className="block h-2 overflow-hidden rounded-sm bg-line">
                  <span className="s3-bar block h-full" style={{ width: `${Math.round(part.value * 100)}%`, background: CARD_TONES[i] }} />
                </span>
                <div className="flex items-center justify-between font-mono text-[12px]">
                  <span className="text-soft">{part.valueText}</span>
                  <span style={{ color: CARD_TONES[i] }}>{part.plus}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ 04 */
export type RiskData = {
  types: string[];
  rows: { label: string; counts: number[]; now: string; change: string; changeColor: string; levelColor: string; levelLabel: string }[];
  max: number;
};

export function SceneRisk({ step, index, total, aiTag, labels, data }: Common & { data: RiskData }) {
  const rows = data.rows.slice(0, 6);
  const cols = data.types.length;
  const cells = rows.flatMap((row, r) =>
    row.counts.map((n, c) => {
      const dx = (c + 0.5) / Math.max(1, cols) - 0.5;
      const dy = (r + 0.5) / Math.max(1, rows.length) - 0.5;
      return { key: `${r}-${c}`, n, dist: Math.min(1, Math.hypot(dx, dy) * 1.3), h: n / Math.max(1, data.max) };
    }),
  );
  return (
    <section data-scene className="scene scene-4 bleed s4">
      <div className="scene-pin">
        <div className="s4-reveal" aria-hidden="true">
          <div className="s4-rings" />
          <div className="s4-sweep" />
          <div className="relative mx-auto flex h-full max-w-7xl items-end justify-end px-4 pb-8 sm:px-6 lg:items-center">
            {rows.length ? (
              <div className="w-full max-w-[560px] lg:w-[52%]">
                <div className="grid gap-1.5" style={{ gridTemplateColumns: `minmax(64px, 1.1fr) repeat(${cols}, minmax(0, 1fr))` }}>
                  <span />
                  {data.types.map((type) => (
                    <span key={type} className="s4-fade truncate pb-1 font-mono text-[9.5px] uppercase tracking-[0.08em] text-[#f7c9cc] sm:text-[10.5px]">
                      {type}
                    </span>
                  ))}
                  {rows.map((row, r) => (
                    <div key={row.label} className="contents">
                      <span className="s4-fade truncate pr-2 text-[11.5px] leading-[34px] text-[#f7dfe0] sm:text-[12.5px] sm:leading-[40px]">{row.label}</span>
                      {row.counts.map((n, c) => {
                        const cell = cells[r * cols + c];
                        return (
                          <span key={c} className="s4-cell flex h-[34px] items-center justify-center rounded-[4px] font-mono text-[11.5px] text-white sm:h-[40px]" style={sv({ "--dist": cell.dist.toFixed(3), "--h": cell.h.toFixed(3) })}>
                            {n || "·"}
                          </span>
                        );
                      })}
                    </div>
                  ))}
                </div>
                <span className="s4-fade mt-2 block font-mono text-[10.5px] text-[#f7c9cc]">{labels.heatNote}</span>
              </div>
            ) : null}
          </div>
        </div>

        <div className="relative mx-auto flex h-full max-w-7xl flex-col gap-4 px-4 py-6 sm:px-6">
          <Meta index={index} total={total} tag={step.tag} aiTag={aiTag} />
          <h3 className="s4-title max-w-[9ch]">{step.title}</h3>
          <p className="max-w-[40ch] text-[14.5px] leading-relaxed text-soft">{step.text}</p>
          <div className="s4-rank mt-auto hidden w-full max-w-[340px] flex-col gap-2 rounded-lg border border-[rgba(242,85,90,0.35)] bg-[rgba(14,10,13,0.82)] p-3.5 backdrop-blur sm:flex">
            {rows.slice(0, 4).map((row, i) => (
              <div key={row.label} className="s4-rank-row grid grid-cols-[10px_minmax(0,1fr)_auto_auto] items-center gap-2.5 text-[12.5px]" style={sv({ "--i": i })}>
                <span className="h-2 w-2 rounded-full" style={{ background: row.levelColor }} aria-hidden="true" />
                <span className="truncate">{row.label}</span>
                <span className="tnum font-mono text-soft">{row.now}</span>
                <span className="font-mono text-[11.5px]" style={{ color: row.changeColor }}>
                  {row.change}
                </span>
              </div>
            ))}
            <span className="s4-rank-row flex items-center gap-2 border-t border-[rgba(242,85,90,0.25)] pt-2 font-mono text-[11px] text-good" style={sv({ "--i": 4 })}>
              <svg width="14" height="16" viewBox="0 0 14 16" aria-hidden="true">
                <path d="M7 1l6 3v4c0 4-3 6-6 7-3-1-6-3-6-7V4z" fill="none" stroke="currentColor" strokeWidth="1.4" />
                <path d="M4 8l2 2 4-4" fill="none" stroke="currentColor" strokeWidth="1.4" />
              </svg>
              {labels.prevention}
            </span>
          </div>
        </div>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ 05 */
export type PackageData = { week: string; findings: string[]; batches: string[]; hash: string };

export function ScenePackage({ step, index, total, aiTag, labels, data }: Common & { data: PackageData }) {
  const chars = Array.from(step.title);
  const layer = (i: number, z: number) => sv({ "--i": i, "--z": `${z}px` });
  return (
    <section data-scene className="scene scene-5 bleed s5">
      <div className="scene-pin">
        <div className="mx-auto grid h-full max-w-7xl grid-rows-[auto_minmax(0,1fr)] gap-6 px-4 py-6 sm:px-6 lg:grid-cols-[minmax(0,1.05fr)_minmax(0,0.95fr)] lg:grid-rows-1 lg:items-center">
          <div className="flex flex-col gap-4 lg:order-2">
            <Meta index={index} total={total} tag={step.tag} aiTag={aiTag} />
            <h3 className="text-[30px] font-semibold leading-tight tracking-tight sm:text-[46px]" aria-label={step.title}>
              {chars.map((ch, i) =>
                ch === " " ? (
                  " "
                ) : (
                  <span key={i} className="s5-char" aria-hidden="true" style={sv({ "--t": (0.02 + (i / chars.length) * 0.26).toFixed(3) })}>
                    {ch}
                  </span>
                ),
              )}
            </h3>
            <p className="max-w-[42ch] text-[14.5px] leading-relaxed text-soft">{step.text}</p>
            <span className="chip chip-chain self-start">{labels.preview}</span>
          </div>

          <div className="s5-scene flex min-h-0 items-center justify-center lg:order-1" aria-hidden="true">
            <div className="s5-obj">
              {/* 0: lembar temuan */}
              <div className="s5-layer flex flex-col gap-2.5 border border-[rgba(167,139,250,0.55)] bg-[#12101f] p-4 shadow-[0_30px_60px_-30px_rgba(0,0,0,0.9)]" style={layer(0, 0)}>
                <span className="s5-callout font-mono text-[10.5px] text-chain">{labels.layers[0]}</span>
                <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted">{data.week}</span>
                <span className="block h-2 w-3/4 rounded-sm bg-[rgba(230,237,243,0.85)]" />
                <div className="mt-1 flex flex-col gap-1.5">
                  {data.findings.map((line) => (
                    <span key={line} className="flex items-center gap-2 truncate text-[11px] text-soft">
                      <span className="h-1.5 w-1.5 flex-none rounded-full bg-crit" />
                      {line}
                    </span>
                  ))}
                </div>
              </div>
              {/* 1: rujukan bukti */}
              <div className="s5-layer s5-ghost" style={layer(1, 90)}>
                <span className="s5-callout font-mono text-[10.5px] text-chain">{labels.layers[1]}</span>
                <div className="absolute inset-x-4 bottom-4 flex flex-wrap gap-1.5">
                  {data.batches.map((b) => (
                    <span key={b} className="chip chip-chain bg-[#12101f] text-[10px]">
                      {b}
                    </span>
                  ))}
                </div>
              </div>
              {/* 2: tanda tangan */}
              <div className="s5-layer s5-ghost" style={layer(2, 180)}>
                <span className="s5-callout font-mono text-[10.5px] text-chain">{labels.layers[2]}</span>
                <svg viewBox="0 0 220 60" className="absolute inset-x-4 bottom-14">
                  <path className="s5-sign" pathLength={1} d="M6 44 C 22 16, 36 16, 46 38 S 72 52, 86 24 S 112 10, 120 36 S 152 50, 168 22 S 198 20, 214 40" fill="none" stroke="var(--chain)" strokeWidth="2.2" strokeLinecap="round" />
                  <line x1="6" x2="214" y1="54" y2="54" stroke="rgba(167,139,250,0.4)" />
                </svg>
              </div>
              {/* 3: segel */}
              <div className="s5-layer s5-ghost" style={layer(3, 270)}>
                <span className="s5-callout font-mono text-[10.5px] text-chain">{labels.layers[3]}</span>
                <svg viewBox="0 0 64 64" className="s5-seal absolute right-4 top-4 h-14 w-14">
                  <circle cx="32" cy="32" r="28" fill="none" stroke="#e0c93a" strokeWidth="2.4" />
                  <circle cx="32" cy="32" r="22" fill="none" stroke="#e0c93a" strokeWidth="1" strokeDasharray="3 3" />
                  <path d="M21 32l8 8 15-15" fill="none" stroke="#e0c93a" strokeWidth="3.2" strokeLinecap="round" />
                </svg>
              </div>
              {/* sisi belakang: hash paket */}
              <div className="s5-back flex flex-col justify-between border-2 border-chain bg-[#0b0916] p-4">
                <div className="flex flex-col gap-2">
                  <span className="label text-chain">{labels.backTitle}</span>
                  <span className="break-all font-mono text-[12px] leading-5 text-fg">{data.hash}</span>
                </div>
                <div className="flex flex-col gap-2">
                  <span className="font-mono text-[10.5px] text-muted">{labels.linked}</span>
                  <div className="flex flex-wrap items-center gap-1.5">
                    {data.batches.map((b, i) => (
                      <span key={b} className="flex items-center gap-1.5">
                        <span className="chip chip-chain text-[10px]">{b}</span>
                        {i < data.batches.length - 1 ? <span className="h-px w-2 bg-chain" /> : null}
                      </span>
                    ))}
                  </div>
                </div>
                <div className="s5-glow pointer-events-none absolute inset-0 rounded-[12px] shadow-[0_0_80px_-10px_rgba(167,139,250,0.7)]" />
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
