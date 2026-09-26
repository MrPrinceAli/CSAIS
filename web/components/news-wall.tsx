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
};

const SLOTS = 6;
const SWAP_MS = 2800;

/**
 * Dinding berita: enam kartu (logo media, judul, jenis serangan) yang berganti
 * satu per satu secara bergiliran dari umpan artikel terbaru. Tanpa gerak:
 * enam kartu pertama saja.
 */
export function NewsWall({ items }: { items: NewsItem[] }) {
  const [slots, setSlots] = useState<number[]>(() => items.slice(0, SLOTS).map((_, i) => i));
  const cursor = useRef(Math.min(SLOTS, items.length));
  const turn = useRef(0);

  useEffect(() => {
    if (items.length <= SLOTS) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const id = window.setInterval(() => {
      const slot = turn.current % SLOTS;
      const next = cursor.current % items.length;
      turn.current += 1;
      cursor.current = next + 1;
      setSlots((prev) => prev.map((v, i) => (i === slot ? next : v)));
    }, SWAP_MS);
    return () => clearInterval(id);
  }, [items.length]);

  if (!items.length) return null;
  return (
    <div className="grid gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
      {slots.map((index, slot) => {
        const it = items[index];
        if (!it) return null;
        return (
          <Link key={`${slot}-${it.id}`} href={it.href} className="card lift card-swap row-link grid h-[104px] grid-cols-[auto_minmax(0,1fr)] items-start gap-3 p-3">
            <span className="inline-flex h-10 w-10 flex-none items-center justify-center overflow-hidden rounded-md border border-line bg-nav">
              <Image src={`https://www.google.com/s2/favicons?domain=${encodeURIComponent(it.domain)}&sz=64`} alt="" width={24} height={24} unoptimized loading="lazy" />
            </span>
            <span className="flex min-w-0 flex-col gap-1">
              <span className="flex items-center justify-between gap-2 font-mono text-[10.5px] text-muted">
                <span className="truncate">{it.domain}</span>
                <span className="flex-none">{it.date}</span>
              </span>
              <span className="line-clamp-2 text-[13px] font-semibold leading-snug">{it.title}</span>
              <span className="truncate font-mono text-[10.5px] text-accent">
                {it.type} · {it.language}
              </span>
            </span>
          </Link>
        );
      })}
    </div>
  );
}
