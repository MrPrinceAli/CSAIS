/**
 * Tanda tangan keputusan lembaga (EIP-712). Setiap keputusan portal
 * ditandatangani kunci lembaga; tanda tangan ikut ke catatan resmi D4 (lewat
 * csais/official.py) dan diperiksa di /verify terhadap alamat lembaga di
 * institution-keys.json, yang juga terdaftar di kontrak CsaisAnchor
 * (setInstitution). Hanya untuk server.
 */
import { recoverTypedDataAddress, type Hex } from "viem";
import { privateKeyToAccount } from "viem/accounts";
import registry from "./institution-keys.json";

export const DECISION_TYPES = {
  Decision: [
    { name: "incidentId", type: "string" },
    { name: "cardHash", type: "bytes32" },
    { name: "institution", type: "string" },
    { name: "status", type: "string" },
    { name: "reason", type: "string" },
    { name: "fields", type: "string" },
    { name: "note", type: "string" },
    { name: "source", type: "string" },
    { name: "issuedAt", type: "uint64" },
  ],
} as const;

export type Decision = {
  incidentId: string;
  cardHash: Hex;
  institution: string;
  status: string;
  reason: string;
  fields: string;
  note: string;
  source: string;
  issuedAt: number;
};

export type Domain = { name: string; version: string; chainId: number; verifyingContract: Hex };

export const DOMAIN = registry.domain as Domain;
export const INSTITUTION_ADDRESSES = registry.addresses as Record<string, string>;

/** Paket tanda tangan yang disimpan bersama keputusan. */
export type SignedDecision = { domain: Domain; message: Decision; signature: Hex; signer: string };

export async function signDecision(privateKey: Hex, message: Decision): Promise<SignedDecision> {
  const account = privateKeyToAccount(privateKey);
  const signature = await account.signTypedData({
    domain: DOMAIN,
    types: DECISION_TYPES,
    primaryType: "Decision",
    message: { ...message, issuedAt: BigInt(message.issuedAt) },
  });
  return { domain: DOMAIN, message, signature, signer: account.address };
}

export type SignatureCheck = { signer: string; expected: string | null; valid: boolean };

/** Pulihkan penanda tangan dan cocokkan dengan alamat lembaga yang terdaftar. */
export async function checkDecision(signed: SignedDecision): Promise<SignatureCheck> {
  const expected = INSTITUTION_ADDRESSES[signed.message.institution] ?? null;
  try {
    const signer = await recoverTypedDataAddress({
      domain: signed.domain,
      types: DECISION_TYPES,
      primaryType: "Decision",
      message: { ...signed.message, issuedAt: BigInt(signed.message.issuedAt) },
      signature: signed.signature,
    });
    return { signer, expected, valid: Boolean(expected) && signer.toLowerCase() === expected?.toLowerCase() };
  } catch {
    return { signer: "", expected, valid: false };
  }
}
