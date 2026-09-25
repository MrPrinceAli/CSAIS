import type { Metadata } from "next";
import Link from "next/link";
import { getSources, type SourceFilters } from "@/lib/queries";
import { isoLabel } from "@/lib/geo";
import { fmtDate, fmtNum } from "@/lib/format";
import { Pagination } from "@/components/pagination";
import { LabelBars, SectionTitle, SourceLogo, Stat } from "@/components/ui";

export const metadata: Metadata = { title: "Sumber" };

type Search = Record<string, string | string[] | undefined>;

function first(value: string | string[] | undefined): string {
  return Array.isArray(value) ? (value[0] ?? "") : (value ?? "");
}

function parse(sp: Search): SourceFilters {
  const page = Number.parseInt(first(sp.page), 10);
  return {
    q: first(sp.q).trim().slice(0, 60) || undefined,
    tipe: ["media", "official", "blog"].includes(first(sp.tipe).toLowerCase()) ? first(sp.tipe).toLowerCase() : undefined,
    negara: first(sp.negara).trim().slice(0, 8) || undefined,
    urut: ["artikel", "terbaru", "nama"].includes(first(sp.urut)) ? first(sp.urut) : undefined,
    page: Number.isFinite(page) && page > 0 ? page : 1,
  };
}

function params(f: SourceFilters): Record<string, string | undefined> {
  return { q: f.q, tipe: f.tipe, negara: f.negara, urut: f.urut };
}

function hrefWith(f: SourceFilters, overrides: Record<string, string | undefined>): string {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries({ ...params(f), ...overrides })) if (v) p.set(k, v);
  const s = p.toString();
  return s ? `/sumber?${s}` : "/sumber";
}

export default async function SumberPage({ searchParams }: { searchParams: Promise<Search> }) {
  const filters = parse(await searchParams);
  const data = await getSources(filters);
  const totalArticles = data.byType.reduce((acc, t) => acc + Number(t.artikel), 0);
  const official = data.byType.find((t) => t.source_type === "OFFICIAL");

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-col gap-1">
        <h1 className="text-[24px] font-bold">Registri sumber</h1>
        <p className="max-w-[84ch] text-[13.5px] text-muted">
          Domain media asli yang diketahui dari artikel yang isinya sudah diambil. Tipe dan negara dipakai trust score
          untuk membedakan media, lembaga resmi, dan blog; logo diambil dari ikon situs masing-masing.
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Domain" value={fmtNum(data.byType.reduce((acc, t) => acc + Number(t.n), 0))} note={`${fmtNum(totalArticles)} artikel dengan URL asli`} />
        <Stat label="Media" value={fmtNum(Number(data.byType.find((t) => t.source_type === "MEDIA")?.n ?? 0))} note="situs berita dan portal" />
        <Stat label="Lembaga resmi" value={fmtNum(Number(official?.n ?? 0))} note="masuk lewat crawler langsung di gelombang 3" tone="high" />
        <Stat label="Negara dikenali" value={fmtNum(data.byCountry.filter((c) => c.country !== "unknown").length)} note="dari akhiran domain; sisanya .com tanpa negara" />
      </div>

      <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
        <div className="card p-4">
          <SectionTitle aside="klik untuk menyaring">Negara sumber</SectionTitle>
          <LabelBars
            data={data.byCountry.map((c) => ({
              label: isoLabel(c.country),
              n: Number(c.n),
              href: hrefWith(filters, { negara: c.country, page: undefined }),
            }))}
          />
        </div>
        <form method="get" action="/sumber" className="card flex flex-wrap items-end gap-3 p-3.5">
          <label className="flex min-w-[200px] flex-1 flex-col gap-1 text-[12px] text-muted">
            Cari domain atau penerbit
            <input id="q" name="q" type="search" defaultValue={filters.q ?? ""} placeholder="misalnya detik, bleepingcomputer" className="field" />
          </label>
          <label className="flex flex-col gap-1 text-[12px] text-muted">
            Tipe
            <select id="tipe" name="tipe" defaultValue={filters.tipe ?? ""} className="field">
              <option value="">Semua</option>
              <option value="media">Media</option>
              <option value="official">Lembaga resmi</option>
              <option value="blog">Blog</option>
            </select>
          </label>
          <label className="flex flex-col gap-1 text-[12px] text-muted">
            Negara
            <select id="negara" name="negara" defaultValue={filters.negara ?? ""} className="field">
              <option value="">Semua</option>
              {data.byCountry.map((c) => (
                <option key={c.country} value={c.country}>
                  {isoLabel(c.country)}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-[12px] text-muted">
            Urutkan
            <select id="urut" name="urut" defaultValue={filters.urut ?? "artikel"} className="field">
              <option value="artikel">Artikel terbanyak</option>
              <option value="terbaru">Terakhir terlihat</option>
              <option value="nama">Nama domain</option>
            </select>
          </label>
          <button type="submit" className="btn btn-primary">
            Terapkan
          </button>
          {filters.q || filters.tipe || filters.negara || filters.urut ? (
            <Link href="/sumber" className="text-[13px] no-underline">
              Atur ulang
            </Link>
          ) : null}
        </form>
      </div>

      {data.rows.length ? (
        <div className="grid gap-2.5 sm:grid-cols-2 xl:grid-cols-3">
          {data.rows.map((s) => (
            <div key={s.domain} className="card flex items-center gap-3 p-3">
              <SourceLogo domain={s.domain} size={28} />
              <div className="flex min-w-0 flex-1 flex-col gap-1">
                <div className="flex items-center justify-between gap-2">
                  <a href={`https://${s.domain}`} target="_blank" rel="noreferrer" className="truncate font-mono text-[12.5px] text-fg no-underline hover:text-accent">
                    {s.domain}
                  </a>
                  <span className={`chip ${s.source_type === "OFFICIAL" ? "chip-good" : ""}`}>{s.source_type.toLowerCase()}</span>
                </div>
                <span className="truncate text-[12px] text-soft">
                  {s.publisher_name || "penerbit tidak diketahui"} · {isoLabel(s.country)}
                </span>
                <div className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-2">
                  <span className="block h-1.5 overflow-hidden rounded-sm bg-line">
                    <span className="block h-full bg-accent" style={{ width: `${Math.max(3, (100 * Number(s.article_count)) / data.max)}%` }} />
                  </span>
                  <span className="tnum font-mono text-[11.5px] text-muted">
                    {fmtNum(s.article_count)} artikel · {fmtDate(s.last_seen)}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="card px-4 py-8 text-center text-[13.5px] text-muted">Tidak ada sumber yang cocok.</div>
      )}

      <Pagination
        page={data.page}
        pages={data.pages}
        total={data.total}
        pageSize={data.pageSize}
        label="domain"
        hrefFor={(p) => hrefWith(filters, { page: p > 1 ? String(p) : undefined })}
        action="/sumber"
        hidden={params(filters)}
      />
    </div>
  );
}
