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

type Text = Record<Lang, string>;
export type Channel = { name: string; url: string };

const BY_TYPE = data.by_type as Record<string, Text[]>;
const ALIAS = data.alias as Record<string, string>;
const BY_GROUP = data.by_group as Record<string, Text>;
const CHANNELS = data.channels as Record<string, Channel>;
const SCAM_TYPES = new Set(data.scam_types);
const LINK_TYPES = new Set(data.link_types);
const FINANCE_GROUPS = new Set(data.finance_groups);

export type Prevention = { steps: string[]; channels: Channel[] };
export type PreventionKeys = { steps: string[]; channels: string[] };

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

/** Teks satu langkah dari kuncinya; null bila kunci tidak dikenal. */
export function tipText(key: string, lang: Lang): string | null {
  const [kind, name, index] = key.split(":");
  if (kind === "group") return BY_GROUP[name]?.[lang] ?? null;
  if (kind === "type") return BY_TYPE[name]?.[Number(index)]?.[lang] ?? null;
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
