import { institutionForCode, portalConfigured, sessionCookie } from "@/lib/portal";

/** Masuk portal lembaga dengan kode akses; sesi disimpan di cookie bertanda tangan HMAC. */
export const dynamic = "force-dynamic";

const attempts = new Map<string, number[]>();

function tooMany(ip: string): boolean {
  const now = Date.now();
  const recent = (attempts.get(ip) ?? []).filter((t) => now - t < 10 * 60_000);
  recent.push(now);
  attempts.set(ip, recent);
  if (attempts.size > 5000) attempts.clear();
  return recent.length > 10;
}

export async function POST(request: Request) {
  if (!portalConfigured()) return Response.json({ ok: false, error: "portal-unavailable" }, { status: 503 });
  const ip = (request.headers.get("x-forwarded-for") ?? "").split(",")[0].trim() || "unknown";
  if (tooMany(ip)) return Response.json({ ok: false, error: "too-many-attempts" }, { status: 429 });
  let code = "";
  try {
    const body = (await request.json()) as { code?: unknown };
    code = typeof body.code === "string" ? body.code.slice(0, 100) : "";
  } catch {
    return Response.json({ ok: false, error: "invalid-json" }, { status: 400 });
  }
  const inst = institutionForCode(code);
  if (!inst) return Response.json({ ok: false, error: "wrong-code" }, { status: 401 });
  const cookie = sessionCookie(inst);
  const response = Response.json({ ok: true, institution: inst });
  response.headers.append(
    "Set-Cookie",
    `${cookie.name}=${cookie.value}; Path=/; Max-Age=${cookie.maxAge}; HttpOnly; SameSite=Lax${process.env.NODE_ENV === "production" ? "; Secure" : ""}`,
  );
  return response;
}
