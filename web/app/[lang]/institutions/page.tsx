import { notFound, permanentRedirect } from "next/navigation";
import { isLang } from "@/lib/i18n";

/** Halaman lembaga sudah digabung ke bawah halaman Transparansi (tab Cek bukti); alamat lama dialihkan permanen ke sana. */
export default async function InstitutionsRedirect({ params }: { params: Promise<{ lang: string }> }) {
  const { lang } = await params;
  if (!isLang(lang)) notFound();
  permanentRedirect(`/${lang}/transparency#lembaga`);
}
