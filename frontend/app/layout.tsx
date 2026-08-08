import type { Metadata } from "next";
import Link from "next/link";
import { Activity, BookOpen, Flag, LogIn } from "lucide-react";
import "./globals.css";

export const metadata: Metadata = { title: "PitSense AI", description: "Race engineer intelligence from driver radio." };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body><header className="border-b border-line bg-ink/95"><div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4"><Link href="/" className="flex items-center gap-3"><span className="flex h-9 w-9 items-center justify-center rounded-lg bg-signal text-white"><Flag size={18}/></span><span className="font-semibold tracking-tight">PitSense <span className="text-cyan">AI</span></span></Link><nav className="flex items-center gap-5 text-sm text-slate-400"><Link className="hover:text-white" href="/sessions"><Activity size={15} className="mr-1 inline"/>Sessions</Link><Link className="hover:text-white" href="/methodology"><BookOpen size={15} className="mr-1 inline"/>Methodology</Link><Link className="hover:text-white" href="/login"><LogIn size={15} className="mr-1 inline"/>Team access</Link></nav></div></header>{children}<footer className="mx-auto max-w-7xl border-t border-line px-6 py-8 text-xs text-slate-500">PitSense AI · race-performance decision support · associations, not diagnoses</footer></body></html>;
}
