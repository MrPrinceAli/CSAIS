import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = { title: "Untuk lembaga" };

const MANDATES = [
  { org: "BSSN", scope: "insiden siber, kerentanan, infrastruktur informasi vital", route: "jenis serangan teknis dan target instansi" },
  { org: "OJK", scope: "bank, asuransi, fintech, pasar modal", route: "target sektor FINANCE dan kelompok nasabah" },
  { org: "Polri", scope: "penipuan online, pidana siber, penangkapan", route: "jenis ONLINE_SCAM, JOB_SCAM, INVESTMENT_SCAM" },
  { org: "Komdigi", scope: "platform digital, PSE, hoaks, konten", route: "target platform dan artikel bertema hoaks" },
] as const;

export default function AtestasiPage() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-2">
        <span className="label text-chain">Tahap berikutnya</span>
        <h1 className="text-balance text-[26px] font-bold leading-tight">Portal atestasi untuk lembaga resmi</h1>
        <p className="max-w-[76ch] text-[14.5px] leading-relaxed text-soft">
          Lembaga masuk dengan wallet yang terdaftar di kontrak CSAIS, melihat antrean incident sesuai mandatnya,
          lalu memberi keputusan: dikonfirmasi, dibantah, sedang diselidiki, atau anotasi advisori. Keputusan
          ditandatangani (EIP-712) dan dikirim ke rantai oleh relayer CSAIS, jadi lembaga tidak perlu memegang token.
          Portal ini dibuka setelah kontrak di Sepolia terpasang.
        </p>
      </div>

      <section className="grid gap-3 sm:grid-cols-2">
        {MANDATES.map((m) => (
          <div key={m.org} className="card flex flex-col gap-1.5 p-4">
            <span className="text-[16px] font-bold">{m.org}</span>
            <span className="text-[13px] text-soft">Mandat: {m.scope}</span>
            <span className="font-mono text-[11.5px] text-muted">Antrean dirutekan dari {m.route}</span>
          </div>
        ))}
      </section>

      <section className="card flex flex-col gap-2 p-4">
        <span className="label">Prinsip yang dipakai</span>
        <ul className="ml-4 list-disc text-[13.5px] leading-relaxed text-soft">
          <li>Bukti dicatat apa adanya begitu terkumpul; atestasi lembaga ditambahkan setelahnya, tidak menjadi gerbang.</li>
          <li>Tidak ada atestasi tidak berarti tidak valid; sebagian besar incident memang tidak akan ditinjau lembaga.</li>
          <li>Atestasi bersifat tambah-saja: yang baru menggantikan yang lama, riwayatnya tetap ada.</li>
          <li>Kunci lembaga terdaftar di kontrak dengan rotasi dan pencabutan; isi catatan disimpan off-chain, hash-nya di rantai.</li>
        </ul>
      </section>

      <Link href="/incident" className="btn btn-ghost self-start">
        Sementara itu, lihat incident yang menunggu
      </Link>
    </div>
  );
}
