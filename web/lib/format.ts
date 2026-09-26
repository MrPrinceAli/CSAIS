import type { Lang } from "./i18n";

const LOCALE: Record<Lang, string> = { id: "id-ID", en: "en-GB" };
const TZ = "Asia/Jakarta";

const cache = new Map<string, Intl.NumberFormat | Intl.DateTimeFormat>();

function numFmt(lang: Lang): Intl.NumberFormat {
  const key = `n:${lang}`;
  let f = cache.get(key) as Intl.NumberFormat | undefined;
  if (!f) {
    f = new Intl.NumberFormat(LOCALE[lang]);
    cache.set(key, f);
  }
  return f;
}

function dateFmt(lang: Lang, kind: "short" | "long" | "time"): Intl.DateTimeFormat {
  const key = `d:${lang}:${kind}`;
  let f = cache.get(key) as Intl.DateTimeFormat | undefined;
  if (!f) {
    const opts: Intl.DateTimeFormatOptions =
      kind === "short"
        ? { day: "numeric", month: "short", timeZone: TZ }
        : kind === "long"
          ? { day: "numeric", month: "long", year: "numeric", timeZone: TZ }
          : { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: TZ };
    f = new Intl.DateTimeFormat(LOCALE[lang], opts);
    cache.set(key, f);
  }
  return f;
}

export function formatters(lang: Lang) {
  const unknown = lang === "en" ? "unknown" : "tidak diketahui";
  return {
    num(value: number | bigint | null | undefined): string {
      if (value === null || value === undefined) return "0";
      return numFmt(lang).format(Number(value));
    },
    date(value: string | null | undefined): string {
      if (!value) return unknown;
      const d = new Date(value);
      return Number.isNaN(d.getTime()) ? value : dateFmt(lang, "short").format(d);
    },
    dateLong(value: string | null | undefined): string {
      if (!value) return unknown;
      const d = new Date(value);
      return Number.isNaN(d.getTime()) ? value : dateFmt(lang, "long").format(d);
    },
    dateTime(value: string | null | undefined): string {
      if (!value) return unknown;
      const d = new Date(value);
      return Number.isNaN(d.getTime()) ? value : `${dateFmt(lang, "time").format(d)} WIB`;
    },
    score(value: number | null | undefined): string {
      if (value === null || value === undefined) return "-";
      const s = Number(value).toFixed(2);
      return lang === "id" ? s.replace(".", ",") : s;
    },
    pct(value: number): string {
      return `${Math.round(value * 100)}%`;
    },
  };
}

/** Judul Google News membawa akhiran " - Penerbit"; buang untuk judul incident. */
export function incidentTitle(title: string | null | undefined, fallback = "Incident"): string {
  if (!title) return fallback;
  return title.replace(/\s+[-–|]\s+[^-–|]{2,60}$/, "").trim() || fallback;
}

/** Nama penerbit dari akhiran judul Google News (" - Help Net Security"); kosong bila tidak ada. */
export function publisherOf(title: string | null | undefined): string {
  const match = /\s[-–|]\s([^-–|]{2,60})$/.exec(title ?? "");
  return match ? match[1].trim() : "";
}

export function attackCode(value: string | null | undefined): string {
  if (!value) return "UNKNOWN";
  return value.toUpperCase().split(",")[0].trim();
}

export function domainOf(url: string | null | undefined): string {
  if (!url) return "";
  try {
    const host = new URL(url).hostname.toLowerCase();
    return host.startsWith("www.") ? host.slice(4) : host;
  } catch {
    return "";
  }
}

export type Severity = "crit" | "high" | "med";

const HEAVY = new Set([
  "data_breach",
  "data_leak",
  "ransomware",
  "supply_chain_attack",
  "critical_infrastructure_attack",
  "ics_scada_attack",
  "data_theft",
]);

/** Keparahan turunan dari jumlah sumber dan jenis serangan; bukan penilaian resmi. */
export function severity(row: { document_count: number | bigint; attack_type: string | null }): Severity {
  const docs = Number(row.document_count);
  const type = (row.attack_type ?? "").toLowerCase().split(",")[0].trim();
  const heavy = HEAVY.has(type);
  if (docs >= 8 || (heavy && docs >= 3)) return "crit";
  if (docs >= 3 || heavy) return "high";
  return "med";
}
