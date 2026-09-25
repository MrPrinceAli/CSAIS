"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";

/** Bungkus bagian yang muncul saat digulir ke layar (sekali saja). */
export function Reveal({ children, className = "", delay = 0 }: { children: ReactNode; className?: string; delay?: number }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (!("IntersectionObserver" in window)) {
      el.classList.add("is-visible");
      return;
    }
    const io = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            el.classList.add("is-visible");
            io.disconnect();
          }
        }
      },
      { rootMargin: "0px 0px -10% 0px", threshold: 0.12 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);
  return (
    <div ref={ref} className={`reveal ${className}`} style={delay ? { transitionDelay: `${delay}ms` } : undefined}>
      {children}
    </div>
  );
}

const fmt = new Intl.NumberFormat("id-ID");

/**
 * Angka yang naik dari 0 ke nilai akhir saat terlihat. Nilai akhir dirender di
 * server (tanpa JavaScript tetap terbaca); animasi mengubah teks langsung di DOM.
 */
export function CountUp({ value, duration = 1400, className = "" }: { value: number; duration?: number; className?: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce || !("IntersectionObserver" in window)) return;
    let raf = 0;
    const io = new IntersectionObserver((entries) => {
      if (!entries.some((e) => e.isIntersecting)) return;
      io.disconnect();
      const start = performance.now();
      const tick = (now: number) => {
        const t = Math.min(1, (now - start) / duration);
        const eased = 1 - Math.pow(1 - t, 3);
        el.textContent = fmt.format(Math.round(value * eased));
        if (t < 1) raf = requestAnimationFrame(tick);
      };
      el.textContent = fmt.format(0);
      raf = requestAnimationFrame(tick);
    });
    io.observe(el);
    return () => {
      io.disconnect();
      cancelAnimationFrame(raf);
    };
  }, [value, duration]);
  return (
    <span ref={ref} className={`tnum ${className}`}>
      {fmt.format(value)}
    </span>
  );
}

/** Rel bab di sisi kiri: menandai bab yang sedang dibaca. */
export function StoryRail({ chapters }: { chapters: { id: string; label: string }[] }) {
  const [active, setActive] = useState(chapters[0]?.id ?? "");
  useEffect(() => {
    if (!("IntersectionObserver" in window)) return;
    const io = new IntersectionObserver(
      (entries) => {
        const visible = entries.filter((e) => e.isIntersecting).sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
        if (visible) setActive(visible.target.id);
      },
      { threshold: [0.25, 0.5, 0.75] },
    );
    for (const c of chapters) {
      const el = document.getElementById(c.id);
      if (el) io.observe(el);
    }
    return () => io.disconnect();
  }, [chapters]);
  return (
    <nav className="fixed left-3 top-1/2 z-10 hidden -translate-y-1/2 flex-col gap-2 xl:flex" aria-label="Bab cerita">
      {chapters.map((c) => (
        <a
          key={c.id}
          href={`#${c.id}`}
          className={`group flex items-center gap-2 no-underline ${active === c.id ? "text-accent" : "text-muted hover:text-soft"}`}
          aria-current={active === c.id ? "true" : undefined}
        >
          <span className={`h-2 w-2 rounded-full ${active === c.id ? "bg-accent" : "bg-line-2"}`} aria-hidden="true" />
          <span className="text-[11px] opacity-0 transition-opacity group-hover:opacity-100 group-focus:opacity-100">{c.label}</span>
        </a>
      ))}
    </nav>
  );
}
