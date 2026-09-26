"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef } from "react";

type Labels = { close: string; full: string; esc: string };

/**
 * Jendela pop-up detail incident di atas dasbor. Tutup lewat tombol, klik di
 * luar jendela, atau Esc; menutup berarti kembali satu langkah riwayat,
 * sehingga dasbor beserta filternya tetap seperti semula.
 */
export function IncidentModal({ id, fullHref, labels, children }: { id: string; fullHref: string; labels: Labels; children: React.ReactNode }) {
  const router = useRouter();
  const panelRef = useRef<HTMLDivElement>(null);
  const close = useCallback(() => router.back(), [router]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      // fase capture: Esc tidak ikut menutup panel daftar incident di belakangnya
      e.preventDefault();
      e.stopImmediatePropagation();
      close();
    };
    window.addEventListener("keydown", onKey, true);
    const previous = document.activeElement as HTMLElement | null;
    panelRef.current?.focus({ preventScroll: true });
    return () => {
      window.removeEventListener("keydown", onKey, true);
      previous?.focus?.({ preventScroll: true });
    };
  }, [close]);

  useEffect(() => {
    panelRef.current?.querySelector(".im-body")?.scrollTo({ top: 0 });
  }, [id]);

  return (
    <div className="im-root" role="dialog" aria-modal="true" aria-labelledby="im-title">
      <button type="button" className="im-backdrop" onClick={close} aria-label={labels.close} tabIndex={-1} />
      <div ref={panelRef} className="im-panel" tabIndex={-1}>
        <header className="im-bar">
          <span className="im-led" aria-hidden="true" />
          <span id="im-title" className="im-id">
            {id}
          </span>
          <span className="im-hint">{labels.esc}</span>
          <a href={fullHref} className="btn btn-ghost px-3 py-1.5 text-[12.5px]">
            {labels.full} ↗
          </a>
          <button type="button" onClick={close} className="btn btn-ghost px-3 py-1.5 text-[12.5px]" autoFocus>
            {labels.close} ✕
          </button>
        </header>
        <div className="im-body cc-scroll">{children}</div>
      </div>
    </div>
  );
}
