#!/usr/bin/env node
/**
 * Buat kunci tanda tangan per lembaga dan enkripsi dengan password lembaga.
 *
 *   node scripts/portal-keys.mjs < passwords.json
 *   passwords.json: {"BSSN": "...", "OJK": "...", "KOMDIGI": "...", "POLRI": "..."}
 *
 * Keluaran (stdout, JSON):
 *   portalKeys  -> isi variabel Vercel PORTAL_KEYS (kunci terenkripsi, tanpa password)
 *   addresses   -> alamat publik lembaga, untuk lib/institution-keys.json dan kontrak
 *
 * Kunci pribadi hanya bisa dibuka dengan password lembaga (scrypt + AES-256-GCM);
 * password tidak disimpan di mana pun. Menjalankan ulang membuat kunci BARU:
 * alamat lembaga berubah dan harus didaftarkan ulang ke kontrak.
 */
import { createCipheriv, randomBytes, scryptSync } from "node:crypto";
import { generatePrivateKey, privateKeyToAccount } from "viem/accounts";

const INSTITUTIONS = ["BSSN", "OJK", "KOMDIGI", "POLRI"];
const KDF = { N: 2 ** 15, r: 8, p: 1 };

const chunks = [];
for await (const chunk of process.stdin) chunks.push(chunk);
const passwords = JSON.parse(Buffer.concat(chunks).toString("utf8"));

const portalKeys = {};
const addresses = {};
for (const inst of INSTITUTIONS) {
  const password = passwords[inst];
  if (!password) throw new Error(`password ${inst} kosong`);
  const privateKey = generatePrivateKey();
  const address = privateKeyToAccount(privateKey).address;
  const salt = randomBytes(16);
  const iv = randomBytes(12);
  const key = scryptSync(password, salt, 32, { ...KDF, maxmem: 64 * 1024 * 1024 });
  const cipher = createCipheriv("aes-256-gcm", key, iv);
  const ct = Buffer.concat([cipher.update(Buffer.from(privateKey.slice(2), "hex")), cipher.final()]);
  portalKeys[inst] = {
    address,
    kdf: KDF,
    salt: salt.toString("base64"),
    iv: iv.toString("base64"),
    ct: ct.toString("base64"),
    tag: cipher.getAuthTag().toString("base64"),
  };
  addresses[inst] = address;
}
process.stdout.write(JSON.stringify({ portalKeys, addresses }) + "\n");
