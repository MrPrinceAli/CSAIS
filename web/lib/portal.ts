/**
 * Portal lembaga (alur D3): lembaga, mandat antrean, pilihan alasan, dan sesi.
 * Hanya dipakai di server. Keputusan disimpan ke database survei (tabel
 * official_reviews, lihat lib/survey.ts) dan dibaca csais/official.py setiap
 * hari menjadi D3, lalu D4 untuk yang dikonfirmasi atau dibantah.
 *
 * Masuk: pilih lembaga lalu password (satu akun per lembaga). Password membuka
 * kunci tanda tangan lembaga yang tersimpan terenkripsi (scrypt + AES-256-GCM),
 * dibuat dengan scripts/portal-keys.mjs; tidak ada hash password terpisah.
 *   PORTAL_KEYS    JSON {"BSSN": {address, kdf, salt, iv, ct, tag}, ...}
 *   PORTAL_SECRET  kunci untuk cookie sesi (HMAC) dan cookie kunci (AES-GCM)
 */
import { createCipheriv, createDecipheriv, createHash, createHmac, randomBytes, scryptSync, timingSafeEqual } from "node:crypto";

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
const KEY_COOKIE = "csais_portal_key";
const SESSION_HOURS = 12;

type EncryptedKey = { address: string; kdf: { N: number; r: number; p: number }; salt: string; iv: string; ct: string; tag: string };

function secret(): string {
  return process.env.PORTAL_SECRET ?? "";
}

function encryptedKeys(): Partial<Record<Institution, EncryptedKey>> {
  try {
    return JSON.parse(process.env.PORTAL_KEYS ?? "{}");
  } catch {
    return {};
  }
}

export function portalConfigured(): boolean {
  return Boolean(secret() && Object.keys(encryptedKeys()).length);
}

/** Buka kunci pribadi lembaga dengan password; null bila password salah. */
export function unlockKey(inst: Institution, password: string): `0x${string}` | null {
  const entry = encryptedKeys()[inst];
  if (!entry || !password) return null;
  try {
    const key = scryptSync(password, Buffer.from(entry.salt, "base64"), 32, { ...entry.kdf, maxmem: 64 * 1024 * 1024 });
    const decipher = createDecipheriv("aes-256-gcm", key, Buffer.from(entry.iv, "base64"));
    decipher.setAuthTag(Buffer.from(entry.tag, "base64"));
    const plain = Buffer.concat([decipher.update(Buffer.from(entry.ct, "base64")), decipher.final()]);
    return `0x${plain.toString("hex")}`;
  } catch {
    return null; // tag GCM tidak cocok: password salah
  }
}

function sameHex(a: string, b: string): boolean {
  const x = Buffer.from(a, "hex");
  const y = Buffer.from(b, "hex");
  return x.length === y.length && x.length > 0 && timingSafeEqual(x, y);
}

function sign(value: string): string {
  return createHmac("sha256", secret()).update(value).digest("hex");
}

function cookieKey(): Buffer {
  return createHash("sha256").update(`${secret()}|portal-key`).digest();
}

export type SessionCookie = { name: string; value: string; maxAge: number };

/** Cookie sesi (lembaga + kedaluwarsa, HMAC) dan cookie kunci (kunci pribadi terenkripsi). */
export function sessionCookies(inst: Institution, privateKey: `0x${string}`): SessionCookie[] {
  const expires = Date.now() + SESSION_HOURS * 3600_000;
  const body = `${inst}.${expires}`;
  const iv = randomBytes(12);
  const cipher = createCipheriv("aes-256-gcm", cookieKey(), iv);
  cipher.setAAD(Buffer.from(body));
  const ct = Buffer.concat([cipher.update(Buffer.from(privateKey.slice(2), "hex")), cipher.final()]);
  const blob = [iv, ct, cipher.getAuthTag()].map((b) => b.toString("base64url")).join(".");
  const maxAge = SESSION_HOURS * 3600;
  return [
    { name: SESSION_COOKIE, value: `${body}.${sign(body)}`, maxAge },
    { name: KEY_COOKIE, value: blob, maxAge },
  ];
}

export const SESSION_COOKIE_NAME = SESSION_COOKIE;
export const KEY_COOKIE_NAME = KEY_COOKIE;

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

/** Kunci pribadi lembaga dari cookie kunci, terikat ke cookie sesi yang sama. */
export function keyFromSession(session: string | undefined, blob: string | undefined): `0x${string}` | null {
  if (!session || !blob || !institutionFromSession(session)) return null;
  const body = session.split(".").slice(0, 2).join(".");
  try {
    const [iv, ct, tag] = blob.split(".").map((part) => Buffer.from(part, "base64url"));
    const decipher = createDecipheriv("aes-256-gcm", cookieKey(), iv);
    decipher.setAAD(Buffer.from(body));
    decipher.setAuthTag(tag);
    return `0x${Buffer.concat([decipher.update(ct), decipher.final()]).toString("hex")}`;
  } catch {
    return null;
  }
}
