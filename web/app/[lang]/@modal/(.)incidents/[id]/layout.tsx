import { notFound } from "next/navigation";
import { getDict, isLang, L } from "@/lib/i18n";
import { IncidentModal } from "@/components/incident-modal";

/**
 * Bingkai jendela pop-up detail incident (rute yang dicegat dari halaman mana
 * pun di bawah /[lang]); tetap terpasang selama isi detail dimuat. Alamat
 * detail yang dibuka langsung atau dimuat ulang merender halaman penuh.
 */
export default async function ModalFrame({ children, params }: { children: React.ReactNode; params: Promise<{ lang: string; id: string }> }) {
  const { lang, id } = await params;
  if (!isLang(lang)) notFound();
  const c = getDict(lang).incidents.cc;
  return (
    <IncidentModal id={id} fullHref={L(lang, `/incidents/${id}`)} labels={{ close: c.close, full: c.openFull, esc: c.escHint }}>
      {children}
    </IncidentModal>
  );
}
