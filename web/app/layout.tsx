import type { Metadata } from "next";
import Link from "next/link";
import { IBM_Plex_Sans, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { getLastRun } from "@/lib/queries";
import { fmtDateTime } from "@/lib/format";

const plex = IBM_Plex_Sans({
  variable: "--font-plex",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

const jet = JetBrains_Mono({
  variable: "--font-jet",
  subsets: ["latin"],
  weight: ["400", "600"],
});

export const metadata: Metadata = {
  title: { default: "CSAIS", template: "%s · CSAIS" },
  description:
    "Cyber Social Attack Intelligence System: berita serangan siber menjadi incident dan bukti yang bisa diverifikasi.",
};

const NAV = [
  { href: "/", label: "Beranda" },
  { href: "/incident", label: "Incident" },
  { href: "/temuan", label: "Temuan & risiko" },
  { href: "/verifikasi", label: "Verifikasi bukti" },
  { href: "/sumber", label: "Sumber" },
  { href: "/atestasi", label: "Untuk lembaga" },
] as const;

export default async function RootLayout({ children }: LayoutProps<"/">) {
  const lastRun = await getLastRun();
  return (
    <html lang="id" className={`${plex.variable} ${jet.variable} h-full`}>
      <body className="min-h-full flex flex-col">
        <header className="sticky top-0 z-20 border-b border-line bg-nav/95 backdrop-blur">
          <div className="mx-auto flex h-14 w-full max-w-7xl items-center gap-6 px-4 sm:px-6">
            <Link
              href="/"
              className="flex items-center gap-2.5 text-[15px] font-bold tracking-wide text-fg no-underline hover:text-fg"
            >
              <span className="inline-block h-5 w-5 rounded-[5px] bg-accent" aria-hidden="true" />
              CSAIS
            </Link>
            <nav className="hidden items-center gap-5 text-[13.5px] md:flex" aria-label="Menu utama">
              {NAV.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className="text-soft no-underline hover:text-fg"
                >
                  {item.label}
                </Link>
              ))}
            </nav>
            <div className="ml-auto hidden items-center gap-3 sm:flex">
              {lastRun ? (
                <span className="font-mono text-[11.5px] text-muted">
                  data {fmtDateTime(lastRun.finished_at)} · pipeline {lastRun.pipeline_version.split("+")[0]}
                </span>
              ) : null}
            </div>
          </div>
          <nav
            className="mx-auto flex w-full max-w-7xl gap-4 overflow-x-auto px-4 pb-2 text-[13px] md:hidden"
            aria-label="Menu utama (ponsel)"
          >
            {NAV.map((item) => (
              <Link key={item.href} href={item.href} className="whitespace-nowrap text-soft no-underline">
                {item.label}
              </Link>
            ))}
          </nav>
        </header>

        <div className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6">{children}</div>

        <footer className="border-t border-line">
          <div className="mx-auto flex w-full max-w-7xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-5 text-[12.5px] text-muted sm:px-6">
            <span>CSAIS · Cyber Social Attack Intelligence System</span>
            <span>Pekerja otomatis membaca berita tiap hari pukul 04:00 WIB; hasil disalin ke Turso dan dibaca halaman ini.</span>
            <Link href="/verifikasi" className="ml-auto no-underline">
              Cara memverifikasi
            </Link>
          </div>
        </footer>
      </body>
    </html>
  );
}
