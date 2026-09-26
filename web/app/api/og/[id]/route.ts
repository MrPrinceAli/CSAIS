import { NextResponse } from "next/server";
import { queryOne } from "@/lib/db";
import { hasColumn } from "@/lib/queries";

/**
 * Gambar artikel untuk slider berita: mengalihkan ke og:image artikel.
 * Urutan: kolom articles.image_url (diisi pipeline saat isi artikel diambil),
 * lalu ambil langsung dari halaman media (hanya resolved_url dari database,
 * bukan URL bebas), lalu gambar pengganti SVG. Hasil di-cache CDN sehari.
 */
export const dynamic = "force-dynamic";

const UA = "Mozilla/5.0 (compatible; CSAIS/1.0; +https://csais.vercel.app)";
const META_KEYS = new Set(["og:image", "og:image:url", "og:image:secure_url", "twitter:image", "twitter:image:src"]);
const CACHE = "public, s-maxage=86400, stale-while-revalidate=604800";
const memo = new Map<number, string | null>();

/** Dekode entitas HTML pada nilai atribut ("&amp;" -> "&"), yang lazim di URL og:image. */
function decodeEntities(value: string): string {
  return value.replace(/&(amp|quot|apos|lt|gt|#\d+|#x[0-9a-f]+);/gi, (_, code: string) => {
    const key = code.toLowerCase();
    if (key === "amp") return "&";
    if (key === "quot") return '"';
    if (key === "apos") return "'";
    if (key === "lt") return "<";
    if (key === "gt") return ">";
    const n = key.startsWith("#x") ? Number.parseInt(key.slice(2), 16) : Number.parseInt(key.slice(1), 10);
    return Number.isFinite(n) ? String.fromCodePoint(n) : "";
  });
}

function absolute(value: string, base: string): string | null {
  try {
    const url = new URL(decodeEntities(value.trim()), base).toString();
    return /^https?:/.test(url) ? url : null;
  } catch {
    return null;
  }
}

/** URL gambar dari tag meta Open Graph / Twitter, absolut terhadap halaman. */
export function findImage(html: string, base: string): string | null {
  for (const tag of html.match(/<meta[^>]+>/gi) ?? []) {
    const key = /(?:property|name)\s*=\s*["']([^"']+)["']/i.exec(tag)?.[1]?.toLowerCase();
    if (!key || !META_KEYS.has(key)) continue;
    const content = /content\s*=\s*["']([^"']+)["']/i.exec(tag)?.[1];
    const url = content ? absolute(content, base) : null;
    if (url) return url;
  }
  return null;
}

function placeholder(domain: string): string {
  const label = domain.replace(/[<>&"]/g, "");
  return `<svg xmlns="http://www.w3.org/2000/svg" width="640" height="360" viewBox="0 0 640 360">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#16212d"/><stop offset="1" stop-color="#0b1219"/></linearGradient>
    <pattern id="p" width="24" height="24" patternUnits="userSpaceOnUse"><path d="M24 0H0V24" fill="none" stroke="rgba(47,183,201,0.12)"/></pattern>
  </defs>
  <rect width="640" height="360" fill="url(#g)"/><rect width="640" height="360" fill="url(#p)"/>
  <circle cx="520" cy="80" r="120" fill="rgba(47,183,201,0.08)"/><circle cx="120" cy="320" r="140" fill="rgba(167,139,250,0.08)"/>
  <text x="320" y="196" text-anchor="middle" font-family="JetBrains Mono, ui-monospace, monospace" font-size="22" fill="#8b9bab">${label}</text>
</svg>`;
}

export async function GET(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const articleId = Number.parseInt(id, 10);
  if (!Number.isFinite(articleId) || articleId <= 0) return new NextResponse("bad id", { status: 400 });

  const withImage = await hasColumn("articles", "image_url");
  const row = await queryOne<{ resolved_url: string | null; source_name: string | null; image_url: string | null }>(
    `SELECT resolved_url, source_name, ${withImage ? "image_url" : "NULL AS image_url"} FROM articles WHERE article_id = ?`,
    [articleId],
  );
  if (!row) return new NextResponse("not found", { status: 404 });
  const headers = { "Cache-Control": CACHE };
  if (row.image_url) return NextResponse.redirect(decodeEntities(row.image_url), { status: 302, headers });

  const pageUrl = row.resolved_url && /^https?:\/\//.test(row.resolved_url) && !/google\./.test(row.resolved_url) ? row.resolved_url : null;
  let domain = row.source_name ?? "";
  if (pageUrl) {
    try {
      domain = new URL(pageUrl).hostname.replace(/^www\./, "");
    } catch {
      /* biarkan nama sumber */
    }
    if (!memo.has(articleId)) {
      try {
        const response = await fetch(pageUrl, { headers: { "User-Agent": UA, Accept: "text/html" }, signal: AbortSignal.timeout(4500), redirect: "follow" });
        const html = (await response.text()).slice(0, 300_000);
        memo.set(articleId, response.ok ? findImage(html, response.url || pageUrl) : null);
      } catch {
        memo.set(articleId, null);
      }
    }
    const image = memo.get(articleId);
    if (image) return NextResponse.redirect(image, { status: 302, headers });
  }
  return new NextResponse(placeholder(domain), { headers: { ...headers, "Content-Type": "image/svg+xml; charset=utf-8" } });
}
