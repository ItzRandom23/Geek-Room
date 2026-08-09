import type { Metadata } from "next";
import Link from "next/link";
import { Activity, BookOpen, Flag, LogIn } from "lucide-react";
import InteractiveBackground from "../components/interactive-background";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000"),
  title: "PitSense AI | Race intelligence from driver radio",
  description: "Turn driver radio, vocal state, and lap context into clear race-engineering actions.",
  openGraph: {
    title: "PitSense AI",
    description: "Hear the signal. Change the lap.",
    images: [{ url: "/og.png", width: 1792, height: 925, alt: "PitSense AI race intelligence dashboard" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "PitSense AI",
    description: "Hear the signal. Change the lap.",
    images: ["/og.png"],
  },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Outfit:wght@300;400;500;600;700;800&family=Space+Grotesk:wght@500;600;700&display=swap" rel="stylesheet" />
      </head>
      <body>
        <InteractiveBackground />
        <header className="site-header sticky top-0 z-50 border-b border-white/[0.06]">
          <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6">
            <Link href="/" aria-label="PitSense AI home" className="group flex items-center gap-3">
              <span className="brand-mark flex h-9 w-9 items-center justify-center rounded-lg">
                <Flag size={17} className="relative z-10 text-cyan" />
              </span>
              <span className="font-display text-[15px] font-bold text-white sm:text-base">PITSENSE <span className="text-gradient-blue">AI</span></span>
            </Link>
            <nav aria-label="Primary navigation" className="flex items-center gap-1 text-sm">
              <Link className="site-nav-link" href="/sessions" title="Sessions"><Activity size={15} className="text-cyan" /><span className="nav-label">Sessions</span></Link>
              <Link className="site-nav-link" href="/methodology" title="Methodology"><BookOpen size={15} className="text-cyan" /><span className="nav-label">Methodology</span></Link>
              <Link className="site-nav-link" href="/login" title="Team access"><LogIn size={15} className="text-cyan" /><span className="nav-label">Team access</span></Link>
            </nav>
          </div>
        </header>
        {children}
        <footer className="relative z-10 mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 border-t border-white/[0.07] px-6 py-7 font-mono text-[10px] uppercase text-slate-600">
          <span>PitSense AI / Race-performance decision support</span>
          <span>Association, not diagnosis</span>
        </footer>
      </body>
    </html>
  );
}
