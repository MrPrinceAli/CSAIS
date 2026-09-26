import { domainOf, publisherOf } from "@/lib/format";

export type Publisher = { name: string; domain: string | null };

/**
 * Penerbit berbeda dari daftar artikel: nama dari akhiran judul Google News
 * ("... - Kompas.com"), domain dari URL media asli bila ada, selain itu dari
 * registri sumber. Penerbit yang punya domain (bisa berlogo) didahulukan.
 */
export function publishersOf(docs: { title: string | null; resolved_url: string | null }[], domains: Record<string, string>): Publisher[] {
  const found = new Map<string, Publisher>();
  for (const d of docs) {
    const name = publisherOf(d.title);
    if (!name) continue;
    const key = name.toLowerCase();
    const own = domainOf(d.resolved_url);
    const domain = own && !own.includes("google.") ? own : (domains[key] ?? null);
    const known = found.get(key);
    if (!known) found.set(key, { name, domain });
    else if (!known.domain && domain) known.domain = domain;
  }
  return [...found.values()].sort((a, b) => Number(Boolean(b.domain)) - Number(Boolean(a.domain)));
}
