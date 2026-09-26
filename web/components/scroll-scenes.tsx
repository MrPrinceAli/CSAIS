"use client";

import { Children, useEffect, useRef, type ReactNode } from "react";

/**
 * Panggung "Cara kerja": satu area yang menempel (sticky) di bawah header,
 * berisi adegan-adegan yang ditumpuk. Posisi gulir di dalam bagian ini dipetakan
 * ke satuan u (0..jumlah bobot); setiap adegan i menempati [awal_i, awal_i + bobot_i].
 * Per adegan ditulis tiga variabel CSS:
 *   --p     0..1 gerak di dalam adegan (selesai sebelum transisi keluar)
 *   --enter 0..1 masuk, pada jendela transisi sebelum adegan dimulai
 *   --exit  0..1 keluar, pada jendela yang sama dengan masuknya adegan berikutnya
 * Adegan di luar jendelanya diberi data-off (tidak dilukis). Tinggi header
 * diukur ke --hdr. Pada prefers-reduced-motion tidak ada yang ditulis; CSS
 * menampilkan adegan berurutan tanpa pin.
 */
const UNIT_VH = 150; // tinggi gulir per satu bobot
const TRANSITION = 0.24; // lebar jendela transisi, dalam satuan bobot

export function ScrollScenes({ children, weights }: { children: ReactNode; weights: number[] }) {
  const ref = useRef<HTMLDivElement>(null);
  const count = Children.count(children);
  const total = weights.slice(0, count).reduce((a, b) => a + b, 0) || count;

  useEffect(() => {
    const root = ref.current;
    if (!root) return;
    const pin = root.firstElementChild as HTMLElement | null;
    if (!pin) return;
    const header = document.querySelector("header");
    const scenes = Array.from(pin.querySelectorAll<HTMLElement>(":scope > [data-scene]"));
    const bars = Array.from(pin.querySelectorAll<HTMLElement>(":scope > .scenes-progress > i"));
    const w = scenes.map((_, i) => weights[i] ?? 1);
    const starts = w.map((_, i) => w.slice(0, i).reduce((a, b) => a + b, 0));
    const sum = w.reduce((a, b) => a + b, 0);
    let hdr = 56;
    let pinH = 0;
    const measure = () => {
      hdr = header ? Math.round(header.getBoundingClientRect().height) : 56;
      document.documentElement.style.setProperty("--hdr", `${hdr}px`);
      pinH = pin.offsetHeight;
    };
    measure();
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    const cache = new Map<string, string>();
    const set = (el: HTMLElement, key: string, name: string, value: number) => {
      const v = value.toFixed(4);
      if (cache.get(key) !== v) {
        cache.set(key, v);
        el.style.setProperty(name, v);
      }
    };
    const clamp = (x: number) => Math.min(1, Math.max(0, x));
    let raf = 0;
    const update = () => {
      raf = 0;
      const rect = root.getBoundingClientRect();
      const span = rect.height - pinH;
      const u = clamp(span > 0 ? (hdr - rect.top) / span : 1) * sum;
      scenes.forEach((el, i) => {
        const last = i === scenes.length - 1;
        const s = starts[i];
        const p = clamp((u - s) / Math.max(0.01, w[i] - (last ? 0 : TRANSITION)));
        const enter = i === 0 ? 1 : clamp((u - (s - TRANSITION)) / TRANSITION);
        const exit = last ? 0 : clamp((u - (s + w[i] - TRANSITION)) / TRANSITION);
        set(el, `p${i}`, "--p", p);
        set(el, `e${i}`, "--enter", enter);
        set(el, `x${i}`, "--exit", exit);
        const off = enter <= 0 || exit >= 1;
        if (off !== el.hasAttribute("data-off")) el.toggleAttribute("data-off", off);
        if (bars[i]) set(bars[i], `f${i}`, "--f", clamp((u - s) / w[i]));
      });
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
  }, [weights]);

  return (
    <div ref={ref} className="scenes bleed" style={{ height: `calc(${Math.round(total * UNIT_VH)}vh + 100svh - var(--hdr))` }}>
      <div className="scenes-pin">
        {children}
        <div className="scenes-progress" style={{ gridTemplateColumns: weights.slice(0, count).map((x) => `${x}fr`).join(" ") }} aria-hidden="true">
          {Array.from({ length: count }, (_, i) => (
            <i key={i} />
          ))}
        </div>
      </div>
    </div>
  );
}
