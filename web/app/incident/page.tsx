import type { Metadata } from "next";
import Link from "next/link";
import { getAttackTypeOptions, getDashboard, type DashboardFilters } from "@/lib/queries";
import { attackLabel, fmtNum } from "@/lib/format";
import { DailyBars, IncidentTable, SectionTitle, Stat, TypeBars } from "@/components/ui";

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
    min: Number.isFinite(min) && min > 1 ? min : undefined,
    hari: [7, 30, 90, 365].includes(hari) ? hari : 30,
    page: Number.isFinite(page) && page > 0 ? page : 1,
  };
}

function hrefWith(f: DashboardFilters, page: number): string {
  const params = new URLSearchParams();
  if (f.q) params.set("q", f.q);
  if (f.jenis) params.set("jenis", f.jenis);
  if (f.bahasa) params.set("bahasa", f.bahasa);
  if (f.min) params.set("min", String(f.min));
  if (f.hari && f.hari !== 30) params.set("hari", String(f.hari));
  if (page > 1) params.set("page", String(page));
  const s = params.toString();
  return s ? `/incident?${s}` : "/incident";
}

export default async function IncidentPage({ searchParams }: { searchParams: Promise<Search> }) {
  const filters = parseFilters(await searchParams);
  const [data, typeOptions] = await Promise.all([getDashboard(filters), getAttackTypeOptions()]);
  const pages = Math.max(1, Math.ceil(data.total / data.pageSize));

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <h1 className="text-[22px] font-bold">Incident</h1>
        <span className="text-[13px] text-muted">
          {fmtNum(data.total)} incident dalam {filters.hari} hari terakhir sesuai saringan
        </span>
      </div>

      <form method="get" action="/incident" className="card flex flex-wrap items-end gap-3 p-3.5">
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
          Minimal sumber
          <select id="min" name="min" defaultValue={String(filters.min ?? 1)} className="field">
            <option value="1">1</option>
            <option value="2">2</option>
            <option value="3">3</option>
            <option value="5">5</option>
            <option value="10">10</option>
          </select>
        </label>
        <label className="flex flex-col gap-1 text-[12px] text-muted">
          Rentang
          <select id="hari" name="hari" defaultValue={String(filters.hari)} className="field">
            <option value="7">7 hari</option>
            <option value="30">30 hari</option>
            <option value="90">90 hari</option>
            <option value="365">1 tahun</option>
          </select>
        </label>
        <button type="submit" className="btn btn-primary">
          Terapkan
        </button>
        <Link href="/incident" className="text-[13px] no-underline">
          Atur ulang
        </Link>
      </form>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Incident" value={fmtNum(data.kpi.total)} note={`${filters.hari} hari terakhir`} />
        <Stat label="Dengan 2+ sumber" value={fmtNum(data.kpi.multi)} note={data.kpi.total ? `${Math.round((100 * Number(data.kpi.multi)) / Number(data.kpi.total))}% dari incident` : ""} tone="good" />
        <Stat label="Target dikenali" value={fmtNum(data.kpi.target_known)} note="nama organisasi korban terekstrak" />
        <Stat label="Artikel berbahasa Indonesia" value={fmtNum(data.kpi.indonesia)} note="incident yang artikel jangkarnya berbahasa Indonesia" tone="high" />
      </div>

      <div className="grid gap-3 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <div className="card p-4">
          <SectionTitle aside="berdasarkan tanggal artikel pertama">Incident baru per hari</SectionTitle>
          <DailyBars data={data.daily} />
        </div>
        <div className="card p-4">
          <SectionTitle>Jenis serangan</SectionTitle>
          <TypeBars data={data.types} />
        </div>
      </div>

      <IncidentTable rows={data.rows} />

      <div className="flex flex-wrap items-center justify-between gap-3 text-[12.5px] text-muted">
        <span>
          Halaman {data.page} dari {fmtNum(pages)} · diurutkan berdasarkan jumlah sumber lalu tanggal
        </span>
        <div className="flex gap-3">
          {data.page > 1 ? (
            <Link href={hrefWith(filters, data.page - 1)} className="no-underline">
              Sebelumnya
            </Link>
          ) : null}
          {data.page < pages ? (
            <Link href={hrefWith(filters, data.page + 1)} className="no-underline">
              Berikutnya
            </Link>
          ) : null}
        </div>
      </div>
    </div>
  );
}
