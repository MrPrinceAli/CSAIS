"use client";

/* Kartu tinjauan portal lembaga: keputusan, alasan, dan penandaan kolom dengan tombol. */
import { useState } from "react";

export type ReviewFieldView = { key: string; label: string; value: string | null };
type Strings = {
  decision: string;
  reason: string;
  fieldsTitle: string;
  fieldsHint: string;
  fieldValues: Record<string, string>;
  note: string;
  source: string;
  reviewer: string;
  submit: string;
  sending: string;
  saved: string;
  again: string;
  failed: string;
  chooseReason: string;
  statuses: Record<string, string>;
  reasons: Record<string, string>;
  unknown: string;
};

const STATUS_TONE: Record<string, string> = { dikonfirmasi: "var(--good)", dibantah: "var(--high)", sebagian: "var(--med)" };

function Choice({ id, name, checked, tone, label, onChange }: { id: string; name: string; checked: boolean; tone: string; label: string; onChange: () => void }) {
  return (
    <label
      htmlFor={id}
      className="cursor-pointer rounded-md border px-3 py-1.5 text-[13px] transition-colors focus-within:outline focus-within:outline-2"
      style={{ borderColor: checked ? tone : "var(--line)", color: checked ? tone : undefined, background: checked ? `color-mix(in srgb, ${tone} 12%, transparent)` : undefined }}
    >
      <input id={id} type="radio" name={name} checked={checked} onChange={onChange} className="sr-only" />
      {label}
    </label>
  );
}

export function ReviewCard({ incidentId, outputId, fields, reasonsByStatus, strings }: { incidentId: string; outputId: number; fields: ReviewFieldView[]; reasonsByStatus: Record<string, string[]>; strings: Strings }) {
  const [status, setStatus] = useState<string | null>(null);
  const [reason, setReason] = useState<string | null>(null);
  const [marks, setMarks] = useState<Record<string, string>>({});
  const [note, setNote] = useState("");
  const [source, setSource] = useState("");
  const [reviewer, setReviewer] = useState("");
  const [state, setState] = useState<"idle" | "sending" | "saved" | "error" | "noreason">("idle");
  const prefix = `rv-${incidentId}`;

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!status || !reason) {
      setState("noreason");
      return;
    }
    setState("sending");
    try {
      const response = await fetch("/api/portal/review", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ incident_id: incidentId, output_id: outputId, status, reason, fields: marks, note, source_url: source, reviewer }),
      });
      setState(response.ok ? "saved" : "error");
    } catch {
      setState("error");
    }
  }

  if (state === "saved") {
    return (
      <div className="flex flex-wrap items-center gap-3 border-t border-line pt-3" role="status">
        <span className="text-[13px] text-good">{strings.saved}</span>
        <button type="button" className="btn btn-ghost text-[12.5px]" onClick={() => setState("idle")}>
          {strings.again}
        </button>
      </div>
    );
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-3 border-t border-line pt-3">
      <fieldset className="flex flex-col gap-1.5">
        <legend className="label mb-1.5">{strings.decision}</legend>
        <div className="flex flex-wrap gap-1.5">
          {Object.keys(reasonsByStatus).map((s) => (
            <Choice
              key={s}
              id={`${prefix}-status-${s}`}
              name={`${prefix}-status`}
              checked={status === s}
              tone={STATUS_TONE[s]}
              label={strings.statuses[s]}
              onChange={() => {
                setStatus(s);
                setReason(null);
                setState("idle");
              }}
            />
          ))}
        </div>
      </fieldset>
      {status ? (
        <fieldset className="flex flex-col gap-1.5">
          <legend className="label mb-1.5">{strings.reason}</legend>
          <div className="flex flex-wrap gap-1.5">
            {reasonsByStatus[status].map((r) => (
              <Choice key={r} id={`${prefix}-reason-${r}`} name={`${prefix}-reason`} checked={reason === r} tone={STATUS_TONE[status]} label={strings.reasons[r]} onChange={() => { setReason(r); setState("idle"); }} />
            ))}
          </div>
        </fieldset>
      ) : null}
      {status ? (
        <details className="rounded-md border border-line p-3">
          <summary className="cursor-pointer text-[13px] text-soft">{strings.fieldsTitle}</summary>
          <p className="mt-2 text-[12px] text-muted">{strings.fieldsHint}</p>
          <div className="mt-2 flex flex-col gap-2">
            {fields.map((f) => (
              <div key={f.key} className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center">
                <span className="text-[13px]">
                  <span className="text-muted">{f.label}: </span>
                  {f.value ?? <span className="text-muted">{strings.unknown}</span>}
                </span>
                <div className="flex gap-1.5">
                  {(["benar", "salah"] as const).map((v) => (
                    <Choice
                      key={v}
                      id={`${prefix}-${f.key}-${v}`}
                      name={`${prefix}-${f.key}`}
                      checked={marks[f.key] === v}
                      tone={v === "benar" ? "var(--good)" : "var(--high)"}
                      label={strings.fieldValues[v]}
                      onChange={() => setMarks((m) => ({ ...m, [f.key]: v }))}
                    />
                  ))}
                </div>
              </div>
            ))}
          </div>
          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            <label className="flex flex-col gap-1 text-[12px] text-muted sm:col-span-2" htmlFor={`${prefix}-note`}>
              {strings.note}
              <textarea id={`${prefix}-note`} value={note} onChange={(e) => setNote(e.target.value)} maxLength={600} rows={2} className="field text-[13px]" />
            </label>
            <label className="flex flex-col gap-1 text-[12px] text-muted" htmlFor={`${prefix}-source`}>
              {strings.source}
              <input id={`${prefix}-source`} type="url" value={source} onChange={(e) => setSource(e.target.value)} className="field text-[13px]" />
            </label>
            <label className="flex flex-col gap-1 text-[12px] text-muted" htmlFor={`${prefix}-reviewer`}>
              {strings.reviewer}
              <input id={`${prefix}-reviewer`} type="text" value={reviewer} onChange={(e) => setReviewer(e.target.value)} maxLength={80} className="field text-[13px]" />
            </label>
          </div>
        </details>
      ) : null}
      <div className="flex flex-wrap items-center gap-3">
        <button type="submit" className="btn btn-primary" disabled={state === "sending" || !status}>
          {state === "sending" ? strings.sending : strings.submit}
        </button>
        {state === "noreason" ? <span className="text-[13px] text-med">{strings.chooseReason}</span> : null}
        {state === "error" ? <span className="text-[13px] text-high">{strings.failed}</span> : null}
      </div>
    </form>
  );
}
