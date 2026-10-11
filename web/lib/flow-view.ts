/* Pembantu tampilan keluaran alur D1 - D4 (tabel flow_outputs) di halaman detail incident. */
import type { FlowOutput } from "@/lib/queries";

export const FLOWS = ["D1", "D2", "D3", "D4"] as const;
export type Flow = (typeof FLOWS)[number];

export const FLOW_TONE: Record<Flow, string> = { D1: "var(--accent)", D2: "var(--med)", D3: "var(--chain)", D4: "var(--good)" };
export const VERDICT_CLASS: Record<string, string> = { benar: "text-good", hoaks: "text-high", belum_pasti: "text-muted" };
const VERDICT_OF_STATUS: Record<string, string> = { tinggi: "benar", dikonfirmasi: "benar", dibantah: "hoaks" };

export function parseJson<T>(raw: string | null | undefined): T | null {
  if (!raw) return null;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

/** Snapshot terakhir tiap alur (tanpa yang dihapus). */
export function latestByFlow(outputs: FlowOutput[]): Partial<Record<Flow, FlowOutput>> {
  const latest: Partial<Record<Flow, FlowOutput>> = {};
  for (const o of outputs) if (o.status !== "dihapus") latest[o.flow] = o;
  return latest;
}

/** Kesimpulan bersama satu keluaran; harus sama dengan verdict() di csais/flow_compare.py. */
export function verdictOf(o: FlowOutput): string {
  if (o.flow === "D2") {
    const value = parseJson<{ verdict?: string }>(o.basis)?.verdict;
    return value && value in VERDICT_CLASS ? value : "belum_pasti";
  }
  return VERDICT_OF_STATUS[o.status] ?? "belum_pasti";
}

export type PreventionPlan = { steps?: string[]; channels?: string[]; text?: string | null; audience?: string[]; topics?: string[] };
