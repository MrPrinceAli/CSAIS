import { NextResponse } from "next/server";
import { query } from "@/lib/db";
import { hasColumn } from "@/lib/queries";
import { decodeEntities, decodeGoogleNews, isGoogleNews, pageImage, UA } from "@/lib/media";

/**
 * Foto berita untuk kartu incident: gambar utama (og:image) salah satu
 * artikel incident, dengan artikel jangkar (yang judulnya tampil di kartu)
 * didahulukan. Sumber: articles.image_url dari pipeline, lalu halaman media
 * (URL asli dari database atau hasil membuka tautan Google News). Byte gambar
 * disalurkan lewat route ini supaya tidak terhalang aturan hotlink atau
 * Cross-Origin-Resource-Policy media. Hasil di-cache CDN seminggu; bila tidak
 * ada gambar yang bisa dimuat, 404 (kartu menampilkan ubin cadangan).
 */
export const dynamic = "force-dynamic";
export const maxDuration = 30;

const FOUND = "public, max-age=86400, s-maxage=604800, stale-while-revalidate=2592000";
const MISSING = "public, s-maxage=1800, stale-while-revalidate=3600";
const MAX_BYTES = 4_000_000;
const memo = new Map<string, string>(); // incident -> URL gambar yang sudah terbukti bisa dimuat

type Row = { article_url: string | null; resolved_url: string | null; image_url: string | null };

/** Ambil gambar; null bila gagal, bukan gambar, atau terlalu besar. */
async function fetchImage(url: string): Promise<Response | null> {
  try {
    const response = await fetch(url, { headers: { "User-Agent": UA, Accept: "image/avif,image/webp,image/*;q=0.8" }, redirect: "follow", signal: AbortSignal.timeout(7000) });
    const type = response.headers.get("content-type") ?? "";
    const size = Number(response.headers.get("content-length") ?? 0);
    if (response.ok && type.startsWith("image/") && size <= MAX_BYTES && response.body) return response;
    response.body?.cancel().catch(() => {});
  } catch {
    /* lanjut ke kandidat berikutnya */
  }
  return null;
}

/** Kandidat URL gambar berurutan prioritas; halaman media dibaca paralel, hasil diambil sesuai urutan. */
async function* candidates(id: string): AsyncGenerator<string> {
  const known = memo.get(id);
  if (known) yield known;
  const withImage = await hasColumn("articles", "image_url");
  const rows = await query<Row>(
    `SELECT a.article_url, a.resolved_url, ${withImage ? "a.image_url" : "NULL AS image_url"}
     FROM v05_incident_documents d
     JOIN articles a ON a.article_id = d.article_id
     JOIN v05_incidents i ON i.incident_id = d.incident_id
     WHERE d.incident_id = ?
     ORDER BY (a.article_id = i.anchor_article_id) DESC,
              ABS(julianday(a.published_date) - julianday(i.anchor_published_date)),
              a.article_id
     LIMIT 6`,
    [id],
  );
  for (const row of rows) if (row.image_url) yield decodeEntities(row.image_url);

  // Halaman media dibaca bertahap: artikel jangkar dan satu artikel lain dulu,
  // tiga berikutnya hanya bila belum ada gambar (hemat permintaan ke media).
  const isMedia = (u: string | null): u is string => Boolean(u && /^https?:\/\//.test(u) && !isGoogleNews(u));
  const seen = new Set<string>();
  for (const wave of [rows.slice(0, 2), rows.slice(2, 5)]) {
    const links = wave.filter((r) => !isMedia(r.resolved_url) && isGoogleNews(r.article_url)).map((r) => r.article_url as string);
    const decoded = links.length ? await decodeGoogleNews(links) : new Map<string, string>();
    const pages = wave
      .map((r) => (isMedia(r.resolved_url) ? r.resolved_url : r.article_url ? decoded.get(r.article_url) : undefined))
      .filter((u): u is string => Boolean(u) && !seen.has(u as string));
    pages.forEach((u) => seen.add(u));
    const pending = pages.map((url) => pageImage(url).catch(() => null));
    for (const promise of pending) {
      const image = await promise;
      if (image) yield image;
    }
  }
}

export async function GET(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  if (!/^INCIDENT_[0-9A-F]{6,40}$/i.test(id)) return new NextResponse("bad id", { status: 400 });

  const tried = new Set<string>();
  try {
    for await (const url of candidates(id)) {
      if (tried.has(url)) continue;
      tried.add(url);
      const response = await fetchImage(url);
      if (!response) {
        if (memo.get(id) === url) memo.delete(id);
        continue;
      }
      memo.set(id, url);
      return new NextResponse(response.body, {
        headers: {
          "Content-Type": response.headers.get("content-type") ?? "image/jpeg",
          "Cache-Control": FOUND,
        },
      });
    }
  } catch {
    /* basis data atau jaringan gagal: anggap tidak ada gambar */
  }
  return new NextResponse(null, { status: 404, headers: { "Cache-Control": MISSING } });
}
