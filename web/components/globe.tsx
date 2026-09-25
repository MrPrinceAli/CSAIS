"use client";

import createGlobe from "cobe";
import { useEffect, useRef } from "react";

export type GlobeMarker = { location: [number, number]; size: number };

/** Globe WebGL (cobe v2) dengan penanda incident per negara; berputar pelan, diam saat reduced motion, bisa diseret. */
export function Globe({ markers, label }: { markers: GlobeMarker[]; label: string }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const pointerStart = useRef<number | null>(null);
  const drag = useRef(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    let phi = 3.9;
    let width = canvas.offsetWidth || 400;
    let raf = 0;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const onResize = () => {
      width = canvas.offsetWidth || width;
    };
    window.addEventListener("resize", onResize);
    const globe = createGlobe(canvas, {
      devicePixelRatio: Math.min(2, window.devicePixelRatio || 1),
      width: width * 2,
      height: width * 2,
      phi,
      theta: 0.22,
      dark: 1,
      diffuse: 1.4,
      mapSamples: 18000,
      mapBrightness: 4.5,
      baseColor: [0.16, 0.22, 0.3],
      markerColor: [0.18, 0.72, 0.79],
      glowColor: [0.06, 0.16, 0.22],
      markers,
    });
    const frame = () => {
      if (!reduce && pointerStart.current === null) phi += 0.0025;
      globe.update({ phi: phi + drag.current, width: width * 2, height: width * 2 });
      raf = requestAnimationFrame(frame);
    };
    raf = requestAnimationFrame(frame);
    return () => {
      cancelAnimationFrame(raf);
      globe.destroy();
      window.removeEventListener("resize", onResize);
    };
  }, [markers]);

  return (
    <canvas
      ref={canvasRef}
      role="img"
      aria-label={label}
      className="h-full w-full cursor-grab active:cursor-grabbing"
      style={{ contain: "layout paint size" }}
      onPointerDown={(e) => {
        pointerStart.current = e.clientX - drag.current * 200;
      }}
      onPointerUp={() => {
        pointerStart.current = null;
      }}
      onPointerOut={() => {
        pointerStart.current = null;
      }}
      onPointerMove={(e) => {
        if (pointerStart.current !== null) drag.current = (e.clientX - pointerStart.current) / 200;
      }}
    />
  );
}
