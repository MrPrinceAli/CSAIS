"use client";

import { useEffect, useRef, type ReactNode } from "react";

/**
 * Penggerak adegan "Cara kerja": untuk setiap [data-scene] di dalamnya,
 * hitung kemajuan gulir 0..1 selama panggungnya menempel (sticky) lalu tulis
 * ke --p pada elemen adegan. Semua gerak selanjutnya dihitung CSS.
 * Tinggi header diukur agar panggung menempel tepat di bawahnya (--hdr).
 * Pada prefers-reduced-motion tidak ada yang ditulis; CSS menampilkan
 * keadaan akhir tanpa pin.
 */
export function ScrollScenes({ children }: { children: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const root = ref.current;
    if (!root) return;
    const header = document.querySelector("header");
    const scenes = Array.from(root.querySelectorAll<HTMLElement>("[data-scene]"));
    let hdr = 56;
    let pins: { el: HTMLElement; pinH: number }[] = [];
    const measure = () => {
      hdr = header ? Math.round(header.getBoundingClientRect().height) : 56;
      document.documentElement.style.setProperty("--hdr", `${hdr}px`);
      pins = scenes.map((el) => ({ el, pinH: (el.firstElementChild as HTMLElement | null)?.offsetHeight ?? window.innerHeight }));
    };
    measure();
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    const last = new WeakMap<HTMLElement, string>();
    let raf = 0;
    const update = () => {
      raf = 0;
      for (const { el, pinH } of pins) {
        const rect = el.getBoundingClientRect();
        const span = rect.height - pinH;
        const p = span > 0 ? Math.min(1, Math.max(0, (hdr - rect.top) / span)) : 1;
        const value = p.toFixed(4);
        if (last.get(el) !== value) {
          last.set(el, value);
          el.style.setProperty("--p", value);
        }
      }
    };
    const schedule = () => {
      if (!raf) raf = requestAnimationFrame(update);
    };
    const onResize = () => {
      measure();
      schedule();
    };
    schedule();
    window.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", onResize);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("scroll", schedule);
      window.removeEventListener("resize", onResize);
    };
  }, []);

  return (
    <div ref={ref} className="flex flex-col">
      {children}
    </div>
  );
}
