/*
 * Lencana "mesin AI" di pojok kanan atas Peta Literasi: inti bercahaya dengan
 * cincin gradasi berputar dan partikel mengorbit, nama model berkilau, status
 * pemrosesan, dan grafik batang mini. Angkanya dari hasil tahap AI terakhir
 * (csais/ai_prevention.py). Semua animasi CSS; mati bila kurangi gerakan.
 */
import type { AiStatus } from "@/lib/queries";
import { formatters } from "@/lib/format";
import { getDict, type Lang } from "@/lib/i18n";

/** "gemini-3.8-flash" -> "Gemini 3.8 Flash" */
export function modelName(model: string): string {
  return model
    .split(/[-_\s]+/)
    .map((part) => (/^\d/.test(part) ? part : part.charAt(0).toUpperCase() + part.slice(1)))
    .join(" ");
}

export function AiEngineBadge({ status, lang }: { status: AiStatus; lang: Lang }) {
  const t = getDict(lang).aiEngine;
  const f = formatters(lang);
  return (
    <div
      className="ai-engine relative flex items-center gap-3 overflow-hidden rounded-xl border border-[color-mix(in_srgb,var(--chain)_45%,var(--line))] bg-[color-mix(in_srgb,var(--bg)_70%,transparent)] py-2 pl-2.5 pr-3.5 backdrop-blur-md"
      title={t.title(status.model)}
    >
      <span className="ai-engine-scan" aria-hidden="true" />
      <span className="relative h-11 w-11 shrink-0" aria-hidden="true">
        <span className="ai-engine-ring absolute inset-0 rounded-full" />
        <span className="absolute inset-[5px] rounded-full bg-[var(--bg)]" />
        <span className="ai-engine-core absolute inset-[11px] rounded-full" />
        <span className="ai-engine-spark absolute inset-0 flex items-center justify-center text-[13px] text-white">✦</span>
        {[0, 1, 2].map((i) => (
          <span key={i} className="ai-engine-orbit absolute inset-0" style={{ animationDuration: `${2.6 + i * 1.3}s`, animationDelay: `${-i * 0.7}s` }}>
            <span
              className="absolute left-1/2 top-0 h-1.5 w-1.5 -translate-x-1/2 rounded-full"
              style={{ background: ["#8ab4ff", "#c58af9", "#2fb7c9"][i], boxShadow: `0 0 8px ${["#8ab4ff", "#c58af9", "#2fb7c9"][i]}` }}
            />
          </span>
        ))}
      </span>
      <span className="relative flex min-w-0 flex-col gap-0.5">
        <span className="flex items-center gap-2">
          <span className="ai-engine-name text-[14px] font-semibold leading-none">{modelName(status.model)}</span>
          <span className="flex items-center gap-1 rounded-full border border-[color-mix(in_srgb,var(--good)_50%,transparent)] px-1.5 py-px text-[9.5px] font-semibold uppercase tracking-wider text-good">
            <span className="ai-engine-live h-1.5 w-1.5 rounded-full bg-[var(--good)]" />
            {t.live}
          </span>
        </span>
        <span className="text-[11.5px] text-soft">
          {t.processing(f.num(status.incidents), f.num(status.provinces))}
          <span className="ai-engine-dots" aria-hidden="true">
            <span>.</span>
            <span>.</span>
            <span>.</span>
          </span>
        </span>
        <span className="flex items-center gap-2 text-[10.5px] text-muted">
          <span className="flex h-3 items-end gap-[2px]" aria-hidden="true">
            {[0, 1, 2, 3, 4, 5, 6].map((i) => (
              <span key={i} className="ai-engine-bar w-[3px] rounded-sm" style={{ animationDelay: `${-i * 0.17}s` }} />
            ))}
          </span>
          {t.outputs(f.num(status.flows))} · {f.dateTime(status.updated)}
        </span>
      </span>
    </div>
  );
}
