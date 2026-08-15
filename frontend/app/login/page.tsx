"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Building2, Eye, EyeOff, LockKeyhole, Mail, UserRound } from "lucide-react";
import { api, ApiError, setToken } from "../../lib/api";
import { Button, ErrorBox } from "../../components/ui";

export default function LoginPage() {
  const router = useRouter();
  const [register, setRegister] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(false);
  const [form, setForm] = useState({ email: "", password: "", full_name: "", organization_name: "" });

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const result = register ? await api.register(form) : await api.login({ email: form.email, password: form.password });
      setToken(result.access_token);
      if (result.user.onboarding_completed) router.push("/sessions");
      else router.push("/onboarding");
    } catch (error) {
      setError(error instanceof ApiError ? error.message : (error as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto grid min-h-[calc(100vh-128px)] max-w-7xl items-center gap-12 px-6 py-12 lg:grid-cols-[1fr_440px]">
      <section className="hidden max-w-xl lg:block">
        <div className="section-badge">Secure paddock access</div>
        <h1 className="mt-6 text-5xl font-bold leading-tight">Your team&apos;s radio intelligence, isolated and inspectable.</h1>
        <p className="mt-5 text-lg leading-8 text-slate-400">Audio, transcripts, lap data, and reports remain scoped to your organization.</p>
        <div className="mt-8 h-px bg-gradient-to-r from-cyan/60 to-transparent" />
      </section>
      <section className="telemetry-shell w-full p-6 sm:p-8">
        <div className="section-badge">Team access</div>
        <h2 className="mt-5 text-3xl font-bold">{register ? "Create your team" : "Welcome back"}</h2>
        <p className="mt-2 text-sm leading-6 text-slate-400">{register ? "Set up a private race-engineering workspace." : "Sign in to continue to race operations."}</p>
        {error && <div className="mt-5"><ErrorBox message={error} /></div>}
        <form onSubmit={submit} className="mt-6 space-y-4">
          {register && <>
            <label className="block text-xs text-slate-400"><span className="flex items-center gap-2"><UserRound size={13} />Your name</span><input required autoComplete="name" placeholder="Alex Morgan" value={form.full_name} onChange={e => setForm({ ...form, full_name: e.target.value })} className="field mt-2" /></label>
            <label className="block text-xs text-slate-400"><span className="flex items-center gap-2"><Building2 size={13} />Team name</span><input required autoComplete="organization" placeholder="Apex Motorsport" value={form.organization_name} onChange={e => setForm({ ...form, organization_name: e.target.value })} className="field mt-2" /></label>
          </>}
          <label className="block text-xs text-slate-400"><span className="flex items-center gap-2"><Mail size={13} />Email</span><input required type="email" autoComplete="email" placeholder="engineer@team.com" value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} className="field mt-2" /></label>
          <label className="block text-xs text-slate-400">
            <span className="flex items-center gap-2"><LockKeyhole size={13} />Password</span>
            <div className="relative mt-2">
              <input required minLength={8} type={showPassword ? "text" : "password"} autoComplete={register ? "new-password" : "current-password"} placeholder="8+ characters" value={form.password} onChange={e => setForm({ ...form, password: e.target.value })} className="field pr-12" />
              <button type="button" onClick={() => setShowPassword(!showPassword)} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white">
                {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>
          </label>
          {!register && (
            <label className="flex items-center gap-2 text-sm text-slate-300 cursor-pointer">
              <input type="checkbox" checked={rememberMe} onChange={e => setRememberMe(e.target.checked)} className="rounded border-line bg-ink accent-cyan h-4 w-4" />
              Remember me
            </label>
          )}
          <Button className="w-full" disabled={busy}>{busy ? (register ? "Creating..." : "Signing in...") : (register ? "Create team account" : "Sign in")}</Button>
        </form>
        <button type="button" onClick={() => { setRegister(!register); setError(""); setShowPassword(false); }} className="mt-5 w-full text-sm font-medium text-cyan transition hover:text-white">
          {register ? "Already have an account? Sign in" : "New to PitSense? Create a team"}
        </button>
        <Link href="/" className="mt-5 flex items-center justify-center gap-2 text-xs text-slate-500 transition hover:text-slate-300"><ArrowLeft size={13} />Back to home</Link>
      </section>
    </main>
  );
}
