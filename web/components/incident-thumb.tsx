import { SafeImage } from "@/components/safe-image";

type Glyph = { tone: string; d: string };

// Ikon garis 24x24 per kelompok jenis serangan, dipakai bila incident belum punya gambar
const GLYPH: Record<string, Glyph> = {
  lock: { tone: "#f25458", d: "M6 11h12v10H6zM8.5 11V7.5a3.5 3.5 0 0 1 7 0V11M12 15v2" },
  hook: { tone: "#f0a860", d: "M13 3v11.5a4.5 4.5 0 1 1-9 0V13M13 3l3.5 3.5M4 13l2.5 2.5" },
  bug: { tone: "#a78bfa", d: "M8 9a4 4 0 0 1 8 0v6a4 4 0 0 1-8 0zM12 9v10M8 12H4M20 12h-4M8 16.5H5M19 16.5h-3M9.5 5 8 3M14.5 5 16 3" },
  data: { tone: "#2fb7c9", d: "M5 5.5c0-1.4 3.1-2.5 7-2.5s7 1.1 7 2.5-3.1 2.5-7 2.5S5 6.9 5 5.5zM5 5.5v13c0 1.4 3.1 2.5 7 2.5s7-1.1 7-2.5v-13M5 12c0 1.4 3.1 2.5 7 2.5s7-1.1 7-2.5" },
  scam: { tone: "#f59e42", d: "M9.5 11a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7zM3 20a6.5 6.5 0 0 1 13 0M19.5 7v6M19.5 16.5v.5" },
  flood: { tone: "#60a5fa", d: "M3 5h18v5H3zM3 14h18v5H3zM7 7.5h.01M7 16.5h.01M11 7.5h6M11 16.5h6" },
  key: { tone: "#eab308", d: "M8 20a4.5 4.5 0 1 0 0-9 4.5 4.5 0 0 0 0 9zM11.2 12.3 20 3.5M16.5 7l3 3M14 9.5l2 2" },
  shield: { tone: "#f472b6", d: "M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6zM12.5 7.5l-2.5 4.5h4l-2.5 4.5" },
  coin: { tone: "#fbbf24", d: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM9 7.5h4.5a2 2 0 0 1 0 4.5H9h5a2 2 0 0 1 0 4.5H9zM11 5.5v2M11 16.5v2" },
  radar: { tone: "#2fb7c9", d: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 16a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM12 12l6-6" },
};

const GROUP: Record<string, keyof typeof GLYPH> = {
  ransomware: "lock",
  cyber_extortion: "lock",
  phishing: "hook",
  malicious_link: "hook",
  malicious_website: "hook",
  malware: "bug",
  mobile_attack: "bug",
  data_breach: "data",
  data_leak: "data",
  data_theft: "data",
  data_exfiltration: "data",
  online_scam: "scam",
  job_scam: "scam",
  investment_scam: "scam",
  social_engineering: "scam",
  deepfake_fraud: "scam",
  ddos: "flood",
  credential_attack: "key",
  account_takeover: "key",
  vulnerability_exploitation: "shield",
  zero_day: "shield",
  remote_code_execution: "shield",
  web_attack: "shield",
  sql_injection: "shield",
  supply_chain_attack: "shield",
  network_intrusion: "shield",
  crypto_attack: "coin",
};

/** Kunci glyph untuk jenis serangan (jenis pertama bila majemuk). */
export function glyphFor(attackType: string | null | undefined): Glyph {
  const key = (attackType ?? "").split(",")[0].trim().toLowerCase();
  return GLYPH[GROUP[key] ?? "radar"];
}

/**
 * Gambar incident: og:image salah satu artikelnya bila ada, di atas ubin grafis
 * bernada jenis serangan. Gambar yang gagal dimuat menghilang sehingga ubinnya
 * tetap terlihat; dengan begitu setiap kartu selalu bergambar.
 */
export function IncidentThumb({ src, attackType, className = "" }: { src?: string | null; attackType: string | null; className?: string }) {
  const glyph = glyphFor(attackType);
  const url = src ? src.replace(/&amp;/g, "&") : null;
  return (
    <span className={`inc-thumb ${className}`} style={{ "--tone": glyph.tone } as React.CSSProperties} aria-hidden="true">
      <svg viewBox="0 0 24 24" className="inc-thumb-glyph" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
        <path d={glyph.d} />
      </svg>
      {url ? <SafeImage src={url} alt="" fill unoptimized referrerPolicy="no-referrer" sizes="112px" className="object-cover" /> : null}
    </span>
  );
}
