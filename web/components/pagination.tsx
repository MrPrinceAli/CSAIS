import Link from "next/link";
import { formatters } from "@/lib/format";
import { getDict, type Lang } from "@/lib/i18n";

type Props = {
  lang: Lang;
  page: number;
  pages: number;
  hrefFor: (page: number) => string;
  action: string;
  hidden: Record<string, string | undefined>;
  total: number;
  pageSize: number;
  label: string;
};

function pageList(page: number, pages: number): (number | "gap")[] {
  if (pages <= 9) return Array.from({ length: pages }, (_, i) => i + 1);
  const set = new Set<number>([1, 2, pages - 1, pages, page - 1, page, page + 1]);
  if (page <= 4) [3, 4, 5].forEach((n) => set.add(n));
  if (page >= pages - 3) [pages - 4, pages - 3, pages - 2].forEach((n) => set.add(n));
  const sorted = [...set].filter((n) => n >= 1 && n <= pages).sort((a, b) => a - b);
  const out: (number | "gap")[] = [];
  for (let i = 0; i < sorted.length; i++) {
    if (i > 0 && sorted[i] - sorted[i - 1] > 1) out.push("gap");
    out.push(sorted[i]);
  }
  return out;
}

/** Paginasi bernomor dengan lompat langsung ke halaman. */
export function Pagination({ lang, page, pages, hrefFor, action, hidden, total, pageSize, label }: Props) {
  const t = getDict(lang).common;
  const f = formatters(lang);
  if (pages <= 1) {
    return <p className="text-[12.5px] text-muted">{t.singlePage(f.num(total), label)}</p>;
  }
  const from = (page - 1) * pageSize + 1;
  const to = Math.min(total, page * pageSize);
  const base = "inline-flex h-9 min-w-9 items-center justify-center rounded-md border px-2.5 text-[13px] no-underline";
  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <span className="text-[12.5px] text-muted">{t.rangeOf(from, to, f.num(total), label)}</span>
      <nav className="flex flex-wrap items-center gap-1.5" aria-label="Pagination">
        {page > 1 ? (
          <Link href={hrefFor(page - 1)} className={`${base} border-line text-soft hover:border-accent hover:text-fg`} rel="prev">
            {t.prev}
          </Link>
        ) : null}
        {pageList(page, pages).map((p, i) =>
          p === "gap" ? (
            <span key={`gap-${i}`} className="px-1 text-muted" aria-hidden="true">
              …
            </span>
          ) : p === page ? (
            <span key={p} className={`${base} border-accent bg-accent font-semibold text-accent-ink`} aria-current="page">
              {p}
            </span>
          ) : (
            <Link key={p} href={hrefFor(p)} className={`${base} border-line text-soft hover:border-accent hover:text-fg`}>
              {p}
            </Link>
          ),
        )}
        {page < pages ? (
          <Link href={hrefFor(page + 1)} className={`${base} border-line text-soft hover:border-accent hover:text-fg`} rel="next">
            {t.next}
          </Link>
        ) : null}
      </nav>
      <form method="get" action={action} className="flex items-center gap-2 text-[12.5px] text-muted">
        {Object.entries(hidden).map(([k, v]) => (v ? <input key={k} type="hidden" name={k} value={v} /> : null))}
        <label htmlFor="page-jump">{t.goToPage}</label>
        <input id="page-jump" name="page" type="number" min={1} max={pages} defaultValue={page} className="field w-20 py-1.5 text-center" />
        <button type="submit" className="btn btn-ghost px-3 py-1.5 text-[12.5px]">
          {t.jump}
        </button>
      </form>
    </div>
  );
}
