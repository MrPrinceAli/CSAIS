import Link from "next/link";

export default function NotFound() {
  return (
    <div className="flex flex-col items-start gap-3 py-16">
      <span className="label">404</span>
      <h1 className="text-[24px] font-semibold">Halaman tidak ditemukan · Page not found</h1>
      <p className="text-[14px] text-soft">Tautan yang Anda buka tidak ada atau sudah dipindahkan. The link you opened does not exist or has moved.</p>
      <div className="flex gap-3">
        <Link href="/id" className="btn btn-ghost">
          Beranda
        </Link>
        <Link href="/en" className="btn btn-ghost">
          Home
        </Link>
      </div>
    </div>
  );
}
