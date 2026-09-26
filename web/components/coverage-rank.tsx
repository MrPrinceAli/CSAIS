import Link from "next/link";
import { glyphFor, IncidentThumb } from "@/components/incident-thumb";
import { SourceLogo } from "@/components/ui";
import type { Publisher } from "@/lib/publishers";

export type RankItem = {
  id: string;
  href: string;
  title: string;
  type: string;
  attackType: string | null;
  articles: number;
  publishers: Publisher[];
};

type Labels = { articles: string; publishers: string; note: string };

/** Sian (liputan lebih sempit) -> kuning tembaga -> merah (terluas); t = 0..1. */
function heatColor(t: number): string {
  const stops: [number, number, number][] = [
    [47, 183, 201],
    [240, 168, 96],
    [242, 84, 88],
  ];
  const x = Math.min(1, Math.max(0, t)) * 2;
  const [a, b] = x <= 1 ? [stops[0], stops[1]] : [stops[1], stops[2]];
  const k = x <= 1 ? x : x - 1;
  return `rgb(${a.map((v, i) => Math.round(v + (b[i] - v) * k)).join(", ")})`;
}

/**
 * Peringkat liputan terluas di panel dasbor incident: nomor peringkat, warna
 * kotak dan batang yang makin panas untuk liputan yang makin luas (relatif ke
 * peringkat 1), foto berita, label jenis serangan berwarna, dan tiga logo
 * penerbit plus penanda "+N".
 */
export function CoverageRank({ items, labels, num }: { items: RankItem[]; labels: Labels; num: (n: number) => string }) {
  const max = Math.max(1, ...items.map((x) => x.articles));
  return (
    <ol className="cc-list cc-feed cc-scroll" aria-label={labels.note}>
      {items.map((item, i) => {
        // akar kuadrat: peringkat 1 yang jauh lebih besar tidak membuat sisanya pudar semua
        const heat = Math.sqrt(item.articles / max);
        const shown = item.publishers.slice(0, 3);
        const more = Math.max(0, item.publishers.length - shown.length);
        return (
          <li key={item.id}>
            <Link href={item.href} scroll={false} className={`cc-rank row-link${i < 3 ? " is-top" : ""}`} style={{ "--heat": heat.toFixed(3), "--c": heatColor(heat) } as React.CSSProperties}>
              <span className="cc-rank-n" aria-label={`#${i + 1}`}>
                {String(i + 1).padStart(2, "0")}
              </span>
              <IncidentThumb id={item.id} attackType={item.attackType} className="aspect-square w-full" />
              <span className="flex min-w-0 flex-col gap-1">
                <span className="line-clamp-2 text-[13px] font-semibold leading-snug">{item.title}</span>
                <span className="type-chip" style={{ "--tone": glyphFor(item.attackType).tone } as React.CSSProperties}>
                  {item.type}
                </span>
                <span className="flex items-center justify-between gap-2">
                  <span className="flex min-w-0 items-center">
                    {shown.map((p, k) => (
                      <span key={p.name} className={k ? "-ml-1.5" : ""} style={{ zIndex: 3 - k }} title={p.name}>
                        {p.domain ? (
                          <SourceLogo domain={p.domain} size={12} />
                        ) : (
                          <span className="cov-mono" style={{ width: 20, height: 20, fontSize: 8.5 }}>
                            {p.name.replace(/[^\p{L}\p{N}]/gu, "").slice(0, 2)}
                          </span>
                        )}
                      </span>
                    ))}
                    {more > 0 ? <span className="cc-rank-more">+{num(more)}</span> : null}
                  </span>
                  <span className="whitespace-nowrap font-mono text-[11px] text-soft" title={`${num(item.articles)} ${labels.articles} · ${num(item.publishers.length)} ${labels.publishers}`}>
                    {num(item.articles)} <span className="text-muted">{labels.articles}</span>
                  </span>
                </span>
                <span className="cc-rank-bar" aria-hidden="true">
                  <i style={{ width: `${Math.max(4, Math.round(heat * 100))}%` }} />
                </span>
              </span>
            </Link>
          </li>
        );
      })}
    </ol>
  );
}
