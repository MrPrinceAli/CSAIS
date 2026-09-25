import type { Metadata } from "next";
import Link from "next/link";
import { getRiskGroups } from "@/lib/queries";
import { attackLabel, fmtNum, GROUP_LABEL, incidentTitle } from "@/lib/format";
import { SectionTitle } from "@/components/ui";

export const metadata: Metadata = { title: "Temuan dan risiko" };
export const revalidate = 3600;

function levelOf(now: number, prev: number): { label: string; cls: string } {
  if (now >= 20 || (now >= 8 && now > prev * 1.5)) return { label: "Tinggi", cls: "border-t-crit" };
  if (now >= 5) return { label: "Sedang", cls: "border-t-high" };
  return { label: "Rendah", cls: "border-t-med" };
}

function trend(now: number, prev: number): string {
  if (prev === 0) return now ? "baru muncul" : "tidak ada";
  const pct = Math.round((100 * (now - prev)) / prev);
  if (pct > 0) return `naik ${pct}%`;
  if (pct < 0) return `turun ${Math.abs(pct)}%`;
  return "tetap";
}

export default async function TemuanPage() {
  const groups = await getRiskGroups();
  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-col gap-1">
        <h1 className="text-[22px] font-bold">Temuan, kelompok berisiko, dan langkah preventif</h1>
        <p className="max-w-[80ch] text-[13.5px] text-muted">
          Kelompok korban diambil dari hasil ekstraksi V0.3 pada incident 30 hari terakhir, dibandingkan dengan 30
          hari sebelumnya. Temuan berkeyakinan dan rekomendasi (Step 4 dan 5) menyusul setelah trust score selesai;
          halaman ini menampilkan bahan mentahnya apa adanya.
        </p>
      </div>

      <section>
        <SectionTitle aside="incident unik per kelompok, 30 hari vs 30 hari sebelumnya">Kelompok berisiko</SectionTitle>
        {groups.length ? (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {groups.map((g) => {
              const level = levelOf(g.now, g.prev);
              return (
                <div key={g.group} className={`card flex flex-col gap-2 border-t-[3px] p-4 ${level.cls}`}>
                  <span className="text-[12px] text-muted">{GROUP_LABEL[g.group] ?? g.group}</span>
                  <div className="flex items-baseline gap-2">
                    <span className="text-[20px] font-bold">{level.label}</span>
                    <span className="tnum font-mono text-[11.5px] text-soft">
                      {fmtNum(g.now)} incident · {trend(g.now, g.prev)}
                    </span>
                  </div>
                  <span className="text-[12.5px] text-soft">
                    {g.types.length ? g.types.map((t) => attackLabel(t.t).toLowerCase()).join(", ") : "jenis serangan belum dikenali"}
                  </span>
                  {g.samples.length ? (
                    <ul className="mt-1 flex list-none flex-col gap-1 border-t border-line pt-2 text-[12.5px]">
                      {g.samples.map((s) => (
                        <li key={s.incident_id} className="truncate">
                          <Link href={`/incident/${s.incident_id}`} className="no-underline">
                            {incidentTitle(s.title)}
                          </Link>
                          <span className="font-mono text-[11px] text-muted"> · {fmtNum(s.document_count)} sumber</span>
                        </li>
                      ))}
                    </ul>
                  ) : null}
                </div>
              );
            })}
          </div>
        ) : (
          <div className="card p-4 text-[13.5px] text-muted">Belum ada kelompok korban yang terekstrak pada 60 hari terakhir.</div>
        )}
      </section>

      <section className="grid gap-3 lg:grid-cols-2">
        <div className="card flex flex-col gap-2 p-4">
          <span className="label">Yang menyusul di Step 4</span>
          <span className="text-[15px] font-semibold">Temuan dengan tingkat keyakinan</span>
          <p className="text-[13.5px] leading-relaxed text-soft">
            Beberapa incident yang bermodus sama digabung menjadi satu temuan, keyakinannya dihitung dari trust score
            incident penyusunnya, lalu dipetakan ke kelompok berisiko dan langkah preventif yang bisa langsung dipakai
            pelaksana literasi.
          </p>
        </div>
        <div className="card flex flex-col gap-2 border-chain p-4">
          <span className="label text-chain">Yang menyusul di Step 5</span>
          <span className="text-[15px] font-semibold">Paket rekomendasi berhash</span>
          <p className="text-[13.5px] leading-relaxed text-soft">
            Setiap paket mingguan di-hash dan dicatat di rantai bersama tautan ke batch bukti penyusunnya, sehingga
            rekomendasi bisa ditelusuri sampai artikel aslinya. Koreksi dilakukan lewat paket baru yang menunjuk paket
            yang digantikan.
          </p>
        </div>
      </section>
    </div>
  );
}
