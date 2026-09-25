import type { Metadata } from "next";
import Link from "next/link";
import { getAttackTypeOptions, getDashboard, type DashboardFilters } from "@/lib/queries";
import { countryOf } from "@/lib/geo";
import { attackLabel, fmtNum } from "@/lib/format";
import { Pagination } from "@/components/pagination";
import { DailyBars, IncidentTable, LabelBars, ScoreLegend, SectionTitle, Stat, TypeBars } from "@/components/ui";

export const metadata: Metadata = { title: "Incident" };

type Search = Record<string, string | string[] | undefined>;

function first(value: string | string[] | undefined): string {
  return Array.isArray(value) ? (value[0] ?? "") : (value ?? "");
}

function parseFilters(sp: Search): DashboardFilters {
  const min = Number.parseInt(first(sp.min), 10);
  const hari = Number.parseInt(first(sp.hari), 10);
  const page = Number.parseInt(first(sp.page), 10);
  return {
    q: first(sp.q).trim().slice(0, 80) || undefined,
    jenis: first(sp.jenis).trim().slice(0, 40) || undefined,
    bahasa: ["id", "en"].includes(first(sp.bahasa)) ? first(sp.bahasa) : undefined,
    negara: first(sp.negara).trim().slice(0, 40) || undefined,
    min: Number.isFinite(min) && min > 1 ? min : undefined,
    hari: [7, 30, 90, 365].includes(hari) ? hari : 30,
    page: Number.isFinite(page) && page > 0 ? page : 1,
  };
}

function params(f: DashboardFilters): Record<string, string | undefined> {
  return {
    q: f.q,
    jenis: f.jenis,
    bahasa: f.bahasa,
    negara: f.negara,
    min: f.min ? String(f.min) : undefined,
    hari: f.hari && f.hari !== 30 ? String(f.hari) : undefined,
  };
}

function hrefWith(f: DashboardFilters, overrides: Record<string, string | undefined>): string {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries({ ...params(f), ...overrides })) if (v) p.set(k, v);
  const s = p.toString();
  return s ? `/incident?${s}` : "/incident";
}

export default async function IncidentPage({ searchParams }: { searchParams: Promise<Search> }) {
  const filters = parseFilters(await searchParams);
  const [data, typeOptions] = await Promise.all([getDashboard(filters), getAttackTypeOptions()]);
  const active = [filters.q, filters.jenis, filters.bahasa, filters.negara, filters.min].filter(Boolean).length;

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex flex-col gap-1">
          <h1 className="text-[24px] font-bold">Incident</h1>
          <span className="text-[13px] text-muted">
            {fmtNum(data.total)} incident dalam {filters.hari} hari terakhir{active ? ` · ${active} saringan aktif` : ""}
          </span>
        </div>
        <div className="flex gap-2 text-[12.5px]">
          {[7, 30, 90, 365].map((d) => (
            <Link
              key={d}
              href={hrefWith(filters, { hari: d === 30 ? undefined : String(d), page: undefined })}
              className={`chip no-underline ${filters.hari === d ? "chip-accent" : ""}`}
            >
              {d === 365 ? "1 tahun" : `${d} hari`}
            </Link>
          ))}
        </div>
      </div>

      <form method="get" action="/incident" className="card flex flex-wrap items-end gap-3 p-3.5">
        {filters.hari && filters.hari !== 30 ? <input type="hidden" name="hari" value={filters.hari} /> : null}
        <label className="flex min-w-[220px] flex-1 flex-col gap-1 text-[12px] text-muted">
          Cari target, pelaku, atau judul
          <input id="q" name="q" type="search" defaultValue={filters.q ?? ""} placeholder="misalnya Telkomsel, LockBit, phishing" className="field" />
        </label>
        <label className="flex flex-col gap-1 text-[12px] text-muted">
          Jenis serangan
          <select id="jenis" name="jenis" defaultValue={filters.jenis ?? ""} className="field">
            <option value="">Semua</option>
            {typeOptions.map((t) => (
              <option key={t.t} value={t.t}>
                {attackLabel(t.t)}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-[12px] text-muted">
          Bahasa artikel
          <select id="bahasa" name="bahasa" defaultValue={filters.bahasa ?? ""} className="field">
            <option value="">Semua</option>
            <option value="id">Indonesia</option>
            <option value="en">Inggris</option>
          </select>
        </label>
        <label className="flex flex-col gap-1 text-[12px] text-muted">
          Negara
          <input id="negara" name="negara" type="text" defaultValue={filters.negara ?? ""} placeholder="indonesia" className="field w-32" />
        </label>
        <label className="flex flex-col gap-1 text-[12px] text-muted">
          Minimal sumber
          <select id="min" name="min" defaultValue={String(filters.min ?? 1)} className="field">
            <option value="1">1</option>
            <option value="2">2</option>
            <option value="3">3</option>
            <option value="5">5</option>
            <option value="10">10</option>
          </select>
        </label>
        <button type="submit" className="btn btn-primary">
          Terapkan
        </button>
        {active ? (
          <Link href="/incident" className="text-[13px] no-underline">
            Atur ulang
          </Link>
        ) : null}
      </form>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Incident" value={fmtNum(data.kpi.total)} note={`${filters.hari} hari terakhir`} />
        <Stat
          label="Dikuatkan 2+ sumber"
          value={fmtNum(data.kpi.multi)}
          note={data.kpi.total ? `${Math.round((100 * Number(data.kpi.multi)) / Number(data.kpi.total))}% dari incident` : ""}
          tone="good"
        />
        <Stat label="Target dikenali" value={fmtNum(data.kpi.target_known)} note="nama organisasi korban terekstrak" />
        <Stat label="Artikel jangkar berbahasa Indonesia" value={fmtNum(data.kpi.indonesia)} note="klik bahasa Indonesia untuk menyaring" tone="high" />
      </div>

      <div className="grid gap-3 lg:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)_minmax(0,1fr)]">
        <div className="card p-4">
          <SectionTitle aside="berdasarkan tanggal artikel pertama">Incident baru per hari</SectionTitle>
          <DailyBars data={data.daily} />
        </div>
        <div className="card p-4">
          <SectionTitle aside="klik untuk menyaring">Jenis serangan</SectionTitle>
          <TypeBars data={data.types} hrefFor={(t) => hrefWith(filters, { jenis: t, page: undefined })} />
        </div>
        <div className="card p-4">
          <SectionTitle aside="negara yang disebut artikel">Lokasi</SectionTitle>
          {data.countries.length ? (
            <LabelBars
              data={data.countries.map((c) => ({
                label: countryOf(c.location)?.label ?? c.location,
                n: Number(c.n),
                href: hrefWith(filters, { negara: c.location, page: undefined }),
              }))}
            />
          ) : (
            <p className="text-[13px] text-muted">Tidak ada lokasi terekstrak pada saringan ini.</p>
          )}
        </div>
      </div>

      <IncidentTable rows={data.rows} />
      <ScoreLegend />

      <Pagination
        page={data.page}
        pages={data.pages}
        total={data.total}
        pageSize={data.pageSize}
        label="incident"
        hrefFor={(p) => hrefWith(filters, { page: p > 1 ? String(p) : undefined })}
        action="/incident"
        hidden={params(filters)}
      />
    </div>
  );
}
