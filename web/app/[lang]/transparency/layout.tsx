import type { ReactNode } from "react";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getDict, isLang, L } from "@/lib/i18n";
import { TabLinks } from "@/components/tab-links";

/** Transparansi: cek bukti (verifikasi), sumber berita, dan perbandingan D1-D4 dalam satu halaman bertab. */
export default async function TransparencyLayout({ children, params }: { children: ReactNode; params: Promise<{ lang: string }> }) {
  const { lang } = await params;
  if (!isLang(lang)) notFound();
  const t = getDict(lang).transparency;
  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-end justify-between gap-3 pt-2">
        <div className="flex max-w-[78ch] flex-col gap-1">
          <span className="label text-chain">{t.eyebrow}</span>
          <p className="text-[13.5px] text-muted">{t.lead}</p>
        </div>
        <Link href={L(lang, "/portal")} className="btn btn-ghost text-[13px]">
          {t.portal}
        </Link>
      </div>
      <TabLinks
        label={t.eyebrow}
        items={[
          { href: L(lang, "/transparency"), label: t.tabs.evidence },
          { href: L(lang, "/transparency/sources"), label: t.tabs.sources },
          { href: L(lang, "/transparency/comparison"), label: t.tabs.comparison },
        ]}
      />
      {children}
    </div>
  );
}
