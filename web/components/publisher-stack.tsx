"use client";

import Image from "next/image";
import { useState } from "react";
import { createPortal } from "react-dom";
import type { Publisher } from "@/lib/publishers";

const LIST_MAX = 40;
const POP_W = 280;

function Mark({ p, size }: { p: Publisher; size: number }) {
  return p.domain ? (
    <span className="pub-logo" style={{ width: size, height: size }}>
      <Image src={`https://www.google.com/s2/favicons?domain=${encodeURIComponent(p.domain)}&sz=64`} alt="" width={size - 4} height={size - 4} unoptimized loading="lazy" />
    </span>
  ) : (
    <span className="cov-mono" style={{ width: size, height: size, fontSize: size * 0.42 }}>
      {p.name.replace(/[^\p{L}\p{N}]/gu, "").slice(0, 2)}
    </span>
  );
}

/**
 * Tiga logo penerbit plus penanda "+N". Saat kursor di atasnya, daftar lengkap
 * penerbit muncul sebagai panel melayang (dirender ke body supaya tidak
 * terpotong area gulir panel dasbor).
 */
export function PublisherStack({ publishers, title, othersLabel }: { publishers: Publisher[]; title: string; othersLabel: string }) {
  const [pos, setPos] = useState<{ left: number; top?: number; bottom?: number } | null>(null);
  if (!publishers.length) return null;
  const shown = publishers.slice(0, 3);
  const more = publishers.length - shown.length;
  const open = (el: HTMLElement) => {
    const r = el.getBoundingClientRect();
    const left = Math.max(8, Math.min(r.right - POP_W, window.innerWidth - POP_W - 8));
    setPos(r.bottom > window.innerHeight * 0.6 ? { left, bottom: window.innerHeight - r.top + 6 } : { left, top: r.bottom + 6 });
  };
  return (
    <span className="pub-stack" onMouseEnter={(e) => open(e.currentTarget)} onMouseLeave={() => setPos(null)}>
      {shown.map((p, k) => (
        <span key={p.name} className={k ? "-ml-1.5" : ""} style={{ zIndex: 3 - k }}>
          <Mark p={p} size={16} />
        </span>
      ))}
      {more > 0 ? <span className="cc-rank-more">+{more}</span> : null}
      {pos
        ? createPortal(
            <div className="pub-pop" role="tooltip" style={{ ...pos, width: POP_W }}>
              <span className="cc-h">{title}</span>
              <ul>
                {publishers.slice(0, LIST_MAX).map((p) => (
                  <li key={p.name}>
                    <Mark p={p} size={16} />
                    <span className="truncate">{p.name}</span>
                  </li>
                ))}
              </ul>
              {publishers.length > LIST_MAX ? <span className="text-[11.5px] text-muted">+{publishers.length - LIST_MAX} {othersLabel}</span> : null}
            </div>,
            document.body,
          )
        : null}
    </span>
  );
}
