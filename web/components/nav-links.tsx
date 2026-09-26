"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

/** Tautan navigasi dengan penanda halaman aktif (garis bawah aksen). */
export function NavLinks({ items, className = "", linkClass = "" }: { items: { href: string; label: string }[]; className?: string; linkClass?: string }) {
  const pathname = usePathname() ?? "";
  return (
    <nav className={className} aria-label="Main">
      {items.map((item) => {
        const isHome = /^\/(id|en)$/.test(item.href);
        const active = isHome ? pathname === item.href : pathname.startsWith(item.href);
        return (
          <Link key={item.href} href={item.href} aria-current={active ? "page" : undefined} className={`nav-link no-underline ${active ? "text-fg" : "text-soft hover:text-fg"} ${linkClass}`}>
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
