"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, ArrowRight, Check, Flag, Radio, ShieldCheck, type LucideIcon } from "lucide-react";
import { api, ApiError } from "../../lib/api";
import { Badge, Button } from "../../components/ui";

const steps: { icon: LucideIcon; title: string; description: string; key: string }[] = [
  { icon: Radio, title: "Your role", description: "Tell us how you'll use PitSense so we can tailor the experience.", key: "role" },
  { icon: Flag, title: "Team context", description: "Optional: add your series, car class, or typical session format.", key: "context" },
  { icon: ShieldCheck, title: "Ready to analyse", description: "You're all set. Open a session and upload your first radio clip.", key: "complete" },
];

type Role = "race_engineer" | "performance_engineer" | "team_principal" | "driver_coach" | "others";
type Context = { series?: string; car_class?: string; session_format?: string };

export default function OnboardingPage() {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [role, setRole] = useState<Role | "">("");
  const [context, setContext] = useState<Context>({ series: "", car_class: "", session_format: "" });

  async function complete() {
    setBusy(true);
    setError("");
    try {
      await api.completeOnboarding();
      router.push("/sessions");
      router.refresh();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : (e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  function nextStep() {
    if (step === 0 && !role) { setError("Select your role to continue."); return; }
    if (step < steps.length - 1) setStep(step + 1);
    else complete();
  }

  function prevStep() {
    if (step > 0) setStep(step - 1);
    else router.push("/sessions");
  }

  return (
    <main className="mx-auto grid min-h-[calc(100vh-128px)] max-w-7xl items-center gap-12 px-6 py-12 lg:grid-cols-[1fr_480px]">
      <section className="hidden max-w-xl lg:block">
        <div className="section-badge">Welcome to PitSense</div>
        <h1 className="mt-6 text-5xl font-bold leading-tight">A quick setup to tailor your race-engineering workspace.</h1>
        <p className="mt-5 text-lg leading-8 text-slate-400">Three short steps. No credit card. You can change everything later in settings.</p>
        <div className="mt-8 h-px bg-gradient-to-r from-cyan/60 to-transparent" />
        <div className="mt-6 flex items-center gap-4">
          {steps.map((_, index) => (
            <div key={index} className="flex items-center gap-2">
              <div className={`w-8 h-8 flex items-center justify-center rounded-full border text-xs font-mono ${index < step ? "border-emerald-400 bg-emerald-400 text-black" : index === step ? "border-cyan bg-cyan/10 text-cyan" : "border-white/15 bg-white/5 text-slate-500"}`}>
                {index < step ? <Check size={14} /> : index + 1}
              </div>
              {index < steps.length - 1 && <div className={`h-1 w-16 ${index < step ? "bg-emerald-400" : "bg-white/10"}`} />}
            </div>
          ))}
        </div>
      </section>

      <section className="telemetry-shell w-full p-6 sm:p-8">
        <div className="section-badge">Setup step {step + 1} of {steps.length}</div>
        <h2 className="mt-5 text-3xl font-bold">{steps[step].title}</h2>
        <p className="mt-2 text-sm leading-6 text-slate-400">{steps[step].description}</p>

        {error && <div className="mt-5"><div role="alert" className="flex gap-3 rounded-lg border border-[rgba(255,92,26,0.35)] bg-[rgba(255,92,26,0.1)] p-4 text-sm text-red-100"><strong className="block text-white">Action needed</strong><span className="mt-1 block leading-5 text-red-100/80">{error}</span></div></div>}

        {step === 0 && (
          <form onSubmit={(e) => { e.preventDefault(); nextStep(); }} className="mt-6 space-y-4">
            <label className="block text-xs text-slate-400">Primary role
              <select required value={role} onChange={(event) => { setRole(event.target.value as Role | ""); setError(""); }} className="field mt-2">
                <option value="" disabled>Select how you use PitSense</option>
                <option value="race_engineer">Race engineer</option>
                <option value="performance_engineer">Performance engineer</option>
                <option value="team_principal">Team principal</option>
                <option value="driver_coach">Driver coach</option>
                <option value="others">Others</option>
              </select>
              <span className="mt-2 block text-[11px] leading-5 text-slate-500">Choose Others for testing, evaluation, research, media, or any role not listed.</span>
            </label>
            <div className="flex justify-between pt-4 border-t border-white/[0.07]">
              <span />
              <Button disabled={busy || !role}>{busy ? "Continuing..." : <>Continue <ArrowRight size={15} /></>}</Button>
            </div>
          </form>
        )}

        {step === 1 && (
          <form onSubmit={(e) => { e.preventDefault(); nextStep(); }} className="mt-6 space-y-4">
            <label className="block text-xs text-slate-400">Championship / series
              <select value={context.series || ""} onChange={e => setContext({ ...context, series: e.target.value })} className="field mt-2">
                <option value="">Select a series (optional)</option>
                <option>Formula 1</option><option>Formula 2 / Formula 3</option><option>Formula E</option>
                <option>FIA WEC</option><option>IMSA</option><option>GT World Challenge / GT3</option>
                <option>IndyCar</option><option>NASCAR</option><option>Club racing / track day</option><option>Others</option>
              </select>
            </label>
            <label className="block text-xs text-slate-400">Car class
              <select value={context.car_class || ""} onChange={e => setContext({ ...context, car_class: e.target.value })} className="field mt-2">
                <option value="">Select a car class (optional)</option>
                <option>Formula</option><option>Prototype / Hypercar</option><option>GT</option>
                <option>Touring car</option><option>Stock car</option><option>Kart</option><option>Road car</option><option>Others</option>
              </select>
            </label>
            <label className="block text-xs text-slate-400">Typical session format
              <select value={context.session_format || ""} onChange={e => setContext({ ...context, session_format: e.target.value })} className="field mt-2">
                <option value="">Select a format (optional)</option>
                <option>Practice</option><option>Qualifying</option><option>Sprint</option><option>Race</option>
                <option>Test day</option><option>Simulation</option><option>Others</option>
              </select>
            </label>
            <p className="text-xs leading-5 text-slate-500">Testers can leave these blank or choose Others. You can update the context later in Settings.</p>
            <div className="flex justify-between pt-4 border-t border-white/[0.07]">
              <Button type="button" variant="ghost" onClick={prevStep}><ArrowLeft size={15} className="mr-1" />Back</Button>
              <Button disabled={busy}>{busy ? "Continuing..." : <>Continue <ArrowRight size={15} /></>}</Button>
            </div>
          </form>
        )}

        {step === 2 && (
          <div className="mt-8 space-y-6">
            <div className="panel p-6 text-center">
              <div className="flex h-14 w-14 mx-auto items-center justify-center rounded-full border border-emerald-400/30 bg-emerald-400/10"><Check className="text-emerald-400" size={24} /></div>
              <h3 className="mt-4 text-xl font-semibold">You're ready to analyse</h3>
              <p className="mt-2 text-sm text-slate-400">Your workspace is configured. Start a session, upload driver radio, and get engineering actions in minutes.</p>
            </div>
            <div className="flex flex-wrap gap-3 justify-center">
              <Button onClick={complete} disabled={busy} className="w-full sm:w-auto">{busy ? "Finishing..." : "Start using PitSense"}</Button>
            </div>
          </div>
        )}
      </section>
    </main>
  );
}
