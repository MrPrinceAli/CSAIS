import type { Metadata } from "next";
import Link from "next/link";
import { getRiskGroups, type GroupStat } from "@/lib/queries";
import { attackLabel, fmtNum, GROUP_LABEL, incidentTitle } from "@/lib/format";
import { SectionTitle, Sparkline } from "@/components/ui";

export const metadata: Metadata = { title: "Temuan dan risiko" };
export const revalidate = 3600;

function levelOf(now: number, prev: number): { label: string; color: string } {
  if (now >= 20 || (now >= 8 && now > prev * 1.5)) return { label: "Tinggi", color: "var(--crit)" };
  if (now >= 5) return { label: "Sedang", color: "var(--high)" };
  return { label: "Rendah", color: "var(--med)" };
}

function trend(now: number, prev: number): { text: string; pct: number | null } {
  if (prev === 0) return { text: now ? "baru muncul" : "tidak ada", pct: null };
  const pct = Math.round((100 * (now - prev)) / prev);
  return { text: pct > 0 ? `naik ${pct}%` : pct < 0 ? `turun ${Math.abs(pct)}%` : "tetap", pct };
}

/** Matriks risiko: sumbu x jumlah incident 30 hari (log), sumbu y perubahan terhadap 30 hari sebelumnya. */
function RiskMatrix({ groups }: { groups: GroupStat[] }) {
  const w = 640;
  const h = 300;
  const pad = { l: 56, r: 24, t: 20, b: 40 };
  const maxN = Math.max(...groups.map((g) => g.now), 2);
  const xs = (n: number) => pad.l + ((w - pad.l - pad.r) * Math.log10(n + 1)) / Math.log10(maxN + 1);
  const ys = (pct: number) => {
    const clamped = Math.max(-100, Math.min(200, pct));
    return pad.t + ((h - pad.t - pad.b) * (200 - clamped)) / 300;
  };
  const zeroY = ys(0);
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full" role="img" aria-label="Matriks risiko kelompok korban">
      <rect x={pad.l} y={pad.t} width={w - pad.l - pad.r} height={zeroY - pad.t} fill="var(--crit)" opacity="0.05" />
      <line x1={pad.l} x2={w - pad.r} y1={zeroY} y2={zeroY} stroke="var(--line-2)" strokeDasharray="4 4" />
      <line x1={pad.l} x2={pad.l} y1={pad.t} y2={h - pad.b} stroke="var(--line)" />
      <line x1={pad.l} x2={w - pad.r} y1={h - pad.b} y2={h - pad.b} stroke="var(--line)" />
      <text x={pad.l - 8} y={zeroY + 4} textAnchor="end" fontSize="10" fill="var(--muted)" fontFamily="var(--font-jet), monospace">
        0%
      </text>
      <text x={pad.l - 8} y={ys(100) + 4} textAnchor="end" fontSize="10" fill="var(--muted)" fontFamily="var(--font-jet), monospace">
        +100%
      </text>
      <text x={pad.l - 8} y={ys(-100) + 4} textAnchor="end" fontSize="10" fill="var(--muted)" fontFamily="var(--font-jet), monospace">
        -100%
      </text>
      <text x={w - pad.r} y={h - 8} textAnchor="end" fontSize="10" fill="var(--muted)" fontFamily="var(--font-jet), monospace">
        jumlah incident 30 hari (skala log) →
      </text>
      <text x={pad.l - 40} y={pad.t + 8} fontSize="10" fill="var(--muted)" fontFamily="var(--font-jet), monospace">
        ↑ naik
      </text>
      {groups.map((g) => {
        const t = trend(g.now, g.prev);
        const pct = t.pct ?? 150;
        const lvl = levelOf(g.now, g.prev);
        const r = 6 + 10 * Math.sqrt(g.now / maxN);
        return (
          <g key={g.group}>
            <circle cx={xs(g.now)} cy={ys(pct)} r={r} fill={lvl.color} opacity="0.75">
              <title>{`${GROUP_LABEL[g.group] ?? g.group}: ${g.now} incident, ${t.text}`}</title>
            </circle>
            <text x={xs(g.now) + r + 4} y={ys(pct) + 4} fontSize="11" fill="var(--fg)">
              {GROUP_LABEL[g.group] ?? g.group}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

export default async function TemuanPage() {
  const groups = await getRiskGroups();
  const totalNow = groups.reduce((acc, g) => acc + g.now, 0);
  const rising = groups.filter((g) => g.now > g.prev).length;
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-[24px] font-bold">Temuan, kelompok berisiko, dan langkah preventif</h1>
        <p className="max-w-[84ch] text-[13.5px] text-muted">
          Kelompok korban diambil dari ekstraksi V0.3 pada incident 30 hari terakhir, dibandingkan 30 hari sebelumnya.
          {" "}{fmtNum(totalNow)} penyebutan kelompok pada 30 hari terakhir; {fmtNum(rising)} dari {fmtNum(groups.length)} kelompok sedang naik.
          Temuan berkeyakinan dan rekomendasi (Step 4 dan 5) menyusul setelah trust score selesai.
        </p>
      </div>

      <section className="grid gap-4 lg:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
        <div className="card p-4">
          <SectionTitle aside="kanan atas = banyak dan naik">Matriks risiko</SectionTitle>
          {groups.length ? <RiskMatrix groups={groups} /> : <p className="text-[13px] text-muted">Belum ada data.</p>}
        </div>
        <div className="card flex flex-col gap-3 p-4">
          <SectionTitle>Cara membaca</SectionTitle>
          <ul className="flex flex-col gap-2 text-[13px] leading-relaxed text-soft">
            <li>
              <b className="text-fg">Tinggi</b> bila 20 incident atau lebih, atau 8 atau lebih dengan kenaikan di atas 50 persen.
            </li>
            <li>
              <b className="text-fg">Sedang</b> bila 5 sampai 19 incident. <b className="text-fg">Rendah</b> di bawah itu.
            </li>
            <li>Ukuran lingkaran mengikuti jumlah incident; garis putus-putus adalah batas tidak berubah.</li>
            <li>Kelompok yang belum pernah muncul sebelumnya diletakkan di bagian paling atas sebagai &quot;baru muncul&quot;.</li>
          </ul>
        </div>
      </section>

      <section>
        <SectionTitle aside="garis: incident per pekan, 8 pekan">Kelompok berisiko</SectionTitle>
        {groups.length ? (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {groups.map((g) => {
              const lvl = levelOf(g.now, g.prev);
              const t = trend(g.now, g.prev);
              return (
                <div key={g.group} className="card flex flex-col gap-2 p-4" style={{ borderTop: `3px solid ${lvl.color}` }}>
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex flex-col">
                      <span className="text-[12px] text-muted">{GROUP_LABEL[g.group] ?? g.group}</span>
                      <span className="text-[20px] font-bold" style={{ color: lvl.color }}>
                        {lvl.label}
                      </span>
                    </div>
                    <Sparkline values={g.weeks} width={110} height={34} color={lvl.color} />
                  </div>
                  <span className="tnum font-mono text-[11.5px] text-soft">
                    {fmtNum(g.now)} incident · {t.text}
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {g.types.map((x) => (
                      <Link key={x.t} href={`/incident?jenis=${encodeURIComponent(x.t)}`} className="chip no-underline">
                        {attackLabel(x.t).toLowerCase()} {fmtNum(x.n)}
                      </Link>
                    ))}
                  </div>
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
          <span className="label">Menyusul di Step 4</span>
          <span className="text-[15px] font-semibold">Temuan dengan tingkat keyakinan</span>
          <p className="text-[13.5px] leading-relaxed text-soft">
            Incident bermodus sama digabung menjadi satu temuan; keyakinannya dihitung dari trust score incident
            penyusunnya, lalu dipetakan ke kelompok berisiko dan langkah preventif yang siap dipakai pelaksana literasi.
          </p>
        </div>
        <div className="card flex flex-col gap-2 p-4" style={{ borderColor: "var(--chain)" }}>
          <span className="label text-chain">Menyusul di Step 5</span>
          <span className="text-[15px] font-semibold">Paket rekomendasi berhash</span>
          <p className="text-[13.5px] leading-relaxed text-soft">
            Paket mingguan di-hash dan dicatat di rantai bersama tautan ke batch bukti penyusunnya, sehingga setiap
            rekomendasi bisa ditelusuri sampai artikel aslinya.
          </p>
        </div>
      </section>
    </div>
  );
}
