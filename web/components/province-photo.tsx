/*
 * Foto ikonik provinsi untuk kepala pop-up Peta Literasi (public/provinces/,
 * dari Wikimedia Commons), memudar ke kiri dan ke bawah agar teks tetap
 * terbaca. Kredit tiap foto ada di lib/province-photos.json dan wajib tampil.
 */
import Image from "next/image";
import photos from "@/lib/province-photos.json";

export type ProvincePhotoInfo = { label: string; title: string; author: string; license: string; url: string };
const PHOTOS = photos.provinces as Record<string, ProvincePhotoInfo>;

export function provincePhoto(code: string): ProvincePhotoInfo | null {
  return PHOTOS[code] ?? null;
}

export function ProvincePhoto({ code }: { code: string }) {
  if (!PHOTOS[code]) return null;
  return (
    <div aria-hidden="true" className="pointer-events-none absolute inset-0 -z-10">
      <Image src={`/provinces/${code}.jpg`} alt="" fill sizes="(min-width: 1280px) 1280px, 100vw" className="object-cover object-center" priority />
      <div
        className="absolute inset-0"
        style={{
          background:
            "linear-gradient(90deg, var(--surface) 0%, color-mix(in srgb, var(--surface) 88%, transparent) 30%, color-mix(in srgb, var(--surface) 35%, transparent) 65%, transparent 100%), linear-gradient(0deg, var(--surface) 0%, transparent 55%)",
        }}
      />
    </div>
  );
}
