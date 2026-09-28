import Link from "next/link";
import { glyphFor, IncidentThumb } from "@/components/incident-thumb";
import { PublisherStack } from "@/components/publisher-stack";
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

type Labels = { articles: string; publishers: string; note: string; others: string };

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
 * Peringkat liputan terluas di panel dasbor incident, ringkas tiga baris:
 * judul (dua baris) lalu satu baris jenis serangan dan logo penerbit; jumlah
 * penerbit dan artikel ada di panel daftar penerbit. Warna kotak dan garis bawah makin panas untuk incident yang
 * diberitakan lebih banyak penerbit (relatif ke peringkat 1).
 */
export function CoverageRank({ items, labels, num }: { items: RankItem[]; labels: Labels; num: (n: number) => string }) {
  const count = (x: RankItem) => Math.max(1, x.publishers.length);
  const max = Math.max(1, ...items.map(count));
  return (
    <ol className="cc-list cc-feed cc-scroll" aria-label={labels.note}>
      {items.map((item, i) => {
        // akar kuadrat: peringkat 1 yang jauh lebih besar tidak membuat sisanya pudar semua
        const heat = Math.sqrt(count(item) / max);
        const summary = `${num(item.publishers.length)} ${labels.publishers} · ${num(item.articles)} ${labels.articles}`;
        return (
          <li key={item.id}>
            <Link href={item.href} scroll={false} className={`cc-rank row-link${i < 3 ? " is-top" : ""}`} style={{ "--heat": heat.toFixed(3), "--c": heatColor(heat) } as React.CSSProperties}>
              <span className="cc-rank-n" aria-label={`#${i + 1}`}>
                {String(i + 1).padStart(2, "0")}
              </span>
              <IncidentThumb id={item.id} attackType={item.attackType} className="aspect-square w-full" />
              <span className="flex min-w-0 flex-col gap-1">
                <span className="line-clamp-2 text-[13px] font-semibold leading-snug">{item.title}</span>
                <span className="cc-rank-meta">
                  <span className="type-chip type-chip-sm" style={{ "--tone": glyphFor(item.attackType).tone } as React.CSSProperties} title={item.type}>
                    {item.type}
                  </span>
                  <PublisherStack publishers={item.publishers} title={summary} othersLabel={labels.others} />
                </span>
              </span>
              <span className="cc-rank-bar" aria-hidden="true">
                <i style={{ width: `${Math.max(4, Math.round(heat * 100))}%` }} />
              </span>
            </Link>
          </li>
        );
      })}
    </ol>
  );
}
