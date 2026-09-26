"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

export type NewsItem = {
  id: number;
  title: string;
  domain: string;
  date: string;
  type: string;
  language: string;
  href: string;
  image: string; // /api/og/<id>: gambar artikel (og:image) atau pengganti
};

const STEP_MS = 3400;

/**
 * Slider berita: kartu bergambar (og:image artikel, logo media di pojok)
 * yang bergeser satu kartu setiap beberapa detik, berhenti saat disorot,
 * dengan tombol sebelumnya/berikutnya. Loop mulus dengan salinan kartu awal.
 */
export function NewsSlider({ items, prevLabel, nextLabel }: { items: NewsItem[]; prevLabel: string; nextLabel: string }) {
  const [idx, setIdx] = useState(0);
  const [noAnim, setNoAnim] = useState(false);
  const paused = useRef(false);
  const clones = Math.min(3, items.length);
  const all = items.length ? [...items, ...items.slice(0, clones)] : [];

  useEffect(() => {
    if (items.length <= 3) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const id = window.setInterval(() => {
      if (!paused.current) setIdx((v) => v + 1);
    }, STEP_MS);
    return () => clearInterval(id);
  }, [items.length]);

  // Setelah menggeser ke kartu salinan, lompat diam-diam ke awal.
  const onTransitionEnd = () => {
    if (idx >= items.length) {
      setNoAnim(true);
      setIdx(idx - items.length);
      window.setTimeout(() => setNoAnim(false), 40);
    }
  };
  const step = (d: number) => {
    setIdx((v) => {
      const n = v + d;
      return n < 0 ? items.length - 1 : n;
    });
  };

  if (!items.length) return null;
  return (
    <div className="relative" onMouseEnter={() => (paused.current = true)} onMouseLeave={() => (paused.current = false)}>
      <div className="-mx-1.5 overflow-hidden">
        <div className={`news-track ${noAnim ? "no-anim" : ""}`} style={{ "--idx": idx } as React.CSSProperties} onTransitionEnd={onTransitionEnd}>
          {all.map((it, i) => (
            <div key={`${it.id}-${i}`} className="news-card px-1.5" aria-hidden={i >= items.length}>
              <Link href={it.href} className="card lift row-link flex h-full flex-col overflow-hidden">
                <span className="relative block aspect-[16/9] w-full overflow-hidden bg-nav">
                  <Image src={it.image} alt="" fill unoptimized sizes="(min-width: 1024px) 33vw, (min-width: 640px) 50vw, 100vw" className="object-cover" />
                  <span className="absolute inset-x-0 bottom-0 h-16 bg-gradient-to-t from-[rgba(11,18,25,0.92)] to-transparent" aria-hidden="true" />
                  <span className="absolute bottom-2.5 left-2.5 flex items-center gap-2">
                    <span className="inline-flex h-7 w-7 items-center justify-center overflow-hidden rounded-md border border-line bg-nav">
                      <Image src={`https://www.google.com/s2/favicons?domain=${encodeURIComponent(it.domain)}&sz=64`} alt="" width={18} height={18} unoptimized loading="lazy" />
                    </span>
                    <span className="max-w-[220px] truncate font-mono text-[11px] text-fg">{it.domain}</span>
                  </span>
                  <span className="absolute bottom-2.5 right-2.5 font-mono text-[10.5px] text-soft">{it.date}</span>
                </span>
                <span className="flex flex-1 flex-col gap-1.5 p-3">
                  <span className="line-clamp-2 text-[13.5px] font-semibold leading-snug">{it.title}</span>
                  <span className="mt-auto truncate font-mono text-[10.5px] text-accent">
                    {it.type} · {it.language}
                  </span>
                </span>
              </Link>
            </div>
          ))}
        </div>
      </div>
      <div className="mt-2 flex items-center justify-end gap-1.5">
        <button type="button" onClick={() => step(-1)} className="btn btn-ghost px-3 py-1.5 text-[12px]" aria-label={prevLabel}>
          ←
        </button>
        <button type="button" onClick={() => step(1)} className="btn btn-ghost px-3 py-1.5 text-[12px]" aria-label={nextLabel}>
          →
        </button>
      </div>
    </div>
  );
}
