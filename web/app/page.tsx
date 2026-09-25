import Link from "next/link";
import { getLatestIncidents, getOverview } from "@/lib/queries";
import { fmtNum } from "@/lib/format";
import { IncidentCard, Stat } from "@/components/ui";

export const revalidate = 3600;

const STEPS = [
  { n: "1", kind: "AI", title: "Ekstraksi dan pengelompokan", text: "Jenis serangan, target, pelaku, waktu. Berita yang sama disatukan jadi satu incident." },
  { n: "2", kind: "Blockchain", title: "Pencatatan bukti", text: "Hash teks artikel, URL asli, dan waktu ambil digabung per batch harian, tidak bisa diubah." },
  { n: "3", kind: "AI", title: "Trust score", text: "Riwayat sumber, kebaruan, sumber independen, pertentangan antarinformasi, atestasi lembaga." },
  { n: "4", kind: "AI", title: "Temuan dan risiko", text: "Kelompok berisiko (nasabah, UMKM, ASN, pelajar) dipetakan ke risiko dan langkah preventif." },
  { n: "5", kind: "Blockchain", title: "Paket rekomendasi", text: "Hash paket dan tanda tangan, tautan ke bukti. Untuk pelaksana literasi digital." },
] as const;

export default async function Home() {
  const [overview, latest] = await Promise.all([getOverview(), getLatestIncidents(5)]);
  return (
    <div className="flex flex-col gap-10">
      <section className="grid items-center gap-8 lg:grid-cols-2">
        <div className="flex flex-col gap-5">
          <span className="font-mono text-[12px] uppercase tracking-[0.08em] text-accent">
            Cyber Social Attack Intelligence System
          </span>
          <h1 className="text-balance text-[34px] font-bold leading-[1.12] tracking-tight sm:text-[42px]">
            Dari ribuan berita serangan siber menjadi bukti yang bisa diverifikasi siapa pun.
          </h1>
          <p className="max-w-[56ch] text-[16px] leading-relaxed text-soft">
            CSAIS membaca berita dari media dan lembaga resmi setiap hari, mengelompokkannya menjadi
            incident, menghitung tingkat keyakinan tiap klaim, dan menyiapkan hash buktinya untuk
            dicatat di blockchain. Lembaga seperti BSSN, OJK, Komdigi, dan Polri nantinya memberi
            atestasi pada incident yang masuk mandatnya.
          </p>
          <div className="flex flex-wrap gap-3">
            <Link href="/incident" className="btn btn-primary">
              Lihat dashboard incident
            </Link>
            <Link href="/verifikasi" className="btn btn-ghost">
              Verifikasi sebuah berita
            </Link>
          </div>
        </div>
        <div className="card flex flex-col gap-3 p-4 sm:p-5">
          <div className="flex items-center justify-between gap-3">
            <span className="text-[13px] text-muted">Incident 30 hari dengan sumber terbanyak</span>
            <span className="chip chip-good">langsung dari Turso</span>
          </div>
          {latest.map((row) => (
            <IncidentCard key={row.incident_id} row={row} />
          ))}
          <Link href="/incident" className="self-end text-[13px] no-underline">
            Semua incident
          </Link>
        </div>
      </section>

      <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Artikel kandidat" value={fmtNum(overview.artikel)} note={`${fmtNum(overview.sumber)} domain sumber`} />
        <Stat label="Incident dikelompokkan" value={fmtNum(overview.incident)} note={`${fmtNum(overview.incident_30)} dalam 30 hari terakhir`} />
        <Stat label="Bukti disiapkan" value={fmtNum(overview.bukti)} note="hash teks artikel, siap dijangkarkan ke rantai" tone="chain" />
        <Stat label="Incident 2+ sumber, 30 hari" value={fmtNum(overview.multi_30)} note="dikuatkan lebih dari satu artikel" tone="good" />
      </section>

      <section className="flex flex-col gap-4">
        <div className="flex items-baseline justify-between gap-3">
          <h2 className="text-[22px] font-bold">Bagaimana CSAIS bekerja</h2>
          <span className="text-[13px] text-muted">AI untuk membaca, blockchain untuk mencatat</span>
        </div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          {STEPS.map((step) => (
            <div key={step.n} className="card flex min-h-[140px] flex-col gap-2 p-4">
              <span className={`label ${step.kind === "AI" ? "text-accent" : "text-chain"}`}>
                {step.n} · {step.kind}
              </span>
              <span className="text-[15px] font-semibold">{step.title}</span>
              <span className="text-[13px] leading-relaxed text-soft">{step.text}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <div className="card flex flex-col gap-3 p-5">
          <h2 className="text-[19px] font-bold">Untuk lembaga resmi</h2>
          <p className="text-[14px] leading-relaxed text-soft">
            Antrean incident yang masuk mandat lembaga Anda, siap diberi atestasi: dikonfirmasi,
            dibantah, sedang diselidiki, atau anotasi advisori. Tanda tangan dengan wallet terdaftar,
            tercatat di rantai.
          </p>
          <div className="flex flex-wrap gap-2">
            <span className="chip">BSSN · insiden dan kerentanan</span>
            <span className="chip">OJK · sektor keuangan</span>
            <span className="chip">Polri · penipuan dan pidana</span>
            <span className="chip">Komdigi · platform dan hoaks</span>
          </div>
          <Link href="/atestasi" className="btn btn-ghost self-start">
            Portal atestasi (segera)
          </Link>
        </div>
        <div className="card flex flex-col gap-3 p-5">
          <h2 className="text-[19px] font-bold">Untuk pelaksana literasi dan publik</h2>
          <p className="text-[14px] leading-relaxed text-soft">
            Kelompok yang sedang diincar, modus yang dipakai, dan langkah pencegahan yang bisa langsung
            disampaikan ke nasabah, siswa, atau pegawai. Setiap temuan bisa ditelusuri ke bukti aslinya.
          </p>
          <div className="flex flex-wrap gap-2">
            <span className="chip">Nasabah bank</span>
            <span className="chip">UMKM</span>
            <span className="chip">ASN dan PPPK</span>
            <span className="chip">Pelajar dan mahasiswa</span>
            <span className="chip">Lansia</span>
          </div>
          <Link href="/temuan" className="btn btn-primary self-start">
            Lihat kelompok berisiko
          </Link>
        </div>
      </section>
    </div>
  );
}
