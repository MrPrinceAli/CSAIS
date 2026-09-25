import Link from "next/link";
import {
  getCountryCounts,
  getDailyArticles,
  getFeaturedIncidentId,
  getIncident,
  getLatestIncidents,
  getOverview,
  getRiskGroups,
  getSampleEvidence,
} from "@/lib/queries";
import { countryOf } from "@/lib/geo";
import { attackCode, domainOf, fmtDate, fmtDateTime, fmtNum, GROUP_LABEL, incidentTitle } from "@/lib/format";
import { trustScore } from "@/lib/trust";
import { Globe, type GlobeMarker } from "@/components/globe";
import { CountUp, Reveal, StoryRail } from "@/components/reveal";
import { DailyBars, HashGrid, IncidentCard, Sparkline, TrustRing } from "@/components/ui";

export const revalidate = 3600;

const CHAPTERS = [
  { id: "bab-0", label: "Peta" },
  { id: "bab-1", label: "Arus berita" },
  { id: "bab-2", label: "Penyaringan" },
  { id: "bab-3", label: "Satu kejadian" },
  { id: "bab-4", label: "Siapa diincar" },
  { id: "bab-5", label: "Bukti" },
  { id: "bab-6", label: "Lembaga" },
];

export default async function Home() {
  const [overview, latest, countries, daily, featuredId, groups, samples] = await Promise.all([
    getOverview(),
    getLatestIncidents(4),
    getCountryCounts(90),
    getDailyArticles(60),
    getFeaturedIncidentId(),
    getRiskGroups(),
    getSampleEvidence(),
  ]);
  const featured = featuredId ? await getIncident(featuredId) : null;

  const maxCountry = Math.max(...countries.map((c) => Number(c.n)), 1);
  const markers: GlobeMarker[] = countries
    .map((c) => {
      const geo = countryOf(c.location);
      return geo ? { location: [geo.lat, geo.lng] as [number, number], size: 0.035 + 0.13 * (Number(c.n) / maxCountry) } : null;
    })
    .filter((m): m is GlobeMarker => m !== null);
  const topCountries = countries.slice(0, 6);
  const totalLocated = countries.reduce((acc, c) => acc + Number(c.n), 0);
  const totalArticles60 = daily.reduce((acc, d) => acc + Number(d.n), 0);
  const featuredTrust = featured
    ? trustScore({
        independence: featured.incident.independence,
        domains: Number(featured.incident.domains ?? 0),
        docs: featured.docs.length,
        targetConfidence: featured.incident.target ? 0.9 : 0,
        contentShare: featured.docs.length ? featured.docs.filter((d) => d.content_status === "ok").length / featured.docs.length : 0,
        clustering: featured.incident.incident_confidence,
      })
    : null;
  const sample = samples[0];

  return (
    <div className="flex flex-col gap-24 pb-10">
      <StoryRail chapters={CHAPTERS} />

      {/* Bab 0: peta dunia */}
      <section id="bab-0" className="story-section grid-bg -mx-4 -mt-6 rounded-b-2xl px-4 pb-10 pt-10 sm:-mx-6 sm:px-6 lg:pt-14">
        <div className="mx-auto grid max-w-7xl items-center gap-8 lg:grid-cols-[minmax(0,1.05fr)_minmax(0,1fr)]">
          <div className="flex flex-col gap-5">
            <span className="font-mono text-[12px] uppercase tracking-[0.08em] text-accent">Cyber Social Attack Intelligence System</span>
            <h1 className="text-balance text-[34px] font-bold leading-[1.1] tracking-tight sm:text-[46px]">
              Serangan siber diberitakan di mana-mana. CSAIS membacanya setiap hari dan mengubahnya menjadi bukti.
            </h1>
            <p className="max-w-[56ch] text-[16px] leading-relaxed text-soft">
              Titik di globe adalah negara yang disebut artikel dalam 90 hari terakhir:{" "}
              {topCountries.map((c, i) => (
                <span key={c.location}>
                  {i > 0 ? ", " : ""}
                  <b className="text-fg">{countryOf(c.location)?.label ?? c.location}</b> {fmtNum(Number(c.n))}
                </span>
              ))}
              . Gulir untuk mengikuti perjalanan satu berita sampai menjadi bukti yang bisa diverifikasi.
            </p>
            <div className="grid grid-cols-3 gap-3">
              <div className="flex flex-col">
                <CountUp value={Number(overview.incident)} className="text-[28px] font-bold leading-tight" />
                <span className="label">incident dikelompokkan</span>
              </div>
              <div className="flex flex-col">
                <CountUp value={Number(overview.artikel)} className="text-[28px] font-bold leading-tight" />
                <span className="label">artikel kandidat</span>
              </div>
              <div className="flex flex-col">
                <CountUp value={Number(overview.bukti)} className="text-[28px] font-bold leading-tight text-chain" />
                <span className="label">bukti disiapkan</span>
              </div>
            </div>
            <div className="flex flex-wrap gap-3">
              <Link href="/incident" className="btn btn-primary">
                Buka dashboard incident
              </Link>
              <a href="#bab-1" className="btn btn-ghost">
                Ikuti ceritanya
              </a>
            </div>
          </div>
          <div className="relative mx-auto aspect-square w-full max-w-[520px]">
            <div className="glow absolute inset-0 rounded-full" aria-hidden="true" />
            <Globe markers={markers} label={`Globe dengan ${fmtNum(totalLocated)} incident dari ${countries.length} negara`} />
            <div className="absolute bottom-2 left-2 flex items-center gap-2 rounded-md border border-line bg-nav/85 px-2.5 py-1.5 font-mono text-[11px] text-muted">
              <span className="pulse inline-block h-2 w-2 rounded-full bg-accent" aria-hidden="true" />
              {fmtNum(totalLocated)} incident berlokasi · 90 hari · seret untuk memutar
            </div>
          </div>
        </div>
      </section>

      {/* Bab 1: arus berita */}
      <section id="bab-1" className="story-section grid items-center gap-8 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
        <Reveal className="flex flex-col gap-4">
          <span className="label text-accent">Bab 1 · Arus berita</span>
          <h2 className="text-balance text-[28px] font-bold leading-tight">Setiap hari ada ratusan artikel yang lolos saringan awal.</h2>
          <p className="text-[15px] leading-relaxed text-soft">
            Pekerja otomatis menarik berita dari Google News untuk 300-an kata kunci dalam delapan bahasa, lalu
            menilai judul dan ringkasannya: berita serangan sungguhan, atau tips, iklan, dan acara. Dalam 60 hari
            terakhir <b className="text-fg">{fmtNum(totalArticles60)}</b> artikel masuk sebagai kandidat.
          </p>
        </Reveal>
        <Reveal delay={120} className="card p-4">
          <div className="mb-2 flex items-baseline justify-between text-[12px] text-muted">
            <span>Artikel kandidat per hari</span>
            <span className="font-mono">60 hari terakhir</span>
          </div>
          <DailyBars data={daily} height={150} />
        </Reveal>
      </section>

      {/* Bab 2: penyaringan */}
      <section id="bab-2" className="story-section flex flex-col gap-6">
        <Reveal className="flex flex-col gap-3">
          <span className="label text-accent">Bab 2 · Penyaringan</span>
          <h2 className="max-w-[28ch] text-balance text-[28px] font-bold leading-tight">Dari artikel menjadi incident, lalu hanya yang dikuatkan lebih dari satu sumber.</h2>
        </Reveal>
        <Reveal delay={100} className="card p-5">
          <div className="grid gap-4 md:grid-cols-4">
            {[
              { label: "artikel kandidat", n: Number(overview.artikel), note: "lolos deteksi relevansi" },
              { label: "incident", n: Number(overview.incident), note: "artikel serupa digabung" },
              { label: "dikuatkan 2+ sumber", n: Number(overview.multi_all), note: "bukan berita tunggal" },
              { label: "target dikenali", n: Number(overview.target_known), note: "nama korban terekstrak" },
            ].map((step, i, arr) => {
              const pct = Math.max(6, Math.round((100 * step.n) / arr[0].n));
              return (
                <div key={step.label} className="flex flex-col gap-2">
                  <span className="label">{step.label}</span>
                  <span className="tnum text-[26px] font-bold leading-tight">{fmtNum(step.n)}</span>
                  <span className="block h-3 overflow-hidden rounded-sm bg-line">
                    <span className="block h-full rounded-sm bg-accent" style={{ width: `${pct}%`, opacity: 1 - i * 0.18 }} />
                  </span>
                  <span className="text-[12px] text-muted">{step.note}</span>
                </div>
              );
            })}
          </div>
        </Reveal>
      </section>

      {/* Bab 3: satu kejadian */}
      <section id="bab-3" className="story-section grid gap-8 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
        <Reveal className="flex flex-col gap-4">
          <span className="label text-accent">Bab 3 · Satu kejadian, banyak sumber</span>
          <h2 className="text-balance text-[28px] font-bold leading-tight">Puluhan berita tentang hal yang sama menjadi satu incident dengan garis waktu.</h2>
          <p className="text-[15px] leading-relaxed text-soft">
            Setiap artikel dibaca isinya, nama korban dan pelaku diekstrak, lalu artikel yang membahas kejadian yang
            sama digabung. Skor kepercayaan naik ketika domain yang berbeda melaporkan hal yang sama, bukan saat
            satu berita disalin berulang.
          </p>
          {featured ? (
            <Link href={`/incident/${featured.incident.incident_id}`} className="btn btn-ghost self-start">
              Buka incident ini
            </Link>
          ) : null}
        </Reveal>
        <Reveal delay={120}>
          {featured ? (
            <div className="card flex flex-col gap-4 p-5">
              <div className="flex items-start justify-between gap-4">
                <div className="flex flex-col gap-1">
                  <span className="font-mono text-[11.5px] text-muted">
                    {attackCode(featured.incident.attack_type).split(",")[0]} · {featured.incident.target}
                  </span>
                  <span className="text-[18px] font-bold leading-snug">{incidentTitle(featured.incident.title)}</span>
                  <span className="text-[12.5px] text-muted">
                    {fmtNum(featured.docs.length)} artikel · {fmtNum(Number(featured.incident.domains ?? 0))} domain · pertama {fmtDate(featured.incident.anchor_published_date)}
                  </span>
                </div>
                {featuredTrust ? <TrustRing trust={featuredTrust} size={64} showLabel /> : null}
              </div>
              <ol className="relative flex flex-col gap-3 border-l border-line pl-4">
                {featured.docs.slice(0, 5).map((d, i) => (
                  <li key={d.article_id} className="relative text-[13px]">
                    <span className={`absolute -left-[21px] top-1.5 h-2.5 w-2.5 rounded-full ${i === 0 ? "bg-accent" : d.syndicated_of ? "bg-line-2" : "bg-good"}`} aria-hidden="true" />
                    <span className="block font-mono text-[11px] text-muted">
                      {fmtDateTime(d.published_date)} · {d.source_domain || domainOf(d.resolved_url) || d.source_name}
                      {i === 0 ? " · pertama" : d.syndicated_of ? " · sindikasi" : ""}
                    </span>
                    <span className="block truncate">{d.title}</span>
                  </li>
                ))}
                {featured.docs.length > 5 ? <li className="text-[12px] text-muted">dan {fmtNum(featured.docs.length - 5)} artikel lagi</li> : null}
              </ol>
            </div>
          ) : (
            <div className="card p-5 text-[13.5px] text-muted">Belum ada incident bertarget dengan 3 sumber atau lebih dalam 45 hari terakhir.</div>
          )}
        </Reveal>
      </section>

      {/* Bab 4: siapa diincar */}
      <section id="bab-4" className="story-section flex flex-col gap-6">
        <Reveal className="flex flex-col gap-3">
          <span className="label text-accent">Bab 4 · Siapa yang diincar</span>
          <h2 className="max-w-[30ch] text-balance text-[28px] font-bold leading-tight">Kelompok korban dipetakan supaya langkah pencegahannya tepat sasaran.</h2>
          <p className="max-w-[70ch] text-[15px] leading-relaxed text-soft">
            Incident 30 hari terakhir menurut kelompok yang disebut artikelnya, dibandingkan 30 hari sebelumnya. Garis
            kecil adalah tren delapan pekan.
          </p>
        </Reveal>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          {groups.slice(0, 5).map((g, i) => (
            <Reveal key={g.group} delay={i * 70}>
              <Link href="/temuan" className="card flex h-full flex-col gap-2 p-4 no-underline hover:border-accent">
                <span className="text-[12px] text-muted">{GROUP_LABEL[g.group] ?? g.group}</span>
                <span className="tnum text-[26px] font-bold leading-tight text-fg">{fmtNum(g.now)}</span>
                <Sparkline values={g.weeks} width={160} height={34} />
                <span className={`font-mono text-[11.5px] ${g.now > g.prev ? "text-high" : g.now < g.prev ? "text-good" : "text-muted"}`}>
                  {g.prev ? `${g.now > g.prev ? "naik" : g.now < g.prev ? "turun" : "tetap"} dari ${fmtNum(g.prev)}` : "baru muncul"}
                </span>
              </Link>
            </Reveal>
          ))}
        </div>
      </section>

      {/* Bab 5: bukti */}
      <section id="bab-5" className="story-section grid items-center gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <Reveal className="flex flex-col gap-4">
          <span className="label text-chain">Bab 5 · Bukti yang bisa diverifikasi</span>
          <h2 className="text-balance text-[28px] font-bold leading-tight">Setiap artikel di-hash saat diambil. Hash itulah yang dicatat ke blockchain, bukan beritanya.</h2>
          <p className="text-[15px] leading-relaxed text-soft">
            Teks artikel, URL asli, dan waktu ambil menghasilkan sidik jari SHA-256. Sidik jari semua artikel dalam
            satu hari digabung menjadi satu akar Merkle yang dijangkarkan ke rantai. Siapa pun bisa mengecek apakah
            sebuah berita ada di catatan tanpa perlu percaya pada CSAIS.
          </p>
          <Link href="/verifikasi" className="btn btn-primary self-start">
            Coba verifikasi sebuah berita
          </Link>
        </Reveal>
        <Reveal delay={120} className="card flex flex-col gap-4 p-5">
          {sample ? (
            <>
              <div className="flex items-center gap-4">
                <HashGrid hex={sample.content_sha256} size={112} label="Sidik jari hash artikel contoh" />
                <div className="flex min-w-0 flex-col gap-1">
                  <span className="label">Contoh bukti terbaru</span>
                  <span className="truncate text-[14px] font-semibold">{sample.title}</span>
                  <span className="font-mono text-[11px] text-muted">evidence_uid {sample.evidence_uid}</span>
                </div>
              </div>
              <code className="block break-all rounded-md border border-line bg-nav p-3 font-mono text-[11.5px] text-soft">{sample.content_sha256}</code>
              <span className="text-[12px] text-muted">
                Kisi di kiri adalah 64 heksadesimal hash yang sama digambar sebagai warna; artikel yang berubah satu huruf pun menghasilkan pola berbeda.
              </span>
            </>
          ) : (
            <span className="text-[13.5px] text-muted">Belum ada artikel dengan hash isi penuh.</span>
          )}
        </Reveal>
      </section>

      {/* Bab 6: lembaga dan publik */}
      <section id="bab-6" className="story-section flex flex-col gap-6">
        <Reveal className="flex flex-col gap-3">
          <span className="label text-accent">Bab 6 · Untuk siapa</span>
          <h2 className="max-w-[30ch] text-balance text-[28px] font-bold leading-tight">Lembaga memberi atestasi, pelaksana literasi memakai temuannya.</h2>
        </Reveal>
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,1.1fr)]">
          <Reveal className="card flex flex-col gap-3 p-5">
            <h3 className="text-[17px] font-bold">Lembaga resmi</h3>
            <p className="text-[13.5px] leading-relaxed text-soft">
              BSSN, OJK, Komdigi, dan Polri mendapat antrean sesuai mandat dan menandatangani keputusan: dikonfirmasi,
              dibantah, sedang diselidiki, atau anotasi.
            </p>
            <Link href="/atestasi" className="text-[13px] no-underline">
              Cara kerjanya
            </Link>
          </Reveal>
          <Reveal delay={80} className="card flex flex-col gap-3 p-5">
            <h3 className="text-[17px] font-bold">Pelaksana literasi</h3>
            <p className="text-[13.5px] leading-relaxed text-soft">
              Kelompok yang sedang diincar, modus yang dipakai, dan langkah pencegahan yang bisa langsung disampaikan ke
              nasabah, siswa, atau pegawai.
            </p>
            <Link href="/temuan" className="text-[13px] no-underline">
              Lihat temuan
            </Link>
          </Reveal>
          <Reveal delay={160} className="card flex flex-col gap-3 p-5">
            <div className="flex items-center justify-between">
              <h3 className="text-[17px] font-bold">Terbaru dengan sumber terbanyak</h3>
              <span className="chip chip-good">30 hari</span>
            </div>
            {latest.map((row) => (
              <IncidentCard key={row.incident_id} row={row} />
            ))}
          </Reveal>
        </div>
      </section>
    </div>
  );
}
