/* Tampilan saran AI (csais/ai_prevention.py): sasaran literasi, materi, langkah, kanal, dan pesan kunci. */
import type { AiAdvice } from "@/lib/queries";
import { getDict, type Lang } from "@/lib/i18n";

export function AiBadge({ lang, model }: { lang: Lang; model?: string | null }) {
  const t = getDict(lang).ai;
  return (
    <span className="chip border-[color-mix(in_srgb,var(--chain)_55%,var(--line))] text-chain" title={model ? t.model(model) : undefined}>
      ✦ {t.badge}
    </span>
  );
}

export function AiAdviceView({ advice, lang, compact = false, parts = ["ringkasan", "sasaran", "materi", "langkah", "kanal", "pesan_kunci"] }: { advice: AiAdvice; lang: Lang; compact?: boolean; parts?: (keyof AiAdvice)[] }) {
  const t = getDict(lang).ai;
  const size = compact ? "text-[12.5px]" : "text-[13px]";
  const show = (key: keyof AiAdvice) => parts.includes(key);
  // satu bagian saja (sel tabel D1 - D4): judul barisnya sudah menamai bagian itu
  const heading = (text: string) => (parts.length > 1 ? <span className="label">{text}</span> : null);
  return (
    <div className={`flex flex-col gap-2.5 ${size}`}>
      {show("ringkasan") && advice.ringkasan ? <p className="leading-snug text-soft">{advice.ringkasan}</p> : null}
      {show("sasaran") && advice.sasaran.length ? (
        <div className="flex flex-col gap-1.5">
          {heading(t.targets)}
          <ul className="flex flex-col gap-1.5">
            {advice.sasaran.map((s) => (
              <li key={s.kelompok} className="flex flex-col gap-0.5 rounded-md border border-line px-2.5 py-1.5">
                <span className="font-semibold leading-snug text-fg">{s.kelompok}</span>
                {s.usia || s.wilayah ? (
                  <span className="text-[11.5px] text-accent">{[s.usia && t.age(s.usia), s.wilayah].filter(Boolean).join(" · ")}</span>
                ) : null}
                {s.alasan && !compact ? <span className="text-[11.5px] leading-snug text-muted">{s.alasan}</span> : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {show("materi") && advice.materi.length ? (
        <div className="flex flex-col gap-1">
          {heading(t.topics)}
          <ol className="flex list-decimal flex-col gap-0.5 pl-4 text-soft">
            {advice.materi.map((m) => (
              <li key={m}>{m}</li>
            ))}
          </ol>
        </div>
      ) : null}
      {show("langkah") && advice.langkah.length ? (
        <div className="flex flex-col gap-1">
          {heading(t.steps)}
          <ul className="flex list-disc flex-col gap-0.5 pl-4 text-soft">
            {advice.langkah.map((m) => (
              <li key={m}>{m}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {show("kanal") && advice.kanal.length ? (
        <p className="text-[11.5px] text-muted">
          {t.channels}: {advice.kanal.join(" · ")}
        </p>
      ) : null}
      {show("pesan_kunci") && advice.pesan_kunci ? (
        <p className="rounded-md border-l-2 border-chain bg-[color-mix(in_srgb,var(--chain)_8%,transparent)] px-2.5 py-1.5 font-semibold leading-snug text-fg">“{advice.pesan_kunci}”</p>
      ) : null}
    </div>
  );
}
