const num = new Intl.NumberFormat("id-ID");
const dateShort = new Intl.DateTimeFormat("id-ID", { day: "numeric", month: "short", timeZone: "Asia/Jakarta" });
const dateLong = new Intl.DateTimeFormat("id-ID", {
  day: "numeric",
  month: "long",
  year: "numeric",
  timeZone: "Asia/Jakarta",
});
const dateTime = new Intl.DateTimeFormat("id-ID", {
  day: "numeric",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
  timeZone: "Asia/Jakarta",
});

export function fmtNum(value: number | bigint | null | undefined): string {
  if (value === null || value === undefined) return "0";
  return num.format(Number(value));
}

export function fmtDate(value: string | null | undefined): string {
  if (!value) return "tidak diketahui";
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? value : dateShort.format(d);
}

export function fmtDateLong(value: string | null | undefined): string {
  if (!value) return "tidak diketahui";
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? value : dateLong.format(d);
}

export function fmtDateTime(value: string | null | undefined): string {
  if (!value) return "tidak diketahui";
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? value : `${dateTime.format(d)} WIB`;
}

export function fmtScore(value: number | null | undefined): string {
  if (value === null || value === undefined) return "-";
  return Number(value).toFixed(2).replace(".", ",");
}

/** Judul Google News membawa akhiran " - Penerbit"; buang untuk judul incident. */
export function incidentTitle(title: string | null | undefined, fallback = "Incident tanpa judul"): string {
  if (!title) return fallback;
  return title.replace(/\s+[-–|]\s+[^-–|]{2,60}$/, "").trim() || fallback;
}

/** "data_breach" atau "DATA_BREACH" menjadi "Data breach". */
export function attackLabel(value: string | null | undefined): string {
  if (!value) return "Belum dikenali";
  const first = value.split(",")[0].trim();
  if (!first) return "Belum dikenali";
  const words = first.toLowerCase().replace(/_/g, " ");
  const special: Record<string, string> = {
    ddos: "DDoS",
    xss: "XSS",
    "sql injection": "SQL injection",
    "remote code execution": "Remote code execution",
    apt: "APT",
    "ics scada attack": "ICS/SCADA attack",
    "iot attack": "IoT attack",
    "dns attack": "DNS attack",
  };
  if (special[words]) return special[words];
  return words.charAt(0).toUpperCase() + words.slice(1);
}

export function attackCode(value: string | null | undefined): string {
  if (!value) return "UNKNOWN";
  return value.toUpperCase();
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

/** Keparahan turunan: jumlah sumber dan jenis serangan; bukan penilaian resmi. */
export function severity(row: { document_count: number | bigint; attack_type: string | null }): Severity {
  const docs = Number(row.document_count);
  const type = (row.attack_type ?? "").toLowerCase().split(",")[0].trim();
  const heavy = HEAVY.has(type);
  if (docs >= 8 || (heavy && docs >= 3)) return "crit";
  if (docs >= 3 || heavy) return "high";
  return "med";
}

export const SEVERITY_LABEL: Record<Severity, string> = {
  crit: "Kritis",
  high: "Tinggi",
  med: "Sedang",
};

export const GROUP_LABEL: Record<string, string> = {
  BANK_CUSTOMERS: "Nasabah bank",
  SMES: "UMKM",
  CIVIL_SERVANTS: "ASN dan PPPK",
  STUDENTS: "Pelajar dan mahasiswa",
  ELDERLY: "Lansia",
  INDIVIDUALS: "Individu dan pengguna",
  EMPLOYEES: "Karyawan",
  CHILDREN: "Anak dan remaja",
  JOB_SEEKERS: "Pencari kerja",
  BUSINESSES: "Perusahaan",
  GOVERNMENT: "Instansi pemerintah",
};

export const EVIDENCE_LABEL: Record<string, string> = {
  INDEPENDENT_SUPPORT: "Independen",
  REPRODUCED_OR_SYNDICATED: "Sindikasi",
  DUPLICATE_OR_REPEATED: "Duplikat",
  SINGLE_SOURCE: "Sumber tunggal",
};

export const RELATION_LABEL: Record<string, string> = {
  LIKELY_INDEPENDENT: "kemungkinan independen",
  LIKELY_REPRODUCED: "kemungkinan salinan",
  POSSIBLE_REPRODUCED: "mungkin salinan",
  LIKELY_DUPLICATE: "kemungkinan duplikat",
  POSSIBLE_DUPLICATE: "mungkin duplikat",
  UNCERTAIN_RELATION: "tidak pasti",
};

export function languageLabel(code: string | null | undefined): string {
  const map: Record<string, string> = {
    id: "Indonesia",
    en: "Inggris",
    de: "Jerman",
    es: "Spanyol",
    pt: "Portugis",
    fr: "Prancis",
    ja: "Jepang",
    ko: "Korea",
    ru: "Rusia",
  };
  return map[code ?? ""] ?? (code || "tidak diketahui");
}
