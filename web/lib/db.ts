import { createClient, type InValue } from "@libsql/client";

// Turso dibaca lewat HTTP (bukan websocket) agar aman di serverless Vercel.
const url = (process.env.TURSO_DATABASE_URL ?? "").replace(/^libsql:\/\//, "https://");
const authToken = process.env.TURSO_AUTH_TOKEN;

let client: ReturnType<typeof createClient> | null = null;

function getClient() {
  if (!client) {
    if (!url || !authToken) {
      throw new Error("TURSO_DATABASE_URL dan TURSO_AUTH_TOKEN belum diisi.");
    }
    client = createClient({ url, authToken });
  }
  return client;
}

/** Jalankan satu SELECT; baris dikembalikan sebagai objek bertipe T. */
export async function query<T extends Record<string, unknown>>(
  sql: string,
  args: InValue[] = [],
): Promise<T[]> {
  const result = await getClient().execute({ sql, args });
  return result.rows.map((row) => {
    const obj: Record<string, unknown> = {};
    for (const column of result.columns) {
      obj[column] = row[column];
    }
    return obj as T;
  });
}

export async function queryOne<T extends Record<string, unknown>>(
  sql: string,
  args: InValue[] = [],
): Promise<T | null> {
  const rows = await query<T>(sql, args);
  return rows[0] ?? null;
}
