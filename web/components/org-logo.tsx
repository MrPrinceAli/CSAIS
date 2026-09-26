import Image from "next/image";

/** Logo resmi lembaga (public/logos, dari Wikimedia Commons) di atas ubin terang agar terbaca di tema gelap. */
const LOGOS: Record<string, string> = {
  BSSN: "/logos/bssn.png",
  OJK: "/logos/ojk.png",
  Polri: "/logos/polri.png",
  Komdigi: "/logos/komdigi.png",
};

export function OrgLogo({ org, size = 48, className = "" }: { org: string; size?: number; className?: string }) {
  const src = LOGOS[org];
  if (!src) return <span className="chip">{org}</span>;
  return (
    <span className={`inline-flex flex-none items-center justify-center rounded-md border border-line bg-white p-1.5 ${className}`} style={{ width: size + 12, height: size + 12 }} title={org}>
      <Image src={src} alt={org} width={size} height={size} className="h-full w-full object-contain" />
    </span>
  );
}

export const ORGS = Object.keys(LOGOS);
