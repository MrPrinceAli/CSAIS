"use client";

import createGlobe, { type Arc, type Marker } from "cobe";
import { useEffect, useRef } from "react";

export type GlobePoint = { id: string; lat: number; lng: number; n: number; label: string; href: string };
export type GlobeArc = { from: [number, number]; to: [number, number]; n: number };

type Props = {
  points: GlobePoint[];
  arcs: GlobeArc[];
  focus: { lat: number; lng: number } | null;
  labels: number; // jumlah label negara teratas yang ditampilkan
  ariaLabel: string;
  readoutLabel: string;
};

/** Sudut globe (phi, theta) yang menghadapkan satu titik lintang/bujur ke penonton. */
function anglesOf(lat: number, lng: number): [number, number] {
  return [Math.PI - ((lng * Math.PI) / 180 - Math.PI / 2), (lat * Math.PI) / 180];
}

/** Warna penanda dari sian (sedikit) ke merah (banyak). */
function heat(t: number): [number, number, number] {
  const a: [number, number, number] = [0.18, 0.72, 0.79];
  const b: [number, number, number] = [0.95, 0.33, 0.35];
  return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t];
}

/**
 * Globe pusat komando (cobe v2): penanda berwarna menurut jumlah incident,
 * busur antara negara yang disebut dalam incident yang sama, label negara
 * yang menempel pada penandanya lewat CSS anchor positioning, dan HUD
 * (cincin, sapuan radar, garis pindai, angka rotasi). Berputar pelan, bisa
 * diseret, dan berputar ke negara yang sedang difilter.
 */
export function CommandGlobe({ points, arcs, focus, labels, ariaLabel, readoutLabel }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const readoutRef = useRef<HTMLSpanElement>(null);
  const dragStart = useRef<number | null>(null);
  const dragOffset = useRef(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let width = canvas.offsetWidth || 600;
    const max = Math.max(1, ...points.map((p) => p.n));
    const markers: Marker[] = points.map((p) => ({
      location: [p.lat, p.lng],
      size: 0.022 + 0.085 * Math.sqrt(p.n / max),
      color: heat(Math.sqrt(p.n / max)),
      id: p.id,
    }));
    const arcList: Arc[] = arcs.map((a, i) => ({ from: a.from, to: a.to, id: `arc${i}` }));
    const [targetPhi, targetTheta] = focus ? anglesOf(focus.lat, focus.lng) : [3.9, 0.3];
    let phi = focus ? targetPhi - 1.2 : targetPhi;
    let theta = focus ? 0.3 : targetTheta;
    let raf = 0;
    const onResize = () => {
      width = canvas.offsetWidth || width;
    };
    window.addEventListener("resize", onResize);
    const globe = createGlobe(canvas, {
      devicePixelRatio: Math.min(2, window.devicePixelRatio || 1),
      width: width * 2,
      height: width * 2,
      phi,
      theta,
      dark: 1,
      diffuse: 1.25,
      mapSamples: 26000,
      mapBrightness: 6.5,
      baseColor: [0.11, 0.18, 0.26],
      markerColor: [0.18, 0.72, 0.79],
      glowColor: [0.07, 0.26, 0.34],
      markers,
      arcs: arcList,
      arcColor: [0.66, 0.55, 0.98],
      arcWidth: 0.55,
      arcHeight: 0.32,
      markerElevation: 0.015,
    });
    const frame = () => {
      if (dragStart.current === null) {
        if (focus) {
          // meluncur ke negara terpilih, lalu melayang pelan
          phi += (targetPhi - phi) * 0.05;
          theta += (targetTheta - theta) * 0.05;
        } else if (!reduce) {
          phi += 0.0022;
        }
      }
      const current = phi + dragOffset.current;
      globe.update({ phi: current, theta, width: width * 2, height: width * 2 });
      if (readoutRef.current) {
        const deg = ((((current * 180) / Math.PI) % 360) + 360) % 360;
        readoutRef.current.textContent = `${deg.toFixed(1).padStart(5, "0")}°`;
      }
      raf = requestAnimationFrame(frame);
    };
    raf = requestAnimationFrame(frame);
    return () => {
      cancelAnimationFrame(raf);
      globe.destroy();
      window.removeEventListener("resize", onResize);
    };
  }, [points, arcs, focus]);

  return (
    <div className="cc-globe relative aspect-square w-full">
      <div className="cc-hud" aria-hidden="true">
        <span className="cc-ring cc-ring-ticks" />
        <span className="cc-ring cc-ring-dash" />
        <span className="cc-ring cc-ring-inner" />
        <span className="cc-sweep" />
        <span className="cc-scan" />
        <span className="cc-cross cc-cross-h" />
        <span className="cc-cross cc-cross-v" />
      </div>
      <canvas
        ref={canvasRef}
        role="img"
        aria-label={ariaLabel}
        className="cc-canvas h-full w-full cursor-grab active:cursor-grabbing"
        onPointerDown={(e) => {
          dragStart.current = e.clientX - dragOffset.current * 220;
        }}
        onPointerUp={() => {
          dragStart.current = null;
        }}
        onPointerOut={() => {
          dragStart.current = null;
        }}
        onPointerMove={(e) => {
          if (dragStart.current !== null) dragOffset.current = (e.clientX - dragStart.current) / 220;
        }}
      />
      {points.slice(0, labels).map((p) => (
        <a key={p.id} href={p.href} className="cc-label" style={{ "--anchor": `--cobe-${p.id}`, opacity: `var(--cobe-visible-${p.id}, 0)` } as React.CSSProperties}>
          <span className="cc-label-dot" aria-hidden="true" />
          <span className="cc-label-text">
            {p.label}
            <b>{p.n}</b>
          </span>
        </a>
      ))}
      <span className="cc-readout" aria-hidden="true">
        {readoutLabel} <span ref={readoutRef}>000.0°</span>
      </span>
    </div>
  );
}
