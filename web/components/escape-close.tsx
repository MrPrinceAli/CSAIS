"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

/** Tutup panel pop-up dengan tombol Esc: pindah ke alamat tanpa parameter panel. */
export function EscapeClose({ href }: { href: string }) {
  const router = useRouter();
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") router.push(href, { scroll: false });
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [href, router]);
  return null;
}
