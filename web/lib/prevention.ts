/**
 * Panduan pencegahan umum: satu langkah khusus kelompok sasaran, lalu langkah
 * untuk jenis serangan, dan kanal pelaporan resmi yang relevan. Isinya praktik
 * baku yang lazim dianjurkan, bukan hasil pipeline; kunci jenis serangan sama
 * dengan v05_incidents.attack_type (huruf kecil).
 *
 * Datanya ada di prevention.json, dibaca juga oleh pipeline (csais/flows.py)
 * untuk menyimpan saran alur D1 per incident. Aturan pemilihan di bawah harus
 * sama dengan ``prevention_for`` di sana.
 */
import type { Lang } from "./i18n";
import data from "./prevention.json";
import platformData from "./platforms.json";

type Text = Record<Lang, string>;
export type Channel = { name: string; url: string };

const BY_TYPE = data.by_type as Record<string, Text[]>;
const ALIAS = data.alias as Record<string, string>;
const BY_GROUP = data.by_group as Record<string, Text>;
const HOAX = data.hoax as Text[];
const CHANNELS = data.channels as Record<string, Channel>;
const SCAM_TYPES = new Set(data.scam_types);
const LINK_TYPES = new Set(data.link_types);
const FINANCE_GROUPS = new Set(data.finance_groups);
const AUDIENCES = data.audiences as Record<string, Text>;
const TOPICS = data.topics as Record<string, Text>;

/** Semua kunci sasaran dan materi literasi (pilihan lembaga di portal). */
export const AUDIENCE_KEYS = Object.keys(AUDIENCES);
export const TOPIC_KEYS = Object.keys(TOPICS);

export type Prevention = { steps: string[]; channels: Channel[] };
export type PreventionKeys = { steps: string[]; channels: string[] };

/* Sasaran dan materi literasi per incident dipilih pipeline (literacy_for di
   csais/flows.py) atau lembaga di portal; web hanya menampilkan teksnya. */
type Platform = { name: string; category: string };
type PlatformCategory = { label: Text; topics: string[]; age?: Text; age_source?: string };
const PLATFORMS = platformData.platforms as Record<string, Platform>;
const CATEGORIES = platformData.categories as Record<string, PlatformCategory>;

/** Platform dan kategorinya untuk kunci audiens ``platform:<kunci>``; null bila bukan platform. */
export function platformOf(key: string): { name: string; category: PlatformCategory | null } | null {
  if (!key.startsWith("platform:")) return null;
  const platform = PLATFORMS[key.slice("platform:".length)];
  return platform ? { name: platform.name, category: CATEGORIES[platform.category] ?? null } : null;
}

/** Teks sasaran literasi; kunci platform menjadi "Pengguna <platform> di Indonesia" (dengan usia bila bersumber). */
export function audienceText(key: string, lang: Lang): string | null {
  const platform = platformOf(key);
  if (platform) {
    const age = platform.category?.age?.[lang];
    const base = lang === "en" ? `${platform.name} users in Indonesia` : `Pengguna ${platform.name} di Indonesia`;
    return age ? `${base}, ${age}` : base;
  }
  return AUDIENCES[key]?.[lang] ?? null;
}

/** Sasaran untuk layanan di luar katalog (korban incident global), mis. "Pengguna dan pelanggan Ticketmaster di Indonesia". */
export function serviceAudience(name: string, lang: Lang): string {
  return lang === "en" ? `Users and customers of ${name} in Indonesia` : `Pengguna dan pelanggan ${name} di Indonesia`;
}

export function topicText(key: string, lang: Lang): string | null {
  return TOPICS[key]?.[lang] ?? null;
}

/** Kunci tiga langkah (kelompok, lalu jenis serangan teratas) dan kanal pelaporan. */
export function preventionKeys(group: string, types: string[]): PreventionKeys {
  const steps: string[] = [];
  if (BY_GROUP[group]) steps.push(`group:${group}`);
  const known = types.map((t) => ALIAS[t] ?? t).filter((t) => BY_TYPE[t]);
  const pool = (known.length ? known : ["cyber_attack"]).flatMap((t, i) =>
    BY_TYPE[t].slice(0, i === 0 ? 2 : 1).map((_, j) => `type:${t}:${j}`),
  );
  for (const key of pool) {
    if (steps.length >= 3) break;
    if (!steps.includes(key)) steps.push(key);
  }
  const keys = new Set<string>();
  if (FINANCE_GROUPS.has(group) || types.includes("investment_scam")) keys.add("ojk");
  if (types.some((t) => SCAM_TYPES.has(t)) || group === "JOB_SEEKERS" || group === "ELDERLY") keys.add("rekening");
  if (types.some((t) => LINK_TYPES.has(t))) keys.add("konten");
  keys.add("patrol");
  return { steps, channels: [...keys] };
}

/**
 * Semua langkah yang relevan untuk satu incident, sebagai pilihan lembaga di
 * portal: langkah kelompok sasaran, semua langkah tiap jenis serangannya, lalu
 * langkah umum serangan siber.
 */
export function candidateSteps(group: string, types: string[]): string[] {
  const keys: string[] = [];
  if (BY_GROUP[group]) keys.push(`group:${group}`);
  const known = [...new Set(types.map((t) => ALIAS[t] ?? t).filter((t) => BY_TYPE[t]))];
  for (const t of [...known.filter((t) => t !== "cyber_attack"), "cyber_attack"]) {
    BY_TYPE[t].forEach((_, j) => keys.push(`type:${t}:${j}`));
  }
  return keys;
}

/** Teks satu langkah dari kuncinya; null bila kunci tidak dikenal. */
export function tipText(key: string, lang: Lang): string | null {
  const [kind, name, index] = key.split(":");
  if (kind === "group") return BY_GROUP[name]?.[lang] ?? null;
  if (kind === "type") return BY_TYPE[name]?.[Number(index)]?.[lang] ?? null;
  if (kind === "hoax") return HOAX[Number(name)]?.[lang] ?? null;
  return null;
}

export function channelOf(key: string): Channel | null {
  return CHANNELS[key] ?? null;
}

/** Tiga langkah dan kanal pelaporan untuk satu kelompok, sebagai teks. */
export function preventionFor(group: string, types: string[], lang: Lang): Prevention {
  const keys = preventionKeys(group, types);
  return {
    steps: keys.steps.map((k) => tipText(k, lang)).filter((s): s is string => Boolean(s)),
    channels: keys.channels.map(channelOf).filter((c): c is Channel => Boolean(c)),
  };
}
