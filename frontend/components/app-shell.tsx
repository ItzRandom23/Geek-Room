"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Activity, BarChart3, BookOpen, LogIn, LogOut, UserRound } from "lucide-react";
import { api, ApiError, getToken, setToken } from "../lib/api";

type AccessState = "checking" | "public" | "authenticated" | "error";

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const publicRoute = pathname === "/" || pathname === "/login";
  const [access, setAccess] = useState<AccessState>(publicRoute ? "public" : "checking");
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function verifyAccess() {
      setError("");
      const token = getToken();
      if (!token) {
        if (publicRoute) setAccess("public");
        else {
          setAccess("checking");
          router.replace("/login");
        }
        return;
      }

      setAccess("checking");
      try {
        const result = await api.me();
        if (cancelled) return;
        if (!result.authenticated || !result.user) throw new ApiError("Your session has expired.", "UNAUTHENTICATED", false, 401);
        if (!result.user.onboarding_completed && pathname !== "/onboarding") {
          router.replace("/onboarding");
          return;
        }
        if (result.user.onboarding_completed && (pathname === "/login" || pathname === "/onboarding")) {
          router.replace("/sessions");
          return;
        }
        setAccess("authenticated");
      } catch (cause) {
        if (cancelled) return;
        if (cause instanceof ApiError && cause.status === 401) {
          setToken(null);
          if (publicRoute) setAccess("public");
          else router.replace("/login");
          return;
        }
        if (publicRoute) {
          setAccess("public");
          return;
        }
        setError(cause instanceof Error ? cause.message : "Unable to verify your account.");
        setAccess("error");
      }
    }

    verifyAccess();
    return () => { cancelled = true; };
  }, [pathname, publicRoute, router]);

  function signOut() {
    setToken(null);
    setAccess("public");
    router.replace("/login");
  }

  const showProtectedContent = access === "authenticated";
  const showPublicContent = publicRoute && access === "public";

  return <>
    <header className="site-header sticky top-0 z-50 border-b border-white/[0.06]">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6">
        <Link href={showProtectedContent ? "/sessions" : "/"} aria-label="PitSense AI" className="group flex items-center gap-3">
          <span className="brand-mark flex h-10 w-10 items-center justify-center rounded-lg">
            <Image src="/pitsense-logo.png" alt="" width={36} height={36} priority className="relative z-10 object-contain" />
          </span>
          <span className="whitespace-nowrap font-display text-[15px] font-bold text-white sm:text-base">PITSENSE <span className="text-gradient-blue">AI</span></span>
        </Link>
        {showProtectedContent && <nav aria-label="Primary navigation" className="flex items-center gap-1 text-sm">
          <Link className="site-nav-link" href="/sessions" title="Dashboard"><Activity size={15} className="text-cyan" /><span className="nav-label">Dashboard</span></Link>
          <Link className="site-nav-link" href="/analytics" title="Analytics"><BarChart3 size={15} className="text-cyan" /><span className="nav-label">Analytics</span></Link>
          <Link className="site-nav-link" href="/methodology" title="Methodology"><BookOpen size={15} className="text-cyan" /><span className="nav-label">Methodology</span></Link>
          <Link className="site-nav-link" href="/settings" title="Settings"><UserRound size={15} className="text-cyan" /><span className="nav-label">Settings</span></Link>
          <button type="button" className="site-nav-link" title="Sign out" onClick={signOut}><LogOut size={15} className="text-cyan" /><span className="nav-label">Sign out</span></button>
        </nav>}
        {showPublicContent && pathname === "/" && <nav aria-label="Public navigation" className="flex items-center gap-1 text-sm">
          <a className="site-nav-link public-nav-secondary" href="#workflow">How it works</a>
          <a className="site-nav-link public-nav-secondary" href="#analysis-modes">Analysis modes</a>
          <Link className="site-nav-link whitespace-nowrap border-cyan/20 text-cyan" href="/login"><LogIn size={15} /><span>Sign in</span></Link>
        </nav>}
      </div>
    </header>

    {showProtectedContent || showPublicContent ? children : (
      <main className="relative z-10 mx-auto flex min-h-[calc(100vh-128px)] max-w-7xl items-center justify-center px-6 py-20">
        {access === "error" ? <div className="telemetry-shell max-w-lg p-7 text-center"><h1 className="text-xl font-bold">Access check unavailable</h1><p className="mt-3 text-sm leading-6 text-slate-400">{error}</p><button type="button" className="btn-glow mt-5" onClick={() => window.location.reload()}>Try again</button></div> : <div className="font-mono text-xs uppercase tracking-[0.18em] text-slate-400">Verifying secure access…</div>}
      </main>
    )}

    {(showProtectedContent || showPublicContent) && <footer className="relative z-10 mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 border-t border-white/[0.07] px-6 py-7 font-mono text-[10px] uppercase text-slate-600">
      <span>PitSense AI / Race-performance decision support</span>
      <span>Association, not diagnosis</span>
    </footer>}
  </>;
}
