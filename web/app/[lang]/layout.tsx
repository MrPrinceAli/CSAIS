import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { IBM_Plex_Sans, JetBrains_Mono } from "next/font/google";
import type { ReactNode } from "react";
import "../globals.css";
import { getLastRun } from "@/lib/queries";
import { formatters } from "@/lib/format";
import { getDict, isLang, L, LANGS, type Lang } from "@/lib/i18n";
import { LangToggle } from "@/components/lang-toggle";
import { NavLinks } from "@/components/nav-links";
import { SurveyPopup } from "@/components/survey-popup";

const plex = IBM_Plex_Sans({ variable: "--font-plex", subsets: ["latin"], weight: ["400", "500", "600", "700"] });
const jet = JetBrains_Mono({ variable: "--font-jet", subsets: ["latin"], weight: ["400", "600"] });

export function generateStaticParams() {
  return LANGS.map((lang) => ({ lang }));
}

export async function generateMetadata({ params }: { params: Promise<{ lang: string }> }): Promise<Metadata> {
  const { lang } = await params;
  const t = getDict(isLang(lang) ? lang : "id");
  return {
    title: { default: t.brand, template: `%s · ${t.brand}` },
    description: lang === "en" ? t.home.lead : t.home.lead,
    alternates: { languages: { id: "/id", en: "/en" } },
  };
}

const NAV: { key: keyof ReturnType<typeof getDict>["nav"]; path: string }[] = [
  { key: "home", path: "/" },
  { key: "incidents", path: "/incidents" },
  { key: "alerts", path: "/alerts" },
  { key: "transparency", path: "/transparency" },
];

export default async function RootLayout({ children, modal, params }: { children: ReactNode; modal: ReactNode; params: Promise<{ lang: string }> }) {
  const { lang: raw } = await params;
  if (!isLang(raw)) notFound();
  const lang: Lang = raw;
  const t = getDict(lang);
  const f = formatters(lang);
  const lastRun = await getLastRun();

  return (
    <html lang={lang} className={`${plex.variable} ${jet.variable} h-full`}>
      <body className="min-h-full flex flex-col">
        <header className="sticky top-0 z-20 border-b border-line bg-nav/95 backdrop-blur">
          <div className="mx-auto flex h-14 w-full max-w-7xl items-center gap-6 px-4 sm:px-6">
            <Link href={L(lang, "/")} className="flex items-center gap-2.5 text-[15px] font-semibold tracking-wide text-fg no-underline hover:text-fg">
              <span className="signal" aria-hidden="true">
                <i />
              </span>
              {t.brand}
            </Link>
            <NavLinks items={NAV.map((item) => ({ href: L(lang, item.path), label: t.nav[item.key] }))} className="hidden items-center gap-5 text-[13.5px] md:flex" />
            <div className="ml-auto flex items-center gap-3">
              {lastRun ? (
                <span className="hidden items-center gap-2 font-mono text-[11px] text-muted lg:inline-flex">
                  <span className="led" aria-hidden="true" />
                  {t.status(f.dateTime(lastRun.finished_at), lastRun.pipeline_version.split("+")[0])}
                </span>
              ) : null}
              <LangToggle lang={lang} />
            </div>
          </div>
          <NavLinks items={NAV.map((item) => ({ href: L(lang, item.path), label: t.nav[item.key] }))} className="mx-auto flex w-full max-w-7xl gap-4 overflow-x-auto px-4 pb-2 text-[13px] md:hidden" linkClass="whitespace-nowrap" />
        </header>

        <div className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6">{children}</div>

        <footer className="mt-10 border-t border-line">
          <div className="mx-auto grid w-full max-w-7xl gap-8 px-4 py-8 text-[12.5px] sm:px-6 md:grid-cols-[minmax(0,1.4fr)_repeat(3,minmax(0,1fr))]">
            <div className="flex flex-col gap-2">
              <span className="flex items-center gap-2 font-semibold text-fg">
                <span className="inline-block h-3.5 w-3.5 rounded-[3px] bg-accent" aria-hidden="true" />
                {t.brand} <span className="font-normal text-muted">· {t.tagline}</span>
              </span>
              <p className="max-w-[52ch] leading-relaxed text-muted">{t.footer.about}</p>
              <span className="text-[12px] text-muted">{t.footer.updated}</span>
            </div>
            <div className="flex flex-col gap-2">
              <span className="label">{t.footer.columns.product}</span>
              <Link href={L(lang, "/incidents")} className="text-soft no-underline hover:text-fg">{t.nav.incidents}</Link>
              <Link href={L(lang, "/alerts")} className="text-soft no-underline hover:text-fg">{t.nav.alerts}</Link>
              <Link href={L(lang, "/transparency/sources")} className="text-soft no-underline hover:text-fg">{t.nav.sources}</Link>
            </div>
            <div className="flex flex-col gap-2">
              <span className="label">{t.footer.columns.method}</span>
              <Link href={`${L(lang, "/")}#process`} className="text-soft no-underline hover:text-fg">{t.footer.links.pipeline}</Link>
              <Link href={L(lang, "/transparency")} className="text-soft no-underline hover:text-fg">{t.footer.links.evidence}</Link>
              <Link href={`${L(lang, "/incidents")}#confidence`} className="text-soft no-underline hover:text-fg">{t.footer.links.confidence}</Link>
            </div>
            <div className="flex flex-col gap-2">
              <span className="label">{t.footer.columns.access}</span>
              <Link href={`${L(lang, "/transparency")}#lembaga`} className="text-soft no-underline hover:text-fg">{t.nav.institutions}</Link>
              <Link href={L(lang, "/survey")} className="text-soft no-underline hover:text-fg">{t.footer.links.survey}</Link>
              <Link href={L(lang, "/transparency/comparison")} className="text-soft no-underline hover:text-fg">{t.footer.links.comparison}</Link>
              <span className="text-muted">{t.footer.links.api}</span>
            </div>
          </div>
        </footer>
        {modal}
        <SurveyPopup
          lang={lang}
          strings={{
            eyebrow: t.surveyPopup.eyebrow,
            ask: t.surveyPopup.ask,
            rate: t.surveyPopup.rate,
            other: t.surveyPopup.other,
            close: t.surveyPopup.close,
            detail: t.surveyPopup.detail,
            publishers: t.surveyPopup.publishers,
            form: {
              answers: t.survey.answers,
              submit: t.survey.submit,
              sending: t.survey.sending,
              chooseOne: t.survey.chooseOne,
              thanks: t.surveyPopup.thanks,
              next: t.survey.next,
              failed: t.survey.failed,
              unknown: t.common.unknown,
            },
          }}
        />
      </body>
    </html>
  );
}
