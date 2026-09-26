"use client";

import { geoCentroid, geoContains, geoDistance, geoGraticule10, geoInterpolate, geoOrthographic, geoPath, geoRotation } from "d3-geo";
import type { Feature, FeatureCollection, Geometry, MultiLineString, Position } from "geojson";
import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef } from "react";
import { feature, mesh } from "topojson-client";
import type { GeometryCollection, Topology } from "topojson-specification";

export type GlobePoint = { id: string; num: string; iso: string; lat: number; lng: number; n: number; label: string; href: string; active: boolean };
export type GlobeArc = { from: [number, number]; to: [number, number]; n: number };

type Props = {
  points: GlobePoint[];
  arcs: GlobeArc[];
  focus: { lat: number; lng: number; num: string } | null;
  labels: number; // jumlah label negara teratas yang ditampilkan
  ariaLabel: string;
  readoutLabel: string;
  zoomLabel: string;
  hint: { filter: string; clear: string; help: string };
};

type Country = { f: Feature<Geometry, { name: string }>; id: string; c: [number, number]; r: number };
type Layer = { countries: Country[]; byId: Map<string, Country>; borders: MultiLineString; coast: MultiLineString };
type View = { lam: number; phi: number; k: number };

const TAU = Math.PI * 2;
const START: View = { lam: -112, phi: -6, k: 1 }; // Asia Tenggara menghadap penonton
const SPIN = 0.005; // derajat per milidetik saat berputar sendiri
const DETAIL_FROM = 1.6; // mulai perbesaran ini peta 1:50 juta dipakai

/** Setiap titik koordinat poligon (Polygon/MultiPolygon). */
function eachPosition(g: Geometry, fn: (p: Position) => void) {
  if (g.type === "Polygon") g.coordinates.forEach((ring) => ring.forEach(fn));
  else if (g.type === "MultiPolygon") g.coordinates.forEach((poly) => poly.forEach((ring) => ring.forEach(fn)));
}

function buildLayer(raw: unknown): Layer {
  const topo = raw as Topology<{ countries: GeometryCollection<{ name: string }> }>;
  const fc = feature(topo, topo.objects.countries) as FeatureCollection<Geometry, { name: string }>;
  const countries = fc.features.map((f) => {
    const c = geoCentroid(f) as [number, number];
    let r = 0;
    eachPosition(f.geometry, (p) => {
      const d = geoDistance(c, p as [number, number]);
      if (d > r) r = d;
    });
    return { f, id: String(f.id ?? ""), c, r };
  });
  countries.sort((a, b) => a.r - b.r); // uji klik: negara kecil (enklave) lebih dulu
  return {
    countries,
    byId: new Map(countries.map((x) => [x.id, x])),
    borders: mesh(topo, topo.objects.countries, (a, b) => a !== b),
    coast: mesh(topo, topo.objects.countries, (a, b) => a === b),
  };
}

const unwrap = (m: unknown) => (m as { default?: unknown }).default ?? m;
let lowPromise: Promise<Layer> | null = null;
let highPromise: Promise<Layer> | null = null;
/** Peta world-atlas: 1:110 juta untuk globe utuh yang berputar (ringan), 1:50 juta saat zoom ke negara. */
const loadLow = () => (lowPromise ??= import("world-atlas/countries-110m.json").then((m) => buildLayer(unwrap(m))));
const loadHigh = () => (highPromise ??= import("world-atlas/countries-50m.json").then((m) => buildLayer(unwrap(m))));

/** Perbesaran agar negara mengisi kira-kira 60% lensa (persentil 85 jarak titik, pulau jauh diabaikan). */
function zoomFor(country: Country | undefined, center: [number, number]): number {
  if (!country) return 2.4;
  const d: number[] = [];
  eachPosition(country.f.geometry, (p) => d.push(geoDistance(center, p as [number, number])));
  d.sort((a, b) => a - b);
  const a = d[Math.floor(d.length * 0.85)] ?? 0.2;
  return Math.min(7, Math.max(1.25, 0.6 / Math.sin(Math.min(Math.max(a, 0.02), 1.4))));
}

/** Warna negara menurut jumlah incident: kuning tembaga (sedikit) ke merah (banyak). */
function heat(t: number, alpha: number): string {
  const r = Math.round(236 + (242 - 236) * t);
  const g = Math.round(168 + (84 - 168) * t);
  const b = Math.round(76 + (88 - 76) * t);
  return `rgba(${r},${g},${b},${alpha})`;
}

const wrap = (deg: number) => ((((deg + 180) % 360) + 360) % 360) - 180;

/**
 * Globe pusat komando: peta negara (batas negara dan garis pantai) pada
 * proyeksi ortografis di kanvas, diwarnai menurut jumlah incident. Berputar
 * pelan dan bisa diseret; negara yang difilter didekati dengan animasi zoom
 * dan digambar dengan peta yang lebih detail. Klik negara untuk memfilter,
 * klik lagi untuk menghapus filter. Busur ungu menghubungkan negara yang
 * disebut dalam incident yang sama.
 */
export function CommandGlobe({ points, arcs, focus, labels, ariaLabel, readoutLabel, zoomLabel, hint }: Props) {
  const router = useRouter();
  const wrapRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const readoutRef = useRef<HTMLSpanElement>(null);
  const tipRef = useRef<HTMLDivElement>(null);
  const labelRefs = useRef(new Map<string, HTMLAnchorElement>());
  const latest = useRef({ points, arcs, focus, hint });
  useEffect(() => {
    latest.current = { points, arcs, focus, hint };
  }, [points, arcs, focus, hint]);
  const view = useRef<View>({ ...START });
  const focusSeen = useRef<string | null>(null);

  const labelled = points.slice(0, labels);
  const activePoint = points.find((p) => p.active);
  if (activePoint && !labelled.includes(activePoint)) labelled.push(activePoint);

  useEffect(() => {
    const canvas = canvasRef.current;
    const box = wrapRef.current;
    const context = canvas?.getContext("2d");
    const map = document.createElement("canvas"); // lapisan peta, digambar ulang hanya bila tampilan berubah
    const mapContext = map.getContext("2d");
    if (!canvas || !box || !context || !mapContext) return;
    const ctx = context;
    const mctx = mapContext;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const started = performance.now();
    let low: Layer | null = null;
    let high: Layer | null = null;
    let alive = true;
    loadLow().then((l) => {
      if (alive) low = l;
    });
    loadHigh().then((l) => {
      if (alive) high = l;
    });

    let mapKey = "";
    const size = { w: 0, h: 0, dpr: 1 };
    const measure = () => {
      const rect = box.getBoundingClientRect();
      size.dpr = Math.min(2, window.devicePixelRatio || 1);
      size.w = rect.width;
      size.h = rect.height;
      canvas.width = map.width = Math.round(rect.width * size.dpr);
      canvas.height = map.height = Math.round(rect.height * size.dpr);
      mapKey = "";
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(box);

    const projection = geoOrthographic().clipAngle(90).precision(0);
    const mapPath = geoPath(projection, mctx);
    const graticule = geoGraticule10();

    let target: View | null = null;
    let lastInput = -Infinity;
    let drag: { x: number; y: number; lam: number; phi: number; moved: boolean } | null = null;
    let pointer: { x: number; y: number } | null = null;
    let hoverKey = "";
    let hovered: Country | null = null;
    let raf = 0;
    let prev = performance.now();

    const geometry = () => {
      const R0 = (Math.min(size.w, size.h) / 2) * 0.96;
      return { cx: size.w / 2, cy: size.h / 2, R0, R: R0 * view.current.k };
    };
    const setProjection = () => {
      const { cx, cy, R } = geometry();
      const v = view.current;
      projection.scale(R).translate([cx, cy]).rotate([v.lam, v.phi]);
    };

    /** Negara di bawah titik layar (peta paling detail yang sudah dimuat), atau null. */
    const countryAt = (x: number, y: number): Country | null => {
      const layer = high ?? low;
      if (!layer) return null;
      const { cx, cy, R0, R } = geometry();
      if (Math.hypot(x - cx, y - cy) > Math.min(R0, R)) return null;
      setProjection();
      const ll = projection.invert?.([x, y]);
      if (!ll) return null;
      for (const c of layer.countries) {
        if (geoDistance(c.c, ll) > c.r + 0.01) continue;
        if (geoContains(c.f, ll)) return c;
      }
      return null;
    };

    const onDown = (e: PointerEvent) => {
      const rect = canvas.getBoundingClientRect();
      drag = { x: e.clientX - rect.left, y: e.clientY - rect.top, lam: view.current.lam, phi: view.current.phi, moved: false };
      lastInput = performance.now();
    };
    const onMove = (e: PointerEvent) => {
      const rect = canvas.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      pointer = { x, y };
      if (!drag) return;
      const dx = x - drag.x;
      const dy = y - drag.y;
      if (!drag.moved && Math.hypot(dx, dy) < 5) return;
      if (!drag.moved) canvas.setPointerCapture(e.pointerId);
      drag.moved = true;
      const degPerPx = 57 / geometry().R;
      view.current.lam = drag.lam + dx * degPerPx;
      view.current.phi = Math.max(-75, Math.min(75, drag.phi - dy * degPerPx));
      target = null; // seretan pengguna menang atas animasi
      lastInput = performance.now();
    };
    const onUp = (e: PointerEvent) => {
      const wasDrag = drag?.moved;
      drag = null;
      if (canvas.hasPointerCapture(e.pointerId)) canvas.releasePointerCapture(e.pointerId);
      lastInput = performance.now();
      if (wasDrag) return;
      const rect = canvas.getBoundingClientRect();
      const hit = countryAt(e.clientX - rect.left, e.clientY - rect.top);
      const point = hit ? latest.current.points.find((p) => p.num === hit.id) : undefined;
      if (point) router.push(point.href, { scroll: false });
    };
    const onLeave = () => {
      pointer = null;
      hovered = null;
      hoverKey = "";
      if (tipRef.current) tipRef.current.style.opacity = "0";
    };
    canvas.addEventListener("pointerdown", onDown);
    canvas.addEventListener("pointermove", onMove);
    canvas.addEventListener("pointerup", onUp);
    canvas.addEventListener("pointercancel", onUp);
    canvas.addEventListener("pointerleave", onLeave);

    /** Laut, daratan, batas negara, garis pantai, dan bayangan bola ke kanvas lapisan peta. */
    const drawMap = (layer: Layer | null, pts: GlobePoint[]) => {
      const { cx, cy, R0, R } = geometry();
      const v = view.current;
      const center: [number, number] = [-v.lam, -v.phi];
      const reach = Math.asin(Math.min(1, R0 / R)) + 0.04; // sudut yang tampak di dalam lensa
      const max = Math.max(1, ...pts.map((p) => p.n));
      const byNum = new Map(pts.map((p) => [p.num, p]));
      const c = mctx;
      c.setTransform(1, 0, 0, 1, 0, 0);
      c.clearRect(0, 0, map.width, map.height);
      c.setTransform(size.dpr, 0, 0, size.dpr, 0, 0);
      c.save();
      c.beginPath();
      c.arc(cx, cy, R0, 0, TAU);
      c.clip();

      const ocean = c.createRadialGradient(cx - R * 0.3, cy - R * 0.35, R * 0.05, cx, cy, R);
      ocean.addColorStop(0, "#10324a");
      ocean.addColorStop(0.7, "#0a1d2c");
      ocean.addColorStop(1, "#06111b");
      c.fillStyle = ocean;
      c.beginPath();
      c.arc(cx, cy, R, 0, TAU);
      c.fill();

      c.beginPath();
      mapPath(graticule);
      c.strokeStyle = "rgba(47,183,201,0.09)";
      c.lineWidth = 0.6;
      c.stroke();

      if (layer) {
        const visible = layer.countries.filter((x) => geoDistance(x.c, center) - x.r < reach);
        c.beginPath();
        for (const x of visible) if (!byNum.has(x.id)) mapPath(x.f);
        c.fillStyle = "#1a2d3d";
        c.fill();
        for (const x of visible) {
          const p = byNum.get(x.id);
          if (!p) continue;
          const t = Math.sqrt(p.n / max);
          c.beginPath();
          mapPath(x.f);
          c.fillStyle = p.active ? "rgba(47,183,201,0.6)" : heat(t, 0.38 + 0.42 * t + (hovered?.id === x.id ? 0.2 : 0));
          c.fill();
        }
        c.beginPath();
        mapPath(layer.borders);
        c.strokeStyle = "rgba(160,205,222,0.26)";
        c.lineWidth = 0.55;
        c.stroke();
        c.beginPath();
        mapPath(layer.coast);
        c.strokeStyle = "rgba(90,200,220,0.5)";
        c.lineWidth = 0.75;
        c.stroke();

        // garis tepi negara disorot: goresan lebar tembus pandang lalu goresan tipis terang
        const outline = (x: Country, color: string, glow: string) => {
          c.beginPath();
          mapPath(x.f);
          c.strokeStyle = glow;
          c.lineWidth = 5;
          c.stroke();
          c.strokeStyle = color;
          c.lineWidth = 1.4;
          c.stroke();
        };
        const hoverShape = hovered ? layer.byId.get(hovered.id) : undefined;
        if (hoverShape) outline(hoverShape, byNum.has(hoverShape.id) ? "rgba(255,255,255,0.9)" : "rgba(160,205,222,0.6)", "rgba(255,255,255,0.08)");
        const active = pts.find((p) => p.active);
        const activeShape = active ? layer.byId.get(active.num) : undefined;
        if (activeShape) outline(activeShape, "#7fe6f2", "rgba(127,230,242,0.22)");
      }

      const shade = c.createRadialGradient(cx - R * 0.32, cy - R * 0.38, R * 0.15, cx, cy, R * 1.02);
      shade.addColorStop(0, "rgba(255,255,255,0.04)");
      shade.addColorStop(0.6, "rgba(2,6,10,0.1)");
      shade.addColorStop(1, "rgba(2,6,10,0.6)");
      c.fillStyle = shade;
      c.beginPath();
      c.arc(cx, cy, R, 0, TAU);
      c.fill();
      c.restore();
    };

    /** Atmosfer, lapisan peta, busur, penanda, tepi lensa, dan label. */
    const draw = (now: number) => {
      const { points: pts, arcs: arcList } = latest.current;
      const { cx, cy, R0, R } = geometry();
      const v = view.current;
      setProjection();
      const center: [number, number] = [-v.lam, -v.phi];
      const max = Math.max(1, ...pts.map((p) => p.n));
      const layer = v.k >= DETAIL_FROM ? (high ?? low) : (low ?? high);

      const key = [
        v.lam.toFixed(3),
        v.phi.toFixed(3),
        v.k.toFixed(4),
        size.w,
        size.h,
        layer === high ? "h" : layer ? "l" : "-",
        hovered?.id ?? "",
        pts.map((p) => `${p.num}:${p.n}${p.active ? "*" : ""}`).join(),
      ].join("|");
      if (key !== mapKey) {
        drawMap(layer, pts);
        mapKey = key;
      }

      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.setTransform(size.dpr, 0, 0, size.dpr, 0, 0);
      const glow = ctx.createRadialGradient(cx, cy, R0 * 0.94, cx, cy, R0 * 1.1);
      glow.addColorStop(0, "rgba(47,183,201,0.28)");
      glow.addColorStop(1, "rgba(47,183,201,0)");
      ctx.fillStyle = glow;
      ctx.beginPath();
      ctx.arc(cx, cy, R0 * 1.1, 0, TAU);
      ctx.fill();
      ctx.drawImage(map, 0, 0, size.w, size.h);

      ctx.save();
      ctx.beginPath();
      ctx.arc(cx, cy, R0, 0, TAU);
      ctx.clip();

      // busur terangkat antara negara yang disebut bersama
      const rotate = geoRotation([v.lam, v.phi]);
      const lift = (lng: number, lat: number, h: number) => {
        const [l, f] = rotate([lng, lat]).map((d) => (d * Math.PI) / 180);
        const x = Math.cos(f) * Math.sin(l);
        const y = -Math.sin(f);
        const z = Math.cos(f) * Math.cos(l);
        const s = R * (1 + h);
        return { x: cx + s * x, y: cy + s * y, show: z > 0 || (1 + h) * Math.hypot(x, y) > 1 };
      };
      arcList.forEach((a, i) => {
        const from: [number, number] = [a.from[1], a.from[0]];
        const to: [number, number] = [a.to[1], a.to[0]];
        const between = geoInterpolate(from, to);
        const height = 0.06 + 0.3 * (geoDistance(from, to) / Math.PI);
        const steps = 40;
        const line = Array.from({ length: steps + 1 }, (_, s) => {
          const [lng, lat] = between(s / steps);
          return lift(lng, lat, height * Math.sin((Math.PI * s) / steps));
        });
        ctx.beginPath();
        let open = false;
        for (const q of line) {
          if (!q.show) {
            open = false;
            continue;
          }
          if (open) ctx.lineTo(q.x, q.y);
          else ctx.moveTo(q.x, q.y);
          open = true;
        }
        ctx.strokeStyle = "rgba(167,139,250,0.55)";
        ctx.lineWidth = 1.1;
        ctx.stroke();
        const head = reduce ? 0.5 : (now / 2600 + i * 0.173) % 1;
        const q = line[Math.round(head * steps)];
        if (q.show) {
          ctx.beginPath();
          ctx.arc(q.x, q.y, 5, 0, TAU);
          ctx.fillStyle = "rgba(167,139,250,0.25)";
          ctx.fill();
          ctx.beginPath();
          ctx.arc(q.x, q.y, 2.2, 0, TAU);
          ctx.fillStyle = "#e3dbff";
          ctx.fill();
        }
      });

      // penanda negara: titik dan denyut untuk tiga teratas serta negara terpilih
      pts.forEach((p, i) => {
        if (geoDistance([p.lng, p.lat], center) > Math.PI / 2 - 0.03) return;
        const xy = projection([p.lng, p.lat]);
        if (!xy || Math.hypot(xy[0] - cx, xy[1] - cy) > R0) return;
        const t = Math.sqrt(p.n / max);
        const r = 1.8 + 3 * t;
        if ((i < 3 || p.active) && !reduce) {
          const phase = (now / 1800 + i * 0.31) % 1;
          ctx.beginPath();
          ctx.arc(xy[0], xy[1], r + phase * 16, 0, TAU);
          ctx.strokeStyle = p.active ? `rgba(127,230,242,${1 - phase})` : heat(t, 0.8 * (1 - phase));
          ctx.lineWidth = 1.2;
          ctx.stroke();
        }
        ctx.beginPath();
        ctx.arc(xy[0], xy[1], r, 0, TAU);
        ctx.fillStyle = p.active ? "#7fe6f2" : heat(t, 1);
        ctx.fill();
      });
      ctx.restore();

      ctx.beginPath();
      ctx.arc(cx, cy, R0, 0, TAU);
      ctx.strokeStyle = "rgba(47,183,201,0.45)";
      ctx.lineWidth = 1;
      ctx.stroke();

      // label HTML mengikuti posisi negaranya; label yang menabrak label berperingkat lebih tinggi disembunyikan
      const placed: [number, number, number, number][] = [];
      const ranked = [...pts].sort((a, b) => Number(b.active) - Number(a.active));
      for (const p of ranked) {
        const el = labelRefs.current.get(p.id);
        if (!el) continue;
        const xy = projection([p.lng, p.lat]);
        let shown = Boolean(xy) && geoDistance([p.lng, p.lat], center) < Math.PI / 2 - 0.12 && Math.hypot(xy![0] - cx, xy![1] - cy) < R0 - 8;
        if (shown && xy) {
          const w = el.offsetWidth;
          const h = el.offsetHeight;
          const box: [number, number, number, number] = [xy[0] + 9, xy[1] - h / 2, xy[0] + 9 + w, xy[1] + h / 2];
          shown = !placed.some((o) => box[0] < o[2] + 4 && box[2] + 4 > o[0] && box[1] < o[3] + 2 && box[3] + 2 > o[1]);
          if (shown) {
            placed.push(box);
            el.style.transform = `translate(${xy[0].toFixed(1)}px, ${xy[1].toFixed(1)}px) translate(9px, -50%)`;
          }
        }
        el.style.opacity = shown ? "1" : "0";
        el.style.pointerEvents = shown ? "auto" : "none";
      }

      if (readoutRef.current) {
        readoutRef.current.textContent = `${wrap(-v.lam).toFixed(1).padStart(6, " ")}° · ${zoomLabel} ×${v.k.toFixed(1)}`;
      }
    };

    /** Tooltip negara di bawah kursor; dihitung ulang hanya bila kursor atau tampilan berubah. */
    const updateHover = () => {
      if (!pointer || drag) return;
      const v = view.current;
      const key = `${pointer.x}|${pointer.y}|${v.lam.toFixed(2)}|${v.phi.toFixed(2)}|${v.k.toFixed(3)}|${high ? 1 : 0}`;
      if (key === hoverKey) return;
      hoverKey = key;
      const hit = countryAt(pointer.x, pointer.y);
      const p = hit ? latest.current.points.find((x) => x.num === hit.id) : undefined;
      canvas.style.cursor = p ? "pointer" : "";
      const tip = tipRef.current;
      if (!tip) return;
      if (hit?.id !== hovered?.id) {
        hovered = hit;
        tip.replaceChildren();
        if (hit) {
          if (p) {
            const flag = document.createElement("img");
            flag.src = `/flags/${p.iso}.svg`;
            flag.alt = "";
            tip.appendChild(flag);
          }
          const title = document.createElement("b");
          title.textContent = p ? `${p.label} · ${p.n}` : hit.f.properties.name;
          tip.appendChild(title);
          if (p) {
            const sub = document.createElement("span");
            sub.textContent = p.active ? latest.current.hint.clear : latest.current.hint.filter;
            tip.appendChild(sub);
          }
        }
      }
      tip.style.opacity = hit ? "1" : "0";
      tip.style.transform = `translate(${pointer.x + 14}px, ${pointer.y + 12}px)`;
    };

    const frame = (now: number) => {
      const dt = Math.min(64, now - prev);
      prev = now;
      const { focus: f } = latest.current;
      const key = f ? `${f.num}:${f.lat}:${f.lng}` : "";
      // zoom ke negara menunggu peta detail (atau 2,5 detik bila peta detail lambat dimuat)
      if (focusSeen.current !== key && (!f || high || (low && now - started > 2500))) {
        focusSeen.current = key;
        target = f
          ? { lam: -f.lng, phi: Math.max(-60, Math.min(60, -f.lat)), k: zoomFor((high ?? low)?.byId.get(f.num), [f.lng, f.lat]) }
          : { lam: view.current.lam, phi: START.phi, k: 1 };
        if (reduce) {
          view.current = { ...target };
          target = null;
        }
      }
      const v = view.current;
      if (target && !drag) {
        const dLam = wrap(target.lam - v.lam);
        const dPhi = target.phi - v.phi;
        const far = Math.hypot(dLam, dPhi) > 25;
        v.lam += dLam * (1 - Math.exp(-dt / 320));
        v.phi += dPhi * (1 - Math.exp(-dt / 320));
        // menjauh dulu saat menempuh jarak jauh, lalu mendekat ke negara tujuan
        const kGoal = far ? Math.min(target.k, 1) : target.k;
        v.k += (kGoal - v.k) * (1 - Math.exp(-dt / 420));
        if (Math.abs(dLam) < 0.02 && Math.abs(dPhi) < 0.02 && Math.abs(target.k - v.k) < 0.002) {
          v.lam = target.lam;
          v.phi = target.phi;
          v.k = target.k;
          if (!latest.current.focus) target = null; // kembali berputar sendiri
        }
      } else if (!latest.current.focus && !drag && !reduce && now - lastInput > 1800) {
        v.lam += SPIN * dt;
      }
      updateHover();
      draw(now);
      raf = requestAnimationFrame(frame);
    };
    raf = requestAnimationFrame(frame);

    return () => {
      alive = false;
      cancelAnimationFrame(raf);
      ro.disconnect();
      canvas.removeEventListener("pointerdown", onDown);
      canvas.removeEventListener("pointermove", onMove);
      canvas.removeEventListener("pointerup", onUp);
      canvas.removeEventListener("pointercancel", onUp);
      canvas.removeEventListener("pointerleave", onLeave);
    };
  }, [router, zoomLabel]);

  return (
    <div ref={wrapRef} className="cc-globe relative aspect-square w-full">
      <div className="cc-hud" aria-hidden="true">
        <span className="cc-ring cc-ring-ticks" />
        <span className="cc-ring cc-ring-dash" />
        <span className="cc-ring cc-ring-inner" />
        <span className="cc-sweep" />
        <span className="cc-scan" />
        <span className="cc-cross cc-cross-h" />
        <span className="cc-cross cc-cross-v" />
      </div>
      <canvas ref={canvasRef} role="img" aria-label={ariaLabel} className="cc-canvas absolute inset-0 h-full w-full" />
      {labelled.map((p) => (
        <Link
          key={p.id}
          href={p.href}
          scroll={false}
          ref={(el) => {
            if (el) labelRefs.current.set(p.id, el);
            else labelRefs.current.delete(p.id);
          }}
          className={`cc-label${p.active ? " is-active" : ""}`}
          title={p.active ? hint.clear : hint.filter}
        >
          <span className="cc-label-text">
            <Image src={`/flags/${p.iso}.svg`} alt="" width={16} height={11} unoptimized className="cc-flag" />
            {p.label}
            <b>{p.n}</b>
            {p.active ? <i aria-hidden="true">×</i> : null}
          </span>
        </Link>
      ))}
      <div ref={tipRef} className="cc-tip" aria-hidden="true" />
      <span className="cc-hint hidden sm:block" aria-hidden="true">
        {hint.help}
      </span>
      <span className="cc-readout" aria-hidden="true">
        {readoutLabel} <span ref={readoutRef}>000.0°</span>
      </span>
    </div>
  );
}
