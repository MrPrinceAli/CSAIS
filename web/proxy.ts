import { NextResponse, type NextRequest } from "next/server";

const LANGS = ["id", "en"] as const;
type Lang = (typeof LANGS)[number];

function isLang(value: string | undefined): value is Lang {
  return LANGS.includes(value as Lang);
}

/** Awali setiap path dengan bahasa (/id atau /en); pilihan disimpan di cookie. */
export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const first = pathname.split("/")[1];
  if (isLang(first)) {
    const response = NextResponse.next();
    if (request.cookies.get("lang")?.value !== first) {
      response.cookies.set("lang", first, { path: "/", maxAge: 60 * 60 * 24 * 365, sameSite: "lax" });
    }
    return response;
  }
  const cookie = request.cookies.get("lang")?.value;
  const accept = (request.headers.get("accept-language") ?? "").toLowerCase();
  const prefersEnglish = accept.startsWith("en") || (accept.includes("en") && !accept.includes("id"));
  const lang: Lang = isLang(cookie) ? cookie : prefersEnglish ? "en" : "id";
  const url = request.nextUrl.clone();
  url.pathname = `/${lang}${pathname === "/" ? "" : pathname}`;
  return NextResponse.redirect(url);
}

export const config = {
  matcher: ["/((?!_next|api|favicon\\.ico|.*\\..*).*)"],
};
