/**
 * Panduan pencegahan umum untuk halaman temuan: satu langkah khusus kelompok
 * sasaran, lalu langkah untuk jenis serangan yang paling sering menimpa
 * kelompok itu, dan kanal pelaporan resmi yang relevan. Isinya praktik baku
 * yang lazim dianjurkan, bukan hasil pipeline; kunci jenis serangan sama
 * dengan v05_incidents.attack_type (huruf kecil).
 */
import type { Lang } from "./i18n";

type Text = Record<Lang, string>;

const BY_TYPE: Record<string, Text[]> = {
  phishing: [
    { id: "Periksa alamat pengirim dan tautan sebelum mengeklik; buka situs resmi dengan mengetik alamatnya sendiri.", en: "Check the sender and the link before clicking; open official sites by typing the address yourself." },
    { id: "Jangan pernah memberikan OTP, PIN, atau kata sandi, termasuk kepada yang mengaku petugas.", en: "Never share OTPs, PINs, or passwords, even with someone claiming to be staff." },
  ],
  malware: [
    { id: "Pasang aplikasi hanya dari toko resmi dan jangan membuka berkas APK kiriman chat.", en: "Install apps only from official stores and never open APK files sent over chat." },
    { id: "Perbarui sistem operasi dan aplikasi, dan biarkan perlindungan bawaan tetap aktif.", en: "Keep the operating system and apps updated and leave built-in protection on." },
  ],
  ransomware: [
    { id: "Buat cadangan data berkala di lokasi terpisah yang tidak selalu terhubung ke jaringan.", en: "Back up data regularly to a separate location that is not always connected." },
    { id: "Segera tambal perangkat yang menghadap internet, seperti VPN, firewall, dan server surel.", en: "Patch internet-facing devices such as VPNs, firewalls, and mail servers promptly." },
  ],
  data_breach: [
    { id: "Ganti kata sandi akun yang terdampak dan aktifkan verifikasi dua langkah.", en: "Change passwords on affected accounts and turn on two-step verification." },
    { id: "Waspadai pesan yang menyebut data pribadi Anda; kebocoran sering disusul penipuan yang meyakinkan.", en: "Be wary of messages quoting your personal data; leaks are often followed by convincing scams." },
  ],
  online_scam: [
    { id: "Verifikasi pihak lawan lewat kanal resmi sebelum mentransfer uang.", en: "Verify the other party through official channels before transferring money." },
    { id: "Cek nomor rekening atau telepon di cekrekening.id sebelum bertransaksi.", en: "Check the account or phone number on cekrekening.id before paying." },
  ],
  job_scam: [
    { id: "Lowongan resmi tidak memungut biaya pendaftaran, pelatihan, atau seragam.", en: "Genuine vacancies never charge registration, training, or uniform fees." },
    { id: "Cocokkan lowongan dengan situs dan akun resmi perusahaan.", en: "Match the vacancy against the company's official site and accounts." },
  ],
  investment_scam: [
    { id: "Pastikan perusahaan dan produknya berizin OJK sebelum menanam uang.", en: "Confirm the company and product are licensed by OJK before investing." },
    { id: "Curigai janji imbal hasil tinggi yang pasti dan desakan untuk segera bergabung.", en: "Distrust guaranteed high returns and pressure to join quickly." },
  ],
  credential_attack: [
    { id: "Gunakan kata sandi berbeda untuk setiap akun dengan bantuan pengelola kata sandi.", en: "Use a different password for every account with a password manager." },
    { id: "Aktifkan verifikasi dua langkah, utamakan aplikasi autentikator daripada SMS.", en: "Turn on two-step verification, preferably an authenticator app over SMS." },
  ],
  vulnerability_exploitation: [
    { id: "Pasang pembaruan keamanan segera, utamakan celah yang sedang dieksploitasi.", en: "Apply security updates quickly, prioritising flaws that are being exploited." },
    { id: "Batasi layanan yang terbuka ke internet dan pantau pemberitahuan vendor.", en: "Limit services exposed to the internet and follow vendor advisories." },
  ],
  network_intrusion: [
    { id: "Wajibkan verifikasi dua langkah untuk akses jarak jauh dan akun admin.", en: "Require two-step verification for remote access and admin accounts." },
    { id: "Pantau log akses dan siapkan rencana respons insiden yang sudah diuji.", en: "Monitor access logs and keep a tested incident response plan." },
  ],
  social_engineering: [
    { id: "Konfirmasi permintaan transfer atau data lewat kanal lain yang sudah dikenal.", en: "Confirm requests for money or data through a separate, known channel." },
    { id: "Tetapkan prosedur verifikasi untuk permintaan mendesak dari atasan atau keluarga.", en: "Agree on a verification step for urgent requests from bosses or family." },
  ],
  crypto_attack: [
    { id: "Jangan pernah membagikan frasa pemulihan dompet kepada siapa pun.", en: "Never share a wallet recovery phrase with anyone." },
    { id: "Periksa alamat situs dan kontrak sebelum menyetujui transaksi.", en: "Check the site address and contract before approving a transaction." },
  ],
  mobile_attack: [
    { id: "Jangan memasang APK dari luar toko resmi dan periksa izin yang diminta aplikasi.", en: "Avoid APKs from outside official stores and review app permissions." },
  ],
  malicious_link: [
    { id: "Jangan membuka tautan dari pesan yang tidak diminta; periksa ejaan domainnya.", en: "Do not open links in unsolicited messages; check the domain spelling." },
  ],
  ddos: [
    { id: "Pasang layanan mitigasi DDoS atau CDN untuk situs dan layanan publik.", en: "Put public sites and services behind DDoS mitigation or a CDN." },
  ],
  cyber_attack: [
    { id: "Aktifkan verifikasi dua langkah dan pasang pembaruan keamanan secara rutin.", en: "Turn on two-step verification and install security updates routinely." },
    { id: "Siapkan cadangan data dan kontak darurat untuk melaporkan insiden.", en: "Keep backups and an emergency contact for reporting incidents." },
  ],
};

// Jenis yang memakai panduan jenis lain yang sepadan
const ALIAS: Record<string, string> = {
  data_leak: "data_breach",
  data_theft: "data_breach",
  data_exfiltration: "data_breach",
  account_takeover: "credential_attack",
  zero_day: "vulnerability_exploitation",
  remote_code_execution: "vulnerability_exploitation",
  web_attack: "vulnerability_exploitation",
  sql_injection: "vulnerability_exploitation",
  deepfake_fraud: "social_engineering",
  malicious_website: "malicious_link",
  cyber_extortion: "ransomware",
  supply_chain_attack: "vulnerability_exploitation",
};

const BY_GROUP: Record<string, Text> = {
  INDIVIDUALS: { id: "Aktifkan verifikasi dua langkah di surel, bank, dan media sosial.", en: "Turn on two-step verification for email, banking, and social media." },
  EMPLOYEES: { id: "Laporkan surel mencurigakan ke tim TI dan jangan memproses pembayaran mendesak tanpa verifikasi.", en: "Report suspicious email to IT and never process urgent payments without verification." },
  STUDENTS: { id: "Waspadai tawaran beasiswa, kerja, atau pinjaman yang meminta data pribadi atau biaya.", en: "Be wary of scholarship, job, or loan offers asking for personal data or fees." },
  CHILDREN: { id: "Dampingi penggunaan gim dan media sosial; jangan bagikan foto atau lokasi kepada orang asing.", en: "Supervise games and social media; never share photos or locations with strangers." },
  JOB_SEEKERS: { id: "Lamar hanya lewat kanal resmi perusahaan dan jangan membayar untuk diterima kerja.", en: "Apply only through official company channels and never pay to be hired." },
  BUSINESSES: { id: "Terapkan hak akses minimum, cadangkan data, dan latih karyawan mengenali phishing.", en: "Apply least-privilege access, back up data, and train staff to spot phishing." },
  GOVERNMENT: { id: "Tambal sistem layanan publik secara berkala dan laporkan insiden ke BSSN.", en: "Patch public-service systems regularly and report incidents to BSSN." },
  BANK_CUSTOMERS: { id: "Bank tidak pernah meminta PIN atau OTP; hubungi nomor resmi di balik kartu Anda.", en: "Banks never ask for PINs or OTPs; call the official number on the back of your card." },
  SMES: { id: "Pisahkan rekening usaha, cadangkan data transaksi, dan waspadai pesanan atau faktur palsu.", en: "Keep a separate business account, back up transaction data, and watch for fake orders or invoices." },
  CIVIL_SERVANTS: { id: "Akses layanan kepegawaian hanya dari situs resmi go.id dan abaikan tautan kiriman chat.", en: "Use civil-service portals only via official go.id sites and ignore links sent over chat." },
  ELDERLY: { id: "Sepakati cara verifikasi dengan keluarga bila ada telepon mendesak soal uang.", en: "Agree on a family verification step for urgent calls about money." },
};

export type Channel = { name: string; url: string };
const CHANNELS: Record<string, Channel> = {
  patrol: { name: "Patroli Siber Polri", url: "https://patrolisiber.id" },
  ojk: { name: "Kontak OJK 157", url: "https://kontak157.ojk.go.id" },
  rekening: { name: "Cek Rekening", url: "https://cekrekening.id" },
  konten: { name: "Aduan Konten Komdigi", url: "https://aduankonten.id" },
};
const SCAM_TYPES = new Set(["online_scam", "job_scam", "investment_scam", "social_engineering", "deepfake_fraud", "crypto_attack"]);
const LINK_TYPES = new Set(["phishing", "malicious_link", "malicious_website"]);
const FINANCE_GROUPS = new Set(["BANK_CUSTOMERS", "SMES"]);

export type Prevention = { steps: string[]; channels: Channel[] };

/** Tiga langkah (kelompok, lalu jenis serangan teratas) dan kanal pelaporan untuk satu kelompok. */
export function preventionFor(group: string, types: string[], lang: Lang): Prevention {
  const steps: string[] = [];
  const groupTip = BY_GROUP[group];
  if (groupTip) steps.push(groupTip[lang]);
  const known = types.map((t) => ALIAS[t] ?? t).filter((t) => BY_TYPE[t]);
  const pool = (known.length ? known : ["cyber_attack"]).flatMap((t, i) => BY_TYPE[t].slice(0, i === 0 ? 2 : 1));
  for (const tip of pool) {
    if (steps.length >= 3) break;
    if (!steps.includes(tip[lang])) steps.push(tip[lang]);
  }
  const keys = new Set<string>();
  if (FINANCE_GROUPS.has(group) || types.includes("investment_scam")) keys.add("ojk");
  if (types.some((t) => SCAM_TYPES.has(t)) || group === "JOB_SEEKERS" || group === "ELDERLY") keys.add("rekening");
  if (types.some((t) => LINK_TYPES.has(t))) keys.add("konten");
  keys.add("patrol");
  return { steps, channels: [...keys].map((k) => CHANNELS[k]) };
}
