import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getDict, isLang, L } from "@/lib/i18n";
import { Reveal } from "@/components/reveal";
import { OrgLogo } from "@/components/org-logo";
import { Signature } from "@/components/seal";

export async function generateMetadata({ params }: { params: Promise<{ lang: string }> }): Promise<Metadata> {
  const { lang } = await params;
  return { title: getDict(isLang(lang) ? lang : "id").nav.institutions };
}

export default async function InstitutionsPage({ params }: { params: Promise<{ lang: string }> }) {
  const { lang } = await params;
  if (!isLang(lang)) notFound();
  const t = getDict(lang);
  return (
    <div className="flex flex-col gap-6">
      <Reveal className="flex flex-col gap-2">
        <span className="label text-chain">{t.institutions.eyebrow}</span>
        <h1 className="text-balance text-[26px] font-semibold leading-tight">
          <span className="mark mark-chain">{t.institutions.title}</span>
        </h1>
        <p className="max-w-[78ch] text-[14.5px] leading-relaxed text-soft">{t.institutions.lead}</p>
        <div className="flex flex-wrap gap-1.5 pt-1">
          {t.institutions.decisions.map((d, i) => (
            <span key={d} className="chip chip-chain fade-up" style={{ "--i": i } as React.CSSProperties}>
              {d}
            </span>
          ))}
        </div>
      </Reveal>

      {/* Kartu segel: cincin berputar, tanda tangan menggambar dirinya */}
      <Reveal>
        <section className="grid gap-3 sm:grid-cols-2">
          {t.institutions.orgs.map((m, i) => (
            <div key={m.org} className="card lift fade-up grid grid-cols-[auto_minmax(0,1fr)] gap-4 p-4" style={{ "--i": i * 2, borderTopColor: "var(--chain)", borderTopWidth: 2 } as React.CSSProperties}>
              <OrgLogo org={m.org} size={64} />
              <div className="flex min-w-0 flex-col gap-1.5">
                <span className="text-[16px] font-semibold">{m.org}</span>
                <span className="text-[13px] text-soft">
                  {t.institutions.mandate}: {m.scope}
                </span>
                <span className="font-mono text-[11.5px] text-muted">
                  {t.institutions.routing} {m.route}
                </span>
                <div className="mt-1 flex flex-col gap-0.5">
                  <Signature width={200} />
                  <span className="font-mono text-[10.5px] text-muted">{t.institutions.signature}</span>
                </div>
              </div>
            </div>
          ))}
        </section>
      </Reveal>

      <Reveal>
        <section className="card flex flex-col gap-3 p-4">
          <span className="label">{t.institutions.principlesTitle}</span>
          <ol className="grid gap-2 md:grid-cols-2">
            {t.institutions.principles.map((p, i) => (
              <li key={p} className="fade-up grid grid-cols-[28px_minmax(0,1fr)] gap-2 text-[13.5px] leading-relaxed text-soft" style={{ "--i": i } as React.CSSProperties}>
                <span className="font-mono text-[12px] text-chain">0{i + 1}</span>
                <span>{p}</span>
              </li>
            ))}
          </ol>
        </section>
      </Reveal>

      <Link href={L(lang, "/incidents")} className="btn btn-ghost self-start">
        {t.institutions.cta}
      </Link>
    </div>
  );
}
