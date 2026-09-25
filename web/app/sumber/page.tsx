import type { Metadata } from "next";
import { getSources } from "@/lib/queries";
import { fmtDate, fmtNum } from "@/lib/format";

export const metadata: Metadata = { title: "Sumber" };
export const revalidate = 3600;

export default async function SumberPage() {
  const sources = await getSources();
  const total = sources.reduce((acc, s) => acc + Number(s.article_count), 0);
  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-col gap-1">
        <h1 className="text-[22px] font-bold">Registri sumber</h1>
        <p className="max-w-[80ch] text-[13.5px] text-muted">
          Domain media asli yang diketahui dari artikel yang isinya sudah diambil ({fmtNum(sources.length)} domain,
          {" "}{fmtNum(total)} artikel). Tipe dan negara dipakai trust score untuk membedakan media, lembaga resmi, dan
          blog. Sumber resmi (BSSN, Komdigi, OJK, Polri) akan masuk lewat crawler langsung pada gelombang berikutnya.
        </p>
      </div>
      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] border-collapse text-[13px]">
            <thead>
              <tr className="label border-b border-line text-left">
                <th className="px-3 py-2.5 font-medium">Domain</th>
                <th className="px-2 py-2.5 font-medium">Penerbit</th>
                <th className="px-2 py-2.5 font-medium">Tipe</th>
                <th className="px-2 py-2.5 font-medium">Negara</th>
                <th className="px-2 py-2.5 text-right font-medium">Artikel</th>
                <th className="px-3 py-2.5 font-medium">Terakhir</th>
              </tr>
            </thead>
            <tbody>
              {sources.map((s) => (
                <tr key={s.domain} className="border-b border-line last:border-b-0">
                  <td className="px-3 py-2 font-mono text-[12px]">{s.domain}</td>
                  <td className="px-2 py-2">{s.publisher_name || "-"}</td>
                  <td className="px-2 py-2">
                    <span className={`chip ${s.source_type === "OFFICIAL" ? "chip-good" : ""}`}>{s.source_type.toLowerCase()}</span>
                  </td>
                  <td className="px-2 py-2 text-soft">{s.country === "unknown" ? "-" : s.country}</td>
                  <td className="tnum px-2 py-2 text-right font-mono">{fmtNum(s.article_count)}</td>
                  <td className="px-3 py-2 font-mono text-[11.5px] text-muted">{fmtDate(s.last_seen)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
