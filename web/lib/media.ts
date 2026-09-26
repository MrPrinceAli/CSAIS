/**
 * Pengambilan gambar berita di sisi server: membuka tautan Google News menjadi
 * URL media asli (protokol batchexecute yang sama dengan googlenewsdecoder di
 * pipeline), menghormati robots.txt, lalu membaca og:image dari bagian <head>
 * halaman media. Hanya dipakai oleh route gambar; tidak menerima URL bebas.
 */

export const UA = "Mozilla/5.0 (compatible; CSAIS/1.0; +https://csais.vercel.app)";
const BOT = "csais"; // nama agen untuk pencocokan robots.txt
const META_KEYS = new Set(["og:image", "og:image:url", "og:image:secure_url", "twitter:image", "twitter:image:src"]);

/** Dekode entitas HTML pada nilai atribut ("&amp;" -> "&"), yang lazim di URL og:image. */
export function decodeEntities(value: string): string {
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
    if (url && !/googleusercontent\.com|gstatic\.com/.test(url)) return url;
  }
  return null;
}

export const isGoogleNews = (url: string | null | undefined) => Boolean(url && /^https?:\/\/news\.google\./.test(url));

/* --- Google News -> URL media --- */

const BATCH_URL = "https://news.google.com/_/DotsSplashUi/data/batchexecute";
const CTX = [["X", "X", ["X", "X"], null, null, 1, 1, "US:en", null, 1, null, null, null, null, null, 0, 1], "X", "X", 1, [1, 1, 1], 1, 1, null, 0, 0, null, 0];

function newsId(url: string): string | null {
  try {
    const u = new URL(url);
    const parts = u.pathname.split("/");
    return u.hostname === "news.google.com" && ["articles", "read"].includes(parts[parts.length - 2]) ? parts[parts.length - 1] || null : null;
  } catch {
    return null;
  }
}

/** Tanda tangan dan stempel waktu dari halaman /rss/articles/{id} (satu-satunya yang tidak dialihkan ke halaman "sorry"). */
async function signatureOf(id: string, source: string): Promise<{ sg: string; ts: string } | null> {
  const q = new URL(source).searchParams;
  let current = `https://news.google.com/rss/articles/${id}?hl=${encodeURIComponent(q.get("hl") ?? "en-US")}&gl=${encodeURIComponent(q.get("gl") ?? "US")}&ceid=${encodeURIComponent(q.get("ceid") ?? "US:en")}`;
  for (let hop = 0; hop < 3; hop++) {
    const response = await fetch(current, { redirect: "manual", headers: { "User-Agent": UA }, signal: AbortSignal.timeout(5000) });
    const location = response.headers.get("location");
    if (response.status >= 300 && response.status < 400 && location) {
      const next = new URL(location, current);
      if (next.hostname !== "news.google.com") return null;
      current = next.toString();
      continue;
    }
    if (!response.ok) return null;
    const html = await response.text();
    const sg = /data-n-a-sg="([^"]+)"/.exec(html)?.[1];
    const ts = /data-n-a-ts="([^"]+)"/.exec(html)?.[1];
    return sg && ts ? { sg, ts } : null;
  }
  return null;
}

/** URL media asli untuk sejumlah tautan Google News (satu POST batchexecute); tautan yang gagal tidak ada di hasil. */
export async function decodeGoogleNews(urls: string[]): Promise<Map<string, string>> {
  const out = new Map<string, string>();
  const items = (
    await Promise.all(
      urls.map(async (url, i) => {
        const id = newsId(url);
        const sig = id ? await signatureOf(id, url).catch(() => null) : null;
        return id && sig ? { req: String(i), url, id, ...sig } : null;
      }),
    )
  ).filter((x): x is NonNullable<typeof x> => x !== null);
  if (!items.length) return out;
  const envelopes = items.map((x) => ["Fbv4je", JSON.stringify(["garturlreq", CTX, x.id, /^\d+$/.test(x.ts) ? Number(x.ts) : x.ts, x.sg]), null, x.req]);
  try {
    const response = await fetch(BATCH_URL, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8", "User-Agent": UA },
      body: `f.req=${encodeURIComponent(JSON.stringify([envelopes]))}`,
      signal: AbortSignal.timeout(6000),
    });
    if (!response.ok) return out;
    let body = await response.text();
    if (body.includes("\n\n")) body = body.slice(body.indexOf("\n\n") + 2);
    body = body.trimStart();
    if (body.startsWith(")]}'")) body = body.slice(body.indexOf("\n") + 1);
    const rows = JSON.parse(body) as unknown[];
    for (const row of rows) {
      if (!Array.isArray(row) || row.length < 3 || (row[0] !== "wrb.fr" && row[1] !== "Fbv4je")) continue;
      const payload = typeof row[2] === "string" ? JSON.parse(row[2]) : row[2];
      if (!Array.isArray(payload) || payload[0] !== "garturlres" || typeof payload[1] !== "string") continue;
      const req = [...row.slice(3)].reverse().find((cell) => cell !== null && cell !== undefined);
      const item = items.find((x) => x.req === String(req)) ?? (items.length === 1 ? items[0] : undefined);
      if (item && /^https?:\/\//.test(payload[1])) out.set(item.url, payload[1]);
    }
  } catch {
    /* Google menolak atau format berubah: kembalikan yang sudah ada */
  }
  return out;
}

/* --- robots.txt --- */

const robotsMemo = new Map<string, { rules: { allow: boolean; path: string }[]; at: number }>();

/** Aturan untuk agen "csais" bila ada, selain itu untuk "*". */
function parseRobots(text: string): { allow: boolean; path: string }[] {
  const groups: { agents: string[]; rules: { allow: boolean; path: string }[] }[] = [];
  let current: (typeof groups)[number] | null = null;
  let lastWasAgent = false;
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.replace(/#.*/, "").trim();
    const m = /^([a-z-]+)\s*:\s*(.*)$/i.exec(line);
    if (!m) continue;
    const key = m[1].toLowerCase();
    const value = m[2].trim();
    if (key === "user-agent") {
      if (!current || !lastWasAgent) {
        current = { agents: [], rules: [] };
        groups.push(current);
      }
      current.agents.push(value.toLowerCase());
      lastWasAgent = true;
    } else if ((key === "allow" || key === "disallow") && current) {
      if (value || key === "allow") current.rules.push({ allow: key === "allow", path: value });
      lastWasAgent = false;
    } else lastWasAgent = false;
  }
  const own = groups.find((g) => g.agents.some((a) => a.includes(BOT)));
  return (own ?? groups.find((g) => g.agents.includes("*")))?.rules ?? [];
}

/** True bila robots.txt situs mengizinkan path ini (aturan terpanjang menang; gagal dimuat = diizinkan). */
export async function robotsAllows(url: string): Promise<boolean> {
  const u = new URL(url);
  let entry = robotsMemo.get(u.origin);
  if (!entry || Date.now() - entry.at > 6 * 3600_000) {
    let rules: { allow: boolean; path: string }[] = [];
    try {
      const response = await fetch(`${u.origin}/robots.txt`, { headers: { "User-Agent": UA }, signal: AbortSignal.timeout(3000) });
      if (response.ok) rules = parseRobots((await response.text()).slice(0, 200_000));
    } catch {
      rules = [];
    }
    entry = { rules, at: Date.now() };
    robotsMemo.set(u.origin, entry);
  }
  const target = u.pathname + u.search;
  let best: { allow: boolean; path: string } | null = null;
  for (const rule of entry.rules) {
    const pattern = new RegExp("^" + rule.path.replace(/[.+?^${}()|[\]\\]/g, "\\$&").replace(/\*/g, ".*").replace(/\\\$$/, "$"));
    if (rule.path && pattern.test(target) && (!best || rule.path.length > best.path.length)) best = rule;
  }
  return best ? best.allow : true;
}

/** og:image halaman media dari bagian <head> saja; null bila diblokir robots, gagal, atau tanpa gambar. */
export async function pageImage(url: string): Promise<string | null> {
  if (!(await robotsAllows(url).catch(() => true))) return null;
  const response = await fetch(url, { headers: { "User-Agent": UA, Accept: "text/html" }, redirect: "follow", signal: AbortSignal.timeout(8000) });
  if (!response.ok || !response.body) return null;
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let html = "";
  while (html.length < 400_000) {
    const { done, value } = await reader.read();
    if (done) break;
    html += decoder.decode(value, { stream: true });
    if (/<\/head>/i.test(html)) break;
  }
  reader.cancel().catch(() => {});
  return findImage(html, response.url || url);
}
