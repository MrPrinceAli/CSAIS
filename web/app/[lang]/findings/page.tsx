import { notFound, permanentRedirect } from "next/navigation";
import { isLang } from "@/lib/i18n";

/** Temuan (kelompok berisiko) digabung ke bagian atas halaman Peringatan; alamat lama dialihkan. */
export default async function FindingsRedirect({ params }: { params: Promise<{ lang: string }> }) {
  const { lang } = await params;
  if (!isLang(lang)) notFound();
  permanentRedirect(`/${lang}/alerts`);
}
