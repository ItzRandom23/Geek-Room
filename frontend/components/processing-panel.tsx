"use client";

import { CSSProperties } from "react";
import { AudioWaveform, BrainCircuit, Check, CircleDashed, Gauge, Radio, ScanLine, ShieldCheck, XCircle } from "lucide-react";
import { AnalysisJob } from "../lib/api";
import { GhostButton } from "./ui";

export const processingPhases = [
  { id: "decoding", label: "Decode", detail: "Preparing the radio signal", icon: Radio },
  { id: "transcribing", label: "Transcript", detail: "Resolving spoken context", icon: AudioWaveform },
  { id: "extracting_features", label: "Features", detail: "Reading vocal and acoustic cues", icon: ScanLine },
  { id: "classifying", label: "Classify", detail: "Comparing trained driver states", icon: BrainCircuit },
  { id: "calibrating", label: "Calibrate", detail: "Applying the confidence gate", icon: Gauge },
  { id: "correlating", label: "Correlate", detail: "Aligning events with lap context", icon: ShieldCheck },
] as const;

export function getProcessingState(job: AnalysisJob) {
  const progress = Math.max(0, Math.min(100, job.progress ?? 0));
  const phaseIndex = processingPhases.findIndex((phase) => phase.id === job.phase);
  const activeIndex = phaseIndex >= 0 ? phaseIndex : job.status === "queued" ? -1 : processingPhases.length - 1;
  const terminal = ["completed", "failed", "cancelled"].includes(job.status);
  return { progress, activeIndex, terminal };
}

export function ProcessingPanel({ job, onCancel }: { job: AnalysisJob; onCancel: () => void }) {
  const { progress, activeIndex } = getProcessingState(job);
  const running = job.status === "queued" || job.status === "running";
  const failed = job.status === "failed";
  const cancelled = job.status === "cancelled";
  const activePhase = processingPhases[activeIndex];
  const statusTitle = failed ? "Analysis interrupted" : cancelled ? "Analysis cancelled" : activePhase?.detail || "Waiting for the analysis worker";
  const waveformHeights = [12, 22, 31, 18, 38, 25, 44, 30, 18, 35, 24, 40, 28, 16, 32, 20, 12];

  return (
    <section
      role="status"
      aria-live="polite"
      aria-atomic="true"
      className={`analysis-processing panel glass-edge mt-5 overflow-hidden p-5 ${failed ? "analysis-processing-error" : ""}`}
      style={{ "--analysis-progress": `${progress * 3.6}deg` } as CSSProperties}
    >
      <div className="analysis-scan" aria-hidden="true" />
      <div className="relative grid items-center gap-7 lg:grid-cols-[210px_1fr_auto]">
        <div className="analysis-core mx-auto" aria-label={`${progress}% complete`}>
          <div className="analysis-core-inner">
            {failed || cancelled ? <XCircle size={28} className={failed ? "text-signal" : "text-slate-400"} /> : <AudioWaveform size={27} className="text-cyan" />}
            <strong className="font-display text-3xl">{progress}%</strong>
            <span className="font-mono text-[9px] uppercase text-slate-500">signal processed</span>
          </div>
          <div className="analysis-orbit-marker" aria-hidden="true" />
        </div>

        <div className="min-w-0">
          <div className="eyebrow">Step 5 / live processing</div>
          <h2 className="mt-3 text-xl font-bold">{statusTitle}</h2>
          <p className="mt-2 text-sm leading-6 text-slate-400">
            {failed
              ? job.error?.message || "The worker could not complete this analysis."
              : cancelled
                ? "The uploaded audio is unchanged and ready to analyse again."
                : "Measured probabilities are calibrated against the promoted model. Low-confidence audio resolves to uncertain."}
          </p>
          <div className="analysis-waveform mt-5" aria-hidden="true">
            {waveformHeights.map((height, index) => <span key={index} style={{ height, animationDelay: `${index * -55}ms` }} />)}
          </div>
          <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-white/5">
            <div className="analysis-progress h-full rounded-full" style={{ width: `${progress}%` }} />
          </div>
        </div>

        {running && <GhostButton onClick={onCancel}>Cancel analysis</GhostButton>}
      </div>

      <ol className="analysis-phases relative mt-7 grid gap-2 sm:grid-cols-3 lg:grid-cols-6" aria-label="Analysis phases">
        {processingPhases.map((phase, index) => {
          const complete = job.status === "completed" || index < activeIndex;
          const active = running && index === activeIndex;
          const Icon = phase.icon;
          return (
            <li key={phase.id} className={`analysis-phase ${complete ? "is-complete" : ""} ${active ? "is-active" : ""}`}>
              <span className="analysis-phase-icon">{complete ? <Check size={14} /> : active ? <Icon size={14} /> : <CircleDashed size={14} />}</span>
              <span className="font-mono text-[10px] uppercase">{phase.label}</span>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
