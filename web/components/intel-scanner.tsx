"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

/** Satu artikel sungguhan yang diputar di panel pemindai beranda. */
export type ScanItem = {
  title: string;
  target: string | null;
  attackLabel: string;
  attackWords: string[]; // kata yang distabilo sebagai jenis serangan
  domain: string;
  language: string;
  date: string;
  docs: number;
  incident_id: string;
  trust: number; // 0..1
  href: string;
};

export type ScanLabels = {
  live: string;
  crawl: string;
  relevance: string;
  extract: string;
  cluster: string;
  target: string;
  type: string;
  sources: string; // kata "sumber"; jumlah ditulis di depannya
  trust: string;
  open: string;
};

type Phase = "arrive" | "scan" | "extract" | "cluster";
const PHASES: { phase: Phase; at: number }[] = [
  { phase: "arrive", at: 0 },
  { phase: "scan", at: 500 },
  { phase: "extract", at: 2100 },
  { phase: "cluster", at: 3200 },
];
const CYCLE_MS = 5200;
const KEYWORDS = [
  "ransomware", "phishing", "malware", "breach", "breached", "leak", "leaked", "hack", "hacked", "hacker", "hackers",
  "ddos", "scam", "spyware", "botnet", "exploit", "zero-day", "cyberattack", "cyber", "attack", "attacks",
  "bocor", "diretas", "dibobol", "dijebol", "peretasan", "pembobolan", "kebocoran", "penipuan", "serangan", "siber",
  "retas", "bobol", "phising", "judol", "data",
];

function tokens(title: string): string[] {
  return title.split(/(\s+)/);
}

function classify(word: string, target: string | null, attackWords: string[]): "target" | "attack" | null {
  const w = word.toLowerCase().replace(/^[^\p{L}\p{N}]+|[^\p{L}\p{N}]+$/gu, "");
  if (w.length < 3) return null;
  const t = (target ?? "").toLowerCase();
  if (t && (t.split(/\s+/).includes(w) || (w.length >= 4 && t.includes(w)))) return "target";
  if (KEYWORDS.includes(w) || attackWords.includes(w)) return "attack";
  return null;
}

/** Judul dengan kata kunci distabilo (kelas .mark menyala pada fase pindai). */
function Highlighted({ item }: { item: ScanItem }) {
  const parts = useMemo(() => tokens(item.title), [item.title]);
  return (
    <span>
      {parts.map((p, i) => {
        const kind = /^\s+$/.test(p) ? null : classify(p, item.target, item.attackWords);
        if (!kind) return <span key={i}>{p}</span>;
        return (
          <span key={i} className={`mark ${kind === "target" ? "mark-accent" : ""}`}>
            {p}
          </span>
        );
      })}
    </span>
  );
}

function pct(v: number): number {
  return Math.round(Math.min(1, Math.max(0, v)) * 100);
}

/**
 * Panel "pemindai": memutar artikel sungguhan lewat empat fase (masuk, dipindai,
 * diekstrak, dikelompokkan) dengan log ala terminal. Tanpa gerak: fase akhir
 * artikel pertama saja.
 */
export function IntelScanner({ items, labels, stamp, reduceMotion = false }: { items: ScanItem[]; labels: ScanLabels; stamp: string; reduceMotion?: boolean }) {
  const [index, setIndex] = useState(0);
  const [phase, setPhase] = useState<Phase>(reduceMotion ? "cluster" : "arrive");
  const [animate, setAnimate] = useState(false);

  useEffect(() => {
    if (!items.length) return;
    const reduce = reduceMotion || window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let timers: number[] = [];
    if (reduce) {
      // tanpa gerak: langsung ke fase akhir (lewat timer agar tidak setState sinkron di effect)
      timers.push(window.setTimeout(() => setPhase("cluster"), 0));
      return () => timers.forEach(clearTimeout);
    }
    let cycle = 0;
    const run = () => {
      timers.forEach(clearTimeout);
      timers = PHASES.map((p) =>
        window.setTimeout(() => {
          if (p.at === 0) setAnimate(true);
          setPhase(p.phase);
        }, p.at),
      );
      timers.push(
        window.setTimeout(() => {
          cycle += 1;
          setIndex(cycle % items.length);
          run();
        }, CYCLE_MS),
      );
    };
    run();
    return () => timers.forEach(clearTimeout);
  }, [items.length, reduceMotion]);

  if (!items.length) return null;
  const item = items[index];
  const stage = PHASES.findIndex((p) => p.phase === phase);
  const next = items[(index + 1) % items.length];
  const after = items[(index + 2) % items.length];

  const logs: { k: string; text: string; tone: string }[] = [
    { k: "crawl", text: `${labels.crawl} · ${item.domain}`, tone: "text-muted" },
    { k: "v02", text: `V0.2 ${labels.relevance} ✓ ${item.language}`, tone: "text-soft" },
    { k: "v03", text: `V0.3 ${labels.extract}: ${item.target ?? "—"} · ${item.attackLabel}`, tone: "text-accent" },
    { k: "v05", text: `V0.5 ${labels.cluster}: ${item.incident_id.replace("INCIDENT_", "#")} · ${item.docs} ${labels.sources}`, tone: "text-chain" },
  ].slice(0, stage + 1);

  return (
    <div className={`card corners relative flex flex-col gap-3 overflow-hidden p-4 grid-bg phase-${phase}`} aria-live="off">
      <div className="flex items-center justify-between gap-3 font-mono text-[11px] text-muted">
        <span className="inline-flex items-center gap-2">
          <span className="led led-accent" aria-hidden="true" />
          {labels.live}
        </span>
        <span>{stamp}</span>
      </div>

      {/* antrean artikel berikutnya */}
      <div className="flex flex-col gap-1.5" aria-hidden="true">
        {[after, next].map((q, i) => (
          <div key={`${q.incident_id}-${i}`} className="h-8 truncate rounded-md border border-line/70 bg-bg/60 px-3 py-1.5 text-[12px] leading-[1.35] text-muted" style={{ opacity: 0.35 + i * 0.25 }}>
            {q.title}
          </div>
        ))}
      </div>

      {/* kartu aktif */}
      <div key={`${item.incident_id}-${index}`} className={`relative rounded-md border border-line-2 bg-bg p-3.5 ${animate ? "fade-in" : ""}`}>
        <div className="beam" aria-hidden="true" />
        <div className="mb-1.5 flex items-center justify-between gap-2 font-mono text-[10.5px] text-muted">
          <span className="truncate">{item.domain}</span>
          <span>{item.date}</span>
        </div>
        <p className="line-clamp-2 min-h-[2.7em] text-[14.5px] font-semibold leading-snug">
          <Highlighted item={item} />
        </p>
        <div className={`mt-3 flex h-[26px] flex-nowrap gap-1.5 overflow-hidden ${stage >= 2 ? "" : "invisible"}`}>
          {[
            { k: "type", label: labels.type, value: item.attackLabel, cls: "" },
            { k: "target", label: labels.target, value: item.target ?? "—", cls: "chip-accent" },
          ].map((c, i) => (
            <span key={c.k} className={`chip ${c.cls} ${stage >= 2 && animate ? "fade-in" : ""}`} style={{ "--i": i } as React.CSSProperties}>
              <span className="text-muted">{c.label}</span> {c.value}
            </span>
          ))}
        </div>
        <div className={`mt-3 flex h-[34px] items-center justify-between gap-3 border-t border-line pt-2.5 ${stage >= 3 ? (animate ? "fade-in" : "") : "invisible"}`}>
          <span className="flex items-center gap-2 font-mono text-[11.5px] text-chain">
            <span className="led" aria-hidden="true" />
            {item.incident_id.replace("INCIDENT_", "#")} · {item.docs} {labels.sources}
          </span>
          <span className="flex items-center gap-2 text-[11.5px] text-muted">
            {labels.trust}
            <span className="relative block h-1.5 w-16 overflow-hidden rounded-sm bg-line">
              <span className="block h-full bg-accent" style={{ width: `${pct(item.trust)}%`, transition: "width 0.9s cubic-bezier(0.2,0.7,0.2,1)" }} />
            </span>
            <span className="tnum font-mono text-fg">{pct(item.trust)}</span>
          </span>
        </div>
      </div>

      {/* log terminal: tinggi tetap empat baris agar panel tidak berubah ukuran */}
      <div className="flex h-[4.8em] flex-col gap-0.5 overflow-hidden font-mono text-[11px] leading-[1.15]">
        {logs.map((l, i) => (
          <span key={l.k} className={`${l.tone} ${animate ? "fade-in" : ""} truncate`} style={{ "--i": 0 } as React.CSSProperties}>
            <span className="text-line-2">{String(i + 1).padStart(2, "0")}</span> {l.text}
            {i === logs.length - 1 ? <span className="caret" /> : null}
          </span>
        ))}
      </div>
      <Link href={item.href} className="self-end text-[12px] no-underline">
        {labels.open} →
      </Link>
    </div>
  );
}
