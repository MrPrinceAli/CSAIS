"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LANGS, type Lang } from "@/lib/i18n";

/** Pengalih bahasa: tautan ke path yang sama dengan prefiks bahasa lain. */
export function LangToggle({ lang }: { lang: Lang }) {
  const pathname = usePathname() ?? "/";
  const rest = pathname.replace(/^\/(id|en)(?=\/|$)/, "");
  return (
    <div className="inline-flex overflow-hidden rounded-md border border-line text-[11.5px] font-semibold tracking-wide" role="group" aria-label="Language">
      {LANGS.map((l) => (
        <Link
          key={l}
          href={`/${l}${rest}`}
          aria-current={l === lang ? "true" : undefined}
          className={`px-2.5 py-1.5 no-underline ${l === lang ? "bg-accent text-accent-ink" : "text-muted hover:text-fg"}`}
        >
          {l.toUpperCase()}
        </Link>
      ))}
    </div>
  );
}
