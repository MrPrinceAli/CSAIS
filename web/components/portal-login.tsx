"use client";

/* Masuk portal lembaga: pilih lembaga lalu password; setelah berhasil halaman dimuat ulang dari server. */
import { useRouter } from "next/navigation";
import { useState } from "react";

type Strings = { title: string; choose: string; label: string; button: string; wrong: string; busy: string; failed: string };
export type InstitutionOption = { code: string; name: string; logo: string };

export function PortalLogin({ strings, institutions }: { strings: Strings; institutions: InstitutionOption[] }) {
  const router = useRouter();
  const [inst, setInst] = useState<string | null>(null);
  const [password, setPassword] = useState("");
  const [state, setState] = useState<"idle" | "sending" | "wrong" | "busy" | "failed">("idle");

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!inst) return;
    setState("sending");
    try {
      const response = await fetch("/api/portal/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ institution: inst, password }),
      });
      if (response.ok) {
        router.refresh();
        return;
      }
      setState(response.status === 401 ? "wrong" : response.status === 429 ? "busy" : "failed");
    } catch {
      setState("failed");
    }
  }

  return (
    <form onSubmit={submit} className="card flex max-w-[560px] flex-col gap-4 p-5">
      <h2 className="text-[16px] font-semibold">{strings.title}</h2>
      <fieldset className="flex flex-col gap-2">
        <legend className="label mb-2">{strings.choose}</legend>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {institutions.map((o) => {
            const checked = inst === o.code;
            return (
              <label
                key={o.code}
                htmlFor={`inst-${o.code}`}
                className="flex cursor-pointer flex-col items-center gap-2 rounded-md border p-3 text-center text-[13px] transition-colors focus-within:outline focus-within:outline-2"
                style={{ borderColor: checked ? "var(--accent)" : "var(--line)", boxShadow: checked ? "inset 0 0 0 1px var(--accent)" : undefined, background: checked ? "color-mix(in srgb, var(--accent) 12%, transparent)" : undefined }}
              >
                <input id={`inst-${o.code}`} type="radio" name="institution" value={o.code} checked={checked} onChange={() => { setInst(o.code); setState("idle"); }} className="sr-only" />
                <span className="flex h-12 w-12 items-center justify-center rounded-md bg-white p-1">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={o.logo} alt="" className="h-full w-full object-contain" />
                </span>
                <span className={checked ? "font-semibold text-fg" : "text-soft"}>{o.name}</span>
              </label>
            );
          })}
        </div>
      </fieldset>
      {inst ? (
        <div className="flex flex-col gap-2">
          <label htmlFor="portal-password" className="label">
            {strings.label}
          </label>
          <input id="portal-password" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} className="field py-2.5 text-[14px]" required autoFocus />
        </div>
      ) : null}
      <button type="submit" className="btn btn-primary self-start" disabled={state === "sending" || !inst || !password}>
        {strings.button}
      </button>
      {state === "wrong" ? <p className="text-[13px] text-high">{strings.wrong}</p> : null}
      {state === "busy" ? <p className="text-[13px] text-high">{strings.busy}</p> : null}
      {state === "failed" ? <p className="text-[13px] text-high">{strings.failed}</p> : null}
    </form>
  );
}

export function PortalLogout({ label }: { label: string }) {
  const router = useRouter();
  return (
    <button
      type="button"
      className="btn btn-ghost text-[13px]"
      onClick={async () => {
        await fetch("/api/portal/logout", { method: "POST" }).catch(() => null);
        router.refresh();
      }}
    >
      {label}
    </button>
  );
}
