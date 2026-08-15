import type { Metadata } from "next";
import InteractiveBackground from "../components/interactive-background";
import AppShell from "../components/app-shell";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000"),
  title: "PitSense AI | Race intelligence from driver radio",
  description: "Turn driver radio, vocal state, and lap context into clear race-engineering actions.",
  icons: { icon: "/pitsense-logo.png", shortcut: "/pitsense-logo.png", apple: "/pitsense-logo.png" },
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
    <html lang="en" data-scroll-behavior="smooth">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Outfit:wght@300;400;500;600;700;800&family=Space+Grotesk:wght@500;600;700&display=swap" rel="stylesheet" />
      </head>
      <body>
        <InteractiveBackground />
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
