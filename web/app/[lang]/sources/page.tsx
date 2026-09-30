import { notFound, permanentRedirect } from "next/navigation";
import { isLang } from "@/lib/i18n";

/** Sumber berita pindah ke tab di Transparansi; alamat lama (beserta ?q=) dialihkan. */
export default async function SourcesRedirect({ params, searchParams }: { params: Promise<{ lang: string }>; searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const { lang } = await params;
  if (!isLang(lang)) notFound();
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(await searchParams)) for (const v of [value].flat()) if (v !== undefined) query.append(key, v);
  const suffix = query.size ? `?${query}` : "";
  permanentRedirect(`/${lang}/transparency/sources${suffix}`);
}
