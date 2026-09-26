import { notFound } from "next/navigation";
import { isLang } from "@/lib/i18n";
import { IncidentDetailView } from "@/components/incident-detail";

/** Detail incident di dalam jendela pop-up (navigasi di dalam situs). */
export default async function IncidentModalPage({ params }: { params: Promise<{ lang: string; id: string }> }) {
  const { lang, id } = await params;
  if (!isLang(lang)) notFound();
  return <IncidentDetailView lang={lang} id={id} variant="modal" />;
}
