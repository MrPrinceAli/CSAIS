import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getIncident } from "@/lib/queries";
import { incidentTitle } from "@/lib/format";
import { getDict, isLang } from "@/lib/i18n";
import { IncidentDetailView } from "@/components/incident-detail";

type Params = { lang: string; id: string };

export async function generateMetadata({ params }: { params: Promise<Params> }): Promise<Metadata> {
  const { lang, id } = await params;
  const data = await getIncident(id);
  return { title: data ? incidentTitle(data.incident.title) : getDict(isLang(lang) ? lang : "id").notFound.title };
}

export default async function IncidentDetail({ params }: { params: Promise<Params> }) {
  const { lang, id } = await params;
  if (!isLang(lang)) notFound();
  return <IncidentDetailView lang={lang} id={id} />;
}
