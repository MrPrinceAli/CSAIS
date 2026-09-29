import { SESSION_COOKIE_NAME } from "@/lib/portal";

export const dynamic = "force-dynamic";

export async function POST() {
  const response = Response.json({ ok: true });
  response.headers.append("Set-Cookie", `${SESSION_COOKIE_NAME}=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax`);
  return response;
}
