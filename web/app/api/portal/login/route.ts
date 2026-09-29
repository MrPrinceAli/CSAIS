import { INSTITUTIONS, portalConfigured, sessionCookies, unlockKey, type Institution } from "@/lib/portal";

/** Masuk portal: pilih lembaga + password. Password membuka kunci tanda tangan lembaga. */
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
  let inst: Institution | null = null;
  let password = "";
  try {
    const body = (await request.json()) as { institution?: unknown; password?: unknown };
    inst = INSTITUTIONS.includes(body.institution as Institution) ? (body.institution as Institution) : null;
    password = typeof body.password === "string" ? body.password.slice(0, 200) : "";
  } catch {
    return Response.json({ ok: false, error: "invalid-json" }, { status: 400 });
  }
  const privateKey = inst ? unlockKey(inst, password) : null;
  if (!inst || !privateKey) return Response.json({ ok: false, error: "wrong-password" }, { status: 401 });
  const response = Response.json({ ok: true, institution: inst });
  for (const cookie of sessionCookies(inst, privateKey)) {
    response.headers.append(
      "Set-Cookie",
      `${cookie.name}=${cookie.value}; Path=/; Max-Age=${cookie.maxAge}; HttpOnly; SameSite=Lax${process.env.NODE_ENV === "production" ? "; Secure" : ""}`,
    );
  }
  return response;
}
