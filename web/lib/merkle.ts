/**
 * Pohon Merkle yang sama dengan csais/ledger.py (harus tetap identik):
 *   daun   = SHA-256(0x00 || payload)                 payload = JSON kanonis ASCII
 *   simpul = SHA-256(0x01 || min(a, b) || max(a, b))  pasangan diurutkan
 *   simpul ganjil tanpa pasangan naik apa adanya ke tingkat berikutnya
 * Dipakai halaman verifikasi (komponen server) untuk menghitung ulang bukti
 * Merkle dari daun-daun batch yang tersimpan di Turso.
 */
import { createHash } from "node:crypto";

const LEAF_PREFIX = Buffer.from([0x00]);
const NODE_PREFIX = Buffer.from([0x01]);

function sha256(...parts: Buffer[]): Buffer {
  const hash = createHash("sha256");
  for (const part of parts) hash.update(part);
  return hash.digest();
}

export function leafHash(payload: string): Buffer {
  return sha256(LEAF_PREFIX, Buffer.from(payload, "ascii"));
}

export function nodeHash(a: Buffer, b: Buffer): Buffer {
  return Buffer.compare(a, b) <= 0 ? sha256(NODE_PREFIX, a, b) : sha256(NODE_PREFIX, b, a);
}

function levels(leaves: Buffer[]): Buffer[][] {
  if (!leaves.length) throw new Error("pohon Merkle tanpa daun");
  const out: Buffer[][] = [leaves.slice()];
  while (out[out.length - 1].length > 1) {
    const current = out[out.length - 1];
    const upper: Buffer[] = [];
    for (let i = 0; i + 1 < current.length; i += 2) upper.push(nodeHash(current[i], current[i + 1]));
    if (current.length % 2) upper.push(current[current.length - 1]);
    out.push(upper);
  }
  return out;
}

export function merkleRoot(leaves: Buffer[]): Buffer {
  const all = levels(leaves);
  return all[all.length - 1][0];
}

export function merkleProof(leaves: Buffer[], index: number): Buffer[] {
  if (index < 0 || index >= leaves.length) throw new RangeError(String(index));
  const proof: Buffer[] = [];
  const all = levels(leaves);
  for (let level = 0; level < all.length - 1; level++) {
    const sibling = index ^ 1;
    if (sibling < all[level].length) proof.push(all[level][sibling]);
    index = Math.floor(index / 2);
  }
  return proof;
}

export function verifyProof(leaf: Buffer, proof: Buffer[], root: Buffer): boolean {
  let current = leaf;
  for (const sibling of proof) current = nodeHash(current, sibling);
  return current.equals(root);
}

export const toHex = (b: Buffer): string => b.toString("hex");
export const fromHex = (s: string): Buffer => Buffer.from(s, "hex");
