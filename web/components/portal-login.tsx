"use client";

/* Masuk portal lembaga dengan kode akses; setelah berhasil halaman dimuat ulang dari server. */
import { useRouter } from "next/navigation";
import { useState } from "react";

type Strings = { title: string; label: string; button: string; wrong: string; busy: string; failed: string };

export function PortalLogin({ strings }: { strings: Strings }) {
  const router = useRouter();
  const [code, setCode] = useState("");
  const [state, setState] = useState<"idle" | "sending" | "wrong" | "busy" | "failed">("idle");

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setState("sending");
    try {
      const response = await fetch("/api/portal/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ code }) });
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
    <form onSubmit={submit} className="card flex max-w-[460px] flex-col gap-3 p-5">
      <h2 className="text-[16px] font-semibold">{strings.title}</h2>
      <label htmlFor="portal-code" className="label">
        {strings.label}
      </label>
      <input id="portal-code" type="password" autoComplete="off" value={code} onChange={(e) => setCode(e.target.value)} className="field py-2.5 font-mono text-[13px]" required />
      <button type="submit" className="btn btn-primary self-start" disabled={state === "sending" || !code}>
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
