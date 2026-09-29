"use client";

/* Formulir survei publik (alur D2): satu kartu inti, tiga pilihan per kolom. */
import { useState } from "react";

export type SurveyFieldView = { key: string; label: string; value: string | null };
type Strings = {
  answers: Record<string, string>;
  submit: string;
  sending: string;
  chooseOne: string;
  thanks: string;
  next: string;
  failed: string;
  unknown: string;
};

const OPTIONS = ["sesuai", "tidak_sesuai", "tidak_tahu"] as const;
const TONE: Record<string, string> = { sesuai: "var(--good)", tidak_sesuai: "var(--high)", tidak_tahu: "var(--muted)" };
const RESPONDENT_KEY = "csais-respondent";

/** Penanda acak per peramban, untuk menghitung responden berbeda; tidak memuat data pribadi. */
function respondentId(): string | null {
  try {
    let id = window.localStorage.getItem(RESPONDENT_KEY);
    if (!id) {
      id = crypto.randomUUID();
      window.localStorage.setItem(RESPONDENT_KEY, id);
    }
    return id;
  } catch {
    return null;
  }
}

export function SurveyForm({ lang, incidentId, outputId, fields, nextHref, strings }: { lang: string; incidentId: string; outputId: number; fields: SurveyFieldView[]; nextHref: string; strings: Strings }) {
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [state, setState] = useState<"idle" | "sending" | "done" | "error" | "empty">("idle");

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!Object.keys(answers).length) {
      setState("empty");
      return;
    }
    setState("sending");
    try {
      const response = await fetch("/api/survey", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ incident_id: incidentId, output_id: outputId, answers, respondent: respondentId(), lang }),
      });
      setState(response.ok ? "done" : "error");
    } catch {
      setState("error");
    }
  }

  if (state === "done") {
    return (
      <div className="card flex flex-col items-start gap-3 p-5" role="status">
        <p className="text-[14px] text-good">{strings.thanks}</p>
        <a href={nextHref} className="btn btn-primary no-underline">
          {strings.next}
        </a>
      </div>
    );
  }

  return (
    <form onSubmit={submit} className="card flex flex-col">
      {fields.map((field) => (
        <fieldset key={field.key} className="grid gap-3 border-b border-line px-4 py-3.5 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center">
          <legend className="sr-only">{field.label}</legend>
          <div className="flex min-w-0 flex-col gap-0.5">
            <span className="label">{field.label}</span>
            <span className={`text-[15px] font-semibold ${field.value ? "" : "font-normal text-muted"}`}>{field.value ?? strings.unknown}</span>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {OPTIONS.map((option) => {
              const id = `answer-${field.key}-${option}`;
              const checked = answers[field.key] === option;
              return (
                <label
                  key={option}
                  htmlFor={id}
                  className="cursor-pointer rounded-md border px-3 py-1.5 text-[13px] transition-colors focus-within:outline focus-within:outline-2"
                  style={{ borderColor: checked ? TONE[option] : "var(--line)", color: checked ? TONE[option] : undefined, background: checked ? `color-mix(in srgb, ${TONE[option]} 12%, transparent)` : undefined }}
                >
                  <input
                    id={id}
                    type="radio"
                    name={field.key}
                    value={option}
                    checked={checked}
                    onChange={() => {
                      setAnswers((prev) => ({ ...prev, [field.key]: option }));
                      setState("idle");
                    }}
                    className="sr-only"
                  />
                  {strings.answers[option]}
                </label>
              );
            })}
          </div>
        </fieldset>
      ))}
      <div className="flex flex-wrap items-center gap-3 px-4 py-3.5">
        <button type="submit" className="btn btn-primary" disabled={state === "sending"}>
          {state === "sending" ? strings.sending : strings.submit}
        </button>
        {state === "empty" ? <span className="text-[13px] text-med">{strings.chooseOne}</span> : null}
        {state === "error" ? <span className="text-[13px] text-high">{strings.failed}</span> : null}
      </div>
    </form>
  );
}
