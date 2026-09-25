import type { Metadata } from "next";
import Link from "next/link";
import { getSampleEvidence, verify } from "@/lib/queries";
import { EVIDENCE_LABEL, fmtDateTime } from "@/lib/format";
import { HashGrid } from "@/components/ui";

export const metadata: Metadata = { title: "Verifikasi bukti" };

type Search = Record<string, string | string[] | undefined>;

export default async function VerifikasiPage({ searchParams }: { searchParams: Promise<Search> }) {
  const sp = await searchParams;
  const raw = Array.isArray(sp.q) ? sp.q[0] : sp.q;
  const input = (raw ?? "").trim().slice(0, 600);
  const [result, samples] = await Promise.all([input ? verify(input) : Promise.resolve(null), getSampleEvidence()]);

  return (
    <div className="flex flex-col gap-6">
      <section className="grid gap-6 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,0.8fr)]">
        <div className="flex flex-col gap-3">
          <h1 className="text-balance text-[28px] font-bold leading-tight">Apakah berita ini tercatat sebagai bukti di CSAIS?</h1>
          <p className="max-w-[70ch] text-[14.5px] leading-relaxed text-soft">
            Tempel tautan artikel, hash SHA-256 teksnya, atau ID bukti. Sistem mencari artikel itu di bukti yang sudah
            disiapkan dan menunjukkan sidik jari hash serta incident tempatnya bergabung. Pencocokan ke rantai (bukti
            Merkle dan transaksi) menyusul begitu kontraknya terpasang.
          </p>
          <form method="get" action="/verifikasi" className="flex w-full flex-col gap-2 sm:flex-row">
            <label htmlFor="q" className="sr-only">
              Tautan, hash, atau ID bukti
            </label>
            <input id="q" name="q" type="text" defaultValue={input} placeholder="https://... atau 64 heksadesimal atau evidence_uid" className="field flex-1 py-2.5 font-mono text-[12.5px]" />
            <button type="submit" className="btn btn-primary justify-center">
              Verifikasi
            </button>
          </form>
          {!input && samples.length ? (
            <div className="flex flex-wrap items-center gap-2 text-[12.5px] text-muted">
              <span>Coba dengan bukti terbaru:</span>
              {samples.map((s) => (
                <Link key={s.evidence_uid} href={`/verifikasi?q=${s.evidence_uid}`} className="chip chip-accent no-underline">
                  {s.evidence_uid}
                </Link>
              ))}
            </div>
          ) : null}
        </div>
        <div className="card grid grid-cols-[auto_minmax(0,1fr)] items-center gap-4 p-4">
          <HashGrid hex={result?.article?.content_sha256 ?? samples[0]?.content_sha256 ?? null} size={112} label="Sidik jari hash" />
          <div className="flex flex-col gap-1 text-[12.5px] text-soft">
            <span className="label">Sidik jari hash</span>
            <span>
              64 heksadesimal SHA-256 digambar sebagai kisi 8×8. Satu huruf berubah pada artikel, seluruh polanya berubah.
              Inilah yang dijangkarkan ke rantai, bukan teks beritanya.
            </span>
          </div>
        </div>
      </section>

      {result ? (
        result.article ? (
          <section className="card flex flex-col gap-4 p-5">
            <div className="flex items-start gap-3">
              <span className="mt-0.5 inline-flex h-8 w-8 flex-none items-center justify-center rounded-full bg-good" aria-hidden="true">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#0f1720" strokeWidth="3">
                  <path d="M5 12l5 5L20 7" />
                </svg>
              </span>
              <div className="flex flex-col">
                <span className="text-[16px] font-bold">Ditemukan. Artikel ini ada di bukti CSAIS.</span>
                <span className="text-[12.5px] text-muted">
                  Dicocokkan lewat {result.kind === "hash" ? "hash SHA-256" : result.kind === "url" ? "tautan" : "ID"}.
                  {result.article.content_fetched_at ? ` Isi diambil ${fmtDateTime(result.article.content_fetched_at)}.` : " Isi penuh belum diambil; hash dihitung dari judul dan ringkasan."}
                </span>
              </div>
            </div>
            <div className="grid gap-4 md:grid-cols-[auto_minmax(0,1fr)]">
              <HashGrid hex={result.article.content_sha256 ?? result.evidence[0]?.content_fingerprint} size={128} label="Sidik jari hash artikel ini" />
              <dl className="grid grid-cols-[130px_minmax(0,1fr)] gap-x-4 gap-y-2 text-[13px]">
                <dt className="text-muted">Artikel</dt>
                <dd>
                  <a href={result.article.resolved_url ?? result.article.article_url ?? "#"} target="_blank" rel="noreferrer" className="no-underline">
                    {result.article.title ?? "(tanpa judul)"}
                  </a>
                </dd>
                <dt className="text-muted">Terbit</dt>
                <dd>{fmtDateTime(result.article.published_date)}</dd>
                <dt className="text-muted">article_uid</dt>
                <dd className="break-all font-mono">{result.article.article_uid ?? "-"}</dd>
                <dt className="text-muted">SHA-256 teks</dt>
                <dd className="break-all font-mono">{result.article.content_sha256 ?? "belum ada (isi belum diambil)"}</dd>
                {result.evidence.map((e) => (
                  <div key={e.evidence_uid} className="contents">
                    <dt className="text-muted">Bukti</dt>
                    <dd className="flex flex-wrap items-center gap-2">
                      <span className="font-mono">{e.evidence_uid}</span>
                      <span className="chip">{EVIDENCE_LABEL[e.evidence_type ?? ""] ?? e.evidence_type}</span>
                      <Link href={`/incident/${e.incident_id}`} className="no-underline">
                        buka incident
                      </Link>
                    </dd>
                  </div>
                ))}
                <dt className="text-muted">Di rantai</dt>
                <dd>
                  <span className="chip chip-chain">Belum dijangkarkan: kontrak Sepolia menyusul</span>
                </dd>
              </dl>
            </div>
          </section>
        ) : (
          <section className="card flex flex-col gap-2 p-5">
            <span className="text-[16px] font-bold">Tidak ditemukan.</span>
            <p className="text-[13.5px] text-soft">
              {result.kind === "kosong"
                ? "Masukkan tautan, hash, atau ID bukti."
                : "Artikel ini tidak ada di antara kandidat yang diproses CSAIS, atau tautannya bukan URL media asli yang tersimpan. Coba tempel tautan dari Google News atau tautan asli media."}
            </p>
          </section>
        )
      ) : null}

      <section className="grid gap-3 sm:grid-cols-3">
        {[
          { n: "1", cls: "text-accent", t: "Hash dihitung saat pengambilan", d: "Teks utama artikel diambil dari situs media, lalu di-hash SHA-256 bersama waktu ambil dan URL aslinya." },
          { n: "2", cls: "text-accent", t: "Bukti diberi ID tetap", d: "evidence_uid diturunkan dari incident dan artikel, sama di database mana pun, sehingga bisa dirujuk dari luar." },
          { n: "3", cls: "text-chain", t: "Dijangkarkan ke rantai", d: "Tiap run harian, akar Merkle dari semua hash baru dicatat di kontrak; halaman ini nanti menampilkan bukti Merkle dan transaksinya." },
        ].map((s) => (
          <div key={s.n} className="card flex flex-col gap-1.5 p-4">
            <span className={`label ${s.cls}`}>Langkah {s.n}</span>
            <span className="text-[14px] font-semibold">{s.t}</span>
            <span className="text-[12.5px] leading-relaxed text-soft">{s.d}</span>
          </div>
        ))}
      </section>
    </div>
  );
}
