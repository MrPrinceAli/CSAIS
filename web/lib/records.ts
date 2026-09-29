/**
 * Identitas dan hash catatan resmi D4, sama persis dengan csais/flows.py
 * (output_hash) dan csais/ledger.py (record_uid). Hanya untuk server.
 */
import { createHash } from "node:crypto";

// Kolom isi yang ikut output_hash, urutannya tidak berpengaruh (kunci diurutkan)
const HASHED = [
  "attack_type", "target", "threat_actor", "attack_date", "location", "target_group",
  "field_status", "status", "tier", "prevention", "basis", "source_ref", "reason", "supersedes",
] as const;

/** JSON kanonis seperti json.dumps(sort_keys=True, separators=(",", ":"), ensure_ascii=True). */
export function canonicalJson(value: Record<string, unknown>): string {
  const sorted: Record<string, unknown> = {};
  for (const key of Object.keys(value).sort()) sorted[key] = value[key];
  return JSON.stringify(sorted).replace(/[\u0080-￿]/g, (c) => `\\u${c.charCodeAt(0).toString(16).padStart(4, "0")}`);
}

/** output_hash satu baris flow_outputs. */
export function outputHash(row: Record<string, unknown>): string {
  const payload: Record<string, unknown> = {};
  for (const key of HASHED) payload[key] = row[key] ?? null;
  return createHash("sha256").update(canonicalJson(payload), "ascii").digest("hex");
}

/** ID daun ledger untuk catatan D4. */
export function recordUid(outputId: number, hash: string): string {
  return createHash("sha256").update(`D4|${outputId}|${hash}`, "ascii").digest("hex").slice(0, 24);
}
