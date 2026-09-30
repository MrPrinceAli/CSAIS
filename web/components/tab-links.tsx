"use client";

/* Tab halaman bertingkat (Transparansi): aktif bila alamatnya sama persis. */
import Link from "next/link";
import { usePathname } from "next/navigation";

export function TabLinks({ items, label }: { items: { href: string; label: string }[]; label: string }) {
  const pathname = usePathname() ?? "";
  return (
    <nav className="flex flex-wrap gap-1 border-b border-line" aria-label={label}>
      {items.map((item) => {
        const active = pathname === item.href;
        return (
          <Link
            key={item.href}
            href={item.href}
            aria-current={active ? "page" : undefined}
            className={`-mb-px border-b-2 px-3 py-2 text-[13.5px] no-underline ${active ? "border-accent text-fg" : "border-transparent text-muted hover:text-fg"}`}
          >
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
