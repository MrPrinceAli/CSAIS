/*
 * Foto latar kartu "Langkah pencegahan per kelompok": foto nyata tiap kelompok
 * sasaran (public/groups/, dari Wikimedia Commons) di bagian atas kartu yang
 * memudar ke warna kartu, diberi rona warna tingkat risiko. Kredit tiap foto
 * ada di lib/group-photos.json dan ditampilkan di bawah daftar kartu.
 */
import Image from "next/image";
import photos from "@/lib/group-photos.json";

export type PhotoCredit = { title: string; author: string; license: string; url: string };
export const GROUP_PHOTOS = photos as Record<string, PhotoCredit>;

export function GroupPhoto({ group, color }: { group: string; color: string }) {
  if (!GROUP_PHOTOS[group]) return null;
  return (
    <div aria-hidden="true" className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-[230px] overflow-hidden">
      <Image src={`/groups/${group.toLowerCase()}.jpg`} alt="" fill sizes="(min-width: 1280px) 420px, (min-width: 768px) 50vw, 100vw" className="object-cover opacity-90" />
      <div
        className="absolute inset-0"
        style={{
          background: `linear-gradient(180deg, color-mix(in srgb, var(--surface) 10%, transparent) 0%, color-mix(in srgb, var(--surface) 45%, transparent) 40%, color-mix(in srgb, var(--surface) 88%, transparent) 75%, var(--surface) 100%),
            linear-gradient(90deg, color-mix(in srgb, var(--surface) 70%, transparent) 0%, transparent 60%),
            color-mix(in srgb, ${color} 8%, transparent)`,
        }}
      />
    </div>
  );
}
