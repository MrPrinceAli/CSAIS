"use client";

/*
 * Pop-up survei publik (alur D2): kartu kecil di pojok kanan bawah yang muncul
 * setelah 20 detik atau setelah halaman digulir, sekali per kunjungan (muat
 * ulang = kunjungan baru; selama tahap pengujian tidak ada "jangan tampilkan
 * lagi"). Pengunjung bisa mengganti berita, menilai kartu, atau menutupnya.
 */
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { SurveyForm, type SurveyFieldView } from "@/components/survey-form";

type Card = {
  incidentId: string;
  outputId: number;
  title: string;
  documentCount: number;
  articles: { title: string; url: string | null; date: string }[];
  fields: SurveyFieldView[];
};

type Strings = {
  eyebrow: string;
  ask: string;
  rate: string;
  other: string;
  close: string;
  read: string;
  articles: string;
  form: {
    answers: Record<string, string>;
    submit: string;
    sending: string;
    chooseOne: string;
    thanks: string;
    next: string;
    failed: string;
    unknown: string;
  };
};

const DELAY_MS = 20_000;
const SCROLL_PX = 400;
// Tidak muncul di portal lembaga, halaman survei, dan saat detail incident terbuka
const HIDDEN = [/\/portal(\/|$)/, /\/survey(\/|$)/, /\/incidents\/INCIDENT_/];

export function SurveyPopup({ lang, strings }: { lang: string; strings: Strings }) {
  const pathname = usePathname() ?? "";
  const [phase, setPhase] = useState<"waiting" | "card" | "form" | "closed">("waiting");
  const [card, setCard] = useState<Card | null>(null);
  const seen = useRef<string[]>([]);
  const hidden = HIDDEN.some((re) => re.test(pathname));

  const load = useCallback(async () => {
    try {
      const response = await fetch(`/api/survey/card?lang=${lang}&exclude=${seen.current.join(",")}`, { cache: "no-store" });
      if (!response.ok) return false;
      const data = (await response.json()) as Card & { ok: boolean };
      if (!data.ok) return false;
      seen.current = [...seen.current, data.incidentId].slice(-50);
      setCard(data);
      return true;
    } catch {
      return false;
    }
  }, [lang]);

  useEffect(() => {
    if (phase !== "waiting") return;
    let fired = false;
    const show = async () => {
      if (fired) return;
      fired = true;
      if (await load()) setPhase("card");
    };
    const timer = window.setTimeout(show, DELAY_MS);
    const onScroll = () => {
      if (window.scrollY > SCROLL_PX) show();
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      window.clearTimeout(timer);
      window.removeEventListener("scroll", onScroll);
    };
  }, [phase, load]);

  if (hidden || !card || phase === "waiting" || phase === "closed") return null;

  return (
    <aside className="survey-pop" role="dialog" aria-label={strings.eyebrow}>
      <div className="flex items-start justify-between gap-3 border-b border-line px-3.5 py-2.5">
        <div className="flex min-w-0 flex-col gap-0.5">
          <span className="label text-med">{strings.eyebrow}</span>
          <span className="text-[12.5px] text-soft">{strings.ask}</span>
        </div>
        <button type="button" onClick={() => setPhase("closed")} className="survey-pop-close" aria-label={strings.close} title={strings.close}>
          ✕
        </button>
      </div>
      <div className="survey-pop-body">
        <div className="flex flex-col gap-1.5 px-3.5 py-3">
          <span className="text-[14px] font-semibold leading-snug">{card.title}</span>
          <span className="text-[11.5px] text-muted">
            {strings.read} · {card.documentCount} {strings.articles}
          </span>
          <ul className="flex flex-col gap-0.5 text-[12px]">
            {card.articles.map((a, i) =>
              a.url ? (
                <li key={i} className="truncate">
                  <span className="font-mono text-muted">{a.date} </span>
                  <a href={a.url} target="_blank" rel="noreferrer">
                    {a.title}
                  </a>
                </li>
              ) : null,
            )}
          </ul>
        </div>
        {phase === "form" ? (
          <SurveyForm key={card.outputId} lang={lang} incidentId={card.incidentId} outputId={card.outputId} fields={card.fields} strings={strings.form} onDone={() => setPhase("closed")} compact />
        ) : (
          <div className="flex flex-wrap gap-2 px-3.5 pb-3.5">
            <button type="button" className="btn btn-primary text-[13px]" onClick={() => setPhase("form")}>
              {strings.rate}
            </button>
            <button
              type="button"
              className="btn btn-ghost text-[13px]"
              onClick={async () => {
                await load();
              }}
            >
              {strings.other}
            </button>
          </div>
        )}
        {phase === "form" ? (
          <div className="px-3.5 pb-3">
            <button type="button" className="text-[12px] text-muted underline" onClick={async () => { if (await load()) setPhase("form"); }}>
              {strings.other}
            </button>
          </div>
        ) : null}
      </div>
    </aside>
  );
}
