import { KEY_COOKIE_NAME, SESSION_COOKIE_NAME } from "@/lib/portal";

export const dynamic = "force-dynamic";

export async function POST() {
  const response = Response.json({ ok: true });
  for (const name of [SESSION_COOKIE_NAME, KEY_COOKIE_NAME]) {
    response.headers.append("Set-Cookie", `${name}=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax`);
  }
  return response;
}
