/**
 * Portal lembaga (alur D3): lembaga, mandat antrean, pilihan alasan, dan sesi.
 * Hanya dipakai di server. Keputusan disimpan ke database survei (tabel
 * official_reviews, lihat lib/survey.ts) dan dibaca csais/official.py setiap
 * hari menjadi D3, lalu D4 untuk yang dikonfirmasi atau dibantah.
 *
 * Masuk memakai kode akses per lembaga (versi awal sebelum wallet dan
 * tanda tangan EIP-712):
 *   PORTAL_ACCESS  JSON {"BSSN": "<sha256 kode>", "OJK": ..., "KOMDIGI": ..., "POLRI": ...}
 *   PORTAL_SECRET  kunci HMAC untuk cookie sesi
 */
import { createHash, createHmac, timingSafeEqual } from "node:crypto";

export const INSTITUTIONS = ["BSSN", "OJK", "KOMDIGI", "POLRI"] as const;
export type Institution = (typeof INSTITUTIONS)[number];

export const INSTITUTION_NAME: Record<Institution, string> = { BSSN: "BSSN", OJK: "OJK", KOMDIGI: "Komdigi", POLRI: "Siber Polri" };
export const INSTITUTION_LOGO: Record<Institution, string> = { BSSN: "BSSN", OJK: "OJK", KOMDIGI: "Komdigi", POLRI: "Polri" };

/** Mandat antrean: jenis serangan (v05, huruf kecil) dan kelompok sasaran (v03). */
export const MANDATE: Record<Institution, { types: string[]; groups: string[] }> = {
  BSSN: {
    types: ["ransomware", "malware", "network_intrusion", "vulnerability_exploitation", "ddos", "supply_chain_attack", "cyber_attack", "zero_day", "web_attack", "cyber_espionage"],
    groups: ["GOVERNMENT", "CIVIL_SERVANTS"],
  },
  OJK: {
    types: ["investment_scam", "credential_attack", "account_takeover", "crypto_attack"],
    groups: ["BANK_CUSTOMERS", "SMES"],
  },
  KOMDIGI: {
    types: ["phishing", "malicious_link", "malicious_website", "data_breach", "data_leak", "mobile_attack", "deepfake_fraud"],
    groups: ["CHILDREN", "STUDENTS"],
  },
  POLRI: {
    types: ["online_scam", "job_scam", "investment_scam", "social_engineering", "deepfake_fraud", "cyber_extortion", "data_theft"],
    groups: ["JOB_SEEKERS", "ELDERLY", "INDIVIDUALS"],
  },
};

export const REVIEW_STATUSES = ["dikonfirmasi", "dibantah", "sebagian"] as const;
export type ReviewStatus = (typeof REVIEW_STATUSES)[number];

/** Alasan yang bisa dipilih per status; teks tampilannya di i18n (portal.reasons). */
export const REASONS: Record<ReviewStatus, string[]> = {
  dikonfirmasi: ["ditangani", "laporan_diterima", "imbauan_terbit"],
  dibantah: ["hoaks", "bukan_serangan", "keliru_sasaran"],
  sebagian: ["diselidiki", "sebagian_benar", "di_luar_mandat"],
};

export const REVIEW_FIELDS = ["attack_type", "target", "threat_actor", "attack_date", "location"] as const;

const SESSION_COOKIE = "csais_portal";
const SESSION_HOURS = 12;

function secret(): string {
  return process.env.PORTAL_SECRET ?? "";
}

export function portalConfigured(): boolean {
  return Boolean(secret() && process.env.PORTAL_ACCESS);
}

function accessHashes(): Partial<Record<Institution, string>> {
  try {
    return JSON.parse(process.env.PORTAL_ACCESS ?? "{}");
  } catch {
    return {};
  }
}

function sameHex(a: string, b: string): boolean {
  const x = Buffer.from(a, "hex");
  const y = Buffer.from(b, "hex");
  return x.length === y.length && x.length > 0 && timingSafeEqual(x, y);
}

/** Lembaga pemilik kode akses; null bila kode salah. */
export function institutionForCode(code: string): Institution | null {
  const digest = createHash("sha256").update(code.trim()).digest("hex");
  const hashes = accessHashes();
  for (const inst of INSTITUTIONS) {
    const expected = hashes[inst];
    if (expected && sameHex(digest, expected)) return inst;
  }
  return null;
}

function sign(value: string): string {
  return createHmac("sha256", secret()).update(value).digest("hex");
}

export function sessionCookie(inst: Institution): { name: string; value: string; maxAge: number } {
  const expires = Date.now() + SESSION_HOURS * 3600_000;
  const body = `${inst}.${expires}`;
  return { name: SESSION_COOKIE, value: `${body}.${sign(body)}`, maxAge: SESSION_HOURS * 3600 };
}

export const SESSION_COOKIE_NAME = SESSION_COOKIE;

/** Lembaga dari nilai cookie sesi; null bila tidak sah atau kedaluwarsa. */
export function institutionFromSession(value: string | undefined): Institution | null {
  if (!value || !portalConfigured()) return null;
  const [inst, expires, mac] = value.split(".");
  if (!inst || !expires || !mac) return null;
  if (!INSTITUTIONS.includes(inst as Institution)) return null;
  if (!sameHex(mac, sign(`${inst}.${expires}`))) return null;
  if (Number(expires) < Date.now()) return null;
  return inst as Institution;
}
