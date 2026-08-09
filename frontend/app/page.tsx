import type { CSSProperties } from "react";
import Link from "next/link";
import { Activity, ArrowRight, AudioLines, BrainCircuit, Gauge, Radio, ShieldCheck, Timer, Zap, type LucideIcon } from "lucide-react";

const workflow: { icon: LucideIcon; num: string; title: string; copy: string }[] = [
  { icon: AudioLines, num: "01", title: "Capture the radio", copy: "Upload the driver channel and preserve every word as timestamped, playable evidence." },
  { icon: BrainCircuit, num: "02", title: "Detect the pressure", copy: "Speech and vocal-state models surface stress, urgency, fatigue, and uncertainty." },
  { icon: Gauge, num: "03", title: "Connect the lap", copy: "Events align with timing deltas to produce a clear, inspectable engineering action." },
];

const wave = [12, 20, 31, 18, 27, 34, 16, 24, 32, 14, 29, 21, 35, 18, 26, 13, 30, 22, 34, 17, 27, 14, 23, 31];

export default function Home() {
  return (
    <main>
      <section className="hero-grid mx-auto grid max-w-7xl gap-12 px-6 pb-16 pt-14 lg:grid-cols-[1.02fr_.98fr] lg:items-center lg:pb-20 lg:pt-20">
        <div className="max-w-2xl">
          <div className="section-badge reveal">
            <span className="signal-dot" />
            Live race intelligence
          </div>
          <h1 className="reveal reveal-delay-1 mt-6 text-5xl font-bold leading-[1.02] md:text-6xl lg:text-[4.4rem]">
            Hear the signal.<br />
            <span className="text-gradient-orange">Change the lap.</span>
          </h1>
          <p className="reveal reveal-delay-2 mt-6 max-w-xl text-lg leading-8 text-slate-400">
            PitSense turns driver radio into a live performance layer, combining transcript, vocal state, lap context, and the next engineering action.
          </p>
          <div className="reveal reveal-delay-3 mt-8 flex flex-wrap gap-3">
            <Link href="/sessions" className="btn-glow text-base">
              Analyse radio <ArrowRight size={17} />
            </Link>
            <Link href="/sessions?demo=1" className="btn-ghost text-base">
              <Activity size={17} /> View live demo
            </Link>
          </div>
          <div className="reveal reveal-delay-3 mt-8 flex flex-wrap gap-x-6 gap-y-3 border-t border-white/[0.07] pt-5 font-mono text-[10px] uppercase text-slate-500">
            <span className="flex items-center gap-2"><ShieldCheck size={14} className="text-cyan" /> Private backend inference</span>
            <span className="flex items-center gap-2"><Timer size={14} className="text-cyan" /> Timestamp accurate</span>
          </div>
        </div>

        <div className="telemetry-shell">
          <div className="flex items-center justify-between border-b border-white/[0.08] px-5 py-4">
            <div className="flex items-center gap-3">
              <span className="flex h-8 w-8 items-center justify-center rounded-lg border border-cyan/20 bg-cyan/[0.07] text-cyan"><Radio size={15} /></span>
              <div>
                <p className="font-mono text-[9px] uppercase text-slate-500">Driver channel / 44.1 kHz</p>
                <p className="mt-0.5 text-xs font-semibold text-slate-200">MONZA / SESSION 03</p>
              </div>
            </div>
            <div className="flex items-center gap-2 font-mono text-[9px] uppercase text-[#ff8958]"><span className="signal-dot" /> Analysing</div>
          </div>

          <div className="grid gap-6 p-5 sm:grid-cols-[1fr_auto] sm:p-6">
            <div>
              <div className="flex items-center justify-between font-mono text-[9px] uppercase text-slate-500">
                <span>Vocal state</span><span>00:15.24</span>
              </div>
              <div className="mt-3 flex items-end gap-3">
                <strong className="font-display text-4xl text-[#ff7840]">STRESSED</strong>
                <span className="mb-1 font-mono text-xs text-slate-400">86%</span>
              </div>
              <div className="mt-4 metric-line" />
              <p className="mt-4 max-w-sm text-sm leading-6 text-slate-300">“Front lock. The car is nervous on entry.”</p>
            </div>
            <div className="flex flex-col items-start sm:items-end">
              <span className="font-mono text-[9px] uppercase text-slate-500">Signal waveform</span>
              <div className="waveform mt-3" aria-hidden="true">
                {wave.map((height, index) => <span key={index} style={{ "--h": `${height}px`, "--d": `${index * -0.06}s` } as CSSProperties} />)}
              </div>
            </div>
          </div>

          <div className="telemetry-row grid grid-cols-3 divide-x divide-white/[0.07]">
            <div className="p-4"><p className="font-mono text-[9px] uppercase text-slate-500">Lap delta</p><p className="mt-2 font-display text-xl font-semibold text-[#ff7840]">+3.80s</p></div>
            <div className="p-4"><p className="font-mono text-[9px] uppercase text-slate-500">Event</p><p className="mt-2 font-display text-xl font-semibold">L04</p></div>
            <div className="p-4"><p className="font-mono text-[9px] uppercase text-slate-500">Confidence</p><p className="mt-2 font-display text-xl font-semibold text-cyan">0.86</p></div>
          </div>

          <div className="telemetry-row flex items-start gap-3 px-5 py-4">
            <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border border-[#ff7840]/20 bg-[#ff7840]/[0.08] text-[#ff7840]"><Zap size={14} /></span>
            <div><p className="font-mono text-[9px] uppercase text-slate-500">Engineer action</p><p className="mt-1 text-sm font-medium text-slate-200">Reduce non-critical radio. Review brake migration before the next run.</p></div>
          </div>
        </div>
      </section>

      <section className="border-y border-white/[0.07] bg-black/10">
        <div className="mx-auto grid max-w-7xl px-6 md:grid-cols-[.8fr_1.2fr]">
          <div className="py-12 pr-0 md:border-r md:border-white/[0.07] md:pr-12">
            <div className="section-badge">Signal chain</div>
            <h2 className="mt-5 max-w-sm text-3xl font-bold leading-tight">From a tense sentence to a useful decision.</h2>
            <p className="mt-4 max-w-md text-sm leading-6 text-slate-400">Every recommendation remains connected to the original audio, model confidence, and lap evidence.</p>
          </div>
          <div className="py-8 md:pl-10">
            {workflow.map(({ icon: Icon, num, title, copy }) => (
              <article className="process-line relative flex gap-5 py-4" key={num}>
                <span className="relative z-10 flex h-[50px] w-[50px] shrink-0 items-center justify-center rounded-lg border border-cyan/20 bg-[#0a1014] text-cyan shadow-[0_0_24px_rgba(83,230,225,.07)]"><Icon size={19} /></span>
                <div className="pt-1"><p className="font-mono text-[9px] text-slate-600">/{num}</p><h3 className="mt-1 font-display text-lg font-semibold">{title}</h3><p className="mt-1 max-w-xl text-sm leading-6 text-slate-400">{copy}</p></div>
              </article>
            ))}
          </div>
        </div>
      </section>
    </main>
  );
}
