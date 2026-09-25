import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getDict, isLang, L } from "@/lib/i18n";

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
      <div className="flex flex-col gap-2">
        <span className="label text-chain">{t.institutions.eyebrow}</span>
        <h1 className="text-balance text-[26px] font-semibold leading-tight">{t.institutions.title}</h1>
        <p className="max-w-[78ch] text-[14.5px] leading-relaxed text-soft">{t.institutions.lead}</p>
      </div>

      <section className="grid gap-3 sm:grid-cols-2">
        {t.institutions.orgs.map((m) => (
          <div key={m.org} className="card flex flex-col gap-1.5 p-4">
            <span className="text-[16px] font-semibold">{m.org}</span>
            <span className="text-[13px] text-soft">
              {t.institutions.mandate}: {m.scope}
            </span>
            <span className="font-mono text-[11.5px] text-muted">
              {t.institutions.routing} {m.route}
            </span>
          </div>
        ))}
      </section>

      <section className="card flex flex-col gap-2 p-4">
        <span className="label">{t.institutions.principlesTitle}</span>
        <ul className="ml-4 list-disc text-[13.5px] leading-relaxed text-soft">
          {t.institutions.principles.map((p) => (
            <li key={p}>{p}</li>
          ))}
        </ul>
      </section>

      <Link href={L(lang, "/incidents")} className="btn btn-ghost self-start">
        {t.institutions.cta}
      </Link>
    </div>
  );
}
